"""Scan the OpenAQ archive files for the two test stations.

A. Units: for every (station, parameter, units, sensor) the first and last date seen, so you can
   see whether a pollutant changes unit inside the study window.
B. Cadence: PM2.5 only. At which minute of the hour does the value change? If the source is
   hourly and repeated across 15-minute stamps, the changes sit at one minute, and that minute
   is the real hour boundary.

Usage: python src/openaq_scan_units_cadence.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "openaq_archive"
SETS = {
    "6358 2025-26": BASE / "6358",
    "2456 2025-26": BASE / "2456",
    "6358 2022-01 (test month)": BASE / "test" / "6358_2022-01",
    "2456 2022-01 (test month)": BASE / "test" / "2456_2022-01",
}


def load(folder):
    frames = []
    for f in sorted(folder.rglob("*.csv.gz")):
        df = pd.read_csv(f, usecols=["sensors_id", "datetime", "parameter", "units", "value"])
        assert df["datetime"].str.endswith("+05:30").all(), f.name
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["t"] = pd.to_datetime(df["datetime"].str[:19])  # local IST clock time
    return df


data = {name: load(folder) for name, folder in SETS.items()}

# ---------------------------------------------------------------- A. units over time
print("A. UNITS: (parameter, units, sensor) with first and last date, 2025-26 files")
for name in ("6358 2025-26", "2456 2025-26"):
    df = data[name]
    g = df.groupby(["parameter", "units", "sensors_id"])["t"].agg(first="min", last="max", days=lambda s: s.dt.normalize().nunique(), rows="size")
    g["first"], g["last"] = g["first"].dt.date, g["last"].dt.date
    print(f"\n-- station {name.split()[0]}")
    print(g.to_string())
    multi = df.groupby("parameter")["units"].nunique()
    multi = multi[multi > 1]
    print("parameters with more than one unit in 2025-26:", list(multi.index) or "none")
print("\n-- units seen in the 2022-01 test months")
for name in ("6358 2022-01 (test month)", "2456 2022-01 (test month)"):
    print(name, data[name].groupby("parameter")["units"].unique().apply(list).to_dict())

# ---------------------------------------------------------------- B. cadence of PM2.5
print("\nB. CADENCE (PM2.5): where does the value change?")
for name, df in data.items():
    pm = df[(df["parameter"] == "pm25") & df["value"].notna()].sort_values(["sensors_id", "t"]).copy()
    print("\n" + "=" * 70)
    print(name, f"- {len(pm):,} PM2.5 records, sensors {sorted(pm['sensors_id'].unique().tolist())}")
    print("minute of hour of all stamps:", pm["t"].dt.minute.value_counts().sort_index().to_dict())

    # (1) consecutive stamps exactly 15 minutes apart: how often does the value change, by minute of the later stamp?
    prev_t, prev_v = pm.groupby("sensors_id")["t"].shift(), pm.groupby("sensors_id")["value"].shift()
    pair = (pm["t"] - prev_t) == pd.Timedelta(minutes=15)
    chg = (pm["value"] != prev_v)[pair]
    by_min = pd.DataFrame({"pairs": chg.groupby(pm["t"][pair].dt.minute).size(),
                           "share_changed": chg.groupby(pm["t"][pair].dt.minute).mean().round(3)})
    print("(1) 15-min neighbours: share of pairs where the value changed, by minute of the LATER stamp")
    print(by_min.to_string())

    # (2) which grouping into clock hours gives the most uniform hours?
    print("(2) share of hour-groups (>= 2 records) holding ONE value, by hour-boundary offset")
    rows = []
    for off in (0, 15, 30, 45):
        key = (pm["t"] - pd.Timedelta(minutes=off)).dt.floor("h")
        grp = pm.groupby([pm["sensors_id"], key])["value"].agg(["size", "nunique"])
        grp = grp[grp["size"] >= 2]
        rows.append({"hour starts at minute": off, "groups": len(grp), "all_one_value": round(float((grp["nunique"] == 1).mean()), 3),
                     "groups_with_4_records": round(float((grp["size"] == 4).mean()), 3)})
    print(pd.DataFrame(rows).to_string(index=False))

    # (3) first and last stamp of each day
    day = pm["t"].dt.normalize()
    first = pm.groupby(["sensors_id", day])["t"].min().dt.strftime("%H:%M").value_counts().head(4).to_dict()
    last = pm.groupby(["sensors_id", day])["t"].max().dt.strftime("%H:%M").value_counts().head(4).to_dict()
    print("(3) most common first stamp of a day:", first)
    print("    most common last stamp of a day: ", last)
