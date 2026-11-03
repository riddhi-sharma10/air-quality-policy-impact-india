# Implementation plan: upwind fire table and final merged dataset

Written 3 Nov 2026. Covers the two items still open in the dataset status: **(A)** the upwind fire table and **(B)** the merge script and final table. The semester ends on 24 Nov, so the targets below leave about ten days for analysis.

## Where things stand

| Input | File | State |
| --- | --- | --- |
| Stations | `data/processed/stations_final.csv` (54) | done |
| Pollution | `data/processed/pollution_hourly.csv` (55 stations incl. validation station 8118) | done |
| Weather | `data/processed/era5_station_hourly.csv` (763,344 rows, UTC hours) | done, built from `data/raw/era5_points/` |
| Policy | `data/processed/grap_hourly.csv` (14,136 IST hours, flags `uncertain`, `inferred`) | done |
| Fire, same-day and lags | `fire_features_daily.csv` (95,742), `fire_features_lags.csv` (95,418) | done |
| **Fire, upwind** | `fire_upwind_daily.csv` | **old 2022 Delhi test version. Replace (Part A)** |
| **Final table** | not written | **Part B** |

Target table: one row per station per IST hour, 54 stations × 14,136 hours = **763,344 rows**. Pollution already gives 664,591 rows with PM2.5; the merge must not change that number.

---

# Before you start: gaps found and how they are settled

| # | Gap | Status | Decision |
| --- | --- | --- | --- |
| G1 | Fire days with no detection: missing or zero | **Settled** | Rule below |
| G2 | Provenance of the weather point files | **Settled** | Already in `docs/provenance_log.csv` (commit 83b4e6e): CDS time-series dataset, 11 cells, 14,136 hours, one file patched for 120 hours from the gridded Nov–Dec 2025 files |
| G3 | Festival flags had no list or source | **Settled and confirmed** against the official Delhi government notifications | List below |
| G4 | Primary upwind setting | **Settled** | 100 km, 45°, `wind_days` 1 (reason below). All 9 combinations stay in the upwind table for sensitivity checks |
| G5 | Who builds what, who reviews | **Settled** | Riddhi does all the work up to the final dataset (owner table below); no second reviewer, so the tests and checks are the safeguard |

## G1: rule for days with no fire detection

In the study window 22 IST dates have no detection anywhere in the file (3.7% of fire rows are missing because of them). They are two different things:

- **Cloud in the monsoon.** Isolated days in Jul–Aug 2025 and 2026 sit next to days with 1 to 6 detections. A true zero is plausible.
- **Satellite or data outages.** 12 Nov 2025 (neighbours 1,286 and 838), 10–13 Mar 2026 (243 before, 271 after), 29–30 Apr 2026 (440 before, 809 after), and a 6-day run 11–16 Jul 2026 (the first NRT month). A real zero is not plausible.

Rule, applied to each empty IST date:

| Condition | Treatment |
| --- | --- |
| Month is June to September **and** the empty run is 1–2 days **and** both neighbouring days have fewer than 100 detections | set the day to **0** (cloud) |
| Anything else | keep as **NaN** (outage) |

Result: 8 dates become 0 (5 Jul, 7 Jul, 14 Jul, 18 Jul, 30 Jul, 25 Aug 2025; 20 Jul, 4 Aug 2026) and 14 stay NaN. Both the 1-day and 2-day lag columns are **recomputed from the daily counts after the rule**, so one empty day no longer empties a two-day sum for the wrong reason. Carry two columns into the final table: `fire_day_status` (`observed`, `zero_assumed`, `outage`) and `is_nrt` (14,904 rows, Jul–Sep 2026, preliminary data). Where this goes in the build: Phase B3.

## G3: festival flags

Flags are in IST dates. Only festivals that plausibly change local emissions are included. Each gets `festival_day` (the day) and `festival_window` (the day before to the day after).

| Festival | Date(s) in the window | Source note |
| --- | --- | --- |
| Holi (and Holika Dahan the day before) | 14 Mar 2025 (Holika Dahan 13 Mar); 4 Mar 2026 (Holika Dahan 3 Mar) | official: gazetted holiday, Holika Dahan restricted |
| Dussehra | 2 Oct 2025 (20 Oct 2026 is after the window) | official: gazetted holiday |
| Diwali | 20 Oct 2025 (8 Nov 2026 is after the window); Naraka Chaturdasi is also 20 Oct and Govardhan Puja 22 Oct | official: gazetted holiday |
| New Year's Eve | 31 Dec 2025 | fixed date |

