"""Look inside three daily OpenAQ archive files for station 6358 (Mandir Marg, Delhi)."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
base = ROOT / "data" / "raw" / "openaq_archive" / "6358" / "2025"
files = {
    "oct03": base / "month=10" / "location-6358-20251003.csv.gz",
    "oct07": base / "month=10" / "location-6358-20251007.csv.gz",
    "oct08": base / "month=10" / "location-6358-20251008.csv.gz",
}
for name, path in files.items():
    df = pd.read_csv(path)  # pandas reads .csv.gz directly
    print("=====", name, "rows:", len(df))
    print(df.columns.tolist())
    print(df.head(8).to_string())
    for c in df.columns:
        if df[c].nunique() < 30:
            print("--", c)
            print(df[c].value_counts(dropna=False))
