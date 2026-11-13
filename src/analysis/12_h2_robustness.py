"""B3: robustness of the H2 counterfactual estimates (checks fixed in docs/work_log/RB_2026-11-10_B3.md).

Each check changes one setting of the B2 pipeline (src/analysis/11_h2_its.py) and re-estimates the effect for every event in
outputs/tables/grap_events.csv that is in the primary or the relaxed set. Writes T06e_h2_robustness.csv,
T06f_h2_robustness_summary.csv and figure F15.

Usage: python src/analysis/12_h2_robustness.py
"""
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

m = importlib.import_module("11_h2_its")   # the B2 module; its settings are changed one at a time below

XLIM = (-100, 320)   # F15 x-axis; wider intervals are cut and labelled
WINDOW_NOTE = {5: "", 7: " (touches the next stage change)", 14: " (runs into the next stage change)"}


def stations_of(group="treated", exclude_sub_area=None, min_pct=None):
    st = pd.read_csv(c.ROOT / "data" / "processed" / "stations_final.csv", encoding="utf-8-sig")
    st = st[st["group"] == group]
    if exclude_sub_area:
        st = st[st["sub_area"] != exclude_sub_area]
    if min_pct is not None:
        st = st[st["pct_pm25"] >= min_pct]
    return st["id"].tolist()


def run_check(label, series, events, changes, windows=None, drop_flagged=False, covars=None, fit_days=None, win_label="w1_3"):
    """Run all events under one setting; returns a list of rows."""
    old_cov, old_fit = m.COVARS, m.FIT_DAYS
    if covars is not None:
        m.COVARS = covars
    if fit_days is not None:
        m.FIT_DAYS = fit_days
    rows = []
    try:
        for _, e in events.iterrows():
            d0, dl = e["date_first"], e["date_last"]
            own = changes.loc[changes["ts_ist"].between(e["ts_first"], e["ts_last"]), "change_date"]
            others = [x for x in changes["change_date"] if x not in set(own) and x < d0]
            r = m.run_event(series, d0, dl, others, windows=windows, drop_flagged=drop_flagged)
            row = {"check": label, "event_date": d0, "stage": f"{int(e['stage_before'])}->{int(e['stage_after'])}",
                   "primary_event": bool(e["usable_primary"]), "n_fit_days": r.get("n_fit_days"), "status": r.get("status"),
                   "cv_r2": r.get("cv_r2"), "weak_counterfactual": r.get("weak_counterfactual"), "window": win_label}
            for k in ("n_days", "pct", "pct_lo", "pct_hi", "ug_diff"):
                row[k] = r.get(f"{win_label}_{k}")
            rows.append(row)
    finally:
        m.COVARS, m.FIT_DAYS = old_cov, old_fit
    return rows


def figure_f15(out, fname="F15_h2_robustness"):
    prim = out[out["primary_event"]]
    dates = sorted(prim["event_date"].unique())
    fig, axes = plt.subplots(1, len(dates), figsize=(6.4 * len(dates), 0.42 * out["check"].nunique() + 2.4), sharey=True, sharex=True)
    axes = np.atleast_1d(axes)
    checks = list(dict.fromkeys(out["check"]))
    ypos = {k: i for i, k in enumerate(checks[::-1])}
    for ax, dt in zip(axes, dates):
        g = prim[prim["event_date"] == dt]
        stg = g["stage"].iloc[0]
        for _, r in g.iterrows():
            if pd.isna(r["pct"]):
                ax.text(0.02, ypos[r["check"]], "no estimate (fewer than 30 valid fit days)", fontsize=7, va="center", transform=ax.get_yaxis_transform(), color="0.4")
                continue
            weak = bool(r["weak_counterfactual"])
            ax.errorbar(r["pct"], ypos[r["check"]], xerr=[[r["pct"] - r["pct_lo"]], [r["pct_hi"] - r["pct"]]], fmt="o", ms=5,
                        mfc="white" if weak else c.TREATED_COLOR, mec=c.TREATED_COLOR, ecolor=c.TREATED_COLOR, capsize=2, lw=1.1)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_xlim(XLIM)
        for _, r in g.iterrows():            # intervals running past the axis are cut and marked with an arrow and the true bound
            if pd.notna(r["pct_hi"]) and r["pct_hi"] > XLIM[1]:
                ax.annotate(f"to +{r['pct_hi']:,.0f}%", (XLIM[1], ypos[r["check"]]), xytext=(-4, 5), textcoords="offset points",
                            ha="right", fontsize=6.5, color="0.3", arrowprops=dict(arrowstyle="->", color=c.TREATED_COLOR, lw=1))
        ax.set_title(f"{pd.Timestamp(dt):%d %b %Y}, stage {stg}", fontsize=10)
        ax.set_xlabel("Change in PM2.5 vs counterfactual (%), 95% interval")
        ax.grid(alpha=0.25, axis="x")
    axes[0].set_yticks(list(ypos.values()))
    axes[0].set_yticklabels(list(ypos.keys()), fontsize=7.5)
    fig.suptitle("H2 robustness: effect of GRAP escalation under each check (primary events; hollow marker = weak counterfactual, CV R² < 0.40)",
                 fontsize=10.5, y=0.995)
    fig.tight_layout(rect=[0, 0.08, 1, 0.97])
    fig.text(0.01, 0.01, "Each row changes one setting of the main specification (top row). Effect window is days 1 to 3 unless the row says otherwise. "
             "Rows are not independent; intervals cut at the axis edge are marked with an arrow.\n"
             "The 19 Oct 2025 event (Diwali) is in T06e only. Weather-offset check pending (needs RS). Source: final_dataset.parquet; script src/analysis/12_h2_robustness.py.\n"
             + m.FORECAST_NOTE + " " + m.POWER_NOTE, fontsize=7)
    c.finish_figure(fig, fname)
    plt.close(fig)


