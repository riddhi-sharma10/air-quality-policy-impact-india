# Final notebook plan: everything after the final dataset, done from scratch

Notebook: `notebooks/air_quality_policy_impact.ipynb` (one notebook, BADIR structure, runs in Colab and locally).
Members: **MA** Manya Awasthi, **MK** Mehak Kumar, **RS** Riddhi Sharma, **RB** Reia Baid.
Follows `docs/FINAL_DELIVERABLE_PLAN.md` (methods in section 4, decision rules in 5.4, figure standards in 6). Rewritten 15 Nov 2026. **Adjust the dates to the real deadlines.** Semester ends 24 Nov, so there are 9 days.

---

## 1. The reset: what stays and what is redone

The final deliverable plan was marked done, but the EDA had not been done, and the analysis that followed was built without it. So **everything after the final dataset is redone from scratch, in the notebook, in the right order: EDA first, then the hypotheses.**

| Stays (not redone) | Redone from scratch in the notebook |
| --- | --- |
| `final_dataset.parquet` (763,344 rows, 70 columns, 54 stations) and `docs/final_dataset_dictionary.md` | Part 1 KPIs (computed live, not copied) |
| `src/validate_final_dataset.py` (51 checks on the dataset) and its tests | Part 2.3 missingness and outage description |
| The plan's **methods and decision rules** (plan sections 4, 5 and 5.4) | Part 3 EDA: F1 to F7, T2, the station-day table |
| The stakeholder text in `report/01_stakeholder_and_kpis.md` (words only; numbers come from new cells) | Part 4 H1, Part 5 H2, Part 6 status and monitoring, Part 7 recommendations |

**Earlier results are reference only.** The H1 and H2 scripts, tables and figures on `origin/mehak/h2-review` are **not inputs** to the notebook. MA's own post-dataset results (KPI baselines, drift and monitoring, hypothesis status, F16) were **removed from `manya_work` on 15 Nov** and exist only in the git history (commit `bd041f0` and earlier). Do not import them, copy their cells, or merge that branch into the working branch. Section 7 explains how they are used once, at the end, as a cross-check.

**Honest note for the report:** the team has already seen the earlier results, so the redo is a replication, not a blind test. The decision rules in plan 5.4 were frozen before and stay unchanged. Any choice that differs from the earlier pass is recorded with its reason, and the number of specifications tried is stated.

### Notebook state today

| Part | State |
| --- | --- |
| 0 Setup and 0.1 load | Built (cells 1 to 5); not yet run in Colab |
| 1 Stakeholders and KPIs | Stub |
| 2 Sources and quality | 2.1, 2.2 not written; 2.3 draft code in cell 10 |
| 3 EDA | Draft starter code for F1 to F6 in cells 12 to 31, never run, no outputs. A first draft to check, not finished work |
| 4 to 9 | Stubs |

---

## 2. Rules for the notebook (all four read this)

### 2.1 Cell pattern (every analysis block)

1. **Markdown header:** question in one line, BADIR letter, owner, reviewer, priority (M, S, C).
2. **Method note** (3 to 6 lines, written **before** fitting): outcome, sample, specification, what counts as the result. For H1 and H2 this is the frozen analysis plan (section 3).
3. **Code cell(s):** compute, then save with `save_fig("F08_lag_correlation")` or `save_table(df, "T03_h1_lag_correlations")` (names follow plan 5.3).
4. **Check cell:** an `assert` that the number on the plot equals the number in the saved table, plus a sanity check against the data (row counts, ranges).
5. **Interpretation cell:** takeaway in one sentence and one thing the output does **not** show. "Associated with", never "caused".
6. **Caption line** in the plan 9.2 template.

### 2.2 Standards

- **No typed numbers.** Every number in a markdown cell comes from a variable (`display(Markdown(f"..."))`) or a saved table.
- **Figure checklist** (plan 6.1): units, IST, legend, n, uncertainty defined, outage hours as grey gaps never interpolated, interpretation sentence.
- **Colours fixed project-wide:** treated `#D55E00`, control `#0072B2` (`COL` in cell 3). One definition, nobody redefines it.
- **No imports from `src/analysis/`.** Code is written in the notebook cells so a reader sees all of it. Shared helper functions live in one cell in Part 0 (RS owns it): `load_df()`, `valid_station_day()`, `group_day()`, `cluster_ols()`, `save_fig()`, `save_table()`.
- **Seeds:** one constant `SEED = 20261115` set in Part 0, used by every random step (bootstrap, placebo draws, simulation).
- **Valid day rule** (from plan 5.1 and 4.3 R4, fixed before EDA): valid hour = `pm25` present and not `network_outage`; valid station-day = at least 18 of 24 valid hours; a group-day counts when at least half of the group's stations are valid. Sensitivity: 12 and 20 hours.
- **Time:** IST everywhere. `hour_ist` is the START of the PM2.5 hour.
- **Units:** PM2.5 in ug/m3; gases as in the dictionary (NO and NO2 ug/m3, NOx ppm), not the archive label.

