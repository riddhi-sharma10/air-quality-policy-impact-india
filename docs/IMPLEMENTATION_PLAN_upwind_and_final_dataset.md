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
| G3 | Festival flags had no list or source | **Settled** (dates to be checked against the official gazette) | List below |
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
| Holi (and Holika Dahan the night before) | 14 Mar 2025; 4 Mar 2026 (one source says 3 Mar, so flag 3–4 Mar 2026) | secondary lists; check the official gazette |
| Dussehra | 2 Oct 2025 (20 Oct 2026 is after the window) | secondary lists |
| Diwali | 20 Oct 2025 (8 Nov 2026 is after the window) | NDMC circular and secondary lists agree |
| New Year's Eve | 31 Dec 2025 | fixed date |

Left out on purpose: Chhath Puja and Eid (not confirmed as gazetted holidays in the sources found, and not a clear emissions driver). The window therefore contains **one** Diwali and one Dussehra, so any festival effect rests on a single occurrence; say so in the dictionary. Before the final run, confirm the dates against the Delhi government gazette (GNCTD holiday list for 2025 and 2026) and write the check date in the provenance log.

## G4: why 100 km and 45°

From `fire_features_lags.csv` over the window: at 50 km, 41% of station-days have no detection (median 1); at 100 km, 27% (median 3, 90th percentile 25); at 200 km, 17% (median 10), and a 200 km cone spans several air-sheds. 100 km is the smallest radius with usable counts. 45° is the middle of the 30/45/60 set. This was chosen from detection counts only, before looking at any link to pollution, so it is not tuned on the outcome. The 50/200 km and 30/60° versions are the sensitivity runs.

## Evidence for the time alignment (decision B-1)

ERA5 2 m temperature was compared with the stations' own temperature sensors (46 stations, about 570,000 hours):

| Join of the ERA5 stamp | Correlation | Mean absolute error |
| --- | --- | --- |
| previous on-the-hour stamp (`floor`) | 0.844 | 2.87 °C |
| next on-the-hour stamp (`ceil`) | 0.872 | 2.53 °C |

`ceil` is better, which supports B-1. Monthly mean bias runs from about −1.6 to +0.9 °C, a grid-versus-station difference, not a timing fault.

## G5: owners (to fill in)

| Work | Owner | Reviewer |
| --- | --- | --- |
| Part A: upwind fire table | Riddhi | self-check: tests plus the script's built-in checks, no second reviewer |
| Part B: merge script and final table | Riddhi | self-check: tests plus the Phase B4 checks, no second reviewer |
| Festival date check against the gazette | Riddhi | none |

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

### Phase A3: run (0.5 day)
```
python src/build_upwind_features.py --stations data/processed/stations_final.csv --wind-source table --wind-days 1 --out data/processed/fire_upwind_daily.csv
```
- Expected: 54 stations, 285,768 rows, every built-in check PASS, non-zero exit on any FAIL.
- Done when: row count matches and the script's own spot check (brute-force recount) passes.

