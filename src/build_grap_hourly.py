"""Turn the CAQM GRAP order table into an hourly stage flag (IST) for the whole NCR.

Reads data/processed/grap_orders.csv (one row per order) and grap_gaps.csv (periods where an
order is known to be missing) and writes data/processed/grap_hourly.csv.

Stage logic: invoking Stage k sets the stage in force to k; revoking Stage k sets it to k-1
(the orders say "revocation of Stage-III and intensifying actions under Stage-I & II").
Orders on the same date are applied in file order.

Effective time: orders say "with immediate effect" but the table has no time of issue yet. Each
change takes effect at effective_time_ist if filled; otherwise at pib_posted_ist (the time the
PIB press release went out, so the order is no later than this); otherwise at --assume-time.
Every hour on a date whose time is not an order time, and every hour inside a known gap, is
flagged uncertain=True; drop those rows (or run a robustness check without them) rather than
trusting the stage there.

Usage:  python src/build_grap_hourly.py [--start 2025-02-19 --end 2026-09-30 --assume-time 12:00]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ORDERS_CSV = ROOT / "data" / "processed" / "grap_orders.csv"
GAPS_CSV = ROOT / "data" / "processed" / "grap_gaps.csv"
OUT_CSV = ROOT / "data" / "processed" / "grap_hourly.csv"

results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def load_orders(assume_time):
    o = pd.read_csv(ORDERS_CSV, dtype={"effective_time_ist": str, "pib_posted_ist": str})
    o["order_date"] = pd.to_datetime(o["order_date"])
    o["time_known"] = o["effective_time_ist"].notna()
    clock = o["effective_time_ist"].fillna(o["pib_posted_ist"]).fillna(assume_time)
    o["effective"] = o["order_date"] + pd.to_timedelta(clock + ":00")
    return o


def stage_changes(o):
    """Walk the orders in file order and record the stage and version after each one."""
    level, version, warnings, rows = 0, None, [], []
    for _, r in o.iterrows():
        before = level
        if r["action"] == "invoke":
            level = int(r["stage"])
        elif r["action"] == "revoke":
            stage = int(r["stage"])
            if before < stage:
                warnings.append(f"{r['order_date'].date()}: revokes Stage-{stage} but only stage {before} was in force "
                                f"(an invocation is missing or the order is wrong)")
            level = stage - 1
        elif r["action"] != "schedule":
            sys.exit(f"unknown action {r['action']!r} on {r['order_date'].date()}")
        version = r["schedule_version"]
        rows.append({"effective": r["effective"], "stage": level, "version": version,
                     "time_known": r["time_known"], "order_date": r["order_date"]})
    return pd.DataFrame(rows), warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-02-19")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--assume-time", default="12:00", help="HH:MM IST used when an order has no time yet")
    args = ap.parse_args()

    o = load_orders(args.assume_time)
    changes, warnings = stage_changes(o)
    if not o["order_date"].is_monotonic_increasing:
        sys.exit("grap_orders.csv must be sorted by order_date")

    hours = pd.date_range(pd.Timestamp(args.start), pd.Timestamp(args.end) + pd.Timedelta(hours=23), freq="h")
    out = pd.DataFrame({"ts_ist": hours})
    # the last change at or before each hour (a same-moment tie goes to the later row)
    idx = changes["effective"].searchsorted(hours, side="right") - 1
    if (idx < 0).any():
        sys.exit("window starts before the first order in grap_orders.csv")
    out["grap_stage"] = changes["stage"].to_numpy()[idx]
    out["schedule_version"] = changes["version"].to_numpy()[idx]

    # Uncertainty: hours on a date whose order time is assumed, and hours inside a known gap
    unknown_dates = set(o.loc[~o["time_known"] & (o["order_date"] >= pd.Timestamp(args.start)), "order_date"])
    day = out["ts_ist"].dt.normalize()
    out["uncertain"] = day.isin(unknown_dates)
    reason = pd.Series("", index=out.index)
    reason[out["uncertain"]] = "order time not known (PIB posting time or assumed)"
    gaps = pd.read_csv(GAPS_CSV, parse_dates=["start_date", "end_date"])
    in_gap = pd.Series(False, index=out.index)
    for _, g in gaps.iterrows():
        in_gap |= (day >= g["start_date"]) & (day <= g["end_date"])
    reason[in_gap] = "known gap in orders"
    out["uncertain"] |= in_gap
    out["uncertain_reason"] = reason

    out["ts_ist"] = out["ts_ist"].dt.strftime("%Y-%m-%d %H:%M")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    n_days = (pd.Timestamp(args.end) - pd.Timestamp(args.start)).days + 1
    print(f"wrote {OUT_CSV.relative_to(ROOT)}: {len(out):,} hours, {args.start} to {args.end}")
    print("\nHours per stage (all / certain only):")
    summary = pd.DataFrame({"hours": out["grap_stage"].value_counts().sort_index(),
                            "certain_hours": out.loc[~out["uncertain"], "grap_stage"].value_counts().sort_index()}).fillna(0).astype(int)
    print(summary.to_string())
    print(f"uncertain hours: {int(out['uncertain'].sum()):,} of {len(out):,} ({out['uncertain'].mean():.1%})")
    print("verification of the orders used:", o["verification"].value_counts().to_dict())
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print("  ", w)

    print("\nChecks")
    check(f"one row per hour: {n_days} days x 24 = {n_days * 24:,}", len(out) == n_days * 24)
    check("no duplicate hours", not out["ts_ist"].duplicated().any())
    check("stage is between 0 and 4 for every hour", out["grap_stage"].between(0, 4).all())
    check("every stage change inside the window is on an order date",
          (out["grap_stage"].ne(out["grap_stage"].shift()).iloc[1:]
           & ~pd.to_datetime(out["ts_ist"]).dt.normalize().iloc[1:].isin(o["order_date"])).sum() == 0)
    # warnings are only acceptable where a gap explains them
    gap_days = set()
    for _, g in gaps.iterrows():
        gap_days |= set(pd.date_range(g["start_date"], g["end_date"]))
    unexplained = [w for w in warnings if pd.Timestamp(w[:10]) not in gap_days
                   and not any(abs((pd.Timestamp(w[:10]) - d).days) <= 1 for d in (min(gap_days), max(gap_days)))
                   ] if gap_days else warnings
    check("every revoke-without-invoke warning sits next to a known gap", not unexplained)

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
