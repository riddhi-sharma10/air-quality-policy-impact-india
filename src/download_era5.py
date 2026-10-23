"""Submit and download the ERA5 requests for the study window.

  python src/download_era5.py --list                 show the periods and which files exist
  python src/download_era5.py 2025_02-04 2025_05-07  download those periods (2-3 at a time)
  python src/download_era5.py --all                  every period that is not downloaded yet

Needs `pip install "cdsapi>=0.7.4"` and a ~/.cdsapirc with your CDS key (never paste the key
into a command or commit it). Requests are sent one after another, so only one sits in the
CDS queue at a time; run two or three of these in separate terminals if the queue is slow.
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

from era5_window import AREA, DATASET, ERA5_DIR, KINDS, PERIODS, VARIABLES, file_path, period_label


def build_request(period):
    year, m1, m2 = period
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [str(year)],
        "month": [f"{m:02d}" for m in range(m1, m2 + 1)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": AREA,
    }


def is_done(period):
    return all(file_path(period, kind).exists() for kind in KINDS)


def kind_of(name):
    """CDS names the two files '..._stepType-instant.nc' and '..._stepType-accum.nc'."""
    for kind in KINDS:
        if kind in name:
            return kind
    return None


def place_files(downloaded, period):
    """Put the CDS result (a zip with two files, or a single file) at the project file names."""
    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ERA5_DIR / f"_tmp_{period_label(period)}"
    tmp.mkdir(exist_ok=True)
    try:
        if zipfile.is_zipfile(downloaded):
            with zipfile.ZipFile(downloaded) as z:
                z.extractall(tmp)
            parts = sorted(tmp.glob("*.nc"))
        else:
            parts = [Path(downloaded)]
        found = {kind_of(p.name): p for p in parts}
        if set(found) != set(KINDS):
            raise RuntimeError(f"expected instant and accum files, got {[p.name for p in parts]}")
        for kind, src in found.items():
            shutil.move(str(src), file_path(period, kind))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        Path(downloaded).unlink(missing_ok=True)


def download(period):
    import cdsapi  # imported here so --list works without the package

    client = cdsapi.Client()
    target = ERA5_DIR / f"_download_{period_label(period)}"
    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    print(f"submitting {period_label(period)} ...", flush=True)
    client.retrieve(DATASET, build_request(period)).download(str(target))
    place_files(target, period)
    print(f"saved {period_label(period)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("periods", nargs="*", help="period labels such as 2025_02-04")
    ap.add_argument("--all", action="store_true", help="every period not downloaded yet")
    ap.add_argument("--list", action="store_true", help="list periods and exit")
    args = ap.parse_args()

    by_label = {period_label(p): p for p in PERIODS}
    if args.list or not (args.periods or args.all):
        for label, p in by_label.items():
            print(f"{label}: {'downloaded' if is_done(p) else 'missing'}")
        sys.exit(0)

    chosen = [p for p in PERIODS if not is_done(p)] if args.all else []
    for label in args.periods:
        if label not in by_label:
            sys.exit(f"unknown period {label}; choose from {list(by_label)}")
        chosen.append(by_label[label])
    for p in chosen:
        download(p)
