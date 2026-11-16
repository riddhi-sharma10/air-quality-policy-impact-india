"""Two exploratory analyses that are NOT in the notebook (their results are documented in docs/exploratory_analyses_not_in_notebook.md).
The third extension analysis, H3 (ventilation), is in the notebook, Phase 8C.

Run from the repository root:   python src/exploratory_analyses.py
Needs data/processed/analysis_station_day.parquet (made by `python run_all.py --from-final`) and data/processed/final_dataset.parquet.
Writes outputs/exploratory/tables/X*.csv and outputs/exploratory/figures/X*.png/.svg (a separate folder, so the notebook inventory is unaffected).

Both were written down BEFORE they were run (16 Nov 2026) and are EXPLORATORY: "added after seeing results".

X1  Upwind fires and PM2.5 inside the April-May fire season (Apr-May 2025 and Apr-May 2026)
     Why: the frozen H1 sample (Oct 2025 to Feb 2026) mixes the fire season with the smog season. April-May has much more day-to-day fire variation.
     Model: the frozen primary H1 model (log daily PM2.5 on the previous-day upwind count within 100 km and 45 degrees, eight weather controls,
          station and weekday effects, treated stations, standard errors clustered by date); only the sample changes. Effect per +5 detections.
     Rule: SUPPORTED if above 0 with the 95% interval excluding 0 and the same sign in at least 75% of the sensitivity runs; NOT SUPPORTED if the
          interval excludes 0 on the negative side; otherwise INCONCLUSIVE. The next-day placebo is reported, not part of the rule.
     Evaluation (added after the first results): train Apr-May 2025, test Apr-May 2026, with and without the fire term.

X2  Traffic and dust tracers after Stage III/IV (GRAP mechanism test)
     Why: Stage III/IV restricts trucks, vehicles and construction; traffic gases and coarse dust should fall RELATIVE to PM2.5 if it works as designed.
     Sample: Oct 2025 to Feb 2026; station-days with at least 18 valid hours of each pollutant used; outage hours dropped.
     Model: log outcome on x (1 on days when Stage III or IV was in force for at least half of the hours at treated stations; 0 for control cities and
          other days), station effects and date effects. Errors clustered by date and by station; the decision interval is the wider of the two.
     Outcomes: log(NO2/PM2.5), log(CO/PM2.5), log(PM10/PM2.5); log PM2.5, log NO2, log CO as reference. Gas units are mislabelled in the archive:
          only relative changes are read.
     Rule: SUPPORTED if BOTH traffic ratios fall with the decision interval excluding 0 and the same sign in at least 75% of the sensitivity runs;
          NOT SUPPORTED if either rises with the interval excluding 0; otherwise INCONCLUSIVE. The dust ratio is reported separately.
     Added after the first results: a stress test on equally polluted days, and a placebo that moves the stage timeline by 12 to 60 days.
"""
import os, sys
import numpy as np
import pandas as pd
import patsy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.regression.linear_model import OLS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TAB, FIG = os.path.join(ROOT, "outputs", "exploratory", "tables"), os.path.join(ROOT, "outputs", "exploratory", "figures")
DAY = os.path.join(ROOT, "data", "processed", "analysis_station_day.parquet")
FINAL = os.path.join(ROOT, "data", "processed", "final_dataset.parquet")
TREATED_C = "#D55E00"
FIRE = "n_up_nh_100km_45deg_lag1"
CONTROLS = "wind_speed + wind_dir_sin + wind_dir_cos + t2m_c + rh_pct + blh_m + tp_mm + sp_hpa"
WINTER = (pd.Timestamp("2025-10-01"), pd.Timestamp("2026-02-28"))
APR_MAY = [(pd.Timestamp("2025-04-01"), pd.Timestamp("2025-05-31")), (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-05-31"))]
if not os.path.exists(DAY) or not os.path.exists(FINAL):
    sys.exit("Missing data/processed/analysis_station_day.parquet or final_dataset.parquet: run `python run_all.py --from-final` first.")
os.makedirs(TAB, exist_ok=True)
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"svg.hashsalt": "x", "svg.fonttype": "none", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def fit(formula, data, cluster):
    y, X = patsy.dmatrices(formula, data, return_type="dataframe")
    groups = pd.factorize(data.loc[X.index, cluster])[0]
    return OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups}), X.index


