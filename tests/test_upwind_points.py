"""Tests for the wind part of src/build_upwind_features.py (hourly wind to daily mean vector, two sources).
Run:  python tests/test_upwind_points.py   (or pytest tests/)"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build_upwind_features import grid_hourly, load_wind_table, station_wind  # noqa: E402

GRID_FILES = [ROOT / "data" / "raw" / "era5" / f"era5_window_2025_11-12_{k}.nc" for k in ("instant", "accum")]
TABLE = ROOT / "data" / "processed" / "era5_station_hourly.csv"
STATIONS = ROOT / "data" / "processed" / "stations_final.csv"
FIRMS = [ROOT / "data" / "raw" / "firms" / n for n in ("fire_archive_SV-C2_829739.csv", "fire_nrt_SV-C2_829739.csv")]


def hours(start, end, u=1.0, v=0.0):
    """Hourly UTC frame in the layout of load_wind_table / grid_hourly."""
    t = pd.date_range(start, end, freq="h")
    return pd.DataFrame({"time_utc": t, "u": np.full(len(t), u), "v": np.full(len(t), v)})


def test_full_ist_day_gives_mean_vector():
    # IST day 20 Feb holds the 24 UTC stamps 19 Feb 19:00 .. 20 Feb 18:00 (= 00:30 .. 23:30 IST)
    w = hours("2025-02-19 19:00", "2025-02-20 18:00", u=3.0, v=-4.0)
    d = station_wind(w, 1)
    row = d.loc["2025-02-20"]
    assert np.isclose(row.u_mean, 3.0) and np.isclose(row.v_mean, -4.0)
    assert np.isclose(row.wind_speed_vec, 5.0) and np.isclose(row.wind_steadiness, 1.0)


def test_incomplete_day_is_nan():
    w = hours("2025-02-19 19:00", "2025-02-20 18:00").drop(index=5)  # one hour missing
    assert np.isnan(station_wind(w, 1).loc["2025-02-20", "u_mean"])


def test_vectors_are_averaged_not_angles():
    # half the day wind from the east (u=-5, blows west), half from the west (u=+5): vector mean is ~0
    w = hours("2025-02-19 19:00", "2025-02-20 18:00")
    w["u"] = np.where(np.arange(len(w)) < 12, -5.0, 5.0)
    row = station_wind(w, 1).loc["2025-02-20"]
    assert abs(row.u_mean) < 1e-9 and row.wind_speed_vec < 1e-9
    assert row.wind_steadiness < 1e-9  # direction kept changing


def test_window_start_matches_the_real_table():
    # the table starts at 2025-02-19 00:00 UTC = 05:30 IST, so IST 19 Feb is incomplete and 20 Feb is the first full day
    w = hours("2025-02-19 00:00", "2025-02-22 23:00")
    d = station_wind(w, 1)
    assert np.isnan(d.loc["2025-02-19", "u_mean"])
    assert d.loc["2025-02-20", "u_mean"] == 1.0


def test_two_day_mean_needs_48_hours_and_averages_both_days():
    w = hours("2025-02-19 19:00", "2025-02-22 18:00")          # IST days 20, 21, 22 complete
    w["u"] = np.where(pd.DatetimeIndex(w["time_utc"]) + pd.Timedelta(hours=5, minutes=30) < pd.Timestamp("2025-02-21"), 2.0, 6.0)
    d = station_wind(w, 2)
    assert np.isnan(d.loc["2025-02-20", "u_mean"])               # only one day of wind so far
    assert np.isclose(d.loc["2025-02-21", "u_mean"], 4.0)        # (2 + 6) / 2
    assert np.isclose(d.loc["2025-02-22", "u_mean"], 6.0)        # days 21 and 22 are both 6


def test_wind_from_direction_convention():
    # wind blowing towards the south (v < 0) comes from the north = 0 degrees
    row = station_wind(hours("2025-02-19 19:00", "2025-02-20 18:00", u=0.0, v=-3.0), 1).loc["2025-02-20"]
    assert np.isclose(row.wind_from_deg, 0.0) or np.isclose(row.wind_from_deg, 360.0)


def test_load_wind_table_layout_and_checks(tmp_path):
    t = pd.DataFrame({"station_id": [1, 1, 2], "time_utc": ["2025-02-19 01:00:00", "2025-02-19 00:00:00", "2025-02-19 00:00:00"],
                      "u10": [1.0, 2.0, 3.0], "v10": [4.0, 5.0, 6.0], "extra": [0, 0, 0]})
    p = tmp_path / "w.csv"
    t.to_csv(p, index=False)
    got = load_wind_table(p)
    assert set(got) == {1, 2} and list(got[1].columns) == ["time_utc", "u", "v"]
    assert got[1]["time_utc"].is_monotonic_increasing and got[1]["u"].tolist() == [2.0, 1.0]
    t.loc[2, ["station_id", "time_utc"]] = [1, "2025-02-19 00:00:00"]  # duplicate station-hour
    t.to_csv(p, index=False)
    with pytest.raises(SystemExit):
        load_wind_table(p)
    with pytest.raises(SystemExit):
        load_wind_table(tmp_path / "missing.csv")


def test_grid_hourly_takes_the_nearest_cell():
    t = pd.date_range("2025-01-01", periods=3, freq="h")
    ds = xr.Dataset({"u10": (("valid_time", "latitude", "longitude"), np.arange(12, dtype=float).reshape(3, 2, 2)),
                     "v10": (("valid_time", "latitude", "longitude"), -np.arange(12, dtype=float).reshape(3, 2, 2))},
                    coords={"valid_time": t, "latitude": [28.5, 28.75], "longitude": [77.0, 77.25]})
    g = grid_hourly(ds, 28.72, 77.02)  # nearest is (28.75, 77.0)
    assert g["u"].tolist() == [2.0, 6.0, 10.0] and g["v"].tolist() == [-2.0, -6.0, -10.0]
    assert list(g.columns) == ["time_utc", "u", "v"]


@pytest.mark.skipif(not (all(f.exists() for f in GRID_FILES) and TABLE.exists()), reason="needs the ERA5 files and the station table")
@pytest.mark.parametrize("wind_days", [1, 2])
def test_table_path_matches_grid_path_for_all_stations(wind_days):
    """The point-file table and the gridded Nov-Dec 2025 download must give the same daily wind at every station."""
    ds = xr.open_dataset(GRID_FILES[0])
    table = load_wind_table(TABLE)
    st = pd.read_csv(STATIONS)
    n_days = 0
    for r in st.itertuples():
        a = station_wind(grid_hourly(ds, r.latitude, r.longitude), wind_days)
        b = station_wind(table[int(r.id)], wind_days)
        days = a.index[a["u_mean"].notna()].intersection(b.index[b["u_mean"].notna()])
        days = days[(days >= "2025-11-03") & (days <= "2025-12-28")]
        assert len(days) > 50, f"station {r.id}: too few common days ({len(days)})"
        n_days += len(days)
        # the table is written with 5 significant digits, so allow a small rounding difference
        assert np.allclose(a.loc[days, "u_mean"], b.loc[days, "u_mean"], atol=2e-3), r.id
        assert np.allclose(a.loc[days, "v_mean"], b.loc[days, "v_mean"], atol=2e-3), r.id
        steady = days[a.loc[days, "wind_speed_vec"] > 0.5]
        diff = np.abs((a.loc[steady, "wind_from_deg"] - b.loc[steady, "wind_from_deg"] + 180) % 360 - 180)
        assert (diff < 1.0).all(), r.id
    assert n_days > 54 * 50


@pytest.mark.skipif(not (all(f.exists() for f in FIRMS) and TABLE.exists()), reason="needs the FIRMS files and the wind table")
def test_script_runs_on_the_table_source(tmp_path):
    out = tmp_path / "up.csv"
    r = subprocess.run([sys.executable, str(ROOT / "src" / "build_upwind_features.py"), "--stations", str(STATIONS),
                        "--start", "2025-10-15", "--end", "2025-10-17", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]
    got = pd.read_csv(out)
    assert len(got) == 54 * 3 * 3 * 3 and got["station_id"].nunique() == 54
    assert got["u_mean"].notna().all()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
