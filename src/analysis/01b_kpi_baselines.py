"""Baseline values of the report KPIs (task M1; see report/01_stakeholder_and_kpis.md).

Reads data/processed/final_dataset.parquet and writes outputs/tables/T00_kpi_baselines.csv.
Every number quoted in the KPI page comes from this file.

Rules (fixed in advance, plan sections 5.1 and R4):
- A valid hour has PM2.5 present and is not a network outage hour (`network_outage` False).
- A valid station-day has at least 18 valid hours (IST date).
- A group-day (treated or control) is the mean of its valid station-days and counts only when at least half of
  the group's stations have a valid day.
- Winter sample: 1 Oct 2025 to 28 Feb 2026.
Run:  python src/analysis/01b_kpi_baselines.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "processed" / "final_dataset.parquet"
OUT = ROOT / "outputs" / "tables" / "T00_kpi_baselines.csv"

MIN_VALID_HOURS = 18          # of 24
MIN_STATION_SHARE = 0.5       # of a group's stations
NAAQS_24H = 60.0              # ug/m3, India NAAQS 24-hour PM2.5 standard
WINTER = ("2025-10-01", "2026-02-28")
FULL = ("2025-02-19", "2026-09-30")
FIRE_SEASON = ("2025-10-01", "2025-11-30")
COLS = ["station_id", "group", "hour_ist", "pm25", "network_outage", "n_up_nh_100km_45deg_lag1", "n_nh_100km_lag1",
        "fire_day_status"]


def station_days(df):
    """One row per station and IST date with the mean of its valid hours and how many there were."""
    valid = df["pm25"].notna() & ~df["network_outage"]
    d = df.assign(date=df["hour_ist"].dt.normalize(), v=valid, pm=df["pm25"].where(valid))
    g = d.groupby(["station_id", "group", "date"], observed=True)
    sd = g.agg(valid_hours=("v", "sum"), pm25_mean=("pm", "mean")).reset_index()
    return sd[sd["valid_hours"] >= MIN_VALID_HOURS]


def group_days(sd, n_stations):
    """Group-day mean of valid station-days, kept when at least half of the group's stations are valid."""
    g = sd.groupby(["group", "date"], observed=True)["pm25_mean"].agg(["mean", "count"]).reset_index()
    g["n_group"] = g["group"].map(n_stations)
    return g[g["count"] >= MIN_STATION_SHARE * g["n_group"]].rename(columns={"mean": "pm25_group_mean"})


def main():
    df = pd.read_parquet(DATA, columns=COLS)
    n_st = df.drop_duplicates("station_id").groupby("group")["station_id"].nunique().to_dict()
    sd = station_days(df)
    gd = group_days(sd, n_st)
    rows = []

    def add(kpi, group, period, stat, value, n, unit, columns):
        rows.append(dict(kpi=kpi, group=group, period=period, statistic=stat, value=round(float(value), 2), n=int(n),
                         unit=unit, columns=columns))

    for pname, (a, b) in {"winter Oct 2025-Feb 2026": WINTER, "full window": FULL}.items():
        for grp in ("treated", "control"):
            x = gd[(gd["group"] == grp) & (gd["date"] >= a) & (gd["date"] <= b)]["pm25_group_mean"]
            add("KPI1 daily mean PM2.5", grp, pname, "mean of group-day means", x.mean(), len(x), "ug/m3 (days)", "pm25")
            add("KPI1 daily mean PM2.5", grp, pname, "median of group-day means", x.median(), len(x), "ug/m3 (days)", "pm25")
            add("KPI1 daily mean PM2.5", grp, pname, "95th percentile of group-day means", x.quantile(0.95), len(x), "ug/m3 (days)", "pm25")
            add("KPI2 days above 60 ug/m3", grp, pname, "share of valid days above 60", 100 * (x > NAAQS_24H).mean(), len(x), "% of days", "pm25")
            add("KPI2 days above 60 ug/m3", grp, pname, "number of days above 60", (x > NAAQS_24H).sum(), len(x), "days", "pm25")
            s = sd[(sd["group"] == grp) & (sd["date"] >= a) & (sd["date"] <= b)]["pm25_mean"]
            add("KPI2 days above 60 ug/m3", grp, pname, "share of valid station-days above 60", 100 * (s > NAAQS_24H).mean(), len(s), "% of station-days", "pm25")

    # KPI4 context: fire exposure of the treated stations in the burning season (previous-day values, not outage days)
    f = df[(df["group"] == "treated") & (df["hour_ist"] >= FIRE_SEASON[0]) & (df["hour_ist"] <= FIRE_SEASON[1] + " 23:00")]
    f = f[f["fire_day_status"] != "outage"].assign(date=lambda t: t["hour_ist"].dt.normalize())
    fd = f.groupby(["station_id", "date"], observed=True)[["n_up_nh_100km_45deg_lag1", "n_nh_100km_lag1"]].first().dropna()
    add("KPI4 fire exposure (context)", "treated", "Oct-Nov 2025", "mean upwind detections per station-day (100 km, 45 deg, previous day)",
        fd["n_up_nh_100km_45deg_lag1"].mean(), len(fd), "detections", "n_up_nh_100km_45deg_lag1")
    add("KPI4 fire exposure (context)", "treated", "Oct-Nov 2025", "max upwind detections in a station-day",
        fd["n_up_nh_100km_45deg_lag1"].max(), len(fd), "detections", "n_up_nh_100km_45deg_lag1")
    add("KPI4 fire exposure (context)", "treated", "Oct-Nov 2025", "share of station-days with at least one upwind detection",
        100 * (fd["n_up_nh_100km_45deg_lag1"] > 0).mean(), len(fd), "% of station-days", "n_up_nh_100km_45deg_lag1")
    add("KPI4 fire exposure (context)", "treated", "Oct-Nov 2025", "mean detections within 100 km, all directions (previous day)",
        fd["n_nh_100km_lag1"].mean(), len(fd), "detections", "n_nh_100km_lag1")

    # KPI5 data coverage (monitoring)
    n_hours = df["hour_ist"].nunique()
    out_h = df.drop_duplicates("hour_ist")["network_outage"].sum()
    add("KPI5 data coverage", "all", "full window", "station-hours with valid PM2.5 (present and not outage)",
        100 * (df["pm25"].notna() & ~df["network_outage"]).mean(), len(df), "% of station-hours", "pm25, network_outage")
    add("KPI5 data coverage", "all", "full window", "network outage hours", out_h, n_hours, "hours", "network_outage")
    add("KPI5 data coverage", "all", "full window", "share of hours that are network outage", 100 * out_h / n_hours, n_hours, "% of hours", "network_outage")
    for grp in ("treated", "control"):
        x = df[df["group"] == grp]
        add("KPI5 data coverage", grp, "full window", "station-hours with valid PM2.5",
            100 * (x["pm25"].notna() & ~x["network_outage"]).mean(), len(x), "% of station-hours", "pm25, network_outage")
    add("KPI5 data coverage", "all", "full window", "valid station-days (at least 18 valid hours), share of all station-days",
        100 * len(sd) / (df["station_id"].nunique() * (n_hours // 24)), df["station_id"].nunique() * (n_hours // 24), "% of station-days", "pm25, network_outage")

    res = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)
    pd.set_option("display.width", 220, "display.max_colwidth", 80)
    print(res.drop(columns="columns").to_string(index=False))
    print(f"\nwritten {OUT}")


if __name__ == "__main__":
    main()
