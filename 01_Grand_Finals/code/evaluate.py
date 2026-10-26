"""AI Concrete — score a plan for one day.

    python evaluate.py ../data/day1_weekday ../data/day1_weekday/planner_plan.csv
    python evaluate.py ../data/day1_weekday out/day1/plan.csv --changes out/day1/order_changes.csv --production out/day1/production_plan.csv

Prints the SLA table + Contribution and writes <plan>_result.json and <plan>_loads.csv (every load: times, gap,
wait — open it in dashboard.html with "โหลดผลของทีม"). Organisers add --truth truth.json (real plant capacity);
your own run uses plants.csv as it is in your copy of the data.
"""
import argparse
import json
import os

from aiconcrete import kpis, load_day, m2t, read_csv, read_plan, simulate, write_csv


def evaluate(data_dir, plan, production=None, changes=None, truth=None, write=True):
    day = load_day(data_dir, truth)
    prod = read_csv(production) if production and os.path.exists(production) else None
    chg = read_csv(changes) if changes and os.path.exists(changes) else None
    sim, errors = simulate(day, read_plan(plan), prod, chg)
    res = kpis(day, sim, errors)
    res["error_list"] = errors[:50]
    res["day"] = day.info
    if write:
        base = os.path.splitext(plan)[0]
        with open(base + "_result.json", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        rows = []
        for (sid, k), r in sorted(sim.done.items()):
            s = day.streams[sid]
            rows.append(dict(stream_id=sid, seq=k, order_id=s["order_id"], customer_id=s["customer_id"],
                             site_id=s["site_id"], grade=s["grade"], product_id=s["product_id"],
                             truck_size=s["truck_size"], plant_id=r["plant_id"], truck_id=r["truck_id"],
                             planned=m2t(r["planned"]), load_start=m2t(r["load_start"]),
                             plant_delay_min=round(r["plant_delay"]), depart=m2t(r["depart"]), arrive=m2t(r["arrive"]),
                             pour_start=m2t(r["pour_start"]), pour_end=m2t(r["pour_end"]),
                             requested=m2t(sim.first_arrival[sid]) if k == 1 else "",
                             gap_min="" if r["gap"] is None else round(r["gap"]), max_gap_min=s["max_gap_min"],
                             wait_min=round(r["wait_site"]), age_min=round(r["age_min"]), rejected=int(r["rejected"]),
                             km_loaded=r["km_loaded"], km_reposition=r["km_reposition"],
                             on_time="" if k > 1 else int(abs(r["arrive"] - sim.first_arrival[sid]) <= 15),
                             over=int(bool(r["rejected"]) + (k > 1 and r["gap"] is not None and r["gap"] > s["max_gap_min"]))))
        write_csv(base + "_loads.csv", rows)
    return res


def report(res, title):
    print(f"\n=== AI Concrete · Day {res['day'].get('day')} {res['day'].get('event')} · {title}")
    if res["errors"]:
        print(f"!! ข้อผิดพลาด {res['errors']} ข้อ (SLA วันนี้ = ไม่ผ่าน) เช่น:")
        for e in res["error_list"][:10]:
            print("   -", e)
    for n in res["notes"]:
        print("  note:", n)
    print(f"\n{'Grade':<16}{'orders':>7}{'ตรงเวลา':>10}{'เป้า':>7}{'':>3}{'ต่อเนื่องเขียว':>15}{'เป้า':>7}")
    ok = lambda b: "✓" if b else "✗"
    for g in res["grades"]:
        print(f"G{g['grade']} {g['name']:<13}{g['orders']:>7}{g['on_time']:>10.0%}{g['on_time_target']:>7.0%}"
              f"{ok(g['on_time_pass']):>3}{g['green']:>15.0%}{g['green_target']:>7.0%}{ok(g['green_pass']):>3}")
    print(f"\nSLA วันนี้                {'ผ่าน ✓' if res['sla_pass'] else 'ไม่ผ่าน ✗'}  ({res['sla_checks_passed']}/{res['sla_checks_total']} เกณฑ์ · คะแนนต่อเนื่อง {res['sla_score']}/60)")
    print(f"Contribution             {res['contribution_baht']:,} บาท  = รายได้ {res['revenue_baht']:,} − วัสดุ {res['material_baht']:,}"
          f" − ขนส่ง {res['transport_baht']:,} − โยก {res['reposition_baht']:,} − เพิ่มไลน์ {res['boost_baht']:,}"
          f" − รถรอ {res['waiting_baht']:,} − จอดเกิน {res['queue_fine_baht']:,}")
    print(f"ระยะทาง                  {res['km_total']:,} กม. (บรรทุก {res['km_loaded']:,} · เปล่า {res['km_empty']:,} · โยก {res['km_reposition']:,})"
          f"   CO2 {res['co2_kg']:,} kg")
    print(f"เที่ยว {res['loads']} · ถูกปฏิเสธ {res['loads_rejected']} · cold joint {res['cold_joints']} · เที่ยวแรกช้า > 1 ชม. "
          f"{res['first_load_late_over_1h']} · รถใช้ {res['trucks_used']} คัน ({res['loads_per_truck']} เที่ยว/คัน)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("plan")
    ap.add_argument("--production", help="production_plan.csv (plant_id, extra_lines, from, to)")
    ap.add_argument("--changes", help="order_changes.csv (order_id, new_first_arrival, reason)")
    ap.add_argument("--truth", help="organisers only")
    a = ap.parse_args()
    res = evaluate(a.data_dir, a.plan, a.production, a.changes, a.truth)
    report(res, a.plan)


if __name__ == "__main__":
    main()
