"""B2: H2 as a weather-and-fire counterfactual (interrupted time series) around GRAP escalations.

Rules are frozen in docs/work_log/RB_2026-11-10_B2.md. In short: fit log(daily PM2.5) on weather and the upwind fire
count over the 60 days before the first change, predict the days after the last change, and compare. The interval comes
from leave-block-out cross-validation in the fit window. Placebo events (high pollution, no escalation) show how much
PM2.5 falls anyway after a spike (regression to the mean).

Writes outputs/tables/T06a_h2_events.csv, T06c_h2_placebo.csv, T06d_h2_crosscheck.csv and figures F12, F13, F14.
Usage: python src/analysis/11_h2_its.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

COVARS = ["log_blh", "wind_speed", "t2m_c", "rh", "rain_flag", "log_fire"]
FIT_DAYS = 60
SKIP_AFTER_OTHER_CHANGE = 3
MIN_FIT_DAYS = 30
CV_R2_MIN = 0.40
WIN1, WIN2 = (1, 3), (4, 7)
PLACEBO_BAND = (0.75, 1.33)
# festival dates in the study window (copied from build_final_dataset.FESTIVALS), used only to annotate figures
FESTIVAL_DATES = [("Holi", pd.Timestamp("2025-03-14")), ("Dussehra", pd.Timestamp("2025-10-02")), ("Diwali", pd.Timestamp("2025-10-20")),
                  ("New Year's Eve", pd.Timestamp("2025-12-31")), ("Holi", pd.Timestamp("2026-03-04"))]
rng = np.random.default_rng(c.SEED)


def zmat(df, mu=None, sd=None):
    x = df[COVARS].astype(float)
    if mu is None:
        mu, sd = x.mean(), x.std(ddof=0).replace(0, 1.0)
    z = (x - mu) / sd
    return np.column_stack([np.ones(len(z)), z.to_numpy()]), mu, sd


def ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def block_cv(X, y, m):
    """Leave-block-out errors: consecutive blocks of m valid days are predicted from a fit without them.
    Returns the block-mean errors (actual minus predicted, log scale) and the pooled day-level CV R2."""
    n = len(y)
    errs_blocks, errs_days = [], np.full(n, np.nan)
    for s in range(0, n, m):
        idx = np.arange(s, min(s + m, n))
        if len(idx) < m:               # drop a short trailing block from the interval, keep it in the day-level errors
            keep = np.setdiff1d(np.arange(n), idx)
            b = ols(X[keep], y[keep]); errs_days[idx] = y[idx] - X[idx] @ b
            continue
        keep = np.setdiff1d(np.arange(n), idx)
        b = ols(X[keep], y[keep])
        e = y[idx] - X[idx] @ b
        errs_days[idx] = e
        errs_blocks.append(e.mean())
    r2 = 1 - np.nansum(errs_days ** 2) / np.sum((y - y.mean()) ** 2)
    return np.array(errs_blocks), r2, errs_days


def fit_window(series, d0, other_change_dates, drop_flagged=False):
    """Valid fit days: the 60 days before day 0, with PM2.5 and all covariates present, and not within 3 days after another change.
    drop_flagged (robustness check): also drop days flagged grap_uncertain or grap_inferred."""
    w = series.loc[d0 - pd.Timedelta(days=FIT_DAYS): d0 - pd.Timedelta(days=1)]
    ok = w["log_pm25"].notna() & w[COVARS].notna().all(axis=1)
    if drop_flagged:
        ok &= ~(w["uncertain_day"].fillna(False).astype(bool) | w["inferred_day"].fillna(False).astype(bool))
    for oc in other_change_dates:
        ok &= ~((w.index >= oc) & (w.index <= oc + pd.Timedelta(days=SKIP_AFTER_OTHER_CHANGE)))
    return w[ok]


def window_effect(series, dl, win, X_mu_sd, beta, smear, cv_blocks, cv_t):
    a, b = win
    post = series.loc[dl + pd.Timedelta(days=a): dl + pd.Timedelta(days=b)]
    post = post[post["log_pm25"].notna() & post[COVARS].notna().all(axis=1)]
    need = 2 if (b - a + 1) <= 3 else 2
    if len(post) < need:
        return None
    X, _, _ = zmat(post, *X_mu_sd)
    pred = X @ beta
    d = float(np.mean(post["log_pm25"].to_numpy() - pred))
    se = float(np.std(cv_blocks, ddof=1)) if len(cv_blocks) > 2 else np.nan
    crit = stats.t.ppf(0.975, max(len(cv_blocks) - 1, 1))
    pred_level = float(np.mean(np.exp(pred) * smear))
    act_level = float(post["pm25"].mean())
    return {"n_days": len(post), "effect_log": d, "se_log": se, "lo_log": d - crit * se, "hi_log": d + crit * se,
            "pct": 100 * (np.exp(d) - 1), "pct_lo": 100 * (np.exp(d - crit * se) - 1), "pct_hi": 100 * (np.exp(d + crit * se) - 1),
            "actual_mean": act_level, "predicted_mean": pred_level, "ug_diff": act_level - pred_level,
            "ug_lo": act_level - pred_level - (pred_level * (np.exp(crit * se) - 1)),
            "ug_hi": act_level - pred_level + (pred_level * (np.exp(crit * se) - 1))}


def run_event(series, d0, dl, other_change_dates, want_detail=False, windows=None, drop_flagged=False):
    """windows: list of (name, (first_day, last_day)) after the last change; the default is the two primary windows."""
    windows = windows or [("w1_3", WIN1), ("w4_7", WIN2)]
    fit = fit_window(series, d0, other_change_dates, drop_flagged)
    res = {"n_fit_days": len(fit)}
    if len(fit) < MIN_FIT_DAYS:
        res["status"] = f"fewer than {MIN_FIT_DAYS} valid fit days"
        return (res, None) if want_detail else res
    X, mu, sd = zmat(fit)
    y = fit["log_pm25"].to_numpy()
    beta = ols(X, y)
    smear = float(np.mean(np.exp(y - X @ beta)))
    res["fit_r2_in_sample"] = float(1 - np.sum((y - X @ beta) ** 2) / np.sum((y - y.mean()) ** 2))
    cvb = {}
    for m in {1, 3} | {min(b - a + 1, 7) for _, (a, b) in windows}:
        cvb[m] = block_cv(X, y, m)
    res["cv_r2"] = float(cvb[3][1])
    res["weak_counterfactual"] = bool(res["cv_r2"] < CV_R2_MIN)
    res["status"] = "ok"
    for name, win in windows:
        m = min(win[1] - win[0] + 1, 7)       # block length = window length, at most 7 days
        e = window_effect(series, dl, win, (mu, sd), beta, smear, cvb[m][0], None)
        if e is not None:
            res.update({f"{name}_{k}": v for k, v in e.items()})
    if want_detail:
        return res, {"fit": fit, "beta": beta, "mu": mu, "sd": sd, "smear": smear, "cv_day_sd": float(np.nanstd(cvb[1][2], ddof=1))}
    return res


def pool(rows, name="w1_3"):
    """Inverse-variance (fixed-effect) mean of the event effects on the log scale; the interval is not a population interval."""
    d = np.array([r[f"{name}_effect_log"] for r in rows])
    se = np.array([r[f"{name}_se_log"] for r in rows])
    w = 1 / se ** 2
    m = float(np.sum(w * d) / np.sum(w))
    s = float(np.sqrt(1 / np.sum(w)))
    return {"effect_log": m, "se_log": s, "pct": 100 * (np.exp(m) - 1), "pct_lo": 100 * (np.exp(m - 1.96 * s) - 1),
            "pct_hi": 100 * (np.exp(m + 1.96 * s) - 1), "n_events": len(rows), "unweighted_mean_pct": 100 * (np.exp(d.mean()) - 1)}


def placebo_dates(series, change_ts, target_pre7, exclude_dates):
    """Dates t with no upward stage change from t-3 d to t+7 d and a pre-7-day mean PM2.5 within the band around the event's."""
    ups = [t for t, dirn in change_ts if dirn == "up"]
    lo, hi = PLACEBO_BAND[0] * target_pre7, PLACEBO_BAND[1] * target_pre7
    out = []
    for t in series.index:
        if t < series.index[0] + pd.Timedelta(days=FIT_DAYS) or t > series.index[-1] - pd.Timedelta(days=8):
            continue
        if any((u >= t - pd.Timedelta(days=3)) and (u <= t + pd.Timedelta(days=8)) for u in ups):
            continue
        if any(abs((t - e).days) <= 7 for e in exclude_dates):
            continue
        pre7 = series.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1), "pm25"]
        if pre7.notna().sum() < 5:
            continue
        if lo <= pre7.mean() <= hi:
            out.append(t)
    return out


