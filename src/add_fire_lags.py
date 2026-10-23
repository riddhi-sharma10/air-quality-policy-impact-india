"""Lagged fire features, so that fires cannot explain earlier readings.

For each station, radius and IST date d, from the daily features (columns n_nh and frp_nh):
  <col>_lag0 = value on IST date d
  <col>_lag1 = value on IST date d-1
  <col>_lag2 = value on d-2 PLUS value on d-1 (a 2-day running sum, so it overlaps lag1)
A missing day (NaN: no detection anywhere in the file) makes every lag that uses it NaN.

RULE for the hourly table: a feature used to explain or predict pollution at hour h may only use
detections strictly before h. IST date d starts at 00:00 IST, so for every hour h of date d only
_lag1 and _lag2 qualify; _lag0 contains detections from passes that happen after h (the day pass
is at about 13:15 IST, the night pass at about 02:00 IST). `assert_hourly_safe` enforces this.

Usage:
  python src/add_fire_lags.py --features data/processed/fire_features_daily.csv \
         --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_lags.csv
The features file must start at least 2 days before --start (build it with --start 2025-02-17).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fire_features import EARTH_RADIUS_KM, haversine_km, load_detections  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE_COLS = ["n_nh", "frp_nh"]
HOURLY_ALLOWED = ("_lag1", "_lag2")
KEY = ["station_id", "radius_km"]
results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def assert_hourly_safe(columns):
    """Raise if any column could contain detections from the same IST date as the hourly row."""
    bad = [c for c in columns if not c.endswith(HOURLY_ALLOWED)]
    if bad:
        raise ValueError(f"not allowed for hourly rows (may use detections at or after the hour): {bad}")


def join_to_hourly(hourly, lags, columns, radius_km):
    """Attach lag features to a station-hour table (needs station_id and ist_date columns)."""
    assert_hourly_safe(columns)
    cols = ["station_id", "ist_date"] + list(columns)
    return hourly.merge(lags.loc[lags["radius_km"] == radius_km, cols], on=["station_id", "ist_date"], how="left")


def add_lags(df):
    df = df.sort_values(KEY + ["ist_date"]).reset_index(drop=True)
    gaps = df.groupby(KEY)["ist_date"].diff().dropna()
    if not (gaps == pd.Timedelta(days=1)).all():
        sys.exit("dates are not consecutive for every station and radius")
    g = df.groupby(KEY)
    for c in BASE_COLS:
        s1, s2 = g[c].shift(1), g[c].shift(2)
        df[f"{c}_lag0"], df[f"{c}_lag1"], df[f"{c}_lag2"] = df[c], s1, s2 + s1
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=ROOT / "data/processed/fire_features_daily.csv")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/fire_features_lags.csv")
    ap.add_argument("--samples", type=int, default=40)
    args = ap.parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)

    feats = pd.read_csv(args.features, parse_dates=["ist_date"])
    if feats["ist_date"].min() > start - pd.Timedelta(days=2):
        sys.exit(f"features start {feats['ist_date'].min().date()}: need data from {(start - pd.Timedelta(days=2)).date()} for the lags")
    full = add_lags(feats)
    lag_cols = [f"{c}_lag{k}" for c in BASE_COLS for k in (0, 1, 2)]
    out = full[(full["ist_date"] >= start) & (full["ist_date"] <= end)]
    keep = KEY + ["ist_date"] + BASE_COLS + lag_cols + ["is_nrt"]
    out = out[keep].copy()
    for c in [c for c in lag_cols if c.startswith("n_")]:
        out[c] = out[c].astype("Int64")
    o = out.copy()
    o["ist_date"] = o["ist_date"].dt.strftime("%Y-%m-%d")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    o.to_csv(args.out, index=False)
    print(f"wrote {args.out}: {len(out):,} rows, {out['station_id'].nunique()} stations, "
          f"{out['ist_date'].nunique()} dates ({out['ist_date'].min().date()} to {out['ist_date'].max().date()})")

    print("\nChecks")
    # 1. lag1(d) must equal the value of the previous row's lag0, compared through an explicit date shift
    prev = full[KEY + ["ist_date", "n_nh"]].assign(ist_date=lambda d: d["ist_date"] + pd.Timedelta(days=1))
    m = out.merge(prev, on=KEY + ["ist_date"], suffixes=("", "_prev"))
    check("n_nh_lag1 on date d == n_nh on date d-1 (merge on shifted date)",
          bool(((m["n_nh_lag1"].astype(float) == m["n_nh_prev"].astype(float)) | m["n_nh_prev"].isna()).all()))

    # 2. the guard
    for cols, expect_ok in ((["n_nh_lag1", "frp_nh_lag2"], True), (["n_nh_lag0"], False), (["n_nh"], False), (["n_nh_lag1", "frp_nh"], False)):
        try:
            assert_hourly_safe(cols)
            ok = expect_ok
        except ValueError:
            ok = not expect_ok
        check(f"assert_hourly_safe({cols}) {'accepts' if expect_ok else 'rejects'}", ok)

    # 3. hourly join: a synthetic station-hour frame; hour 00:00 of date d must receive exactly lag1(d)
    st0 = int(out["station_id"].iloc[0])
    hours = pd.date_range(start, start + pd.Timedelta(days=2, hours=23), freq="h")
    hourly = pd.DataFrame({"station_id": st0, "hour_ist": hours, "ist_date": hours.normalize()})
    joined = join_to_hourly(hourly, out, ["n_nh_lag1", "n_nh_lag2"], 100)
    ref = out[(out["station_id"] == st0) & (out["radius_km"] == 100)].set_index("ist_date")
    ok = all(joined.loc[joined["hour_ist"] == d, "n_nh_lag1"].iloc[0] == ref.loc[d, "n_nh_lag1"] or pd.isna(ref.loc[d, "n_nh_lag1"])
             for d in hourly["ist_date"].unique())
    check("hourly join gives every hour of date d the lag1 value of date d", ok and len(joined) == len(hourly))
    try:
        join_to_hourly(hourly, out, ["n_nh_lag0"], 100)
        check("hourly join refuses n_nh_lag0", False)
    except ValueError:
        check("hourly join refuses n_nh_lag0", True)

    # 4. no look-ahead, from the raw detections: every detection behind lag1/lag2 is before 00:00 IST of date d
    det, _ = load_detections()
    det = det[det["confidence"].isin(["n", "h"])]
    stations = pd.read_csv(ROOT / "data/processed/stations.csv").rename(columns={"id": "station_id"}).set_index("station_id")
    rows = out.dropna(subset=["n_nh_lag2"]).sample(args.samples, random_state=0)
    all_ok, latest = True, pd.Timestamp.min
    for r in rows.itertuples():
        s = stations.loc[r.station_id]
        d = r.ist_date
        window_det = det[(det["ist_date"] >= d - pd.Timedelta(days=2)) & (det["ist_date"] <= d - pd.Timedelta(days=1))]
        near = window_det[haversine_km(s["latitude"], s["longitude"], window_det["latitude"].to_numpy(), window_det["longitude"].to_numpy()) <= r.radius_km]
        used_lag1 = near[near["ist_date"] == d - pd.Timedelta(days=1)]
        if len(near):
            latest = max(latest, near["ist"].max())
        if not (near["ist"] < d).all():  # d is 00:00 IST of the date, the earliest hour of that date
            all_ok = False
        if len(used_lag1) != r.n_nh_lag1 or len(near) != r.n_nh_lag2:
            all_ok = False
        if abs(near["frp"].sum() - r.frp_nh_lag2) > 1e-6 or abs(used_lag1["frp"].sum() - r.frp_nh_lag1) > 1e-6:
            all_ok = False
    check(f"{args.samples} random station-dates: lag1/lag2 recounted from raw detections, all before 00:00 IST of the date "
          f"(latest used: {latest})", all_ok)

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
