# Manya Awasthi (MA): work done and work left

Role: problem definition, data quality, MLOps. Reviewer for all my work: RS. Backup: RS.
Plan this follows: `docs/FINAL_DELIVERABLE_PLAN.md` (task cards in section 4.2). Last updated 13 Nov 2026.
Branch: `manya_work`. MK's H1 results are on `origin/mehak/h2-review` (built on RB's `reia/h2-work`); that branch is not merged into mine yet.

## 1. Status at a glance

| Task | What | Status | Reviewer sign-off |
| --- | --- | --- | --- |
| Final dataset | Built and merged (763,344 rows, 70 columns, 54 stations) | Done (before this branch) | n/a |
| M3 | Pollution EDA, figures F1 to F6, data-quality section | EDA done (reported by me); **code and figures not yet in the repo** | Not started |
| T0.3 | `docs/work_log/`, template, branch | Done | Pending RS |
| M2 | Data validation script, tests, saved run output | Done | Pending RS |
| M1 | Stakeholder and KPI page, KPI baseline script | Done | Pending RS |
| M4 | Monitoring and drift (F16) | Done on MK's T04e (input drift and model error, thresholds fixed first) | Pending RS |
| G4 | Formal H1 and H2 status from the section 5.4 rules | Done: H1 INCONCLUSIVE, H2 INCONCLUSIVE | Pending RS |
| Report sections 1, 3, 4 (my half), 8 (my part) | Drafting | Not started | n/a |
| Stage 2 slides 1 and 2 | Data preparation, EDA | Not started | n/a |
| G4, Stage 3 slide 4, review of RS, viva | Later phases | Not started | n/a |

## 2. What is done

### T0.3: work log and branch
- `docs/work_log/README.md`: the pre-task note template (plan section 9.1), branch names and review pairs.
- `docs/work_log/ma_2026-11-13_M2.md` and `ma_2026-11-13_M1.md`: pre-task notes with the options considered, the choice, the risks and the result.
- Branch `ma/validation-and-stakeholders` created.

### M2: data validation (gate G1)
- `src/validate_final_dataset.py`: 51 checks in plain pandas, prints PASS/FAIL, exit code 0 (pass), 1 (fail), 2 (file unreadable).
  Covers: row count and the 70 columns; keys unique; 54 stations x 14,136 hours with no hole; time range and `hour_utc = hour_ist - 5:30`; calendar columns;
  39 treated / 15 control; allowed category values; empty cells per column against the dictionary; value limits; PM2.5 count and the outage flag
  (928 hours, 50,112 rows, constant across stations in an hour, equal to "share < 0.5"); the January outage window; weather relations;
  **no lag0 or same-day fire column**, fire values constant within a station-date, cloud-day rule; GRAP stage per hour, `grap_stage_applied`, 30 changes,
  hours per stage; festival flags; the Stage III/IV count.
- `tests/test_validate_final_dataset.py`: 11 tests, all pass. Broken copies that must fail: dropped row, value out of range, filled empty cell, duplicate key,
  same-day fire column, wrong group, wrong outage flag, GRAP applied to a control station, bad file on the command line (exit codes 1 and 2).
- `docs/validation_run_output.txt`: saved run on the real file: 51 passed, 0 failed.
- Rest of the test suite: 71 passed, 3 skipped. Two test files cannot load on this machine because `xarray` is not installed (see section 5).

### M1: stakeholder and KPI page (BADIR: B)
- `report/01_stakeholder_and_kpis.md`: stakeholder table (CAQM, state boards and DPCC, city health departments, Punjab and Haryana agriculture departments,
  control-city boards) with the decision each makes, the linked hypothesis, and an honest "can the data support it" column; 5 KPIs with their columns; constraints; slide text.
- `src/analysis/01b_kpi_baselines.py` -> `outputs/tables/T00_kpi_baselines.csv`: baseline numbers behind the KPIs.
- `tests/test_kpi_baselines.py`: 3 tests of the valid-day and group-day rules (pass).

KPI baselines (winter sample 1 Oct 2025 to 28 Feb 2026; descriptions, not effects):

| KPI | Treated | Control |
| --- | --- | --- |
| Mean of daily mean PM2.5 (ug/m3) | 163.4 (129 valid days) | 65.1 (130 valid days) |
| Days above 60 ug/m3 | 122 of 129 (94.6%) | 87 of 130 (66.9%) |
| Valid PM2.5 station-hours, full window | 87.0% | 86.1% |
| Network outage hours, full window | 928 of 14,136 (6.6%) | same |

### M4: monitoring and drift (done after MK's tables arrived)
- Thresholds were written in `docs/work_log/ma_2026-11-13_M4.md` before any result: PSI >= 0.25 or KS D >= 0.20 flags an input-month; a model-error month is flagged above 1.5 x the reference RMSE.
- `src/analysis/05a_input_drift.py` (T09a month-matched, T09b overall) and `src/analysis/05b_model_monitoring.py` (T09c, figure F16 as PNG and SVG), `tests/test_input_drift.py` (5 tests).
- Result: no month is flagged on error (the written reference, the first three test months, includes the burning season, so this rule has little power; a post-hoc relative-error panel is labelled as such).
  Inputs drift year on year: a weather input passes PSI 0.25 in 7 of 8 comparable months (mostly dewpoint) and the fire input in 2. Drift does not by itself show the model got worse.
- `outputs/figure_registry.csv` started with F16.