def pct(res, term, scale=1.0):
    b, ci, p = res.params[term], res.conf_int().loc[term], res.pvalues[term]
    f = lambda v: 100 * (np.exp(v * scale) - 1)
    return f(b), f(ci[0]), f(ci[1]), p


def save_fig(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=200, bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".svg"), bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)


def forest(ax, rows):
    """rows: list of (label, effect, lo, hi, highlight)"""
    for i, (lab, e, lo, hi, hl) in enumerate(rows[::-1]):
        c = TREATED_C if hl else "#555555"
        ax.plot([lo, hi], [i, i], color=c, lw=2.2)
        ax.plot(e, i, "o", color=c, ms=6)
        ax.text(hi, i, f"  {e:+.1f}%", va="center", fontsize=8.5, color=c)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8.5)
    ax.axvline(0, color="#888888", ls="--", lw=1)


def oos(label, analysis, formula, train, test, cols):
    tr, te = train.dropna(subset=cols), test.dropna(subset=cols)
    te = te[te["station_id"].isin(tr["station_id"].unique())]
    y, X = patsy.dmatrices(formula, tr, return_type="dataframe")
    res = OLS(y, X).fit()
    smear = float(np.mean(np.exp(res.resid)))
    Xt = patsy.build_design_matrices([X.design_info], te, return_type="dataframe")[0]
    pred = np.exp(np.asarray(Xt @ res.params)) * smear
    act = te.loc[Xt.index, "pm25_day"].to_numpy()
    return {"Analysis": analysis, "Model": label, "Train station-days": int(res.nobs), "Test station-days": len(act),
            "Test RMSE (ug/m3)": round(float(np.sqrt(np.mean((act - pred) ** 2))), 2), "Test MAE (ug/m3)": round(float(np.mean(np.abs(act - pred))), 2),
            "Test R-squared": round(1 - float(np.sum((act - pred) ** 2) / np.sum((act - act.mean()) ** 2)), 3), "In-sample adj. R-squared": round(res.rsquared_adj, 3)}


day = pd.read_parquet(DAY)
day["date_ist"] = pd.to_datetime(day["date_ist"])
status, runs_log = [], []

# ============================ X1: April-May fires ============================
def h1_frame(window_list, groups=("treated",)):
    frame = day[day["group"].isin(groups)].copy()
    frame = frame[np.logical_or.reduce([frame["date_ist"].between(a, b) for a, b in window_list])]
    frame["log_pm25"], frame["weekday"] = np.log(frame["pm25_day"]), frame["date_ist"].dt.dayofweek
    frame["week"] = frame["date_ist"].dt.isocalendar().week.astype(int)
    frame["year"] = frame["date_ist"].dt.year
    lead = day[["station_id", "date_ist", FIRE]].copy()
    lead["date_ist"] -= pd.Timedelta(days=1)
    return frame.merge(lead.rename(columns={FIRE: "fire_lead"}), on=["station_id", "date_ist"], how="left")

x1 = []
def run_x1(label, frame, var=FIRE, extra="", per="+5", scale=5.0, primary=False, placebo=False):
    res, idx = fit(f"log_pm25 ~ {var} + {CONTROLS} + C(station_id) + C(weekday){extra}", frame, "date_ist")
    e, lo, hi, p = pct(res, var, scale)
    x1.append({"Run": label, "Unit": f"per {per}", "Effect (%)": round(e, 2), "CI low": round(lo, 2), "CI high": round(hi, 2), "p": round(p, 4),
               "Station-days": int(res.nobs), "Dates": frame.loc[idx, "date_ist"].nunique(), "Primary": primary, "Placebo": placebo})
    return e

