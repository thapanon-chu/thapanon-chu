"""AI Concrete v2 — data loader + execution simulator (the official scoring rules).

Python 3.9+ standard library only. The organisers score every team with this same file; the only difference
is that they pass the *true* plant capacity (`truth.json`) instead of what plants.csv says.

Data layout:  data/common/*.csv  (city, plants, products, sites, customers, routes, costs)
              data/dayN_xxx/*.csv (planner orders + plan, traffic events, plant status, trucks available)
Time is minutes after midnight in the code, "HH:MM" in every CSV.
"""
from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass, field

# ------------------------------------------------------------------ fixed operating rules
WASH_MIN = 10            # wash-out at site after discharge
ON_TIME_TOL = 15         # first load on time when |arrival - requested| <= 15 min
TRUCK_DAY_START = 5 * 60 # trucks may leave their home plant from 05:00 (morning repositioning)
RED_SHARE = 0.5          # continuity colour: GREEN no load over, YELLOW <= 50 % of loads over, RED > 50 %

GRADES = {  # grade: (name, on-time target, continuity GREEN target, max gap min, weight)
    1: ("Blue Diamond", 0.95, 1.00, 5, 7.0),
    2: ("Platinum", 0.90, 0.95, 10, 5.0),
    3: ("Gold", 0.85, 0.90, 15, 4.0),
    4: ("Silver", 0.80, 0.85, 20, 3.0),
    5: ("Bronze", 0.75, 0.80, 25, 2.0),
    6: ("Standard", 0.70, 0.75, 30, 1.5),
    7: ("Basic", 0.65, 0.70, 40, 1.0),
}


def t2m(s) -> int:
    s = str(s).strip()
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def m2t(m: float) -> str:
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def windows(text):
    """'07:00-09:00|16:00-19:00' -> [(420, 540), (960, 1140)]"""
    out = []
    for part in str(text or "").split("|"):
        if "-" in part:
            a, b = part.split("-")
            out.append((t2m(a), t2m(b)))
    return out


# ------------------------------------------------------------------ data
@dataclass
class Day:
    folder: str
    info: dict
    day_type: str
    plants: dict
    products: dict
    plant_product: dict   # (plant_id, product_id) -> material cost ฿/m3 (missing = cannot produce)
    sites: dict
    customers: dict
    orders: dict          # order_id -> [stream_id, ...]
    streams: dict         # stream_id -> dict (one pour line)
    trucks: dict          # only trucks available today
    trucks_off: set
    travel: dict          # (from, to) -> dict(km, offpeak, normal, peak, holiday)
    periods: list         # [(start, end, period)] for this day_type
    events: list          # [dict(zones:set, start, end, factor, reason)]
    status: list          # [dict(plant_id, start, end, lines, note)]
    cost: dict


