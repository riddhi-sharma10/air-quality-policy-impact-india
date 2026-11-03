"""Build the final dataset: one row per station per IST hour (54 stations x 14,136 hours = 763,344 rows).

Built in phases, see docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md (Part B):
  B1  spine (every station x every hour of the study window) and the pollution join
  B2  gas/sensor realignment (B-10), weather (B-1), policy and calendar columns
  B3  fire columns (lag1 and lag2 only, empty-day rule G1, upwind from the previous day)   <- done here
The row count is fixed by the spine: every later join is a left join onto it, so a missing source
shows up as empty cells and can never add or remove rows.

Keys and time: the table is keyed on (station_id, hour_ist). hour_ist is the START of the PM2.5 hour in IST
(same convention as pollution_hourly.csv); hour_utc = hour_ist - 5:30, so it falls at :30 past the UTC hour.

Quality limits (decision B-11): gas and sensor values that are physically impossible or beyond the instrument range
(for example SO2 of 2e16 ppb, relative humidity below 0 or above 100) are set to empty before anything else is done to them.

Two alignment settings (decisions B-1 and B-10 in the plan):
  ERA5_STAMP_OFFSET_HOURS  weather is taken at the ERA5 stamp hour_utc.ceil('h') + this many hours (0 = the
                           stamp at the middle of the PM2.5 hour). Rain is the average of the stamp S and S + 1 h,
                           because the ERA5 value at T is the hour ending at T.
  NONPM_ALIGN_LAG_ROWS     gases and the stations' own sensors have real clock-time stamps, but the pollution file
                           labels every channel with the PM2.5 shift, so in one row they describe the hour after the
                           PM2.5. They are taken from the row this many hours earlier (set 0 to switch it off).

Usage:
  python src/build_final_dataset.py [--out CSV]      (writes the CSV and a Parquet copy next to it)
Every check prints PASS or FAIL; if one fails nothing is written and the script exits with a non-zero code.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_fire_lags import add_lags, assert_hourly_safe  # noqa: E402
from build_fire_features import haversine_km, load_detections  # noqa: E402
from era5_window import STUDY_END, STUDY_START  # noqa: E402
from fire_empty_days import apply_zero_days, classify_dates  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FINAL = ROOT / "data" / "processed" / "stations_final.csv"
POLLUTION = ROOT / "data" / "processed" / "pollution_hourly.csv"
ERA5_TABLE = ROOT / "data" / "processed" / "era5_station_hourly.csv"
GRAP_HOURLY = ROOT / "data" / "processed" / "grap_hourly.csv"
FIRE_DAILY = ROOT / "data" / "processed" / "fire_features_daily.csv"
FIRE_UPWIND = ROOT / "data" / "processed" / "fire_upwind_daily.csv"
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
# Fire (decision B-4): only lag1 and lag2 columns, which use detections strictly before the IST date of the row.
FIRE_RADII = [50, 100, 200]
UPWIND_RADIUS_KM, UPWIND_THETA_DEG = 100, 45      # the main upwind setting (decision G4); the other eight stay in fire_upwind_daily.csv
FIRE_LAG_COLS = [f"{b}_{r}km_lag{k}" for r in FIRE_RADII for b in ("n_nh", "frp_nh") for k in (1, 2)]
UPWIND_COLS = [f"{b}_{UPWIND_RADIUS_KM}km_{UPWIND_THETA_DEG}deg_lag1" for b in ("n_up_nh", "frp_up_nh")]
FIRE_COLS = FIRE_LAG_COLS + UPWIND_COLS + ["fire_day_status", "fire_is_nrt"]
DAY = pd.Timedelta(days=1)
# Decision B-11: gas and sensor values outside these limits are physically impossible or beyond the instrument range
# (pollution_hourly.csv only cleaned PM) and are set to empty before the realignment. Units are those in the file.
QC_LIMITS = {"no": (0, 2000), "no2": (0, 1000), "nox": (0, 10), "so2": (0, 1000), "o3": (0, 1000), "co": (0, 100),
             "local_temp_c": (-10, 55), "local_rh": (0, 100), "local_wind_speed": (0, 40)}
NO_VALUE = "none"  # text columns never hold empty cells: 'none' means no festival / no stage change yet

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


def outside_limits(values, lo, hi):
    """True where a value is present and outside [lo, hi]."""
    v = np.asarray(values, dtype=float)
    return (v < lo) | (v > hi)


def qc_gases_sensors(table, limits=QC_LIMITS):
    """Decision B-11: set values outside `limits` to empty. Returns the cleaned table and the number removed per column.
    The reading counts (n_*) are left as they are."""
    out = table.copy()
    removed = {}
    for c, (lo, hi) in limits.items():
        bad = outside_limits(out[c], lo, hi)
        removed[c] = int(bad.sum())
        out.loc[bad, c] = np.nan
    return out, removed


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
    of `grap_stage` (0 in the hour of the change) and its direction ('up' or 'down'). Before the first change the hours
    are empty and the direction is 'none'."""
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
    out["last_change_direction"] = direction.fillna(NO_VALUE).to_numpy()
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
    itself, `festival_window` the day before to the day after; `festival` names it ("none" outside, so the column
    never has empty cells and reads back with one type)."""
    out = table.copy()
    t = out["hour_ist"]
    day = t.dt.normalize()
    out["hour"] = t.dt.hour
    out["weekday"] = t.dt.dayofweek
    out["month"] = t.dt.month
    out["season"] = out["month"].map(SEASONS)
    name = pd.Series(NO_VALUE, index=out.index, dtype=object)
    on_day = pd.Series(False, index=out.index)
    in_window = pd.Series(False, index=out.index)
    for fest, date in FESTIVALS:
        gap = (day - pd.Timestamp(date)).dt.days
        w = gap.abs() <= 1
        name = name.where(~w | (name != NO_VALUE), fest)
        on_day |= gap == 0
        in_window |= w
    out["festival"], out["festival_day"], out["festival_window"] = name, on_day, in_window
    return out


def date_status(detections):
    """Decision G1: 'observed', 'zero_assumed' or 'outage' for every IST date from the first to the last detection."""
    c = detections.groupby("ist_date").size()
    c = c.reindex(pd.date_range(c.index.min(), c.index.max(), freq="D"), fill_value=0)
    return classify_dates(c)


def fire_lags_wide(daily, status):
    """Daily counts and FRP (confidence n and h) with the G1 rule applied, lag1 and lag2 recomputed from them,
    one row per station and IST date and one column per radius: `n_nh_50km_lag1` ... `frp_nh_200km_lag2`.

    lag1 on date d is the value on d - 1 and lag2 is d - 1 plus d - 2, so they use detections strictly before date d."""
    d = apply_zero_days(daily[["station_id", "radius_km", "ist_date", "n_nh", "frp_nh"]], status, ["n_nh", "frp_nh"])
    full = add_lags(d)
    values = [f"{b}_lag{k}" for b in ("n_nh", "frp_nh") for k in (1, 2)]
    w = full.pivot(index=["station_id", "ist_date"], columns="radius_km", values=values)
    w.columns = [f"{v[:-5]}_{r}km_{v[-4:]}" for v, r in w.columns]
    return w.reset_index()[["station_id", "ist_date"] + FIRE_LAG_COLS]


def upwind_lag1(upwind, status):
    """Upwind counts at the main setting (100 km, 45 degrees) with the G1 rule applied, moved forward one IST day:
    the value of date d - 1 is stored under date d (`fire_date`), because the upwind table holds same-day values."""
    u = upwind[(upwind["radius_km"] == UPWIND_RADIUS_KM) & (upwind["theta_deg"] == UPWIND_THETA_DEG)]
    u = apply_zero_days(u[["station_id", "ist_date", "n_up_nh", "frp_up_nh"]], status, ["n_up_nh", "frp_up_nh"])
    u = u.assign(fire_date=u["ist_date"] + DAY).drop(columns="ist_date")
    return u.rename(columns={"n_up_nh": UPWIND_COLS[0], "frp_up_nh": UPWIND_COLS[1]})


def join_fire(table, lags_wide, upwind_prev, status, nrt_first):
    """Decision B-4: attach the fire columns by station and the IST date of `hour_ist`. Every hour of date d gets
    the same values. `fire_day_status` is the status of date d - 1 (the lag1 day) and `fire_is_nrt` is true when d - 1
    is on or after the first near-real-time (preliminary) date."""
    assert_hourly_safe(FIRE_LAG_COLS + UPWIND_COLS)
    out = table.copy()
    out["fire_date"] = out["hour_ist"].dt.normalize()
    out = out.merge(lags_wide.rename(columns={"ist_date": "fire_date"}), on=["station_id", "fire_date"], how="left", validate="many_to_one")
    out = out.merge(upwind_prev, on=["station_id", "fire_date"], how="left", validate="many_to_one")
    prev = out["fire_date"] - DAY
    out["fire_day_status"] = prev.map(status)
    out["fire_is_nrt"] = prev >= nrt_first
    return out.drop(columns="fire_date")


def order_columns(table):
    cols = (ID_COLS + ["hour_ist", "hour_utc"] + POLLUTION_COLS + WEATHER_COLS + FIRE_COLS + POLICY_COLS + CALENDAR_COLS)
    return table[cols]


def check_fire(t, stations, det, status, daily, upwind, nrt_first, n_samples=40):
    """Phase B3 checks on the sorted table `t`. Expected values come from the raw detections, not from the merge code."""
    O = set(status.index[status == "outage"])
    Z = set(status.index[status == "zero_assumed"])
    window = pd.date_range(STUDY_START, STUDY_END, freq="D")
    in_range = status.loc[daily["ist_date"].min():daily["ist_date"].max()]
    nan_dates = set(daily.loc[daily["n_nh"].isna(), "ist_date"])
    check("the dates with no detection in the daily fire table are exactly the dates the rule classifies as empty",
          nan_dates == set(in_range.index[in_range != "observed"]))
    n_z, n_o = int((in_range == "zero_assumed").sum()), int((in_range == "outage").sum())
    check(f"empty-day rule (G1): {n_z} cloud days set to 0 and {n_o} outage days kept missing (plan: 8 and 14)", (n_z, n_o) == (8, 14))
    check("only lag1 / lag2 columns are used (assert_hourly_safe) and no lag0 or same-day column is present",
          not any("lag0" in c for c in t.columns) and all(c.endswith(("_lag1", "_lag2")) for c in FIRE_LAG_COLS + UPWIND_COLS))
    # the same values for all 24 hours of an IST date
    day = t["hour_ist"].dt.normalize()
    check("every fire column is constant within an IST date for each station (hourly rows use the previous days only)",
          (t.groupby(["station_id", day])[FIRE_LAG_COLS + UPWIND_COLS].nunique(dropna=False) <= 1).all().all())

    # which rows must be empty, from the status of d - 1 and d - 2
    d1, d2 = day - DAY, day - 2 * DAY
    out1, out2 = d1.isin(O), d2.isin(O)
    up_start = upwind["ist_date"].min()
    check("lag1 is empty exactly on the dates after an outage day (all radii, all rows)",
          all((t[f"n_nh_{r}km_lag1"].isna() == out1).all() and (t[f"frp_nh_{r}km_lag1"].isna() == out1).all() for r in FIRE_RADII))
    check("lag2 is empty exactly when d - 1 or d - 2 is an outage day (all radii, all rows)",
          all((t[f"n_nh_{r}km_lag2"].isna() == (out1 | out2)).all() and (t[f"frp_nh_{r}km_lag2"].isna() == (out1 | out2)).all() for r in FIRE_RADII))
    up_empty = out1 | (d1 < up_start)
    check(f"upwind lag1 is empty exactly after an outage day or before the upwind table starts ({up_start.date()}): "
          f"{int(up_empty.sum()):,} rows", all((t[c].isna() == up_empty).all() for c in UPWIND_COLS))
    z1 = d1.isin(Z)
    check("after a cloud day (zero assumed) lag1 is 0, not empty (all radii, upwind too)",
          all((t.loc[z1, f"n_nh_{r}km_lag1"] == 0).all() for r in FIRE_RADII) and (t.loc[z1 & (d1 >= up_start), UPWIND_COLS[0]] == 0).all())
    check("fire_day_status is the status of d - 1 (outage rows match the empty lag1 rows) and is never empty",
          t["fire_day_status"].notna().all() and ((t["fire_day_status"] == "outage") == out1).all() and ((t["fire_day_status"] == "zero_assumed") == z1).all())
    nrt_rows = int(t["fire_is_nrt"].sum())
    check(f"fire_is_nrt is true exactly from {(nrt_first + DAY).date()} (preliminary data in the lag): {nrt_rows:,} rows",
          (t["fire_is_nrt"] == (d1 >= nrt_first)).all() and nrt_rows == int(((window > nrt_first).sum()) * 24 * len(stations)))

    # independent recount from the raw detections: dates next to empty days on purpose
    ll = stations.set_index("station_id")[["latitude", "longitude"]]
    tt = t.set_index(KEY)
    rng = np.random.default_rng(3)
    special = [d for d in window if {d - DAY, d - 2 * DAY} & (O | Z)]
    dates = list(rng.choice(special, size=n_samples // 4, replace=False)) + list(rng.choice(window, size=n_samples - n_samples // 4, replace=False))
    det_by_day = {k: g for k, g in det[det["confidence"].isin(["n", "h"])].groupby("ist_date")}

    def day_value(sid, radius, d, what):
        if d in O:
            return np.nan
        if d in Z or d not in det_by_day:
            return 0.0
        g = det_by_day[d]
        near = g[haversine_km(ll.loc[sid, "latitude"], ll.loc[sid, "longitude"], g["latitude"].to_numpy(), g["longitude"].to_numpy()) <= radius]
        return float(len(near)) if what == "n" else float(near["frp"].sum())

    ok = True
    for d in dates:
        d = pd.Timestamp(d)
        sid = int(rng.choice(stations["station_id"]))
        r = int(rng.choice(FIRE_RADII))
        row = tt.loc[(sid, d + pd.Timedelta(hours=12))]
        for what, name in (("n", "n_nh"), ("frp", "frp_nh")):
            v1, v2 = day_value(sid, r, d - DAY, what), day_value(sid, r, d - 2 * DAY, what)
            tol = 1e-9 if what == "n" else 0.06  # the daily table keeps FRP to two decimals
            ok &= same([row[f"{name}_{r}km_lag1"]], [v1], tol) and same([row[f"{name}_{r}km_lag2"]], [v1 + v2], tol)
    check(f"{n_samples} station-dates recounted from the raw detections (lag1 and lag2, counts and FRP), a quarter of them next to empty days", ok)

    u = upwind[(upwind["radius_km"] == UPWIND_RADIUS_KM) & (upwind["theta_deg"] == UPWIND_THETA_DEG)].set_index(["station_id", "ist_date"])
    ok_u = True
    for d in rng.choice(window[2:], size=30, replace=False):
        d = pd.Timestamp(d)
        sid = int(rng.choice(stations["station_id"]))
        prev = d - DAY
        exp = np.nan if prev in O else (0.0 if prev in Z else float(u.loc[(sid, prev), "n_up_nh"]))
        ok_u &= same([tt.loc[(sid, d + pd.Timedelta(hours=5)), UPWIND_COLS[0]]], [exp])
    check("30 station-dates: upwind lag1 on date d equals the upwind table on date d - 1", ok_u)


def check_ranges(t):
    """Phase B4: plausible ranges. The bounds are physical limits, far wider than what the data show."""
    limits = {"pm25": (0, 1000), "pm10": (0, 2000), "t2m_c": (-10, 55), "d2m_c": (-30, 40), "sp_hpa": (850, 1100),
              "wind_speed": (0, 40), "wind_from_deg": (0, 360), "blh_m": (0, 8000), "tp_mm": (0, 200),
              "latitude": (24, 30), "longitude": (76, 86), "grap_stage": (0, 4), "grap_stage_applied": (0, 4),
              "hour": (0, 23), "weekday": (0, 6), "month": (1, 12), "network_pm25_share": (0, 1)}
    bad = {c: int(((t[c] < lo) | (t[c] > hi)).sum()) for c, (lo, hi) in limits.items()}
    check("values inside physical limits: " + ", ".join(f"{c} {lo} to {hi}" for c, (lo, hi) in list(limits.items())[:9]) + " ...",
          not any(bad.values()))
    for c, n in bad.items():
        if n:
            print(f"      {c}: {n:,} rows outside {limits[c]}")
    check("dewpoint is never above the temperature (small rounding allowed; rows without weather are not compared)",
          not ((t["d2m_c"] - t["t2m_c"]) > 0.01).any())
    counts = [c for c in t.columns if c.startswith("n_")]
    check("counts are not negative (n_* reading counts, fire counts)", all((t[c].dropna() >= 0).all() for c in counts))
    check("fire radius ordering: 50 km <= 100 km <= 200 km for lag1 and lag2 counts",
          all(((t[f"n_nh_50km_lag{k}"] <= t[f"n_nh_100km_lag{k}"]) | t[f"n_nh_100km_lag{k}"].isna()).all()
              and ((t[f"n_nh_100km_lag{k}"] <= t[f"n_nh_200km_lag{k}"]) | t[f"n_nh_200km_lag{k}"].isna()).all() for k in (1, 2)))
    check("upwind count (100 km, 45 degrees) is not above the all-direction count at 100 km (lag1)",
          ((t[UPWIND_COLS[0]] <= t["n_nh_100km_lag1"]) | t[UPWIND_COLS[0]].isna()).all())


# ---------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", type=Path, default=STATIONS_FINAL)
    ap.add_argument("--pollution", type=Path, default=POLLUTION)
    ap.add_argument("--weather", type=Path, default=ERA5_TABLE)
    ap.add_argument("--grap", type=Path, default=GRAP_HOURLY)
    ap.add_argument("--fire-daily", type=Path, default=FIRE_DAILY)
    ap.add_argument("--fire-upwind", type=Path, default=FIRE_UPWIND)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    print("Reading inputs")
    stations = load_stations(args.stations)
    pollution = load_pollution(args.pollution)
    era5 = load_weather(args.weather)
    grap = load_grap(args.grap)
    daily = pd.read_csv(args.fire_daily, usecols=["station_id", "radius_km", "ist_date", "n_nh", "frp_nh", "is_nrt"], parse_dates=["ist_date"])
    upwind = pd.read_csv(args.fire_upwind, usecols=["station_id", "ist_date", "radius_km", "theta_deg", "n_up_nh", "frp_up_nh"], parse_dates=["ist_date"])
    detections, _ = load_detections()
    print(f"  stations: {len(stations)}; pollution: {len(pollution):,} rows; weather: {len(era5):,} rows; GRAP: {len(grap):,} hours; "
          f"fire: {len(daily):,} daily rows, {len(upwind):,} upwind rows, {len(detections):,} detections")

    print("B1: spine and pollution")
    spine = build_spine(stations, STUDY_START, STUDY_END)
    joins = []   # (label, rows after the join, rows matched): the join report and its checks

    def log_join(label, tab, matched):
        joins.append((label, len(tab), int(np.asarray(matched).sum())))

    table = join_pollution(spine, pollution)
    pol_keys = pollution[pollution["station_id"].isin(stations["station_id"])].set_index(KEY).index
    log_join("pollution (station, hour)", table, table.set_index(KEY).index.isin(pol_keys))
    table, qc_removed = qc_gases_sensors(table)
    print("  B-11 values set to empty (outside physical limits): " + ", ".join(f"{c} {n:,}" for c, n in qc_removed.items() if n))
    n_st = len(stations)
    n_hours = len(pd.date_range(STUDY_START, pd.Timestamp(STUDY_END) + pd.Timedelta(hours=23), freq="h"))
    src = pollution[pollution["station_id"].isin(stations["station_id"])].sort_values(KEY).reset_index(drop=True)
    print(f"B2: realign gases and sensors by {NONPM_ALIGN_LAG_ROWS} row, weather (stamp offset {ERA5_STAMP_OFFSET_HOURS} h), policy, calendar")
    table = align_nonpm(table)
    table = join_weather(table, era5)
    log_join("weather (station, ERA5 stamp)", table, table["u10"].notna())
    table = join_policy(table, grap)
    log_join("policy (hour)", table, table["grap_stage"].notna())
    table = add_calendar(table)
    print("B3: fire columns (empty-day rule, lag1 and lag2, upwind from the previous day)")
    status = date_status(detections)
    nrt_first = daily.loc[daily["is_nrt"], "ist_date"].min()
    lags_wide, up_prev = fire_lags_wide(daily, status), upwind_lag1(upwind, status)
    day_key = pd.MultiIndex.from_arrays([table["station_id"], table["hour_ist"].dt.normalize()])
    table = join_fire(table, lags_wide, up_prev, status, nrt_first)
    log_join("fire lags (station, IST date)", table, day_key.isin(pd.MultiIndex.from_frame(lags_wide[["station_id", "ist_date"]])))
    log_join("upwind, previous day (station, IST date)", table, day_key.isin(pd.MultiIndex.from_frame(up_prev[["station_id", "fire_date"]])))
    table = order_columns(table)
    print("\nJoin report (rows matched and unmatched after each join)")
    for label, n, m in joins:
        print(f"  {label}: {m:,} matched, {n - m:,} unmatched, {n:,} rows after the join")

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
        a = src[c].to_numpy(dtype=float).copy()
        if c in QC_LIMITS:
            a[outside_limits(a, *QC_LIMITS[c])] = np.nan    # the expected value is the source after the B-11 limits
        a = a.reshape(shape)
        exp = np.full(shape, np.nan)
        exp[:, NONPM_ALIGN_LAG_ROWS:] = a[:, :n_hours - NONPM_ALIGN_LAG_ROWS]
        ok &= same(t[c].to_numpy(dtype=float).reshape(shape), exp)
    check(f"each of the {len(NONPM_COLS)} gas/sensor columns in hour h equals the source in hour h - {NONPM_ALIGN_LAG_ROWS}", ok)
    first = t["hour_ist"] < start_ist + NONPM_ALIGN_LAG_ROWS * HOUR
    check("the first hour of every station is empty for those columns", t.loc[first, NONPM_COLS].isna().all().all())

    print("Checks: B-11 quality limits")
    check("no gas or sensor value is outside its limits",
          not any(outside_limits(t[c], *lim).any() for c, lim in QC_LIMITS.items()))
    exp_removed = {c: int(outside_limits(src[c], *lim).sum()) for c, lim in QC_LIMITS.items()}
    check(f"the number of values removed equals the number outside the limits in the source ({sum(qc_removed.values()):,} values)",
          exp_removed == qc_removed)
    check("PM2.5 and PM10 are untouched by B-11 (their limits were applied when pollution_hourly.csv was built)",
          int(t["pm25"].notna().sum()) == int(src["pm25"].notna().sum()) and int(t["pm10"].notna().sum()) == int(src["pm10"].notna().sum()))

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

    print("Checks: joins")
    jd = {label.split(" (")[0] + ("_up" if label.startswith("upwind") else ""): (n, m) for label, n, m in joins}
    check(f"no join changed the number of rows (all {len(joins)} joins leave {n_st * n_hours:,} rows)", all(n == n_st * n_hours for _, n, _ in joins))
    day = t["hour_ist"].dt.normalize()
    up_first = upwind["ist_date"].min()
    exp_unmatched = {"pollution": 0, "weather": int((stamp_idx < 0).sum()), "policy": 0, "fire lags": 0,
                     "upwind, previous day_up": int((day < up_first + DAY).sum())}
    got_unmatched = {k: n - m for k, (n, m) in jd.items()}
    check("unmatched rows are exactly the expected ones: " + ", ".join(f"{k.replace('_up', '')} {v:,}" for k, v in exp_unmatched.items()),
          got_unmatched == exp_unmatched)

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

    print("Checks: fire (B3)")
    check_fire(t, stations, detections, status, daily, upwind, nrt_first)

    print("Checks: ranges (B4)")
    check_ranges(t)

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
    check("festival names are set exactly inside the windows ('none' outside)", ((t["festival"] != NO_VALUE) == t["festival_window"]).all())

    print("\nMissing values by column group")
    for label, cols in [("pollution", POLLUTION_COLS), ("weather", WEATHER_COLS), ("fire", FIRE_COLS), ("policy", POLICY_COLS), ("calendar", CALENDAR_COLS)]:
        n_empty = table[cols].isna().sum()
        print(f"  {label}: {int(n_empty.sum()):,} empty cells; columns with the most: "
              + ", ".join(f"{c} {int(v):,}" for c, v in n_empty.sort_values(ascending=False).head(3).items() if v > 0))

    failed = [label for label, ok in results if not ok]
    if not failed:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.out, index=False)
        table.to_parquet(args.out.with_suffix(".parquet"), index=False)
        print(f"\nwrote {args.out} and {args.out.with_suffix('.parquet').name}: {len(table):,} rows, {table.shape[1]} columns")
    else:
        print("\nnothing written: the output files are only written when every check passes")
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
