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
| AirNow station 8118 kept as a separate validation series | Done 3 Nov 2026: re-checked against ERA5 temperature. Raw 15-minute temperature stamps are real clock times, so the one-hour shift is right for the hourly PM2.5 numbers and about an hour early for gases and local sensors. The final-table merge realigns those by one row (plan B-10); `pollution_hourly.csv` is unchanged |
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
- Missing hours are not random. All stations are empty from 10 Jan 17:00 to 20 Jan 18:00 IST 2026 (242 hours, about a third of that month), and there are shorter outages on 9 to 11 Apr 2025 (61 h), 23 to 25 Jun 2026 (53 h) and 27 to 30 Aug 2026 (54 h in two runs); 928 outage hours in 170 runs in all. These are now flagged in `network_outage`; any model should treat them as outages and not as clean air.
- The earlier "8.5% of hours hold more than one value" is real: about 8% of Delhi PM hours change mid-hour. Averaging covers it. Gas readings change every 15 minutes, so most gas hours hold several values.
- Hour 00 IST in CPCB files has only the :45 stamp, since 00:00 to 00:30 never appear.
- PM flat-lines (24 hours or more) are rare, with the largest at stations 5626 (541 PM10 hours) and 5613 (283). The 5613 and 5626 PM10 flatlines are removed.
- `hour_utc` falls at :30 past the UTC hour, which is the 30-minute gap to ERA5.
- The OpenAQ key is not used anywhere in this pipeline (the archive is public), so regenerating it is no longer blocking.

## 2. ERA5 (weather): done (3 Nov 2026)

| Done | Left |
| --- | --- |
| Account and licence; limits learned (7 variables cost about 1,008 per day, so at most 120 days per request; each gridded request returns an instant and an accum file). `cdsapi` is installed and `~/.cdsapirc` is set up on this machine (the key stays out of commands and Git) | Nothing |
| Understood: time is UTC; precipitation is the hour ending at the timestamp, so sum hourly values | |
| **Weather for the study window:** 11 single-point series (`data/raw/era5_points/`, git-ignored, 5.9 MB), because the CDS gridded queue allows one request at a time and the web form rejects a box wider than 2 degrees of longitude. The 54 final stations fall in 11 grid cells, so this equals the nearest-cell extraction. Each file is 14,136 hours with all 7 variables and no gaps. `src/extract_era5_stations.py` reads them by default (`--source points`; `--source grid` keeps the gridded route) and writes `data/processed/era5_station_hourly.csv`: 763,344 rows, 54 stations, no NaNs, units converted (°C, hPa, mm), wind speed and wind-from direction | The point files carry no `expver`, so `expver` is "NA" and `era5_preliminary` is empty; which months are preliminary (ERA5T) is unknown. This is stated in the final dataset's dictionary |
| **Cross-check against the gridded route:** one gridded period (Nov-Dec 2025) was downloaded; the point series match it to float precision. The gridded values of the 11 cells are stored as a test fixture (`tests/fixtures/era5_grid_cells_2025-11-01_2025-12-31.csv`), so the comparison runs without the large gridded files | |
| Gridded route built but not needed beyond that: `src/era5_window.py`, `src/download_era5.py` (builds, downloads, unzips and renames each request) and `src/inspect_era5_window.py` (checks a file and the joined series against the study window). The other six gridded periods and the wide-box test were dropped | If any of the 2022 Delhi requests (Aug-Oct and Nov-Dec 2022) are still queued in the CDS account, cancel them; they are not used |
| Delhi 2022 test files (Jan-Apr and May-Jul): downloaded, renamed and checked (2,880 and 2,208 steps, 8 x 7 grid, expver 1); extraction tested on the Jan-Apr file: 118,080 rows, 41 stations, no NaNs, plausible ranges; Lucknow, Kanpur and Patna correctly skipped (Delhi-only box). Not used in the analysis | |
| Time alignment decided and checked against ERA5 and the stations' own sensors (plan decisions B-1 and B-10): weather is taken at the stamp in the middle of the PM2.5 hour, gases and local sensors are moved one hour; the analysis repeats the main model with the weather offset at +1 and -1 | |
| `tests/test_extract_era5_stations.py` (5 tests): units, rain clipping, wind speed and direction, nearest cell, request periods. `.gitignore` excludes `data/processed/era5_station_*.csv` (regenerate with `extract_era5_stations.py`) | |

