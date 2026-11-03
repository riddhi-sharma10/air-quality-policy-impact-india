"""Build the final dataset: one row per station per IST hour (54 stations x 14,136 hours = 763,344 rows).

Built in phases, see docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md (Part B):
  B1  spine (every station x every hour of the study window) and the pollution join
  B2  gas/sensor realignment (B-10), weather (B-1), policy and calendar columns     <- done here
  B3  fire columns
The row count is fixed by the spine: every later join is a left join onto it, so a missing source
shows up as empty cells and can never add or remove rows.

Keys and time: the table is keyed on (station_id, hour_ist). hour_ist is the START of the PM2.5 hour in IST
(same convention as pollution_hourly.csv); hour_utc = hour_ist - 5:30, so it falls at :30 past the UTC hour.

Two alignment settings (decisions B-1 and B-10 in the plan):
  ERA5_STAMP_OFFSET_HOURS  weather is taken at the ERA5 stamp hour_utc.ceil('h') + this many hours (0 = the
                           stamp at the middle of the PM2.5 hour). Rain is the average of the stamp S and S + 1 h,
                           because the ERA5 value at T is the hour ending at T.
  NONPM_ALIGN_LAG_ROWS     gases and the stations' own sensors have real clock-time stamps, but the pollution file
                           labels every channel with the PM2.5 shift, so in one row they describe the hour after the
                           PM2.5. They are taken from the row this many hours earlier (set 0 to switch it off).

Usage:
  python src/build_final_dataset.py [--out CSV]
Every check prints PASS or FAIL and the script exits with a non-zero code if one fails.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from era5_window import STUDY_END, STUDY_START  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FINAL = ROOT / "data" / "processed" / "stations_final.csv"
POLLUTION = ROOT / "data" / "processed" / "pollution_hourly.csv"
ERA5_TABLE = ROOT / "data" / "processed" / "era5_station_hourly.csv"
GRAP_HOURLY = ROOT / "data" / "processed" / "grap_hourly.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "final_dataset.csv"

ERA5_STAMP_OFFSET_HOURS = 0
NONPM_ALIGN_LAG_ROWS = 1

HOUR = pd.Timedelta(hours=1)
IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
ID_COLS = ["station_id", "name", "city", "sub_area", "group", "latitude", "longitude"]
KEY = ["station_id", "hour_ist"]
POLLUTANTS = ["pm25", "pm10", "no", "no2", "nox", "so2", "co", "o3"]
POLLUTION_COLS = (POLLUTANTS + [f"n_{p}" for p in POLLUTANTS]
                  + ["local_temp_c", "local_rh", "local_wind_speed", "network_pm25_share", "network_outage"])
# columns that stay in their row (PM channels and the network flags) and those moved by NONPM_ALIGN_LAG_ROWS
NONPM_GASES = ["no", "no2", "nox", "so2", "co", "o3"]
NONPM_COLS = NONPM_GASES + [f"n_{p}" for p in NONPM_GASES] + ["local_temp_c", "local_rh", "local_wind_speed"]
PM_COLS = [c for c in POLLUTION_COLS if c not in NONPM_COLS]
WEATHER_INSTANT = ["u10", "v10", "wind_speed", "wind_from_deg", "t2m_c", "d2m_c", "sp_hpa", "blh_m"]
WEATHER_COLS = ["era5_time_utc"] + WEATHER_INSTANT + ["tp_mm"]
POLICY_COLS = ["grap_stage", "grap_stage_applied", "schedule_version", "grap_uncertain", "grap_inferred",
               "hours_since_stage_change", "last_change_direction"]
CALENDAR_COLS = ["hour", "weekday", "month", "season", "festival", "festival_day", "festival_window"]

# Festival dates (IST), confirmed against the Delhi government notifications No.F.53/689/GAD/CN/2024-25 (2025)
# and No.F.53/812/GAD/CN/2025 of 04.12.2025 (2026). Holika Dahan is the day before Holi, so it falls in the window.
# Only dates inside the study window are listed (Dussehra 20 Oct 2026 and Diwali 8 Nov 2026 are after it).
FESTIVALS = [("Holi", "2025-03-14"), ("Dussehra", "2025-10-02"), ("Diwali", "2025-10-20"),
             ("New Year's Eve", "2025-12-31"), ("Holi", "2026-03-04")]
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "summer", 4: "summer", 5: "summer",
           6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post_monsoon", 11: "post_monsoon"}

results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def same(a, b, tol=1e-9):
    """Two arrays are equal where both are present and have empty cells in the same places."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return a.shape == b.shape and np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], atol=tol, rtol=0)