Left out on purpose: Chhath Puja (28 Oct 2025, a restricted holiday) and Eid (not a clear emissions driver). The window therefore contains **one** Diwali and one Dussehra, so any festival effect rests on a single occurrence; say so in the dictionary. Confirmed on 3 Nov 2026 against the Delhi government notifications: No.F.53/689/GAD/CN/2024-25 (holidays 2025) and No.F.53/812/GAD/CN/2025 dated 04.12.2025 (holidays 2026), General Administration Department, GNCT of Delhi. New Year's Eve is a fixed date and is not in either list. Both notification numbers and their links are recorded in `docs/provenance_log.csv` (done in Phase B2).

## G4: why 100 km and 45°

From `fire_features_lags.csv` over the window: at 50 km, 41% of station-days have no detection (median 1); at 100 km, 27% (median 3, 90th percentile 25); at 200 km, 17% (median 10), and a 200 km cone spans several air-sheds. 100 km is the smallest radius with usable counts. 45° is the middle of the 30/45/60 set. This was chosen from detection counts only, before looking at any link to pollution, so it is not tuned on the outcome. The 50/200 km and 30/60° versions are the sensitivity runs.

## Evidence for the time alignment (decision B-1)

ERA5 2 m temperature was compared with the stations' own temperature sensors (46 stations, about 570,000 hours):

| Join of the ERA5 stamp | Correlation | Mean absolute error |
| --- | --- | --- |
| previous on-the-hour stamp (`floor`) | 0.844 | 2.87 °C |
| next on-the-hour stamp (`ceil`) | 0.872 | 2.53 °C |

`ceil` is better than `floor`. Monthly mean bias runs from about −1.6 to +0.9 °C, a grid-versus-station difference, not a timing fault.

**Wider timing test (3 Nov 2026, before B1).** The same comparison with the ERA5 stamp moved k hours later than `ceil` (higher correlation is better):

| k | Sensor temperature, level (r, MAE in °C) | Sensor temperature, hourly changes (r) |
| --- | --- | --- |
| −1 | 0.844, 2.87 | 0.273 |
| 0 | 0.872, 2.53 | 0.338 |
| **+1** | **0.887, 2.33** | 0.392 |
| +2 | 0.887, 2.33 | **0.401** |
| +3 | | 0.367 |