def crosscheck_segmented(series, d0, dl):
    """Method A: OLS of log PM2.5 on the controls, a linear time term and a post indicator (days 1 to 7 after the last change),
    over days -30 to +7, with Newey-West (lag 3) standard errors. Day 0 to the last change day are left out."""
    w = series.loc[d0 - pd.Timedelta(days=30): dl + pd.Timedelta(days=7)].copy()
    w = w[(w.index < d0) | (w.index > dl)]
    w = w[w["log_pm25"].notna() & w[COVARS].notna().all(axis=1)]
    w["post"] = (w.index > dl).astype(float)
    w["t"] = (w.index - d0).days.astype(float)
    cols = [k for k in COVARS if w[k].std() > 0] + ["t", "post"]      # a covariate that never varies in the window (e.g. no rain) is dropped
    X = sm.add_constant(w[cols].astype(float))
    m = sm.OLS(w["log_pm25"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    b, se = float(m.params["post"]), float(m.bse["post"])
    return {"post_level_change_pct": 100 * (np.exp(b) - 1), "lo": 100 * (np.exp(b - 1.96 * se) - 1), "hi": 100 * (np.exp(b + 1.96 * se) - 1),
            "n_days": len(w), "n_post_days": int(w["post"].sum())}


# ------------------------------------------------------------------------------------------ figures
def figure_f12(items, series, fname="F12_h2_actual_vs_counterfactual"):
    n = len(items)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 4.6), sharey=True)
    axes = np.atleast_1d(axes)
    ymax = 0
    for ax, it in zip(axes, items):
        r, det = it["res"], it["det"]
        d0, dl = it["d0"], it["dl"]
        w = series.loc[d0 - pd.Timedelta(days=14): dl + pd.Timedelta(days=7)]
        X, _, _ = zmat(w[w[COVARS].notna().all(axis=1)], det["mu"], det["sd"])
        wv = w[w[COVARS].notna().all(axis=1)]
        pred = np.exp(X @ det["beta"]) * det["smear"]
        band = 1.96 * det["cv_day_sd"]
        ax.axvspan(d0, dl + pd.Timedelta(days=1), color="0.85", lw=0, label="Day of change (not used)")
        ax.axvspan(dl + pd.Timedelta(days=1), dl + pd.Timedelta(days=4), color="#FFF2AE", alpha=0.6, lw=0, label="Effect days 1 to 3")
        ax.axvspan(dl + pd.Timedelta(days=4), dl + pd.Timedelta(days=8), color="#FFE0B2", alpha=0.5, lw=0, label="Effect days 4 to 7")
        ax.plot(wv.index, pred, ls="--", color="k", lw=1.2, label="Weather+fire counterfactual")
        ax.fill_between(wv.index, pred * np.exp(-band), pred * np.exp(band), color="0.5", alpha=0.18, lw=0, label="95% band (cross-validated daily error)")
        ax.plot(w.index, w["pm25"], color=c.TREATED_COLOR, lw=1.6, marker="o", ms=3, label="Actual (treated stations)")
        ax.axvline(d0, color="k", lw=1.0)
        weak = "\nWEAK counterfactual (CV R² < 0.40): not pooled" if r["weak_counterfactual"] else ""
        fest = [f"{n} {f:%d %b}" for n, f in FESTIVAL_DATES if d0 - pd.Timedelta(days=1) <= f <= dl + pd.Timedelta(days=7)]
        fest_txt = ("\nFestival in the window: " + ", ".join(fest) + " (confound)") if fest else ""
        ax.set_title(f"Stage {it['sb']}→{it['sa']} on {d0:%d %b %Y}\nfit on {r['n_fit_days']} days, CV R² = {r['cv_r2']:.2f}{weak}{fest_txt}", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
        ax.grid(alpha=0.25)
        ymax = max(ymax, np.nanmax(w["pm25"]), np.nanmax(pred * np.exp(band)))
        txt = []
        if "w1_3_pct" in r:
            txt.append(f"Days 1-3: {r['w1_3_pct']:+.0f}% [{r['w1_3_pct_lo']:+.0f}, {r['w1_3_pct_hi']:+.0f}]")
        if "w4_7_pct" in r:
            txt.append(f"Days 4-7: {r['w4_7_pct']:+.0f}% [{r['w4_7_pct_lo']:+.0f}, {r['w4_7_pct_hi']:+.0f}]")
        ax.text(0.02, 0.02, "\n".join(txt), transform=ax.transAxes, fontsize=8, va="bottom",
                bbox=dict(boxstyle="round", fc="w", ec="0.7"))
    for ax in axes:
        ax.set_ylim(0, ymax * 1.08)
        ax.set_xlabel("Date (IST)")
    axes[0].set_ylabel("PM2.5 (µg/m³), daily mean")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, -0.2))
    fig.suptitle("Actual versus weather-and-fire counterfactual PM2.5 around GRAP escalations (treated stations, 14 days before to 7 days after)", fontsize=10.5, y=1.07)
    fig.text(0.01, -0.3, "Effect = mean of log(actual) − log(predicted) over the window, shown as % change with the 95% interval from leave-block-out cross-validation in the fit window. "
             "n = 2 primary (+1 relaxed) events. Gaps = invalid days. Source: final_dataset.parquet; script src/analysis/11_h2_its.py.", fontsize=7)
    c.finish_figure(fig, fname)
    plt.close(fig)


