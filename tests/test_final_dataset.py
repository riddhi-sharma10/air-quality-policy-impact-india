"""Tests for src/build_final_dataset.py (phase B1 so far: spine and pollution join).
Run:  python tests/test_final_dataset.py   (or pytest tests/)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build_final_dataset import (ID_COLS, IST_OFFSET, KEY, POLLUTION, POLLUTION_COLS, STATIONS_FINAL,  # noqa: E402
                                 build_spine, join_pollution, load_pollution, load_stations)


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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
