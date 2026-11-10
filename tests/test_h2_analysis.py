"""Tests for the H2 analysis (src/analysis): episodes, daily series rules, and the counterfactual method on synthetic data.

The synthetic tests do not need the real dataset; the last tests are skipped when the real files are absent.
Run: python -m pytest tests/test_h2_analysis.py -q
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "analysis"))
c = importlib.import_module("common")
its = importlib.import_module("11_h2_its")
ev = importlib.import_module("10_grap_events")
FINAL = ROOT / "data" / "processed" / "final_dataset.parquet"
EVENTS = ROOT / "outputs" / "tables" / "grap_events.csv"


# --------------------------------------------------------------------------------------- episodes (B1)
def _changes(times):
    ts = pd.to_datetime(times)
    return pd.DataFrame({"ts_ist": ts, "change_date": ts.normalize(), "stage_before": [2, 3, 4][:len(ts)], "stage_after": [3, 4, 3][:len(ts)],
                         "direction": ["up", "up", "down"][:len(ts)], "time_uncertain": [False] * len(ts), "time_source": ["meeting"] * len(ts)})


def test_changes_within_24_hours_form_one_episode():
    ch, ep = ev.make_episodes(_changes(["2025-12-13 10:00", "2025-12-13 19:00", "2025-12-24 12:00"]))
    assert len(ep) == 2
    first = ep.iloc[0]
    assert first["n_changes"] == 2 and first["stage_before"] == 2 and first["stage_after"] == 4 and first["direction"] == "up"


def test_exactly_24_hours_apart_is_merged_and_25_is_not():
    _, ep24 = ev.make_episodes(_changes(["2026-01-16 21:00", "2026-01-17 21:00"]))
    _, ep25 = ev.make_episodes(_changes(["2026-01-16 21:00", "2026-01-17 22:00"]))
    assert len(ep24) == 1 and len(ep25) == 2


# --------------------------------------------------------------------------------------- daily series (common)
def _hourly(n_stations, hours_by_station, value=50.0):
    rows = []
    for s in range(n_stations):
        for h in range(hours_by_station[s]):
            rows.append({"station_id": s, "city": "X", "sub_area": "X", "group": "treated", "hour_ist": pd.Timestamp("2025-11-01") + pd.Timedelta(hours=h),
                         "pm25": value + 100 * s, "network_outage": False, "u10": 1.0, "v10": 1.0, "wind_speed": 2.0, "t2m_c": 20.0, "d2m_c": 10.0,
                         "sp_hpa": 1000.0, "blh_m": 500.0, "tp_mm": 0.0, "n_up_nh_100km_45deg_lag1": 3.0, "n_nh_100km_lag1": 4.0,
                         "fire_day_status": "observed", "fire_is_nrt": False, "grap_stage": 2, "grap_uncertain": False, "grap_inferred": False})
    d = pd.DataFrame(rows)
    d["date"] = d["hour_ist"].dt.normalize()
    return d


def test_station_day_needs_18_valid_hours_and_group_day_needs_half_the_stations():
    d = _hourly(3, [24, 24, 10])                       # third station has only 10 hours: its day is invalid
    t = c.group_daily(d, "treated")
    assert t.loc["2025-11-01", "n_stations"] == 2
    assert t.loc["2025-11-01", "pm25"] == pytest.approx((50 + 150) / 2)
    d2 = _hourly(3, [24, 10, 10])                      # only 1 of 3 stations valid: below half, so the day is empty
    assert np.isnan(c.group_daily(d2, "treated").loc["2025-11-01", "pm25"])


def test_outage_hours_are_removed_before_averaging():
    d = _hourly(1, [24])
    d.loc[d["hour_ist"].dt.hour < 8, "network_outage"] = True      # 8 outage hours leave 16 valid hours: below 18
    assert np.isnan(c.group_daily(d, "treated").loc["2025-11-01", "pm25"])


# --------------------------------------------------------------------------------------- the counterfactual method
def _synthetic(effect_log, rng, n=160, rho=0.5, sd=0.35):
    idx = pd.date_range("2025-09-01", periods=n)
    x = rng.normal(size=(n, len(its.COVARS)))
    s = pd.DataFrame(x, index=idx, columns=its.COVARS)
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = rho * e[i - 1] + rng.normal(0, sd * np.sqrt(1 - rho ** 2))
    ls = 4.5 + x @ np.linspace(0.3, -0.2, len(its.COVARS)) + e
    d0 = idx[110]
    post = [i for i in range(n) if 1 <= (idx[i] - d0).days <= 3]
    ls[post] += effect_log
    s["log_pm25"], s["pm25"] = ls, np.exp(ls)
    s["uncertain_day"], s["inferred_day"] = False, False
    return s, d0


def _run(effect, reps=60, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        s, d0 = _synthetic(effect, rng)
        r = its.run_event(s, d0, d0, [])
        out.append((r["w1_3_effect_log"], r["w1_3_lo_log"], r["w1_3_hi_log"]))
    return np.array(out)


def test_method_recovers_a_known_fall_without_bias():
    r = _run(-0.30)
    assert abs(r[:, 0].mean() - (-0.30)) < 0.08


def test_method_finds_nothing_when_there_is_no_effect():
    r = _run(0.0)
    assert abs(r[:, 0].mean()) < 0.08


def test_interval_has_roughly_95_percent_coverage():
    for eff in (0.0, -0.30):
        r = _run(eff, reps=80, seed=5)
        cover = np.mean((r[:, 1] <= eff) & (eff <= r[:, 2]))
        assert 0.82 <= cover <= 1.0, f"coverage {cover:.2f} at effect {eff}"


def test_block_cv_is_near_perfect_on_noise_free_data():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(60), rng.normal(size=(60, 3))])
    y = X @ np.array([1.0, 0.5, -0.4, 0.2])
    blocks, r2, _ = its.block_cv(X, y, 3)
    assert r2 > 0.999 and np.abs(blocks).max() < 1e-8


def test_fit_window_excludes_the_day_of_the_change_and_the_days_after_other_changes():
    rng = np.random.default_rng(1)
    s, d0 = _synthetic(0.0, rng)
    other = d0 - pd.Timedelta(days=20)
    fit = its.fit_window(s, d0, [other])
    assert d0 not in fit.index and fit.index.max() == d0 - pd.Timedelta(days=1)
    assert not any(other <= day <= other + pd.Timedelta(days=3) for day in fit.index)
    assert len(fit) == 60 - 4


def test_fit_window_drops_days_without_pm25_or_covariates():
    rng = np.random.default_rng(2)
    s, d0 = _synthetic(0.0, rng)
    s.loc[d0 - pd.Timedelta(days=5), "log_pm25"] = np.nan
    s.loc[d0 - pd.Timedelta(days=6), "log_fire"] = np.nan
    assert len(its.fit_window(s, d0, [])) == 58


def test_pooled_estimate_is_the_inverse_variance_mean():
    rows = [{"w1_3_effect_log": -0.2, "w1_3_se_log": 0.1}, {"w1_3_effect_log": 0.1, "w1_3_se_log": 0.2}]
    p = its.pool(rows)
    w = np.array([100.0, 25.0])
    assert p["effect_log"] == pytest.approx((w[0] * -0.2 + w[1] * 0.1) / w.sum())
    assert p["se_log"] == pytest.approx(np.sqrt(1 / w.sum()))


# --------------------------------------------------------------------------------------- real outputs (skipped if absent)
@pytest.mark.skipif(not EVENTS.exists(), reason="run src/analysis/10_grap_events.py first")
def test_event_table_has_the_expected_primary_events():
    e = pd.read_csv(EVENTS, parse_dates=["date_first"])
    assert len(e) == 28
    prim = set(e.loc[e["usable_primary"], "date_first"].dt.strftime("%Y-%m-%d"))
    assert prim == {"2025-11-11", "2025-12-13"}
    assert (e.loc[e["usable_primary"], "valid_days_pre60"] >= 40).all()
    assert (e.loc[e["usable_primary"], "direction"] == "up").all() and (e.loc[e["usable_primary"], "stage_after"] >= 2).all()


@pytest.mark.skipif(not FINAL.exists(), reason="final_dataset.parquet not present")
def test_daily_series_matches_a_manual_recount_on_the_real_data():
    d = c.load_hourly()
    t = c.group_daily(d, "treated")
    tr = d[d["group"] == "treated"].copy()
    tr.loc[tr["network_outage"], "pm25"] = np.nan
    for day in ("2025-11-17", "2025-12-08", "2026-05-12"):
        x = tr[tr["date"] == day]
        vals = [g["pm25"].dropna().mean() for _, g in x.groupby("station_id") if g["pm25"].notna().sum() >= 18]
        assert t.loc[day, "pm25"] == pytest.approx(np.mean(vals))
        assert t.loc[day, "n_stations"] == len(vals)
