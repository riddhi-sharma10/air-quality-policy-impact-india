"""Count, for each IST date, how many distinct clock hours have a PM2.5 value (OpenAQ archive).

Usage:  python src/openaq_pm25_coverage.py [station_id ...] [--start YYYY-MM-DD --end YYYY-MM-DD]
        (default stations: 6358 2456; default window: first to last file date)
Reads data/raw/openaq_archive/<station_id>/<year>/month=MM/location-<id>-<YYYYMMDD>.csv.gz.
A day with no file, or a file without PM2.5, counts as 0 hours.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "openaq_archive"
THRESHOLD = 20  # days with fewer hours than this are listed as poorly covered


def hours_per_day(station_id, start=None, end=None):
    files = sorted((BASE / str(station_id)).rglob("*.csv.gz"))
    if not files:
        sys.exit(f"no files under {BASE / str(station_id)}")
    parts, n_rows = [], 0
    for f in files:
        df = pd.read_csv(f, usecols=["sensors_id", "datetime", "parameter", "value"])
        n_rows += len(df)
        pm = df[(df["parameter"] == "pm25") & df["value"].notna()]
        if len(pm) == 0:
            continue
        # every timestamp in the archive carries +05:30; keep the local clock time
        assert pm["datetime"].str.endswith("+05:30").all(), f"unexpected offset in {f.name}"
        t = pd.to_datetime(pm["datetime"].str[:19])
        parts.append(pd.DataFrame({"sensor": pm["sensors_id"].to_numpy(), "ist_hour": t.dt.floor("h")}))
    pm_all = pd.concat(parts, ignore_index=True)
    hours = pm_all.drop_duplicates("ist_hour")  # distinct hours with a value from any PM2.5 sensor
    per_day = hours.groupby(hours["ist_hour"].dt.normalize()).size()

    # default window is first to last file date; days with no file become 0 hours
    dates = [pd.Timestamp(f.name.split("-")[-1].split(".")[0]) for f in files]
    calendar = pd.date_range(start or min(dates), end or max(dates), freq="D")
    per_day = per_day.reindex(calendar, fill_value=0)
    return per_day, set(dates), pm_all["sensor"].unique(), len(files), n_rows


def runs(days):
    """Group consecutive dates into (start, end) runs."""
    out, start, prev = [], None, None
    for d in days:
        if start is None:
            start = prev = d
        elif d - prev == pd.Timedelta(days=1):
            prev = d
        else:
            out.append((start, prev))
            start = prev = d
    if start is not None:
        out.append((start, prev))
    return out


ap = argparse.ArgumentParser()
ap.add_argument("stations", nargs="*", type=int, default=[6358, 2456])
ap.add_argument("--start", type=pd.Timestamp)
ap.add_argument("--end", type=pd.Timestamp)
args = ap.parse_args()

for sid in args.stations:
    per_day, file_dates, pm_sensors, n_files, n_rows = hours_per_day(sid, args.start, args.end)
    n = len(per_day)
    no_file = [d for d in per_day.index if d not in file_dates]
    low = per_day[per_day < THRESHOLD]
    print("=" * 70)
    print(f"Station {sid}: {n_files} files, {n_rows:,} rows, PM2.5 sensor IDs seen: {sorted(pm_sensors.tolist())}")
    print(f"Calendar {per_day.index[0].date()} to {per_day.index[-1].date()}: {n} days")
    print(f"  days with no file:           {len(no_file)}")
    print(f"  days with 24 PM2.5 hours:    {int((per_day == 24).sum())}")
    print(f"  days with {THRESHOLD}-23 hours:         {int(((per_day >= THRESHOLD) & (per_day < 24)).sum())}")
    print(f"  days with < {THRESHOLD} hours (incl. no file / no PM2.5): {len(low)}")
    print(f"  PM2.5 hours present: {int(per_day.sum()):,} of {n * 24:,} possible ({per_day.sum() / (n * 24):.1%})")

    print("\n  Per month: days, mean hours/day, days < threshold")
    by_month = per_day.groupby(per_day.index.to_period("M"))
    summary = pd.DataFrame({"days": by_month.size(), "mean_hours": by_month.mean().round(1),
                            "days_low": by_month.apply(lambda s: int((s < THRESHOLD).sum()))})
    print(summary.to_string())

    print(f"\n  Runs of days with fewer than {THRESHOLD} hours (start - end: days, hours on those days):")
    for start, end in runs(low.index):
        seg = per_day[start:end]
        print(f"    {start.date()} - {end.date()}: {len(seg)} day(s), {int(seg.sum())} hour(s)")
