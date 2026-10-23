"""Sanity-check the ERA5 files for the study window (wide box, 2025-2026).

Per file: variables, hour count, duplicates, gaps, grid size, expver. Then the joined series
must cover the whole study window with no gaps. Exits non-zero on any failure.
Missing periods are reported as failures, so this is also a progress check while downloads queue.
"""
import sys

import pandas as pd
import xarray as xr

from era5_window import KINDS, N_LAT, N_LON, PERIODS, STUDY_END, STUDY_START, file_path, period_bounds, period_label

results = []


def check(label, ok):
    results.append((label, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def expver_label(values):
    return sorted(set(values.astype(str).tolist()))


def inspect(path, period, kind):
    print("=" * 70, f"\n{path.name}\n" + "=" * 70)
    ds = xr.open_dataset(path)
    start, end = period_bounds(period)
    full = pd.date_range(start, end, freq="h")
    times = pd.DatetimeIndex(ds["valid_time"].values)
    n, tag = len(full), path.name
    print(f"Variables: {sorted(ds.data_vars)}; {len(times)} steps {times[0]} to {times[-1]}; "
          f"expver {expver_label(ds['expver'].values)}")
    check(f"{tag}: variables are {sorted(KINDS[kind])}", set(ds.data_vars) == KINDS[kind])
    check(f"{tag}: {n} hours (found {len(times)})", len(times) == n)
    check(f"{tag}: no duplicate hours", not times.has_duplicates)
    check(f"{tag}: no missing hours (missing {len(full.difference(times))})", len(full.difference(times)) == 0)
    check(f"{tag}: grid {N_LAT} lat x {N_LON} lon", ds.sizes["latitude"] == N_LAT and ds.sizes["longitude"] == N_LON)
    check(f"{tag}: expver is 1 or 5 only", set(expver_label(ds["expver"].values)) <= {"0001", "0005", "1", "5"})
    for name, var in ds.data_vars.items():
        print(f"  {name}: NaN {int(var.isnull().sum())} of {var.size}; min {float(var.min()):.4g}, "
              f"max {float(var.max()):.4g}, mean {float(var.mean()):.4g} {var.attrs.get('units', '')}")
        check(f"{tag}: {name} has no NaN", int(var.isnull().sum()) == 0)
    return times


if __name__ == "__main__":
    all_times = {kind: [] for kind in KINDS}
    for period in PERIODS:
        for kind in KINDS:
            path = file_path(period, kind)
            if path.exists():
                all_times[kind].append(inspect(path, period, kind))
            else:
                print(f"MISSING: {path.name}")
                check(f"{period_label(period)} {kind}: file exists", False)

    window = pd.date_range(STUDY_START, pd.Timestamp(STUDY_END) + pd.Timedelta(hours=23), freq="h")
    joined = {}
    for kind, parts in all_times.items():
        if len(parts) == len(PERIODS):
            joined[kind] = pd.DatetimeIndex(sorted(t for p in parts for t in p))
            check(f"joined {kind}: no duplicate hours", not joined[kind].has_duplicates)
            check(f"joined {kind}: covers the study window ({len(window)} h)", len(window.difference(joined[kind])) == 0)
    if len(joined) == len(KINDS):
        check("instant and accum have identical hours", joined["instant"].equals(joined["accum"]))

    failed = [label for label, ok in results if not ok]
    print("=" * 70, f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    sys.exit(1 if failed else 0)
