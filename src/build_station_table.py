import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "openaq_api"
OUT = ROOT / "data" / "processed"

# city -> (json file, group). Delhi file = stations within 25 km of central
# Delhi, which includes parts of the NCR (Noida, Ghaziabad, Gurugram,
# Faridabad). All lie inside the GRAP area, so all are treated.
CITIES = {
    "Delhi (25 km)": (RAW / "delhi.json", "treated"),
    "Lucknow": (RAW / "lucknow.json", "control"),
    "Kanpur": (RAW / "kanpur.json", "control"),
    "Patna": (RAW / "patna.json", "control"),
}

COVERAGE_START = datetime(2021, 9, 30, 23, 59, 59, tzinfo=timezone.utc)  # first must be <= this day
COVERAGE_END = datetime(2026, 9, 30, tzinfo=timezone.utc)                # last must be >= this day
NEAR_KM = 1.0

FIELDS = [
    "id", "name", "city", "sub_area", "group", "pair_flag", "provider", "owner", "latitude", "longitude",
    "pollutants", "datetimeFirst", "datetimeLast", "isMonitor",
]


NCR_SUB_AREAS = ["Noida", "Ghaziabad", "Gurugram", "Faridabad"]  # Greater Noida matches "Noida"


def sub_area(city, name):
    if city != "Delhi (25 km)":
        return city
    for area in NCR_SUB_AREAS:
        if area in name:
            return area
    return "Delhi"


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


# 1. Load every city with the same loop; keep monitors only.
rows = []
for city, (path, group) in CITIES.items():
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for station in data["results"]:
        if not station.get("isMonitor"):
            continue
        pollutants = set()
        for sensor in station.get("sensors") or []:
            pollutants.add(sensor["parameter"]["name"])
        coords = station.get("coordinates") or {}
        first = station.get("datetimeFirst") or {}
        last = station.get("datetimeLast") or {}
        rows.append({
            "id": station["id"],
            "name": station["name"],
            "city": city,
            "sub_area": sub_area(city, station["name"]),
            "group": group,
            "pair_flag": "",
            "provider": (station.get("provider") or {}).get("name"),
            "owner": (station.get("owner") or {}).get("name"),
            "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"),
            "pollutants": ";".join(sorted(pollutants)),
            "datetimeFirst": first.get("utc"),
            "datetimeLast": last.get("utc"),
            "isMonitor": station["isMonitor"],
        })
n_monitors = len(rows)

# 5. Separate the AirNow station (ID 8118, PM2.5 only) into its own validation file.
validation = [r for r in rows if r["id"] == 8118]
rows = [r for r in rows if r["id"] != 8118]

# 2. Coverage filter. Blank dates fail automatically.
def covered(r):
    first, last = parse(r["datetimeFirst"]), parse(r["datetimeLast"])
    return bool(first and last and first <= COVERAGE_START and last >= COVERAGE_END)

n_before_cov = len(rows)
rows = [r for r in rows if covered(r)]
n_after_cov = len(rows)

# 3. Duplicate physical stations: group by lat/lon rounded to 3 decimals.
def rank(r):
    coverage = (parse(r["datetimeLast"]) - parse(r["datetimeFirst"])).days
    return (coverage, r["provider"] == "CPCB", len(r["pollutants"].split(";")))

by_place = defaultdict(list)
for r in rows:
    by_place[(round(r["latitude"], 3), round(r["longitude"], 3))].append(r)

kept, dup_log = [], []
for place, group_rows in by_place.items():
    group_rows.sort(key=rank, reverse=True)
    kept.append(group_rows[0])
    for dropped in group_rows[1:]:
        dup_log.append({
            "lat_lon": place, "kept_id": group_rows[0]["id"], "dropped_id": dropped["id"],
            "reason": f"kept has rank (coverage_days, is_CPCB, n_pollutants)={rank(group_rows[0])} "
                      f"vs dropped {rank(dropped)}",
        })
rows = sorted(kept, key=lambda r: (r["city"], r["id"]))

# Near-duplicates the rounding can miss: report for manual review, never auto-drop.
near = []
for i, a in enumerate(rows):
    for b in rows[i + 1:]:
        d = haversine_km(a, b)
        if d < NEAR_KM:
            near.append((a["id"], a["name"], b["id"], b["name"], round(d, 3)))
            # pair_flag holds the partner station ID(s) so the pair can be resolved by hand
            a["pair_flag"] = ";".join(filter(None, [a["pair_flag"], str(b["id"])]))
            b["pair_flag"] = ";".join(filter(None, [b["pair_flag"], str(a["id"])]))

with open(OUT / "stations.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

with open(OUT / "stations_validation_airnow.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(validation)

with open(OUT / "station_duplicates_log.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["lat_lon", "kept_id", "dropped_id", "reason"])
    writer.writeheader()
    writer.writerows(dup_log)

print(f"{n_monitors} monitors across {len(CITIES)} files; {len(validation)} AirNow -> validation file")
print(f"coverage filter: {n_before_cov} -> {n_after_cov}")
print(f"exact-place duplicates dropped: {len(dup_log)}")
print(f"final main list: {len(rows)} stations")
for g in ("treated", "control"):
    print(f"  {g}: {sum(r['group'] == g for r in rows)}")
for c in CITIES:
    print(f"  {c}: {sum(r['city'] == c for r in rows)}")
for s in sorted({r["sub_area"] for r in rows}):
    print(f"  sub_area {s}: {sum(r['sub_area'] == s for r in rows)}")
print(f"pairs within {NEAR_KM} km (check by hand):")
for pair in near:
    print("  ", pair)
