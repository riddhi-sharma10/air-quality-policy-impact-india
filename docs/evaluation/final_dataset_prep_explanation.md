# How the final dataset was prepared: a complete explanation

This document explains how `data/processed/final_dataset.csv` (and its Parquet twin `final_dataset.parquet`) was made, from the first download to the last check. It covers what each input is, what each script does, which decisions were made and why, what the numbers are, and how to rebuild the file.

It is written from the code in `src/` and the project's own records: `docs/final_dataset_dictionary.md`, `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md`, `docs/project_status.md`, `docs/provenance_log.csv`, `docs/final_dataset_run_output.txt` and the notebook. Where this document gives a number, it comes from those records. The column-by-column dictionary stays in `docs/final_dataset_dictionary.md`; this document is the story of how the table was built.

---

## 1. What the final dataset is

| Item | Value |
| --- | --- |
| Unit of observation | one **station** in one **IST hour** |
| Key | (`station_id`, `hour_ist`), unique |
| Stations | **54**: 39 treated (inside the NCR, so GRAP applies) and 15 control (Patna, Lucknow, Kanpur, outside the NCR) |
| Hours per station | **14,136** (19 Feb 2025 00:00 to 30 Sep 2026 23:00 IST, 589 days) |
| Rows | **763,344** (54 × 14,136) |
| Columns | **70** |
| Files | `final_dataset.csv` (about 360 MB) and `final_dataset.parquet` (about 39 MB, same values, faster to read) |
| Git | both files are git-ignored (too large); copy them between machines, or rebuild with the commands in section 12 |
| PM2.5 present | 664,591 rows (87.1%) |

The 70 columns come from five inputs plus a few derived columns:

| Group | Columns | Source |
| --- | --- | --- |
| Identifiers and time | `station_id`, `name`, `city`, `sub_area`, `group`, `latitude`, `longitude`, `hour_ist`, `hour_utc` | station list |
| Pollution | `pm25`, `pm10`, `no`, `no2`, `nox`, `so2`, `co`, `o3`, the `n_*` reading counts, `local_temp_c`, `local_rh`, `local_wind_speed`, `network_pm25_share`, `network_outage` | OpenAQ archive (CPCB monitors) |
| Weather | `era5_time_utc`, `u10`, `v10`, `wind_speed`, `wind_from_deg`, `t2m_c`, `d2m_c`, `sp_hpa`, `blh_m`, `tp_mm` | ERA5 reanalysis |
| Fire | `n_nh_{50,100,200}km_lag{1,2}`, `frp_nh_{50,100,200}km_lag{1,2}`, `n_up_nh_100km_45deg_lag1`, `frp_up_nh_100km_45deg_lag1`, `fire_day_status`, `fire_is_nrt` | NASA FIRMS VIIRS |
| Policy | `grap_stage`, `grap_stage_applied`, `schedule_version`, `grap_uncertain`, `grap_inferred`, `hours_since_stage_change`, `last_change_direction` | CAQM GRAP orders |
| Calendar | `hour`, `weekday`, `month`, `season`, `festival`, `festival_day`, `festival_window` | derived, festival dates from Delhi government notifications |

**Why this shape.** The project asks two questions: H1 (are upwind fires associated with higher PM2.5?) and H2 (is GRAP activation associated with PM2.5?). Both need the same thing: the hourly pollution at each station beside the weather, the fire exposure and the policy stage that applied at that time. One row per station per hour puts all of it in one place, so any later daily or event-based analysis is a simple aggregation.

---

## 2. The pipeline in one picture

```
 OpenAQ archive (AWS, 15-min CPCB records)              NASA FIRMS (VIIRS detections)
   |  download_openaq_archive.py                           |  (downloaded by request 829739)
   |  build_station_table.py  -> stations.csv              |  build_fire_features.py  -> fire_features_daily.csv
   |  openaq_station_coverage.py -> station_coverage.csv   |  add_fire_lags.py        -> fire_features_lags.csv
   |  select_stations.py      -> stations_final.csv (54)   |  build_upwind_features.py-> fire_upwind_daily.csv  (needs ERA5 wind)
   |  build_pollution_hourly.py -> pollution_hourly.csv    |
   |                                                       |
 ERA5 (Copernicus CDS, 11 point series)                 CAQM / PIB orders (read by hand into grap_orders.csv)
   |  extract_era5_stations.py -> era5_station_hourly.csv  |  build_grap_hourly.py -> grap_hourly.csv
   |                                                       |
   +---------------------------+---------------------------+
                               |
                 build_final_dataset.py   (spine + joins + alignment + cleaning + 45 checks)
                               |
              final_dataset.csv / final_dataset.parquet   (763,344 rows x 70 columns)
                               |
                 validate_final_dataset.py  (a second, independent check)
                               |
                 notebook Phase 3 and 4  (checks, then the station-day analysis table)
```

