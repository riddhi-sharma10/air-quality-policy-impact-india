# Project status: what is done and what is left

## The goal in one line

The final dataset is one table with one row per station per hour. Each row holds pollution readings, weather, fire features and the policy status for that hour. Everything below feeds that table.

**Study window under discussion:** 19 Feb 2025 to 30 Sep 2026 (589 days, 14,136 hours per station). The OpenAQ archive has nothing for 2023 and 2024, and only fragments of 2022, so this is the only continuous stretch.

## What the final table will contain

| Group | Columns | Source |
| --- | --- | --- |
| Identifiers | station ID, city, group (treated or control), sub-area, hour (UTC and IST) | station list |
| Pollution | PM2.5 and PM10 (µg/m³); NO, NO2, NOx, SO2, CO (ppb); O3 (µg/m³) | OpenAQ |
| Weather | wind u and v, wind speed and direction, temperature, dewpoint, pressure, boundary layer height, rain | ERA5 |
| Fire | detection count and total fire radiative power at 50, 100 and 200 km, plus an upwind version | FIRMS |
| Policy | GRAP stage in force, the GRAP schedule version, before or after each order | CAQM orders |
| Calendar | hour, weekday, season, festival flags | derived |

Row count: 54 stations × 14,136 hours = 763,344 rows, of which 664,591 have PM2.5 (the minimum is 100,000). The pollution part is built; the rest is still to be joined.

## 1. OpenAQ (pollution): done

| Done | Left |
| --- | --- |
| Station metadata for Delhi, Lucknow, Kanpur and Patna; `stations.csv` with 56 stations | Nothing blocking. Your sign-off on the one-hour label shift is assumed; to undo it use `stamp_hour_ist` |
| AirNow station 8118 kept as a separate validation series | Optional: if ERA5 is downloaded, re-check the shift against ERA5 temperature |
| AWS CLI works; archive layout understood | Modelling choice for outage hours: default is to drop `network_outage` hours |
| **New:** bulk download of all 56 stations plus 8118, 2025 and 2026 (`src/download_openaq_archive.py`; incremental, so rerun to repair). Parallel runs of 16 crashed on this machine's memory; 8 workers is the safe limit | Pick the pollution-to-ERA5 time alignment at the merge step |
| **New:** station list rebuilt on hours covered (`openaq_station_coverage.py` then `select_stations.py`): 54 kept (33 Delhi, 3 Ghaziabad, 2 Noida, 1 Gurugram treated; 7 Patna, 5 Lucknow, 3 Kanpur control). Decisions in `station_selection_log.csv` | |
| **New:** close pairs resolved by more hours: Lodhi Road keeps 5634 (not 11607), Gurugram keeps 10921 (not 10900). Multi-ID sites need no choice: the other R K Puram and Anand Vihar IDs stopped in 2018 to 2022. Station 5652 (Patna) has no PM10, so it is kept as PM2.5-only | |
| **New:** hourly aggregation rule set: mean of the HH:00 to HH:45 readings, `n_*` readings kept, several sensors averaged per stamp (`build_pollution_hourly.py`) | |
| **New:** start-versus-end test done: AirNow 8118 is end-stamped; after shifting `hour_ist` back one hour the Delhi median matches 8118 best at lag 0 (r 0.954, vs 0.950 at +1 h and 0.930 at −1 h) | |
| **New:** quality checks run, counts in `pollution_quality_report.csv`: negatives set empty, PM2.5 > 1000 and PM10 > 2000 set empty, PM runs of 24 or more identical hours set empty, spikes counted only. One unit per pollutant everywhere (`pollution_units.csv`) | |
| **New:** CPCB PM2.5 validated against 8118 (hourly): Delhi median r = 0.954, bias +2.3, MAE 11.7 µg/m³; single stations r = 0.75 to 0.91 | |
| **New:** output `data/processed/pollution_hourly.csv` (777,480 rows, 55 stations including 8118, no duplicates; git-ignored) and `docs/pollution_hourly_dictionary.md` | |
| **New:** tests in `tests/test_pollution_hourly.py` (3 pass) | |
| **New:** end-of-interval check on the true 15-minute feeds, using the daily temperature cycle against Delhi: phase differences from the longitude expectation are 0.08 h (Lucknow), −0.23 h (Kanpur) and 0.33 h (Patna), so no 1-hour offset. The shift applies to all four cities | |
| **New:** network outages flagged: `network_pm25_share` and `network_outage` (fewer than half the stations report) mark 928 of 14,136 hours (6.6%); 662,378 PM2.5 rows remain outside them | |

**Findings**
- Of the 54 kept stations, PM2.5 is present in 87% of hours (664,591 of 763,344 rows); PM2.5 and PM10 together in 648,525 rows. This is well above the 100,000-row minimum.
- Missing hours are not random. All stations are empty from 11 to 20 Jan 2026 (about 35% of that month), and there are shorter outages on 9 to 11 Apr 2025, 24 to 25 Jun 2026 and 28 to 29 Aug 2026. These are now flagged in `network_outage`; any model should treat them as outages and not as clean air.
- The earlier "8.5% of hours hold more than one value" is real: about 8% of Delhi PM hours change mid-hour. Averaging covers it. Gas readings change every 15 minutes, so most gas hours hold several values.
- Hour 00 IST in CPCB files has only the :45 stamp, since 00:00 to 00:30 never appear.
- PM flat-lines (24 hours or more) are rare, with the largest at stations 5626 (541 PM10 hours) and 5613 (283). The 5613 and 5626 PM10 flatlines are removed.
- `hour_utc` falls at :30 past the UTC hour, which is the 30-minute gap to ERA5.
- The OpenAQ key is not used anywhere in this pipeline (the archive is public), so regenerating it is no longer blocking.

