"""Shared settings for the ERA5 download of the study window (19 Feb 2025 to 30 Sep 2026).

Used by download_era5.py, inspect_era5_window.py and extract_era5_stations.py, so the area,
the request periods and the file names are defined once.
"""
import calendar
from pathlib import Path

ERA5_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "era5"

DATASET = "reanalysis-era5-single-levels"
VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_dewpoint_temperature",
    "2m_temperature",
    "surface_pressure",
    "total_precipitation",
    "boundary_layer_height",
]
# CDS order is [North, West, South, East]. Covers Delhi-NCR, Lucknow, Kanpur and Patna/Hajipur
# (stations span lat 25.59-28.82, lon 77.03-85.25).
AREA = [29.5, 76.5, 25.0, 85.75]
N_LAT, N_LON = 19, 38  # 0.25 degree grid over AREA

# Short names in the NetCDF files, by file kind (CDS returns one instant and one accum file).
KINDS = {
    "instant": {"u10", "v10", "d2m", "t2m", "sp", "blh"},
    "accum": {"tp"},
}

STUDY_START = "2025-02-19"
STUDY_END = "2026-09-30"

# (year, first month, last month). Whole months are requested; the first and last are
# trimmed to the study window later. Each is at most 92 days, under the 120-day limit.
PERIODS = [
    (2025, 2, 4),
    (2025, 5, 7),
    (2025, 8, 10),
    (2025, 11, 12),
    (2026, 1, 3),
    (2026, 4, 6),
    (2026, 7, 9),
]


def period_label(period):
    year, m1, m2 = period
    return f"{year}_{m1:02d}-{m2:02d}"


def period_bounds(period):
    """First and last hour (as 'YYYY-MM-DD HH:00' strings) of a request period."""
    year, m1, m2 = period
    last_day = calendar.monthrange(year, m2)[1]
    return f"{year}-{m1:02d}-01 00:00", f"{year}-{m2:02d}-{last_day:02d} 23:00"


def period_hours(period):
    import pandas as pd
    start, end = period_bounds(period)
    return len(pd.date_range(start, end, freq="h"))


def file_path(period, kind):
    return ERA5_DIR / f"era5_window_{period_label(period)}_{kind}.nc"