# ---------------------------------------------------------------------------------------------- B1
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


# ---------------------------------------------------------------------------------------------- B2
def align_nonpm(table, lag_rows=NONPM_ALIGN_LAG_ROWS):
    """Decision B-10: the gas and local-sensor columns in the row for hour h come from the row for hour h - lag_rows.

    Needs a complete spine (one row per station per hour), so a row shift is an hour shift; the first
    `lag_rows` hours of every station become empty for these columns."""
    out = table.copy()
    if lag_rows == 0:
        return out
    order = table.sort_values(KEY).index
    s = table.loc[order]
    if not (s.groupby("station_id")["hour_ist"].diff().dropna() == HOUR).all():
        sys.exit("the table is not a complete hourly spine, so a row shift is not an hour shift")
    shifted = s.groupby("station_id")[NONPM_COLS].shift(lag_rows)
    out[NONPM_COLS] = shifted.reindex(table.index)
    return out


def load_weather(path):
    cols = ["station_id", "time_utc"] + WEATHER_INSTANT + ["tp_mm"]
    return pd.read_csv(path, usecols=cols, parse_dates=["time_utc"])


def join_weather(table, era5, offset_hours=ERA5_STAMP_OFFSET_HOURS):
    """Decision B-1. Instant variables at S = hour_utc.ceil('h') + offset; rain = 0.5 x tp(S) + 0.5 x tp(S + 1 h).

    `era5_time_utc` is S where the stamp exists in the ERA5 table and empty where it does not."""
    stamp = table["hour_utc"].dt.ceil("h") + pd.Timedelta(hours=offset_hours)
    key = pd.DataFrame({"station_id": table["station_id"].to_numpy(), "time_utc": stamp.to_numpy()})
    inst = key.merge(era5[["station_id", "time_utc"] + WEATHER_INSTANT], on=["station_id", "time_utc"], how="left", validate="many_to_one")
    rain = era5[["station_id", "time_utc", "tp_mm"]]
    cur = key.merge(rain, on=["station_id", "time_utc"], how="left", validate="many_to_one")
    nxt = key.assign(time_utc=key["time_utc"] + HOUR).merge(rain, on=["station_id", "time_utc"], how="left", validate="many_to_one")
    out = table.copy()
    for c in WEATHER_INSTANT:
        out[c] = inst[c].to_numpy()
    out["tp_mm"] = 0.5 * cur["tp_mm"].to_numpy() + 0.5 * nxt["tp_mm"].to_numpy()
    out["era5_time_utc"] = pd.Series(stamp.to_numpy(), index=out.index).where(inst["u10"].notna().to_numpy())
    return out


def stage_events(grap):
    """Event-time columns on the hourly GRAP frame (one row per hour, sorted): hours since the last change
    of `grap_stage` (0 in the hour of the change) and its direction. Empty before the first change."""
    n = len(grap)
    stage = grap["grap_stage"].to_numpy()
    change = np.zeros(n, dtype=bool)
    change[1:] = stage[1:] != stage[:-1]
    pos = np.arange(n)
    last = pd.Series(np.where(change, pos, np.nan)).ffill().to_numpy()
    up = np.zeros(n, dtype=bool)
    up[1:] = stage[1:] > stage[:-1]
    direction = pd.Series(np.where(change, np.where(up, "up", "down"), None), dtype=object).ffill()
    out = grap.copy()
    out["hours_since_stage_change"] = pos - last
    out["last_change_direction"] = direction.to_numpy()
    return out


