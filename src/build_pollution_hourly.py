"""Aggregate the OpenAQ archive (15-minute and hourly records) to one row per station per hour.

Window: 2025-02-19 to 2026-09-30 (IST), 14,136 hours per station, every hour present (NaN when missing).
Stations: data/processed/stations_final.csv (from select_stations.py) plus the AirNow validation station 8118.

Rules (all documented in docs/pollution_hourly_dictionary.md):
  * Group readings by the IST clock hour of the timestamp (HH:00 to HH:45); aggregate = mean of the readings.
    n_<param> = number of readings in the hour. Several sensors of one parameter at a station are averaged per stamp.
  * Label: the archive timestamps mark the END of the measurement interval (tested against AirNow 8118, see
    docs/project_status.md), so the hour grouped under stamp-hour H covers [H-1, H). `hour_ist` is the hour
    BEGINNING (= stamp hour minus 1 h); `stamp_hour_ist` keeps the raw stamp hour.
  * hour_utc = hour_ist - 5:30 (so it falls at :30 past the UTC hour; alignment with ERA5 is decided at merge time).
  * QC (counts in data/processed/pollution_quality_report.csv): negatives -> NaN; implausible highs
    (PM2.5 > 1000, PM10 > 2000) -> NaN; PM flat-lines (>= 24 identical consecutive valid hours) -> NaN;
    spikes (hour-to-hour PM change > 300 ug/m3) are counted but NOT removed.
  * network_outage = True when fewer than half of the kept stations have PM2.5 in that hour (flagged, not removed).
  * Local sensors (temperature, relative humidity, wind speed) are kept as local_* for the ERA5 comparison.

Usage: python src/build_pollution_hourly.py [station_id ...]    (default: all)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "openaq_archive"
PROC = ROOT / "data" / "processed"
OUT = PROC / "pollution_hourly.csv"
REPORT = PROC / "pollution_quality_report.csv"
UNITS_OUT = PROC / "pollution_units.csv"

START, END = pd.Timestamp("2025-02-19"), pd.Timestamp("2026-09-30")
GRID = pd.date_range(START, END + pd.Timedelta(hours=23), freq="h")  # hour-beginning labels (IST)
POLLUTANTS = ["pm25", "pm10", "no", "no2", "nox", "so2", "co", "o3"]
LOCAL = {"temperature": "local_temp_c", "relativehumidity": "local_rh", "wind_speed": "local_wind_speed"}
MAX_PLAUSIBLE = {"pm25": 1000, "pm10": 2000}
FLAT_HOURS = 24
SPIKE = 300
OUTAGE_SHARE = 0.5


def file_date(path):
    return pd.Timestamp(path.name.split("-")[-1].split(".")[0])


def read_station(sid):
    # stamp hours START+1h .. END+1d 00:00 label hours START .. END 23:00, so read files up to END+1 day
    files = [f for f in (BASE / str(sid)).rglob("*.csv.gz") if START <= file_date(f) <= END + pd.Timedelta(days=1)]
    frames = [pd.read_csv(f, usecols=["sensors_id", "datetime", "parameter", "units", "value"],
                          encoding="latin-1") for f in sorted(files)]
    df = pd.concat(frames, ignore_index=True)
    assert df["datetime"].str.endswith("+05:30").all(), f"unexpected offset at {sid}"
    df["t"] = pd.to_datetime(df["datetime"].str[:19])
    df["units"] = df["units"].str.replace(r"[^\x20-\x7e]", "u", regex=True)
    df["units"] = df["units"].str.replace(r"^u+g/mu+$", "ug/m3", regex=True)  # archive writes ug/m3 with non-ASCII bytes
    return df, len(files)


def flat_runs(s, min_len):
    """Boolean mask of valid hours inside runs of >= min_len identical consecutive values (NaN breaks a run)."""
    v = s.to_numpy()
    new = np.r_[True, (v[1:] != v[:-1]) | np.isnan(v[1:]) | np.isnan(v[:-1])]
    run_id = np.cumsum(new)
    sizes = pd.Series(run_id).map(pd.Series(run_id).value_counts()).to_numpy()
    return (sizes >= min_len) & ~np.isnan(v)


def station_hourly(sid):
    df, n_files = read_station(sid)
    unit_rows = df.groupby(["parameter", "units"]).size().reset_index(name="n").assign(station_id=sid)
    keep = df[df["parameter"].isin(POLLUTANTS + list(LOCAL))]
    n_sensors = keep.groupby("parameter")["sensors_id"].nunique()
    # one value per stamp and parameter (mean across sensors), then per clock hour
    per_stamp = keep.groupby(["parameter", "t"])["value"].mean().reset_index()
    per_stamp["stamp_hour"] = per_stamp["t"].dt.floor("h")
    # hours holding more than one distinct value (mid-hour changes), for the findings report
    multi = per_stamp.groupby(["parameter", "stamp_hour"])["value"].nunique()

    out = pd.DataFrame(index=GRID)
    out.index.name = "hour_ist"
    qc = []
    for p in POLLUTANTS + list(LOCAL):
        sub = per_stamp[per_stamp["parameter"] == p]
        agg = sub.groupby("stamp_hour")["value"].agg(["mean", "count"])
        agg.index = agg.index - pd.Timedelta(hours=1)  # end-of-interval stamp -> hour beginning
        agg = agg.reindex(GRID)
        col = LOCAL.get(p, p)
        out[col] = agg["mean"]
        if p in POLLUTANTS:
            out[f"n_{p}"] = agg["count"].fillna(0).astype("int16")
            n_valid0 = int(out[col].notna().sum())
            neg = int((out[col] < 0).sum())
            out.loc[out[col] < 0, col] = np.nan
            high = 0
            if p in MAX_PLAUSIBLE:
                high = int((out[col] > MAX_PLAUSIBLE[p]).sum())
                out.loc[out[col] > MAX_PLAUSIBLE[p], col] = np.nan
            flat = spike = 0
            if p in MAX_PLAUSIBLE:
                mask = flat_runs(out[col], FLAT_HOURS)
                flat = int(mask.sum())
                out.loc[mask, col] = np.nan
                spike = int((out[col].diff().abs() > SPIKE).sum())
            m = multi.get(p, pd.Series(dtype=int))
            qc.append({"station_id": sid, "parameter": p, "hours_in_window": len(GRID), "hours_with_data": n_valid0,
                       "negative": neg, "implausibly_high": high, "flatline_hours": flat, "spikes_gt300": spike,
                       "hours_valid_after_qc": int(out[col].notna().sum()), "n_sensors": int(n_sensors.get(p, 0)),
                       "hours_multi_value": int((m > 1).sum()), "hours_total_with_stamps": int(len(m))})
    out.insert(0, "station_id", sid)
    out["hour_utc"] = out.index - pd.Timedelta(hours=5, minutes=30)
    out["stamp_hour_ist"] = out.index + pd.Timedelta(hours=1)
    return out.reset_index(), qc, unit_rows, n_files


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]]
    if not ids:
        ids = pd.read_csv(PROC / "stations_final.csv")["id"].tolist()
        ids += pd.read_csv(PROC / "stations_validation_airnow.csv")["id"].tolist()
    frames, qcs, units = [], [], []
    for sid in ids:
        h, qc, u, n_files = station_hourly(sid)
        frames.append(h)
        qcs += qc
        units.append(u)
        print(f"{sid}: {n_files} files, PM2.5 hours {int(h['pm25'].notna().sum())}, PM10 hours {int(h['pm10'].notna().sum())}",
              flush=True)
    cols = ["station_id", "hour_ist", "hour_utc", "stamp_hour_ist"] + POLLUTANTS + list(LOCAL.values()) \
        + [f"n_{p}" for p in POLLUTANTS] + ["network_pm25_share", "network_outage"]
    table = pd.concat(frames, ignore_index=True)
    # Network outage flag: share of the kept stations (not 8118) with PM2.5 in that hour; below half = outage.
    # Flagged, not dropped: the analysis decides (default: exclude flagged hours, they are outages, not clean air).
    kept = table["station_id"].isin(pd.read_csv(PROC / "stations_final.csv")["id"])
    share = table[kept].groupby("hour_ist")["pm25"].apply(lambda s: s.notna().mean())
    table["network_pm25_share"] = table["hour_ist"].map(share).round(3)
    table["network_outage"] = table["network_pm25_share"] < OUTAGE_SHARE
    table[cols].to_csv(OUT, index=False, float_format="%.6g")
    print(f"network outage hours: {int((share < OUTAGE_SHARE).sum())} of {len(share)}")
    pd.DataFrame(qcs).to_csv(REPORT, index=False)
    u = pd.concat(units, ignore_index=True).groupby(["parameter", "units"]).agg(
        stations=("station_id", "nunique"), n=("n", "sum")).reset_index()
    u.to_csv(UNITS_OUT, index=False)
    print(f"wrote {OUT.name}, {REPORT.name}, {UNITS_OUT.name}")
