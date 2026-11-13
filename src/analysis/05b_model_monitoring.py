"""M4 (model half) and figure F16: monthly model error and input drift with thresholds drawn.

Thresholds were fixed before any result in docs/work_log/ma_2026-11-13_M4.md:
- model error: a month is flagged when its RMSE exceeds 1.5 x the reference RMSE. The reference is the median monthly RMSE of the same model in the
  train period; T04e (MK's expanding-window table) holds only out-of-sample months, so the written fallback applies: the median of the model's first
  three test months (Oct to Dec 2025), stated on the figure.
- input drift: PSI >= 0.25 or KS D >= 0.20 flags an input-month (computed by 05a_input_drift.py, month-matched).
POST-HOC (added after seeing the rule flag nothing; labelled as such): RMSE as a share of the month's mean PM2.5, because RMSE scales with the PM2.5 level.

Inputs: T04e (--h1-tables-dir), T09a (outputs/tables), final_dataset.parquet (monthly mean PM2.5 of valid treated station-days).
Outputs: outputs/tables/T09c_model_monitoring.csv, outputs/figures/F16_monitoring.png and .svg
Run:  python src/analysis/05b_model_monitoring.py --h1-tables-dir DIR
"""
import argparse
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
TABLES, FIGS = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
FACTOR, N_REF_MONTHS = 1.5, 3
PSI_MODERATE, PSI_MAJOR = 0.10, 0.25
COL_WEATHER, COL_FIRE, INK, MUTED = "#5E4FA2", "#B07A00", "#222222", "#6B6B6B"      # first two validated with scripts/validate_palette.js
MODELS = ["Weather only", "Weather + upwind fire"]
WEATHER_INPUTS = ["wind_speed", "u10", "v10", "t2m_c", "d2m_c", "blh_m", "tp_mm", "sp_hpa"]