### 2.3 Avoiding merge conflicts (an `.ipynb` is one JSON file)

1. Each person works in their own part file: `notebooks/parts/part3_ma.ipynb`, `part3_rs.ipynb`, `part4_mk.ipynb`, `part5_rb.ipynb`, `part6_ma.ipynb`, `part8_rs.ipynb`. Each starts with the same Part 0 cells.
2. At each checkpoint (section 6) **RS pastes the finished cells into the master** (a 20-line `nbformat` script `tools/assemble_notebook.py`), runs all, and commits the master.
3. Nobody edits the master between checkpoints. Outputs are cleared in the weekly commits; the final master (G6) is committed with outputs and a Colab link.

### 2.4 Review pairs and gate

Pairs as in plan 1.2 (MA to RS, RS to MA, MK to RB, RB to MK). The review-before-you-start gate (plan 1.1) is shortened to fit nine days: look at the data (shape, date range, missing counts), write the pre-task note (5 lines, two options), get the **DECISION** replies, then work. A block is done when the reviewer has re-run it from a clean Colab session and the check cell passes.

---

## 3. Order of work and the frozen analysis plan

```
Part 0 setup + 3.1 station-day table
        │
        ▼
Part 3 EDA (F1 to F7, T2)  ──►  EDA findings meeting (30 min, 17 Nov)
        │                               │
        │                               ▼
        │                 FROZEN ANALYSIS PLAN (markdown cell, 18 Nov morning):
        │                 H1 specification and the robustness list, H2 event rule,
        │                 windows, counterfactual model, placebo rule, unit for "per +n fires"
        ▼                               │
Part 2.3, Part 1 (parallel)             ▼
                         Part 4 H1  and  Part 5 H2  (parallel, primary first, robustness second)
                                        │
                                        ▼
                  Part 6 status (MA) + monitoring ──► Part 7 recommendations ──► Part 8, Part 9
```

**Why EDA gates the models:** EDA shows the shape of PM2.5 (is a log scale needed), the fire distribution (what "per +n detections" means in the data), which weather variables vary, how often the GRAP stages occur and where the outage sits. These decide the specifications.

**The frozen analysis plan** is one markdown cell at the top of Part 4 and Part 5, written by MK and RB **before any model is fitted**, and committed with a timestamp. It fixes: outcome and sample, the primary specification (one per hypothesis), the sensitivity list, the event rule and windows for H2, the unit for the H1 effect, and the diagnostics. Anything added later is labelled "added after seeing results" with the reason. DECISION on the frozen plan: reviewer per plan 1.2 (RB for MK's H1 plan, MK for RB's H2 plan).

---

## 4. Work division at a glance

Priority: **M** must, **S** should, **C** could (plan section 2). Do not start a C block while an M block is open.

| Part | Block | Output IDs | Pri | Author | Reviewer |
| --- | --- | --- | --- | --- | --- |
| 0 | Setup, helper cell, requirements, Colab path, seed | none | M | RS | MA |
| 1 | Stakeholders, hypotheses, KPIs (computed live), evaluation strategy | T00, rules table | M | MA | RS |
| 2.1 | Sources and join flow | T1, F0 | S | RS | MA |
| 2.2 | Structure of the final table | none | M | RS | MA |
| 2.3 | Missingness, outage, cleaning, validation cell | T2 | M | MA | RS |
| 3.1 | Valid station-day table and group-day series | analysis_station_day | M | RS | MA |
| 3.2 | Availability heatmap | F1 | M | MA | RS |
| 3.3 | Station map | F2 | S | MA | RS |
| 3.4 | PM2.5 and GRAP timeline | F3 | M | MA (data) with RB (stage strip) | RS |
| 3.5 | Seasonal profile | F4 | S | RS | MA |
| 3.6 | Diurnal profile | F5 | S | RS | MA |
| 3.7 | Distribution | F6 | M | RS | MA |
| 3.8 | Fire time series | F7 | M | MK | RB |
| 3.9 | EDA findings table and interpretations | none | M | MA | RS |
| 4 | H1: lag correlation, regression, diagnostics, prediction, robustness | F8 to F11, T3, T4 and more | M, S | MK | RB |
| 5 | H2: events, counterfactual, placebo, robustness, power | T5, T6, F12 to F15, F17 | M, S | RB | MK |
| 6.1 to 6.2 | Robustness overview and hypothesis status | T7 | M | MA | RS |
| 6.3 | Monitoring and drift | F16, T9 | S | MA | RS |
| 7 | Recommendations and roadmap | T8 | M | RB | MA |
| 8 | Deployment demo and dashboard link | dashboard | S | RS | MA |
| 9 | Final checks, clean run, reconciliation with the earlier pass | none | M | RS runs, all tick | all |

