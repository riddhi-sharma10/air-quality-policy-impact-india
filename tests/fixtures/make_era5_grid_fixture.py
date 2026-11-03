"""Builds tests/fixtures/era5_grid_cells_2025-11-01_2025-12-31.csv from the gridded ERA5 download.

The fixture holds hourly u10 and v10 (m/s, 6 decimals) of the 11 grid cells that contain the 54 final stations, taken
straight from data/raw/era5/era5_window_2025_11-12_instant.nc. tests/test_upwind_points.py compares the daily wind
built from the single-point weather table with the daily wind built from these gridded values, so that check runs in
any checkout without the large gridded files.

Run (only when the gridded file is present):  python tests/fixtures/make_era5_grid_fixture.py
"""
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from build_upwind_features import grid_hourly  # noqa: E402

GRID = ROOT / "data" / "raw" / "era5" / "era5_window_2025_11-12_instant.nc"
STATIONS = ROOT / "data" / "processed" / "stations_final.csv"
OUT = Path(__file__).resolve().parent / "era5_grid_cells_2025-11-01_2025-12-31.csv"


def cell(v):
    return round(round(v / 0.25) * 0.25, 2)


if __name__ == "__main__":
    st = pd.read_csv(STATIONS)
    cells = sorted({(cell(a), cell(b)) for a, b in zip(st["latitude"], st["longitude"])})
    ds = xr.open_dataset(GRID)
    parts = []
    for lat, lon in cells:
        g = grid_hourly(ds, lat, lon)          # the cell itself: lat and lon are grid points
        g.insert(0, "longitude", lon)
        g.insert(0, "latitude", lat)
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    out[["u", "v"]] = out[["u", "v"]].round(6)
    out.rename(columns={"u": "u10", "v": "v10"}).to_csv(OUT, index=False)
    print(f"wrote {OUT.name}: {len(cells)} cells, {len(out):,} rows, {out['time_utc'].min()} to {out['time_utc'].max()}")