def load_day(folder: str, truth: str | None = None) -> Day:
    folder = os.path.abspath(folder)
    common = os.path.join(os.path.dirname(folder), "common")
    c = lambda n: os.path.join(common, n)
    d = lambda n: os.path.join(folder, n)
    info = {r["key"]: r["value"] for r in read_csv(d("day_info.csv"))}
    plants = {r["plant_id"]: r for r in read_csv(c("plants.csv"))}
    for p in plants.values():
        for k in ("lines", "prep_min", "mix_load_min", "qc_min", "boost_max_lines"):
            p[k] = int(p.get(k) or 0)
        p["boost_cost_per_hour"] = float(p.get("boost_cost_per_hour") or 0)
        p["open_m"], p["close_m"] = t2m(p["open"]), t2m(p["close"])
    if truth:  # organisers: real capacity overrides what the system says
        with open(truth, encoding="utf-8") as f:
            for pid, lines in json.load(f)["true_lines"].items():
                plants[pid]["lines"] = int(lines)
    products = {r["product_id"]: r for r in read_csv(c("products.csv"))}
    for p in products.values():
        p["concrete_life_min"] = int(p["concrete_life_min"])
    plant_product = {(r["plant_id"], r["product_id"]): float(r["material_cost_per_m3"])
                     for r in read_csv(c("plant_product_cost.csv")) if r["can_produce"] == "1"}
    sites = {r["site_id"]: r for r in read_csv(c("sites.csv"))}
    for s in sites.values():
        s["no_entry"] = windows(s.get("no_entry_windows"))
        s["tags"] = {s["zone"], "ALL"} | ({"SCHOOL"} if s.get("school_zone") == "1" else set())
        s["access_min"] = float(s.get("access_min") or 0)
        s["max_queue"] = int(s.get("max_queue") or 99)
    # day-specific site closures / bans (e.g. festival road closure) are added from traffic_events
    customers = {r["customer_id"]: r for r in read_csv(c("customers.csv"))}
    for cu in customers.values():
        cu["grade"] = int(cu["grade"])
        cu["site_delay_min"] = int(cu["site_delay_min"] or 0)
        cu["pour_factor"] = float(cu["pour_factor"] or 1)
        cu["flex_max_shift_min"] = int(cu.get("flex_max_shift_min") or 0)
    orders, streams = {}, {}
    for r in read_csv(d("planner_orders.csv")):
        for k in ("grade", "loads", "interval_min", "max_gap_min", "cold_joint_min"):
            r[k] = int(r[k])
        for k in ("volume_m3", "price_per_m3", "load_m3"):
            r[k] = float(r[k])
        r["first_arrival"] = t2m(r["requested_start"])
        streams[r["stream_id"]] = r
        orders.setdefault(r["order_id"], []).append(r["stream_id"])
    trucks = {r["truck_id"]: r for r in read_csv(c("trucks.csv"))}
    off = set()
    p = d("trucks_today.csv")
    if os.path.exists(p):
        off = {r["truck_id"] for r in read_csv(p) if r["available"] != "1"}
    for t in trucks.values():
        t["allowed"] = None if t["allowed_plants"] == "ALL" else set(t["allowed_plants"].split("|"))
        t["capacity_m3"] = float(t["capacity_m3"])
    trucks_today = {k: v for k, v in trucks.items() if k not in off}
    travel = {}
    for r in read_csv(c("routes.csv")):
        dd = {"km": float(r["km"]), "offpeak": float(r["min_offpeak"]), "normal": float(r["min_normal"]),
              "peak": float(r["min_peak"]), "holiday": float(r["min_holiday"])}
        travel[(r["from_id"], r["to_id"])] = dd
        travel[(r["to_id"], r["from_id"])] = dd
    day_type = info["day_type"]
    periods = [(t2m(r["start"]), t2m(r["end"]), r["period"]) for r in read_csv(c("traffic_periods.csv"))
               if r["day_type"] == day_type]
    events = []
    p = d("traffic_events.csv")
    for r in (read_csv(p) if os.path.exists(p) else []):
        events.append(dict(zones=set(r["zones"].split("|")), start=t2m(r["start"]), end=t2m(r["end"]),
                           factor=float(r["travel_factor"]), no_entry=r.get("no_entry_for_sites", "") == "1",
                           reason=r["reason"]))
    for e in events:   # a closure = no truck may arrive at sites in those zones during the window
        if e["no_entry"]:
            for s in sites.values():
                if s["tags"] & e["zones"]:
                    s["no_entry"] = s["no_entry"] + [(e["start"], e["end"])]
    status = []
    p = d("plant_status.csv")
    for r in (read_csv(p) if os.path.exists(p) else []):
        status.append(dict(plant_id=r["plant_id"], start=t2m(r["start"]), end=t2m(r["end"]),
                           lines=int(r["lines_available"]), note=r.get("note", "")))
    cost = {r["param"]: float(r["value"]) for r in read_csv(c("cost_params.csv"))}
    return Day(folder, info, day_type, plants, products, plant_product, sites, customers, orders, streams,
               trucks_today, off, travel, periods, events, status, cost)


def period_at(day: Day, t: float) -> str:
    for a, b, p in day.periods:
        if a <= t < b:
            return p
    return "offpeak"


def tags_of(day: Day, node: str) -> set:
    if node in day.plants:
        return {day.plants[node]["zone"], "ALL"}
    return day.sites[node]["tags"]