am = h1_frame(APR_MAY)
sd = lambda col: float(am[col].std())
primary_x1 = run_x1("PRIMARY: Apr-May, treated, upwind count", am, primary=True)
winter_ref = run_x1("Reference: frozen winter sample (Oct to Feb)", h1_frame([WINTER]))
run_x1("Treated and control stations together", h1_frame(APR_MAY, ("treated", "control")))
run_x1("Year effect added", am, extra=" + C(year)")
run_x1("Week effects added", am, extra=" + C(week)")
run_x1("Apr-May 2025 only", am[am["year"] == 2025])
run_x1("Apr-May 2026 only", am[am["year"] == 2026])
run_x1("Fire radiative power (upwind), per +1 SD", am, var="frp_up_nh_100km_45deg_lag1", per="+1 SD", scale=sd("frp_up_nh_100km_45deg_lag1"))
run_x1("All-direction count within 200 km, per +1 SD", am, var="n_nh_200km_lag1", per="+1 SD", scale=sd("n_nh_200km_lag1"))
run_x1("Placebo: next day's upwind count", am, var="fire_lead", placebo=True)
t1 = pd.DataFrame(x1)
t1["Same sign as primary"] = np.sign(t1["Effect (%)"]) == np.sign(primary_x1)
t1.to_csv(os.path.join(TAB, "X1_aprmay_fire.csv"), index=False)
sens = t1[~t1["Primary"] & ~t1["Placebo"] & ~t1["Run"].str.startswith("Reference")]
pr = t1[t1["Primary"]].iloc[0]
share = sens["Same sign as primary"].mean()
s1 = "SUPPORTED" if (pr["CI low"] > 0 and share >= .75) else "NOT SUPPORTED" if pr["CI high"] < 0 else "INCONCLUSIVE"
status.append(["X1 fires in Apr-May", s1, f"{pr['Effect (%)']:+.1f}% per +5 [{pr['CI low']:+.1f}, {pr['CI high']:+.1f}]; same sign in {int(sens['Same sign as primary'].sum())} of {len(sens)} sensitivity runs"])
fig, ax = plt.subplots(figsize=(8.5, 4.6))
forest(ax, [(r["Run"], r["Effect (%)"], r["CI low"], r["CI high"], r["Primary"]) for _, r in t1.iterrows()])
ax.set_xlabel("Change in PM2.5 (%) per +5 upwind detections (SD-based rows: per +1 SD); 95% interval, date-clustered")
ax.set_title("X1. Fires and PM2.5 inside the April-May season (daily, treated stations)", fontsize=10, loc="left")
save_fig(fig, "X1_aprmay_fire")
tr1, te1 = am[am["year"] == 2025], am[am["year"] == 2026]
cols1 = ["log_pm25", "weekday", FIRE, "wind_speed", "wind_dir_sin", "wind_dir_cos", "t2m_c", "rh_pct", "blh_m", "tp_mm", "sp_hpa"]
ev1 = pd.DataFrame([oos(lab, "X1 (train Apr-May 2025, test Apr-May 2026)", f"log_pm25 ~ C(station_id) + C(weekday) + {CONTROLS}{rhs}", tr1, te1, cols1)
                    for lab, rhs in [("Weather controls only", ""), ("Weather controls + upwind fire", f" + {FIRE}")]])
ev1.to_csv(os.path.join(TAB, "X1b_aprmay_out_of_sample.csv"), index=False)
runs_log.append(["X1 (10 regression runs, 2 out-of-sample fits)", len(t1) + len(ev1)])

# ============================ X2: tracers after Stage III/IV ============================
h = pd.read_parquet(FINAL, columns=["station_id", "group", "sub_area", "hour_ist", "pm25", "pm10", "no2", "co", "network_outage", "grap_stage_applied"])
h["date_ist"] = pd.to_datetime(h["hour_ist"]).dt.normalize()
h = h[h["date_ist"].between(*WINTER)]
ok = ~h["network_outage"]
for v in ("pm25", "pm10", "no2", "co"):
    h[v] = h[v].where(ok)
h["s3"], h["s2"] = (h["grap_stage_applied"] >= 3).astype(float), (h["grap_stage_applied"] >= 2).astype(float)
agg = h.groupby(["station_id", "group", "sub_area", "date_ist"], observed=True).agg(
    pm25=("pm25", "mean"), n_pm25=("pm25", "count"), pm10=("pm10", "mean"), n_pm10=("pm10", "count"), no2=("no2", "mean"), n_no2=("no2", "count"),
    co=("co", "mean"), n_co=("co", "count"), s3=("s3", "mean"), s2=("s2", "mean")).reset_index()