def figure_f13(rows, pooled, fname="F13_h2_effect_per_event"):
    labels, est, lo, hi, cols = [], [], [], [], []
    for r in rows:
        for nm, tag in (("w1_3", "days 1-3"), ("w4_7", "days 4-7")):
            if f"{nm}_pct" in r:
                labels.append(f"{r['date']:%d %b %Y} (stage {r['sb']}→{r['sa']}), {tag}" + ("" if r["primary"] else "  [relaxed set]")
                              + ("  [weak counterfactual]" if r["weak_counterfactual"] else ""))
                est.append(r[f"{nm}_pct"]); lo.append(r[f"{nm}_pct_lo"]); hi.append(r[f"{nm}_pct_hi"])
                cols.append(c.TREATED_COLOR if nm == "w1_3" else "#8C510A")
    if pooled:
        labels.append("Pooled, days 1-3 (fixed effect, primary events)")
        est.append(pooled["pct"]); lo.append(pooled["pct_lo"]); hi.append(pooled["pct_hi"]); cols.append("k")
    y = np.arange(len(labels))[::-1]
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(labels) + 2))
    for yi, e, l, h, col in zip(y, est, lo, hi, cols):
        ax.errorbar(e, yi, xerr=[[e - l], [h - e]], fmt="o", color=col, capsize=3)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Change in PM2.5 relative to the weather-and-fire counterfactual (%), 95% interval")
    ax.set_title("H2: effect of GRAP escalation per event (negative = PM2.5 lower than predicted)", fontsize=10.5)
    ax.grid(alpha=0.25, axis="x")
    if not pooled:
        ax.text(0.99, 0.02, "No pooled estimate: fewer than 2 primary events with an adequate counterfactual", transform=ax.transAxes,
                ha="right", fontsize=8, bbox=dict(boxstyle="round", fc="w", ec="0.7"))
    fig.text(0.01, -0.04, "Intervals from leave-block-out cross-validation in the 60-day fit window; they do not include the uncertainty from having only a few events. "
             "Source: final_dataset.parquet; script src/analysis/11_h2_its.py.", fontsize=7)
    c.finish_figure(fig, fname)
    plt.close(fig)


