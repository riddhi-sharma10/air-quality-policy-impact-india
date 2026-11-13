"""Independent validation of data/processed/final_dataset.parquet (task M2, gate G1).

The build script (src/build_final_dataset.py) already runs 45 checks while it builds the table.
This script is a second, separate check on the FINISHED file: it re-derives the expectations from
docs/final_dataset_dictionary.md and the run output, using plain pandas asserts (no schema library),
so a file that was edited, truncated or rebuilt with other settings is caught.

Run:   python src/validate_final_dataset.py [path-to-parquet-or-csv]
Exit:  0 when every check passes, 1 when any check fails, 2 when the file cannot be read.
Output is printed as PASS / FAIL lines; save it with
       python src/validate_final_dataset.py > docs/validation_run_output.txt
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "processed" / "final_dataset.parquet"

# --- Expectations (all taken from docs/final_dataset_dictionary.md and docs/final_dataset_run_output.txt) ---
N_STATIONS, N_TREATED, N_CONTROL = 54, 39, 15
N_HOURS = 14_136                       # 19 Feb 2025 00:00 to 30 Sep 2026 23:00 IST, 589 days
N_ROWS = N_STATIONS * N_HOURS          # 763,344
START, END = pd.Timestamp("2025-02-19 00:00"), pd.Timestamp("2026-09-30 23:00")
UTC_SHIFT = pd.Timedelta(hours=5, minutes=30)
TREATED_SUB_AREAS = {"Delhi", "Ghaziabad", "Noida", "Gurugram"}
CONTROL_SUB_AREAS = {"Patna", "Lucknow", "Kanpur"}

EXPECTED_COLUMNS = [
    "station_id", "name", "city", "sub_area", "group", "latitude", "longitude", "hour_ist", "hour_utc",
    "pm25", "pm10", "no", "no2", "nox", "so2", "co", "o3",
    "n_pm25", "n_pm10", "n_no", "n_no2", "n_nox", "n_so2", "n_co", "n_o3",
    "local_temp_c", "local_rh", "local_wind_speed", "network_pm25_share", "network_outage",
    "era5_time_utc", "u10", "v10", "wind_speed", "wind_from_deg", "t2m_c", "d2m_c", "sp_hpa", "blh_m", "tp_mm",
    "n_nh_50km_lag1", "n_nh_50km_lag2", "frp_nh_50km_lag1", "frp_nh_50km_lag2",
    "n_nh_100km_lag1", "n_nh_100km_lag2", "frp_nh_100km_lag1", "frp_nh_100km_lag2",
    "n_nh_200km_lag1", "n_nh_200km_lag2", "frp_nh_200km_lag1", "frp_nh_200km_lag2",
    "n_up_nh_100km_45deg_lag1", "frp_up_nh_100km_45deg_lag1", "fire_day_status", "fire_is_nrt",
    "grap_stage", "grap_stage_applied", "schedule_version", "grap_uncertain", "grap_inferred",
    "hours_since_stage_change", "last_change_direction",
    "hour", "weekday", "month", "season", "festival", "festival_day", "festival_window",
]

# Empty cells per column (dictionary). Every column not listed here must have no empty cells.
EXPECTED_MISSING = {
    "pm25": 98_753, "pm10": 106_271, "no": 96_826, "no2": 93_186, "nox": 358_508, "so2": 177_639,
    "co": 93_363, "o3": 93_282,
    "n_no": 54, "n_no2": 54, "n_nox": 54, "n_so2": 54, "n_co": 54, "n_o3": 54,
    "local_temp_c": 193_555, "local_rh": 185_085, "local_wind_speed": 417_957,
    "era5_time_utc": 270, "u10": 270, "v10": 270, "wind_speed": 270, "wind_from_deg": 270, "t2m_c": 270,
    "d2m_c": 270, "sp_hpa": 270, "blh_m": 270, "tp_mm": 270,
    **{f"{k}_{r}km_lag1": 18_144 for k in ("n_nh", "frp_nh") for r in (50, 100, 200)},
    **{f"{k}_{r}km_lag2": 24_624 for k in ("n_nh", "frp_nh") for r in (50, 100, 200)},
    "n_up_nh_100km_45deg_lag1": 20_736, "frp_up_nh_100km_45deg_lag1": 20_736,
    "hours_since_stage_change": 7_506,
}

# Hard limits (lower, upper). The gas and sensor limits are the cleaning limits of decision B-11.
RANGES = {
    "latitude": (25, 29), "longitude": (76, 86),
    "pm25": (0, 1000), "pm10": (0, 2000), "no": (0, 2000), "no2": (0, 1000), "nox": (0, 10),
    "so2": (0, 1000), "co": (0, 100), "o3": (0, 1000),
    "n_pm25": (0, 6), "n_pm10": (0, 6), "n_no": (0, 6), "n_no2": (0, 6), "n_nox": (0, 6), "n_so2": (0, 6),
    "n_co": (0, 6), "n_o3": (0, 6),
    "local_temp_c": (-10, 55), "local_rh": (0, 100), "local_wind_speed": (0, 40),
    "network_pm25_share": (0, 1),
    "u10": (-15, 15), "v10": (-15, 15), "wind_speed": (0, 15), "wind_from_deg": (0, 360),
    "t2m_c": (-5, 50), "d2m_c": (-5, 35), "sp_hpa": (900, 1050), "blh_m": (0, 6000), "tp_mm": (0, 100),
    "grap_stage": (0, 4), "grap_stage_applied": (0, 4), "hours_since_stage_change": (0, 14_136),
    "hour": (0, 23), "weekday": (0, 6), "month": (1, 12),
}
CATEGORIES = {
    "group": {"treated", "control"},
    "city": {"Delhi (25 km)", "Patna", "Lucknow", "Kanpur"},
    "sub_area": TREATED_SUB_AREAS | CONTROL_SUB_AREAS,
    "fire_day_status": {"observed", "zero_assumed", "outage"},
    "schedule_version": {"13-Dec-2024", "21-Nov-2025", "Sep-2026"},
    "last_change_direction": {"up", "down", "none"},
    "season": {"winter", "summer", "monsoon", "post_monsoon"},
    "festival": {"Diwali", "Dussehra", "Holi", "New Year's Eve", "none"},
}
BOOL_COLS = ["network_outage", "fire_is_nrt", "grap_uncertain", "grap_inferred", "festival_day", "festival_window"]
# Counts of True values / rows (dictionary).
EXPECTED_TRUE = {"network_outage": 50_112, "fire_is_nrt": 117_936, "grap_uncertain": 51_840,
                 "grap_inferred": 162_000, "festival_day": 6_480, "festival_window": 19_440}
EXPECTED_FIRE_STATUS_ROWS = {"outage": 18_144, "zero_assumed": 10_368}
EXPECTED_PM25_ROWS, EXPECTED_PM25_OUTSIDE_OUTAGE = 664_591, 662_378
EXPECTED_OUTAGE_HOURS = 928
EXPECTED_STAGE_CHANGES = 30
EXPECTED_STAGE_HOURS = {0: 8_067, 1: 2_995, 2: 2_103, 3: 651, 4: 320}      # hours in the window per stage
FIRE_PREFIXES = ("n_nh_", "frp_nh_", "n_up_nh_", "frp_up_nh_")


class Report:
    """Collects PASS/FAIL lines. A check that raises counts as FAIL and shows the error."""

    def __init__(self):
        self.rows = []

    def check(self, name, func):
        try:
            result = func()
            ok, detail = result if isinstance(result, tuple) else (result, "")
            ok = bool(ok)  # numpy booleans are not the Python False that n_fail tests for
        except Exception as exc:  # a broken file can fail in many ways; report, do not crash
            ok, detail = False, f"error: {type(exc).__name__}: {exc}"
        self.rows.append((ok, name, detail))

    def info(self, name, detail):
        self.rows.append((None, name, detail))

    @property
    def n_fail(self):
        return sum(1 for ok, _, _ in self.rows if ok is False)

    @property
    def n_pass(self):
        return sum(1 for ok, _, _ in self.rows if ok is True)

    def lines(self):
        out = []
        for ok, name, detail in self.rows:
            tag = "INFO" if ok is None else ("PASS" if ok else "FAIL")
            out.append(f"[{tag}] {name}" + (f" -- {detail}" if detail else ""))
        out.append(f"\n{self.n_pass} passed, {self.n_fail} failed")
        out.append("RESULT: " + ("PASS" if self.n_fail == 0 else "FAIL"))
        return out


def load(path):
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, parse_dates=["hour_ist", "hour_utc", "era5_time_utc"])


def is_fire_col(name):
    return name.startswith(FIRE_PREFIXES)


def run_checks(df):
    """Run every check on df and return the Report. A table too broken for the set-up lines still returns a FAIL."""
    r = Report()
    try:
        _run_checks(df, r)
    except Exception as exc:
        r.rows.append((False, "the checks could not all run (the table is malformed)", f"{type(exc).__name__}: {exc}"))
    return r


def _run_checks(df, r):
    c = r.check

    # ---- 1. Shape, columns, types
    c("row count is 763,344 (54 stations x 14,136 hours)", lambda: (len(df) == N_ROWS, f"got {len(df):,}"))
    c("70 columns, names and order as in the dictionary", lambda: (
        list(df.columns) == EXPECTED_COLUMNS,
        f"missing {sorted(set(EXPECTED_COLUMNS) - set(df.columns))}, extra {sorted(set(df.columns) - set(EXPECTED_COLUMNS))}"))
    c("time columns are datetimes, flags are booleans", lambda: (
        all(pd.api.types.is_datetime64_any_dtype(df[k]) for k in ("hour_ist", "hour_utc", "era5_time_utc"))
        and all(df[k].dtype == bool for k in BOOL_COLS), ""))

    # ---- 2. Keys, grid and time
    c("(station_id, hour_ist) is unique", lambda: (not df.duplicated(["station_id", "hour_ist"]).any(),
                                                     f"{df.duplicated(['station_id', 'hour_ist']).sum()} duplicates"))
    c("54 stations, each with exactly 14,136 hours", lambda: (
        df.station_id.nunique() == N_STATIONS and (df.groupby("station_id").size() == N_HOURS).all(),
        f"{df.station_id.nunique()} stations, hours per station {sorted(df.groupby('station_id').size().unique())}"))
    c("every hour has all 54 stations (no hole in the grid)", lambda: (
        df.groupby("hour_ist").size().eq(N_STATIONS).all() and df.hour_ist.nunique() == N_HOURS, ""))
    c("hour_ist runs 19 Feb 2025 00:00 to 30 Sep 2026 23:00, on the hour", lambda: (
        df.hour_ist.min() == START and df.hour_ist.max() == END and (df.hour_ist.dt.minute == 0).all()
        and (df.hour_ist.dt.second == 0).all(), f"{df.hour_ist.min()} to {df.hour_ist.max()}"))
    c("hour_utc = hour_ist - 5:30 in every row", lambda: ((df.hour_utc == df.hour_ist - UTC_SHIFT).all(), ""))
    c("hour, weekday, month, season agree with hour_ist", lambda: (
        (df.hour == df.hour_ist.dt.hour).all() and (df.weekday == df.hour_ist.dt.weekday).all()
        and (df.month == df.hour_ist.dt.month).all()
        and (df.season == df.month.map({12: "winter", 1: "winter", 2: "winter", 3: "summer", 4: "summer", 5: "summer",
                                        6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
                                        10: "post_monsoon", 11: "post_monsoon"})).all(), ""))

    # ---- 3. Stations and groups
    def stations_ok():
        st = df.drop_duplicates("station_id")
        n = st.group.value_counts().to_dict()
        # one set of attributes per station
        consistent = (df.groupby("station_id")[["name", "city", "sub_area", "group", "latitude", "longitude"]]
                      .nunique().max().max() == 1)
        return n == {"treated": N_TREATED, "control": N_CONTROL} and consistent, f"{n}, one set of attributes per station: {consistent}"
    c("39 treated and 15 control stations, attributes constant per station", stations_ok)
    c("treated = Delhi/Ghaziabad/Noida/Gurugram, control = Patna/Lucknow/Kanpur", lambda: (
        set(df.loc[df.group == "treated", "sub_area"]) <= TREATED_SUB_AREAS
        and set(df.loc[df.group == "control", "sub_area"]) <= CONTROL_SUB_AREAS, ""))
    for col, allowed in CATEGORIES.items():
        c(f"{col}: only allowed values", lambda col=col, allowed=allowed: (
            set(df[col].unique()) <= allowed, f"unexpected {sorted(set(df[col].unique()) - allowed)}"))

    # ---- 4. Missing values (counts from the dictionary) and ranges
    def missing_ok():
        got = df.isna().sum()
        bad = {k: (int(got[k]), EXPECTED_MISSING.get(k, 0)) for k in df.columns if int(got[k]) != EXPECTED_MISSING.get(k, 0)}
        return not bad, f"(got, expected) for differing columns: {bad}" if bad else ""
    c("empty cells per column match the dictionary; every other column has none", missing_ok)

    def ranges_ok():
        bad = {}
        for col, (lo, hi) in RANGES.items():
            s = df[col].dropna()
            if len(s) and (s.min() < lo or s.max() > hi):
                bad[col] = (float(s.min()), float(s.max()), (lo, hi))
        return not bad, f"outside limits (min, max, limits): {bad}" if bad else ""
    c(f"values of {len(RANGES)} numeric columns stay inside their limits", ranges_ok)
    c("no negative fire counts or fire radiative power", lambda: (
        all((df[k].dropna() >= 0).all() for k in df.columns if is_fire_col(k) and df[k].dtype != object), ""))

    # ---- 5. PM2.5, readings and the outage flag
    c("pm25 present in 664,591 rows", lambda: (df.pm25.notna().sum() == EXPECTED_PM25_ROWS, f"got {df.pm25.notna().sum():,}"))
    c("every pm25 value has at least one reading behind it (n_pm25 > 0)", lambda: ((df.loc[df.pm25.notna(), "n_pm25"] > 0).all(), ""))
    c("n_pm25 = 0 only where pm25 is empty", lambda: (df.loc[df.n_pm25 == 0, "pm25"].isna().all(), ""))
    cleaned = int((df.pm25.isna() & (df.n_pm25 > 0)).sum())
    r.info("rows with readings (n_pm25 > 0) but pm25 emptied by the quality rules (above 1,000 or flat runs)",
           f"{cleaned:,} rows; n_pm25 counts raw readings, so it is not 0 there")
    share = df.groupby("hour_ist").pm25.apply(lambda s: s.notna().mean())
    c("network_pm25_share equals the share of stations with PM2.5 in that hour (stored with 3 decimals)", lambda: (
        np.allclose(df.hour_ist.map(share).to_numpy(), df.network_pm25_share.to_numpy(), atol=6e-4), ""))
    c("network_outage is exactly 'share < 0.5'", lambda: ((df.network_outage == (df.network_pm25_share < 0.5)).all(), ""))
    per_hour = df.groupby("hour_ist").network_outage.agg(["min", "max"])
    c("network_outage is the same for all stations in an hour", lambda: ((per_hour["min"] == per_hour["max"]).all(), ""))
    c("928 outage hours (50,112 rows)", lambda: (
        per_hour["max"].sum() == EXPECTED_OUTAGE_HOURS and df.network_outage.sum() == EXPECTED_TRUE["network_outage"],
        f"{int(per_hour['max'].sum())} hours, {int(df.network_outage.sum()):,} rows"))
    c("662,378 PM2.5 rows remain outside outage hours", lambda: (
        (df.pm25.notna() & ~df.network_outage).sum() == EXPECTED_PM25_OUTSIDE_OUTAGE,
        f"got {(df.pm25.notna() & ~df.network_outage).sum():,}"))
    jan = df[(df.hour_ist >= "2026-01-10 18:00") & (df.hour_ist <= "2026-01-20 18:00")]
    c("10 Jan 18:00 to 20 Jan 18:00 IST 2026 (241 hours): PM2.5 empty at every station and flagged as outage", lambda: (
        bool(jan.pm25.isna().all()) and bool(jan.network_outage.all()) and jan.hour_ist.nunique() == 241,
        f"{jan.pm25.notna().sum()} PM2.5 values, {jan.hour_ist.nunique()} hours in the window"))

    # ---- 6. Weather
    c("weather is empty only in the first 5 hours of 19 Feb 2025", lambda: (
        df.loc[df.u10.isna(), "hour_ist"].max() < pd.Timestamp("2025-02-19 05:00"), ""))
    c("wind_speed = sqrt(u10^2 + v10^2) (within the rounding of the stored u10 and v10)", lambda: (
        np.allclose(df.wind_speed.dropna(), np.hypot(df.u10, df.v10).dropna(), atol=2e-3), "u10 and v10 are stored rounded"))
    c("dewpoint never above air temperature (small tolerance)", lambda: ((df.d2m_c.dropna() <= df.t2m_c.dropna() + 0.5).all(), ""))
    c("ERA5 stamp is hour_utc rounded up to the hour", lambda: (
        (df.era5_time_utc.dropna() == df.loc[df.era5_time_utc.notna(), "hour_utc"].dt.ceil("h")).all(), ""))

    # ---- 7. Fire: only previous-day columns, constant within an IST date
    fire_cols = [k for k in df.columns if is_fire_col(k)]
    c("no lag0 or same-day fire column exists (every fire column ends in lag1 or lag2)", lambda: (
        all(k.endswith(("_lag1", "_lag2")) for k in fire_cols) and not any("lag0" in k for k in df.columns),
        f"fire columns: {fire_cols}"))
    ist_date = df.hour_ist.dt.normalize()
    def fire_const():
        g = df.groupby(["station_id", ist_date])
        bad = [k for k in fire_cols if (g[k].nunique(dropna=False) > 1).any()]
        return not bad, f"changes within a day: {bad}" if bad else ""
    c("fire values are constant within each station and IST date (previous day applied to all 24 hours)", fire_const)
    c("fire_day_status counts: outage 18,144 rows, zero_assumed 10,368 rows", lambda: (
        df.fire_day_status.value_counts().reindex(["outage", "zero_assumed"]).to_dict() == EXPECTED_FIRE_STATUS_ROWS,
        str(df.fire_day_status.value_counts().to_dict())))
    c("lag1 is empty on outage days and only then (apart from the first two dates)", lambda: (
        df.loc[df.fire_day_status == "outage", "n_nh_100km_lag1"].isna().all()
        and df.loc[(df.fire_day_status != "outage") & (df.hour_ist >= "2025-02-21"), "n_nh_100km_lag1"].notna().all(), ""))
    c("zero_assumed days have lag1 = 0", lambda: (
        (df.loc[df.fire_day_status == "zero_assumed", "n_nh_100km_lag1"] == 0).all(), ""))
    def radius_order():
        both = df[["n_nh_50km_lag1", "n_nh_100km_lag1", "n_nh_200km_lag1", "n_up_nh_100km_45deg_lag1"]].dropna()
        return ((both.n_nh_50km_lag1 <= both.n_nh_100km_lag1).all() and (both.n_nh_100km_lag1 <= both.n_nh_200km_lag1).all()
                and (both.n_up_nh_100km_45deg_lag1 <= both.n_nh_100km_lag1).all()), ""
    c("counts grow with radius (50 <= 100 <= 200 km) and upwind <= all-direction 100 km", radius_order)
    def lag2_ge_lag1():
        both = df[["n_nh_100km_lag1", "n_nh_100km_lag2"]].dropna()
        return (both.n_nh_100km_lag2 >= both.n_nh_100km_lag1).all(), ""
    c("the 2-day sum (lag2) is never below the 1-day value (lag1)", lag2_ge_lag1)
    c("fire_is_nrt is true only from 2 Jul 2026 (117,936 rows)", lambda: (
        df.fire_is_nrt.sum() == EXPECTED_TRUE["fire_is_nrt"] and df.loc[df.fire_is_nrt, "hour_ist"].min() >= pd.Timestamp("2026-07-02")
        and not df.loc[df.hour_ist < "2026-07-02", "fire_is_nrt"].any(), f"{int(df.fire_is_nrt.sum()):,}"))

    # ---- 8. Policy (GRAP)
    stage = df.groupby("hour_ist").grap_stage.agg(["min", "max"])
    c("grap_stage is the same at every station in an hour", lambda: ((stage["min"] == stage["max"]).all(), ""))
    c("grap_stage_applied = grap_stage for treated, 0 for control", lambda: (
        (df.loc[df.group == "treated", "grap_stage_applied"] == df.loc[df.group == "treated", "grap_stage"]).all()
        and (df.loc[df.group == "control", "grap_stage_applied"] == 0).all(), ""))
    hourly = df.drop_duplicates("hour_ist").sort_values("hour_ist")
    c("hours per stage 0..4 are 8,067 / 2,995 / 2,103 / 651 / 320", lambda: (
        hourly.grap_stage.value_counts().sort_index().to_dict() == EXPECTED_STAGE_HOURS,
        str(hourly.grap_stage.value_counts().sort_index().to_dict())))
    c("30 stage changes in the window", lambda: (
        int((hourly.grap_stage.diff().fillna(0) != 0).sum()) == EXPECTED_STAGE_CHANGES,
        f"{int((hourly.grap_stage.diff().fillna(0) != 0).sum())} changes"))
    c("hours_since_stage_change is 0 at each change and empty only before the first one", lambda: (
        (hourly.loc[hourly.grap_stage.diff().fillna(0) != 0, "hours_since_stage_change"] == 0).all()
        and hourly.hours_since_stage_change.isna().sum() == 139
        and hourly.hours_since_stage_change.notna().iloc[139:].all(), ""))
    c("flag counts: grap_uncertain 51,840 rows, grap_inferred 162,000 rows", lambda: (
        df.grap_uncertain.sum() == EXPECTED_TRUE["grap_uncertain"] and df.grap_inferred.sum() == EXPECTED_TRUE["grap_inferred"], ""))
    c("festival_day is inside festival_window; counts 6,480 and 19,440 rows", lambda: (
        not (df.festival_day & ~df.festival_window).any() and df.festival_day.sum() == EXPECTED_TRUE["festival_day"]
        and df.festival_window.sum() == EXPECTED_TRUE["festival_window"] and ((df.festival != "none") == df.festival_window).all(), ""))

    # ---- 9. Information that the report quotes (not pass/fail rules, but they are asserted below)
    iv = hourly.grap_stage >= 3
    ov = int((iv & hourly.network_outage).sum())
    r.info("Stage III/IV hours in the window", f"{int(iv.sum())} hours")
    r.info("Stage III/IV hours that fall inside a network outage", f"{ov} hours")
    in_jan = int((iv & (hourly.hour_ist >= "2026-01-10 18:00") & (hourly.hour_ist <= "2026-01-20 18:00")).sum())
    r.info("  of which in the January 2026 outage (10 Jan 18:00 to 20 Jan 18:00 IST) / in shorter outages", f"{in_jan} / {ov - in_jan}")
    c("Stage III/IV hours: 971 in total, 112 of them inside a network outage (the number quoted in the report)", lambda: (
        int(iv.sum()) == 971 and ov == 112, f"{int(iv.sum())} total, {ov} in outage"))


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    print(f"Validating {path}")
    try:
        df = load(path)
    except Exception as exc:
        print(f"[FAIL] cannot read the file: {type(exc).__name__}: {exc}")
        return 2
    report = run_checks(df)
    print("\n".join(report.lines()))
    return 0 if report.n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