The within-day pattern agrees (correlation of departures from the day's mean: 0.633 at k = −1, 0.750 at 0, 0.812 at +1). Pollutants respond to boundary-layer growth (morning, hourly changes) most strongly at k = 0 to +1 for PM2.5 (r −0.099, −0.097), at +1 for NO2 (−0.083) and at +1 to +2 for CO (−0.061, −0.062). Every check peaks later than k = 0, with a central value near +1; the cause is not settled (the CPCB hour labels may be about an hour early, or the sensors lag, or the pollutants respond late to boundary-layer growth). This is why the offset is a setting with a required sensitivity run, not a fixed choice. The mean daily temperature curves differ in shape (the minimum matches at k = 0; ERA5 peaks about an hour later), so the curves alone cannot settle it. It also reopens one item in the status doc ("re-check the shift against ERA5 temperature"): the one-hour label shift made with AirNow station 8118 stays as built, and B-1 handles the remaining offset against ERA5.

**Resolution (3 Nov 2026, before B1 was accepted).** Raw temperature feeds (46 stations, Oct to Dec 2025) were compared with ERA5 interpolated to the exact clock time, shifting the ERA5 series in 15-minute steps: the best shift is 0 for the median station (quartiles 0 to 0), so the raw stamps are real clock times, not end-of-hour labels, and none of those feeds repeats a value on four stamps. The AirNow check behind the one-hour label shift concerns the hourly PM2.5 numbers, where a value stamped H is the average of the hour before H. So the shift is right for PM2.5 and one hour too early for the 15-minute channels. Other evidence for PM2.5: hourly PM2.5 changes in Lucknow, Kanpur and Patna against the Delhi median peak at lag 0 or within half an hour of it (correlation 0.22 to 0.24), and PM2.5 changes against boundary-layer changes in the morning peak at k = 0 to +1 for Delhi (-0.119, -0.117) and at k = 0 for the other cities (-0.050). Conclusion: weather is aligned to the PM2.5 hour with offset 0 (B-1), and the other channels are moved one row (B-10). The earlier choice of offset +1 reflected the 15-minute channels, not PM2.5.

## G5: owners (to fill in)

| Work | Owner | Reviewer |
| --- | --- | --- |
| Part A: upwind fire table | Riddhi | self-check: tests plus the script's built-in checks, no second reviewer |
| Part B: merge script and final table | Riddhi | self-check: tests plus the Phase B4 checks, no second reviewer |
| Festival date check against the gazette | done 3 Nov 2026 | none |

Riddhi does all the work up to and including the final dataset, so there is no hand-off between people. With no second reviewer, the tests and the printed PASS/FAIL checks in each phase are the safeguard, and each phase is finished only when they pass on the real files.

---

# Part A: upwind fire table

## Why it is blocked

`src/build_upwind_features.py` reads only the gridded files `data/raw/era5/era5_delhi_*_instant.nc` (`load_era5`, line 44). The new weather data is single-point files, already turned into `era5_station_hourly.csv` (columns `station_id, time_utc, u10, v10, ...`). The script needs a second wind source. Its fire geometry, tests and checks stay as they are.

## Design decisions (settle in Phase A0)

| # | Decision | Recommendation |
| --- | --- | --- |
| A-1 | Where winds come from | Add `--wind-source table` (reads `era5_station_hourly.csv`) and keep `grid` for the 2022 test files, so existing behaviour and tests still work |
| A-2 | First day of the window | The table starts at 19 Feb 00:00 UTC (05:30 IST). IST day 19 Feb needs 00:30 to 23:30 IST, so it is incomplete and the script (correctly) returns NaN. Upwind therefore starts on **20 Feb 2025**. Accept this and state it; the alternative is a small extra ERA5 download for 18 Feb 18:00 to 23:00 UTC |
| A-3 | Same-day leakage | Upwind counts use detections and wind from the **same IST day**, like `lag0`, so they include passes after the hour being explained. The merge must use the **previous** IST day (`lag1`). Either add `*_lag1` columns inside the upwind script or shift in the merge. Recommended: shift in the merge, with `assert_hourly_safe`-style protection (see B-4) |
| A-4 | Which radius and angle go into the final table | **Settled (G4):** 100 km, 45°, `wind_days=1` in the main table; all 3 × 3 combinations stay in `fire_upwind_daily.csv` for sensitivity checks |

## Phases

### Phase A0: decisions (0.5 day): DONE 3 Nov 2026
- A-1 to A-4 are final as written in the table above (A-4 settled in G4).
- Checked on `era5_station_hourly.csv`: every station has 14,136 hours. Every station has a full 24-hour set of stamps for **588 IST days, 20 Feb 2025 to 30 Sep 2026**. The two incomplete days are 19 Feb 2025 (19 hours) and 1 Oct 2026 (5 hours), and the script correctly turns both into NaN, so A-2 holds.
- Expected output: 54 stations × 588 dates × 3 radii × 3 half-angles = **285,768 rows**.
- Places in `build_upwind_features.py` that read the gridded dataset and must change in Phase A1: `load_era5` (line 44), `station_wind` (line 56, uses `ds.sel`), the "inside the ERA5 box" filter in `main` (uses the dataset's lat/lon range), and the hand spot check (uses `ds.sel` to recompute the wind). The fire geometry, the counts and the other checks need no change.
- The script's default station file is the old 56-station `stations.csv`. Every run command must pass `--stations data/processed/stations_final.csv`.
- New requirement for the merge (Phase B3): the empty-day rule (G1) also applies to the upwind columns, which are NaN on dates with no detection anywhere, so the same 8 cloud days become 0 and the other 14 stay NaN before the one-day shift.

### Phase A1: code change (0.5 day): DONE 3 Nov 2026
Result: `--wind-source table|grid` (default `table`) and `--wind-table` added; `station_wind` now takes an hourly frame, shared by both sources; `grid_hourly` and `load_wind_table` added; the box filter and the hand spot check read whichever source was chosen. Verified: `--help` shows the options; the grid path reproduces the existing 2022 test table exactly (77,859 rows, identical values); the table path ran on 15 Oct to 15 Nov 2025 with 54 stations, 8 of 8 checks passing (written to a scratch file, the real output was not touched). The default source changed from grid to table, so old commands for the 2022 files need `--wind-source grid` (README update is in A4).

Plan as written:
- `build_upwind_features.py`:
  - Add `load_wind_table(path)`: read `era5_station_hourly.csv`, keep `station_id, time_utc, u10, v10`.
  - Make `station_wind` accept an hourly frame (`time_utc`, `u`, `v`) instead of an xarray dataset. The grid path builds that frame from `ds.sel(...)`, so both sources share the same daily-mean code.
  - Replace the "inside the ERA5 box" filter for the table source with "station has wind rows".
  - Fix the spot check near line 203, which recomputes wind from raw ERA5 hours, so it reads whichever source was used.
- Keep the existing rules: u and v are averaged, never the angles; a day needs all 24 hours or it is NaN; ERA5 stamps are UTC on the hour, IST day d holds the stamps 00:30 to 23:30 IST.
- Done when: `python src/build_upwind_features.py --help` shows the new option and the grid path still runs on the 2022 files.

### Phase A2: tests (0.5 day): DONE 3 Nov 2026
Result: `tests/test_upwind_points.py`, 11 tests, all pass (full suite: 37 pass). They cover the full-day mean, an incomplete day giving NaN, vectors averaged not angles, the window start (19 Feb NaN, 20 Feb first full day), the two-day mean, the wind-from convention, the table loader and its error exits, the grid helper, a table-versus-grid comparison for **all 54 stations** over 3 Nov to 28 Dec 2025 for both `wind_days` 1 and 2 (max difference 2e-5 m/s; shifting the table by 1 hour gives 0.19 m/s, so the test can fail), and one end-to-end run of the script. Also run once to scratch files, not yet written to the real output: the full table (285,768 rows, 54 stations, 20 Feb 2025 to 30 Sep 2026, no duplicates, 8 of 8 script checks pass; the 22 NaN fire dates are exactly the 22 empty days of G1) and `wind_days` 2 (285,282 rows, starts 21 Feb 2025, 8 of 8 checks pass).

Plan as written:
Add `tests/test_upwind_points.py` on small made-up frames:
- a day with 24 hours gives a mean vector, a day with 23 gives NaN;
- u and v averaged, not angles (two opposite winds give a speed near 0, not a direction);
- the first IST day of the window is NaN as in decision A-2;
- **equivalence test:** for Nov–Dec 2025, the table path and the grid path (`data/raw/era5/era5_window_2025_11-12_*.nc`) give the same `u_mean`, `v_mean` for a station. This also guards the :30 timestamp handling.
- Done when: `pytest tests` passes, including the old tests.

### Phase A3: run (0.5 day): DONE 3 Nov 2026
Result: `data/processed/fire_upwind_daily.csv` written (git-ignored) with `--wind-days 1`: 285,768 rows, 54 stations (all of `stations_final.csv`), 588 IST dates 20 Feb 2025 to 30 Sep 2026, radii 50/100/200, half-angles 30/45/60, 17 columns, no duplicate keys, no missing wind, no 2022 rows left. Exit code 0, 8 of 8 script checks PASS. Fire columns are NaN on exactly the 22 empty dates of G1 (10,692 rows = 22 × 486) and `is_nrt` is true for 44,712 rows from 1 Jul 2026. Full output saved in `docs/upwind_run_output.txt`. The earlier 2022 test table is replaced.

Plan as written:
```
python src/build_upwind_features.py --stations data/processed/stations_final.csv --wind-source table --wind-days 1 --out data/processed/fire_upwind_daily.csv
```
- Expected: 54 stations, 285,768 rows, every built-in check PASS, non-zero exit on any FAIL.
- Done when: row count matches and the script's own spot check (brute-force recount) passes.

### Phase A4: record (0.25 day): DONE 3 Nov 2026
Result: `README.md` (fire section: wind source, expected 285,768 rows, 20 Feb start, NaN dates, same-day warning, `--wind-source grid` for the 2022 files, new test command), `docs/project_status.md` (section 3 rewritten as done, G1 rule, suggested order updated) and `docs/provenance_log.csv` (row for the upwind run) updated. Full suite still 37 passed. Part A is complete.

Plan as written:
- Update `README.md` (command, expected rows), `docs/project_status.md` (fires: done), `docs/provenance_log.csv` (the point-file row already exists; add the upwind run date).
- State in the README: upwind starts 20 Feb 2025; the feature is approximate (0.25° wind, daily mean).
- Done when: the status table shows fires as complete.

---

# Part B: merge script and final table

## Inputs and keys

| Table | Key in that table | Key in the final table |
| --- | --- | --- |
| Pollution | `station_id`, `hour_ist` (start of hour, text `YYYY-MM-DD HH:MM:SS`) | `station_id`, `hour_ist` |
| Weather | `station_id`, `time_utc` | `station_id`, `hour_ist` via the alignment rule (B-1) |
| Fire lags | `station_id`, `ist_date`, `radius_km` (long) | `station_id`, `hour_ist.date` and radius, pivoted wide |
| Upwind | `station_id`, `ist_date`, `radius_km`, `theta_deg` (long) | same, one chosen setting, previous day |
| GRAP | `ts_ist` (start of hour, text `YYYY-MM-DD HH:MM`) | `hour_ist` (same for every station) |

All timestamp columns must be parsed with `pd.to_datetime` before joining; the two text formats above differ and a string join matches nothing.

## Design decisions (settle in Phase B0)

| # | Decision | Recommendation |
| --- | --- | --- |
| B-1 | Pollution to ERA5 time alignment (settled in B0: weather aligned to the PM2.5 hour with `ERA5_STAMP_OFFSET_HOURS = 0`; gases and local sensors realigned one row, B-10) | The original recommendation, kept for the record: join the instant variables at `hour_utc.ceil('h')` and rain at the same stamp. The settled answer in the Phase B0 table below replaces it (rain is now a half-and-half average of two stamps) |
| B-2 | Outage hours | Keep all rows, keep `network_outage`, and let each analysis choose. The default stays "drop `network_outage` hours" in models |
| B-3 | GRAP `uncertain` and `inferred` hours | Keep both flags in the table; run the main analysis with them in and a robustness run without |
| B-4 | Fire columns allowed | Only `lag1` and `lag2` for hourly rows. Reuse `assert_hourly_safe` from `src/add_fire_lags.py`; apply the same one-day shift to upwind columns |
| B-5 | Treated and control | Use the `group` column of `stations_final.csv`; build `grap_stage_applied` = `grap_stage` for treated stations and 0 for control |
| B-6 | Station 8118 | Exclude from the final table (validation only) |
| B-7 | Calendar | `hour`, `weekday`, `month`, `season` (winter Dec–Feb, summer Mar–May, monsoon Jun–Sep, post-monsoon Oct–Nov), festival flags **as settled in G3** (Holi, Dussehra, Diwali, New Year's Eve; `festival_day` and `festival_window`). Record the gazette check in the provenance log |
| B-8 | "Before or after each order" | Add `days_since_last_order` and `post_order` columns from `grap_orders.csv` order dates |
| B-9 | Output format | `data/processed/final_dataset.csv` (git-ignored) plus a Parquet copy for speed |

## Phases

### Phase B0: decisions (0.5 day): DONE 3 Nov 2026
All of B-1 to B-9 have a chosen answer, below. They replace the recommendations in the table above where they differ. Checked on the real files while settling them.

| # | Settled answer |
| --- | --- |
| B-1 | **Weather is aligned to the PM2.5 hour.** `hour_ist` is the start of the PM2.5 hour, so `hour_utc.ceil('h')` is the ERA5 stamp at the middle of it: **`ERA5_STAMP_OFFSET_HOURS = 0`**, one named setting at the top of `build_final_dataset.py`. Instant variables (`u10`, `v10`, `t2m_c`, `d2m_c`, `sp_hpa`, `blh_m`, wind speed and direction) at `S = hour_utc.ceil('h') + offset`; rain `tp_mm = 0.5 x tp(S) + 0.5 x tp(S + 1 h)` (the stamp at T is the hour ending at T). Keep `era5_time_utc` (the stamp S) in the table. Evidence in the section below (PM2.5 labels agree across the four cities; PM2.5 against boundary-layer change peaks at 0 to +0.5 h; the AirNow check). **Sensitivity run required in the analysis:** repeat the main model with offsets +1 and -1. **Consequence:** the first 5 hours of 19 Feb 2025 IST (270 rows) have no weather, because the table starts at 00:00 UTC; they stay NaN |
| B-2 | Keep every row. Keep `network_pm25_share` and `network_outage` (928 hours, 50,112 rows for 54 stations). Models drop `network_outage` hours by default |
| B-3 | Keep `grap_uncertain` and `grap_inferred` (renamed from `uncertain` and `inferred`). Main run keeps them, a robustness run drops `grap_uncertain` |
| B-4 | Fire columns in the table are only lag1 and lag2 (checked by `assert_hourly_safe`). Upwind uses the previous IST day. `lag1` on date d is the value on d-1; `lag2` is d-1 plus d-2 and is NaN if either day is NaN. After the G1 rule the lags are recomputed from the daily counts |
| B-5 | `group` from `stations_final.csv` (39 treated, 15 control). `grap_stage_applied` = `grap_stage` for treated, 0 for control. Keep the raw `grap_stage` as well |
| B-6 | Station 8118 is not in the table. Station list comes from `stations_final.csv`, which does not contain it (checked) |
| B-7 | `hour` (IST), `weekday`, `month`, `season`, and `festival` (the name, or `none`), `festival_day`, `festival_window` as in G3. Season: winter Dec-Feb, summer Mar-May, monsoon Jun-Sep, post-monsoon Oct-Nov |
| B-8 | Event-time columns come from the stage changes in `grap_hourly` (30 changes in the window): `hours_since_stage_change` (NaN before the first change on 24 Feb 2025 19:00) and `last_change_direction` (`up` or `down`). Orders that do not change the stage, like 7 Mar 2025, give no event |
| B-9 | `data/processed/final_dataset.csv` (git-ignored) and `final_dataset.parquet` (`pyarrow` 25.0.1 is installed) |
| B-10 | **Gases and the stations' own sensors are realigned to the PM2.5 hour.** Their raw stamps are real clock times (temperature matches ERA5 at lag 0 on the raw stamps at 46 stations), but `pollution_hourly.csv` labels every channel with the PM2.5 shift, so in one row these channels describe the hour after the PM2.5. In the merge, `NONPM_ALIGN_LAG_ROWS = 1`: for `no`, `no2`, `nox`, `so2`, `co`, `o3`, their `n_*` counts, `local_temp_c`, `local_rh` and `local_wind_speed`, the value in the row for hour h is taken from the row for hour h - 1. The first hour of each station (19 Feb 2025 00:00) is then empty for these columns. `pm25`, `pm10`, `network_pm25_share` and `network_outage` are not moved. The pollution file itself stays as built. Set the lag to 0 to switch it off |
| B-11 | **Impossible gas and sensor values are set to empty** (found 3 Nov 2026 while writing the dictionary: `pollution_hourly.csv` cleaned PM only, so SO2 reached 2e16, NO 59,000, relative humidity -90 to 183 and temperature -61). `QC_LIMITS` in `build_final_dataset.py`: no 0 to 2000, no2 0 to 1000, nox 0 to 10, so2 0 to 1000, o3 0 to 1000, co 0 to 100, local_temp_c -10 to 55, local_rh 0 to 100, local_wind_speed 0 to 40 (limits kept). Applied before the realignment; 1,865 values removed in all; `n_*` counts and `pollution_hourly.csv` unchanged. **Unit warning, not rescaled (evidence gathered 3 Nov 2026):** the archive labels all the gases ppb, but `co` has a median of about 1 (an urban background of 1 ppb is impossible; probably mg/m³) and row by row `nox` = 0.00066 x (`no` + `no2`) (correlation 0.88), which fits NO and NO2 in µg/m³ and NOx in ppm and not NO and NO2 in ppb (that would give 0.001); `so2` is probably µg/m³ too. This is inferred, not confirmed: the original CPCB files or OpenAQ's ingestion notes are needed. The dictionary labels all five gas columns unit-doubtful with the evidence; use them as relative measures only |

Verified before closing B0: every source column named in the list exists in its file (pollution, stations, weather, fire lags, upwind, GRAP); `group` has the values `treated` and `control`; radii are 50, 100 and 200; GRAP has 30 stage changes (14 up, 16 down); weather rows missing at offset 0, 1 and 2 are 270, 216 and 162; gases and local sensors lose the first hour of each station (54 rows) after B-10 (all on 19 Feb 2025 IST).

**Final column list (about 70 columns):**
- **Identifiers (9):** `station_id`, `name`, `city`, `sub_area`, `group`, `latitude`, `longitude`, `hour_ist`, `hour_utc`
- **Pollution (21):** `pm25`, `pm10`, `no`, `no2`, `nox`, `so2`, `co`, `o3`; the eight `n_*` reading counts; `local_temp_c`, `local_rh`, `local_wind_speed` (validation only, not model inputs); `network_pm25_share`, `network_outage` (the shift-helper column `stamp_hour_ist` is dropped). Gases and local sensors are realigned one row (B-10)
- **Weather (10):** `era5_time_utc`, `u10`, `v10`, `wind_speed`, `wind_from_deg`, `t2m_c`, `d2m_c`, `sp_hpa`, `blh_m`, `tp_mm`
- **Fire (16):** for radius 50, 100 and 200: `n_nh_<r>km_lag1`, `frp_nh_<r>km_lag1`, `n_nh_<r>km_lag2`, `frp_nh_<r>km_lag2` (12 columns); upwind at 100 km and 45 degrees: `n_up_nh_100km_45deg_lag1`, `frp_up_nh_100km_45deg_lag1`; `fire_day_status`, `fire_is_nrt` (true when a day used is on or after 1 Jul 2026)
- **Policy (7):** `grap_stage`, `grap_stage_applied`, `schedule_version`, `grap_uncertain`, `grap_inferred`, `hours_since_stage_change`, `last_change_direction`
- **Calendar (7):** `hour`, `weekday`, `month`, `season`, `festival`, `festival_day`, `festival_window`

**Expected missing values (for the Phase B4 checks):** weather, 270 rows (first 5 hours of 19 Feb 2025 IST, at offset 0); gases and local sensors, 54 more (first hour, from B-10); upwind lag1, the first 2 IST days (19 and 20 Feb 2025) plus days after a G1 outage date; fire lags, days that use a G1 outage date; pollution as it is today (PM2.5 present in 664,591 of 763,344 rows).

### Phase B1: skeleton (0.5 day): DONE 3 Nov 2026
Result: `src/build_final_dataset.py` (functions `load_stations`, `load_pollution`, `build_spine`, `join_pollution`; run with `python src/build_final_dataset.py`) and `tests/test_final_dataset.py` (10 tests; full suite 47 pass). On the real files: spine 763,344 rows (54 stations x 14,136 hours), no duplicate keys, every station has every hour, station 8118 absent, the spine and the pollution table hold the same station-hours, PM2.5 present in 664,591 rows (87.1%), every pollution column equals its source, 50,112 outage rows (928 hours x 54). 8 of 8 script checks pass. Check sensitivity shown: a pollution table with 100 rows removed makes the script report FAIL and exit 1. The run so far wrote only to a scratch file; the real `final_dataset.csv` is written when B2 and B3 are done.

Plan as written:
- Create `src/build_final_dataset.py`.
- Build the **spine**: every combination of the 54 `stations_final.csv` ids and the 14,136 hourly stamps. Left-join everything onto it, so a missing source shows up as NaN and the row count cannot change by accident.
- Join pollution first and drop 8118.
- Done when: the spine has 763,344 rows and 664,591 of them have PM2.5.

### Phase B2: weather, policy, calendar (1 day): DONE 3 Nov 2026
Result: `src/build_final_dataset.py` now also realigns gases and sensors (`align_nonpm`, setting `NONPM_ALIGN_LAG_ROWS = 1`, B-10), joins weather (`join_weather`, `ERA5_STAMP_OFFSET_HOURS = 0`, rain as the half-and-half average, B-1), the GRAP columns (`stage_events`, `join_policy`, `grap_stage_applied`) and the calendar and festival columns (`add_calendar`, dates from the Delhi government notifications). 54 columns, 763,344 rows. All 23 script checks pass on the real files; each expected value is recomputed by plain index arithmetic, not by the merge code: every instant weather variable and the rain at every row, every one of the 15 realigned columns, and `grap_stage` at every hour. Weather is empty only in the first 5 hours of 19 Feb 2025 (270 rows); the first hour of each station is empty for the 15 realigned columns; GRAP has no missing values; `hours_since_stage_change` is empty for 139 hours per station before the first change; 30 stage changes (14 up, 16 down); festival rows are 5 days x 24 x 54 = 6,480 and 3-day windows 19,440. Tests: 11 new unit tests (21 in `tests/test_final_dataset.py`, including one full run on the real files; the whole suite is 58 passed). Three deliberate faults (weather one hour late, gases not realigned, control stations given the stage) each made the script report FAIL. Three random rows were traced by hand to every source and all matched. The run wrote to a scratch file; the real `final_dataset.csv` is written when B3 adds the fire columns.

Plan as written:
- Realign the gas and local-sensor columns by one row per B-10 (a test: the value in the row for hour h equals the source value for hour h - 1; the first hour is empty).
- Weather: parse `time_utc`, apply B-1 (instant variables at the `ceil` stamp plus the offset of 0, rain as the half-and-half rule), join on `station_id` and the aligned stamp; keep the ERA5 columns in the B0 column list.
- Policy: parse `ts_ist`, join on hour; add `grap_stage_applied`, `post_order`, `days_since_last_order`.
- Calendar: hour, weekday, month, season, festival flags.
- Done when: each join leaves the row count at 763,344 and the report prints how many rows matched.

### Phase B3: fire (1 day): DONE 3 Nov 2026
Result: `src/fire_empty_days.py` (the G1 rule: `classify_dates`, `apply_zero_days`) and, in `src/build_final_dataset.py`, `date_status`, `fire_lags_wide`, `upwind_lag1`, `join_fire` and `check_fire`. The rule is applied to the daily counts, lag1 and lag2 are recomputed with the existing `add_lags`, the 12 lag columns are pivoted by radius (`n_nh_50km_lag1` ... `frp_nh_200km_lag2`), the upwind columns at 100 km and 45 degrees are moved forward one IST day (`n_up_nh_100km_45deg_lag1`, `frp_up_nh_100km_45deg_lag1`), and `fire_day_status` (the status of the previous day) and `fire_is_nrt` are added. Names end in `_lag1` or `_lag2` so `assert_hourly_safe` accepts them. Final table: 763,344 rows, 70 columns. All 35 script checks pass on the real files, including the dates classified by the rule (8 cloud days set to 0, 14 outage days kept missing, matching exactly the dates empty in the daily table), lag1 empty exactly after an outage day, lag2 empty exactly when d-1 or d-2 is an outage day, upwind lag1 empty exactly after an outage day or before 20 Feb 2025 (20,736 rows), lag1 equal to 0 after a cloud day, `fire_is_nrt` true for 117,936 rows (from 2 Jul 2026), every fire column constant within an IST date, 40 station-dates recounted from the raw detections (a quarter of them next to empty days) and 30 upwind station-dates traced to the upwind table. Tests: 10 in `tests/test_fire_empty_days.py` (including the real-data check of 8 and 14) and 5 new in `tests/test_final_dataset.py`; the whole suite is 73 passed. Three deliberate faults (upwind not shifted, cloud rule switched off, lag1 holding the same-day value) each made the script report FAIL. The run wrote to a scratch file; the real `final_dataset.csv` is written in B4 after the final checks, or earlier by running the script.
- **First apply the empty-day rule (G1)** to the daily counts and recompute `lag1` and `lag2` from them (a small function, for example `src/fire_empty_days.py`, with its own test: a 1-day June gap between low days becomes 0, a 4-day March gap stays NaN). Add `fire_day_status` and keep `is_nrt`.
- Pivot `fire_features_lags.csv` to one row per station and date with columns such as `n_nh_lag1_50`, `n_nh_lag1_100`, `n_nh_lag1_200` and the `lag2` and `frp` versions.
- Join on station and the IST date of `hour_ist`. Run the `assert_hourly_safe` check on the column list before the join.
- After Part A: take the chosen upwind setting (A-4), shift it by one IST day (A-3) and join the same way. If Part A is not finished, build the table without these columns and add them in one small step later.
- Done when: no `lag0` or unshifted columns are in the table. (Written before the empty-day rule: the upwind columns are also empty on the day after each of the 14 outage days, by design, 20,736 rows in all; the checks verify exactly that pattern.)

### Phase B4: checks (0.5 day): DONE 3 Nov 2026
Result: all of these are built into `src/build_final_dataset.py` and pass on the real files (43 checks): row count, duplicates, 54 stations x 14,136 hours, PM2.5 count 664,591, every join checked against its source for every row, the missing-value summary by column group, range checks (`check_ranges`: PM, temperature, dewpoint, pressure, wind, boundary layer, rain, coordinates, GRAP stage, calendar, counts not negative, fire radius ordering, upwind not above all-direction), the B-11 limits, only lag1/lag2 fire columns, and hand traces of random rows. Update 3 Nov 2026: the script now also prints a join report (rows matched and unmatched after each of the five joins) and checks it (no join changes the row count; the unmatched rows are exactly 0, 270, 0, 0 and 2,592), so it has 45 checks, and its output is saved in `docs/final_dataset_run_output.txt`. The dictionary reads its check count from that file. The script writes `data/processed/final_dataset.csv` and `final_dataset.parquet` (both git-ignored) only when every check passes; the two files hold the same values. The range checks and the dictionary found the B-11 problem, which no earlier check had looked for.

Plan as written:
The script prints PASS or FAIL for each and exits non-zero on failure:
- 763,344 rows; no duplicate (`station_id`, `hour_ist`); 54 stations; 14,136 hours each.
- PM2.5 non-null count equals 664,591 (nothing lost or added by the joins).
- Every join: rows matched and unmatched, and no row multiplied (a many-to-many join would show up as extra rows).
- Missing-value summary per column group; GRAP has 0 missing, weather only the 270 rows of B-1, fire only the start-of-window and outage-day gaps listed in B0.
- Range checks (temperature, pressure, wind speed, rain).
- Fire columns: only `lag1`/`lag2` and shifted upwind.
- Spot checks: three random rows traced by hand back to each source file.
- Done when: all checks pass on the real files.

### Phase B5: tests and documents (0.5 day): DONE 3 Nov 2026 (the README, status and provenance updates are in the commit with the dictionary)
Result: `tests/test_final_dataset.py` (28 tests besides the full real run), `tests/test_fire_empty_days.py` (10), `docs/final_dataset_dictionary.md` generated from the real file (every figure in it recomputed from the Parquet and matched), a provenance row for the final table, and the README and status updated. The whole suite passes.

Plan as written:
- `tests/test_final_dataset.py` on small made-up frames: alignment rule (a known `hour_utc` finds the right ERA5 stamp), `grap_stage_applied` for treated and control, fire shift (value on day d is the table value of day d−1), spine row count.
- `docs/final_dataset_dictionary.md`: every column, unit, source, join rule, missing-value meaning, and the alignment and leakage choices.
- `docs/provenance_log.csv`: a row for the final table, with the date and the inputs' versions.
- `README.md` and `docs/project_status.md`: the run command and the expected row count.
- Done when: `pytest tests` passes and the dictionary matches the file (recompute the numbers it quotes).

### Phase B6: hand-off (0.25 day)
- Branch, pull request, a final self-review of the diff and of the Phase B4 output (re-run it from a clean checkout), merge.
- Note the table's path and row count in the README and status file, and that it is git-ignored and must be copied, not downloaded, if anyone else needs it.

## Suggested timeline

| Day | Work |
| --- | --- |
| 4 Nov | A0, A1, B0 |
| 5 Nov | A2, A3, A4; B1 |
| 6–7 Nov | B2, B3 |
| 8 Nov | B4 |
| 9 Nov | B5, B6 |
| 10 Nov onward | EDA, difference-in-differences, event study, placebo tests |

## Risks

| Risk | Handling |
| --- | --- |
| Merge multiplies rows (long fire tables joined without pivoting) | Spine plus a row-count check after every join |
| Fire or upwind same-day values explain earlier readings | B-4 guard and a test |
| String timestamps match nothing | Parse both sides to datetime before any join; test it |
| ERA5 preliminary flag unknown for point files | State it in the dictionary; it affects at most the recent months |
| Raw files missing on someone's machine | The final table is git-ignored; copy it between machines and record the row count |
