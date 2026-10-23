"""Task 1: is the UTC -> IST date conversion in build_fire_features.py correct?

Compares the script's IST date with an independent calculation (pandas Timestamp + Timedelta per
unique acq_date/acq_time pair, no vectorised datetime parsing), and shows how day and night
detections fall relative to the UTC date.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fire_features import load_detections  # noqa: E402  (the script's own loader)

det, n_raw = load_detections()
det["utc_date"] = det["utc"].dt.normalize()
det["utc_hour"] = det["utc"].dt.hour

print("\n(a) detections by UTC hour of acq_time, D and N separately")
print(pd.crosstab(det["utc_hour"], det["daynight"]).to_string())

print("\n(b) earliest and latest UTC acq_time")
for dn in ("D", "N"):
    t = det.loc[det["daynight"] == dn, "utc"].dt.strftime("%H:%M")
    print(f"  {dn}: earliest {t.min()}, latest {t.max()}")
n18 = det[(det["daynight"] == "N") & (det["utc"].dt.hour == 18)]
print(f"  N rows in the 18:00-18:29 UTC window (same IST date): {int((n18['utc'].dt.minute < 30).sum())}; "
      f"18:30-18:59 UTC (next IST date): {int((n18['utc'].dt.minute >= 30).sum())}")

print("\n(c) IST date compared with the UTC date")
day_diff = (det["ist_date"] - det["utc_date"]).dt.days
print(pd.crosstab(det["daynight"], day_diff).rename(columns=lambda d: f"IST date = UTC date {d:+d} day").to_string())

print("\n(d) independent recalculation, per unique (acq_date, acq_time) pair")
pairs = det[["acq_date", "acq_time"]].drop_duplicates()
def independent_ist_date(date_str, hhmm):
    hh, mm = divmod(int(hhmm), 100)  # 620 -> 6 h 20 min
    ts = pd.Timestamp(date_str) + pd.Timedelta(hours=hh, minutes=mm)  # UTC
    return (ts + pd.Timedelta(hours=5, minutes=30)).normalize()
pairs["indep"] = [independent_ist_date(d, t) for d, t in zip(pairs["acq_date"], pairs["acq_time"])]
merged = det.merge(pairs, on=["acq_date", "acq_time"], how="left")
mismatch = merged[merged["ist_date"] != merged["indep"]]
print(f"  {len(pairs):,} unique pairs checked; rows where the script's IST date differs: {len(mismatch):,}")
print("  [PASS] script IST date == independent calculation" if len(mismatch) == 0
      else "  [FAIL] script IST date differs from the independent calculation")
sys.exit(1 if len(mismatch) else 0)
