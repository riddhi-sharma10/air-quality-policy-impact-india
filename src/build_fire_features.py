"""Build daily fire-detection features per station from the FIRMS VIIRS S-NPP files.

For every station, IST calendar date and radius (50, 100, 200 km) it counts the
detections and sums FRP, for two confidence sets (all; n+h only) crossed with three
periods (whole day; daytime pass only; night pass only).

Dates are IST (UTC+5:30): acq_date + acq_time are UTC, so a night pass at about
20:00-22:00 UTC falls on the NEXT IST date.

Usage:  python src/build_fire_features.py [--start YYYY-MM-DD --end YYYY-MM-DD]
        (--start/--end restrict the output rows, in IST dates; detections are never trimmed)
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
STATIONS_CSV = ROOT / "data" / "processed" / "stations.csv"
OUT_CSV = ROOT / "data" / "processed" / "fire_features_daily.csv"
FIG_DIR = ROOT / "docs" / "figures"

RADII_KM = [50, 100, 200]
EARTH_RADIUS_KM = 6371.0088  # mean Earth radius
IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
NRT_START = pd.Timestamp("2026-07-01")  # IST dates from here depend on near-real-time data
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
    # acq_time is an integer without leading zero (620 = 06:20): pad to HHMM, then parse as UTC
    hhmm = det["acq_time"].astype(int).astype(str).str.zfill(4)
    det["utc"] = pd.to_datetime(det["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M")
    det["ist"] = det["utc"] + IST_OFFSET
    det["ist_date"] = det["ist"].dt.normalize()
    return det, sum(len(f) for f in frames)


def load_stations():
    st = pd.read_csv(STATIONS_CSV)
    st = st.rename(columns={"id": "station_id"})[["station_id", "latitude", "longitude"]]
    st = st.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if st["station_id"].duplicated().any():
        sys.exit("duplicate station IDs in stations.csv")
    return st


# 2. Features ---------------------------------------------------------------------------
def build_features(det, stations, dates):
    n_dates = len(dates)
    date_idx = ((det["ist_date"] - dates[0]).dt.days).to_numpy()
    frp = det["frp"].to_numpy(dtype=float)
    daynight = det["daynight"].to_numpy()
    conf = det["confidence"].to_numpy()

    masks = {}
    for (c, p) in COMBOS:
        m = np.ones(len(det), dtype=bool)
        if CONFIDENCE_SETS[c] is not None:
            m &= np.isin(conf, CONFIDENCE_SETS[c])
        if PERIODS[p] is not None:
            m &= daynight == PERIODS[p]
        masks[(c, p)] = m

    # BallTree on (lat, lon) in RADIANS: the haversine metric works on radians and returns the
    # central angle in radians, so the radius must also be in radians (km / Earth radius).
    tree = BallTree(np.radians(det[["latitude", "longitude"]].to_numpy()), metric="haversine")
    st_rad = np.radians(stations[["latitude", "longitude"]].to_numpy())
    # One query at the largest radius; the smaller radii are subsets of it by distance.
    ind, dist = tree.query_radius(st_rad, r=max(RADII_KM) / EARTH_RADIUS_KM, return_distance=True)

    frames = []
    for i, sid in enumerate(stations["station_id"]):
        idx, dkm = ind[i], dist[i] * EARTH_RADIUS_KM
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
    ap.add_argument("--start", help="first IST date to write (default: first date in the data)")
    ap.add_argument("--end", help="last IST date to write (default: last date in the data)")
    ap.add_argument("--spot-station", type=int, help="station_id for the spot check")
    ap.add_argument("--spot-date", help="IST date for the spot check")
    args = ap.parse_args()

    print("Reading detections")
    det, n_raw = load_detections()
    stations = load_stations()
    print(f"  stations: {len(stations)} from {STATIONS_CSV.name}")

    # Full IST date range present in the data, and the dates with no detection at all
    all_dates = pd.date_range(det["ist_date"].min(), det["ist_date"].max(), freq="D")
    totals_by_date = det.groupby("ist_date").size().reindex(all_dates, fill_value=0)
    missing_dates = totals_by_date.index[totals_by_date == 0]

    # IST days that are only partly inside the downloaded UTC span (first and last day)
    span_start = pd.Timestamp(det["acq_date"].min())
    span_end = pd.Timestamp(det["acq_date"].max()) + pd.Timedelta(days=1)
    day_start_utc = all_dates - IST_OFFSET
    partial = (day_start_utc < span_start) | (day_start_utc + pd.Timedelta(days=1) > span_end)

    print("Computing features")
    feats = build_features(det, stations, all_dates)

    # 3. Dates with no detection anywhere in the file are MISSING (NaN), not zero
    is_missing = feats["ist_date"].isin(missing_dates)
    for col in COUNT_COLS + FRP_COLS:
        feats[col] = feats[col].astype(float).mask(is_missing)
    for col in COUNT_COLS:
        feats[col] = feats[col].astype("Int64")
    feats["is_nrt"] = feats["ist_date"] >= NRT_START
    feats["partial_day"] = feats["ist_date"].isin(all_dates[partial])
    feats = feats[["station_id", "ist_date", "radius_km"] + COUNT_COLS + FRP_COLS + ["is_nrt", "partial_day"]]

    if args.start:
        feats = feats[feats["ist_date"] >= pd.Timestamp(args.start)]
    if args.end:
        feats = feats[feats["ist_date"] <= pd.Timestamp(args.end)]
    feats = feats.sort_values(["station_id", "radius_km", "ist_date"]).reset_index(drop=True)

    # 4. Write
    out = feats.copy()
    out["ist_date"] = out["ist_date"].dt.strftime("%Y-%m-%d")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    print("\nSummary")
    print(f"  wrote {OUT_CSV.relative_to(ROOT)}: {len(out):,} rows "
          f"({feats['station_id'].nunique()} stations x {feats['ist_date'].nunique()} dates x {len(RADII_KM)} radii)")
    print(f"  IST dates in data: {all_dates[0].date()} to {all_dates[-1].date()} ({len(all_dates)} days)")
    print(f"  output window: {feats['ist_date'].min().date()} to {feats['ist_date'].max().date()}")
    print(f"  partial IST days (edge of download): {[d.date().isoformat() for d in all_dates[partial]]}")
    print(f"  rows with is_nrt: {int(feats['is_nrt'].sum()):,}")
    big = feats[feats["radius_km"] == 200]
    print(f"  200 km n_nh: mean {big['n_nh'].astype(float).mean():.1f}, max {int(big['n_nh'].max())}; "
          f"share of zero days {(big['n_nh'] == 0).mean():.1%}")

    # ---------------------------------------------------------------- checks
    print("\nChecks")
    key = ["station_id", "ist_date"]
    piv = feats.sort_values(key + ["radius_km"])
    def stack(col):
        return piv[col].astype(float).to_numpy().reshape(-1, len(RADII_KM))
    def nested(a):
        # nan-aware: a row with NaN (missing date) passes
        ok = ((a[:, 0] <= a[:, 1]) | np.isnan(a[:, 0])) & ((a[:, 1] <= a[:, 2]) | np.isnan(a[:, 1]))
        return bool(ok.all())
    check("count 50 km <= 100 km <= 200 km (all stations/dates, all 6 count columns)",
          all(nested(stack(c)) for c in COUNT_COLS))
    check("FRP sum 50 km <= 100 km <= 200 km (all 6 FRP columns)",
          all(nested(stack(c) + 0.0) for c in FRP_COLS))

    date_total = det.groupby("ist_date").size()
    cap = feats["ist_date"].map(date_total).fillna(0)
    check("no daily count exceeds the number of detections in the file for that IST date",
          bool((feats["n_all"].astype(float).fillna(0) <= cap).all()))

    check(f"detections after UTC->IST conversion == rows read ({n_raw:,})",
          int(date_total.sum()) == n_raw and det["ist_date"].notna().all())
    check(f"rows read == {EXPECTED_ROWS:,} (archive + nrt in provenance log)", n_raw == EXPECTED_ROWS)
    print(f"  INFO dates flagged missing (no detection anywhere in the file, IST dates): {len(missing_dates)}")
    print(f"  INFO first IST date {all_dates[0].date()}, last IST date {all_dates[-1].date()}")

    # Spot check: one station, one date, detections within 100 km listed by hand-checkable distance
    treated_delhi = stations.merge(pd.read_csv(STATIONS_CSV).rename(columns={"id": "station_id"})[["station_id", "city"]])
    delhi_ids = treated_delhi.loc[treated_delhi["city"].str.startswith("Delhi"), "station_id"]
    spot_station = args.spot_station if args.spot_station else int(delhi_ids.iloc[0])
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

    # Sanity plot: daily 200 km count (n+h) for the spot station, plus seasonal check
    s200 = feats[(feats["station_id"] == spot_station) & (feats["radius_km"] == 200)].set_index("ist_date")
    series = s200["n_nh"].astype(float)
    monthly = series.groupby(series.index.month).mean()
    top4 = set(monthly.sort_values(ascending=False).index[:4])
    print("\nMean daily 200 km count (n+h) by calendar month, station", spot_station)
    print("  " + ", ".join(f"{m:02d}: {v:.1f}" for m, v in monthly.items()))
    check(f"seasonal sanity: top-4 months {sorted(top4)} are within Mar-May and Oct-Nov",
          top4 <= {3, 4, 5, 10, 11})

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=130)
    ax.plot(series.index, series.values, color="#2a6fbb", linewidth=0.9)
    ax.axvline(NRT_START, color="#8a8f98", linewidth=1, linestyle=(0, (4, 3)))
    ax.text(NRT_START, ax.get_ylim()[1], " near-real-time from 1 Jul 2026", va="top", ha="left",
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
