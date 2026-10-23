"""Tests for src/fire_geometry.py. Run:  python tests/test_fire_geometry.py   (or pytest tests/)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fire_geometry import angular_diff_deg, bearing_via_vectors_deg, initial_bearing_deg, wind_from_deg  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) < tol


def test_wind_from_cardinal_directions():
    assert close(wind_from_deg(1, 0), 270)    # u>0, v=0: blowing towards the east = from the WEST
    assert close(wind_from_deg(0, -1), 0)     # u=0, v<0: blowing towards the south = from the NORTH
    assert close(wind_from_deg(-1, 0), 90)    # u<0, v=0: from the EAST
    assert close(wind_from_deg(0, 1), 180)    # u=0, v>0: blowing towards the north = from the SOUTH


def test_wind_from_diagonal_and_scale():
    assert close(wind_from_deg(3, 3), 225)    # towards the north-east = from the SOUTH-WEST
    assert close(wind_from_deg(-2, -2), 45)   # from the NORTH-EAST
    assert close(wind_from_deg(10, 0), wind_from_deg(0.1, 0))  # speed does not change the direction


def test_calm_wind_has_no_direction():
    assert np.isnan(wind_from_deg(0, 0))


def test_angular_difference_wraps_around_north():
    assert close(angular_diff_deg(350, 10), 20)
    assert close(angular_diff_deg(10, 350), 20)
    assert close(angular_diff_deg(0, 359), 1)
    assert close(angular_diff_deg(0, 360), 0)
    assert close(angular_diff_deg(180, 0), 180)
    assert close(angular_diff_deg(90, 90), 0)


def test_upwind_decision_across_the_wrap():
    # wind from 355 deg (just west of north); a detection at bearing 5 is 10 deg away: upwind for theta 30
    assert angular_diff_deg(5, 355) <= 30
    assert angular_diff_deg(40, 355) > 30      # 45 deg away
    assert angular_diff_deg(40, 355) <= 45     # the half-angle is inclusive


def test_bearing_cardinal_directions():
    assert close(initial_bearing_deg(0, 0, 1, 0), 0)      # due north
    assert close(initial_bearing_deg(0, 0, 0, 1), 90)     # due east
    assert close(initial_bearing_deg(0, 0, -1, 0), 180)   # due south
    assert close(initial_bearing_deg(0, 0, 0, -1), 270)   # due west


def test_bearing_two_independent_methods_agree():
    rng = np.random.default_rng(1)
    for _ in range(200):
        lat1, lon1 = rng.uniform(24.5, 32.5), rng.uniform(73.5, 86.5)
        lat2, lon2 = lat1 + rng.uniform(-2, 2), lon1 + rng.uniform(-2, 2)
        a, b = initial_bearing_deg(lat1, lon1, lat2, lon2), bearing_via_vectors_deg(lat1, lon1, lat2, lon2)
        assert angular_diff_deg(a, b) < 1e-6


def test_detection_to_the_west_is_upwind_of_a_west_wind():
    wind_from = wind_from_deg(5, 0)                        # a wind blowing from the west
    to_west = initial_bearing_deg(28.6, 77.2, 28.6, 76.5)  # detection ~70 km west of the station
    to_east = initial_bearing_deg(28.6, 77.2, 28.6, 77.9)
    assert angular_diff_deg(to_west, wind_from) < 5        # upwind
    assert angular_diff_deg(to_east, wind_from) > 170      # downwind


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)):
        try:
            fn()
            print(f"[PASS] {name}")
        except AssertionError:
            failed += 1
            print(f"[FAIL] {name}")
    print(f"{failed} failed")
    sys.exit(1 if failed else 0)
