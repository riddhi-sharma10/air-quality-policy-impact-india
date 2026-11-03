# Data dictionary: `data/processed/final_dataset.csv`

One row per station per IST hour for 19 Feb 2025 to 30 Sep 2026: **54 stations × 14,136 hours = 763,344 rows, 70 columns**. Every station has every hour; missing data is an empty cell, except the two text columns that use `none` (see Missing values). It is built by `python src/build_final_dataset.py` from five inputs and written as `final_dataset.csv` (360 MB) and `final_dataset.parquet` (39 MB, the same values, faster to read). Both are git-ignored, so copy them between machines instead of downloading them. The script runs 45 checks and writes nothing if one fails; tests are in `tests/test_final_dataset.py`, `tests/test_fire_empty_days.py` and `tests/test_upwind_points.py`.

**Sources:** stations from `stations_final.csv`; pollution from `pollution_hourly.csv`; weather from `era5_station_hourly.csv` (ERA5 single-point series, nearest 0.25° cell); fire from `fire_features_daily.csv` (the lags are recomputed after the empty-day rule) and `fire_upwind_daily.csv` (FIRMS request 829739); policy from `grap_hourly.csv`; festival dates from the Delhi government holiday notifications (see `docs/provenance_log.csv`). Station 8118 (AirNow, validation only) is not in the table.

**Groups:** 39 treated stations (Delhi, Ghaziabad, Noida, Gurugram) and 15 control stations (Patna, Lucknow, Kanpur).

## Columns

### Identifiers

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `station_id` |  | OpenAQ location ID; joins to `stations_final.csv` | 0 | 17 to 234568 |
| `name` |  | Station name | 0 | 54 distinct values |
| `city` |  | `Delhi (25 km)` (monitors within 25 km of central Delhi, including those in Ghaziabad, Noida and Gurugram), `Patna`, `Lucknow` or `Kanpur` | 0 | `Delhi (25 km)`, `Kanpur`, `Lucknow`, `Patna` |
| `sub_area` |  | Delhi, Ghaziabad, Noida, Gurugram, Patna, Lucknow or Kanpur | 0 | `Delhi`, `Ghaziabad`, `Gurugram`, `Kanpur`, `Lucknow`, `Noida`, `Patna` |
| `group` |  | `treated`: inside the NCR, so GRAP applies. `control`: Patna, Lucknow and Kanpur, outside the NCR | 0 | `control`, `treated` |
| `latitude` | °N | Station location | 0 | 25.59 to 28.82 |
| `longitude` | °E | Station location | 0 | 77.03 to 85.25 |
| `hour_ist` | IST | START of the PM2.5 hour (the row for 18:00 is the PM2.5 average of 18:00 to 19:00). Primary time key together with `station_id` | 0 | 2025-02-19 00:00 to 2026-09-30 23:00 |
| `hour_utc` | UTC | `hour_ist` minus 5:30, so it falls at :30 past the UTC hour | 0 | 2025-02-18 18:30 to 2026-09-30 17:30 |

