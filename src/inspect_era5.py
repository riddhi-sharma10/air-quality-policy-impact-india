"""Inspect and sanity-check all ERA5 NetCDF files for the Delhi box, 2022.

Each request (month range) should give an `instant` and an `accum` file. Every
file is checked on its own, then the requests are joined and the whole year is
checked for gaps and duplicate hours.
"""
import calendar
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

ERA5_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "era5"
YEAR = 2022
PERIODS = [(1, 4), (5, 7), (8, 10), (11, 12)]  # first and last month of each request
KINDS = {
    "instant": {"u10", "v10", "d2m", "t2m", "sp", "blh"},
    "accum": {"tp"},
}
N_LAT, N_LON = 8, 7
EXPECTED_STEPS = {(1, 4): 2880, (5, 7): 2208, (8, 10): 2208, (11, 12): 1464}
EXPECTED_YEAR_STEPS = 8760

results = []  # (label, ok) for the final summary


def check(label, ok):
    results.append((label, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def expver_is_one(value):
    """expver is stored as text ('0001'); convert to int explicitly. Anything else fails."""
    try:
        return int(str(value).strip()) == 1
    except ValueError:
        return False


def period_bounds(first_month, last_month):
    start = pd.Timestamp(YEAR, first_month, 1)
    end = pd.Timestamp(YEAR, last_month, calendar.monthrange(YEAR, last_month)[1], 23)
    return start, end


def file_path(period, kind):
    return ERA5_DIR / f"era5_delhi_{YEAR}_{period[0]:02d}-{period[1]:02d}_{kind}.nc"


def inspect(path, period, kind):
    print("=" * 70)
    print(path.name)
    print("=" * 70)
    ds = xr.open_dataset(path)
    start, end = period_bounds(*period)
    full = pd.date_range(start, end, freq="h")
    times = pd.DatetimeIndex(ds["valid_time"].values)
    lats, lons = ds["latitude"].values, ds["longitude"].values

    print("Variables:")
    for name, var in ds.data_vars.items():
        print(f"  {name}: units={var.attrs.get('units')}, long_name={var.attrs.get('long_name')}")
    print(f"Time: 'valid_time', length {len(times)}, first {times[0]}, last {times[-1]}")
    print(f"Grid: {len(lats)} lat ({lats.min()} to {lats.max()}), {len(lons)} lon ({lons.min()} to {lons.max()})")
    expver = sorted(set(ds["expver"].values.astype(str).tolist()))
    print(f"expver values: {expver}   number: {ds['number'].values}")

    print("Checks:")
    name = path.name
    check(f"{name}: variables are {sorted(KINDS[kind])}", set(ds.data_vars) == KINDS[kind])
    check(f"{name}: {EXPECTED_STEPS[period]} time steps (found {len(times)})", len(times) == EXPECTED_STEPS[period])
    check(f"{name}: no duplicate hours", not times.has_duplicates)
    missing = full.difference(times)
    check(f"{name}: no missing hours (missing {len(missing)})", len(missing) == 0)
    check(f"{name}: first {start}, last {end}", times[0] == start and times[-1] == end)
    check(f"{name}: {N_LAT} lat x {N_LON} lon", len(lats) == N_LAT and len(lons) == N_LON)
    check(f"{name}: expver is 1 for every hour", all(expver_is_one(v) for v in expver))

    print("NaN count / min / max / mean per variable:")
    for vname, var in ds.data_vars.items():
        print(f"  {vname}: NaN {int(var.isnull().sum())} of {var.size}; "
              f"min {float(var.min()):.4g}, max {float(var.max()):.4g}, "
              f"mean {float(var.mean()):.4g} {var.attrs.get('units', '')}")
    print()
    return ds


def check_year(datasets, kind):
    """Join the requests of one kind and check the whole year."""
    print(f"-- Whole year, {kind} files --")
    if len(datasets) < len(PERIODS):
        check(f"year {kind}: all {len(PERIODS)} requests present (have {len(datasets)})", False)
        return
    times = pd.DatetimeIndex(sorted(t for ds in datasets for t in ds["valid_time"].values))
    full = pd.date_range(f"{YEAR}-01-01 00:00", f"{YEAR}-12-31 23:00", freq="h")
    check(f"year {kind}: {EXPECTED_YEAR_STEPS} hours (found {len(times)})", len(times) == EXPECTED_YEAR_STEPS)
    check(f"year {kind}: no duplicate hours", not times.has_duplicates)
    check(f"year {kind}: no gaps (missing {len(full.difference(times))})", len(full.difference(times)) == 0)
    return times


if __name__ == "__main__":
    loaded = {kind: [] for kind in KINDS}
    n_expected_files = len(PERIODS) * len(KINDS)
    n_present = sum(file_path(p, k).exists() for p in PERIODS for k in KINDS)
    print(f"files present: {n_present} of {n_expected_files}\n")
    for period in PERIODS:
        for kind in KINDS:
            path = file_path(period, kind)
            if not path.exists():
                print(f"MISSING: {path.name}\n")
                check(f"{path.name}: file exists", False)
                continue
            loaded[kind].append(inspect(path, period, kind))

    year_times = {kind: check_year(loaded[kind], kind) for kind in KINDS}
    if all(t is not None for t in year_times.values()):
        check("year: instant and accum have identical hours", year_times["instant"].equals(year_times["accum"]))

    failed = [label for label, ok in results if not ok]
    print("=" * 70)
    print(f"files present: {n_present} of {n_expected_files}")
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)
