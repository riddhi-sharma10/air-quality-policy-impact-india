"""Tests for src/build_final_dataset.py (phase B1 so far: spine and pollution join).
Run:  python tests/test_final_dataset.py   (or pytest tests/)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build_final_dataset import (ERA5_TABLE, FESTIVALS, GRAP_HOURLY, ID_COLS, IST_OFFSET, KEY, NONPM_COLS,  # noqa: E402
                                 PM_COLS, POLLUTION, POLLUTION_COLS, SEASONS, STATIONS_FINAL, WEATHER_INSTANT,
                                 add_calendar, align_nonpm, build_spine, join_policy, join_pollution, join_weather,
                                 load_pollution, load_stations, stage_events)
from build_final_dataset import (FIRE_COLS, FIRE_LAG_COLS, FIRE_RADII, UPWIND_COLS, UPWIND_RADIUS_KM, UPWIND_THETA_DEG,  # noqa: E402
                                 QC_LIMITS, date_status, fire_lags_wide, join_fire, outside_limits, qc_gases_sensors, upwind_lag1)


def stations(ids=(1, 2)):
    return pd.DataFrame({"station_id": list(ids), "name": [f"s{i}" for i in ids], "city": "Delhi", "sub_area": "Delhi",
                         "group": "treated", "latitude": 28.6, "longitude": 77.2})


def pollution_rows(ids, hours, pm25=10.0):
    """A pollution frame in the layout of pollution_hourly.csv for the given stations and IST hours."""
    df = pd.MultiIndex.from_product([list(ids), pd.DatetimeIndex(hours)], names=KEY).to_frame(index=False)
    df["hour_utc"] = df["hour_ist"] - IST_OFFSET
    for c in POLLUTION_COLS:
        df[c] = 1.0
    df["pm25"] = pm25
    return df


def test_spine_size_and_hours():
    sp = build_spine(stations((1, 2, 3)), "2025-02-19", "2025-02-21")
    assert len(sp) == 3 * 3 * 24
    assert sp["hour_ist"].min() == pd.Timestamp("2025-02-19 00:00") and sp["hour_ist"].max() == pd.Timestamp("2025-02-21 23:00")
    assert not sp.duplicated(KEY).any()
    assert list(sp.columns) == ID_COLS + ["hour_ist", "hour_utc"]


def test_spine_hour_utc_is_half_past():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19")
    assert (sp["hour_utc"] == sp["hour_ist"] - pd.Timedelta(hours=5, minutes=30)).all()
    assert sp.loc[0, "hour_utc"] == pd.Timestamp("2025-02-18 18:30")


def test_study_window_spine_has_14136_hours_per_station():
    from era5_window import STUDY_END, STUDY_START
    sp = build_spine(stations((1,)), STUDY_START, STUDY_END)
    assert len(sp) == 589 * 24 == 14136


def test_join_keeps_row_count_and_values():
    sp = build_spine(stations((1, 2)), "2025-02-19", "2025-02-19")
    out = join_pollution(sp, pollution_rows((1, 2), sp["hour_ist"].unique(), pm25=42.0))
    assert len(out) == len(sp) and (out["pm25"] == 42.0).all()
    assert set(POLLUTION_COLS) <= set(out.columns) and "hour_utc_pollution" not in out.columns


def test_join_drops_stations_not_in_the_spine():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19")
    out = join_pollution(sp, pollution_rows((1, 8118), sp["hour_ist"].unique()))
    assert set(out["station_id"]) == {1} and len(out) == 24


def test_missing_pollution_hour_gives_empty_cells_not_a_lost_row():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19")
    pol = pollution_rows((1,), sp["hour_ist"].unique()).drop(index=5)  # one hour absent from the pollution table
    out = join_pollution(sp, pol)
    assert len(out) == 24 and out["pm25"].isna().sum() == 1


def test_join_refuses_duplicate_pollution_rows():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19")
    pol = pollution_rows((1,), sp["hour_ist"].unique())
    with pytest.raises(pd.errors.MergeError):
        join_pollution(sp, pd.concat([pol, pol.iloc[[0]]], ignore_index=True))


def test_join_refuses_inconsistent_hour_utc():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19")
    pol = pollution_rows((1,), sp["hour_ist"].unique())
    pol["hour_utc"] = pol["hour_utc"] + pd.Timedelta(hours=1)
    with pytest.raises(SystemExit):
        join_pollution(sp, pol)


def test_load_stations_renames_id_and_rejects_duplicates(tmp_path):
    st = stations((1, 2)).rename(columns={"station_id": "id"})
    p = tmp_path / "s.csv"
    st.to_csv(p, index=False)
    got = load_stations(p)
    assert list(got.columns) == ID_COLS and got["station_id"].tolist() == [1, 2]
    pd.concat([st, st.iloc[[0]]]).to_csv(p, index=False)
    with pytest.raises(SystemExit):
        load_stations(p)


@pytest.mark.skipif(not (POLLUTION.exists() and STATIONS_FINAL.exists()), reason="needs the processed pollution and station tables")
def test_real_tables_join_without_losing_pm25():
    st = load_stations(STATIONS_FINAL)
    pol = load_pollution(POLLUTION)
    out = join_pollution(build_spine(st, "2025-02-19", "2026-09-30"), pol)
    src = pol[pol["station_id"].isin(st["station_id"])]
    assert len(out) == 54 * 14136 == 763344
    assert int(out["pm25"].notna().sum()) == int(src["pm25"].notna().sum()) == 664591
    # three station-hours traced by hand to the source table
    for r in out.sample(3, random_state=5).itertuples():
        s = src[(src["station_id"] == r.station_id) & (src["hour_ist"] == r.hour_ist)].iloc[0]
        assert (np.isnan(r.pm25) and np.isnan(s["pm25"])) or r.pm25 == s["pm25"]
        assert r.hour_utc == s["hour_utc"]



# ---------------------------------------------------------------------------------------------- B2
def table_with_gas(hours=4, ids=(1, 2)):
    """A joined frame whose gas columns count up by hour (10, 11, 12 ...) and whose PM columns are fixed."""
    sp = build_spine(stations(ids), "2025-02-19", "2025-02-19").query("hour_ist < '2025-02-19 %02d:00'" % hours)
    t = sp.reset_index(drop=True)
    for c in NONPM_COLS:
        t[c] = 10.0 + t["hour_ist"].dt.hour
    for c in PM_COLS:
        t[c] = 5.0
    return t


def test_nonpm_columns_come_from_the_previous_hour():
    t = table_with_gas()
    out = align_nonpm(t, 1)
    for sid in (1, 2):
        g = out[out["station_id"] == sid]
        assert g["no2"].isna().tolist() == [True, False, False, False]
        assert g["no2"].tolist()[1:] == [10.0, 11.0, 12.0]          # hour h holds the value of hour h - 1
    assert (out["pm25"] == 5.0).all() and (out["network_outage"] == 5.0).all()   # PM and flags stay in their row
    assert list(out.index) == list(t.index)


def test_nonpm_lag_zero_changes_nothing_and_gaps_are_refused():
    t = table_with_gas()
    assert align_nonpm(t, 0).equals(t)
    with pytest.raises(SystemExit):
        align_nonpm(t.drop(index=1), 1)    # a missing hour: a row shift would no longer be an hour shift


def era5_frame(sid=1, start="2025-02-18 20:00", periods=10):
    t = pd.date_range(start, periods=periods, freq="h")
    e = pd.DataFrame({"station_id": sid, "time_utc": t})
    for i, c in enumerate(WEATHER_INSTANT):
        e[c] = (i + 1) * 100.0 + np.arange(periods)
    e["tp_mm"] = np.arange(periods) * 2.0
    return e


def test_weather_is_taken_at_the_stamp_in_the_middle_of_the_hour():
    sp = build_spine(stations((1,)), "2025-02-19", "2025-02-19").iloc[:3]      # hour_utc 18:30, 19:30, 20:30 (18 Feb 18:30 ...)
    e = era5_frame()                                                           # stamps from 18 Feb 20:00
    out = join_weather(sp, e, 0)
    # hour_utc 18:30 -> ceil 19:00, not in the table (starts 20:00); 19:30 -> 20:00 is index 0; 20:30 -> 21:00 index 1
    assert out["u10"].isna().tolist() == [True, False, False]
    assert out["u10"].tolist()[1:] == [100.0, 101.0]
    assert out.loc[1, "era5_time_utc"] == pd.Timestamp("2025-02-18 20:00")
    assert pd.isna(out.loc[out["u10"].isna(), "era5_time_utc"]).all()


def test_rain_is_half_this_stamp_and_half_the_next():
    sp = pd.DataFrame({"station_id": [1], "hour_utc": [pd.Timestamp("2025-02-18 22:30")]})
    out = join_weather(sp, era5_frame(), 0)       # stamp 23:00 = index 3 -> tp 6.0, next index 4 -> tp 8.0
    assert out.loc[0, "tp_mm"] == 7.0
    assert out.loc[0, "u10"] == 100.0 + 3


def test_weather_offset_moves_the_stamp_and_rain_is_empty_at_the_end():
    sp = pd.DataFrame({"station_id": [1], "hour_utc": [pd.Timestamp("2025-02-18 22:30")]})
    assert join_weather(sp, era5_frame(), 1).loc[0, "u10"] == 100.0 + 4
    last = pd.DataFrame({"station_id": [1], "hour_utc": [pd.Timestamp("2025-02-19 04:30")]})   # stamp 05:00 = last index 9
    out = join_weather(last, era5_frame(), 0)
    assert out.loc[0, "u10"] == 100.0 + 9 and np.isnan(out.loc[0, "tp_mm"])


def test_weather_join_refuses_duplicate_stamps():
    sp = pd.DataFrame({"station_id": [1], "hour_utc": [pd.Timestamp("2025-02-18 22:30")]})
    e = era5_frame()
    with pytest.raises(pd.errors.MergeError):
        join_weather(sp, pd.concat([e, e.iloc[[3]]], ignore_index=True), 0)


def test_stage_events_hours_since_change_and_direction():
    g = pd.DataFrame({"grap_stage": [2, 2, 1, 1, 1, 2, 2]})
    out = stage_events(g)
    assert out["hours_since_stage_change"].tolist()[2:] == [0.0, 1.0, 2.0, 0.0, 1.0]
    assert out["hours_since_stage_change"].iloc[:2].isna().all()
    assert out["last_change_direction"].iloc[2:].tolist() == ["down", "down", "down", "up", "up"]
    assert out["last_change_direction"].iloc[:2].tolist() == ["none", "none"]


def test_policy_applies_the_stage_to_treated_stations_only():
    st = stations((1, 2))
    st["group"] = ["treated", "control"]
    sp = build_spine(st, "2025-02-19", "2025-02-19").iloc[[0, 24]]    # one hour per station, same hour
    grap = pd.DataFrame({"hour_ist": pd.date_range("2025-02-19", periods=24, freq="h"), "grap_stage": 3,
                         "schedule_version": "v", "grap_uncertain": False, "grap_inferred": False,
                         "hours_since_stage_change": 5.0, "last_change_direction": "up"})
    out = join_policy(sp, grap)
    assert out["grap_stage"].tolist() == [3, 3] and out["grap_stage_applied"].tolist() == [3, 0]
    assert len(out) == 2


def test_calendar_columns_and_festival_windows():
    t = pd.DataFrame({"hour_ist": pd.to_datetime(["2025-10-18 23:00", "2025-10-19 00:00", "2025-10-20 12:00", "2025-10-21 23:00",
                                                  "2025-10-22 00:00", "2026-03-03 10:00", "2025-12-31 23:00", "2026-01-01 00:00"])})
    out = add_calendar(t)
    assert out["festival_day"].tolist() == [False, False, True, False, False, False, True, False]
    assert out["festival_window"].tolist() == [False, True, True, True, False, True, True, True]
    assert out["festival"].tolist() == ["none", "Diwali", "Diwali", "Diwali", "none", "Holi", "New Year's Eve", "New Year's Eve"]
    assert out.loc[2, "weekday"] == 0 and out.loc[2, "hour"] == 12 and out.loc[2, "month"] == 10   # 20 Oct 2025 is a Monday
    assert out["season"].tolist()[:1] == ["post_monsoon"] and out["season"].iloc[5] == "summer" and out["season"].iloc[7] == "winter"


def test_festival_dates_are_inside_the_window_and_seasons_cover_all_months():
    assert all("2025-02-19" <= d <= "2026-09-30" for _, d in FESTIVALS)
    assert sorted(SEASONS) == list(range(1, 13))


@pytest.mark.skipif(not all(f.exists() for f in (POLLUTION, STATIONS_FINAL, ERA5_TABLE, GRAP_HOURLY)), reason="needs the processed tables")
def test_real_run_passes_all_checks_and_has_the_expected_shape(tmp_path):
    import subprocess
    out = tmp_path / "final.csv"
    r = subprocess.run([sys.executable, str(ROOT / "src" / "build_final_dataset.py"), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]
    assert "0 failed" in r.stdout
    got = pd.read_csv(out, nrows=5)
    assert got.shape[1] == 70 and "tp_mm" in got.columns and "grap_stage_applied" in got.columns and "n_nh_100km_lag1" in got.columns



# ---------------------------------------------------------------------------------------------- B3
DAYS = pd.date_range("2025-07-01", periods=8, freq="D")
N_NH = [3.0, 4.0, np.nan, 5.0, np.nan, 2.0, 1.0, 6.0]           # day 3 = cloud (zero assumed), day 5 = outage
STATUS = pd.Series(["observed", "observed", "zero_assumed", "observed", "outage", "observed", "observed", "observed"], index=DAYS)


def daily_fire(sid=1):
    rows = []
    for r in FIRE_RADII:
        for d, n in zip(DAYS, N_NH):
            rows.append({"station_id": sid, "radius_km": r, "ist_date": d, "n_nh": n * r / 50 if n == n else n, "frp_nh": n * 10 if n == n else n})
    return pd.DataFrame(rows)


def test_date_status_from_detections():
    det = pd.DataFrame({"ist_date": pd.to_datetime(["2025-07-01", "2025-07-01", "2025-07-03", "2025-07-04"])})
    s = date_status(det)                                    # 2 Jul is empty, a monsoon day between quiet days
    assert s["2025-07-02"] == "zero_assumed" and (s.drop(pd.Timestamp("2025-07-02")) == "observed").all()


def test_fire_lags_apply_the_cloud_rule_and_recompute_lag2():
    w = fire_lags_wide(daily_fire(), STATUS).set_index("ist_date")
    assert list(w.columns) == ["station_id"] + FIRE_LAG_COLS
    n = "n_nh_50km_lag1"
    # lag1 on date d is the value of d - 1; the cloud day (3 Jul) counts as 0, the outage day (5 Jul) stays empty
    assert w.loc["2025-07-04", n] == 0.0 and np.isnan(w.loc["2025-07-06", n])
    assert w.loc["2025-07-03", n] == 4.0 and w.loc["2025-07-05", n] == 5.0
    l2 = "n_nh_50km_lag2"
    assert w.loc["2025-07-05", l2] == 5.0 + 0.0                                    # d-1 = 4 Jul (5), d-2 = 3 Jul (cloud, 0)
    assert np.isnan(w.loc["2025-07-06", l2]) and np.isnan(w.loc["2025-07-07", l2])  # d-1 or d-2 is the outage day
    assert w.loc["2025-07-08", l2] == 1.0 + 2.0
    assert w.loc["2025-07-08", "n_nh_200km_lag1"] == 4.0                          # 7 Jul has 1 at 50 km, 4 at 200 km


def test_upwind_is_moved_forward_one_day_and_uses_only_the_main_setting():
    rows = []
    for r in FIRE_RADII:
        for th in (30, UPWIND_THETA_DEG, 60):
            for d, n in zip(DAYS, N_NH):
                rows.append({"station_id": 1, "ist_date": d, "radius_km": r, "theta_deg": th,
                             "n_up_nh": n + (100 if (r, th) != (UPWIND_RADIUS_KM, UPWIND_THETA_DEG) else 0) if n == n else n, "frp_up_nh": n * 2 if n == n else n})
    u = upwind_lag1(pd.DataFrame(rows), STATUS)
    assert len(u) == len(DAYS) and list(u.columns) == ["station_id", UPWIND_COLS[0], UPWIND_COLS[1], "fire_date"]
    u = u.set_index("fire_date")
    assert u.loc["2025-07-02", UPWIND_COLS[0]] == 3.0           # the value of 1 Jul, not of 2 Jul
    assert u.loc["2025-07-04", UPWIND_COLS[0]] == 0.0 and np.isnan(u.loc["2025-07-06", UPWIND_COLS[0]])
    assert u.loc["2025-07-04", UPWIND_COLS[1]] == 0.0


def test_join_fire_gives_every_hour_of_a_date_the_previous_days_values():
    sp = build_spine(stations((1,)), "2025-07-03", "2025-07-07")
    out = join_fire(sp, fire_lags_wide(daily_fire(), STATUS),
                    upwind_lag1(pd.DataFrame([{"station_id": 1, "ist_date": d, "radius_km": UPWIND_RADIUS_KM, "theta_deg": UPWIND_THETA_DEG,
                                               "n_up_nh": n, "frp_up_nh": n} for d, n in zip(DAYS, N_NH)]), STATUS),
                    STATUS, pd.Timestamp("2025-07-06"))
    assert len(out) == len(sp) and set(FIRE_COLS) <= set(out.columns)
    by_day = out.groupby(out["hour_ist"].dt.normalize())
    assert (by_day["n_nh_50km_lag1"].nunique(dropna=False) == 1).all()           # constant within a date
    status = by_day["fire_day_status"].first()
    assert status["2025-07-04"] == "zero_assumed" and status["2025-07-06"] == "outage" and status["2025-07-07"] == "observed"
    nrt = by_day["fire_is_nrt"].first()
    assert not nrt["2025-07-06"]                                                  # d - 1 = 5 Jul, before the 6 Jul start
    assert nrt["2025-07-07"]                                                      # d - 1 = 6 Jul


def test_fire_column_names_pass_the_hourly_guard():
    from add_fire_lags import assert_hourly_safe
    assert_hourly_safe(FIRE_LAG_COLS + UPWIND_COLS)
    assert len(FIRE_LAG_COLS) == 12 and len(UPWIND_COLS) == 2 and len(FIRE_COLS) == 16



# ---------------------------------------------------------------------------------------------- B-11
def test_quality_limits_remove_only_impossible_values():
    t = pd.DataFrame({c: [1.0] * 5 for c in QC_LIMITS})                          # every limited column, all inside its limits
    t = t.assign(so2=[10.0, 1000.0, 1000.1, 2.07e16, np.nan], local_rh=[-5.0, 0.0, 100.0, 100.1, 183.0],
                 local_temp_c=[-61.5, -10.0, 28.0, 55.0, 55.1], pm25=[5000.0] * 5, n_so2=[4] * 5)
    out, removed = qc_gases_sensors(t)
    assert out["so2"].isna().tolist() == [False, False, True, True, True]          # the limit itself is kept
    assert out["local_rh"].isna().tolist() == [True, False, False, True, True]
    assert out["local_temp_c"].isna().tolist() == [True, False, False, False, True]
    assert removed["so2"] == 2 and removed["local_rh"] == 3 and removed["local_temp_c"] == 2
    assert out["pm25"].tolist() == [5000.0] * 5 and out["n_so2"].tolist() == [4] * 5      # PM and counts untouched
    assert t["so2"].iloc[3] == 2.07e16                                                     # the input is not changed


def test_outside_limits_ignores_empty_cells():
    assert outside_limits([np.nan, 5.0, 150.0, -1.0], 0, 100).tolist() == [False, False, True, True]


def test_every_gas_and_sensor_column_has_a_limit_and_the_pm_columns_do_not():
    assert set(QC_LIMITS) == set(NONPM_COLS) - {f"n_{g}" for g in ("no", "no2", "nox", "so2", "co", "o3")}
    assert "pm25" not in QC_LIMITS and "pm10" not in QC_LIMITS


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