def leg(day: Day, a: str, b: str, depart: float):
    """(km, minutes) of a trip a -> b leaving at `depart` (traffic period + today's events)."""
    if a == b:
        return 0.0, 0.0
    d = day.travel[(a, b)]
    mins = d[period_at(day, depart)]
    ta, tb = tags_of(day, a), tags_of(day, b)
    f = 1.0
    for e in day.events:
        if e["start"] <= depart < e["end"] and (ta & e["zones"] or tb & e["zones"]):
            f = max(f, e["factor"])
    return d["km"], mins * f


def transport_cost(day: Day, km: float, m3: float) -> float:
    c = day.cost
    return c["trip_base_baht"] + c["loaded_baht_per_km_m3"] * km * m3


# ------------------------------------------------------------------ simulation state
@dataclass
class Line:
    busy: list = field(default_factory=list)      # [(a, b)] reserved intervals
    blocks: list = field(default_factory=list)    # [(a, b)] line not available
    boost: bool = False

    def fits(self, a, b):
        return all(b <= x or a >= y for x, y in self.busy) and all(b <= x or a >= y for x, y in self.blocks)

    def earliest(self, a, length):
        """earliest start >= a such that [start, start+length) is free."""
        t = a
        for _ in range(500):
            clash = [y for x, y in self.busy + self.blocks if not (t + length <= x or t >= y)]
            if not clash:
                return t
            t = max(clash)
        return None


@dataclass
class TruckState:
    loc: str
    ready: float
    loads: int = 0
    km_loaded: float = 0
    km_empty: float = 0
    km_reposition: float = 0