## 3. FIRMS (fires): all three fire tables built on the final 54 stations (3 Nov 2026)

| Done | Left |
| --- | --- |
| Request 829739 downloaded: archive file (857,474 rows, to 30 Jun 2026) and near-real-time file (1,369 rows, from 1 Jul 2026). Quality checks passed: no duplicates, all rows inside the box, plausible seasons | Nothing. `build_fire_features.py` and `add_fire_lags.py` were rerun on the 54 final stations: `fire_features_daily.csv` 95,742 rows, `fire_features_lags.csv` 95,418 rows, all checks pass (commands in the README). The raw FIRMS files are git-ignored and not on every machine, so copy them rather than re-request |
| `build_fire_features.py` written; independent brute-force test matched on 28 of 28 cases; `tests/test_fire_geometry.py` passes | Nothing. The upwind step now reads the station wind table (`--wind-source table`; `grid` keeps the 2022 test route). `fire_upwind_daily.csv` is built for the whole window: 285,768 rows (54 stations x 588 dates, 20 Feb 2025 to 30 Sep 2026 x 3 radii x 3 half-angles), 8 of 8 checks pass, output in `docs/upwind_run_output.txt`. It starts on 20 Feb because IST 19 Feb has no full day of wind. 11 tests in `tests/test_upwind_points.py` pass, including table versus grid at all 54 stations (max difference 2e-5 m/s), and a 60-case recount from the raw files matched with 0 mismatches |
| Night-detection date check settled: night passes are at about 19:00–22:00 UTC, so they belong to the next IST date and the conversion in the script is right. `src/check_night_dates.py` compares it with an independent calculation | Done: `check_night_dates.py` passes (script IST date equals the independent calculation on 11,861 time pairs); output saved in `docs/night_check_output.txt` |
| Rules set: IST dates, near-real-time rows flagged, dates with no detection anywhere in the file stored as missing (NaN), not zero | Decided (plan, gap G1): of the 22 empty dates in the window, 8 become 0 (June to September, a run of 1 or 2 days, both neighbouring days under 100 detections) and 14 stay missing (outages). Applied in the merge, with `fire_day_status` and `is_nrt` carried into the final table |
| Lags built in `src/add_fire_lags.py`: `lag0`, `lag1`, `lag2` (a 2-day running sum). Only `lag1` and `lag2` may be used for an hourly reading, because `lag0` contains passes after the hour; `assert_hourly_safe` enforces this | Read the UTC-to-IST conversion (lines 78–83 of `build_fire_features.py`) and the distance query (lines 120–123) yourself and be able to explain them |
| Upwind feature built in `src/build_upwind_features.py` (radius x half-angle; u and v averaged over the day, never the angles). It holds same-day values, so the merge must use the previous IST day. Main setting 100 km and 45 degrees; the other eight combinations stay for sensitivity checks | |
| The window has only one burning season: stated in the README Limitations | |
| Fire tables are git-ignored (`data/processed/fire_*.csv`) and no longer tracked; the README gives the regeneration commands and expected row counts | |

## 4. Policy orders (CAQM GRAP): table, order PDFs and hourly flag built