### G4: formal hypothesis status (done)
- `src/analysis/20_g4_status.py` reads MK's and RB's tables, re-evaluates every plan 5.4 criterion and writes `outputs/tables/T07_hypothesis_status.csv` and `report/09_hypothesis_status.md` (text generated, no typed numbers). Note: `docs/work_log/ma_2026-11-13_G4.md`.
- **H1 = INCONCLUSIVE.** Primary +11.8% per +10 upwind detections, CI [-3.0, +28.9]; 14 of 15 checks same sign; fire model beats weather-only by 0.59% RMSE. The CI includes 0, so "supported" fails; it is far from ruling out an effect, so "not supported" fails.
- **H2 = INCONCLUSIVE.** Only one primary event (11 Nov 2025) has an adequate counterfactual: +23% [-48, +190]; placebo share 0.52; 1 of 15 checks below zero. Simulated power to see a 30% fall is 18%.
- Recomputed numbers match MK's and RB's provisional ones.

### Corrections made to the shared plan
- `docs/FINAL_DELIVERABLE_PLAN.md`, Known facts table: Stage III/IV hours inside outages are **112** (94 in the January outage, 18 in shorter ones), not "about 99".
  The January outage is 10 Jan 18:00 to 20 Jan 18:00 IST (241 hours), not "11 to 20 Jan".

## 3. What is left for me

### Can do now (needs no one else)
0. **Merge or rebase onto `origin/mehak/h2-review`** (or main once it is merged) so `20_g4_status.py` and `05b_model_monitoring.py` find T04d, T04e, T04g, T06a/e/f/g and T07a in `outputs/tables/` without `--tables-dir`.
1. **Get the EDA into the repo.** Commit the code as `src/analysis/01_eda_pollution.py` and F1 to F6 plus table T2 (missingness by station and month) in `outputs/`.
   Create `outputs/figure_registry.csv` (figure id, script, input, date, author, reviewer, status).
2. **Run the figure checklist (plan section 6.1) on F1 to F6**: title, axis units, legend, n, uncertainty, outages as grey gaps, IST, caption in the 9.2 template.
3. **Add to the EDA output:** the missingness table T2, and the outage/Stage III-IV overlap (112 hours: 94 + 18; `validate_final_dataset.py` already prints it).
4. **Draft report section 1** (problem, KPIs, hypotheses; most of it is in `report/01_stakeholder_and_kpis.md`) **and section 3** (data quality: cleaning, outliers, missing values, validation).
   Write my half of section 4 (EDA).
5. **Stage 2 slides 1 and 2:** slide 1 data preparation, slide 2 EDA (F3, F4, F6, F7).
6. **Cite sources** for the stakeholder descriptions in M1 (what CAQM, the boards and health departments decide).
7. **Commit and push** the branch and open a pull request for RS to review.

### Waits for other people
| Item | Waits for |
| --- | --- |
| M2, M1 sign-off, work-log notes | RS review |
| Missing-data choice for the EDA (drop outage hours as primary, interpolate gaps of 3 hours or less as sensitivity) | RS yes (marked DECISION in the plan) |
| Reviews of M4, G4, F16 | RS |
| F3 (PM2.5 and GRAP timeline) | RB for the stage shading and event list (B1); the data part can be built now |
| Stage 3 slide 4 (roadmap) | RB's recommendations (B4) |

### Later
- Review RS's work (R1 to R4) and F0.
- Viva preparation (plan section 8): questions on the window, time alignment, outage handling, gas unit labels.
- Final report sections 8 (my part) and 9 and 11 jointly.

## 4. Findings from this work that others should use
- Outage: all stations empty from 10 Jan 18:00 to 20 Jan 18:00 IST (241 hours); 928 outage hours in all; 112 of 971 Stage III/IV hours inside outages. (RB: event windows; MK: robustness.)
- 2,994 rows have readings counted in `n_pm25` but an empty `pm25` (emptied by the PM2.5 quality rules: above 1,000 or flat runs). `n_pm25` is a raw count, not "0 where empty". The dictionary line for `n_pm25` should say so.
- `network_pm25_share` is stored with 3 decimals (51/54 = 0.944); do not compare it exactly to a recomputed share.
- `wind_speed` equals `sqrt(u10^2 + v10^2)` only to about 1e-3, because `u10` and `v10` are stored rounded.
- H1 scale (for MK): the plan's F9 unit "per +50 upwind detections" is far outside the winter data. Treated stations in Oct 2025 to Feb 2026: median 2, 99th percentile 23, maximum 28, standard deviation about 5. Use "per +10" or "per 1 SD".

## 5. What I need from other members
- **RS:** review M2, M1 and the work log; confirm the missing-data choice; align R4's station-day rule with mine (at least 18 of 24 valid hours; a group-day counts when at least half of the group's stations are valid);
  add `xarray` (and any other missing package) to `requirements.txt`, since `tests/test_extract_era5_stations.py` and `tests/test_upwind_points.py` fail to load without it.
- **MK:** nothing blocking. MK already used "per +10". Please confirm that treated = blue (`h1_common.py`) is meant; RB's `common.py` uses treated = vermillion, control = blue, so the two sets of figures disagree.
- **RB:** event list and stage shading for F3 are on your branch (T06a, grap_events.csv); use the corrected outage window. Fix the treated/control colour clash with MK (see above).

## 6. How to rerun everything I made
```
python src/validate_final_dataset.py > docs/validation_run_output.txt   # 51 checks, needs data/processed/final_dataset.parquet
python src/analysis/01b_kpi_baselines.py                                # writes outputs/tables/T00_kpi_baselines.csv
python src/analysis/05a_input_drift.py                                  # T09a, T09b
python src/analysis/05b_model_monitoring.py                             # T09c and F16 (needs MK's T04e)
python src/analysis/20_g4_status.py                                     # T07 and report/09_hypothesis_status.md (needs MK's and RB's tables)
python -m pytest tests/test_validate_final_dataset.py tests/test_kpi_baselines.py tests/test_input_drift.py -q
```