def load_grap(path):
    g = pd.read_csv(path, parse_dates=["ts_ist"]).rename(
        columns={"ts_ist": "hour_ist", "uncertain": "grap_uncertain", "inferred": "grap_inferred"})
    if g["hour_ist"].duplicated().any() or not (g["hour_ist"].diff().dropna() == HOUR).all():
        sys.exit("grap_hourly.csv must hold one row per hour, in order")
    return stage_events(g)


def join_policy(table, grap):
    """GRAP columns by hour (the same for every station), plus `grap_stage_applied`: the stage for treated
    stations and 0 for control stations (decision B-5)."""
    cols = ["hour_ist", "grap_stage", "schedule_version", "grap_uncertain", "grap_inferred",
            "hours_since_stage_change", "last_change_direction"]
    out = table.merge(grap[cols], on="hour_ist", how="left", validate="many_to_one")
    out["grap_stage_applied"] = np.where(out["group"] == "treated", out["grap_stage"], 0)
    return out


def add_calendar(table):
    """hour, weekday (0 = Monday), month, season and festival flags from IST dates. `festival_day` is the day
    itself, `festival_window` the day before to the day after; `festival` names it (empty outside)."""
    out = table.copy()
    t = out["hour_ist"]
    day = t.dt.normalize()
    out["hour"] = t.dt.hour
    out["weekday"] = t.dt.dayofweek
    out["month"] = t.dt.month
    out["season"] = out["month"].map(SEASONS)
    name = pd.Series("", index=out.index, dtype=object)
    on_day = pd.Series(False, index=out.index)
    in_window = pd.Series(False, index=out.index)
    for fest, date in FESTIVALS:
        gap = (day - pd.Timestamp(date)).dt.days
        w = gap.abs() <= 1
        name = name.where(~w | (name != ""), fest)
        on_day |= gap == 0
        in_window |= w
    out["festival"], out["festival_day"], out["festival_window"] = name, on_day, in_window
    return out


def order_columns(table):
    cols = (ID_COLS + ["hour_ist", "hour_utc"] + POLLUTION_COLS + WEATHER_COLS + POLICY_COLS + CALENDAR_COLS)
    return table[cols]


