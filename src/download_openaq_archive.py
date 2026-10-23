"""Download the OpenAQ archive (public S3 bucket, no key) for every station in stations.csv
plus the AirNow validation station, years 2025 and 2026.

  python src/download_openaq_archive.py            all stations, skipping nothing (sync is incremental)
  python src/download_openaq_archive.py 17 50      only these station IDs

Files land in data/raw/openaq_archive/<id>/<year>/month=MM/ (git-ignored), the same layout the
other openaq_* scripts read. Needs the AWS CLI; `--no-sign-request` means no credentials.
"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw" / "openaq_archive"
BUCKET = "s3://openaq-data-archive/records/csv.gz"
YEARS = (2025, 2026)


def station_ids():
    ids = pd.read_csv(ROOT / "data" / "processed" / "stations.csv", encoding="utf-8-sig")["id"].tolist()
    ids += pd.read_csv(ROOT / "data" / "processed" / "stations_validation_airnow.csv")["id"].tolist()
    return ids


def sync(job):
    sid, year = job
    cmd = ["aws", "s3", "sync", "--no-sign-request", "--only-show-errors",
           f"{BUCKET}/locationid={sid}/year={year}/", str(DEST / str(sid) / str(year))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return sid, year, r.returncode, r.stderr.strip()


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or station_ids()
    jobs = [(i, y) for i in ids for y in YEARS]
    failed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sid, year, code, err in pool.map(sync, jobs):
            n = len(list((DEST / str(sid) / str(year)).rglob("*.csv.gz")))
            print(f"{sid} {year}: {n} files" + (f"  FAILED {code}: {err}" if code else ""), flush=True)
            failed += code != 0
    sys.exit(1 if failed else 0)