**EDA is split on purpose** (plan M3 names MA as owner): the whole analysis is being redone in nine days, so MA takes the data-quality and timeline figures and the findings write-up, and RS takes the station-day table and the three descriptive figures. Both review each other. Flip it if you prefer MA alone.

**Load:** MA 7 blocks, RS 8 small blocks plus assembly, MK 2 large, RB 3 large (one is shared). MK and RB have the heaviest statistics, but nothing in H1 or H2 can start fitting until the frozen analysis plan is in (18 Nov), so both begin with design work and data checks now.

---

## 5. Blocks in detail

### 5.0 Setup that must happen first (15 to 16 Nov)

| ID | Task | Owner | Done when |
| --- | --- | --- | --- |
| N0.1 | Part 0: pinned `requirements.txt` (pandas, numpy, scipy, statsmodels, matplotlib, seaborn, pyarrow, nbformat), helper cell, `SEED`, SVG saving in `save_fig` | RS | clean Colab session runs Part 0 |
| N0.2 | Put `final_dataset.parquet` (39 MB) in the shared Drive folder, set `DRIVE_DIR`, record the checksum | RS | all four see `exists: True` |
| N0.3 | `notebooks/parts/` and `tools/assemble_notebook.py` | RS | test assembly of two parts works |
| N0.4 | **3.1 station-day table.** `valid_station_day()` and `group_day()` built and saved as `analysis_station_day.parquet`; recount 5 station-days by hand | RS | MA signs off; **everyone else waits on this** |
| N0.5 | Everyone: print shape, date range and missing counts of the columns they use, compare with the dictionary, write the 5-line pre-task note | all | notes in `docs/work_log/` |

### 5.1 MA: Parts 1, 2.3, EDA data quality and timeline, status, monitoring

**Part 1 (M).** Stakeholder table from `report/01_stakeholder_and_kpis.md` (words only). H1 and H2 as in plan section 0. **KPI table computed from `df`** (daily mean PM2.5, days above 60 ug/m3, completeness, outage hours; KPI 3 and 4 filled after Parts 4 and 5). Print the **plan 5.4 decision rules as a table** and say they were fixed before results.

**2.3 (M).** T2 missingness by station and month. Describe the 10 Jan 18:00 to 20 Jan 18:00 IST 2026 outage and the other outages from `network_outage`; **count the Stage III/IV hours that fall inside outages in the cell** (compare with the validation script, plan G1). Cleaning summary from `data/processed/pollution_quality_report.csv`. Missing-data rule: drop outage hours as primary, short-gap interpolation (up to 3 hours, never across an outage) as sensitivity. Validation cell: run the checks of `src/validate_final_dataset.py` on the loaded file and show the PASS count. Note `n_pm25` is a raw count (readings can exist where `pm25` is empty after quality rules) and the gas units are mislabelled in the archive.

**EDA figures (plan 6.2):**
- **F1 (M)** availability heatmap: stations by month, share of hours with PM2.5, grouped treated and control, outage months annotated.
- **F2 (S)** station map: longitude and latitude, colour by group, labelled by city, 25 km circle around central Delhi, "no basemap, degrees".
- **F3 (M, with RB)** daily mean PM2.5 for treated and control (95% band over stations), GRAP stage strip below sharing the x-axis, outage periods grey. MA builds the series from 3.1; RB adds the stage strip from `grap_stage_applied`.

