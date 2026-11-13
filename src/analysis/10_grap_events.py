"""B1: GRAP stage changes, episodes and the primary event set (rules frozen in docs/work_log/RB_2026-11-10_B1.md).

Writes outputs/tables/grap_changes.csv (the 30 stage changes) and outputs/tables/grap_events.csv (episodes), and figure F3.

Usage: python src/analysis/10_grap_events.py [--min-gap-before 7]
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

MERGE_HOURS = 24         # consecutive changes this close (or closer) are one episode
PRE_DAYS_FIT = 60        # fitting window before the episode
MIN_PRE_VALID = 40       # valid days needed in the 60
GAP_BEFORE = 7           # primary: no other change in the 7 days before
GAP_AFTER = 3            # primary: no other change in days 1 to 3 after the last change
OUTAGE_BEFORE, OUTAGE_AFTER = 14, 7


def attach_orders(ch):
    """Join the order's time source (meeting, pib_posted, assumed) and verification to each change."""
    o = pd.read_csv(c.GRAP_ORDERS, parse_dates=["order_date"])
    o = o[o["action"].isin(["invoke", "revoke"])].copy()
    o["stage"] = o["stage"].astype(int)
    out = ch.copy()
    keys = []
    for _, r in out.iterrows():
        stage = r["stage_after"] if r["direction"] == "up" else r["stage_before"]
        action = "invoke" if r["direction"] == "up" else "revoke"
        keys.append((r["change_date"], action, stage))
    m = []
    for k in keys:
        hit = o[(o["order_date"] == k[0]) & (o["action"] == k[1]) & (o["stage"] == k[2])]
        m.append(hit.iloc[0] if len(hit) == 1 else None)
    out["order_date"] = [x["order_date"] if x is not None else pd.NaT for x in m]
    out["time_source"] = [x["time_source"] if x is not None else None for x in m]
    out["verification"] = [x["verification"] if x is not None else None for x in m]
    out["order_serial"] = [x["order_serial"] if x is not None else None for x in m]
    return out


def make_episodes(ch):
    ch = ch.sort_values("ts_ist").reset_index(drop=True)
    gap = ch["ts_ist"].diff().dt.total_seconds() / 3600.0
    ch["episode_id"] = (gap.isna() | (gap > MERGE_HOURS)).cumsum()
    rows = []
    for eid, g in ch.groupby("episode_id"):
        first, last = g.iloc[0], g.iloc[-1]
        rows.append({"episode_id": int(eid), "ts_first": first["ts_ist"], "ts_last": last["ts_ist"],
                     "date_first": first["change_date"], "date_last": last["change_date"], "n_changes": len(g),
                     "stage_before": int(first["stage_before"]), "stage_after": int(last["stage_after"]),
                     "direction": "up" if last["stage_after"] > first["stage_before"] else "down",
                     "time_uncertain": bool(g["time_uncertain"].any()),
                     "time_source": ";".join(g["time_source"].fillna("?").astype(str))})
    return ch, pd.DataFrame(rows)


def long_outage_text(runs, start, end):
    """Long outage runs (>= 24 h) that overlap [start, end): text for the table, empty when none."""
    hit = runs[runs["long"] & (runs["start"] < end) & (runs["end"] + pd.Timedelta(hours=1) > start)]
    return "; ".join(f"{r.start:%Y-%m-%d %H:%M} to {r.end:%Y-%m-%d %H:%M} ({r.hours} h)" for r in hit.itertuples())


