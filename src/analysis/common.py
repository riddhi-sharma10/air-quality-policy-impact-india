"""Shared helpers for the H2 analysis (GRAP events, interrupted time series, robustness).

Reads data/processed/final_dataset.parquet and builds one DAILY series per group (treated or control).
All dates are IST calendar dates of `hour_ist` (the START of the PM2.5 hour).

Rules (see docs/work_log/RB_2026-11-10_B1.md):
  * PM2.5 hours inside a network-wide outage (`network_outage`) are set to empty before any averaging.
  * A station-day is valid with at least MIN_VALID_HOURS valid PM2.5 hours.
  * A group-day is valid when at least MIN_STATION_SHARE of the group's stations have a valid station-day;
    its PM2.5 is the mean of the station-day means.
  * Weather is the mean over the group's station-hours (ERA5 nearest cell); rain is a daily total.
  * Fire is the previous-day upwind count (`n_up_nh_100km_45deg_lag1`), the same for every hour of a date.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "data" / "processed" / "final_dataset.parquet"
GRAP_HOURLY = ROOT / "data" / "processed" / "grap_hourly.csv"
GRAP_ORDERS = ROOT / "data" / "processed" / "grap_orders.csv"
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_FIGS = ROOT / "outputs" / "figures"

MIN_VALID_HOURS = 18
MIN_STATION_SHARE = 0.5
TREATED_COLOR = "#D55E00"   # fixed across every figure: treated = vermillion, control = blue
CONTROL_COLOR = "#0072B2"
SEED = 20261110

LOAD_COLS = ["station_id", "city", "sub_area", "group", "hour_ist", "pm25", "network_outage", "u10", "v10",
             "wind_speed", "t2m_c", "d2m_c", "sp_hpa", "blh_m", "tp_mm", "n_up_nh_100km_45deg_lag1",
             "n_nh_100km_lag1", "fire_day_status", "fire_is_nrt", "grap_stage", "grap_uncertain", "grap_inferred"]


def load_hourly(cols=LOAD_COLS):
    d = pd.read_parquet(FINAL, columns=cols)
    d["date"] = d["hour_ist"].dt.normalize()
    return d


def rh_from_t_td(t, td):
    """Relative humidity (%) from air and dewpoint temperature (deg C), Magnus formula."""
    a, b = 17.625, 243.04
    return 100.0 * np.exp(a * td / (b + td)) / np.exp(a * t / (b + t))


def station_days(d, min_valid_hours=MIN_VALID_HOURS):
    """One row per station and date: mean PM2.5 over valid (non-outage) hours, valid only with enough hours."""
    x = d[["station_id", "group", "city", "sub_area", "date", "pm25", "network_outage"]].copy()
    x.loc[x["network_outage"], "pm25"] = np.nan
    g = x.groupby(["station_id", "group", "city", "sub_area", "date"], observed=True)["pm25"]
    out = g.agg(["mean", "count"]).rename(columns={"mean": "pm25", "count": "n_valid_hours"}).reset_index()
    out.loc[out["n_valid_hours"] < min_valid_hours, "pm25"] = np.nan
    return out


def group_daily(d, group, stations=None, cities=None, min_valid_hours=MIN_VALID_HOURS, min_station_share=MIN_STATION_SHARE):
    """Daily series for a group ('treated' or 'control'), optionally restricted to `stations` or `cities`.

    Columns: pm25 (mean of station-day means), n_stations (valid), pm25_sem, weather means, fire, stage at 12:00,
    outage_hours (hours of the date with a network-wide outage)."""
    sub = d[d["group"] == group]
    if stations is not None:
        sub = sub[sub["station_id"].isin(stations)]
    if cities is not None:
        sub = sub[sub["city"].isin(cities)]
    n_total = sub["station_id"].nunique()
    sd = station_days(sub, min_valid_hours)
    g = sd.groupby("date")["pm25"]
    out = pd.DataFrame({"pm25": g.mean(), "n_stations": g.count(), "pm25_sd": g.std()})
    out["pm25_sem"] = out["pm25_sd"] / np.sqrt(out["n_stations"].clip(lower=1))
    bad = out["n_stations"] < np.ceil(min_station_share * n_total)
    out.loc[bad, ["pm25", "pm25_sem"]] = np.nan
    w = sub.assign(rh=rh_from_t_td(sub["t2m_c"], sub["d2m_c"])).groupby("date")
    wx = w[["u10", "v10", "wind_speed", "t2m_c", "d2m_c", "rh", "sp_hpa", "blh_m"]].mean()
    wx["tp_mm"] = w["tp_mm"].mean() * 24.0           # mean hourly rain x 24 = daily total (mm)
    fire = sub.groupby("date").agg(fire_up=("n_up_nh_100km_45deg_lag1", "mean"), fire_all100=("n_nh_100km_lag1", "mean"),
                                  fire_status=("fire_day_status", "first"), fire_is_nrt=("fire_is_nrt", "max"))
    noon = sub[sub["hour_ist"].dt.hour == 12].groupby("date")["grap_stage"].first().rename("stage_noon")
    maxs = sub.groupby("date")["grap_stage"].max().rename("stage_max")
    one = sub[sub["station_id"] == sub["station_id"].iloc[0]]
    outh = one.groupby("date")["network_outage"].sum().rename("outage_hours")
    unc = sub.groupby("date")["grap_uncertain"].max().rename("uncertain_day")
    inf = sub.groupby("date")["grap_inferred"].max().rename("inferred_day")
    res = out.join([wx, fire, noon, maxs, outh, unc, inf])
    res["log_pm25"] = np.log(res["pm25"].where(res["pm25"] > 0))
    res["log_fire"] = np.log1p(res["fire_up"])
    res["log_blh"] = np.log(res["blh_m"].clip(lower=10))
    res["rain_flag"] = (res["tp_mm"] > 0.1).astype(float)
    return res


LONG_OUTAGE_HOURS = 24   # a network-wide PM2.5 outage run of at least this many hours counts as a "long outage"


def outage_runs(d):
    """Runs of consecutive network-wide outage hours (the flag is the same for every station).

    Returns one row per run: start (first outage hour, IST), end (last outage hour), hours, and `long` (>= LONG_OUTAGE_HOURS).
    This is the corrected outage window: the long run in January 2026 is 10 Jan 17:00 to 20 Jan 18:00 IST (242 hours),
    not '11 to 20 Jan' as an earlier note said."""
    h = d.groupby("hour_ist")["network_outage"].agg(["min", "max"]).sort_index()
    if (h["min"] != h["max"]).any():
        raise ValueError("network_outage differs between stations in some hour; it should be network-wide")
    flag = h["max"].astype(bool)
    run_id = (flag != flag.shift(fill_value=False)).cumsum()
    runs = []
    for _, g in flag[flag].groupby(run_id[flag]):
        runs.append({"start": g.index[0], "end": g.index[-1], "hours": len(g)})
    out = pd.DataFrame(runs, columns=["start", "end", "hours"])
    out["long"] = out["hours"] >= LONG_OUTAGE_HOURS
    return out


def load_changes():
    """The 30 stage changes from grap_hourly.csv with the order information (date, time source)."""
    g = pd.read_csv(GRAP_HOURLY, parse_dates=["ts_ist"])
    prev = g["grap_stage"].shift(1)
    ch = g[(g["grap_stage"] != prev) & prev.notna()].copy()
    ch["stage_before"] = prev[ch.index].astype(int)
    ch["stage_after"] = ch["grap_stage"].astype(int)
    ch["direction"] = np.where(ch["stage_after"] > ch["stage_before"], "up", "down")
    ch["change_date"] = ch["ts_ist"].dt.normalize()
    ch = ch.rename(columns={"uncertain": "time_uncertain", "inferred": "stage_inferred"})
    return ch[["ts_ist", "change_date", "stage_before", "stage_after", "direction", "time_uncertain",
               "uncertain_reason", "stage_inferred"]].reset_index(drop=True)


def finish_figure(fig, name, title_note=""):
    """Save a figure as PNG (300 dpi) and SVG in outputs/figures."""
    OUT_FIGS.mkdir(parents=True, exist_ok=True)
    plt.rcParams["svg.hashsalt"] = "h2-analysis"            # fixed, so a rerun writes an identical SVG
    fig.savefig(OUT_FIGS / f"{name}.png", dpi=300, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(OUT_FIGS / f"{name}.svg", bbox_inches="tight", metadata={"Date": None, "Creator": None})


def register_figure(fig_id, name, script, inputs, author="RB", status="draft, not yet peer reviewed"):
    """Add or update a row in outputs/figure_registry.csv."""
    OUT_TABLES.parent.mkdir(parents=True, exist_ok=True)
    path = OUT_TABLES.parent / "figure_registry.csv"
    cols = ["figure_id", "file", "script", "input", "date_made", "author", "reviewer", "status"]
    row = {"figure_id": fig_id, "file": f"outputs/figures/{name}.png", "script": script, "input": inputs,
           "date_made": pd.Timestamp.today().strftime("%Y-%m-%d"), "author": author, "reviewer": "", "status": status}
    reg = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=cols)
    reg = reg[reg["figure_id"] != fig_id]
    pd.concat([reg, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False)