def load_kpi_module():
    spec = importlib.util.spec_from_file_location("kpi", ROOT / "src" / "analysis" / "01b_kpi_baselines.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def monthly_mean_pm25(kpi):
    df = pd.read_parquet(kpi.DATA, columns=kpi.COLS)
    sd = kpi.station_days(df)
    t = sd[sd["group"] == "treated"]
    return t.groupby(t["date"].dt.to_period("M"))["pm25_mean"].agg(mean_pm25="mean", n_station_days="size")


def monitoring_table(h1_dir):
    e = pd.read_csv(Path(h1_dir) / "T04e_h1_expanding_window.csv")
    e["month"] = pd.PeriodIndex(e["test_month"], freq="M")
    w = e.pivot_table(index="month", columns="model", values="rmse_ugm3").sort_index()
    ref = w.iloc[:N_REF_MONTHS].median()
    out = w.copy()
    for m in MODELS:
        out[f"flag_{m}"] = w[m] > FACTOR * ref[m]
    out = out.join(monthly_mean_pm25(load_kpi_module()))
    for m in MODELS:
        out[f"rmse_pct_of_mean_{m}"] = 100 * w[m] / out["mean_pm25"]                  # post-hoc
    return out, ref


def drift_series():
    d = pd.read_csv(TABLES / "T09a_input_drift_month_matched.csv")
    d["month"] = pd.PeriodIndex(d["test_month"], freq="M")
    fire = d[d["input"] == "n_up_nh_100km_45deg_lag1"].set_index("month")["psi"]
    wx = d[d["input"].isin(WEATHER_INPUTS)].groupby("month")["psi"].max()
    wx_name = d[d["input"].isin(WEATHER_INPUTS)].loc[lambda x: x.groupby("month")["psi"].transform("max") == x["psi"]].set_index("month")["input"]
    return fire, wx, wx_name


def make_figure(tab, ref, fire, wx):
    plt.rcParams.update({"font.size": 12, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                         "axes.spines.top": False, "axes.spines.right": False})
    months = list(tab.index)
    x = np.arange(len(months))
    labels = [m.strftime("%b\n%Y") for m in months]
    fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True, constrained_layout=True)
    style = {"Weather only": dict(c=COL_WEATHER, marker="o", ls="-"), "Weather + upwind fire": dict(c=COL_FIRE, marker="s", ls="--")}

    a = ax[0]
    for m in MODELS:
        a.plot(x, tab[m], lw=2, ms=6, mfc="#fcfcfb", mew=2, color=style[m]["c"], marker=style[m]["marker"], ls=style[m]["ls"], label=m)
        a.axhline(FACTOR * ref[m], color=MUTED, lw=1, ls=":")
    a.set_ylabel("RMSE of daily station PM2.5\n(ug/m3, test month)")
    a.set_title("(a) Monthly model error, treated stations, Oct 2025 to Sep 2026 (IST)", loc="left", fontsize=12, color=INK)
    a.text(len(months) - 0.55, FACTOR * ref[MODELS[0]], f" flag line: 1.5 x median of first {N_REF_MONTHS} test months\n (no month above it)", va="top", ha="right", fontsize=10, color=MUTED)
    a.legend(frameon=False, loc="upper right", bbox_to_anchor=(1, 0.80))
    a.text(0.0, 0.02, "the two models are almost identical, so the lines overlap", transform=a.transAxes, fontsize=10, color=MUTED)

    b = ax[1]
    for m in MODELS:
        b.plot(x, tab[f"rmse_pct_of_mean_{m}"], lw=2, ms=6, mfc="#fcfcfb", mew=2, color=style[m]["c"], marker=style[m]["marker"], ls=style[m]["ls"], label=m)
    b.set_ylabel("RMSE as % of the month's\nmean PM2.5 (%)")
    b.set_ylim(bottom=0)
    b.set_title("(b) Same error relative to the PM2.5 level (post-hoc view, added after (a) flagged nothing)", loc="left", fontsize=12, color=INK)

    c = ax[2]
    px = [months.index(m) for m in fire.index if m in months]
    c.plot(px, [fire[months[i]] for i in px], lw=2, ms=6, mfc="#fcfcfb", mew=2, color=COL_FIRE, marker="s", ls="--", label="Fire input (upwind detections, 100 km, 45 deg)")
    c.plot(px, [wx[months[i]] for i in px], lw=2, ms=6, mfc="#fcfcfb", mew=2, color=COL_WEATHER, marker="o", ls="-", label="Highest PSI of the 8 weather inputs")
    c.axhline(PSI_MODERATE, color=MUTED, lw=1, ls=":")
    c.axhline(PSI_MAJOR, color=MUTED, lw=1, ls=":")
    c.text(-0.4, PSI_MODERATE, " 0.10 moderate", va="bottom", fontsize=10, color=MUTED)
    c.text(-0.4, PSI_MAJOR, " 0.25 major", va="bottom", fontsize=10, color=MUTED)
    c.set_ylabel("Population stability index\n(PSI, same month in 2025 as reference)")
    c.set_title("(c) Input drift by month, Jan 2026 has no 2025 counterpart (no point); Oct to Dec 2025 are training months", loc="left", fontsize=12, color=INK)
    c.set_ylim(-0.05, 2.15)
    c.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.0))
    c.set_xticks(x)
    c.set_xticklabels(labels)
    c.set_xlabel("Month (IST)")
    for k in (0, 1, 2):
        ax[k].grid(axis="y", color="#e6e6e6", lw=0.8)
        ax[k].set_axisbelow(True)
    rel = pd.concat([tab[f"rmse_pct_of_mean_{m}"] for m in MODELS])
    n_wx_major, n_fire_major = int((wx >= PSI_MAJOR).sum()), int((fire >= PSI_MAJOR).sum())
    fig.text(0.01, -0.01, "F16. Source: T04e (MK expanding-window RMSE; n = %d to %d station-days per month), final_dataset.parquet; scripts 05a_input_drift.py, 05b_model_monitoring.py. "
             "Thresholds fixed before results (work log M4).\nTakeaway: no month crosses the pre-set error line (a); relative to the PM2.5 level the error is %.0f%% to %.0f%% (b). "
             "Year on year, a weather input passes PSI 0.25 in %d of %d comparable months and the fire input in %d (c). "
             "Not shown: whether the drifting inputs cause the larger errors."
             % (tab["n_station_days"].min(), tab["n_station_days"].max(), rel.min(), rel.max(), n_wx_major, int(wx.notna().sum()), n_fire_major),
             fontsize=9, color=MUTED, va="top", wrap=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / "F16_monitoring.png", dpi=300, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(FIGS / "F16_monitoring.svg", bbox_inches="tight", metadata={"Date": None})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1-tables-dir", default=str(TABLES))
    args = ap.parse_args()
    tab, ref = monitoring_table(args.h1_tables_dir)
    fire, wx, wx_name = drift_series()
    out = tab.copy()
    out.index = out.index.astype(str)
    out.round(3).to_csv(TABLES / "T09c_model_monitoring.csv", index_label="test_month")
    make_figure(tab, ref, fire, wx)
    pd.set_option("display.width", 220)
    print("reference RMSE (median of first %d test months):" % N_REF_MONTHS, ref.round(1).to_dict())
    print(out.round(1).to_string())
    print("\nmonths flagged on RMSE:", int(tab[[f'flag_{m}' for m in MODELS]].sum().sum()))
    print("highest-PSI weather input by month:", wx_name.astype(str).to_dict())


if __name__ == "__main__":
    main()
