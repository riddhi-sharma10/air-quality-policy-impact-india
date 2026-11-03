"""Build the final dataset: one row per station per IST hour (54 stations x 14,136 hours = 763,344 rows).

Built in phases, see docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md (Part B):
  B1  spine (every station x every hour of the study window) and the pollution join   <- done here
  B2  weather, policy and calendar columns
  B3  fire columns
The row count is fixed by the spine: every later join is a left join onto it, so a missing source
shows up as empty cells and can never add or remove rows.

Keys and time: the table is keyed on (station_id, hour_ist). hour_ist is the START of the hour in IST
(same convention as pollution_hourly.csv); hour_utc = hour_ist - 5:30, so it falls at :30 past the UTC hour.

Usage:
  python src/build_final_dataset.py [--out CSV]
Every check prints PASS or FAIL and the script exits with a non-zero code if one fails.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from era5_window import STUDY_END, STUDY_START  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FINAL = ROOT / "data" / "processed" / "stations_final.csv"
POLLUTION = ROOT / "data" / "processed" / "pollution_hourly.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "final_dataset.csv"

IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
ID_COLS = ["station_id", "name", "city", "sub_area", "group", "latitude", "longitude"]
KEY = ["station_id", "hour_ist"]
POLLUTANTS = ["pm25", "pm10", "no", "no2", "nox", "so2", "co", "o3"]
POLLUTION_COLS = (POLLUTANTS + [f"n_{p}" for p in POLLUTANTS]
                  + ["local_temp_c", "local_rh", "local_wind_speed", "network_pm25_share", "network_outage"])

results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def load_stations(path):
    """The final station list (54 stations); `id` becomes `station_id`."""
    st = pd.read_csv(path, encoding="utf-8-sig").rename(columns={"id": "station_id"})
    if st["station_id"].duplicated().any():
        sys.exit("duplicate station IDs in the station file")
    return st[ID_COLS].reset_index(drop=True)


def load_pollution(path):
    cols = KEY + ["hour_utc"] + POLLUTION_COLS
    return pd.read_csv(path, usecols=cols, parse_dates=["hour_ist", "hour_utc"])


def build_spine(stations, start, end):
    """One row per station and IST hour from `start` 00:00 to `end` 23:00, with hour_utc."""
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    spine = stations[ID_COLS].merge(pd.DataFrame({"hour_ist": hours}), how="cross")
    spine["hour_utc"] = spine["hour_ist"] - IST_OFFSET
    return spine[ID_COLS + ["hour_ist", "hour_utc"]]


def join_pollution(spine, pollution):
    """Left-join the pollution columns onto the spine. Stations not in the spine (validation station 8118)
    are dropped; the join must be one-to-one and the two hour_utc columns must agree."""
    pol = pollution[pollution["station_id"].isin(spine["station_id"])]
    out = spine.merge(pol, on=KEY, how="left", validate="one_to_one", suffixes=("", "_pollution"))
    both = out["hour_utc_pollution"].notna()
    if not (out.loc[both, "hour_utc"] == out.loc[both, "hour_utc_pollution"]).all():
        sys.exit("hour_utc in the pollution table disagrees with hour_ist - 5:30")
    return out.drop(columns="hour_utc_pollution")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", type=Path, default=STATIONS_FINAL)
    ap.add_argument("--pollution", type=Path, default=POLLUTION)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    print("Reading inputs")
    stations = load_stations(args.stations)
    pollution = load_pollution(args.pollution)
    print(f"  stations: {len(stations)}; pollution table: {len(pollution):,} rows, {pollution['station_id'].nunique()} stations")

    print("B1: spine and pollution")
    spine = build_spine(stations, STUDY_START, STUDY_END)
    table = join_pollution(spine, pollution)
    n_hours = len(pd.date_range(STUDY_START, pd.Timestamp(STUDY_END) + pd.Timedelta(hours=23), freq="h"))
    src = pollution[pollution["station_id"].isin(stations["station_id"])]

    print("\nChecks")
    check(f"{len(stations)} stations x {n_hours:,} hours = {len(stations) * n_hours:,} rows", len(table) == len(stations) * n_hours)
    check("no duplicate (station_id, hour_ist)", not table.duplicated(KEY).any())
    check("every station has every hour", (table.groupby("station_id").size() == n_hours).all())
    check("station set equals stations_final.csv", set(table["station_id"]) == set(stations["station_id"]))
    check("validation station 8118 is not in the table", 8118 not in set(table["station_id"]))
    t_keys, s_keys = table.set_index(KEY).index, src.set_index(KEY).index
    check("the spine and the pollution table hold the same station-hours (none lost, none empty)",
          t_keys.difference(s_keys).empty and s_keys.difference(t_keys).empty)
    check(f"PM2.5 rows unchanged by the join ({int(src['pm25'].notna().sum()):,})",
          int(table["pm25"].notna().sum()) == int(src["pm25"].notna().sum()))
    check("every pollution column equals its source value (all columns, NaN-safe)",
          table[POLLUTION_COLS].reset_index(drop=True).equals(
              src.merge(table[KEY], on=KEY, how="right")[POLLUTION_COLS].reset_index(drop=True)))
    print(f"  PM2.5 present in {int(table['pm25'].notna().sum()):,} of {len(table):,} rows "
          f"({table['pm25'].notna().mean():.1%}); outage rows: {int(table['network_outage'].sum()):,}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}: {len(table):,} rows, {table.shape[1]} columns (phase B1 only: identifiers and pollution)")

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