def build(min_hours=18):
    d = agg.copy()
    for v in ("pm25", "pm10", "no2", "co"):
        d.loc[d[f"n_{v}"] < min_hours, v] = np.nan
    d = d[(d[["pm25", "pm10", "no2", "co"]] > 0).where(d[["pm25", "pm10", "no2", "co"]].notna(), True).all(axis=1)]
    d["x"], d["x2"] = (d["s3"] >= .5).astype(float), (d["s2"] >= .5).astype(float)
    d["l_pm25"], d["l_no2"], d["l_co"] = np.log(d["pm25"]), np.log(d["no2"]), np.log(d["co"])
    d["l_no2r"], d["l_cor"], d["l_pm10r"] = np.log(d["no2"] / d["pm25"]), np.log(d["co"] / d["pm25"]), np.log(d["pm10"] / d["pm25"])
    return d
OUTC = [("l_no2r", "NO2 / PM2.5 (traffic)"), ("l_cor", "CO / PM2.5 (traffic)"), ("l_pm10r", "PM10 / PM2.5 (coarse dust share)"),
        ("l_pm25", "PM2.5 (reference)"), ("l_no2", "NO2 (reference)"), ("l_co", "CO (reference)")]
x2 = []
def run_x2(run, d, xvar="x", fe="C(date_ist)"):
    for col, lab in OUTC:
        s = d.dropna(subset=[col])
        f = f"{col} ~ {xvar} + C(station_id)" + (f" + {fe}" if fe else "")
        rd, _ = fit(f, s, "date_ist")
        rs, _ = fit(f, s, "station_id")
        e, lo_d, hi_d, p_d = pct(rd, xvar)
        _, lo_s, hi_s, _ = pct(rs, xvar)
        x2.append({"Run": run, "Outcome": lab, "Effect (%)": round(e, 2), "Decision CI low": round(min(lo_d, lo_s), 2), "Decision CI high": round(max(hi_d, hi_s), 2),
                   "p (date)": round(p_d, 4), "Station-days": int(rd.nobs), "Stage III/IV station-days": int(s[xvar].sum())})
base = build(18)
run_x2("PRIMARY: 18 valid hours, Stage III/IV", base)
run_x2("12 valid hours", build(12))
run_x2("20 valid hours", build(20))
run_x2("Drop the 10 to 20 Jan 2026 outage", base[~base["date_ist"].between("2026-01-10", "2026-01-20")])
run_x2("Delhi stations vs control cities", base[(base["group"] == "control") | (base["sub_area"] == "Delhi")])
run_x2("Exposure: Stage II or higher", base, "x2")
# stress test: PM2.5 rose far more than the gases on Stage III/IV days, so compare with equally polluted days (treated stations only)
dm = base[base["group"] == "treated"].groupby("date_ist")["pm25"].mean()
high = base[(base["group"] == "treated") & base["date_ist"].isin(dm[dm >= 150].index)]
run_x2("STRESS TEST (added after seeing results): treated stations, days with mean PM2.5 of 150 or more, no control cities", high, "x", fe="")
t2 = pd.DataFrame(x2)
t2.to_csv(os.path.join(TAB, "X2_tracers.csv"), index=False)
prim = t2[t2["Run"].str.startswith("PRIMARY")].set_index("Outcome")
sens_runs = [r for r in t2["Run"].unique() if not r.startswith(("PRIMARY", "STRESS")) and "Stage II or" not in r]
same = []
for r in sens_runs:
    s = t2[t2["Run"] == r].set_index("Outcome")
    same.append(all(np.sign(s.loc[o, "Effect (%)"]) == np.sign(prim.loc[o, "Effect (%)"]) for o in ("NO2 / PM2.5 (traffic)", "CO / PM2.5 (traffic)")))
n_, c_ = prim.loc["NO2 / PM2.5 (traffic)"], prim.loc["CO / PM2.5 (traffic)"]
if n_["Decision CI high"] < 0 and c_["Decision CI high"] < 0 and np.mean(same) >= .75:
    s2_ = "SUPPORTED"
elif n_["Decision CI low"] > 0 or c_["Decision CI low"] > 0:
    s2_ = "NOT SUPPORTED"
else:
    s2_ = "INCONCLUSIVE"