def figure_f14(placebos, items, fname="F14_h2_placebo_distribution"):
    n = len(items)
    fig, axes = plt.subplots(1, n, figsize=(5.0 * n, 4.2), sharex=True)
    axes = np.atleast_1d(axes)
    allv = np.concatenate([p["effects"] for p in placebos if len(p["effects"])] + [[it["res"]["w1_3_pct"] for it in items]])
    bins = np.linspace(np.floor(allv.min() / 10) * 10, np.ceil(allv.max() / 10) * 10, 20)
    for ax, it, p in zip(axes, items, placebos):
        ax.hist(p["effects"], bins=bins, color="0.65", edgecolor="w")
        ax.axvline(it["res"]["w1_3_pct"], color=c.TREATED_COLOR, lw=2, label=f"Real event: {it['res']['w1_3_pct']:+.0f}%")
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{it['d0']:%d %b %Y} (stage {it['sb']}→{it['sa']})\n{len(p['effects'])} placebo dates; share at or below the real effect = {p['share_below']:.2f}", fontsize=9)
        ax.set_xlabel("Days 1-3 change vs counterfactual (%)")
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Number of placebo dates")
    fig.suptitle("Placebo check: same method on high-pollution dates with no stage escalation (treated stations)", fontsize=10.5, y=1.03)
    fig.text(0.01, -0.06, "Placebo dates: no upward stage change from 3 days before to 8 days after and a 7-day pre-mean PM2.5 within 0.75 to 1.33 times the real event's. Consecutive dates are not independent. "
             "Source: final_dataset.parquet; script src/analysis/11_h2_its.py.", fontsize=7)
    c.finish_figure(fig, fname)
    plt.close(fig)


