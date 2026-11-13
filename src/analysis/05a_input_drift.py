"""M4 (input half): drift of the model inputs between the train period and the test period.
Thresholds were written before the first run in docs/work_log/ma_2026-11-13_M4.md and are copied below.
Reads data/processed/final_dataset.parquet; writes outputs/tables/T09a_input_drift_month_matched.csv and T09b_input_drift_overall.csv.
Run:  python src/analysis/05a_input_drift.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "processed" / "final_dataset.parquet"
OUT = ROOT / "outputs" / "tables"

TRAIN = ("2025-02-19", "2025-12-31 23:00")
TEST = ("2026-01-01", "2026-09-30 23:00")
INPUTS = ["n_up_nh_100km_45deg_lag1", "wind_speed", "u10", "v10", "t2m_c", "d2m_c", "blh_m", "tp_mm", "sp_hpa"]
PSI_MODERATE, PSI_MAJOR, KS_FLAG, N_BINS = 0.10, 0.25, 0.20, 10      # fixed in advance
MIN_N = 1000


def psi(ref, new, n_bins=N_BINS):
    """Population stability index of `new` against `ref`; bins are quantiles of `ref` (ties merged), open at both ends."""
    ref, new = np.asarray(ref, float), np.asarray(new, float)
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)[1:-1]))
    edges = np.concatenate([[-np.inf], edges, [np.inf]])
    p = np.histogram(ref, edges)[0] / len(ref)
    q = np.histogram(new, edges)[0] / len(new)
    p, q = np.clip(p, 1e-4, None), np.clip(q, 1e-4, None)
    return float(np.sum((q - p) * np.log(q / p)))


def ks_d(a, b):
    """Two-sample Kolmogorov-Smirnov statistic (largest gap between the two empirical distribution functions)."""
    a, b = np.sort(np.asarray(a, float)), np.sort(np.asarray(b, float))
    grid = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, grid, side="right") / len(a) - np.searchsorted(b, grid, side="right") / len(b))))


def verdict(p, d):
    if p >= PSI_MAJOR or d >= KS_FLAG:
        return "flagged"
    return "moderate" if p >= PSI_MODERATE else "stable"


def compare(ref, new, col):
    r, n = ref[col].dropna(), new[col].dropna()
    if len(r) < MIN_N or len(n) < MIN_N:
        return dict(n_train=len(r), n_test=len(n), psi=np.nan, ks_d=np.nan, mean_train=np.nan, mean_test=np.nan, status="n/a")
    p, d = psi(r, n), ks_d(r, n)
    return dict(n_train=len(r), n_test=len(n), psi=round(p, 3), ks_d=round(d, 3), mean_train=round(r.mean(), 3),
                mean_test=round(n.mean(), 3), status=verdict(p, d))


def main():
    df = pd.read_parquet(DATA, columns=["hour_ist", "network_outage", "fire_day_status"] + INPUTS)
    df = df[~df["network_outage"]].copy()
    df.loc[df["fire_day_status"] == "outage", "n_up_nh_100km_45deg_lag1"] = np.nan
    train = df[(df.hour_ist >= TRAIN[0]) & (df.hour_ist <= TRAIN[1])]
    test = df[(df.hour_ist >= TEST[0]) & (df.hour_ist <= TEST[1])]
    OUT.mkdir(parents=True, exist_ok=True)

    overall = pd.DataFrame([dict(input=c, **compare(train, test, c)) for c in INPUTS])
    overall.insert(1, "comparison", "all train vs all test (season mix differs)")
    overall.to_csv(OUT / "T09b_input_drift_overall.csv", index=False)

    rows = []
    for m in range(1, 10):                                           # test months Jan to Sep 2026
        new = test[test.hour_ist.dt.month == m]
        ref = train[train.hour_ist.dt.month == m]                    # same calendar month in the train period
        for c in INPUTS:
            rows.append(dict(test_month=f"2026-{m:02d}", input=c, **compare(ref, new, c)))
    monthly = pd.DataFrame(rows)
    monthly.to_csv(OUT / "T09a_input_drift_month_matched.csv", index=False)

    pd.set_option("display.width", 200)
    print("OVERALL (train 19 Feb-31 Dec 2025 vs test Jan-Sep 2026; season mix differs)")
    print(overall.drop(columns="comparison").to_string(index=False))
    print("\nMONTH-MATCHED status (rows = input, columns = test month)")
    print(monthly.pivot(index="input", columns="test_month", values="status").reindex(INPUTS).to_string())
    print("\nMONTH-MATCHED PSI")
    print(monthly.pivot(index="input", columns="test_month", values="psi").reindex(INPUTS).to_string())
    print("\nflagged input-months:", int((monthly.status == "flagged").sum()), "of", int((monthly.status != "n/a").sum()))


if __name__ == "__main__":
    main()
