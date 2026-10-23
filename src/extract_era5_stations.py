"""Turn the ERA5 grid files into one hourly table per station (nearest grid cell).

Output columns (UTC hours; see docs for the time-alignment decision, which is made at merge time):
  station_id, time_utc, cell_lat, cell_lon,
  u10, v10 (m/s), wind_speed (m/s), wind_from_deg (meteorological, 0 = from north),
  t2m_c, d2m_c (deg C), sp_hpa (hPa), blh_m (m),
  tp_mm   precipitation in the hour ENDING at time_utc (ERA5 accumulates over the hour before the stamp),
  expver, era5_preliminary   (ERA5T, expver 5, is preliminary and may be revised)

Run:  python src/extract_era5_stations.py
Test on the 2022 Delhi files:
      python src/extract_era5_stations.py --pattern "era5_delhi_2022_*" --out <file>
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from era5_window import ERA5_DIR, KINDS, STUDY_END, STUDY_START
from fire_geometry import wind_from_deg

ROOT = Path(__file__).resolve().parent.parent
STATIONS = ROOT / "data" / "processed" / "stations.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "era5_station_hourly.csv"
GRID_STEP = 0.25
MAX_OFFSET_DEG = GRID_STEP  # a station farther than one cell from the nearest grid point is outside the box


def convert(df):
    """Raw ERA5 units to analysis units and derived wind columns."""
    out = df.copy()
    out["wind_speed"] = np.hypot(out["u10"], out["v10"])
    out["wind_from_deg"] = wind_from_deg(out["u10"].to_numpy(), out["v10"].to_numpy())
    out["t2m_c"] = out["t2m"] - 273.15
    out["d2m_c"] = out["d2m"] - 273.15
    out["sp_hpa"] = out["sp"] / 100.0
    out["blh_m"] = out["blh"]
    # total precipitation is in metres of water; tiny negative values are float noise
    out["tp_mm"] = (out["tp"] * 1000.0).clip(lower=0.0)
    return out


def nearest_cells(stations, lats, lons):
    """Index of the nearest grid latitude and longitude for each station."""
    ilat = np.abs(lats[None, :] - stations["latitude"].to_numpy()[:, None]).argmin(axis=1)
    ilon = np.abs(lons[None, :] - stations["longitude"].to_numpy()[:, None]).argmin(axis=1)
    return ilat, ilon


def load_kind(files):
    """Open and join the files of one kind (instant or accum) along time."""
    datasets = [xr.open_dataset(f) for f in files]
    return xr.concat(datasets, dim="valid_time") if len(datasets) > 1 else datasets[0]


def extract(pattern, stations):
    files = {k: sorted(ERA5_DIR.glob(f"{pattern}_{k}.nc")) for k in KINDS}
    if not all(files.values()):
        sys.exit(f"no ERA5 files match {pattern}_<kind>.nc in {ERA5_DIR}")
    inst, acc = load_kind(files["instant"]), load_kind(files["accum"])
    if not inst["valid_time"].to_index().equals(acc["valid_time"].to_index()):
        sys.exit("instant and accum files do not cover the same hours")

    lats, lons = inst["latitude"].values, inst["longitude"].values
    ilat, ilon = nearest_cells(stations, lats, lons)
    offset = np.maximum(np.abs(lats[ilat] - stations["latitude"].to_numpy()),
                        np.abs(lons[ilon] - stations["longitude"].to_numpy()))
    inside = offset <= MAX_OFFSET_DEG / 2 + 1e-9
    for sid, off in zip(stations.loc[~inside, "id"], offset[~inside]):
        print(f"skipping station {sid}: {off:.2f} deg outside the ERA5 box")
    stations, ilat, ilon = stations[inside].reset_index(drop=True), ilat[inside], ilon[inside]

    times = pd.DatetimeIndex(inst["valid_time"].values)
    expver = inst["expver"].values.astype(str)
    frames = []
    for i, sid in enumerate(stations["id"]):
        pt_i = inst.isel(latitude=ilat[i], longitude=ilon[i])
        pt_a = acc.isel(latitude=ilat[i], longitude=ilon[i])
        df = pd.DataFrame({k: pt_i[k].values for k in KINDS["instant"]})
        df["tp"] = pt_a["tp"].values
        df.insert(0, "time_utc", times)
        df.insert(0, "station_id", sid)
        df.insert(2, "cell_lat", lats[ilat[i]])
        df.insert(3, "cell_lon", lons[ilon[i]])
        df["expver"] = expver
        frames.append(df)
    out = convert(pd.concat(frames, ignore_index=True))
    # ERA5T (preliminary) carries expver 5; final ERA5 is expver 1
    out["era5_preliminary"] = out["expver"].map(lambda v: int(str(v).strip()) != 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pattern", default="era5_window_*", help="file prefix before _instant/_accum.nc")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-trim", action="store_true", help="keep hours outside the study window")
    args = ap.parse_args()

    stations = pd.read_csv(STATIONS, encoding="utf-8-sig")
    result = extract(args.pattern, stations)
    if not args.no_trim:
        lo, hi = pd.Timestamp(STUDY_START), pd.Timestamp(STUDY_END) + pd.Timedelta(hours=23)
        result = result[(result["time_utc"] >= lo) & (result["time_utc"] <= hi)]
    keep = ["station_id", "time_utc", "cell_lat", "cell_lon", "u10", "v10", "wind_speed", "wind_from_deg",
            "t2m_c", "d2m_c", "sp_hpa", "blh_m", "tp_mm", "expver", "era5_preliminary"]
    result = result[keep].sort_values(["station_id", "time_utc"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False, float_format="%.5g")
    print(f"wrote {len(result)} rows, {result['station_id'].nunique()} stations, "
          f"{result['time_utc'].min()} to {result['time_utc'].max()} -> {args.out}")
    print(f"preliminary (ERA5T) rows: {int(result['era5_preliminary'].sum())}")