class Sim:
    """Executes loads one at a time (official rules). `simulate` feeds loads in order of planned load_start."""

    def __init__(self, day: Day, production=None, changes=None):
        self.day = day
        self.notes = []
        self.lines = {}
        for pid, p in day.plants.items():
            lines = []
            for i in range(p["lines"]):
                ln = Line(blocks=[(0, p["open_m"]), (p["close_m"], 24 * 60)])
                for s in day.status:   # e.g. breakdown: only `lines` lines work in the window
                    if s["plant_id"] == pid and i >= s["lines"]:
                        ln.blocks.append((s["start"], s["end"]))
                lines.append(ln)
            self.lines[pid] = lines
        self.boost_cost = 0.0
        for row in production or []:
            pid = row["plant_id"]
            if pid not in day.plants:
                self.notes.append(f"production_plan: ไม่มีโรงงาน {pid}")
                continue
            n = int(row["extra_lines"])
            a, b = t2m(row["from"]), t2m(row["to"])
            p = day.plants[pid]
            if n > p["boost_max_lines"]:
                self.notes.append(f"{pid}: ขอเพิ่ม {n} ไลน์ แต่เพิ่มได้สูงสุด {p['boost_max_lines']} → ใช้ {p['boost_max_lines']}")
                n = p["boost_max_lines"]
            if not p.get("boost_from"):
                continue
            lo, hi = t2m(p["boost_from"]), t2m(p["boost_to"])
            a, b = max(a, lo), min(b, hi)
            if n <= 0 or b <= a:
                continue
            for _ in range(n):
                ln = Line(blocks=[(0, a), (b, 24 * 60)], boost=True)
                for s in day.status:   # a broken plant cannot be boosted either
                    if s["plant_id"] == pid and s["lines"] == 0:
                        ln.blocks.append((s["start"], s["end"]))
                self.lines[pid].append(ln)
            self.boost_cost += n * (b - a) / 60 * p["boost_cost_per_hour"]
        self.trucks = {tid: TruckState(t["home_plant"], TRUCK_DAY_START) for tid, t in day.trucks.items()}
        self.first_arrival = {sid: s["first_arrival"] for sid, s in day.streams.items()}
        self.changed_orders = {}
        for row in changes or []:
            oid = row["order_id"]
            if oid not in day.orders:
                self.notes.append(f"order_changes: ไม่มี order {oid}")
                continue
            new = t2m(row["new_first_arrival"])
            s0 = day.streams[day.orders[oid][0]]
            cust = day.customers[s0["customer_id"]]
            shift = new - s0["first_arrival"]
            ok = (cust["flex_type"] == "later_ok" and 0 <= shift <= cust["flex_max_shift_min"]) or                  (cust["flex_type"] == "earlier_ok" and -cust["flex_max_shift_min"] <= shift <= 0)
            self.changed_orders[oid] = ok
            if ok:
                for sid in day.orders[oid]:
                    self.first_arrival[sid] = new + (day.streams[sid]["first_arrival"] - s0["first_arrival"])
            else:
                self.notes.append(f"order_changes: ลูกค้าของ {oid} ไม่ยอมเลื่อนเป็น {row['new_first_arrival']} → ถือว่าผิดนัด (SLA ของออเดอร์นี้ = ไม่ผ่าน)")
        self.site_free = {}      # stream_id -> pour end of previous load
        self.done = {}           # (stream_id, seq) -> result dict

    # ---------------------------------------------------------------- one load
    def line_start(self, pid, desired):
        """earliest load_start >= desired with a free line (line busy prep_min before to mix_load_min after)."""
        p = self.day.plants[pid]
        best = None
        for i, ln in enumerate(self.lines[pid]):
            s = ln.earliest(desired - p["prep_min"], p["prep_min"] + p["mix_load_min"])
            if s is None:
                continue
            s += p["prep_min"]
            if best is None or s < best[0]:
                best = (s, i)
        return best

    def preview(self, sid: str, seq: int, pid: str, tid: str, planned: float):
        day, s = self.day, self.day.streams[sid]
        t, ts = day.trucks[tid], self.trucks[tid]
        p = day.plants[pid]
        cust = day.customers[s["customer_id"]]
        site = day.sites[s["site_id"]]
        problems = []
        if t["size"] != s["truck_size"]:
            problems.append("ขนาดรถไม่ตรงออเดอร์")
        if t["allowed"] is not None and pid not in t["allowed"]:
            problems.append("รถ vendor นี้ไม่ได้รับอนุญาตที่โรงงานนี้")
        if (pid, s["product_id"]) not in day.plant_product:
            problems.append(f"โรงงาน {pid} ผลิต {s['product_id']} ไม่ได้")
        # truck to plant (empty). First load at another plant = morning repositioning from 05:00.
        if ts.loc == pid:
            ready, km_e, km_rep = ts.ready, 0.0, 0.0
        else:
            km_e, mins = leg(day, ts.loc, pid, ts.ready)
            ready = ts.ready + mins
            km_rep = km_e if ts.loc in day.plants else 0.0
        best = self.line_start(pid, max(planned, ready))
        if best is None:
            best = (max(planned, ready), -1)
            problems.append("ไม่มีไลน์ผลิตว่าง")
        start, line_i = best
        depart = start + p["mix_load_min"] + p["qc_min"]
        km_l, mins = leg(day, pid, s["site_id"], depart)
        arrive = depart + mins + site["access_min"]
        wait_ban = 0.0
        for a, b in site["no_entry"]:          # truck ban / road closure: wait outside until it ends
            if a <= arrive < b:
                wait_ban = b - arrive
                arrive = b
        site_open = self.first_arrival[sid] + cust["site_delay_min"]
        prev_end = self.site_free.get(sid)
        pour_start = max(arrive, site_open if seq == 1 else 0, prev_end or 0)
        pour_min = s["interval_min"] * cust["pour_factor"]
        pour_end = pour_start + pour_min
        gap = None if seq == 1 or prev_end is None else max(0.0, pour_start - prev_end)
        life = day.products[s["product_id"]]["concrete_life_min"]
        rejected = (pour_end - start) > life
        return dict(stream_id=sid, seq=seq, plant_id=pid, truck_id=tid, planned=planned, truck_ready=ready,
                    load_start=start, line=line_i, depart=depart, arrive=arrive, wait_ban=wait_ban,
                    pour_start=pour_start, pour_end=pour_end, wait_site=max(0.0, pour_start - arrive) + wait_ban,
                    gap=gap, rejected=rejected, age_min=pour_end - start, plant_delay=start - planned,
                    km_loaded=km_l, km_empty_to_plant=km_e, km_reposition=km_rep, problems=problems)

    def commit(self, r):
        sid, pid, tid = r["stream_id"], r["plant_id"], r["truck_id"]
        p = self.day.plants[pid]
        if r["line"] >= 0:
            self.lines[pid][r["line"]].busy.append((r["load_start"] - p["prep_min"], r["load_start"] + p["mix_load_min"]))
        ts = self.trucks[tid]
        ts.km_empty += r["km_empty_to_plant"] - r["km_reposition"]
        ts.km_reposition += r["km_reposition"]
        ts.km_loaded += r["km_loaded"]
        ts.loc = self.day.streams[sid]["site_id"]
        ts.ready = r["pour_end"] + WASH_MIN
        ts.loads += 1
        self.site_free[sid] = r["pour_end"]
        self.done[(sid, r["seq"])] = r
        return r