Everything after the `data/raw/` inputs is a script, so the table can be rebuilt from scratch. Three steps are manual by nature and are recorded in `docs/provenance_log.csv`: the FIRMS download request, the ERA5 point downloads, and reading the GRAP order PDFs into `grap_orders.csv`.

---

## 3. Study window and the choice of stations

### 3.1 Why 19 Feb 2025 to 30 Sep 2026

The OpenAQ archive holds nothing for 2023 and 2024 and only fragments of 2022. The only continuous stretch of CPCB data is 19 Feb 2025 onward, so that is the window. It contains **one** winter and **one** stubble-burning season (Oct to Nov 2025). That is the single biggest limit of the whole project: any fire or policy result rests on one season.

### 3.2 From monitors to stations (`build_station_table.py`)

1. **Station lists.** The OpenAQ v3 `locations` API was queried for monitors within 25 km of central Delhi (28.61, 77.21), and within 25 km of Lucknow, Kanpur and Patna. The raw answers are saved in `data/raw/openaq_api/*.json`.
2. **Monitors only** (`isMonitor`), so sensors that are not regulatory-grade are excluded.
3. **Group.** The Delhi 25 km file is **treated** (it includes parts of Noida, Ghaziabad, Gurugram and Faridabad, all inside the GRAP area); Lucknow, Kanpur and Patna are **control** (outside the NCR, so GRAP does not apply to them).
4. **Sub-area** from the station name: Noida, Ghaziabad, Gurugram, Faridabad, otherwise Delhi; the control cities keep their own name.
5. **Validation station.** AirNow station 8118 reports PM2.5 only and is end-stamped. It is moved to its own file (`stations_validation_airnow.csv`) and used only to check the PM2.5 timing and values. It is **not** in the final table.
6. **Exact duplicates** (same latitude and longitude to 3 decimals) are collapsed, keeping the one with more coverage days, then CPCB as provider, then more pollutants. The decisions are logged in `station_duplicates_log.csv`.
7. **Near duplicates** (closer than 1 km) are flagged in `pair_flag` for a human decision, never dropped automatically.

### 3.3 From candidates to 54 final stations (`openaq_station_coverage.py` and `select_stations.py`)

`openaq_station_coverage.py` counts, for every downloaded station, the clock hours inside the window that hold at least one non-negative PM2.5 (and PM10) reading. `select_stations.py` then applies three rules, in this order:

1. **Close pairs:** keep the member with more PM2.5 + PM10 hours (Lodhi Road 5634 over 11607; Gurugram 10921 over 10900).
2. **Coverage floor:** drop stations with PM2.5 in fewer than **70%** of the 14,136 hours (`MIN_PCT = 70`).
3. **No PM10:** keep stations without PM10 (at least 70% PM2.5) and flag them `pm10_available = False` (station 5652 in Patna).

Result: **54 stations**: Delhi 33, Ghaziabad 3, Noida 2, Gurugram 1 (treated, 39) and Patna 7, Lucknow 5, Kanpur 3 (control, 15). Every decision is in `station_selection_log.csv`.

**Why this matters.** The treated group is 85% Delhi. Results for Ghaziabad, Noida and Gurugram rest on 1 to 3 stations each; the notebook reports this in its equity and bias tables.

---

## 4. Pollution (`download_openaq_archive.py` and `build_pollution_hourly.py`)

### 4.1 Download

