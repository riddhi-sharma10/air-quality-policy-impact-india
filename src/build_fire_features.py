"""Build daily fire-detection features per station from the FIRMS VIIRS S-NPP files.

For every station, IST calendar date and radius (50, 100, 200 km) it counts the
detections and sums FRP, for two confidence sets (all; n+h only) crossed with three
periods (whole day; daytime pass only; night pass only).

Dates are IST (UTC+5:30): acq_date + acq_time are UTC, so a night pass at about
18:58-21:59 UTC (00:28-03:29 IST) falls on the NEXT IST date.

Usage:
  python src/build_fire_features.py                                   # all dates, data/processed/stations.csv
  python src/build_fire_features.py --stations data/processed/stations_window.csv \
         --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_daily.csv
All detections are read; only IST dates inside --start/--end get features.
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parent.parent
FIRMS_DIR = ROOT / "data" / "raw" / "firms"
PRODUCTS = {
    "archive": FIRMS_DIR / "fire_archive_SV-C2_829739.csv",
    "nrt": FIRMS_DIR / "fire_nrt_SV-C2_829739.csv",
}
DEFAULT_STATIONS = ROOT / "data" / "processed" / "stations.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "fire_features_daily.csv"
FIG_DIR = ROOT / "docs" / "figures"

RADII_KM = [50, 100, 200]
EARTH_RADIUS_KM = 6371.0088  # mean Earth radius
IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
EXPECTED_ROWS = 858_843  # archive 857,474 + nrt 1,369, from docs/provenance_log.csv
KEEP = ["latitude", "longitude", "acq_date", "acq_time", "confidence", "frp", "daynight", "version"]

CONFIDENCE_SETS = {"all": None, "nh": ["n", "h"]}
PERIODS = {"": None, "_day": "D", "_night": "N"}
COMBOS = [(c, p) for c in CONFIDENCE_SETS for p in PERIODS]
COUNT_COLS = [f"n_{c}{p}" for c, p in COMBOS]
FRP_COLS = [f"frp_{c}{p}" for c, p in COMBOS]

results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Plain numpy, independent of BallTree (used to verify it)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlmb = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


# 1. Read both files, align columns, build UTC and IST timestamps -----------------------
def load_detections():
    frames = []
    for product, path in PRODUCTS.items():
        df = pd.read_csv(path)
        df["product"] = product
        print(f"  {path.name}: {len(df):,} rows, {df.shape[1] - 1} columns")
        frames.append(df)
    # concat aligns on column names: the 'type' column exists only in the archive file and is
    # not needed, so keep only the columns both files share.
    det = pd.concat(frames, ignore_index=True)[KEEP + ["product"]]
    # acq_time is stored as an integer, so 06:20 arrives as 620 and the leading zero is lost.
    # zfill(4) turns 620 into "0620" so it parses as HHMM; without it 620 would read as 62:0.
    hhmm = det["acq_time"].astype(int).astype(str).str.zfill(4)
    det["utc"] = pd.to_datetime(det["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M")
    # IST is UTC + 5 h 30 min. Adding the offset BEFORE taking the date is what moves a
    # detection made at 19:30 UTC on the 5th to 01:00 on the 6th (IST).
    det["ist"] = det["utc"] + IST_OFFSET
    det["ist_date"] = det["ist"].dt.normalize()
    return det, sum(len(f) for f in frames)


def load_stations(path):
    st = pd.read_csv(path)
    st = st.rename(columns={"id": "station_id"})
    keep = [c for c in ("station_id", "latitude", "longitude", "city") if c in st.columns]
    st = st[keep].dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if st["station_id"].duplicated().any():
        sys.exit("duplicate station IDs in the station file")
    return st


# 2. Features ---------------------------------------------------------------------------
def build_features(det, stations, dates):
    n_dates = len(dates)
    date_idx = ((det["ist_date"] - dates[0]).dt.days).to_numpy()
    in_window = (date_idx >= 0) & (date_idx < n_dates)  # detections outside the window are skipped
    frp = det["frp"].to_numpy(dtype=float)
    daynight = det["daynight"].to_numpy()
    conf = det["confidence"].to_numpy()

    masks = {}
    for (c, p) in COMBOS:
        m = in_window.copy()
        if CONFIDENCE_SETS[c] is not None:
            m &= np.isin(conf, CONFIDENCE_SETS[c])
        if PERIODS[p] is not None:
            m &= daynight == PERIODS[p]
        masks[(c, p)] = m

    # BallTree with the haversine metric works on angles in RADIANS, not degrees, and returns
    # distances as an angle in radians. So the (lat, lon) of every point must be converted to
    # radians, and the search radius too: a distance in km divided by the Earth's radius is
    # exactly the angle (in radians) that distance subtends at the Earth's centre.
    tree = BallTree(np.radians(det[["latitude", "longitude"]].to_numpy()), metric="haversine")
    st_rad = np.radians(stations[["latitude", "longitude"]].to_numpy())
    # One query at the largest radius; the smaller radii are subsets of it by distance.
    ind, dist = tree.query_radius(st_rad, r=max(RADII_KM) / EARTH_RADIUS_KM, return_distance=True)

    frames = []
    for i, sid in enumerate(stations["station_id"]):
        idx, dkm = ind[i], dist[i] * EARTH_RADIUS_KM  # back from radians to km
        for radius in RADII_KM:
            sel = idx[dkm <= radius]
            block = {"station_id": sid, "ist_date": dates, "radius_km": radius}
            for (c, p), cnt_col, frp_col in zip(COMBOS, COUNT_COLS, FRP_COLS):
                s = sel[masks[(c, p)][sel]]
                block[cnt_col] = np.bincount(date_idx[s], minlength=n_dates)
                block[frp_col] = np.bincount(date_idx[s], weights=frp[s], minlength=n_dates)
            frames.append(pd.DataFrame(block))
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", type=Path, default=DEFAULT_STATIONS, help="station CSV with id, latitude, longitude")
    ap.add_argument("--start", help="first IST date to compute (default: first date in the data)")
    ap.add_argument("--end", help="last IST date to compute (default: last date in the data)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output CSV")
    ap.add_argument("--spot-station", type=int, help="station_id for the spot check")
    ap.add_argument("--spot-date", help="IST date for the spot check")
    args = ap.parse_args()

    print("Reading detections")
    det, n_raw = load_detections()
    stations = load_stations(args.stations)
    print(f"  stations: {len(stations)} from {args.stations}")

    span_start = pd.Timestamp(det["acq_date"].min())
    span_end = pd.Timestamp(det["acq_date"].max()) + pd.Timedelta(days=1)
    # Default window = the IST dates fully inside the downloaded UTC span (the first and last IST
    # date of the raw data are partial days: they start before / end after the files do).
    first_full = (span_start + IST_OFFSET).ceil("D")
    last_full = (span_end - pd.Timedelta(days=1) + IST_OFFSET).floor("D")
    start = pd.Timestamp(args.start) if args.start else first_full
    end = pd.Timestamp(args.end) if args.end else last_full
    window = pd.date_range(start, end, freq="D")

    print("\nChecks (inputs)")
    # IST date d spans UTC [d 00:00 - 5:30, d+1 00:00 - 5:30). The downloaded files must cover that
    # whole span for the first and last window date, otherwise those dates would be partly empty.
    need_start, need_end = start - IST_OFFSET, end + pd.Timedelta(days=1) - IST_OFFSET
    print(f"  window {start.date()} to {end.date()} (IST) needs UTC {need_start} to {need_end}; "
          f"files cover UTC {span_start} to {span_end}")
    check("input covers the window completely at both ends", span_start <= need_start and need_end <= span_end)

    # Dates with no detection anywhere in the file are MISSING (no usable pass or an outage), not zero.
    totals_by_date = det.groupby("ist_date").size().reindex(window, fill_value=0)
    missing_dates = totals_by_date.index[totals_by_date == 0]

    # is_nrt = True from the first IST date that contains any NRT detection onwards. That date is
    # 2026-07-01: IST 2026-06-30 = UTC 06-29 18:30 .. 06-30 18:30 (archive only), while IST 2026-07-01
    # = UTC 06-30 18:30 .. 07-01 18:30 mixes one archive night pass with NRT rows, so it is flagged.
    # Dates after it are flagged even if they have no detections, because their (missing) data
    # would come from the preliminary product too.
    nrt_first_date = det.loc[det["product"] == "nrt", "ist_date"].min()

    print("\nComputing features")
    feats = build_features(det, stations, window)

    # Missing dates become NaN (unknown) instead of 0 (known: no fire near the station).
    is_missing = feats["ist_date"].isin(missing_dates)
    for col in COUNT_COLS + FRP_COLS:
        feats[col] = feats[col].astype(float).mask(is_missing)
    for col in COUNT_COLS:
        feats[col] = feats[col].astype("Int64")
    feats["is_nrt"] = feats["ist_date"] >= nrt_first_date
    day_start_utc = feats["ist_date"] - IST_OFFSET
    feats["partial_day"] = (day_start_utc < span_start) | (day_start_utc + pd.Timedelta(days=1) > span_end)
    feats = feats[["station_id", "ist_date", "radius_km"] + COUNT_COLS + FRP_COLS + ["is_nrt", "partial_day"]]
    feats = feats.sort_values(["station_id", "radius_km", "ist_date"]).reset_index(drop=True)

    # Write
    out = feats.copy()
    out["ist_date"] = out["ist_date"].dt.strftime("%Y-%m-%d")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print("\nSummary")
    print(f"  wrote {args.out}: {len(out):,} rows "
          f"({feats['station_id'].nunique()} stations x {feats['ist_date'].nunique()} IST dates x {len(RADII_KM)} radii)")
    print(f"  window {window[0].date()} to {window[-1].date()} ({len(window)} days)")
    print(f"  partial IST days inside the window: {int(feats['partial_day'].groupby(feats['ist_date']).first().sum())}")
    print(f"  dates flagged is_nrt: {int(feats['is_nrt'].groupby(feats['ist_date']).first().sum())}")
    print(f"  dates MISSING (no detection anywhere in the file): {len(missing_dates)}: "
          f"{[d.date().isoformat() for d in missing_dates]}")
    on = [d.date().isoformat() for d in missing_dates if (d.year, d.month) in {(2025, 10), (2025, 11)}]
    print(f"  missing dates in Oct-Nov 2025: {on or 'none'}")
    big = feats[feats["radius_km"] == 200]
    print(f"  200 km n_nh: mean {big['n_nh'].astype(float).mean():.1f}, max {int(big['n_nh'].max())}; "
          f"share of zero days {(big['n_nh'] == 0).mean():.1%}")

    # ---------------------------------------------------------------- checks
    print("\nChecks (outputs)")
    key = ["station_id", "ist_date"]
    piv = feats.sort_values(key + ["radius_km"])
    def stack(col):
        return piv[col].astype(float).to_numpy().reshape(-1, len(RADII_KM))
    def nested(a):
        ok = ((a[:, 0] <= a[:, 1]) | np.isnan(a[:, 0])) & ((a[:, 1] <= a[:, 2]) | np.isnan(a[:, 1]))
        return bool(ok.all())
    check("count 50 km <= 100 km <= 200 km (all stations/dates, all 6 count columns)",
          all(nested(stack(c)) for c in COUNT_COLS))
    check("FRP sum 50 km <= 100 km <= 200 km (all 6 FRP columns)", all(nested(stack(c)) for c in FRP_COLS))

    date_total = det.groupby("ist_date").size()
    cap = feats["ist_date"].map(date_total).fillna(0)
    check("no daily count exceeds the number of detections in the file for that IST date",
          bool((feats["n_all"].astype(float).fillna(0) <= cap).all()))
    check(f"detections after UTC->IST conversion == rows read ({n_raw:,})",
          int(date_total.sum()) == n_raw and det["ist_date"].notna().all())
    check(f"rows read == {EXPECTED_ROWS:,} (archive + nrt in provenance log)", n_raw == EXPECTED_ROWS)
    check("no partial IST day inside the window", not feats["partial_day"].any())

    # Boundary dates for is_nrt, checked by hand against the raw rows
    print("  is_nrt boundary (rows contributing to each IST date, box-wide):")
    for d in ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"):
        sub = det[det["ist_date"] == pd.Timestamp(d)]
        print(f"    IST {d}: archive {int((sub['product'] == 'archive').sum())}, nrt {int((sub['product'] == 'nrt').sum())}, "
              f"UTC range {sub['utc'].min()} .. {sub['utc'].max()}")
    flag = feats.groupby("ist_date")["is_nrt"].first()
    if start <= pd.Timestamp("2026-06-30") and end >= pd.Timestamp("2026-07-01"):
        check("is_nrt False on 2026-06-30 (archive only) and True on 2026-07-01 (mixed)",
              (not flag[pd.Timestamp("2026-06-30")]) and bool(flag[pd.Timestamp("2026-07-01")]))
    else:
        print("  (window does not contain the 2026-06-30/07-01 boundary; boundary test skipped)")

    # Spot check: one station, one date, detections within 100 km listed by hand-checkable distance
    if "city" in stations.columns and stations["city"].astype(str).str.startswith("Delhi").any():
        default_station = int(stations.loc[stations["city"].astype(str).str.startswith("Delhi"), "station_id"].iloc[0])
    else:
        default_station = int(stations["station_id"].iloc[0])
    spot_station = args.spot_station or default_station
    srow = stations[stations["station_id"] == spot_station].iloc[0]
    sub100 = feats[(feats["station_id"] == spot_station) & (feats["radius_km"] == 100)]
    if args.spot_date:
        spot_date = pd.Timestamp(args.spot_date)
    else:
        cand = sub100[(sub100["ist_date"].dt.month == 11) & sub100["n_all"].between(5, 15)]
        spot_date = (cand if len(cand) else sub100.sort_values("n_all", ascending=False)).iloc[0]["ist_date"]
    day = det[det["ist_date"] == spot_date].copy()
    day["dist_km"] = haversine_km(srow["latitude"], srow["longitude"], day["latitude"], day["longitude"])
    near = day[day["dist_km"] <= 100].sort_values("dist_km")
    print(f"\nSpot check: station {spot_station} ({srow['latitude']:.4f}, {srow['longitude']:.4f}), "
          f"IST date {spot_date.date()}, detections within 100 km: {len(near)}")
    print(near[["utc", "ist", "latitude", "longitude", "dist_km", "confidence", "daynight", "frp"]]
          .head(30).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    table_row = sub100[sub100["ist_date"] == spot_date].iloc[0]
    check(f"spot check: table n_all ({table_row['n_all']}) == recount with plain haversine ({len(near)})",
          int(table_row["n_all"]) == len(near))
    check(f"spot check: table frp_all ({table_row['frp_all']:.3f}) == recount ({near['frp'].sum():.3f})",
          abs(float(table_row["frp_all"]) - float(near["frp"].sum())) < 1e-6)

    # Sanity plot and seasonal check
    s200 = feats[(feats["station_id"] == spot_station) & (feats["radius_km"] == 200)].set_index("ist_date")
    series = s200["n_nh"].astype(float)
    monthly = series.groupby(series.index.month).mean()
    top4 = sorted(monthly.sort_values(ascending=False).index[:4])
    print("\nMean daily 200 km count (n+h) by calendar month, station", spot_station)
    print("  " + ", ".join(f"{m:02d}: {v:.1f}" for m, v in monthly.items()))
    # Seasonal sanity is a pass/fail check only on a multi-year window (the full 2022-2026 file gave
    # top months 4, 5, 10, 11). On a window with a single burning season it is informational:
    # one weak October moves December into the top four.
    if (window[-1] - window[0]).days >= 3 * 365:
        check(f"seasonal sanity: top-4 months {top4} are within Mar-May and Oct-Nov", set(top4) <= {3, 4, 5, 10, 11})
    else:
        print(f"  INFO seasonal sanity (window under 3 years, not a pass/fail check): top-4 months {top4}")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=130)
    ax.plot(series.index, series.values, color="#2a6fbb", linewidth=0.9)
    if series.index.min() <= pd.Timestamp("2026-07-01") <= series.index.max():
        ax.axvline(pd.Timestamp("2026-07-01"), color="#8a8f98", linewidth=1, linestyle=(0, (4, 3)))
        ax.text(pd.Timestamp("2026-07-01"), ax.get_ylim()[1], " near-real-time from 1 Jul 2026", va="top", ha="left",
                fontsize=8, color="#555b66")
    ax.set_title(f"Fire detections within 200 km per day (confidence n+h), station {spot_station}",
                 loc="left", fontsize=11, color="#1f2430")
    ax.set_ylabel("detections per IST day", color="#555b66")
    ax.grid(axis="y", color="#e3e6ea", linewidth=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c5cad1")
    ax.tick_params(colors="#555b66", labelsize=8)
    fig.tight_layout()
    fig_path = FIG_DIR / f"fire_count_200km_station_{spot_station}.png"
    fig.savefig(fig_path)
    print(f"  wrote {fig_path.relative_to(ROOT)}")

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
