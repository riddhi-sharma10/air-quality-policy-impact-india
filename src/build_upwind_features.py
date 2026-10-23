"""Daily UPWIND fire features per station, from FIRMS detections and ERA5 winds.

For each station, IST date, radius (50/100/200 km) and half-angle theta (30/45/60 deg) it counts
the detections (confidence n+h) whose bearing from the station lies within +-theta of the
direction the wind blows FROM, and sums their FRP. Whole-day, day-pass and night-pass versions.

Wind: u10 and v10 at the station's nearest ERA5 grid cell, averaged over the last --wind-days IST
calendar days (1 = the same IST day as the detections; 2 = that day and the day before). The
vectors u and v are averaged, never the angles; direction is then taken from the mean vector.
Only stations inside the ERA5 box and dates with a full set of wind hours are produced.

Usage:
  python src/build_upwind_features.py [--stations CSV] [--start D --end D] [--wind-days 1|2]
         [--era5-dir DIR] [--out CSV]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.neighbors import BallTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fire_features import (DEFAULT_STATIONS, EARTH_RADIUS_KM, IST_OFFSET, RADII_KM,  # noqa: E402
                                 haversine_km, load_detections, load_stations)
from fire_geometry import (angular_diff_deg, bearing_via_vectors_deg, initial_bearing_deg,  # noqa: E402
                           wind_from_deg)

ROOT = Path(__file__).resolve().parent.parent
THETAS = [30, 45, 60]  # half-angles of the upwind cone, degrees (sensitivity set)
PERIODS = {"": None, "_day": "D", "_night": "N"}
COUNT_COLS = [f"n_up_nh{p}" for p in PERIODS]
FRP_COLS = [f"frp_up_nh{p}" for p in PERIODS]
results = []


def check(label, ok):
    results.append((label, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def load_era5(era5_dir):
    files = sorted(era5_dir.glob("era5_delhi_*_instant.nc"))
    if not files:
        sys.exit(f"no ERA5 instant files in {era5_dir}")
    parts = [xr.open_dataset(f)[["u10", "v10"]].load() for f in files]
    ds = xr.concat(parts, dim="valid_time").sortby("valid_time")
    if ds.indexes["valid_time"].has_duplicates:
        sys.exit("duplicate ERA5 hours")
    print(f"  ERA5: {len(files)} files, {ds.sizes['valid_time']} hours, {ds.indexes['valid_time'][0]} .. {ds.indexes['valid_time'][-1]} UTC")
    return ds


def station_wind(ds, lat, lon, wind_days):
    """Daily mean wind vector at the nearest ERA5 cell, over the last `wind_days` IST days."""
    cell = ds.sel(latitude=lat, longitude=lon, method="nearest")
    # ERA5 stamps are UTC on the hour = IST :30. IST day d therefore holds the 24 stamps 00:30..23:30 IST.
    ist = pd.DatetimeIndex(cell["valid_time"].values) + IST_OFFSET
    u, v = cell["u10"].values.astype(float), cell["v10"].values.astype(float)
    hourly = pd.DataFrame({"u": u, "v": v, "spd": np.hypot(u, v), "n": 1}, index=ist.floor("D"))
    daily = hourly.groupby(level=0).sum()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D"), fill_value=0)
    roll = daily.rolling(wind_days, min_periods=wind_days).sum()
    full = roll["n"] == 24 * wind_days  # every wind hour present, otherwise the day is NaN
    out = pd.DataFrame(index=daily.index)
    out["u_mean"] = (roll["u"] / roll["n"]).where(full)
    out["v_mean"] = (roll["v"] / roll["n"]).where(full)
    out["wind_from_deg"] = wind_from_deg(out["u_mean"], out["v_mean"])
    out["wind_speed_vec"] = np.hypot(out["u_mean"], out["v_mean"])  # speed of the mean vector, m/s
    # steadiness 1 = wind always the same direction all period; near 0 = it kept changing direction
    out["wind_steadiness"] = out["wind_speed_vec"] / (roll["spd"] / roll["n"]).where(full)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", type=Path, default=DEFAULT_STATIONS)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--wind-days", type=int, default=1, choices=[1, 2])
    ap.add_argument("--era5-dir", type=Path, default=ROOT / "data" / "raw" / "era5")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processed" / "fire_upwind_daily.csv")
    ap.add_argument("--spot-station", type=int)
    args = ap.parse_args()

    print("Reading inputs")
    det, n_raw = load_detections()
    stations = load_stations(args.stations)
    ds = load_era5(args.era5_dir)

    # Stations inside the ERA5 box (half a grid cell of tolerance); the rest have no wind data.
    lat_lo, lat_hi = float(ds["latitude"].min()) - 0.125, float(ds["latitude"].max()) + 0.125
    lon_lo, lon_hi = float(ds["longitude"].min()) - 0.125, float(ds["longitude"].max()) + 0.125
    inside = stations["latitude"].between(lat_lo, lat_hi) & stations["longitude"].between(lon_lo, lon_hi)
    print(f"  stations inside the ERA5 box: {int(inside.sum())} of {len(stations)} (others skipped: no wind)")
    stations = stations[inside].reset_index(drop=True)

    winds = {int(r.station_id): station_wind(ds, r.latitude, r.longitude, args.wind_days) for r in stations.itertuples()}
    valid = [w["u_mean"].notna() for w in winds.values()]
    dates_ok = valid[0].index[valid[0]]
    assert all(v.index[v].equals(dates_ok) for v in valid), "stations disagree on wind availability"
    lo = max(dates_ok.min(), pd.Timestamp(args.start)) if args.start else dates_ok.min()
    hi = min(dates_ok.max(), pd.Timestamp(args.end)) if args.end else dates_ok.max()
    window = pd.date_range(lo, hi, freq="D")
    assert window.isin(dates_ok).all(), "gap in the wind data inside the window"
    print(f"  dates with a full wind set: {window[0].date()} to {window[-1].date()} ({len(window)} days), wind averaged over {args.wind_days} IST day(s)")

    # ---- detection arrays
    date_idx = ((det["ist_date"] - window[0]).dt.days).to_numpy()
    in_window = (date_idx >= 0) & (date_idx < len(window))
    nh = det["confidence"].isin(["n", "h"]).to_numpy()
    frp = det["frp"].to_numpy(dtype=float)
    daynight = det["daynight"].to_numpy()
    det_lat, det_lon = det["latitude"].to_numpy(), det["longitude"].to_numpy()
    tree = BallTree(np.radians(det[["latitude", "longitude"]].to_numpy()), metric="haversine")
    totals = det.groupby("ist_date").size().reindex(window, fill_value=0)
    missing = (totals == 0).to_numpy()  # no detection anywhere in the file on that IST date -> NaN, not 0
    nrt_first = det.loc[det["product"] == "nrt", "ist_date"].min()

    def counts(idx, dkm, upwind_mask, radius):
        """bincount per IST date for the three periods; upwind_mask=None means no direction filter."""
        res = {}
        for p, code in PERIODS.items():
            m = dkm <= radius
            if upwind_mask is not None:
                m &= upwind_mask
            if code is not None:
                m &= daynight[idx] == code
            res[f"n_up_nh{p}"] = np.bincount(date_idx[idx[m]], minlength=len(window)).astype(float)
            res[f"frp_up_nh{p}"] = np.bincount(date_idx[idx[m]], weights=frp[idx[m]], minlength=len(window))
        return res

    frames, total_check = [], []
    for r in stations.itertuples():
        sid = int(r.station_id)
        ind, dist = tree.query_radius(np.radians([[r.latitude, r.longitude]]), r=max(RADII_KM) / EARTH_RADIUS_KM, return_distance=True)
        idx, dkm = ind[0], dist[0] * EARTH_RADIUS_KM
        keep = in_window[idx] & nh[idx]
        idx, dkm = idx[keep], dkm[keep]
        bearing = initial_bearing_deg(r.latitude, r.longitude, det_lat[idx], det_lon[idx])
        wind = winds[sid].reindex(window)
        diff = angular_diff_deg(bearing, wind["wind_from_deg"].to_numpy()[date_idx[idx]])
        for radius in RADII_KM:
            plain = counts(idx, dkm, None, radius)  # no direction filter, for the checks
            full = counts(idx, dkm, diff <= 180, radius)  # theta = 180 must reproduce `plain`
            total_check.append(all(np.array_equal(plain[k], full[k]) for k in plain))
            for theta in THETAS:
                res = counts(idx, dkm, diff <= theta, radius)
                block = pd.DataFrame({"station_id": sid, "ist_date": window, "radius_km": radius, "theta_deg": theta,
                                      "wind_days": args.wind_days})
                for c in ("u_mean", "v_mean", "wind_from_deg", "wind_speed_vec", "wind_steadiness"):
                    block[c] = wind[c].to_numpy()
                for c in COUNT_COLS + FRP_COLS:
                    block[c] = np.where(missing, np.nan, res[c])
                block["_total_n"] = np.where(missing, np.nan, plain["n_up_nh"])
                frames.append(block)
    out = pd.concat(frames, ignore_index=True)
    out["is_nrt"] = out["ist_date"] >= nrt_first
    for c in COUNT_COLS:
        out[c] = out[c].astype("Int64")
    out = out.sort_values(["station_id", "radius_km", "theta_deg", "ist_date"]).reset_index(drop=True)

    # ---- write
    to_write = out.drop(columns="_total_n").copy()
    to_write["ist_date"] = to_write["ist_date"].dt.strftime("%Y-%m-%d")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    to_write.to_csv(args.out, index=False)
    print("\nSummary")
    print(f"  wrote {args.out}: {len(to_write):,} rows ({len(stations)} stations x {len(window)} dates x {len(RADII_KM)} radii x {len(THETAS)} thetas)")
    d = out[(out["radius_km"] == 100) & (out["theta_deg"] == 45)]
    print(f"  100 km, theta 45: mean upwind n+h per day {d['n_up_nh'].astype(float).mean():.2f} "
          f"(all directions {d['_total_n'].mean():.2f}); share of detections upwind {d['n_up_nh'].astype(float).sum() / d['_total_n'].sum():.1%} "
          f"(a 90-degree cone is 25% of the circle; fires are not spread evenly around a station, so this is not a baseline)")

    # ---- checks
    print("\nChecks")
    check("theta = 180 reproduces the plain count (all stations, radii, periods, FRP too)", all(total_check))
    key = out.sort_values(["station_id", "ist_date", "radius_km", "theta_deg"])
    cols = COUNT_COLS + FRP_COLS
    arr = {c: key[c].astype(float).to_numpy().reshape(-1, len(RADII_KM), len(THETAS)) for c in cols}
    def mono(a, axis):
        diffs = np.diff(a, axis=axis)
        return bool(((diffs >= -1e-9) | np.isnan(diffs)).all())
    check("upwind count/FRP: theta 30 <= 45 <= 60", all(mono(arr[c], 2) for c in cols))
    check("upwind count/FRP: 50 km <= 100 km <= 200 km", all(mono(arr[c], 1) for c in cols))
    tot = key["_total_n"].astype(float).to_numpy()
    check("upwind count <= count in all directions", bool(((key["n_up_nh"].astype(float) <= tot) | np.isnan(tot)).all()))
    check("no missing wind in the output", not out["u_mean"].isna().any())

    # Spot check by hand: one station and date
    sid0 = args.spot_station or int(stations["station_id"].iloc[0])
    srow = stations[stations["station_id"] == sid0].iloc[0]
    sub = out[(out["station_id"] == sid0) & (out["radius_km"] == 100) & (out["theta_deg"] == 45)]
    cand = sub[(sub["_total_n"] >= 8) & (sub["_total_n"] <= 25) & (sub["n_up_nh"] > 0) & (sub["n_up_nh"].astype(float) < sub["_total_n"])]
    row = (cand if len(cand) else sub.sort_values("_total_n", ascending=False)).iloc[0]
    date = row["ist_date"]
    day = det[(det["ist_date"] == date) & det["confidence"].isin(["n", "h"])].copy()
    day["dist_km"] = haversine_km(srow["latitude"], srow["longitude"], day["latitude"], day["longitude"])
    near = day[day["dist_km"] <= 100].copy()
    near["bearing"] = bearing_via_vectors_deg(srow["latitude"], srow["longitude"], near["latitude"].to_numpy(), near["longitude"].to_numpy())  # second method
    # wind recomputed straight from the ERA5 hours of that IST day, not from the table
    cell = ds.sel(latitude=srow["latitude"], longitude=srow["longitude"], method="nearest")
    ist = pd.DatetimeIndex(cell["valid_time"].values) + IST_OFFSET
    days_used = [date - pd.Timedelta(days=k) for k in range(args.wind_days)]
    sel = ist.floor("D").isin(days_used)
    u_chk, v_chk = float(cell["u10"].values[sel].mean()), float(cell["v10"].values[sel].mean())
    wf = float(wind_from_deg(u_chk, v_chk))
    near["wind_from"] = wf
    near["diff"] = angular_diff_deg(near["bearing"], wf)
    near["upwind_45"] = near["diff"] <= 45
    print(f"\nSpot check: station {sid0}, IST date {date.date()}, wind averaged over {args.wind_days} day(s): "
          f"u={u_chk:.3f}, v={v_chk:.3f} m/s -> from {wf:.1f} deg ({int(sel.sum())} hourly values)")
    print(near.sort_values("dist_km")[["ist", "latitude", "longitude", "dist_km", "bearing", "diff", "upwind_45", "frp"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    check(f"spot check: wind (u, v) from the raw ERA5 hours matches the table ({row['u_mean']:.4f}, {row['v_mean']:.4f})",
          abs(u_chk - row["u_mean"]) < 1e-5 and abs(v_chk - row["v_mean"]) < 1e-5)
    check(f"spot check: upwind count at 100 km, theta 45 ({int(row['n_up_nh'])}) == recount with the second bearing method ({int(near['upwind_45'].sum())})",
          int(row["n_up_nh"]) == int(near["upwind_45"].sum()))
    check(f"spot check: count in all directions ({int(row['_total_n'])}) == {len(near)}", int(row["_total_n"]) == len(near))

    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