### Phase A4: record (0.25 day)
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
| B-1 | Pollution to ERA5 time alignment | Pollution `hour_ist` covers [hour, hour + 1 h) IST. Its `hour_utc` is at :30, so the hour's midpoint is `hour_utc` + 30 min, which is an ERA5 stamp. Join the instant variables (wind, temperature, dewpoint, pressure, boundary layer height) at `hour_utc.ceil('h')`. Rain is the hour ending at the stamp, so it overlaps half the pollution hour on either side; use the same stamp and say so in the dictionary |
| B-2 | Outage hours | Keep all rows, keep `network_outage`, and let each analysis choose. The default stays "drop `network_outage` hours" in models |
| B-3 | GRAP `uncertain` and `inferred` hours | Keep both flags in the table; run the main analysis with them in and a robustness run without |
| B-4 | Fire columns allowed | Only `lag1` and `lag2` for hourly rows. Reuse `assert_hourly_safe` from `src/add_fire_lags.py`; apply the same one-day shift to upwind columns |
| B-5 | Treated and control | Use the `group` column of `stations_final.csv`; build `grap_stage_applied` = `grap_stage` for treated stations and 0 for control |
| B-6 | Station 8118 | Exclude from the final table (validation only) |
| B-7 | Calendar | `hour`, `weekday`, `month`, `season` (winter Dec–Feb, summer Mar–May, monsoon Jun–Sep, post-monsoon Oct–Nov), festival flags **as settled in G3** (Holi, Dussehra, Diwali, New Year's Eve; `festival_day` and `festival_window`). Record the gazette check in the provenance log |
| B-8 | "Before or after each order" | Add `days_since_last_order` and `post_order` columns from `grap_orders.csv` order dates |
| B-9 | Output format | `data/processed/final_dataset.csv` (git-ignored) plus a Parquet copy for speed |

## Phases

### Phase B0: decisions (0.5 day)
- Settle B-1 to B-9, with the pollution-to-ERA5 alignment (B-1) as the one the team must sign off.
- Done when: the table above has a chosen answer for each row.

### Phase B1: skeleton (0.5 day)
- Create `src/build_final_dataset.py`.
- Build the **spine**: every combination of the 54 `stations_final.csv` ids and the 14,136 hourly stamps. Left-join everything onto it, so a missing source shows up as NaN and the row count cannot change by accident.
- Join pollution first and drop 8118.
- Done when: the spine has 763,344 rows and 664,591 of them have PM2.5.

### Phase B2: weather, policy, calendar (1 day)
- Weather: parse `time_utc`, apply B-1, join on `station_id` and the aligned stamp; keep the ERA5 columns that are in the target table (`u10`, `v10`, `wind_speed`, `wind_from_deg`, `t2m_c`, `d2m_c`, `sp_hpa`, `blh_m`, `tp_mm`).
- Policy: parse `ts_ist`, join on hour; add `grap_stage_applied`, `post_order`, `days_since_last_order`.
- Calendar: hour, weekday, month, season, festival flags.
- Done when: each join leaves the row count at 763,344 and the report prints how many rows matched.

### Phase B3: fire (1 day)
- **First apply the empty-day rule (G1)** to the daily counts and recompute `lag1` and `lag2` from them (a small function, for example `src/fire_empty_days.py`, with its own test: a 1-day June gap between low days becomes 0, a 4-day March gap stays NaN). Add `fire_day_status` and keep `is_nrt`.
- Pivot `fire_features_lags.csv` to one row per station and date with columns such as `n_nh_lag1_50`, `n_nh_lag1_100`, `n_nh_lag1_200` and the `lag2` and `frp` versions.
- Join on station and the IST date of `hour_ist`. Run the `assert_hourly_safe` check on the column list before the join.
- After Part A: take the chosen upwind setting (A-4), shift it by one IST day (A-3) and join the same way. If Part A is not finished, build the table without these columns and add them in one small step later.
- Done when: no `lag0` or unshifted columns are in the table, and 19–20 Feb 2025 are the only upwind gaps.

### Phase B4: checks (0.5 day)
The script prints PASS or FAIL for each and exits non-zero on failure:
- 763,344 rows; no duplicate (`station_id`, `hour_ist`); 54 stations; 14,136 hours each.
- PM2.5 non-null count equals 664,591 (nothing lost or added by the joins).
- Every join: rows matched and unmatched, and no row multiplied (a many-to-many join would show up as extra rows).
- Missing-value summary per column group; weather and GRAP have 0 missing, fire has only the known start-of-window and no-detection-day gaps.
- Range checks (temperature, pressure, wind speed, rain).
- Fire columns: only `lag1`/`lag2` and shifted upwind.
- Spot checks: three random rows traced by hand back to each source file.
- Done when: all checks pass on the real files.

### Phase B5: tests and documents (0.5 day)
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