def main():
    c.OUT_TABLES.mkdir(parents=True, exist_ok=True)
    d = c.load_hourly()
    base = c.group_daily(d, "treated")
    events = pd.read_csv(c.OUT_TABLES / "grap_events.csv", parse_dates=["ts_first", "ts_last", "date_first", "date_last"])
    events = events[events["usable_primary"] | events["usable_relaxed"]].reset_index(drop=True)
    changes = pd.read_csv(c.OUT_TABLES / "grap_changes.csv", parse_dates=["ts_ist", "change_date"])
    covars_nofire = [k for k in m.COVARS if k != "log_fire"]
    rows = []
    rows += run_check("0 baseline (B2)", base, events, changes)
    rows += run_check("1 drop flagged fit days", base, events, changes, drop_flagged=True)
    rows += run_check("2 24-hour buffer (days 2-4)", base, events, changes, windows=[("w2_4", (2, 4))], win_label="w2_4")
    for b in (5, 7, 14):
        rows += run_check(f"3 window days 1-{b}{WINDOW_NOTE[b]}", base, events, changes, windows=[(f"w1_{b}", (1, b))], win_label=f"w1_{b}")
    good = stations_of(min_pct=90)
    rows += run_check(f"7 stations with 90%+ PM2.5 coverage (n={len(good)})", c.group_daily(d, "treated", stations=good), events, changes)
    for sa in ("Delhi", "Ghaziabad", "Noida", "Gurugram"):
        keep = stations_of(exclude_sub_area=sa)
        rows += run_check(f"8 without {sa} (n={len(keep)})", c.group_daily(d, "treated", stations=keep), events, changes)
    rows += run_check("12 no fire term", base, events, changes, covars=covars_nofire)
    for v in (12, 20):
        rows += run_check(f"13 valid day = {v} hours", c.group_daily(d, "treated", min_valid_hours=v), events, changes)
    for fd in (45, 90):
        rows += run_check(f"14 fit window {fd} days", base, events, changes, fit_days=fd)
    out = pd.DataFrame(rows)
    out.to_csv(c.OUT_TABLES / "T06e_h2_robustness.csv", index=False)

    # sign agreement and ranges (the checks are not independent: this is a consistency table, not a test)
    summ = []
    for (dt, stg), g in out.groupby(["event_date", "stage"]):
        ok = g[(g["status"] == "ok") & g["pct"].notna()]
        adequate = ok[~ok["weak_counterfactual"].astype(bool)]
        summ.append({"event_date": dt, "stage": stg, "n_checks_run": len(g), "n_with_estimate": len(ok), "n_adequate_counterfactual": len(adequate),
                     "share_negative_all": float((ok["pct"] < 0).mean()) if len(ok) else np.nan,
                     "share_negative_adequate": float((adequate["pct"] < 0).mean()) if len(adequate) else np.nan,
                     "share_interval_below_zero": float((ok["pct_hi"] < 0).mean()) if len(ok) else np.nan,
                     "min_pct": ok["pct"].min(), "median_pct": ok["pct"].median(), "max_pct": ok["pct"].max()})
    summ = pd.DataFrame(summ)
    summ.to_csv(c.OUT_TABLES / "T06f_h2_robustness_summary.csv", index=False)
    print(summ.round(2).to_string(index=False))
    base_rows = out[out["check"].str.startswith("0 ")]
    chk = [("baseline reproduces the B2 table (days 1-3 effects)",
            np.allclose(base_rows["pct"].to_numpy(float), pd.read_csv(c.OUT_TABLES / "T06a_h2_events.csv")["w1_3_pct"].to_numpy(float))),
           ("every check ran for every selected event", len(out) == out["check"].nunique() * len(events))]
    for lab, ok in chk:
        print(f"  [{'PASS' if ok else 'FAIL'}] {lab}")
    if not all(ok for _, ok in chk):
        sys.exit("a check failed")
    figure_f15(out)
    c.register_figure("F15", "F15_h2_robustness", "src/analysis/12_h2_robustness.py", "final_dataset.parquet, outputs/tables/grap_events.csv")
    print("wrote T06e, T06f and figure F15")


if __name__ == "__main__":
    main()
