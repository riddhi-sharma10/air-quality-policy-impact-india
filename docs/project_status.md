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
| **New (3 Nov 2026):** ERA5 obtained as 11 single-point series (`data/raw/era5_points/`, git-ignored, 5.9 MB) because the CDS gridded queue allows one request at a time and the web form rejects a box wider than 2 degrees of longitude. The 54 final stations fall in 11 grid cells, so this equals the nearest-cell extraction. Each file is 14,136 hours with all 7 variables and no gaps; Nov-Dec 2025 matches the gridded files to float precision. `extract_era5_stations.py` now reads them by default (`--source points`; `--source grid` keeps the old route) and wrote `era5_station_hourly.csv`: 763,344 rows, 54 stations, no NaNs | The point files carry no `expver`, so `expver` is "NA" and `era5_preliminary` is empty; the ERA5T share of the last months is unknown. The gridded `download_era5.py` route is no longer needed. Wide-box test and the 14 gridded files are dropped |

The CDS queue is the bottleneck. Today it held about 10,000 queued requests, and priority drops if you hold many at once.

## 3. FIRMS (fires): code complete; the final runs wait for the raw files and ERA5

| Done | Left |
| --- | --- |
| Request 829739 downloaded: archive file (857,474 rows, to 30 Jun 2026) and near-real-time file (1,369 rows, from 1 Jul 2026). Quality checks passed: no duplicates, all rows inside the box, plausible seasons | Rerun `build_fire_features.py` and `add_fire_lags.py` on the final 54 stations with `--stations data/processed/stations_final.csv` (commands in the README). The table now on disk used the old 56-station list and still contains the dropped duplicates 10900 and 11607. Needs the raw FIRMS files, which are not on every machine |
| `build_fire_features.py` written; independent brute-force test matched on 28 of 28 cases; `tests/test_fire_geometry.py` passes | Run `build_upwind_features.py` for the whole window once the ERA5 window files exist (it was tested only on ERA5 Delhi Jan–Jul 2022: 41 stations, 77,859 rows) |
| Night-detection date check settled: night passes are at about 19:00–22:00 UTC, so they belong to the next IST date and the conversion in the script is right. `src/check_night_dates.py` compares it with an independent calculation | Run `check_night_dates.py` once where the FIRMS files are and keep its output with the provenance log |
| Rules set: IST dates, near-real-time rows flagged, dates with no detection anywhere in the file stored as missing (NaN), not zero | Optional decision: monsoon days (Jun–Sep) with no detection anywhere are probably cloud, not an outage; they could be set to zero instead (35 of the 67 empty dates in the old table fall in July) |
| Lags built in `src/add_fire_lags.py`: `lag0`, `lag1`, `lag2` (a 2-day running sum). Only `lag1` and `lag2` may be used for an hourly reading, because `lag0` contains passes after the hour; `assert_hourly_safe` enforces this | Read the UTC-to-IST conversion (lines 78–83 of `build_fire_features.py`) and the distance query (lines 120–123) yourself and be able to explain them |
| Upwind feature built in `src/build_upwind_features.py` (radius x half-angle; u and v averaged over the day, never the angles) | |
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
| Join pollution, weather (station to nearest grid cell, aligned hour), fire (station and IST date) and policy (date and area) | Not started |
| Row count, duplicates, missing-value summary, data dictionary, provenance log | Partly: log started |
| EDA, difference-in-differences, event study, placebo tests, model, SHAP, MLflow | Not started |
| Report, slides, public GitHub repository | Not started |

## Decisions that block progress

1. Regenerate the OpenAQ key anyway, since it appeared in pasted commands (the archive pipeline does not need it).
2. Confirm the one-hour label shift for pollution (section 1) and choose the pollution-to-ERA5 time alignment.

## Suggested order

1. Regenerate the key (optional: the archive pipeline does not need it). The night-detection check is settled (section 3); run `check_night_dates.py` where the FIRMS files are to keep its output.
2. ~~Rebuild the station list on hours covered, then bulk-download OpenAQ.~~ Done (section 1).
3. Test the ERA5 wide box and submit the window requests in small batches (scripts are ready; see section 2).
4. While ERA5 queues: ~~compile the GRAP table~~ (done, section 4), rerun the fire features, run the start-versus-end test.
5. Merge, check, then analyse.

The semester ends on 24 Nov, about four weeks away. The merge needs ERA5, so submit those requests as soon as the window is settled.