status.append(["X2 tracers after Stage III/IV", s2_,
               f"NO2/PM2.5 {n_['Effect (%)']:+.1f}% [{n_['Decision CI low']:+.1f}, {n_['Decision CI high']:+.1f}]; CO/PM2.5 {c_['Effect (%)']:+.1f}% [{c_['Decision CI low']:+.1f}, {c_['Decision CI high']:+.1f}]; same sign in {int(sum(same))} of {len(same)} sensitivity runs"])
fig, ax = plt.subplots(figsize=(8.5, 4.2))
forest(ax, [(r["Outcome"], r["Effect (%)"], r["Decision CI low"], r["Decision CI high"], i < 3) for i, (_, r) in enumerate(prim.reset_index().iterrows())])
ax.set_xlabel("Change on Stage III/IV days vs control cities (%), 95% decision interval")
ax.set_title("X2. Traffic and dust tracers on Stage III/IV days (Oct 2025 to Feb 2026, date effects)", fontsize=10, loc="left")
save_fig(fig, "X2_tracers_stage34")
# placebo: move the stage timeline by k days (same shift for every treated station) and refit
xd = base[base["group"] == "treated"].groupby("date_ist")["x"].max()
plc = []
for k in [-60, -45, -35, -30, -25, -20, -15, -12, 12, 15, 20, 25, 30, 35, 45, 60]:
    d = base.copy()
    sh = xd.reindex(d["date_ist"] + pd.Timedelta(days=k)).to_numpy()
    d["xs"] = np.where(d["group"] == "treated", np.nan_to_num(sh), 0.0)
    if d["xs"].sum() < 200:
        continue
    for col, lab in [("l_no2r", "NO2 / PM2.5"), ("l_cor", "CO / PM2.5"), ("l_pm10r", "PM10 / PM2.5")]:
        s_ = d.dropna(subset=[col])
        r_, _ = fit(f"{col} ~ xs + C(station_id) + C(date_ist)", s_, "date_ist")
        plc.append({"Shift (days)": k, "Outcome": lab, "Effect (%)": round(pct(r_, "xs")[0], 2), "Shifted exposure station-days": int(s_["xs"].sum())})
t_pl = pd.DataFrame(plc)
real = prim["Effect (%)"]
t_pl["Real effect (%)"] = t_pl["Outcome"].map({"NO2 / PM2.5": real["NO2 / PM2.5 (traffic)"], "CO / PM2.5": real["CO / PM2.5 (traffic)"], "PM10 / PM2.5": real["PM10 / PM2.5 (coarse dust share)"]})
t_pl.to_csv(os.path.join(TAB, "X2b_tracer_placebo_shifts.csv"), index=False)
fig, axs = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
for ax, lab in zip(axs, ["NO2 / PM2.5", "CO / PM2.5", "PM10 / PM2.5"]):
    v = t_pl[t_pl["Outcome"] == lab]
    ax.hist(v["Effect (%)"], bins=8, color="#BBBBBB", edgecolor="white")
    ax.axvline(v["Real effect (%)"].iloc[0], color=TREATED_C, lw=2.5, label="real timeline")
    ax.set_title(lab, fontsize=10); ax.set_xlabel("Effect of a shifted timeline (%)")
axs[0].set_ylabel("Number of shifts"); axs[0].legend(frameon=False, fontsize=8)
fig.suptitle("X2b. Placebo: the Stage III/IV timeline moved by 12 to 60 days, same model", fontsize=10, x=0.01, ha="left")
fig.tight_layout()
save_fig(fig, "X2b_tracer_placebo_shifts")
runs_log.append(["X2 (42 regression fits, 48 placebo-shift fits)", len(t2) + len(plc)])

# ============================ summary ============================
pd.DataFrame(status, columns=["Analysis", "Status by the pre-set rule", "Evidence"]).to_csv(os.path.join(TAB, "X_status.csv"), index=False)
pd.DataFrame(runs_log + [["Total", sum(r[1] for r in runs_log)]], columns=["Analysis", "Model fits"]).to_csv(os.path.join(TAB, "X_runs.csv"), index=False)
print("\n".join(f"{a}: {b} | {c}" for a, b, c in status))
print("reference winter estimate (should be 9.5):", round(winter_ref, 2))