### Pollution (from `pollution_hourly.csv`)

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `pm25` | µg/m³ | PM2.5, mean of the readings in the hour. The outcome variable | 98,753 | 0 to 1000 |
| `pm10` | µg/m³ | PM10 (54 stations kept, but station 5652 has none) | 106,271 | 0 to 2000 |
| `no` | labelled ppb, probably µg/m³ | Nitric oxide. **Unit doubtful** (see Unit labels). Realigned one hour; values above 2,000 set to empty | 96,826 | 0 to 1991 |
| `no2` | labelled ppb, probably µg/m³ | Nitrogen dioxide. **Unit doubtful** (see Unit labels). Realigned one hour; values above 1,000 set to empty | 93,186 | 0 to 1000 |
| `nox` | labelled ppb, probably ppm | Nitrogen oxides. **Unit doubtful** (see Unit labels): about 1/1500 of NO + NO2. Realigned one hour | 358,508 | 0 to 3.614 |
| `so2` | labelled ppb, probably µg/m³ | Sulphur dioxide. **Unit doubtful** (see Unit labels). Realigned one hour; values above 1,000 set to empty | 177,639 | 0 to 1000 |
| `co` | labelled ppb, probably mg/m³ | Carbon monoxide. **Unit doubtful** (see Unit labels): the median is about 1. Realigned one hour; values above 100 set to empty | 93,363 | 0 to 58.12 |
| `o3` | µg/m³ | Ozone. Realigned one hour; values above 1,000 set to empty | 93,282 | 0 to 1000 |
| `n_pm25` | count | Readings averaged into `pm25` (0 = no data) | 0 | 0 to 6 |
| `n_pm10` | count | Readings averaged into `pm10` | 0 | 0 to 6 |
| `n_no` | count | Readings behind `no` (moved with it) | 54 | 0 to 6 |
| `n_no2` | count | Readings behind `no2` (moved with it) | 54 | 0 to 6 |
| `n_nox` | count | Readings behind `nox` (moved with it) | 54 | 0 to 5 |
| `n_so2` | count | Readings behind `so2` (moved with it) | 54 | 0 to 4 |
| `n_co` | count | Readings behind `co` (moved with it) | 54 | 0 to 6 |
| `n_o3` | count | Readings behind `o3` (moved with it) | 54 | 0 to 6 |
| `local_temp_c` | °C | The station's own temperature sensor (46 stations). Validation only, not a model input. Realigned one hour; values outside -10 to 55 set to empty | 193,555 | -8.447 to 51.95 |
| `local_rh` | % | The station's own relative humidity. Validation only. Realigned one hour; values outside 0 to 100 set to empty | 185,085 | 0 to 100 |
| `local_wind_speed` | m/s | The station's own wind speed (from Oct 2025). Validation only. Realigned one hour; values above 40 set to empty | 417,957 | 0 to 32.9 |
| `network_pm25_share` | 0 to 1 | Share of the 54 stations with PM2.5 in that hour (same for every station in the hour) | 0 | 0 to 1 |
| `network_outage` |  | True when `network_pm25_share` is below 0.5: a network-wide outage, not clean air | 0 | true in 50,112 rows |

### Weather (ERA5, from `era5_station_hourly.csv`)

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `era5_time_utc` | UTC | The ERA5 stamp used for this row: `hour_utc` rounded up to the hour (offset 0). Empty where there is no weather | 270 | 2025-02-19 00:00 to 2026-09-30 18:00 |
| `u10` | m/s | 10 m wind, eastward component | 270 | -12.46 to 8.412 |
| `v10` | m/s | 10 m wind, northward component | 270 | -7.102 to 6.886 |
| `wind_speed` | m/s | Wind speed from `u10` and `v10` | 270 | 0.01512 to 12.48 |
| `wind_from_deg` | ° | Direction the wind blows FROM (0 = north, 90 = east) | 270 | 0.00176 to 360 |
| `t2m_c` | °C | 2 m air temperature | 270 | 4.359 to 44.85 |
| `d2m_c` | °C | 2 m dewpoint temperature | 270 | 0.4933 to 29.93 |
| `sp_hpa` | hPa | Surface pressure | 270 | 966.9 to 1018 |
| `blh_m` | m | Boundary layer height | 270 | 9.938 to 5275 |
| `tp_mm` | mm | Precipitation in the PM2.5 hour: half of the hour ending at the stamp plus half of the next hour | 270 | 0 to 24.56 |