**3.9 EDA findings (M).** One table "what the EDA tells H1 and H2": level and spread of PM2.5 by group, how often each GRAP stage occurs and in which months, the fire season, the January gap, treated versus control. Plus an interpretation cell for every figure from 3.2 to 3.8 (what it shows, one thing it does not). This table is the input to the frozen analysis plan (section 3). **Deadline 17 Nov.**

**Part 6 (M, after Parts 4 and 5 have primary results).**
- **6.1** One robustness overview: counts of checks with the same sign for H1 and for H2, from MK's and RB's saved tables. No new models.
- **6.2 Hypothesis status.** Apply plan 5.4 to the saved tables. Write the status for H1 and H2 (supported, not supported, inconclusive) as a table, with each criterion, the observed value, met or not, and the table it comes from. The text is generated from the table. MA writes the status because MA did not run the models (G4).
- **6.3 Monitoring (S).** Thresholds written first (for example population stability index at least 0.25 or KS statistic at least 0.20 flags an input-month; model error above 1.5 times a reference RMSE flags a month). Compare input distributions between the training and test periods and the monthly RMSE of MK's prediction model. One chart F16 with month on the x-axis and units on the y-axis.

**Reviews:** RS's 0, 2.2, 2.1, 3.1, 3.5 to 3.7, 8.

### 5.2 RS: Parts 0, 2.1, 2.2, 3.1, descriptive EDA, assembly, deployment, final run

- **Part 0 and N0.1 to N0.4** as above.
- **2.1 (S)** T1 sources table (provider, columns, retrieval date, coverage, licence, resolution, join key, unit) from `docs/provenance_log.csv`; F0 flow diagram with row counts from `docs/final_dataset_run_output.txt`; duplicates (stations 10900 and 11607 dropped), unit harmonisation, `ERA5_STAMP_OFFSET_HOURS` and `NONPM_ALIGN_LAG_ROWS`.
- **2.2 (M)** head, dtypes, stations by group and city, column groups from the dictionary.
- **3.1 (M)** the station-day table, saved. Add the 12-hour and 20-hour variants. Document its columns.
- **F4 seasonal (S)** monthly median and IQR of PM2.5 by group, n stations per month.
- **F5 diurnal (S)** mean PM2.5 by hour of day, winter versus monsoon, by group, with 95% CI.
- **F6 distribution (M)** histogram or ECDF on a log axis by group with the 60 ug/m3 standard as a labelled line.
- **Part 8 (S)** list the saved outputs; show `python run_all.py --from-final`; link the dashboard (`docs/Dashboard.md`, Core pages).
- **Part 9 (M)** clean "Restart and run all" in Colab, the reconciliation (section 7), the checklist.
- **Assembly** at every checkpoint.

**Reviews:** MA's 1, 2.3, 3.2 to 3.4, 3.9, Part 6.

### 5.3 MK: F7 and Part 4 (H1: fire and PM2.5)

**3.8 F7 (M).** Daily detections within 100 km, Delhi treated stations, burning season shaded, `fire_day_status` `outage` and `zero_assumed` days marked differently. Also print the distribution of `n_up_nh_100km_45deg_lag1` for treated stations in the winter sample (median, 99th percentile, maximum, standard deviation). **This decides the unit of the H1 effect** ("per +10", "per 1 SD"), not the plan's "+50".

**Part 4.** Method from plan 4.4 (K1 to K4); write it in the frozen analysis plan first.

| Cell | Content | Pri | Output |
| --- | --- | --- | --- |
| 4.0 | **Frozen H1 plan:** outcome (log PM2.5, station-day, winter sample 1 Oct 2025 to 28 Feb 2026), primary specification, sensitivity list, decision rule from plan 5.4, effect unit | M | markdown |
| 4.1 K1 | Cross-correlation of the Delhi-NCR daily mean PM2.5 with fire counts at lag 0 to 5 days. Lag 0 drawn in a different colour and labelled "diagnostic, not used" (only lag 1 and 2 are allowed as inputs). 95% CI and n | M | F8, T3 |
| 4.2 K2 | Primary: `log(pm25) ~ upwind count (100 km, 45 deg, lag1) + wind speed + wind direction terms + temperature + humidity (from `t2m_c` and `d2m_c`) + `blh_m` + `tp_mm` + `sp_hpa` + hour and day effects + station fixed effects`. Standard errors clustered by station and by date; Newey-West on the Delhi daily series as a cross-check. Report the effect in plain units with the 95% CI, n observations, days and stations | M | T4, F9 |
| 4.3 K2 | Diagnostics: residual versus fitted, residual ACF, Q-Q, variance inflation factors, influence of single days | S | F10 |
| 4.4 K3 | Prediction, time-blocked: train Feb to Dec 2025, test Jan to Sep 2026 (test never used to choose the specification), expanding-window check. Baselines: climatology by month, persistence, weather only. RMSE, MAE, R2 and the gain of fire plus weather over weather only (the answer to RQ1) | M (one split) | F11, T4d |
| 4.5 K4 | Robustness: drop outage vs interpolate short gaps, drop `fire_is_nrt` rows, drop `outage` fire days, leave one station out, leave one city out, other radius and angle, winter only vs all days, weather offset +1 and -1 (needs a recomputation from `era5_station_hourly.csv`: ask RS), placebo (future fire lag, expected about zero) | S, then M for 4 to 5 of them | T4g, F9 extended |
| 4.6 | Interpretation in plain units, what H1 does not show (one season, low power, association only) | M | markdown |

