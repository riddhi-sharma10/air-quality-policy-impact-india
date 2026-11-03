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
    assert out["last_change_direction"].iloc[:2].isna().all()


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
    assert out["festival"].tolist() == ["", "Diwali", "Diwali", "Diwali", "", "Holi", "New Year's Eve", "New Year's Eve"]
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
    assert got.shape[1] == 54 and "tp_mm" in got.columns and "grap_stage_applied" in got.columns


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