### Fire (NASA FIRMS VIIRS, from `fire_features_lags.csv` and `fire_upwind_daily.csv`)

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `n_nh_50km_lag1` | count | VIIRS detections (confidence nominal or high) within 50 km of the station, on the previous IST date | 18,144 | 0 to 95 |
| `n_nh_50km_lag2` | count | VIIRS detections (confidence nominal or high) within 50 km of the station, summed over the previous two IST dates | 24,624 | 0 to 181 |
| `frp_nh_50km_lag1` | MW | Total fire radiative power of those detections within 50 km of the station, on the previous IST date | 18,144 | 0 to 1142 |
| `frp_nh_50km_lag2` | MW | Total fire radiative power of those detections within 50 km of the station, summed over the previous two IST dates | 24,624 | 0 to 1334 |
| `n_nh_100km_lag1` | count | VIIRS detections (confidence nominal or high) within 100 km of the station, on the previous IST date | 18,144 | 0 to 431 |
| `n_nh_100km_lag2` | count | VIIRS detections (confidence nominal or high) within 100 km of the station, summed over the previous two IST dates | 24,624 | 0 to 708 |
| `frp_nh_100km_lag1` | MW | Total fire radiative power of those detections within 100 km of the station, on the previous IST date | 18,144 | 0 to 3082 |
| `frp_nh_100km_lag2` | MW | Total fire radiative power of those detections within 100 km of the station, summed over the previous two IST dates | 24,624 | 0 to 4012 |
| `n_nh_200km_lag1` | count | VIIRS detections (confidence nominal or high) within 200 km of the station, on the previous IST date | 18,144 | 0 to 1333 |
| `n_nh_200km_lag2` | count | VIIRS detections (confidence nominal or high) within 200 km of the station, summed over the previous two IST dates | 24,624 | 0 to 2391 |
| `frp_nh_200km_lag1` | MW | Total fire radiative power of those detections within 200 km of the station, on the previous IST date | 18,144 | 0 to 8477 |
| `frp_nh_200km_lag2` | MW | Total fire radiative power of those detections within 200 km of the station, summed over the previous two IST dates | 24,624 | 0 to 1.313e+04 |
| `n_up_nh_100km_45deg_lag1` | count | Detections within 100 km whose bearing from the station lies within ±45° of the direction the wind blew from (daily mean wind), previous IST date | 20,736 | 0 to 177 |
| `frp_up_nh_100km_45deg_lag1` | MW | Fire radiative power of those upwind detections | 20,736 | 0 to 2286 |
| `fire_day_status` |  | Status of the previous IST date: `observed`, `zero_assumed` (an empty cloud day set to 0) or `outage` (an empty day kept missing) | 0 | `observed`, `outage`, `zero_assumed` |
| `fire_is_nrt` |  | True when the previous IST date is in the near-real-time (preliminary) part of the FIRMS data, from 1 Jul 2026 | 0 | true in 117,936 rows |

### Policy (CAQM GRAP, from `grap_hourly.csv`)

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `grap_stage` | 0 to 4 | GRAP stage in force in the NCR at the start of the hour (0 = none). Same for every station | 0 | 0 to 4 |
| `grap_stage_applied` | 0 to 4 | `grap_stage` for treated stations, 0 for control stations | 0 | 0 to 4 |
| `schedule_version` |  | Version of the GRAP rules in force: `13-Dec-2024`, `21-Nov-2025` or `Sep-2026` | 0 | `13-Dec-2024`, `21-Nov-2025`, `Sep-2026` |
| `grap_uncertain` |  | True when the hour is on a date whose order time is unknown or inside the missing-order gap, so the stage may be wrong around a change | 0 | true in 51,840 rows |
| `grap_inferred` |  | True when the stage follows from the orders around it, not from an order naming this stretch (19 to 23 Feb 2025; 16 Jun to 13 Oct 2025) | 0 | true in 162,000 rows |
| `hours_since_stage_change` | hours | Hours since the last change of `grap_stage` (0 in the hour of the change). Empty before the first change on 24 Feb 2025 19:00 | 7,506 | 0 to 2979 |
| `last_change_direction` |  | `up` or `down` for the last change; `none` before the first change | 0 | `down`, `none`, `up` |

### Calendar

| Column | Unit | Meaning | Empty cells | Range or values |
| --- | --- | --- | --- | --- |
| `hour` | 0 to 23 | Hour of the day, IST, start of the hour | 0 | 0 to 23 |
| `weekday` | 0 to 6 | 0 = Monday | 0 | 0 to 6 |
| `month` | 1 to 12 |  | 0 | 1 to 12 |
| `season` |  | winter Dec to Feb, summer Mar to May, monsoon Jun to Sep, post_monsoon Oct to Nov | 0 | `monsoon`, `post_monsoon`, `summer`, `winter` |
| `festival` |  | Name of the festival whose 3-day window contains the date (`Holi`, `Dussehra`, `Diwali`, `New Year's Eve`), else `none` | 0 | `Diwali`, `Dussehra`, `Holi`, `New Year's Eve`, `none` |
| `festival_day` |  | True on the festival date itself (IST date) | 0 | true in 6,480 rows |
| `festival_window` |  | True from the day before to the day after the festival | 0 | true in 19,440 rows |

