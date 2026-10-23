"""Tests for src/extract_era5_stations.py. Run:  python tests/test_extract_era5_stations.py   (or pytest tests/)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from extract_era5_stations import convert, nearest_cells  # noqa: E402
from era5_window import PERIODS, period_hours  # noqa: E402


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) < tol


def frame(**kw):
    base = dict(u10=0.0, v10=0.0, d2m=273.15, t2m=273.15, sp=100000.0, blh=500.0, tp=0.0)
    base.update(kw)
    return convert(pd.DataFrame({k: [v] for k, v in base.items()}))


def test_units():
    r = frame(t2m=300.15, d2m=290.15, sp=99000.0, tp=0.0025).iloc[0]
    assert close(r.t2m_c, 27.0) and close(r.d2m_c, 17.0)
    assert close(r.sp_hpa, 990.0)
    assert close(r.tp_mm, 2.5)


def test_negative_rain_noise_is_clipped():
    assert frame(tp=-1e-9).iloc[0].tp_mm == 0.0


def test_wind_speed_and_direction():
    r = frame(u10=3.0, v10=4.0).iloc[0]
    assert close(r.wind_speed, 5.0)
    assert close(frame(u10=5.0, v10=0.0).iloc[0].wind_from_deg, 270)   # westerly
    assert close(frame(u10=0.0, v10=-5.0).iloc[0].wind_from_deg, 0)    # northerly
    assert np.isnan(frame().iloc[0].wind_from_deg)                      # calm


def test_nearest_cell():
    lats = np.array([29.5, 29.25, 29.0, 28.75, 28.5])
    lons = np.array([76.5, 76.75, 77.0, 77.25, 77.5])
    st = pd.DataFrame({"latitude": [28.563, 29.4], "longitude": [77.187, 76.55]})
    ilat, ilon = nearest_cells(st, lats, lons)
    assert list(lats[ilat]) == [28.5, 29.5]
    assert list(lons[ilon]) == [77.25, 76.5]


def test_request_periods_within_cds_limit_and_contiguous():
    assert all(period_hours(p) <= 120 * 24 for p in PERIODS)
    months = [(y, m) for y, a, b in PERIODS for m in range(a, b + 1)]
    expected = pd.period_range("2025-02", "2026-09", freq="M")
    assert months == [(p.year, p.month) for p in expected]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} passed")