# ------------------------------------------------------------------ whole plan
def read_plan(path):
    rows = read_csv(path)
    for r in rows:
        r["seq"] = int(r["seq"])
        r["load_start"] = t2m(r["load_start"])
    return rows


def simulate(day: Day, plan, production=None, changes=None):
    errors = []
    sim = Sim(day, production, changes)
    seen = set()
    plan = sorted(plan, key=lambda r: (r["load_start"], r["stream_id"], r["seq"]))
    last_seq = {}
    for r in plan:
        key = (r["stream_id"], r["seq"])
        if r["stream_id"] not in day.streams:
            errors.append(f"ไม่มีสายเท {r['stream_id']}")
            continue
        if key in seen:
            errors.append(f"เที่ยวซ้ำ {key}")
            continue
        if r["truck_id"] in day.trucks_off:
            errors.append(f"{key}: รถ {r['truck_id']} ไม่มาทำงานวันนี้ (trucks_today.csv)")
            continue
        if r["plant_id"] not in day.plants or r["truck_id"] not in day.trucks:
            errors.append(f"โรงงาน/รถไม่ถูกต้อง {key}")
            continue
        if r["seq"] != last_seq.get(r["stream_id"], 0) + 1:
            errors.append(f"{r['stream_id']}: เที่ยว {r['seq']} ออกก่อน/ข้ามเที่ยวก่อนหน้า (ต้องเรียงเวลาโหลดตาม seq)")
        last_seq[r["stream_id"]] = r["seq"]
        seen.add(key)
        res = sim.preview(r["stream_id"], r["seq"], r["plant_id"], r["truck_id"], r["load_start"])
        for p in res["problems"]:
            errors.append(f"{key}: {p}")
        sim.commit(res)
    return sim, errors


def finish_day(sim: Sim):
    """Trucks drive home after their last discharge (km only; site -> home is part of the delivery fee)."""
    for tid, ts in sim.trucks.items():
        home = sim.day.trucks[tid]["home_plant"]
        if ts.loc != home:
            k, _ = leg(sim.day, ts.loc, home, ts.ready)
            if ts.loc in sim.day.plants:
                ts.km_reposition += k
            else:
                ts.km_empty += k
            ts.loc = home


def queue_violations(day: Day, sim: Sim):
    """Trucks waiting at a site beyond its max_queue (parking on the street)."""
    n = 0
    by_stream = {}
    for (sid, k), r in sim.done.items():
        by_stream.setdefault(day.streams[sid]["site_id"], []).append(r)
    for site_id, rs in by_stream.items():
        q = day.sites[site_id]["max_queue"]
        for r in rs:
            waiting = sum(1 for o in rs if o is not r and o["arrive"] <= r["arrive"] < o["pour_start"])
            if waiting >= q:
                n += 1
    return n