H1 rests on one burning season. If the result is inconclusive, say so; that is a valid result.

### 5.4 RB: Part 5 (H2: GRAP), F3 stage strip, Part 7

**Part 5.** Method from plan 4.5 (B1 to B3); frozen first.

| Cell | Content | Pri | Output |
| --- | --- | --- | --- |
| 5.0 | **Frozen H2 plan:** event rule (Stage II or higher, with at least 7 clean days either side), windows (days 1 to 3 and 4 to 7), 12-hour buffer around the change, fit window (60 days, excluding days within 7 days of another change), counterfactual model, minimum fit quality, placebo rule, decision rule from plan 5.4 | M | markdown |
| 5.1 B1 | From `grap_stage_applied` list every stage change (date and hour, direction, stage before and after, `time_source`, `grap_uncertain`), pre-change 7-day PM2.5 level, outage hours in the window, overlap flag, usable flag with reason. Reconcile the count with `data/processed/grap_orders.csv`; spot check 10 events against the order text | M | T5, F3 strip |
| 5.2 B2 | Counterfactual: fit `log(pm25)` on weather and fire (plus day of week) in the fit window, check the fit on held-out days, predict days 1 to 7 after activation, effect = actual minus predicted with a 95% interval from block resampling. Report each event separately; **pool only if enough events pass the fit rule** | M | T6a, F12, F13 |
| 5.3 B2 | Placebo events (the mean-reversion check): dates as polluted as the real events but no stage invoked, picked by a fixed rule before outcomes; the same event dates in the control cities. Where do the real events fall in the placebo distribution | M | F14, T6c |
| 5.4 B2 | Cross-check with segmented regression (level and slope change) on the daily Delhi-NCR series | S | T6 |
| 5.5 B3 | Robustness, one change at a time: exclude `grap_uncertain` and `grap_inferred` hours, windows of 3, 5, 7 and 14 days, stations with at least 90% coverage, leave one sub-area out, with and without fire terms, Stage I versus Stage III/IV, drop events overlapping the January outage, drop the largest event | M (5 checks), S (all) | T6e, F15 |
| 5.6 | Power simulation: how large a true fall would this method detect with this number of events | C | F17 |
| 5.7 | Interpretation: stages are raised on a forecast of worsening air, which the model cannot see; "inconclusive" may be mostly a statement about power. Never "GRAP reduced PM2.5 by X" | M | markdown |

**F3 stage strip (M, with MA).** Shaded stage numbers on the shared x-axis.

**Part 7 (M).** T8: three to five recommendations tied one to one to findings. Each has: the finding it rests on, its status, what we are not claiming, the action, a responsible stakeholder (CAQM, state board, city health department), timeline (before winter 2026-27, within a year), indicator and target, data needed. **No policy recommendation where the evidence is inconclusive**, only "collect this data" or "run this trial" (keep stations reporting through outages, log the exact time of each GRAP order, extend over several winters, staggered or paired-city design). Roadmap table for Stage 3 slide 4. MA reviews.

### 5.5 Part 9 final checklist (all four tick, RS runs)

- [ ] Restart and run all passes in a clean Colab session; runtime recorded
- [ ] Every figure ticked on the plan 6.1 checklist by author and reviewer; registry row filled
- [ ] No typed numbers; every number in the text traces to a cell and a saved table
- [ ] Wording search: no "caused", "reduced by" or "proved" without a qualifier
- [ ] Treated vermillion, control blue everywhere; outage hours grey gaps
- [ ] Reconciliation with the earlier pass done and every difference explained (section 7)
- [ ] Final master committed with outputs; Colab link in `README.md`