The OpenAQ archive is a public S3 bucket (`s3://openaq-data-archive/records/csv.gz/`), read with the AWS CLI using `--no-sign-request`, so **no API key is needed**. One daily gzipped CSV per station per day holds 15-minute CPCB records stamped in IST (+05:30). `download_openaq_archive.py` syncs years 2025 and 2026 for every station plus 8118, with 8 parallel workers (16 crashed this machine's memory). The sync is incremental, so rerunning repairs gaps.

### 4.2 Aggregation to one row per station-hour

`build_pollution_hourly.py` builds a complete grid (every station × every hour of the window, `NaN` when missing) with these rules:

- **Averaging.** Readings are grouped by IST clock hour and averaged; `n_<pollutant>` keeps the number of readings in the hour. Several sensors of the same pollutant at one station are averaged per time stamp first.
- **The one-hour label shift.** The archive stamps mark the **end** of the measuring interval (tested against AirNow 8118: after shifting back one hour, the Delhi median matches 8118 best at lag 0, r = 0.954, against 0.950 at +1 h and 0.930 at -1 h). So the hour grouped under stamp-hour H covers [H-1, H). `hour_ist` is the **start** of the hour. `stamp_hour_ist` keeps the raw stamp. `hour_utc = hour_ist - 5:30`, which falls at :30 past the UTC hour (the 30-minute gap to ERA5 is handled in section 6).
- **Quality control (PM only):** negative values to empty; PM2.5 above 1,000 and PM10 above 2,000 µg/m³ to empty; PM runs of 24 or more identical consecutive hours (flat-lines, a stuck sensor) to empty; spikes (hour-to-hour jump above 300 µg/m³) are **counted but kept**. The counts per station and pollutant are in `pollution_quality_report.csv`.
- **Network outage flag.** `network_pm25_share` is the share of the 54 stations reporting PM2.5 in that hour; `network_outage` is true when that share is below 0.5. This marks **928 of 14,136 hours (6.6%)**, i.e. 50,112 rows. All stations are empty from 11 to 20 Jan 2026, and there are shorter outages on 9 to 11 Apr 2025, 24 to 25 Jun 2026 and 28 to 29 Aug 2026. These hours are **flagged, not removed**: they are outages, not clean air, so analyses drop them by default and never set them to zero.
- **Local sensors.** Temperature, humidity and wind speed from the stations' own sensors are kept as `local_*` for checking ERA5, not for modelling.
- **Units** are recorded in `pollution_units.csv`.

The output is `pollution_hourly.csv` (777,480 rows: 55 stations including 8118, no duplicates).

### 4.3 What the unit labels really are

The archive labels NO, NO2, NOx, SO2 and CO as "ppb". That label is wrong, and the dictionary documents the evidence (CPCB's own transmission protocol plus a fit on the data): `no` and `no2` are µg/m³, `nox` is ppm (CPCB's ppb divided by 1,000), `co` is probably mg/m³ and `so2` probably µg/m³. The test: if NO and NO2 are µg/m³ and NOx is ppm, then NOx = 0.001 × (NO/1.23 + NO2/1.88). The data give a slope of 0.00099 and a correlation of 0.89, while reading NO and NO2 as ppb fits much worse. **No column is rescaled**, because a unit is a fixed multiplier and does not change ratios within a column or logs. Use the units in the dictionary, not the file's label, if a gas is compared with a standard or with another gas.

---

## 5. Weather (`extract_era5_stations.py`)

- **Source.** ERA5 hourly reanalysis on single levels, from the Copernicus Climate Data Store. Seven variables: 10 m wind (u and v), 2 m temperature, 2 m dewpoint, surface pressure, total precipitation, boundary-layer height.
- **How it was obtained.** The gridded CDS queue allows one request at a time, so the weather was downloaded as **11 single-point time series**, one for each 0.25° grid cell that holds a station (the 54 stations fall in 11 cells). Each file has 14,136 hours and no gaps. One point (28.75/77.25) was patched for 120 hours from the gridded Nov to Dec 2025 files; the two routes agree to float precision, and a gridded fixture is kept in `tests/fixtures/` so the comparison is tested without the big files.
- **Nearest cell.** Each station takes the series of its nearest 0.25° cell (about 28 km resolution), not a measurement at the station.
- **Unit conversion.** Kelvin to °C (`t2m_c`, `d2m_c`), Pa to hPa (`sp_hpa`), metres of water to mm for rain (`tp_mm`, tiny negatives from float noise clipped to 0), `wind_speed = hypot(u10, v10)`, and `wind_from_deg` = the direction the wind blows **from** (0 = north, 90 = east; calm air gives empty). Time stays in UTC; the alignment to the PM2.5 hour is made at merge time.
- **Known gap.** The point files carry no data-version flag, so which months are preliminary (ERA5T) is unknown. The dictionary states this.

Output: `era5_station_hourly.csv` (763,344 rows, 54 stations, no NaNs).

---

## 6. Time alignment: the decisions that matter most

Three data sources use three different clocks, and an error of an hour would quietly weaken every result. The alignment was therefore tested before the merge, then written as two named settings at the top of `build_final_dataset.py`.

### 6.1 Weather to the PM2.5 hour (B-1): `ERA5_STAMP_OFFSET_HOURS = 0`

`hour_ist` is the start of the PM2.5 hour, so `hour_utc` falls at :30. The ERA5 stamp in the middle of that hour is `hour_utc` rounded **up** to the whole hour: `S = hour_utc.ceil('h') + 0`.

- Instant variables (wind, temperature, dewpoint, pressure, boundary-layer height) are taken at `S`.
- ERA5 rain at stamp T is the total of the hour **ending** at T, so `tp_mm = 0.5 × tp(S) + 0.5 × tp(S + 1 h)`: half of the hour ending at the stamp plus half of the next hour, which covers the PM2.5 hour.
- `era5_time_utc` keeps the stamp used.

**Evidence** (in the plan, section "Evidence for the time alignment"): PM2.5 hour labels agree across the four cities (hourly PM2.5 changes in Lucknow, Kanpur and Patna against the Delhi median peak at lag 0 or within half an hour); PM2.5 against boundary-layer change in the morning peaks at k = 0 to +1; and the AirNow check above. Because the evidence is indirect, the notebook repeats the main model with the offset at +1 and -1 as a sensitivity run.

### 6.2 Gases and local sensors one hour back (B-10): `NONPM_ALIGN_LAG_ROWS = 1`

The raw 15-minute temperature feeds are real clock times (ERA5 temperature matches the raw stamps at lag 0 at 46 stations). But `pollution_hourly.csv` gives every channel the PM2.5 label shift, so in one row the gases and local sensors describe the hour **after** the PM2.5. The merge fixes this: for `no`, `no2`, `nox`, `so2`, `co`, `o3`, their `n_*` counts and the three `local_*` sensors, the value in the row for hour h is taken from the row for hour h-1 (a row shift is an hour shift because the spine is complete; the script checks this). `pm25`, `pm10`, `network_pm25_share` and `network_outage` stay in their row. The first hour of every station is therefore empty for those columns (54 rows). `pollution_hourly.csv` itself is unchanged, and setting the lag to 0 switches this off.

### 6.3 Fire uses the previous days only (B-4)

Every hour of IST date d gets fire values from d-1 or d-1 plus d-2. There is no same-day fire column, and the build refuses one (section 7.4).

---

## 7. Fire (`build_fire_features.py`, `add_fire_lags.py`, `build_upwind_features.py`, `fire_empty_days.py`)

### 7.1 Source

NASA FIRMS **VIIRS S-NPP 375 m** active-fire detections for a box W 73.5, S 24.5, E 86.5, N 32.5, dates 2022-01-01 to 2026-09-30 (request 829739). Two files: the archive (857,474 rows to 30 Jun 2026) and the near-real-time file (1,369 rows from 1 Jul 2026), 858,843 detections in all, no duplicates, all inside the box. Only detections with confidence **nominal or high** (`n`, `h`) are used for the main columns (`nh` in the names).

### 7.2 Daily counts around each station (`build_fire_features.py`)

- **Dates are IST.** FIRMS gives `acq_date` and `acq_time` in UTC. The script pads `acq_time` to four digits (so 620 becomes 06:20), builds the UTC time, then **adds 5 h 30 min before taking the date**. A night pass at about 19:00 to 22:00 UTC therefore falls on the **next** IST date; this was verified against an independent calculation on 11,861 time pairs (the project status records the check; its helper script is not in the repository).
- **Distance.** A `BallTree` with the haversine metric (angles in radians, distance divided by the Earth's radius 6,371.0088 km) finds every detection within 200 km of each station; 50 and 100 km are subsets of the same query. An independent brute-force test matched on 28 of 28 cases.
- **What is counted:** for each station, IST date and radius (50, 100, 200 km): the number of detections and the sum of fire radiative power (FRP, in MW), for all confidence levels and for nominal-or-high, split into whole day, day pass and night pass.
- The features are built from 17 Feb 2025 so that the lags have two earlier days to draw on.

### 7.3 Empty days: cloud or outage? (decision G1, `fire_empty_days.py`)

In the window, 22 IST dates have **no detection anywhere in the file**. A genuine "no fires" is implausible on most of them, so they are not all zeros. The rule, applied to each run of consecutive empty dates:

| Condition | Status | Value |
| --- | --- | --- |
| run of 1 or 2 days, all in June to September, and both neighbouring days have fewer than 100 detections in the whole box | `zero_assumed` (cloud) | set to **0** |
| anything else (also a run at the edge of the data) | `outage` | kept **missing** |
| any date with at least one detection | `observed` | as counted |

Result: **8 dates become 0** (5, 7, 14, 18 and 30 Jul and 25 Aug 2025; 20 Jul and 4 Aug 2026) and **14 stay missing** (for example 12 Nov 2025, 10 to 13 Mar 2026, 29 to 30 Apr 2026 and the 11 to 16 Jul 2026 run). The lag columns are **recomputed from the daily counts after this rule**, so one empty day does not empty a two-day sum for the wrong reason. The status of day d-1 goes into the table as `fire_day_status`.

### 7.4 Lags and the no-look-ahead rule (`add_fire_lags.py`)

For station s, radius r and IST date d:

- `lag1` = the value on d-1;
- `lag2` = the value on d-1 **plus** the value on d-2 (a two-day running sum, which overlaps `lag1`);
- a missing day makes every lag that uses it missing.

`lag0` (the same day) also exists in the intermediate file but must **never** reach an hourly row, because the day's satellite passes (about 13:15 IST and about 02:00 IST) come after some of the hours in it. `assert_hourly_safe` raises an error for any column not ending in `_lag1` or `_lag2`, and the build script runs it. A recount from the raw detections confirmed that every detection behind `lag1` and `lag2` is earlier than 00:00 IST of the row's date.

### 7.5 The upwind feature (`build_upwind_features.py`)

A fire only matters for a station if the wind carries its smoke there. For each station, IST date, radius (50, 100, 200 km) and half-angle theta (30, 45, 60 degrees):

1. **Daily wind.** `u10` and `v10` at the station's ERA5 cell are averaged over the 24 hours of the IST day. The **vectors** are averaged, never the angles. The wind-from direction comes from the mean vector. Days missing any wind hour are empty. The table starts on 20 Feb 2025 because 19 Feb has no full day of wind.
2. **Bearing.** The initial great-circle bearing from the station to each detection (cross-checked by a second method using 3-D unit vectors).
3. **Upwind.** A detection counts when its bearing is within ±theta of the wind-from direction (the smallest angle across the 0/360 wrap).
4. **Output.** `fire_upwind_daily.csv`: 285,768 rows (54 stations × 588 dates × 3 radii × 3 thetas), for counts and FRP.

**Primary setting: 100 km and 45 degrees** (decision G4). It was chosen **from detection counts only, before looking at any link to pollution**: at 50 km, 41% of station-days have no detection; at 100 km, 27% (median 3); at 200 km, 17% but a 200 km cone spans several air-sheds. 100 km is the smallest radius with usable counts and 45 degrees is the middle of the 30/45/60 set. The other eight combinations stay in the upwind table for the sensitivity runs. Across the window the mean upwind count at 100 km and 45 degrees is 3.03 a day, against 10.59 in all directions.

**One-day shift.** The upwind table holds same-day values (the wind of day d with the detections of day d). In the final table the value of date d-1 is stored under date d (`upwind_lag1`), so an hourly row sees only the previous day. Because of this the upwind columns are also empty on 19 and 20 Feb 2025.

**Near-real-time data.** FIRMS data from 1 Jul 2026 is preliminary and may be replaced. `fire_is_nrt` is true when the lag day (d-1) is in that period (2 Jul to 30 Sep 2026, 117,936 rows).

---

## 8. Policy (`build_grap_hourly.py`)

### 8.1 Where the orders come from

GRAP (the Graded Response Action Plan) is applied by the Commission for Air Quality Management (CAQM) through **orders**, each invoking or revoking a stage for the whole NCR. There is no table of them, so one was compiled by hand, `data/processed/grap_orders.csv` (38 rows, Sep 2024 to Oct 2026): 32 order PDFs from the CAQM site (saved in `data/raw/caqm_grap_pdfs/`, git-ignored) and 19 Press Information Bureau releases, the only source for the orders of 24 Feb to 29 Mar 2025. Each row has the order date, action (`invoke`, `revoke` or `schedule`), stage, schedule version, the source and how it was verified. The schedule chain is: Direction 83 (17 Sep 2024), amended 20 Nov 2024, revised 13 Dec 2024, modified 21 Nov 2025, revised again by Direction 104 (29 Sep 2026).

### 8.2 From orders to hours

- **Stage logic.** Invoking Stage k sets the stage in force to k. Revoking Stage k sets it to **k-1** (the orders say "revocation of Stage-III and intensifying actions under Stage-I & II"). Orders on the same date are applied in file order.
- **Hour convention.** `ts_ist` is the start of the hour and `grap_stage` is the stage in force at that instant. An hour that contains a change keeps the old stage.
- **Effective time.** Almost every order says "with immediate effect" without a time. A change takes effect at the order's stated time if there is one (only three have it), otherwise at the **PIB posting time** (an upper bound on when the order existed), otherwise at an assumed 12:00 IST.
- **Baseline.** Stage II had been in force since 22 Oct 2024 (stated in the PIB release of 24 Feb 2025), so the window starts at stage 2.

### 8.3 Uncertainty flags

| Flag | Meaning | Rows in the final table |
| --- | --- | --- |
| `grap_uncertain` | the hour is on a date whose order time is not an order time (PIB time or assumed), **or** inside the known gap 25 Feb to 6 Mar 2025, where a Stage-I revocation is missing | 51,840 |
| `grap_inferred` | the stage follows from the orders around it, not from an order naming this stretch: 19 to 23 Feb 2025 and 16 Jun to 13 Oct 2025 (no orders listed, so stage 0 is an inference) | 162,000 |

The gaps are in `data/processed/grap_gaps.csv`. The main analysis keeps both kinds of hour; a robustness run drops the uncertain ones. `build_grap_hourly.py` runs its own checks (one row per hour, no duplicates, stage between 0 and 4, every change on an order date, and so on) and exits non-zero if one fails.

### 8.4 Treated and control

GRAP applies to the whole NCR, so the stage is the same for every station. `grap_stage_applied` is `grap_stage` for **treated** stations and **0 for control** stations (decision B-5), so the control cities carry "no policy" even when the NCR is at Stage IV. The raw `grap_stage` is kept too.

### 8.5 Event-time columns (B-8)

`stage_events` finds each change of `grap_stage` in the hourly series (30 in the window: 14 up and 16 down) and adds:

- `hours_since_stage_change`: hours since the last change (0 in the hour of the change); empty before the first change (24 Feb 2025 19:00), which is 139 hours per station;
- `last_change_direction`: `up`, `down`, or `none` before the first change.

Orders that do not change the stage (such as 7 Mar 2025) give no event.

---

## 9. The merge: `build_final_dataset.py`

The script builds the table in three blocks, B1 to B3 (named after the plan's phases), then runs the checks. The key idea: **every join is a left join onto a fixed spine**, so a missing source shows up as empty cells and can never add or remove rows.

### B1: spine and pollution

1. `load_stations`: reads the 54 stations from `stations_final.csv` (station 8118 is not in it).
2. `build_spine`: the cross product of 54 stations and 14,136 hours, plus `hour_utc = hour_ist - 5:30`. This fixes the row count at **763,344**.
3. `join_pollution`: a one-to-one left join on (`station_id`, `hour_ist`); it exits if the `hour_utc` in the pollution table disagrees with `hour_ist - 5:30`.
4. `qc_gases_sensors` (**decision B-11**): `pollution_hourly.csv` cleaned PM only, so the gas and sensor columns still held instrument glitches (SO2 of 2×10¹⁶, NO of 59,000, relative humidity from -90% to 183%, temperature down to -61 °C). Values outside physical limits are set to empty **before anything else is done to them** (the limit value itself is kept):

| Column | Limits (file units) | Values set to empty |
| --- | --- | --- |
| `no` | 0 to 2000 | 91 |
| `no2` | 0 to 1000 | 32 |
| `nox` | 0 to 10 | 0 |
| `so2` | 0 to 1000 | 64 |
| `o3` | 0 to 1000 | 190 |
| `co` | 0 to 100 | 3 |
| `local_temp_c` | -10 to 55 | 102 |
| `local_rh` | 0 to 100 | 1,382 |
| `local_wind_speed` | 0 to 40 | 1 |

That is **1,865 values** out of about 5.16 million remaining. The `n_*` counts are not changed. The limits only remove impossible values; real spikes below them stay, so models should use logs or rank-based transforms for the gases.

### B2: realignment, weather, policy, calendar

5. `align_nonpm`: the one-row shift of section 6.2, after checking that the spine is complete.
6. `join_weather`: the stamp rule and rain average of section 6.1; `era5_time_utc` records the stamp. Weather is empty only for the first 5 hours of 19 Feb 2025 (270 rows), because the ERA5 table starts at 00:00 UTC.
7. `load_grap` and `join_policy`: stage events, then the join on `hour_ist` (same for every station) and `grap_stage_applied`.
8. `add_calendar`: `hour`, `weekday` (0 = Monday), `month`, `season` (winter Dec to Feb, summer Mar to May, monsoon Jun to Sep, post-monsoon Oct to Nov), and festival flags.

**Festivals (decision G3).** Only festivals that plausibly change local emissions: Holi (14 Mar 2025 and 4 Mar 2026, with Holika Dahan the day before), Dussehra (2 Oct 2025), Diwali (20 Oct 2025) and New Year's Eve (31 Dec 2025, a fixed date). `festival_day` is the date itself; `festival_window` runs from the day before to the day after; `festival` names it, or says `none`. Dates were confirmed against the Delhi government notifications No.F.53/689/GAD/CN/2024-25 (holidays 2025) and No.F.53/812/GAD/CN/2025 of 04.12.2025 (holidays 2026); one secondary list gave Holi 2026 as 3 Mar, which is Holika Dahan in the official notification, so the official dates are used. Chhath Puja and Eid were left out on purpose. **There is one Diwali and one Dussehra in the window**, so any festival effect rests on a single occurrence. Text columns use `none` instead of blank, so the CSV reads back with one type per column.

### B3: fire

9. `date_status` (the G1 rule of section 7.3), then `fire_lags_wide` (daily counts with the rule applied, lags recomputed, pivoted to one column per radius) and `upwind_lag1` (the main setting, moved forward one day).
10. `join_fire`: attaches the values by station and the IST date of `hour_ist`, so every hour of a date carries the same values. It first calls `assert_hourly_safe`.

### Column order and output

`order_columns` fixes the order (identifiers, pollution, weather, fire, policy, calendar). The file is written **only if every check passes**; otherwise nothing is written and the script exits non-zero.

---

## 10. Checks: how we know the table is right

`build_final_dataset.py` runs **45 checks** and prints PASS or FAIL for each (the last run is in `docs/final_dataset_run_output.txt`: 45 passed, 0 failed). The expected value in each check is computed by plain index arithmetic or from the raw files, **not** by the merge code, so a bug in the merge cannot hide itself.

| Block | What is checked |
| --- | --- |
| B1 structure | 54 × 14,136 = 763,344 rows; no duplicate key; every station has every hour; station set equals `stations_final.csv` with 8118 absent; same station-hours as the pollution table; PM2.5 rows unchanged (664,591); PM and network columns equal their source |
| B-10 realignment | each of the 15 shifted columns in hour h equals the source at h-1; the first hour of every station is empty |
| B-11 limits | no value outside a limit; the number removed equals the number outside the limits in the source (1,865); PM2.5 and PM10 untouched |
| B-1 weather | the ERA5 table is a complete hourly series; instant variables equal the table at the stamp at every row; rain equals the half-and-half rule at every row; weather is empty exactly where the stamp falls outside the table (270 rows); `era5_time_utc` is set exactly where weather is present |
| Joins | no join changed the row count; unmatched rows are exactly the expected ones (weather 270, upwind 2,592, others 0) |
| Policy | `grap_stage` equals `grap_hourly.csv` at every hour; no missing values; treated equals stage and control equals 0; 30 changes (14 up, 16 down); `hours_since_stage_change` empty only before the first one |
| Fire | the dates with no detection equal the rule's empty dates; 8 cloud and 14 outage days; no lag0 or same-day column; fire columns constant within a station-date; `lag1` empty exactly after an outage day and `lag2` when d-1 or d-2 is an outage; after a cloud day `lag1` is 0; `fire_day_status` and `fire_is_nrt` as expected; **40 station-dates recounted from the raw detections** (a quarter of them next to empty days) and **30 upwind station-dates** matched |
| Ranges | pollution, weather, coordinates, stage and calendar inside physical limits; dewpoint never above temperature; counts not negative; 50 km ≤ 100 km ≤ 200 km; upwind count ≤ all-direction count |
| Calendar | `hour`, `weekday`, `month` agree with the time stamp (20 Oct 2025 is a Monday); seasons follow the month; festival rows are 5 days × 24 hours × 54 stations = 6,480 and windows 19,440 |

Further safeguards:

- **`validate_final_dataset.py`** re-derives the expectations from the dictionary and the run output with plain pandas asserts, so a file that was edited, truncated or rebuilt with other settings is caught. Exit 0 means every check passed.
- **The test suite** (`tests/`: `test_final_dataset.py`, `test_fire_empty_days.py`, `test_fire_geometry.py`, `test_grap_hourly.py`, `test_pollution_hourly.py`, `test_extract_era5_stations.py`, `test_upwind_points.py`, `test_validate_final_dataset.py`) covers each step, including one full run on the real files. During development, three deliberate faults (weather one hour late, gases not realigned, control stations given the stage) each made the script report FAIL, and three random rows were traced by hand to every source.
- **The notebook** (Phase 3) repeats structural, outage, weather, fire and policy checks on the finished file and stops if any fails.

---

## 11. Missing values and what they mean

| Group | Empty cells and why |
| --- | --- |
| Pollution | PM2.5 empty in 98,753 rows (12.9%): no reading, outage or removed by the quality rules. Of these, 50,112 rows are `network_outage` hours. The gases are empty more often (for example `nox` 358,508 and `local_wind_speed` 417,957, which only starts in Oct 2025), and also in the first hour of each station (the realignment) |
| Weather | 270 rows: the first 5 hours of 19 Feb 2025 |
| Fire | `lag1` empty on the 18,144 rows after an outage day; `lag2` empty on 24,624; upwind on 20,736 (adds 19 and 20 Feb 2025) |
| Policy | `hours_since_stage_change` empty for the 139 hours per station before the first change (7,506 cells); nothing else |
| Calendar | none |

**Missingness is not random.** The outages cluster (11 to 20 Jan 2026, about a third of that month, was empty at every station), which is why outage hours are flagged and why the notebook reports where missing data sit before using any of it.

---

## 12. How to rebuild the table

The commands below are in the order the pieces depend on each other. The README has the same commands for the fire and final steps.

```bash
# 1. stations and pollution (needs the AWS CLI; no key)
python src/build_station_table.py
python src/download_openaq_archive.py
python src/openaq_station_coverage.py
python src/select_stations.py
python src/build_pollution_hourly.py

# 2. weather (point files downloaded from the CDS into data/raw/era5_points/)
python src/extract_era5_stations.py

# 3. fire (FIRMS files in data/raw/firms/)
python src/build_fire_features.py --stations data/processed/stations_final.csv --start 2025-02-17 --end 2026-09-30 --out data/processed/fire_features_daily.csv
python src/add_fire_lags.py --features data/processed/fire_features_daily.csv --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_lags.csv
python src/build_upwind_features.py --stations data/processed/stations_final.csv --wind-days 1 --out data/processed/fire_upwind_daily.csv

# 4. policy (needs grap_orders.csv and grap_gaps.csv, compiled by hand)
python src/build_grap_hourly.py

# 5. the final table (writes CSV and Parquet only if all 45 checks pass)
python src/build_final_dataset.py
python src/validate_final_dataset.py

# 6. tests
python -m pytest tests -q
```

The raw FIRMS, ERA5 point, OpenAQ archive and GRAP PDF files are git-ignored, so copy them between machines rather than requesting them again. Source URLs, request parameters, retrieval dates and row counts for every input are in `docs/provenance_log.csv`.

---

## 13. From the final dataset to the analysis tables

The final dataset is hourly. The notebook (`notebooks/air_quality_policy_impact.ipynb`) reads it in Phase 3, checks it, and in Phase 4 builds the **station-day table** that H1 and H2 use:

1. **Valid hours.** An hour is valid when PM2.5 is present and `network_outage` is false. Outage hours are dropped, never set to zero.
2. **Daily PM2.5.** The mean over valid hours for each station and IST date, kept only when the day has **at least 18 valid hours** (`MIN_VALID_HOURS = 18`). The sensitivity runs use 12 and 20 hours (saved as `analysis_station_day_min12h.parquet` and `analysis_station_day_min20h.parquet`).
3. **Daily weather and policy.** Means of the weather variables over all 24 hours (rain is the total), plus relative humidity from temperature and dewpoint (Magnus formula), wind direction from the daily mean wind vector and its sine and cosine, the highest stage of the day (`stage_max`) and the stage at 12:00 (`stage_noon`).
4. **Daily fire and calendar.** The fire columns are constant within a date, so the first value of the day is taken; weekday, month, season and festival likewise.
5. **Result.** `analysis_station_day.parquet`: **26,725 rows × 45 columns**, one row per station-day with PM2.5, weather, fire and policy together. A group-day table (treated and control means, with an approximate 95% band over stations; at least half the stations needed) is built from it.

Dropped days are linked to outages, so the notebook reports the share of dropped days that contain an outage hour against the share of kept days.

---

## 14. Limits of the dataset (read before using it)

- **One winter, one burning season.** Any test of a fire or GRAP effect has low statistical power. Nov 2025 to Jan 2026 holds almost all of Stage III and IV.
- **Fire is an incomplete measure.** The satellite sees a place only when it passes overhead, and cloud can hide fires, so counts are a lower bound. The upwind feature uses a daily mean wind at about 28 km resolution and a straight cone; it is **not a trajectory model**. 14 outage days are missing, not zero.
- **Weather is the nearest ERA5 cell**, not a measurement at the station. The timing between PM2.5 and weather rests on indirect evidence, which is why the offset is a setting with sensitivity runs.
- **GRAP timing is uncertain.** Orders rarely give a time of day, so 51,840 rows are `grap_uncertain` and 162,000 `grap_inferred`. One Stage-I revocation (25 Feb to 6 Mar 2025) is missing. The stage is also **called because pollution is high**, so a plain correlation of PM2.5 with stage looks positive; use the control group.
- **Treated and control are not twins.** 39 against 15 stations, treated 85% Delhi, and the control cities differ in weather and fire exposure.
- **Gas units** are labelled ppb in the archive but are not (section 4.3); CO and SO2 units are probable, not confirmed. The OpenAQ ingestion code was not found.
- **One occurrence of each festival** in the window.
- **Near-real-time fire data** from 1 Jul 2026 is preliminary.

---

## 15. Decision register (where each choice is recorded)

| ID | Decision | Where |
| --- | --- | --- |
| B-1 | Weather aligned to the PM2.5 hour, offset 0; rain half-and-half | `ERA5_STAMP_OFFSET_HOURS`, section 6.1 |
| B-2 | Keep every row and the outage flag; models drop outage hours by default | section 4.2 |
| B-3 | Keep `grap_uncertain` and `grap_inferred`; robustness run without the uncertain | section 8.3 |
| B-4 | Only `lag1` and `lag2` fire columns for hourly rows; upwind from the previous day | sections 7.4, 7.5 |
| B-5 | `grap_stage_applied` is the stage for treated and 0 for control | section 8.4 |
| B-6 | Station 8118 excluded (validation only) | section 3.2 |
| B-7 | Calendar and festival columns | section 9 (B2) |
| B-8 | Event-time columns from the real stage changes | section 8.5 |
| B-9 | Output as CSV plus Parquet | section 1 |
| B-10 | Gases and local sensors realigned one hour | `NONPM_ALIGN_LAG_ROWS`, section 6.2 |
| B-11 | Impossible gas and sensor values set to empty; unit labels documented, not rescaled | section 9 (B1), section 4.3 |
| G1 | Empty fire days: cloud (0) or outage (missing) | section 7.3 |
| G3 | Festival list and sources | section 9 (B2) |
| G4 | Primary upwind setting 100 km and 45 degrees, chosen without looking at pollution | section 7.5 |

Full wording of each decision is in `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md`.

---

## 16. Where to look for more

| Need | File |
| --- | --- |
| Every column, unit, empty count and range | `docs/final_dataset_dictionary.md` |
| Source URLs, queries and retrieval dates | `docs/provenance_log.csv` |
| Design decisions and evidence for alignment | `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md` |
| The last build output (45 checks) | `docs/final_dataset_run_output.txt` |
| The independent validation output | `docs/validation_run_output.txt` |
| Upwind build output | `docs/upwind_run_output.txt` |
| GRAP hourly flag columns | `docs/grap_hourly_dictionary.md` |
| Pollution hourly columns | `docs/pollution_hourly_dictionary.md` |
| What is done and what is left | `docs/project_status.md` |
| The analysis notebook | `notebooks/air_quality_policy_impact.ipynb` |