## How the time columns line up
- **The PM2.5 hour is the reference.** `hour_ist` is the start of the hour. In the pollution file the one-hour label shift is right for the hourly PM2.5 numbers (a value stamped H is the average of the hour before H).
- **Weather (decision B-1).** ERA5 stamps are on the hour in UTC and `hour_utc` is at :30, so the stamp in the middle of the PM2.5 hour is `hour_utc` rounded up (setting `ERA5_STAMP_OFFSET_HOURS = 0`). Rain is the hour ending at a stamp, so `tp_mm` averages the stamp and the next one. Timing checks against ERA5 and across the four cities support this for PM2.5. For a robustness check, rerun the model with the offset at +1 and −1.
- **Gases and the stations' own sensors (decision B-10).** Their raw stamps are real clock times, but the pollution file gives every channel the PM2.5 label, so in the pollution file those columns describe the hour after the PM2.5 in the same row. In this table they are taken from the row one hour earlier (`NONPM_ALIGN_LAG_ROWS = 1`) so that every column in a row describes the same hour. The first hour of each station is empty for them. `pm25`, `pm10`, `network_pm25_share` and `network_outage` stay in their row. `pollution_hourly.csv` itself is unchanged.
- **Fire and the upwind feature use the previous days only.** Every hour of IST date d gets the fire values of d−1 (`lag1`) or d−1 plus d−2 (`lag2`), so no detection after the hour can explain a reading. The upwind columns are the previous day's same-day values. There are no lag-0 or same-day fire columns; the build refuses them.

## Unit labels in the archive: the gas columns are unit-doubtful
The archive labels NO, NO2, NOx, SO2 and CO as ppb. Two checks on the data show that this cannot be right for CO and NOx, and probably not for NO, NO2 and SO2 either:

- **CO:** the median is 0.88 and the 99th percentile 4.74 in file units. About 1 ppb is impossible for urban air (even clean background air holds about 100 ppb), while about 1 is normal in mg/m³, the unit Indian pollution control boards use for CO.
- **NOx against NO + NO2:** row by row, NOx = 0.00066 × (NO + NO2) (correlation 0.88; per-station slope 0.00046 to 0.00102, median 0.00066). If NO and NO2 were in ppb and NOx in ppm, the slope would be 0.001. If NO and NO2 are in µg/m³ and NOx in ppm it should be about 0.0006 to 0.0007, because 1 ppb of NO2 is 1.88 µg/m³ and 1 ppb of NO is 1.23 µg/m³. The data fit the second case.
- **Conclusion (inferred, not confirmed):** `co` is probably mg/m³, `nox` probably ppm, and `no`, `no2` and `so2` probably µg/m³, the units the Indian boards report. `o3` is labelled µg/m³ and agrees with that. Confirming it needs the original CPCB files or OpenAQ's notes on how it ingests them; I found neither.
- **What it affects:** a unit is a fixed multiplier, so changes, ratios within one column, logs and standardised values are not affected. It does matter when a gas is compared with a standard or with another gas, so do not do that with these columns. No column is rescaled in this table.
- **Where the usual Indian units come from:** the UPPCB report to the National Green Tribunal in OA 725 of 2022 (CAAQMS CO in mg/m³, other gases and PM in µg/m³) and CPCB-derived public sites that state 'µg/m³, CO in mg/m³'.

## Cleaning done in this table (decision B-11)
`pollution_hourly.csv` cleaned PM only (negatives, PM2.5 above 1,000, PM10 above 2,000, flat runs). The gas and sensor columns still held instrument glitches, for example SO2 of 2×10¹⁶ ppb, NO of 59,000 ppb, relative humidity from −90 % to 183 % and temperatures down to −61 °C. In this table, values outside these limits are set to empty before anything else is done to them (the limit itself is kept):

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

That is 1,865 values in all, out of about 5,160,695 that remain. The reading counts (`n_*`) are not changed. `pollution_hourly.csv` itself is unchanged. The limits only remove impossible values; real spikes below them stay, so models should still use robust methods (logs or rank-based transforms) for the gases.