def kpis(day: Day, sim: Sim, errors=None):
    finish_day(sim)
    c = day.cost
    res = {"errors": len(errors or []), "notes": sim.notes}
    grade_rows, order_rows = [], []
    revenue = material = transport = waiting = 0.0
    loads_total = loads_rejected = cold = late_hour = 0
    m3_delivered = 0.0
    for oid, sids in day.orders.items():
        s0 = day.streams[sids[0]]
        g = s0["grade"]
        bad_change = sim.changed_orders.get(oid) is False
        n_over = n_loads = 0
        on_time = True
        o_rev = o_cost = 0.0
        for sid in sids:
            s = day.streams[sid]
            for k in range(1, s["loads"] + 1):
                n_loads += 1
                loads_total += 1
                r = sim.done.get((sid, k))
                if r is None:
                    n_over += 1
                    loads_rejected += 1
                    if k == 1:
                        on_time = False
                    continue
                waiting += r["wait_site"]
                tc = transport_cost(day, r["km_loaded"], s["load_m3"])
                mc = day.plant_product.get((r["plant_id"], s["product_id"]), 0) * s["load_m3"]
                transport += tc
                material += mc
                o_cost += tc + mc
                if r["rejected"]:
                    loads_rejected += 1
                    n_over += 1
                else:
                    revenue += s["price_per_m3"] * s["load_m3"]
                    o_rev += s["price_per_m3"] * s["load_m3"]
                    m3_delivered += s["load_m3"]
                if k == 1:
                    dev = r["arrive"] - sim.first_arrival[sid]
                    if abs(dev) > ON_TIME_TOL:
                        on_time = False
                    if dev > 60:
                        late_hour += 1
                elif r["gap"] is not None and r["gap"] > s["max_gap_min"]:
                    n_over += 1
                    if r["gap"] > s["cold_joint_min"]:
                        cold += 1
        colour = "GREEN" if n_over == 0 else ("RED" if n_over > RED_SHARE * n_loads else "YELLOW")
        if bad_change:
            on_time, colour = False, "RED"
        order_rows.append(dict(order_id=oid, grade=g, customer_id=s0["customer_id"], site_id=s0["site_id"],
                               loads=n_loads, loads_over=n_over, on_time=on_time, colour=colour,
                               revenue=round(o_rev), direct_cost=round(o_cost)))
    km_loaded = sum(t.km_loaded for t in sim.trucks.values())
    km_empty = sum(t.km_empty for t in sim.trucks.values())
    km_rep = sum(t.km_reposition for t in sim.trucks.values())
    reposition = km_rep * c["reposition_baht_per_km"]
    wait_cost = waiting * c["truck_wait_baht_per_min"]
    qv = queue_violations(day, sim)
    queue_cost = qv * c["site_queue_fine_baht"]
    contribution = revenue - material - transport - reposition - sim.boost_cost - wait_cost - queue_cost
    co2 = km_loaded * c["co2_kg_per_km_loaded"] + (km_empty + km_rep) * c["co2_kg_per_km_empty"]
    num = den = 0.0
    passed = 0
    for g, (name, t_on, t_green, gap, w) in GRADES.items():
        rows = [o for o in order_rows if o["grade"] == g]
        if not rows:
            continue
        on = sum(o["on_time"] for o in rows) / len(rows)
        gr = sum(o["colour"] == "GREEN" for o in rows) / len(rows)
        ok_on, ok_gr = on >= t_on - 1e-9, gr >= t_green - 1e-9
        passed += ok_on + ok_gr
        num += w * (0.5 * min(1, on / t_on) + 0.5 * min(1, gr / t_green))
        den += w
        grade_rows.append(dict(grade=g, name=name, orders=len(rows), on_time=round(on, 3), on_time_target=t_on,
                               on_time_pass=ok_on, green=round(gr, 3), green_target=t_green, green_pass=ok_gr))
    sla_score = 60 * num / den if den else 0
    total = 2 * len(grade_rows)
    if errors:
        sla_score, passed = 0.0, 0
    used = [t for t in sim.trucks.values() if t.loads]
    res.update(
        sla_pass=(passed == total and not errors), sla_checks_passed=passed, sla_checks_total=total,
        sla_score=round(sla_score, 2),
        contribution_baht=round(contribution), revenue_baht=round(revenue), material_baht=round(material),
        transport_baht=round(transport), reposition_baht=round(reposition), boost_baht=round(sim.boost_cost),
        waiting_baht=round(wait_cost), queue_fine_baht=round(queue_cost), queue_violations=qv,
        m3_delivered=round(m3_delivered, 1), km_loaded=round(km_loaded), km_empty=round(km_empty),
        km_reposition=round(km_rep), km_total=round(km_loaded + km_empty + km_rep), co2_kg=round(co2),
        loads=loads_total, loads_rejected=loads_rejected, cold_joints=cold, first_load_late_over_1h=late_hour,
        truck_wait_min=round(waiting), trucks_used=len(used),
        loads_per_truck=round(sum(t.loads for t in used) / max(1, len(used)), 2),
        grades=grade_rows, orders=order_rows)
    return res