---

## 6. Timeline and checkpoints (adjust)

| Checkpoint | Date | What must be true | Plan gate |
| --- | --- | --- | --- |
| N0 | 15 to 16 Nov | Setup done (5.0); station-day table signed off; pre-task notes written | G0 |
| N1 | 17 Nov | Part 1, 2.3, EDA (F1, F3, F6, F7 at least) and the findings table done; **EDA meeting** | G2 |
| **Freeze** | 18 Nov morning | Frozen H1 and H2 plans committed; nothing fitted before this | n/a |
| N2 | 20 Nov | Primary H1 (4.1, 4.2, 4.4) and primary H2 (5.1 to 5.3) done; the reviewer re-runs and gets the same numbers to 3 significant figures | G3 |
| N3 | 21 Nov | Robustness (5 to 6 checks each), status (6.2), monitoring if time allows, Part 7 | G4 |
| N4 | 22 Nov | Master assembled; Part 9 ticked; scripts frozen, only wording changes after this | G5, G6 |
| N5 | 23 to 24 Nov | Mock viva from the notebook; repo clean; submission opened on a second machine | G7 |

Daily 15-minute stand-up. Blocked for more than half a day: say so.

**This is a compressed version of the plan.** The original plan gave EDA until 15 Nov and models until 19 Nov. If a checkpoint slips, cut in this order (all C and then S items): the power simulation (5.6), the monitoring chart (6.3), the full robustness grids, the diagnostics figure (4.3), F2, F5, F4, the dashboard. Never cut: EDA data quality, the frozen plans, the primary H1 and H2 results, the status table, the wording rules.

---

## 7. The earlier pass: reference values and one reconciliation

The earlier scripts produced these numbers (H1 and H2 from tables on `origin/mehak/h2-review`; the status, drift and KPI values from the removed `manya_work` files, readable with `git show bd041f0:<path>`). They are **not** targets and **not** inputs. They are used once, in Part 9, after the notebook's own results are saved:

| Quantity | Earlier-pass value (reference only) |
| --- | --- |
| H1 primary, upwind count (100 km, 45 deg, lag 1) | +11.8% per +10 detections, 95% CI [-3.0, +28.9], 4,757 station-days, 129 days, 39 stations |
| H1 robustness | 14 of 15 checks same sign |
| H1 prediction, fire plus weather vs weather only | RMSE 32.08 vs 32.27 ug/m3 |
| H2, 11 Nov 2025 event | +23% [-48, +190], placebo share 0.52 |
| Hypothesis status | H1 and H2 both INCONCLUSIVE |
| Outage | 241 hours (10 Jan 18:00 to 20 Jan 18:00 IST), 928 outage hours, 112 of 971 Stage III/IV hours inside outages |
| Validation | 51 checks passed |

**Procedure (RS, in Part 9, a Should item):** check out the earlier tables into a temporary folder outside the repo, put them side by side with the notebook's tables, and write one row per quantity: notebook value, earlier value, same or different, reason. A difference is not an error: it may come from a different specification, sample or rule. Two quantities are exceptions and **must** match because they come straight from the dataset: the outage counts and the validation result. If the notebook's H1 or H2 status differs from the earlier pass, say so in the report and explain why; do not adjust the notebook to match.

If the team decides not to use the earlier pass at all, delete this section and the Part 9 line; nothing else depends on it.

---

## 8. Risks

| Risk | What we do |
| --- | --- |
| Nine days for what the plan gave three weeks | Priorities M, S, C in section 4; cut list in section 6; freeze at N4 |
| EDA slips and holds up H1 and H2 | EDA meeting on 17 Nov even if F2, F4, F5 are not done; MK and RB do design work and checks meanwhile; the frozen plans need only the findings table (3.9) |
| Everyone sees the earlier numbers and picks specifications to match | Frozen plans committed before fitting; differences from the earlier pass recorded; the replication caveat in the report |
| Notebook merge conflicts | Part files and RS assembly (2.3) |
| Clean run too slow in Colab (bootstrap, placebo, power) | Cache results to `outputs/tables/` and let the cell load them when `RERUN = False`; the reviewer runs once with `RERUN = True` |
| Missing data is correlated with treatment | Outage hours dropped in the primary run; the January outage listed in every H2 event window; sensitivity run |
| Causal over-claiming | Wording check in Part 9; reviewers search the notebook text |