| Done | Left |
| --- | --- |
| `data/processed/grap_orders.csv`: 38 rows, Sep 2024 to Oct 2026. 30 rows have the order PDF read (16 PDF only, 14 also with a PIB release), 6 have only a PIB release, 2 are references to earlier orders. Each row has the order serial (where written on the order), file name and link | The orders say "with immediate effect" and almost none gives a time of day. Only three do (the Sub-Committee meeting times on 13.12.2025 at 10:00 AM and 6:30 PM and on 17.01.2026 at 8:15 PM). For the other changes the time is the PIB posting time (an upper bound) or an assumed 12:00, so about 7% of hours are flagged `uncertain` |
| All 32 PDFs saved in `data/raw/caqm_grap_pdfs/` (git-ignored, 116 MB); source URLs are in the `pdf_url` column and the provenance log | Find the one missing order: a Stage-I revocation between 24 Feb and 7 Mar 2025 (`grap_gaps.csv`). Nothing before 2 Apr 2025 is listed on the CAQM site; no PIB release found |
| `src/build_grap_hourly.py` writes `grap_hourly.csv` (14,136 IST hours, stage 0–4, schedule version, `uncertain` and `inferred` flags); 6 self-checks and 10 tests (`tests/test_grap_hourly.py`) pass; dictionary in `docs/grap_hourly_dictionary.md` | Decide how to treat `uncertain` hours (6.8%) in the analysis; suggested: keep them in the main run and repeat without them. The 3,000 `inferred` hours (19–23 Feb and 16 Jun to 13 Oct 2025) are flagged but kept. The orders cover the whole NCR, so the merge needs a `grap_stage_applied` column (0 for the control cities) |
| Baseline: Stage-II was in force from 22 Oct 2024 until 24 Feb 2025, so the window starts at stage 2. Stage-I invoked 7 Mar, revoked 15 Mar, invoked 24 Mar, revoked 29 Mar 2025 (PIB) | Check the 15 Jun to 13 Oct 2025 stretch: no orders are listed, so stage 0 there is an inference. The 07.06 and 15.06.2025 orders show Stage-I was in force from 07.06 until 15.06 |
| Schedule chain read from the documents: Direction No. 83 of 17.09.2024, amended 20.11.2024, comprehensively revised by the order of 13.12.2024 (so the 13 Dec 2024 date was right), modified 21.11.2025, revised by Direction No. 104 of 29.09.2026 (all with immediate effect) | The 11.11.2025 Stage-III invocation (no. 1444) is only on the site as its clarification (no. 1445); the original was not found as a file |
| The 26.11.2025 order confirms Stage-III revoked while Stage-I and II stay invoked, so the stage after it is 2 | |

## 5. Merging and finishing

| Step | Status |
| --- | --- |
| Join pollution, weather (station to nearest grid cell, aligned hour), fire (station and IST date) and policy (date and area) | **Done 3 Nov 2026:** `src/build_final_dataset.py` writes `final_dataset.csv` and `.parquet` (763,344 rows, 70 columns, all checks pass (last run in `docs/final_dataset_run_output.txt`), the whole test suite passes). Plan: `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md` |
| Row count, duplicates, missing-value summary, data dictionary, provenance log | **Done:** checks are in the script, `docs/final_dataset_dictionary.md` written from the real file, provenance row added. Found and handled: impossible gas and sensor values (set to empty) and wrong unit labels on the gas columns (NO and NO2 are µg/m³ and NOx is ppm, confirmed against CPCB's protocol and a fit; CO and SO2 are probably mg/m³ and µg/m³; documented, not rescaled) |
| EDA, difference-in-differences, event study, placebo tests, model, SHAP, MLflow | Not started |
| Report, slides, public GitHub repository | Not started |

## Decisions that block progress

1. Regenerate the OpenAQ key anyway, since it appeared in pasted commands (the archive pipeline does not need it).
2. Confirm the one-hour label shift for pollution (section 1) and choose the pollution-to-ERA5 time alignment.

## Suggested order

1. Regenerate the key (optional: the archive pipeline does not need it). The night-detection check is settled (section 3); run `check_night_dates.py` where the FIRMS files are to keep its output.
2. ~~Rebuild the station list on hours covered, then bulk-download OpenAQ.~~ Done (section 1).
3. ~~Test the ERA5 wide box and submit the window requests~~ Done another way: point series (section 2).
4. ~~Compile the GRAP table, rerun the fire features, build the upwind table~~ Done (sections 3 and 4).
5. Merge (plan in `docs/IMPLEMENTATION_PLAN_upwind_and_final_dataset.md`, Part B), check, then analyse.

The semester ends on 24 Nov. All five inputs of the merge now exist; the merge script and final table are the next work.