## 2. ERA5 (weather)

| Done | Left |
| --- | --- |
| Account and licence; limits learned (7 variables cost about 1,008 per day, so at most 120 days per request); each request returns an instant and an accum file | Install `cdsapi` and set up `~/.cdsapirc` (neither is on this machine yet; keep the key out of commands and Git) |
| Delhi 2022: Jan–Apr and May–Jul downloaded, renamed and checked (2,880 and 2,208 steps, 8 × 7 grid, expver 1) | Test the wide box (N 29.5, S 25, W 76.5, E 85.75) in the CDS form: does the size bar change with the area? If rejected, split into two areas |
| `inspect_era5.py` works and exits non-zero on failure (left as is for the 2022 files) | Request the window: 7 requests, two or three at a time, with `python src/download_era5.py <period>` or `--all` (`--list` shows what is missing) |
| Understood: time is UTC; precipitation is the hour ending at the timestamp, so sum hourly values | Decide the two queued 2022 requests: Nov–Dec 2022 has no pollution data, so consider cancelling it |
| **New:** `src/era5_window.py` holds the shared settings: wide box (19 × 38 grid, covers all 56 stations), 7 request periods of at most 92 days that cover Feb 2025 to Sep 2026 with no gaps, file names | Choose the time alignment (pollution and ERA5 are 30 minutes apart); `era5_station_hourly.csv` keeps clean UTC hours so this can be decided at merge time |
| **New:** `src/download_era5.py` builds each request, downloads it, unzips and renames to `era5_window_<period>_instant.nc` and `_accum.nc`. Not yet run against the real CDS, so the unzip and rename step is untested | Run `inspect_era5_window.py` once files arrive |
| **New:** `src/inspect_era5_window.py` checks each file (variables, hours, duplicates, gaps, grid, expver, NaNs) and the joined series against the study window; exits non-zero on failure. Missing periods count as failures | Compare ERA5 with the stations' own local temperature and wind (available from Oct 2025) |
| **New:** `src/extract_era5_stations.py` takes the nearest grid cell per station and writes `data/processed/era5_station_hourly.csv`: units converted (°C, hPa, mm), wind speed, wind-from direction (same convention as the fire upwind feature), ERA5T flag `era5_preliminary`, trimmed to the study window, stations outside the box skipped | Rerun the extraction after the real files are downloaded and check the preliminary (ERA5T) row count |
| **New:** `tests/test_extract_era5_stations.py` (5 tests pass): units, rain clipping, wind speed and direction, nearest cell, request periods | |
| **New:** extraction tested on the 2022 Jan–Apr file: 118,080 rows, 41 stations, no NaNs, plausible ranges; Lucknow, Kanpur and Patna stations correctly skipped (Delhi-only box) | |
| **New:** `.gitignore` now excludes `data/processed/era5_station_*.csv` (regenerate with `extract_era5_stations.py`) | |

The CDS queue is the bottleneck. Today it held about 10,000 queued requests, and priority drops if you hold many at once.

## 3. FIRMS (fires)

| Done | Left |
| --- | --- |
| Request 829739 downloaded: archive file (857,474 rows, to 30 Jun 2026) and near-real-time file (1,369 rows, from 1 Jul 2026) | Resolve the night-detection date check (UTC against IST dates); the earlier report's two statements conflict |
| Quality checks passed: no duplicates, all rows inside the box, plausible seasons | Rerun `build_fire_features.py` for the new station list and window |
| `build_fire_features.py` written; independent brute-force test matched on 28 of 28 cases | Read lines 76, 78, 111 to 114 and 160 yourself and explain them |
| Rules set: IST dates, no-detection dates are missing and not zero, near-real-time rows flagged | Upwind-weighted feature: needs ERA5 wind and a tested direction convention |
| | Decide the lag (same day, previous 24 and 48 hours) so fires can't "explain" earlier readings |
| | Keep `fire_features_daily.csv` out of Git; document how to regenerate it |
| | State the limit that the window has only one burning season (Oct–Nov 2025) |

## 4. Policy orders (CAQM GRAP): nothing built yet

| Done | Left |
| --- | --- |
| Located the CAQM site; some order dates noted from search snippets | Compile the table from the PDFs: order date, stage, invoked or revoked, area, order number, link |
| | Cover every order from February 2025 to September 2026 (only parts have been seen so far) |
| | Record the GRAP schedule version for each order (revised 13 Dec 2024 and 21 Nov 2025) |
| | Turn the table into an hourly stage flag, including revoke and re-invoke cases |

## 5. Merging and finishing

| Step | Status |
| --- | --- |
| Join pollution, weather (station to nearest grid cell, aligned hour), fire (station and IST date) and policy (date and area) | Not started |
| Row count, duplicates, missing-value summary, data dictionary, provenance log | Partly: log started |
| EDA, difference-in-differences, event study, placebo tests, model, SHAP, MLflow | Not started |
| Report, slides, public GitHub repository | Not started |

## Decisions that block progress

1. Regenerate the OpenAQ key anyway, since it appeared in pasted commands (the archive pipeline does not need it).
2. Confirm the one-hour label shift for pollution (section 1) and choose the pollution-to-ERA5 time alignment.

## Suggested order

1. Regenerate the key and settle the night-detection check.
2. ~~Rebuild the station list on hours covered, then bulk-download OpenAQ.~~ Done (section 1).
3. Test the ERA5 wide box and submit the window requests in small batches (scripts are ready; see section 2).
4. While ERA5 queues: compile the GRAP table, rerun the fire features, run the start-versus-end test.
5. Merge, check, then analyse.

The semester ends on 24 Nov, about four weeks away. The merge needs ERA5, so submit those requests as soon as the window is settled.
