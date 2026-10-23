"""Tests for src/build_pollution_hourly.py. Run:  python tests/test_pollution_hourly.py   (or pytest tests/)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from build_pollution_hourly import GRID, END, START, flat_runs  # noqa: E402


def test_flat_runs_marks_only_long_identical_runs():
    s = pd.Series([5.0] * 24 + [6.0] + [7.0] * 23 + [np.nan] + [9.0] * 30)
    m = flat_runs(s, 24)
    assert m[:24].all() and not m[24] and not m[25:48].any()   # 23 equal values: kept
    assert not m[48] and m[49:].all()                           # NaN breaks a run; the 30-run is flagged


def test_flat_runs_nan_is_never_flagged():
    assert not flat_runs(pd.Series([np.nan] * 30), 24).any()


def test_grid_is_the_study_window():
    assert len(GRID) == 589 * 24 == 14136
    assert GRID[0] == START and GRID[-1] == END + pd.Timedelta(hours=23)
    assert GRID.is_unique


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