# ---------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", type=Path, default=STATIONS_FINAL)
    ap.add_argument("--pollution", type=Path, default=POLLUTION)
    ap.add_argument("--weather", type=Path, default=ERA5_TABLE)
    ap.add_argument("--grap", type=Path, default=GRAP_HOURLY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    print("Reading inputs")
    stations = load_stations(args.stations)
    pollution = load_pollution(args.pollution)
    era5 = load_weather(args.weather)
    grap = load_grap(args.grap)
    print(f"  stations: {len(stations)}; pollution: {len(pollution):,} rows; weather: {len(era5):,} rows; GRAP: {len(grap):,} hours")

    print("B1: spine and pollution")
    spine = build_spine(stations, STUDY_START, STUDY_END)
    table = join_pollution(spine, pollution)
    n_st = len(stations)
    n_hours = len(pd.date_range(STUDY_START, pd.Timestamp(STUDY_END) + pd.Timedelta(hours=23), freq="h"))
    src = pollution[pollution["station_id"].isin(stations["station_id"])].sort_values(KEY).reset_index(drop=True)
    print(f"B2: realign gases and sensors by {NONPM_ALIGN_LAG_ROWS} row, weather (stamp offset {ERA5_STAMP_OFFSET_HOURS} h), policy, calendar")
    table = align_nonpm(table)
    table = join_weather(table, era5)
    table = join_policy(table, grap)
    table = add_calendar(table)
    table = order_columns(table)

    # ------------------------------------------------------------------ checks (expected values by plain index arithmetic)
    t = table.sort_values(KEY).reset_index(drop=True)
    start_ist = pd.Timestamp(STUDY_START)
    hidx = ((t["hour_ist"] - start_ist) // HOUR).to_numpy()
    shape = (n_st, n_hours)
    print("\nChecks: B1")
    check(f"{n_st} stations x {n_hours:,} hours = {n_st * n_hours:,} rows", len(table) == n_st * n_hours)
    check("no duplicate (station_id, hour_ist)", not table.duplicated(KEY).any())
    check("every station has every hour", (table.groupby("station_id").size() == n_hours).all())
    check("station set equals stations_final.csv; validation station 8118 absent",
          set(table["station_id"]) == set(stations["station_id"]) and 8118 not in set(table["station_id"]))
    check("the table and the pollution table hold the same station-hours",
          t.set_index(KEY).index.equals(src.set_index(KEY).index))
    check(f"PM2.5 rows unchanged ({int(src['pm25'].notna().sum()):,})", int(table["pm25"].notna().sum()) == int(src["pm25"].notna().sum()))
    check("PM and network columns equal their source values (not moved)",
          all(same(t[c].astype(float), src[c].astype(float)) for c in PM_COLS))

    print("Checks: B-10 gas and sensor realignment")
    ok = True
    for c in NONPM_COLS:
        a = src[c].to_numpy(dtype=float).reshape(shape)
        exp = np.full(shape, np.nan)
        exp[:, NONPM_ALIGN_LAG_ROWS:] = a[:, :n_hours - NONPM_ALIGN_LAG_ROWS]
        ok &= same(t[c].to_numpy(dtype=float).reshape(shape), exp)
    check(f"each of the {len(NONPM_COLS)} gas/sensor columns in hour h equals the source in hour h - {NONPM_ALIGN_LAG_ROWS}", ok)
    first = t["hour_ist"] < start_ist + NONPM_ALIGN_LAG_ROWS * HOUR
    check("the first hour of every station is empty for those columns", t.loc[first, NONPM_COLS].isna().all().all())

    print("Checks: B-1 weather")
    e = era5.sort_values(["station_id", "time_utc"])
    t0 = e["time_utc"].min()
    ok_e = e.groupby("station_id").size().nunique() == 1 and (e.groupby("station_id")["time_utc"].diff().dropna() == HOUR).all()
    check("the weather table is a complete hourly series for every station", ok_e)
    sidx = {sid: g for sid, g in e.groupby("station_id")}
    stamp_idx = (((t["hour_utc"].dt.ceil("h") + pd.Timedelta(hours=ERA5_STAMP_OFFSET_HOURS)) - t0) // HOUR).to_numpy()
    n_e = e.groupby("station_id").size().iloc[0]
    ok_w, ok_rain = True, True
    for sid in stations["station_id"]:
        m = (t["station_id"] == sid).to_numpy()
        g, ix = sidx[sid], stamp_idx[m]
        valid = (ix >= 0) & (ix < n_e)
        for c in WEATHER_INSTANT:
            arr = g[c].to_numpy(dtype=float)
            exp = np.where(valid, arr[np.clip(ix, 0, n_e - 1)], np.nan)
            ok_w &= same(t.loc[m, c].to_numpy(dtype=float), exp)
        tp = g["tp_mm"].to_numpy(dtype=float)
        v2 = (ix >= 0) & (ix + 1 < n_e)
        exp = np.where(v2, 0.5 * tp[np.clip(ix, 0, n_e - 1)] + 0.5 * tp[np.clip(ix + 1, 0, n_e - 1)], np.nan)
        ok_rain &= same(t.loc[m, "tp_mm"].to_numpy(dtype=float), exp)
    check("instant weather variables equal the ERA5 table at the stamp (all stations, all rows)", ok_w)
    check("rain equals 0.5 x tp(S) + 0.5 x tp(S + 1 h) (all stations, all rows)", ok_rain)
    miss = t[WEATHER_INSTANT + ["tp_mm"]].isna().any(axis=1)
    exp_miss = (stamp_idx < 0) | (stamp_idx + 1 >= n_e)  # the stamp, or the next one for rain, is outside the ERA5 table
    check(f"weather is empty exactly where the stamp (or the next one, for rain) is outside the ERA5 table ({int(miss.sum())} rows, "
          f"the first {int(miss.sum()) // n_st} hours of the window for every station)",
          (miss.to_numpy() == exp_miss).all() and t.loc[miss, "hour_ist"].max() < start_ist + (int(miss.sum()) // n_st) * HOUR)
    check("era5_time_utc is set exactly where the weather is present", (t["era5_time_utc"].notna() == ~miss).all())

    print("Checks: policy")
    g_stage = grap["grap_stage"].to_numpy(dtype=float)
    check("grap_stage equals grap_hourly.csv at every hour (all rows)", same(t["grap_stage"].to_numpy(dtype=float), g_stage[hidx]))
    check("no missing GRAP values", t[["grap_stage", "schedule_version", "grap_uncertain", "grap_inferred"]].notna().all().all())
    treated = t["group"] == "treated"
    check("grap_stage_applied = grap_stage for treated stations and 0 for control",
          (t.loc[treated, "grap_stage_applied"] == t.loc[treated, "grap_stage"]).all() and (t.loc[~treated, "grap_stage_applied"] == 0).all())
    per = t[t["station_id"] == stations["station_id"].iloc[0]]
    changes = per["grap_stage"].ne(per["grap_stage"].shift()).iloc[1:]
    first_change = per.loc[changes[changes].index[0], "hour_ist"]
    n_pre = int(((per["hour_ist"] < first_change)).sum())
    check(f"{int(changes.sum())} stage changes; hours_since_stage_change is empty only before the first one ({n_pre} hours per station)",
          int(per["hours_since_stage_change"].isna().sum()) == n_pre and per.loc[changes[changes].index, "hours_since_stage_change"].eq(0).all())
    d = per.loc[changes[changes].index, "last_change_direction"].value_counts().to_dict()
    check(f"direction of the changes: {d.get('up', 0)} up and {d.get('down', 0)} down, matching the stage steps",
          d.get("up", 0) == int((per["grap_stage"].diff().iloc[1:] > 0).sum()) and d.get("down", 0) == int((per["grap_stage"].diff().iloc[1:] < 0).sum()))

    print("Checks: calendar")
    ts = t["hour_ist"]
    check("hour, weekday, month agree with the timestamp (20 Oct 2025 is a Monday)",
          (t["hour"] == ts.dt.hour).all() and (t["weekday"] == ts.dt.dayofweek).all() and (t["month"] == ts.dt.month).all()
          and int(t.loc[ts == pd.Timestamp("2025-10-20 12:00"), "weekday"].iloc[0]) == 0)
    check("every row has a season; seasons follow the month (Dec-Feb winter ... Oct-Nov post_monsoon)",
          t["season"].notna().all() and (t["season"] == t["month"].map(SEASONS)).all())
    fd, fw = int(t["festival_day"].sum()), int(t["festival_window"].sum())
    check(f"festival rows: {len(FESTIVALS)} festival days x 24 hours x {n_st} stations = {len(FESTIVALS) * 24 * n_st:,} (found {fd:,}); "
          f"windows of 3 days = {len(FESTIVALS) * 72 * n_st:,} (found {fw:,})",
          fd == len(FESTIVALS) * 24 * n_st and fw == len(FESTIVALS) * 72 * n_st)
    check("festival names are set exactly inside the windows", ((t["festival"] != "") == t["festival_window"]).all())

    print("\nMissing values by column group")
    for label, cols in [("pollution", POLLUTION_COLS), ("weather", WEATHER_COLS), ("policy", POLICY_COLS), ("calendar", CALENDAR_COLS)]:
        n_empty = table[cols].isna().sum()
        print(f"  {label}: {int(n_empty.sum()):,} empty cells; columns with the most: "
              + ", ".join(f"{c} {int(v):,}" for c, v in n_empty.sort_values(ascending=False).head(3).items() if v > 0))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}: {len(table):,} rows, {table.shape[1]} columns (phases B1 and B2: fire columns come in B3)")

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
