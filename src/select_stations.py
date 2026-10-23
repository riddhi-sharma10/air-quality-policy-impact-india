"""Choose the final station list from window coverage (run openaq_station_coverage.py first).

Rules, applied in this order (each decision is written to data/processed/station_selection_log.csv):
  1. Close pairs (pair_flag): keep the member with more PM2.5+PM10 hours in the window, drop the other.
     (Lodhi Road 5634 vs 11607; Gurugram 10921 vs 10900.)
  2. Drop stations with PM2.5 present in fewer than MIN_PCT % of the 14,136 window hours.
  3. Keep stations without PM10 (>= MIN_PCT) but flag them pm10_available = False.
The other IDs of R K Puram and Anand Vihar (5639, 7044, 5509, 10487) stopped reporting in 2018-2022,
before the window, so they never enter the list.
AirNow 8118 is not part of this list; it stays a separate validation series.
Output: data/processed/stations_final.csv (stations.csv columns + coverage columns)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
MIN_PCT = 70.0

cov = pd.read_csv(PROC / "station_coverage.csv")
stations = pd.read_csv(PROC / "stations.csv", encoding="utf-8-sig")
cov = cov[cov["id"].isin(stations["id"])].set_index("id")
log = []

drop = set()
for sid, partner in stations.loc[stations["pair_flag"].notna(), ["id", "pair_flag"]].itertuples(index=False):
    partner = int(partner)
    if sid < partner:  # handle each pair once
        keep, lose = (sid, partner) if cov.loc[sid, "hours_both"] >= cov.loc[partner, "hours_both"] else (partner, sid)
        drop.add(lose)
        log.append({"id": lose, "decision": "drop", "reason": f"close pair with {keep}; fewer PM2.5+PM10 hours "
                    f"({cov.loc[lose, 'hours_both']} vs {cov.loc[keep, 'hours_both']})"})
for sid in cov.index:
    if sid not in drop and cov.loc[sid, "pct_pm25"] < MIN_PCT:
        drop.add(sid)
        log.append({"id": sid, "decision": "drop", "reason": f"PM2.5 coverage {cov.loc[sid, 'pct_pm25']}% < {MIN_PCT}%"})
for sid in cov.index:
    if sid not in drop and cov.loc[sid, "pct_pm10"] < MIN_PCT:
        log.append({"id": sid, "decision": "keep, PM2.5 only",
                    "reason": f"PM10 coverage {cov.loc[sid, 'pct_pm10']}% < {MIN_PCT}%"})

final = stations[~stations["id"].isin(drop)].merge(
    cov[["hours_pm25", "hours_pm10", "hours_both", "pct_pm25", "pct_pm10", "pct_both"]].reset_index(), on="id")
final["pm10_available"] = final["pct_pm10"] >= MIN_PCT
final.to_csv(PROC / "stations_final.csv", index=False)
pd.DataFrame(log).to_csv(PROC / "station_selection_log.csv", index=False)
print(pd.DataFrame(log).to_string(index=False))
print(final.groupby(["group", "sub_area"]).size().to_string())
print(f"{len(stations)} candidates -> {len(final)} kept")
