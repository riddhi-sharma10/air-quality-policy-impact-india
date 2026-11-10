"""H2 power check: how large a fall could the B2 method detect?

Takes the real treated daily series (real weather and fire covariates), simulates log PM2.5 from the fitted weather model plus
AR(1) noise with the residual standard deviation and day-to-day correlation seen in the real data, puts a known fall on days 1 to 3
after a random date, and runs the exact B2 pipeline (src/analysis/11_h2_its.py). Reports how often the 95% interval lies below 0.

Writes outputs/tables/T06g_h2_power.csv and figure F17. Usage: python src/analysis/13_h2_power.py [--reps 300]
"""
import argparse
import importlib
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

m = importlib.import_module("11_h2_its")
EFFECTS_PCT = [-10, -20, -30, -40, -50, -60, -70]


def simulate(series_ok, X, beta, rho, sd, effect_log, reps, rng):
    """Run `reps` simulated events; returns an array of (estimate, lower, upper) on the log scale."""
    idx = series_ok.index
    out = []
    for _ in range(reps):
        e = np.zeros(len(idx))
        for i in range(1, len(e)):
            e[i] = rho * e[i - 1] + rng.normal(0, sd * np.sqrt(1 - rho ** 2))
        ls = X @ beta + e
        k = rng.integers(80, len(idx) - 12)
        d0 = idx[k]
        post = [j for j in range(len(idx)) if 1 <= (idx[j] - d0).days <= 3]
        if len(post) < 3:
            continue
        ls[post] += effect_log
        s = series_ok.copy()
        s["log_pm25"], s["pm25"] = ls, np.exp(ls)
        full = s.reindex(pd.date_range(s.index.min(), s.index.max()))
        r = m.run_event(full, d0, d0, [])
        if r.get("status") == "ok" and "w1_3_effect_log" in r:
            out.append((r["w1_3_effect_log"], r["w1_3_lo_log"], r["w1_3_hi_log"]))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=300)
    a = ap.parse_args()
    rng = np.random.default_rng(c.SEED)
    t = c.group_daily(c.load_hourly(), "treated")
    base = t[t[m.COVARS].notna().all(axis=1)].copy()
    X, _, _ = m.zmat(base)
    y = np.log(base["pm25"].fillna(base["pm25"].median()).to_numpy())
    beta = m.ols(X, y)
    res = y - X @ beta
    sd, rho = float(res.std()), float(np.corrcoef(res[:-1], res[1:])[0, 1])
    print(f"simulation settings from the real data: residual sd {sd:.3f} (log), lag-1 autocorrelation {rho:.2f}, reps {a.reps}")
    rows = []
    for pct in [0] + EFFECTS_PCT:
        eff = np.log(1 + pct / 100.0)
        r = simulate(base, X, beta, rho, sd, eff, a.reps, rng)
        n = len(r)
        covers = float(np.mean((r[:, 1] <= eff) & (eff <= r[:, 2])))
        power = float(np.mean(r[:, 2] < 0))
        rows.append({"true_effect_pct": pct, "n_sims": n, "mean_estimate_pct": 100 * (np.exp(r[:, 0].mean()) - 1),
                     "interval_covers_truth": covers, "share_interval_below_zero": power,
                     "power_se": float(np.sqrt(power * (1 - power) / n)), "mean_interval_width_log": float(np.mean(r[:, 2] - r[:, 1]))})
        print(f"true {pct:+4d}%: n={n}, mean estimate {rows[-1]['mean_estimate_pct']:+.1f}%, interval covers truth {covers:.2f}, "
              f"share of intervals below 0 {power:.2f}")
    out = pd.DataFrame(rows)
    out.to_csv(c.OUT_TABLES / "T06g_h2_power.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    p = out[out["true_effect_pct"] < 0]
    ax.errorbar(-p["true_effect_pct"], 100 * p["share_interval_below_zero"], yerr=100 * 1.96 * p["power_se"], fmt="o-", color=c.TREATED_COLOR, capsize=3,
                label="Share of simulated events where the 95% interval is below 0")
    ax.axhline(80, color="0.4", ls="--", lw=1)
    ax.text(0.02, 0.815, "80% power", transform=ax.transAxes, fontsize=8, color="0.3")
    ax.axhline(2.5, color="0.7", ls=":", lw=1)
    ax.text(0.30, 0.03, "Share of intervals below 0 when there is no effect (should be about 2.5%): "
            f"{100 * float(out.loc[out['true_effect_pct'] == 0, 'share_interval_below_zero'].iloc[0]):.1f}%", transform=ax.transAxes, fontsize=7.5, color="0.35")
    ax.set_xlabel("True fall in PM2.5 on days 1 to 3 after the event (%)")
    ax.set_ylabel("Probability the method detects it (%)")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.set_title("H2 power: how often the B2 method detects a known fall (simulation)", fontsize=10.5)
    ax.legend(fontsize=8, loc="upper left")
    fig.text(0.01, -0.06, f"{a.reps} simulated events per point (error bars: 95% binomial interval). Simulated from the real treated daily weather and fire series with AR(1) noise "
             f"(residual sd {sd:.2f}, lag-1 autocorrelation {rho:.2f}). Source: script src/analysis/13_h2_power.py.", fontsize=7, wrap=True)
    c.finish_figure(fig, "F17_h2_power")
    plt.close(fig)
    c.register_figure("F17", "F17_h2_power", "src/analysis/13_h2_power.py", "final_dataset.parquet (real covariates), simulation")
    print("wrote T06g and figure F17")


if __name__ == "__main__":
    main()