## Missing values and what they mean
- **Pollution:** as in `pollution_hourly.csv`. PM2.5 is present in 664,591 of 763,344 rows (87.1%). 50,112 rows (928 hours × 54) are network-wide outage hours, flagged in `network_outage`, not removed; the default for analysis is to drop them.
- **Weather:** empty only for the first 5 hours of 19 Feb 2025 (270 rows), because the weather table starts at 00:00 UTC. `era5_time_utc` is empty on the same rows.
- **Gases and local sensors:** empty also in the first hour of each station (54 rows), from the one-hour realignment.
- **Fire:** the FIRMS file has no detection at all on 22 IST dates in the window. The rule (decision G1): an empty run of 1 or 2 days in June to September whose neighbouring days both have fewer than 100 detections is cloud, so the value is 0 (8 dates); every other empty date is an outage and stays missing (14 dates). Rows with `fire_day_status` `outage` (18,144) have empty `lag1`; `lag2` is also empty when the day before that was an outage. `lag1` after a cloud day is 0 (`zero_assumed`: 10,368 rows). Empty `n_nh_100km_lag1` rows: 18,144; `n_nh_100km_lag2`: 24,624.
- **Upwind:** also empty on 19 and 20 Feb 2025, because the weather table starts at 05:30 IST on 19 Feb, so there is no full day of wind before 20 Feb and the previous-day value is missing for 19 and 20 Feb (20,736 rows in total).
- **Near-real-time:** `fire_is_nrt` is true for 117,936 rows (2 Jul to 30 Sep 2026); the FIRMS data from 1 Jul 2026 is preliminary and may be replaced.
- **Policy:** `grap_stage` and the flags have no empty cells. `hours_since_stage_change` is empty for the 139 hours per station before the first stage change; `last_change_direction` says `none` there. The window has 30 stage changes.
- **Text columns never have empty cells.** `festival` and `last_change_direction` say `none` instead of leaving a blank, so the file reads back with one type per column.

## Using it
- **Time keys:** parse `hour_ist` and `hour_utc` as datetimes before joining to anything. `grap_hourly.csv` writes `ts_ist` without seconds and `pollution_hourly.csv` writes `hour_ist` with seconds, so a text join matches nothing.
- **Treatment:** use `group` and `grap_stage_applied`. GRAP applies to the whole NCR, so there is no per-station policy flag. 51,840 rows are `grap_uncertain` and 162,000 are `grap_inferred`; keep them in the main run and repeat the analysis without the uncertain ones.
- **Event studies:** `hours_since_stage_change` and `last_change_direction` locate each hour relative to the last stage change. Orders that do not change the stage (such as 7 Mar 2025) give no event.
- **The stage is called because pollution is high**, so a plain correlation of PM2.5 with `grap_stage` looks positive. Use it with the control group, not on its own.
- **Sensor columns** (`local_*`) are for checking the weather, not for modelling.

## Limits
- **One burning season.** The window has only one stubble-burning season (October to November 2025), so any test of a fire effect has low statistical power.
- **One occurrence of each festival** in the window (Diwali 20 Oct 2025, Dussehra 2 Oct 2025, Holi twice). `festival_day` covers 6,480 rows and `festival_window` 19,440 rows.
- **Fire is an incomplete measure.** The satellite sees a place only when it passes overhead and cloud can hide fires; the upwind feature is approximate (0.25° daily mean wind) and is not a trajectory model.
- **Policy variation sits mostly in one winter** (Nov 2025 to Jan 2026 holds almost all of stages III and IV).
- **Treated and control differ in size:** 39 against 15 stations, and the control cities are far from Delhi, so they differ in weather and fire exposure.
- **Weather is the nearest ERA5 cell (about 28 km)**, not a measurement at the station, and the ERA5 point files carry no data-version flag, so which months are preliminary (ERA5T) is unknown.
- **Time alignment** between PM2.5 and the weather rests on indirect evidence (see the plan, section on the timing test), which is why the offset is a setting and the analysis should include the sensitivity runs.

Plan and decisions: `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md` (B-1 to B-10, G1 to G5).
