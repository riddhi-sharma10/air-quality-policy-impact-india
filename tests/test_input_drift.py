"""Tests for the PSI and KS functions in src/analysis/05a_input_drift.py (M4)."""
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("drift", ROOT / "src" / "analysis" / "05a_input_drift.py")
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


def test_identical_samples_have_zero_drift():
    x = np.random.default_rng(0).normal(size=5000)
    assert drift.psi(x, x) < 1e-6 and drift.ks_d(x, x) == 0.0


def test_a_shift_gives_large_psi_and_ks():
    rng = np.random.default_rng(1)
    a, b = rng.normal(0, 1, 20000), rng.normal(1.5, 1, 20000)
    assert drift.psi(a, b) > 0.25 and drift.ks_d(a, b) > 0.2
    assert drift.verdict(drift.psi(a, b), drift.ks_d(a, b)) == "flagged"


def test_same_distribution_different_draw_is_stable():
    rng = np.random.default_rng(2)
    a, b = rng.normal(size=20000), rng.normal(size=20000)
    assert drift.psi(a, b) < 0.01 and drift.verdict(drift.psi(a, b), drift.ks_d(a, b)) == "stable"


def test_ks_matches_a_hand_value():
    # {1,2,3,4} against {3,4,5,6}: the distribution functions differ by at most 0.5 (at 2 and 3)
    assert drift.ks_d([1, 2, 3, 4], [3, 4, 5, 6]) == 0.5


def test_psi_handles_many_ties_like_fire_counts():
    rng = np.random.default_rng(3)
    a = rng.poisson(0.3, 20000).astype(float)
    b = rng.poisson(3.0, 20000).astype(float)
    assert drift.psi(a, a.copy()) < 1e-6 and drift.psi(a, b) > 0.25