def context_and_flags(ep, treated, control, gap_before=GAP_BEFORE, runs=None):
    """Context columns and the primary / relaxed flags for every episode.
    `runs` (common.outage_runs) adds the long-outage columns."""
    out = []
    ts_list = ep["ts_first"].tolist()
    for i, r in ep.iterrows():
        d0, dl = r["date_first"], r["date_last"]
        prev_ts = ts_list[i - 1] if i > 0 else None
        # note: episodes are separated by more than 24 h, so the neighbours are the previous and next episode
        next_ts = ep["ts_first"].iloc[i + 1] if i + 1 < len(ep) else None
        prev_last = ep["ts_last"].iloc[i - 1] if i > 0 else None
        days_prev = (r["ts_first"] - prev_last).total_seconds() / 86400 if prev_last is not None else np.nan
        days_next = (next_ts - r["ts_last"]).total_seconds() / 86400 if next_ts is not None else np.nan
        pre7 = treated.loc[d0 - pd.Timedelta(days=7): d0 - pd.Timedelta(days=1)]
        pre60 = treated.loc[d0 - pd.Timedelta(days=PRE_DAYS_FIT): d0 - pd.Timedelta(days=1)]
        post3 = treated.loc[dl + pd.Timedelta(days=1): dl + pd.Timedelta(days=3)]
        post47 = treated.loc[dl + pd.Timedelta(days=4): dl + pd.Timedelta(days=7)]
        win = treated.loc[d0 - pd.Timedelta(days=OUTAGE_BEFORE): dl + pd.Timedelta(days=OUTAGE_AFTER)]
        ctl3 = control.loc[dl + pd.Timedelta(days=1): dl + pd.Timedelta(days=3)]
        rec = {"pm25_pre7_mean": pre7["pm25"].mean(), "valid_days_pre7": int(pre7["pm25"].notna().sum()),
               "valid_days_pre60": int(pre60["pm25"].notna().sum()), "valid_days_post1_3": int(post3["pm25"].notna().sum()),
               "valid_days_post4_7": int(post47["pm25"].notna().sum()),
               "outage_hours_window": int(win["outage_hours"].sum()),
               "long_outage_in_window": (long_outage_text(runs, d0 - pd.Timedelta(days=OUTAGE_BEFORE), dl + pd.Timedelta(days=OUTAGE_AFTER + 1))
                                         if runs is not None else ""),
               "days_since_previous_episode": days_prev, "days_to_next_episode": days_next,
               "pre7_wind_speed": pre7["wind_speed"].mean(), "pre7_blh_m": pre7["blh_m"].mean(),
               "pre7_rain_mm": pre7["tp_mm"].mean(), "control_pm25_post1_3_mean": ctl3["pm25"].mean(),
               "pm25_post1_3_mean_RAW_DESCRIPTIVE": post3["pm25"].mean()}
        reasons, reasons_relaxed = [], []
        if r["direction"] != "up":
            reasons.append("not an invocation")
        if r["stage_after"] < 2:
            reasons.append("stage after < 2")
        if not np.isnan(days_prev) and days_prev < gap_before:
            reasons.append(f"another change {days_prev:.1f} d before (< {gap_before})")
        if not np.isnan(days_prev) and days_prev < 3:
            reasons_relaxed.append(f"another change {days_prev:.1f} d before (< 3)")
        if not np.isnan(days_next) and days_next < GAP_AFTER + 1:
            reasons.append(f"another change {days_next:.1f} d after the last change (< {GAP_AFTER + 1})")
            reasons_relaxed.append(f"another change {days_next:.1f} d after the last change")
        # Amendment A1: outage hours in the window are reported (outage_hours_window) but are not an exclusion;
        # missing data is handled by the valid-day rules below.
        if rec["valid_days_pre60"] < MIN_PRE_VALID:
            reasons.append(f"only {rec['valid_days_pre60']} valid days in the 60 before (< {MIN_PRE_VALID})")
            reasons_relaxed.append("too few valid pre days")
        if rec["valid_days_post1_3"] < 3:
            reasons.append(f"only {rec['valid_days_post1_3']} of 3 post days valid")
        if rec["valid_days_post1_3"] < 2:
            reasons_relaxed.append("fewer than 2 of 3 post days valid")
        if r["direction"] != "up" or r["stage_after"] < 2:
            reasons_relaxed += ["not an invocation to stage 2 or higher"]
        rec["usable_primary"] = len(reasons) == 0
        rec["exclusion_reason_primary"] = "; ".join(reasons)
        rec["usable_relaxed"] = len(reasons_relaxed) == 0
        rec["exclusion_reason_relaxed"] = "; ".join(reasons_relaxed)
        out.append(rec)
    return pd.concat([ep.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def figure_f3(treated, control, events, changes):
    """F3: daily mean PM2.5 (treated and control), GRAP stage strip, outage periods."""
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(13, 6.2), sharex=True, gridspec_kw={"height_ratios": [4, 0.9], "hspace": 0.06})
    for df, col, lab in [(treated, c.TREATED_COLOR, "Treated (Delhi-NCR)"), (control, c.CONTROL_COLOR, "Control (Patna, Lucknow, Kanpur)")]:
        s = df["pm25"]
        ax.plot(s.index, s.values, color=col, lw=1.2, label=f"{lab}")
        ax.fill_between(s.index, (s - 1.96 * df["pm25_sem"]).values, (s + 1.96 * df["pm25_sem"]).values, color=col, alpha=0.18, lw=0)
    out = treated["outage_hours"] >= 12
    # shade runs of days with at least 12 outage hours
    runs, start = [], None
    for d, flag in out.items():
        if flag and start is None:
            start = d
        if not flag and start is not None:
            runs.append((start, d)); start = None
    if start is not None:
        runs.append((start, out.index[-1] + pd.Timedelta(days=1)))
    for i, (a, b) in enumerate(runs):
        ax.axvspan(a, b, color="0.6", alpha=0.35, lw=0, label="Network-wide outage (12 h or more a day)" if i == 0 else None)
    ax.set_ylim(0, 470)
    prim = events[events["usable_primary"]].reset_index(drop=True)
    for i, r in prim.iterrows():
        ax.axvline(r["date_first"], color="k", ls="--", lw=1.0)
        side = "right" if i % 2 == 0 else "left"      # first label left of its line, second right of its line
        off = -5 if side == "right" else 5
        ax.annotate(f"Primary event: stage {r['stage_before']}→{r['stage_after']}\n{r['date_first']:%d %b %Y}", (r["date_first"], 465),
                    xytext=(off, -2), textcoords="offset points", va="top", ha=side, fontsize=8)
    ax.set_ylabel("PM2.5 (µg/m³), daily mean")
    ax.set_title("Daily mean PM2.5, treated versus control stations, with GRAP stage (19 Feb 2025 to 30 Sep 2026, IST)", fontsize=11)
    ax.legend(loc="upper left", fontsize=8, ncol=1, frameon=True)
    ax.grid(alpha=0.25)
    stage = treated["stage_noon"]
    cmap = {0: "#FFFFFF", 1: "#FFF2AE", 2: "#FDCC8A", 3: "#FC8D59", 4: "#B30000"}
    ax2.step(stage.index, stage.values, where="post", color="k", lw=0.8)
    for st, col in cmap.items():
        ax2.fill_between(stage.index, 0, 4, where=(stage.values == st), color=col, step="post", alpha=0.9, lw=0)
    ax2.set_yticks([0, 1, 2, 3, 4])
    ax2.set_ylabel("GRAP stage\n(at 12:00 IST)")
    ax2.set_ylim(0, 4)
    ax2.set_xlabel("Date (IST). Control cities are outside the NCR and have no GRAP stage; stage shown is the NCR stage.")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.text(0.01, -0.02, f"Band: 95% interval across stations that day (n = {int(treated['n_stations'].median())} treated and {int(control['n_stations'].median())} control stations, median). "
             "Gaps = fewer than half of the stations valid or outage. Source: final_dataset.parquet; script src/analysis/10_grap_events.py.", fontsize=7)
    c.finish_figure(fig, "F03_pm25_grap_timeline")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-gap-before", type=int, default=GAP_BEFORE)
    a = ap.parse_args()
    c.OUT_TABLES.mkdir(parents=True, exist_ok=True)
    d = c.load_hourly()
    treated, control = c.group_daily(d, "treated"), c.group_daily(d, "control")
    ch = attach_orders(c.load_changes())
    ch, ep = make_episodes(ch)
    runs = c.outage_runs(d)
    ev = context_and_flags(ep, treated, control, a.min_gap_before, runs)
    ev["overlaps_long_outage"] = ev["long_outage_in_window"].astype(str).str.len() > 0

    print(f"stage changes: {len(ch)} (up {(ch.direction == 'up').sum()}, down {(ch.direction == 'down').sum()}); episodes: {len(ev)}")
    checks = []
    checks.append(("30 stage changes", len(ch) == 30))
    checks.append(("every change matched to exactly one order row", ch["order_date"].notna().all()))
    checks.append(("exact times only for meeting-time changes", set(ch.loc[~ch["time_uncertain"], "time_source"]) == {"meeting"}))
    checks.append(("episode count equals changes minus merged changes", len(ev) == 30 - int((ev["n_changes"] - 1).sum())))
    n_out = int(d.loc[d["station_id"] == d["station_id"].iloc[0], "network_outage"].sum())
    checks.append((f"outage hours in the table = 928 (found {n_out})", n_out == 928))
    checks.append(("outage runs add up to the 928 outage hours", int(runs["hours"].sum()) == 928))
    jan = runs[(runs["start"] >= "2026-01-01") & (runs["start"] < "2026-02-01") & runs["long"]]
    checks.append(("the January 2026 long outage is 10 Jan 17:00 to 20 Jan 18:00 IST (242 h)",
                   len(jan) == 1 and jan.iloc[0]["start"] == pd.Timestamp("2026-01-10 17:00") and jan.iloc[0]["end"] == pd.Timestamp("2026-01-20 18:00")
                   and jan.iloc[0]["hours"] == 242))
    hr = d.loc[d["station_id"] == d["station_id"].iloc[0], ["hour_ist", "grap_stage", "network_outage"]]
    stage3_hours = int((hr["grap_stage"] >= 3).sum())
    stage3_out = int(((hr["grap_stage"] >= 3) & hr["network_outage"]).sum())
    print(f"stage 3 or 4 hours: {stage3_hours}; of these inside a network outage: {stage3_out} ({100 * stage3_out / stage3_hours:.1f}%)")
    for lab, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {lab}")
    if not all(ok for _, ok in checks):
        sys.exit("a check failed; nothing written")

    ch.to_csv(c.OUT_TABLES / "grap_changes.csv", index=False)
    ev.to_csv(c.OUT_TABLES / "grap_events.csv", index=False)
    runs.assign(start=runs["start"].dt.strftime("%Y-%m-%d %H:%M"), end=runs["end"].dt.strftime("%Y-%m-%d %H:%M")).to_csv(
        c.OUT_TABLES / "outage_runs.csv", index=False)
    print(f"primary events (provisional until MK confirms B1.4): {int(ev['usable_primary'].sum())}; relaxed: {int(ev['usable_relaxed'].sum())}")
    show = ev[["episode_id", "date_first", "stage_before", "stage_after", "direction", "usable_primary", "usable_relaxed",
               "exclusion_reason_primary"]]
    print(show.to_string(index=False))
    figure_f3(treated, control, ev, ch)
    c.register_figure("F3", "F03_pm25_grap_timeline", "src/analysis/10_grap_events.py", "final_dataset.parquet, grap_hourly.csv")
    print("wrote outputs/tables/grap_changes.csv, grap_events.csv and figure F03")


if __name__ == "__main__":
    main()
