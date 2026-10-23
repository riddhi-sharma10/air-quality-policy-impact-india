"""Rank every downloaded OpenAQ station by hours of PM2.5 and PM10 inside the study window.

Study window (IST dates): 2025-02-19 to 2026-09-30 = 589 days = 14,136 hours.
A clock hour counts when at least one non-null, non-negative reading of that pollutant exists in it
(timestamps are IST, so hour = floor of the IST clock time). Output: data/processed/station_coverage.csv

Usage: python src/openaq_station_coverage.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "openaq_archive"
OUT = ROOT / "data" / "processed" / "station_coverage.csv"
START, END = pd.Timestamp("2025-02-19"), pd.Timestamp("2026-09-30")
WINDOW_HOURS = ((END - START).days + 1) * 24


def file_date(path):
    return pd.Timestamp(path.name.split("-")[-1].split(".")[0])


def coverage(sid):
    files = [f for f in (BASE / str(sid)).rglob("*.csv.gz") if START <= file_date(f) <= END]
    parts, n_rows = [], 0
    for f in files:
        df = pd.read_csv(f, usecols=["datetime", "parameter", "value"])
        n_rows += len(df)
        df = df[df["parameter"].isin(["pm25", "pm10"]) & df["value"].notna()]
        if len(df):
            assert df["datetime"].str.endswith("+05:30").all(), f.name
            parts.append(pd.DataFrame({"parameter": df["parameter"].to_numpy(),
                                       "hour": pd.to_datetime(df["datetime"].str[:19]).dt.floor("h"),
                                       "value": df["value"].to_numpy()}))
    row = {"id": sid, "n_files": len(files), "n_rows": n_rows}
    h = {}
    if parts:
        all_ = pd.concat(parts, ignore_index=True)
        for p in ("pm25", "pm10"):
            sub = all_[(all_["parameter"] == p) & (all_["value"] >= 0)]
            h[p] = set(sub["hour"].unique())
    row["hours_pm25"] = len(h.get("pm25", ()))
    row["hours_pm10"] = len(h.get("pm10", ()))
    row["hours_both"] = len(h.get("pm25", set()) & h.get("pm10", set()))
    return row


if __name__ == "__main__":
    stations = pd.read_csv(ROOT / "data" / "processed" / "stations.csv", encoding="utf-8-sig")
    val = pd.read_csv(ROOT / "data" / "processed" / "stations_validation_airnow.csv")
    meta = pd.concat([stations, val], ignore_index=True)[["id", "name", "city", "sub_area", "group", "pair_flag"]]
    ids = [i for i in meta["id"] if (BASE / str(i)).exists()]
    rows = []
    for i in ids:  # sequential: parallel workers ran out of memory on this machine
        rows.append(coverage(i))
        print(f"{i}: {rows[-1]['hours_both']} PM2.5+PM10 hours", flush=True)
    out = meta.merge(pd.DataFrame(rows), on="id", how="left")
    for p in ("pm25", "pm10", "both"):
        out[f"pct_{p}"] = (out[f"hours_{p}"] / WINDOW_HOURS * 100).round(1)
    out = out.sort_values("hours_both", ascending=False)
    out.to_csv(OUT, index=False)
    print(f"window = {WINDOW_HOURS} hours; {len(rows)} of {len(meta)} stations downloaded")
    print(out.drop(columns=["city", "sub_area"]).to_string(index=False))