def main():
    c.OUT_TABLES.mkdir(parents=True, exist_ok=True)
    d = c.load_hourly()
    treated, control = c.group_daily(d, "treated"), c.group_daily(d, "control")
    ev = pd.read_csv(c.OUT_TABLES / "grap_events.csv", parse_dates=["ts_first", "ts_last", "date_first", "date_last"])
    ch = pd.read_csv(c.OUT_TABLES / "grap_changes.csv", parse_dates=["ts_ist", "change_date"])
    change_ts = list(zip(ch["change_date"], ch["direction"]))
    chosen = ev[ev["usable_primary"] | ev["usable_relaxed"]].reset_index(drop=True)
    rows, items, placebos, control_rows, cross_rows = [], [], [], [], []
    for _, e in chosen.iterrows():
        d0, dl = e["date_first"], e["date_last"]
        own = ch.loc[ch["ts_ist"].between(e["ts_first"], e["ts_last"]), "change_date"]
        others = [x for x in ch["change_date"] if x not in set(own) and x < d0]
        res, det = run_event(treated, d0, dl, others, want_detail=True)
        res.update({"date": d0, "sb": int(e["stage_before"]), "sa": int(e["stage_after"]), "primary": bool(e["usable_primary"]),
                    "pm25_pre7_mean": float(e["pm25_pre7_mean"])})
        # descriptive comparison with the control cities (method C, not a counterfactual): same method on the control series
        cres = run_event(control, d0, dl, [], want_detail=False)
        cres.update({"date": d0})
        control_rows.append(cres)
        # placebo events on the treated series
        pdates = placebo_dates(treated, change_ts, e["pm25_pre7_mean"], [d0])
        eff = []
        for t in pdates:
            r = run_event(treated, t, t, [x for x in ch["change_date"] if x < t])
            if r.get("status") == "ok" and "w1_3_pct" in r and not r["weak_counterfactual"]:
                eff.append(r["w1_3_pct"])
        eff = np.array(eff)
        share = float(np.mean(eff <= res["w1_3_pct"])) if len(eff) else np.nan
        res.update({"placebo_n": len(eff), "placebo_share_at_or_below": share,
                    "placebo_median_pct": float(np.median(eff)) if len(eff) else np.nan})
        cross = crosscheck_segmented(treated, d0, dl)
        res.update({f"segmented_{k}": v for k, v in cross.items()})
        rows.append(res)
        items.append({"res": res, "det": det, "d0": d0, "dl": dl, "sb": res["sb"], "sa": res["sa"]})
        placebos.append({"effects": eff, "share_below": share})
        print(f"{d0:%Y-%m-%d} stage {res['sb']}->{res['sa']} primary={res['primary']}: fit days {res['n_fit_days']}, CV R2 {res['cv_r2']:.2f}, "
              f"days1-3 {res.get('w1_3_pct', np.nan):+.1f}% [{res.get('w1_3_pct_lo', np.nan):+.1f}, {res.get('w1_3_pct_hi', np.nan):+.1f}], "
              f"days4-7 {res.get('w4_7_pct', np.nan):+.1f}%, placebo n={len(eff)} share<=real {share:.2f}, "
              f"segmented {cross['post_level_change_pct']:+.1f}% [{cross['lo']:+.1f}, {cross['hi']:+.1f}], control {cres.get('w1_3_pct', np.nan):+.1f}%")
    prim = [r for r in rows if r["primary"] and not r["weak_counterfactual"] and "w1_3_pct" in r]
    pooled = pool(prim) if len(prim) >= 2 else None
    if pooled:
        print(f"pooled days 1-3 (primary, n={pooled['n_events']}): {pooled['pct']:+.1f}% [{pooled['pct_lo']:+.1f}, {pooled['pct_hi']:+.1f}]")
    pd.DataFrame(rows).to_csv(c.OUT_TABLES / "T06a_h2_events.csv", index=False)
    pd.DataFrame(control_rows).to_csv(c.OUT_TABLES / "T06d_h2_control_cities.csv", index=False)
    pd.DataFrame([{"date": it["d0"], "placebo_effect_pct": v} for it, p in zip(items, placebos) for v in p["effects"]]).to_csv(
        c.OUT_TABLES / "T06c_h2_placebo.csv", index=False)
    if pooled:
        pd.DataFrame([pooled]).to_csv(c.OUT_TABLES / "T06b_h2_pooled.csv", index=False)
    figure_f12(items, treated)
    figure_f13(rows, pooled)
    figure_f14(placebos, items)
    for fid, nm in (("F12", "F12_h2_actual_vs_counterfactual"), ("F13", "F13_h2_effect_per_event"), ("F14", "F14_h2_placebo_distribution")):
        c.register_figure(fid, nm, "src/analysis/11_h2_its.py", "final_dataset.parquet, outputs/tables/grap_events.csv")
    print("wrote T06a to T06d and figures F12 to F14")


if __name__ == "__main__":
    main()
