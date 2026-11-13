"""G4: formal status of H1 and H2 by the pre-set rules (plan section 5.4).

Written by someone who did not run the models: this script only READS result tables and re-evaluates each criterion with its own
definitions (recorded before the run in docs/work_log/ma_2026-11-13_G4.md). Nothing is typed by hand; the report text is generated.

Inputs (outputs/tables or --tables-dir): T04d, T04e, T04g (H1, MK); T06a, T06e, T06f, T06g (H2, RB); T07a (MK's provisional label, compared only).
Outputs: outputs/tables/T07_hypothesis_status.csv and report/09_hypothesis_status.md
Run:  python src/analysis/20_g4_status.py [--tables-dir DIR]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SAME_SIGN_MIN = 0.75              # plan 5.4
LOWER_TAIL = 0.10                 # "lower tail of the placebo distribution" = at or below the 10th percentile (RB's frozen rule in B2)
MEANINGFUL_PCT = 10.0             # a fall of 10% or more is "a meaningful effect" (RB's frozen rule in B2)
H1_EXCLUDED = ("Primary (A)", "Cluster by station only", "Placebo: NEXT day", "Placebo: fires permuted")


def read(d, name):
    return pd.read_csv(Path(d) / f"{name}.csv")


def h1_rows(tables):
    reg = read(tables, "T04g_h1_robustness")
    pred = read(tables, "T04d_h1_prediction").set_index("model")
    prov = read(tables, "T07a_h1_status_inputs").iloc[0]
    primary = reg[reg["check"].str.startswith("Primary (A)")].iloc[0]
    checks = reg[~reg["check"].str.startswith(H1_EXCLUDED)]
    same = int((np.sign(checks["pct_per_unit"]) == np.sign(primary["pct_per_unit"])).sum())
    opposite = checks.loc[np.sign(checks["pct_per_unit"]) != np.sign(primary["pct_per_unit"]), "check"].tolist()
    excl0 = bool(primary["pct_lo"] > 0 or primary["pct_hi"] < 0)
    wrong_side = bool(primary["pct_hi"] < 0)
    share = same / len(checks)
    fire, weather = pred.loc["Weather + upwind fire"], pred.loc["Weather only"]
    beats = bool(fire["rmse_ugm3"] < weather["rmse_ugm3"])
    ruled_out = bool(primary["pct_hi"] < MEANINGFUL_PCT and primary["pct_lo"] > -MEANINGFUL_PCT)   # CI inside +-10%: a meaningful effect is ruled out
    station_only = reg[reg["check"].str.startswith("Cluster by station only")].iloc[0]
    exp = read(tables, "T04e_h1_expanding_window")
    w = exp.pivot_table(index="test_month", columns="model", values="rmse_ugm3")
    months_better = int((w["Weather + upwind fire"] < w["Weather only"]).sum())
    crit = [
        ("H1", "Primary coefficient > 0 with 95% CI excluding 0",
         f"{primary['pct_per_unit']:+.1f}% per +10 upwind detections, 95% CI [{primary['pct_lo']:+.1f}, {primary['pct_hi']:+.1f}] (two-way cluster, {int(primary['n_days'])} days, {int(primary['n_stations'])} stations)",
         excl0 and primary["pct_lo"] > 0, "T04g row Primary (A)"),
        ("H1", "Same sign in at least 75% of robustness checks",
         f"{same} of {len(checks)} ({100 * share:.0f}%); opposite sign: {'; '.join(opposite) if opposite else 'none'}",
         share >= SAME_SIGN_MIN, "T04g, 15 rows (exclusions in the work-log note)"),
        ("H1", "Fire model beats weather-only on the test period",
         f"RMSE {fire['rmse_ugm3']:.2f} vs {weather['rmse_ugm3']:.2f} ug/m3 ({100 * (1 - fire['rmse_ugm3'] / weather['rmse_ugm3']):.2f}% lower); lower in {months_better} of {len(w)} expanding-window months",
         beats, "T04d, T04e"),
        ("H1", "Not-supported test: CI on the wrong side of 0",
         f"upper limit {primary['pct_hi']:+.1f}%", wrong_side, "T04g"),
        ("H1", f"Not-supported test: CI rules out an effect of +-{MEANINGFUL_PCT:.0f}%",
         f"CI [{primary['pct_lo']:+.1f}, {primary['pct_hi']:+.1f}] is {'inside' if ruled_out else 'wider than'} +-{MEANINGFUL_PCT:.0f}%", ruled_out, "T04g"),
    ]
    supported = excl0 and primary["pct_lo"] > 0 and share >= SAME_SIGN_MIN and beats
    status = "SUPPORTED" if supported else ("NOT SUPPORTED" if (wrong_side or ruled_out) else "INCONCLUSIVE")
    notes = [f"With standard errors clustered by station only, the CI is [{station_only['pct_lo']:+.1f}, {station_only['pct_hi']:+.1f}] and excludes 0; "
             "the pre-set primary is the two-way (station and date) cluster, which is the right one because days are strongly correlated and there are only "
             f"{int(primary['n_days'])} winter days. The label does not change after the fact.",
             f"Provisional label from MK (T07a): {prov['provisional_status']}; recomputed here: {status}."]
    return status, crit, notes


def h2_rows(tables):
    ev = read(tables, "T06a_h2_events")
    rob = read(tables, "T06e_h2_robustness")
    summ = read(tables, "T06f_h2_robustness_summary")
    power = read(tables, "T06g_h2_power").set_index("true_effect_pct")
    prim = ev[ev["primary"].astype(bool)]
    adequate = prim[~prim["weak_counterfactual"].astype(bool) & (prim["status"] == "ok")]
    n_adequate = len(adequate)
    if n_adequate >= 2:
        w = 1 / adequate["w1_3_se_log"] ** 2
        pooled_log = float((w * adequate["w1_3_effect_log"]).sum() / w.sum())
        se = float(np.sqrt(1 / w.sum()))
        pooled = (100 * (np.exp(pooled_log) - 1), 100 * (np.exp(pooled_log - 1.96 * se) - 1), 100 * (np.exp(pooled_log + 1.96 * se) - 1))
        pooled_txt = f"pooled {pooled[0]:+.0f}% [{pooled[1]:+.0f}, {pooled[2]:+.0f}] from {n_adequate} events"
        pooled_ok = pooled[2] < 0
    else:
        pooled = None
        pooled_ok = False
        e = adequate.iloc[0] if n_adequate else None
        pooled_txt = (f"no pooled estimate: {n_adequate} of {len(prim)} primary events has an adequate counterfactual (CV R2 >= 0.40); "
                      + (f"that event ({e['date']}) shows {e['w1_3_pct']:+.0f}% [{e['w1_3_pct_lo']:+.0f}, {e['w1_3_pct_hi']:+.0f}]" if e is not None else ""))
    tail = adequate["placebo_share_at_or_below"] if n_adequate else prim["placebo_share_at_or_below"]
    in_tail = bool(len(tail) > 0 and (tail <= LOWER_TAIL).all())
    r = rob[rob["primary_event"].astype(bool) & ~rob["weak_counterfactual"].fillna(True).astype(bool) & rob["pct"].notna()
            & ~rob["check"].str.startswith("0 baseline")]
    neg = int((r["pct"] < 0).sum())
    share_neg = neg / len(r) if len(r) else float("nan")
    wrong_side_events = adequate[adequate["w1_3_pct_lo"] > 0]            # a rise whose interval excludes 0, among events with an adequate counterfactual
    ruled_out = bool(n_adequate and (adequate["w1_3_pct_lo"] > -MEANINGFUL_PCT).all())   # the interval does not reach a fall of 10% or more
    relaxed = ev[~ev["primary"].astype(bool)]
    crit = [
        ("H2", "Pooled day 1-3 actual minus predicted below 0, 95% CI excluding 0", pooled_txt, pooled_ok, "T06a (primary events, CV R2 >= 0.40)"),
        ("H2", "Real events in the lower tail of the placebo distribution (at or below the 10th percentile)",
         "share of placebo effects at or below the real one: " + ", ".join(f"{d}: {s:.2f}" for d, s in zip(prim["date"], prim["placebo_share_at_or_below"])),
         in_tail, "T06a"),
        ("H2", "Same sign (a fall) in at least 75% of robustness checks",
         f"{neg} of {len(r)} checks on the adequate primary event(s) are below 0 ({100 * share_neg:.0f}%)" if len(r) else "no adequate checks",
         bool(len(r) and share_neg >= SAME_SIGN_MIN), "T06e"),
        ("H2", "Not-supported test: an adequate primary event's CI excludes 0 on the wrong side (a rise)",
         ("none of the primary events with an adequate counterfactual" if wrong_side_events.empty else f"{', '.join(wrong_side_events['date'])}"), bool(not wrong_side_events.empty), "T06a"),
        ("H2", f"Not-supported test: CI rules out a fall of {MEANINGFUL_PCT:.0f}% or more",
         (f"adequate event CI [{adequate['w1_3_pct_lo'].min():+.0f}, {adequate['w1_3_pct_hi'].max():+.0f}]% reaches below -{MEANINGFUL_PCT:.0f}%, so a fall of that size is not ruled out" if n_adequate and not ruled_out else "a fall of that size is ruled out" if ruled_out else "no adequate event"),
         ruled_out, "T06a"),
    ]
    supported = pooled_ok and in_tail and bool(len(r) and share_neg >= SAME_SIGN_MIN)
    status = "SUPPORTED" if supported else ("NOT SUPPORTED" if (not wrong_side_events.empty) or ruled_out else "INCONCLUSIVE")
    notes = []
    if not relaxed.empty:
        for _, x in relaxed.iterrows():
            notes.append(f"The relaxed-set event {x['date']} (stage {x['sb']}->{x['sa']}) shows {x['w1_3_pct']:+.0f}% [{x['w1_3_pct_lo']:+.0f}, {x['w1_3_pct_hi']:+.0f}] "
                         "above the counterfactual. It is outside the primary set (one day before Diwali, and the control cities show a similar rise), so it is not used for the label.")
    p30, p50 = power.loc[-30, "share_interval_below_zero"], power.loc[-50, "share_interval_below_zero"]
    notes.append(f"Power (T06g, simulated): if GRAP really lowered PM2.5 by 30%, this design's interval would lie below zero in only {100 * p30:.0f}% of runs "
                 f"(50%: {100 * p50:.0f}%). A null result here is therefore not evidence of no effect.")
    notes.append("The wording rule applies: even a 'supported' label would mean 'consistent with an effect, conditional on the weather model', not that GRAP caused a change.")
    return status, crit, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables-dir", default=str(ROOT / "outputs" / "tables"))
    args = ap.parse_args()
    s1, c1, n1 = h1_rows(args.tables_dir)
    s2, c2, n2 = h2_rows(args.tables_dir)
    rows = pd.DataFrame([dict(hypothesis=h, criterion=c, observed=o, met=bool(m), source=s) for h, c, o, m, s in c1 + c2])
    rows["status"] = rows["hypothesis"].map({"H1": s1, "H2": s2})
    out_t = ROOT / "outputs" / "tables" / "T07_hypothesis_status.csv"
    out_t.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out_t, index=False)

    def block(h, status, crit, notes, title, claim):
        lines = [f"### {title}", "", f"**Status by the pre-set rules (plan 5.4): {status}.** {claim}", "",
                 "| Criterion | Observed | Met? | Source |", "| --- | --- | --- | --- |"]
        lines += [f"| {c} | {o} | {'yes' if m else 'no'} | {s} |" for hh, c, o, m, s in crit]
        lines += [""] + [f"- {n}" for n in notes] + [""]
        return lines

    md = ["# 9. Hypothesis status (gate G4)  `[BADIR: I]`", "",
          "Assigned by MA from the result tables, using the rules fixed before the results (plan section 5.4). MA did not run either model. "
          "Generated by `src/analysis/20_g4_status.py`; every number below is read from a table.", "",
          "| Hypothesis | Status |", "| --- | --- |",
          f"| H1: higher upwind fire counts on the previous day are associated with higher PM2.5, given the weather | **{s1}** |",
          f"| H2: PM2.5 falls after GRAP activation relative to the weather-and-fire prediction | **{s2}** |", ""]
    md += block("H1", s1, c1, n1, "H1 (fires)", "Plain words: the data lean towards a positive association, but one burning season is not enough to tell it apart from zero.")
    md += block("H2", s2, c2, n2, "H2 (GRAP)", "Plain words: there is no usable evidence of a fall after activation, and the design could not have detected a moderate one.")
    md += ["Reviewer: RS (pending). Wording check: no use of 'caused', 'reduced by' or 'proved'.", ""]
    out_m = ROOT / "report" / "09_hypothesis_status.md"
    out_m.parent.mkdir(exist_ok=True)
    out_m.write_text("\n".join(md), encoding="utf-8")
    print(rows.drop(columns="source").to_string(index=False, max_colwidth=110))
    print(f"\nH1 = {s1}; H2 = {s2}\nwritten {out_t} and {out_m}")


if __name__ == "__main__":
    main()
