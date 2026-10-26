"""AI Concrete — the ONE command every team must keep working (the organisers run it on the hidden Day 5).

    python solve.py <day_dir> <out_dir>
    python solve.py ../data/day1_weekday ../out/day1

Reads one day folder (and ../common), writes <out_dir>/plan.csv, order_changes.csv, production_plan.csv.
Rules for the hidden day: same command, no internet, no manual edits, finish within 5 minutes.
Replace plan_day() with your own solver (any language is fine as long as this command produces the 3 files).
"""
import os
import sys

from aiconcrete import load_day, write_csv
from master_solver import solve_day


def main():
    if len(sys.argv) < 3:
        print("Usage: python solve.py <day_dir> <out_dir>")
        sys.exit(1)
    day_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    day = load_day(day_dir)
    plan, changes, production = solve_day(day)
    write_csv(os.path.join(out_dir, "plan.csv"), plan, ["stream_id", "seq", "plant_id", "truck_id", "load_start"])
    write_csv(os.path.join(out_dir, "order_changes.csv"), changes, ["order_id", "new_first_arrival", "reason"])
    write_csv(os.path.join(out_dir, "production_plan.csv"), production, ["plant_id", "extra_lines", "from", "to"])
    print(f"Master Solver: Day {day.info.get('day')} {day.info.get('event')}: {len(plan)} loads -> {out_dir}")


if __name__ == "__main__":
    main()
