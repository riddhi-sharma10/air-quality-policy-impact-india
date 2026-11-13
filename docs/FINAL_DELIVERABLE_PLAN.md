# Final deliverable plan: team of four, end to end

Project: *Do Burning and Emission Restrictions Reduce Air Pollution in Northern India? A Multi-Source Analysis of Stubble Fires, Weather and GRAP Interventions* (Group 3).
Members: Manya Awasthi (MA), Riddhi Sharma (RS), Mehak Kumar (MK), Reia Baid (RB).
Written 10 Nov 2026. Semester ends 24 Nov 2026. **Adjust every date below to the real dates of the final report and the Stage 2 and Stage 3 presentations.**

This plan covers the final report (10 marks), the final presentation (20 marks) and the reproducible code and data that go with them. It follows the course guideline: BADIR, stakeholder first, authentic multi-source data, one consistent dataset (SSOT), prescribed course methods only, several lines of evidence per finding, "inconclusive" accepted as a valid result, association kept apart from causation.

---

## 0. Where we start (facts to build on, do not re-derive)

| Item | Status |
| --- | --- |
| Final dataset | Built and checked: `data/processed/final_dataset.parquet` (39 MB) and `.csv` (360 MB), git-ignored. 763,344 rows, 70 columns, 54 stations (39 treated, 15 control), hourly, 19 Feb 2025 to 30 Sep 2026 (IST). |
| Dictionary and provenance | `docs/final_dataset_dictionary.md`, `docs/provenance_log.csv`, run log `docs/final_dataset_run_output.txt` |
| Hypotheses (from the Stage 1 proposal) | **H1**: higher upwind fire counts in the previous 1 to 3 days are associated with higher PM2.5 (beta > 0, p < 0.05), controlling for wind, temperature, humidity, boundary-layer height. **H2**: PM2.5 falls after GRAP activation relative to the trend predicted by weather and fires alone. |
| Analysis | Not started. This plan is the analysis, the report and the presentation. |

### Known facts that shape the analysis (all four must read this table)

| Fact | Consequence |
| --- | --- |
| One burning season only (Oct to Nov 2025) and one winter | H1 has low power. "Inconclusive" is a legitimate result. State it, do not hide it. |
| GRAP is invoked because pollution is high | Reverse causation and regression to the mean. A fall after activation is not automatically an effect. Use the weather-and-fire counterfactual and the control cities. |
| Stage III and IV hours: 971 in total, almost all Nov 2025 to Jan 2026 | H2 rests on a handful of episodes. Report per event, not only pooled. |
| Network-wide PM2.5 outage 10 Jan 18:00 to 20 Jan 18:00 IST 2026 (241 hours, called "11 to 20 Jan" elsewhere) and shorter ones; 928 outage hours in all | 112 of the 971 Stage III/IV hours fall inside an outage: 94 in the January one, 18 in shorter ones (counted by `src/validate_final_dataset.py`). Missing data is correlated with treatment. Report it and run a sensitivity check. |
| 6.8% of hours `grap_uncertain`, 21% `grap_inferred` | Primary run keeps them, a robustness run drops them, and event windows get a buffer around the change. |
| Control cities (Patna, Lucknow, Kanpur) have different weather and fire exposure and their own local action plans | Controls are a comparison, not a clean counterfactual. Say so. |
| Gas columns are mislabelled "ppb" in the archive | Use the units in the dictionary (NO, NO2 in ug/m3, NOx in ppm). Gases are secondary variables. |
| Pre-submission proposed Oct to Feb 2018 to 2025, daily; the data is 2025 to 2026, hourly | **Deviation** from the proposal. Needs written instructor approval (task T0.1). |
| Out-of-sample "by year" is impossible | Use a time-blocked split. State this change. |

---

## 1. Working rules for everybody

### 1.1 Review-before-you-start gate (applies to every task, no exceptions)

Before starting any task card, the owner does this, in this order:

1. **Review.** Re-read the "Review first" list on the task card (docs, code, previous outputs). Open the actual files, not memory.
2. **Look at the data you will use.** Print shape, date range, missing counts and 5 rows. Confirm they match the dictionary.
3. **Write a pre-task note** (5 to 10 lines) in `docs/work_log/<initials>_<yyyy-mm-dd>_<task-id>.md` using the template in section 9: what was reviewed, what the task needs, **at least two options considered**, the one chosen and why, risks.
4. **Ask for options.** Post the options to the group chat (or ask Claude Code for them) and wait for the reviewer's reply (target: same day). Choices marked **(DECISION)** on a task card need the named reviewer to say yes before work starts. Choices not marked can proceed once the note is written.
5. **Do the work.** Then run the task's acceptance checks.
6. **Peer review** by the assigned reviewer (section 1.2) before the output counts as done.

Why: the project already lost time to unit labels, time alignment and stale documents. Looking first and choosing between options on paper is cheaper than redoing analysis.

### 1.2 Cross-review pairs

| Author | Reviewer |
| --- | --- |
| MA | RS |
| RS | MA |
| MK | RB |
| RB | MK |

Every table, figure and number that goes into the report or slides is reviewed by someone who did not make it. The reviewer checks the figure checklist (section 6) and re-runs the script from a clean state.

### 1.3 Frameworks and standards

- **BADIR** structures everything: Business question, Analysis plan, Data, Insights, Recommendations. Every report section and slide carries its BADIR tag (section 7).
- **Hypothesis workflow.** Decision rules for "supported / not supported / inconclusive" are written down **before** results are seen (section 5.4). Do not move them afterwards.
- **Statistics.** Report effect sizes with 95% confidence intervals, not p-values alone. State the unit of observation and what the standard errors are clustered on. Check residuals and autocorrelation. One primary specification per hypothesis chosen in advance; everything else is labelled sensitivity. Say how many specifications were tried.
- **Association versus causation.** Wording rule: findings are "associated with" unless a design supports more. H2 can at best be "consistent with an effect, conditional on the weather model". Never write "GRAP reduced PM2.5 by X" without the qualifier and the interval.
- **Scope.** Use only methods in the course handout (confirm with T0.2). Anything else (difference-in-differences, boosted models, SHAP, MLflow) is optional, labelled "extension", and used only with written instructor approval.
- **Reproducibility.** Every number and figure is made by a script in the repo with a fixed random seed, reading from `data/processed/final_dataset.parquet`. No hand-edited numbers, no screenshots of notebooks. Package versions are pinned in `requirements.txt`.
- **Git.** One branch per person (`ma/...`, `rs/...`, `mk/...`, `rb/...`), pull requests reviewed by the cross-review partner. Commit code and documents only, never data files. No co-author lines in commits.

---

## 2. Roles and ownership (from the team table)

| Member | Role | Owns (files and deliverables) | Backup |
| --- | --- | --- | --- |
| **MA** | Problem definition, data quality, MLOps | Stakeholder and KPI page, pollution EDA, data validation script, monitoring (data drift, model performance over time), quality section of the report | RS |
| **RS** | Data engineering, integration, deployment | Dataset reproducibility (`requirements.txt`, run order, Docker), feature checks, dashboard or API (small), deployment documentation, SSOT section of the report | MA |
| **MK** | Statistical analysis, predictive modelling | H1: correlation and lag analysis, regression, prediction model, diagnostics, robustness | RB |
| **RB** | GRAP intervention and policy analysis | H2: interrupted time series or regression, event list, uncertainty, policy recommendations, implementation roadmap | MK |

**Shared:** hypothesis refinement, integration testing, final report, presentation, viva preparation.

Priority within each role (so scope stays finishable in two weeks):

- **Must:** everything on the task cards marked M.
- **Should:** marked S, done if the Must items pass review.
- **Could:** marked C, only if time remains. Do not start a C item while an M item is open.

---

## 3. End-to-end flow and timeline

```
T0 Setup & approvals ──► P1 Data & quality ──► P2 EDA ──► P3 Models (H1, H2) ──► P4 Robustness
        │                                                                              │
        └────────────────────────────────────────────────────────────────────────────►│
                                                                                       ▼
                                          P5 Integration & findings ──► P6 Report & slides ──► P7 Rehearsal & submit
```

| Phase | Dates (adjust) | BADIR | Presentation stage | Gate to pass before moving on |
| --- | --- | --- | --- | --- |
| T0 Setup, approvals | 10 to 11 Nov | B | Stage 1 content (already presented) | G0: approvals asked, environment runs, work log started |
| P1 Data and quality | 11 to 13 Nov | D | Stage 2 slide 1 | G1: validation script passes, dataset reproducible from instructions |
| P2 EDA | 12 to 15 Nov | A, D | Stage 2 slide 2 | G2: all EDA figures pass the figure checklist and are peer reviewed |
| P3 Models | 14 to 19 Nov | A, I | Stage 2 slides 3 to 4 | G3: primary H1 and H2 results reproduced by the reviewer |
| P4 Robustness | 18 to 20 Nov | I | Stage 2 slides 3 to 5 | G4: robustness table complete, hypothesis status assigned by the pre-set rules |
| P5 Integration | 19 to 21 Nov | I, R | Stage 3 slides 1 to 3 | G5: one findings table, every number traced to a script |
| P6 Report and slides | 20 to 22 Nov | I, R | Stage 3 slide 4 | G6: report and slides reviewed by all four |
| P7 Rehearsal, submit | 22 to 24 Nov | R | all | G7: mock viva done, repo clean, submission checked |

Daily rhythm: 15-minute stand-up (what I finished, what I am starting, what I need). A person who is blocked for more than half a day says so immediately.

---

## 4. Task cards by person

Each card: **Review first**, **Options** (pick one, record it in the pre-task note), **Steps**, **Output**, **Acceptance**. **(DECISION)** means the reviewer must confirm before work starts.

### 4.1 Shared tasks (T0)

| ID | Task | Owner | Output |
| --- | --- | --- | --- |
| T0.1 | Send the instructor a one-page deviation note: (a) time window is 19 Feb 2025 to 30 Sep 2026, hourly, one burning season (OpenAQ has no 2023 and 2024 data); (b) time-blocked validation instead of by-year; (c) lag range for H1; (d) control cities and which optional methods we use. Ask for approval in writing. | RB drafts, all review | `docs/deviation_note.md`, instructor reply saved |
| T0.2 | Check the course handout's method list against section 1.3 and mark each method allowed, not allowed, or unsure | MK | `docs/methods_check.md` (a table: method, handout page, allowed) |
| T0.3 | Create `docs/work_log/`, branches, and read sections 0 and 1 of this plan together (20 minutes) | MA | folder, branches |

### 4.2 MA: problem definition, data quality, MLOps

**M1. Stakeholder and KPI page** (BADIR: B)
- *Review first:* the Stage 1 summary PDF, README intro, section 0 here.
- *Options:* (A) one primary stakeholder (CAQM) with others as secondary; (B) a table of all stakeholders (CAQM, state boards, city health departments) with their decision and the evidence we can offer each. **Recommended: B, but limit the "can we support this" column honestly:** we have stations only in Delhi-NCR, Patna, Lucknow, Kanpur, so we cannot support Punjab or Haryana specific claims.
- *Steps:* list decisions each stakeholder makes; define 3 to 5 KPIs (for example PM2.5 daily mean, days above 60 ug/m3, response of PM2.5 in 3 days after a stage change); list constraints (what GRAP covers, what data we have).
- *Output:* `report/01_stakeholder_and_kpis.md` (one page and one slide).
- *Acceptance:* every KPI is computable from `final_dataset`, with the column named. Every stakeholder decision links to a hypothesis or is marked "outside the data".

**M2. Data validation script** (D)
- *Review first:* `docs/final_dataset_dictionary.md`, the 45 checks in `src/build_final_dataset.py`, `docs/final_dataset_run_output.txt`.
- *Options:* (A) a standalone `src/validate_final_dataset.py` with plain pandas asserts; (B) a schema library (for example pandera). **Recommended: A** (fewer dependencies; the course scope is simpler).
- *Steps:* checks on row count (763,344), keys unique, 54 stations, date range, value ranges per column, the missing-value counts in the dictionary, the outage flag, treated/control counts, and that no `lag0` or same-day fire column exists. Print PASS/FAIL and exit non-zero on failure. Add tests.
- *Output:* `src/validate_final_dataset.py`, `tests/test_validate_final_dataset.py`, saved run output `docs/validation_run_output.txt`.
- *Acceptance:* passes on the real file; a deliberately broken copy (drop a row, change a value) fails.

**M3. Pollution EDA and data-quality section** (D, A)
- *Review first:* quality report `data/processed/pollution_quality_report.csv`, dictionary "Cleaning" and "Missing values" sections.
- *Options for missing data:* (A) drop outage hours (default in the dictionary); (B) keep all hours and add the outage flag as a model term; (C) short-gap interpolation, as the proposal said (only for gaps up to 3 hours). **Recommended: A as primary, C as a sensitivity run. Never interpolate across a network outage.** **(DECISION: reviewer RS)**
- *Steps:* figures F1 to F5 (section 6); a table of missingness by station and month; description of the 11 to 20 Jan 2026 outage and its overlap with Stage III/IV.
- *Output:* `src/analysis/01_eda_pollution.py`, figures and tables in `outputs/`, report section "Data quality and preparation".
- *Acceptance:* figure checklist passed; the overlap of outage and stage hours is stated with the exact count from the data.

**M4. Monitoring and drift (MLOps)** (I, S)
- *Review first:* MK's model outputs (after G3); the handout's position on MLOps (T0.2).
- *Options:* (A) a monitoring script that compares the model's error and the input distributions between a training period and a later period and writes a table and one chart; (B) a full pipeline with a tracking tool. **Recommended: A. B only with instructor approval (scope).**
- *Steps:* population stability index or a Kolmogorov-Smirnov test for key inputs between train (Feb to Dec 2025) and test (Jan to Sep 2026); monthly RMSE of the model on the test period; thresholds written in advance.
- *Output:* `src/analysis/05_monitoring.py`, figure F16, one report paragraph.
- *Acceptance:* thresholds are stated before the results; the chart shows the month on the x-axis and the metric with units on the y-axis.

### 4.3 RS: data engineering, integration, deployment

**R1. Reproducible build** (D)
- *Review first:* README, `docs/provenance_log.csv`, the order of scripts in the README, `src/build_final_dataset.py` header.
- *Options:* (A) `requirements.txt` plus one `REPRODUCE.md` with the run order; (B) a `Makefile` or `run_all.py` that calls the scripts in order; (C) Docker. **Recommended: A and B (Must), C as Should.**
- *Steps:* find every import and pin the version used on the machine that built the data (the build machine, not this one); list which raw files are needed and where to get them; separate "rebuild from raw" (needs accounts and hours) from "start from `final_dataset.parquet`"; state where the Parquet is shared (the file is too big for Git).
- *Output:* `requirements.txt`, `REPRODUCE.md`, `run_all.py`.
- *Acceptance:* a clean virtual environment on another machine runs `python run_all.py --from-final` and reproduces EDA tables (compare checksums or values), and the full test suite passes with no missing-module error.

**R2. SSOT and provenance section** (D)
- *Review first:* the dictionary, provenance log, README Limitations.
- *Steps:* one table of sources: link, retrieval date, time coverage, licence, resolution, join key, unit. One diagram of the join flow (stations spine → pollution → weather by nearest cell → fire by station and IST date → GRAP by hour). Explain duplicates (stations 10900 and 11607 dropped), missing values, unit harmonisation (incl. the gas unit labels), time alignment (settings `ERA5_STAMP_OFFSET_HOURS`, `NONPM_ALIGN_LAG_ROWS`).
- *Output:* `report/02_data_and_ssot.md`, diagram figure F0.
- *Acceptance:* each join key, unit and rule is traceable to a script line or dictionary row. Every number matches the run output.

**R3. Feature review** (A, D)
- *Review first:* the dictionary fire and weather sections, `src/build_upwind_features.py`.
- *Options for H1's "1 to 3 days":* (A) keep lag1 and lag2 and write H1 as "previous 1 to 2 days" (needs instructor OK, deviation); (B) build lag3 from the raw FIRMS file (needs the raw files and hours of compute, but keeps the proposal's wording). **(DECISION: reviewer MK, and tell the instructor in T0.1.)**
- *Output:* a one-paragraph decision plus, if B, `fire_*_lag3` columns with tests (strictly before the IST date; recount 40 station-dates from raw).
- *Acceptance:* no same-day fire column is introduced; `assert_hourly_safe` passes.

**R4. Derived analysis table** (D, S)
- *Steps:* a documented script `src/analysis/00_make_analysis_tables.py` producing (i) a station-day table (daily mean PM2.5 with the number of valid hours, daily mean weather, fire columns, GRAP stage at 12:00 and the daily maximum), (ii) a Delhi-NCR and a control-city daily series. State the minimum valid hours (for example 18 of 24) for a day to count.
- *Options:* (A) minimum 18 valid hours; (B) 12; (C) 20. **Recommended A, with B and C as sensitivity.**
- *Output:* `data/processed/analysis_station_day.parquet` (git-ignored, regenerated), its dictionary.
- *Acceptance:* row counts per station add up; a manual recount of 5 station-days from the hourly table matches.

**R5. Dashboard or API (small) and deployment notes** (R, S/C)
- *Review first:* the stakeholder KPIs (M1).
- *Options:* (A) a static HTML or notebook-free dashboard with the main charts; (B) a small Streamlit app; (C) Docker image for either. **Recommended: A (Should). B or C only if G5 has passed.**
- *Acceptance:* the dashboard shows the same numbers as the report (tested by a script that compares them).

### 4.4 MK: statistical analysis and predictive modelling (H1)

**K1. Correlation and lag analysis** (A, I)
- *Review first:* dictionary fire, weather and calendar sections; the Known facts table; `src/build_upwind_features.py`.
- *Options for the outcome:* (A) PM2.5 in ug/m3; (B) log(PM2.5); (C) daily mean per station. **Recommended: log(PM2.5), daily station means (R4), Oct 2025 to Feb 2026 as the main "winter" sample, then all days as a sensitivity.** **(DECISION: reviewer RB)**
- *Steps:* cross-correlation of the Delhi-NCR daily mean PM2.5 against fire counts at lag 0 to 5 days (note: only lags 1 and 2 are allowed as model inputs; lag0 is shown only as a diagnostic and labelled so); plots F7, F8. Report correlation with its 95% CI and the number of days.
- *Acceptance:* every plot has the correct lag direction (fires lead PM2.5), the sample and its size in the caption.

**K2. H1 regression** (A, I)
- *Options for the specification (choose one primary in advance):*
  - (A) PM2.5 on upwind fire count (100 km, 45 degrees, lag1) plus controls. Primary.
  - (B) Same with FRP in place of counts.
  - (C) Counts at 50, 100, 200 km (all directions).
  - (D) Add lag2.
  **Recommended: A as the primary, B to D as sensitivity.** Using all radii together causes severe collinearity; do not put them in one model.
- *Model:* `log(pm25) ~ fire + wind_speed + wind direction terms + temperature + humidity (from t2m and d2m) + blh + rain + pressure + hour/day effects + station fixed effects`. Standard errors: cluster by station and also report by date (or Newey-West for the Delhi daily series), because days are autocorrelated and stations in one city are correlated. State clearly that effective independent observations are few (one season).
- *Diagnostics:* residual versus fitted plot, residual autocorrelation (ACF), variance inflation factors for the controls, influence of single days.
- *Acceptance:* the coefficient is reported with the 95% CI, the interpretation in plain units (for example "+10% PM2.5 per +50 upwind detections"), plus the sample size, the number of days and stations. Figure F9 (coefficients across specifications) and F10 (diagnostics).

**K3. Prediction model** (I)
- *Options:* (A) the regression from K2 used for prediction; (B) a decision tree or random forest if in the handout; (C) boosting plus SHAP only with approval. **Recommended: A. B only if T0.2 says it is in the handout.**
- *Validation:* time-blocked split (train Feb to Dec 2025, test Jan to Sep 2026), plus an expanding-window check. Baselines: (i) climatology by calendar month, (ii) yesterday's PM2.5 (persistence), (iii) weather only. Report RMSE, MAE and R2 for each, with the improvement in the fire-plus-weather model over the weather-only model (this is the answer to RQ1: "how much variation do fires explain after meteorology").
- *Acceptance:* the test period is never used for choosing the specification; F11 (predicted versus actual with the 1:1 line, units, n).

**K4. Robustness for H1** (I)
- *Checks:* drop outage hours versus interpolate short gaps; drop NRT (preliminary) fire rows (`fire_is_nrt`); drop `outage` fire days; leave one station out; leave one city out; weather offset +1 and -1 hours (`ERA5_STAMP_OFFSET_HOURS`; this needs a rebuild of the weather columns, or a recomputation from `era5_station_hourly.csv`: ask RS); different radius and angle (the other 8 upwind settings); winter sample only; placebo (fire values from the same calendar dates of the wrong station region, or future fire lag, expected to be about zero).
- *Output:* one table, F9 extended.
- *Acceptance:* the table lists the sign, size, CI and sample for every check. The hypothesis status follows the rules in section 5.4.

### 4.5 RB: GRAP intervention and policy analysis (H2)

**B1. GRAP event table** (B, D)
- *Review first:* `data/processed/grap_orders.csv`, `grap_gaps.csv`, `docs/grap_hourly_dictionary.md`, the Known facts table.
- *Steps:* from `grap_hourly.csv` list the 30 stage changes with: date and hour, direction, the stage before and after, `time_source` and uncertainty, the pre-change 7-day PM2.5 level, the PM2.5 trend before, whether any outage hours fall inside the window, and an exclusion flag (overlaps another change within 7 days).
- *Options:* (A) all 30 changes; (B) only invocations of Stage II or higher with at least 7 clean days either side; (C) group by stage. **Recommended: B for the primary result, A and C reported descriptively.** **(DECISION: reviewer MK)**
- *Output:* `outputs/tables/grap_events.csv` and F3 (series with GRAP shading).
- *Acceptance:* each event row reconciles with `grap_orders.csv` (spot check 10 events by reading the PDF order or the PIB text).

**B2. H2 interrupted time series** (A, I)
- *Options:*
  - (A) **Segmented regression on the daily Delhi-NCR series** (level and slope change at activation) with weather and fire controls. Closest to the proposal.
  - (B) **Counterfactual approach:** fit the weather-and-fire model on days outside the event window (for example the 60 days before), predict inside the window, and compare actual versus predicted for 1 to 7 days after activation (this is exactly the proposal's wording for H2).
  - (C) **Control cities as a comparison** (treated minus control, before and after), only if the handout covers it.
  **Recommended: B as primary (it matches H2), A as a cross-check, C as a sensitivity run.** **(DECISION: reviewer MK)**
- *Rules:* effect window pre-set: days 1 to 3 and days 4 to 7 after activation. Buffer of 12 hours around the change (hour of change is uncertain for most orders). Drop outage hours. Report each event separately, then a pooled estimate with an interval that reflects between-event variation (a simple random-effects mean or the median with a bootstrap over events). With about 5 to 8 usable events, say clearly that this is a small number.
- *Mean-reversion check:* activation follows high pollution, so PM2.5 tends to fall afterwards anyway. Show the same analysis on **placebo events**: (i) dates when pollution was equally high but no stage was invoked, (ii) the same dates in the control cities. Report where the real events lie among the placebo distribution (F14).
- *Acceptance:* F12 (actual versus counterfactual per event with 95% band, activation line, units and dates in IST), F13 (effect per event with CI), F14 (placebo distribution). The status of H2 follows section 5.4.

**B3. H2 robustness** (I)
- *Checks:* exclude `grap_uncertain` and `grap_inferred` hours; alternative windows (3, 5, 7, 14 days); alternative stations (only stations with at least 90% PM2.5 coverage; leave one sub-area out: Delhi, Ghaziabad, Noida, Gurugram); counterfactual model with and without fire terms; Stage I only versus Stage III/IV; the effect of the January 2026 outage (drop events whose window overlaps it).
- *Output:* robustness table and F15 (all checks on one forest plot with the same x-axis).

**B4. Policy recommendations and roadmap** (R)
- *Options:* (A) three to five recommendations tied one to one to findings; (B) a broader policy memo. **Recommended: A.** Each recommendation has: the finding it rests on, the confidence (supported, not supported, inconclusive), what we are not claiming, the action, a responsible stakeholder, a timeline and a measurable indicator.
- *Rules:* a recommendation is **not** allowed where the evidence is inconclusive, except as "collect this data" or "run this trial". Examples that need data we lack (stubble-source states, farmer compensation) stay out.
- *Output:* `report/07_recommendations_roadmap.md`, Stage 3 slides 2 to 4.
- *Acceptance:* every recommendation names the table or figure it relies on, and the limitations paragraph states what would change it.

---

## 5. Analysis specification (so everyone does the same thing)

### 5.1 Definitions

- **Winter sample (main):** 1 Oct 2025 to 28 Feb 2026 (one burning season and one winter). Full window is a sensitivity run.
- **Valid day:** at least 18 of 24 hours with PM2.5 outside outage hours (decision R4).
- **Treated / control:** `group` column. **Policy variable:** `grap_stage_applied`. Control cities always 0.
- **Time:** IST everywhere in figures; state it in every time axis.
- **Units:** PM2.5 in ug/m3; gases in the units from the dictionary, not the file label.

### 5.2 Data files each person uses

| File | Producer | Used by |
| --- | --- | --- |
| `data/processed/final_dataset.parquet` | already built | everyone |
| `data/processed/analysis_station_day.parquet` | RS (R4) | MK, RB, MA |
| `outputs/tables/grap_events.csv` | RB (B1) | RB, MK |
| `outputs/tables/*.csv`, `outputs/figures/*.png/.svg` | script that makes them | report, slides |

### 5.3 Output naming

`outputs/figures/F<nn>_<short_name>.png` (300 dpi) and `.svg`; `outputs/tables/T<nn>_<short_name>.csv`; a registry `outputs/figure_registry.csv` listing figure id, script, input file, date made, author, reviewer, status.

### 5.4 Pre-set decision rules for hypothesis status (written before results; do not change after)

| Status | H1 (fire) | H2 (GRAP) |
| --- | --- | --- |
| **Supported** | Primary coefficient > 0 with 95% CI excluding 0, **and** same sign in at least 75% of robustness checks, **and** fire model beats the weather-only model on the test period | Pooled post-activation actual minus predicted is below 0 with 95% CI excluding 0, **and** the real events lie in the lower tail of the placebo distribution, **and** same sign in at least 75% of robustness checks |
| **Not supported** | CI excludes 0 on the wrong side, or the coefficient is close to 0 with a tight CI that rules out a meaningful effect (state the size we could rule out) | Same logic for H2 |
| **Inconclusive** | Anything else: a wide CI, a sign that flips between checks, too few independent days | Anything else, including few usable events, results driven by one event, or placebo results as large as the real ones |

State the status in plain words, never "significant therefore causal".

---

## 6. Figure and table standards (every graph must pass all of these)

### 6.1 Checklist (author ticks, reviewer ticks again)

- [ ] **Title** says what is shown, the unit of observation and the period (for example "Daily mean PM2.5, Delhi-NCR stations versus control cities, Oct 2025 to Feb 2026").
- [ ] **Axes labelled with quantity and unit** (for example "PM2.5 (ug/m3)", "Date (IST)"). No unlabelled ticks. Log scales say "log scale".
- [ ] **Legend** names every colour, line style, marker and shaded area. Shaded GRAP stages show stage numbers.
- [ ] **n shown:** number of stations, days or events behind each line or point, in the caption or annotation.
- [ ] **Uncertainty shown** and defined: "95% CI, standard errors clustered by station" or "5th to 95th percentile".
- [ ] **Missing data is a gap, not zero.** Outage periods are marked (grey band) and not interpolated.
- [ ] **Correct times:** IST, hour convention stated (`hour_ist` is the START of the PM2.5 hour).
- [ ] **Correct units for gases** (dictionary, not the archive label).
- [ ] **Same scale across panels** that are meant to be compared. A zero baseline for bars. Dual y-axes are avoided; if unavoidable, each axis is coloured to match its line and the reason is stated.
- [ ] **Colour-blind-safe palette**, readable in greyscale, same colour meaning in every figure (treated = one colour, control = another, fixed across the report).
- [ ] **Numbers in the figure agree with the table** they relate to. The script asserts this (for example the plotted mean equals the table mean).
- [ ] **Source and script** in the caption: "Source: final_dataset.parquet; script `src/analysis/..`".
- [ ] **Readable at slide size:** font at least 12 pt when the figure is placed on a slide; no text over data.
- [ ] **Reproduces from a clean run** by the reviewer, with the same picture and the same numbers.
- [ ] **Interpretation sentence** next to it: what the reader should take away, and one thing it does **not** show.

### 6.2 Figure list (owner, purpose, exact specification)

| ID | Owner | Figure | Specification |
| --- | --- | --- | --- |
| F0 | RS | Data integration flow | Boxes: sources → keys → joins → final table, with row counts at each step (from the run output). |
| F1 | MA | PM2.5 data availability | Heatmap: stations (rows, grouped treated/control) by month (columns), colour = share of hours with PM2.5; outage months annotated. |
| F2 | MA | Station map | Scatter of longitude/latitude, colour by group, labelled by city. State "no basemap, coordinates in degrees". Add the 25 km circle around central Delhi. |
| F3 | MA/RB | PM2.5 and GRAP timeline | Daily mean PM2.5 for treated and control groups (two lines, 95% band over stations), GRAP stage as a stepped strip below sharing the x-axis, outage periods shaded grey. |
| F4 | MA | Seasonal profile | Monthly median and IQR of PM2.5 by group; n stations per month. |
| F5 | MA | Diurnal profile | Mean PM2.5 by hour of day for winter versus monsoon, by group, with 95% CI. |
| F6 | MA | PM2.5 distribution | Histogram or ECDF on a log axis by group, with the guideline thresholds (for example 60 ug/m3 24-hour standard) as labelled vertical lines. |
| F7 | MK | Fire time series | Daily detections within 100 km (Delhi stations mean) with the burning season shaded; days with no usable satellite pass (`outage`/`zero_assumed`) marked differently. |
| F8 | MK | Lag correlation | Correlation of daily PM2.5 with fire counts at lag 0 to 5 days, with 95% CI bars; lag 0 drawn in a different colour and labelled "diagnostic, not used". |
| F9 | MK | H1 coefficient plot | One coefficient (per +50 upwind detections, in % change of PM2.5) with 95% CI per specification and robustness check; vertical zero line; sample size on the right. |
| F10 | MK | H1 diagnostics | Residuals versus fitted, residual ACF, Q-Q plot, in one panel set with a shared caption. |
| F11 | MK | Prediction | Predicted versus actual daily PM2.5 on the test period, 1:1 line, RMSE and n in the annotation; a second panel with the monthly RMSE of the three baselines. |
| F12 | RB | ITS per event | One panel per event: actual daily PM2.5 (line), counterfactual (dashed) with 95% band, activation time as a vertical line, 7 days before and after, outage hours shaded. |
| F13 | RB | Effect per event | Forest plot: effect (ug/m3 and %) with 95% CI per event and pooled, ordered by date. |
| F14 | RB | Placebo distribution | Histogram of placebo effects with the real events marked and the share of placebos below each real event. |
| F15 | RB | H2 robustness | Forest plot of the pooled effect under every check on one common axis. |
| F16 | MA | Monitoring | Monthly RMSE and the drift statistic for key inputs with thresholds drawn. |

Tables: T1 sources and provenance (RS), T2 missingness (MA), T3 correlations (MK), T4 H1 regression (MK), T5 GRAP events (RB), T6 H2 results and robustness (RB), T7 hypothesis status (all), T8 recommendations and roadmap (RB).

---

## 7. Deliverables mapped to the guideline

### 7.1 Final report outline (each section tagged with BADIR)

| # | Section | BADIR | Owner |
| --- | --- | --- | --- |
| 1 | Problem statement, stakeholder, KPIs, research questions, hypotheses | B | MA |
| 2 | Data sources, provenance, integration (SSOT), reproducibility | D | RS |
| 3 | Data quality and preparation (cleaning, outliers, missing values, validation) | D | MA |
| 4 | Exploratory data analysis | A, D | MA, MK |
| 5 | Methods (regression, lag analysis, ITS, validation design, decision rules) | A | MK, RB |
| 6 | Results: H1 | I | MK |
| 7 | Results: H2 | I | RB |
| 8 | Robustness, monitoring and unsupported or inconclusive findings | I | MK, RB, MA |
| 9 | Findings summary table (supported / not supported / inconclusive) | I | all |
| 10 | Policy and business recommendations and implementation roadmap | R | RB |
| 11 | Limitations, assumptions, deviations (approved) | I | all |
| 12 | Appendix: data dictionary, figure registry, reproduction steps, work-log summary | | RS |

Guideline checklist (final submission requirements 1 to 8): problem and hypotheses (sections 1), sources and integration (2), dataset or reproducible procedure (2, appendix), quality and EDA (3, 4), methods and hypothesis assessment (5 to 9), evidence, findings, limitations (8, 9, 11), recommendations and roadmap (10), reproducible code (appendix and repo).

### 7.2 Presentation: three stages

| Stage | Slide | Content | Owner |
| --- | --- | --- | --- |
| 2 (analysis) | 1 | Data preparation: integration, cleaning, missing values, outliers, checks | RS, MA |
| 2 | 2 | EDA: F3, F4, F6, F7 | MA |
| 2 | 3 | Hypothesis testing: F9, F12, F13 and T7 | MK, RB |
| 2 | 4 | Unsupported or inconclusive hypotheses and why | MK, RB |
| 2 | 5 | Revised analysis plan | all |
| 3 (decision) | 1 | Final findings: each hypothesis classed | all |
| 3 | 2 | Business and policy implications | RB |
| 3 | 3 | Impact and limitations | all |
| 3 | 4 | Implementation roadmap: actions, timelines, responsible stakeholders, indicators | RB, MA |

Slide rules: one message per slide stated in the title, at most one figure and four lines of text, every number traceable to a table, every chart passing section 6, speaker notes with the source script.

### 7.3 Implementation roadmap content (Stage 3 slide 4)

Table with columns: action, finding it rests on and its status, responsible stakeholder (CAQM, state board, city health department), timeline (before winter 2026-27, within a year), indicator and target, data needed. Include "improve evidence" actions that the inconclusive results call for: keep stations reporting through outages, log the exact time of each GRAP order, extend the data over several winters, run a staggered or paired-city enforcement design.

---

## 8. Quality gates and integration testing

| Gate | Test | Who runs it |
| --- | --- | --- |
| G1 | `validate_final_dataset.py` passes; the test suite passes in a clean environment | MA, RS |
| G2 | Every EDA figure ticked on the checklist by author and reviewer; registry filled | MA, RS |
| G3 | Reviewer re-runs H1 and H2 scripts from the Parquet file and gets the same coefficients (to 3 significant figures) | RB for H1, MK for H2 |
| G4 | Robustness table complete; status of H1 and H2 assigned using section 5.4, written by someone who did not run the models | MA |
| G5 | Findings table T7: every number has a script, a table and a figure; no number is typed by hand | RS runs a script that compares the report text numbers with the tables |
| G6 | Report and slides read by all four; the guideline checklist in 7.1 is ticked; spelling, units and IST checked | all |
| G7 | Repo clean (no data files, no secrets, no stale docs), `README` and `REPRODUCE.md` correct, submission files opened on a second machine | RS |

**Integration test (end to end):** on a clean environment, run `python run_all.py --from-final`; it must (1) validate the dataset, (2) build the analysis tables, (3) produce every figure and table, (4) fill the registry, (5) fail if any figure is missing its caption or any number differs from its table.

**Viva preparation (shared, 22 to 23 Nov):** each person prepares answers to the questions below and the group rehearses once with someone asking questions from the report.

- Why this window and why hourly? What did the loss of 2023 to 2024 cost us?
- How do you know the time alignment is right? What changes at +1 and -1 hours?
- Why upwind fire counts, why 100 km and 45 degrees, and what if you change them?
- Why is the H1 sample only one season, and what does that do to the confidence intervals?
- GRAP is triggered by pollution. How does your design deal with that? What does it **not** deal with?
- How many events does H2 rest on? What happens if the biggest one is dropped?
- What is in the outage window (11 to 20 Jan 2026) and how did you handle it?
- What is wrong with the gas unit labels and how did you find it?
- Why did you choose each method, which course topic is it from, and what did you leave out?
- What would you recommend to CAQM, how sure are you, and what would change your mind?

---

## 9. Templates

### 9.1 Pre-task note (`docs/work_log/<initials>_<date>_<task>.md`)

```
Task: <ID and name>        Owner: <initials>        Reviewer: <initials>        Date:
1. What I reviewed (files, lines, outputs):
2. What the data looks like (shape, date range, missing counts; matches dictionary? yes/no):
3. What the task needs (inputs, outputs, acceptance):
4. Options considered (at least two) and the trade-off of each:
   - A:
   - B:
5. Choice and why (and, if marked DECISION, the reviewer's reply and date):
6. Risks / what could make this wrong:
7. After the work: acceptance checks run (PASS/FAIL), reviewer sign-off:
```

### 9.2 Figure caption template

`F<nn>. <What is plotted>, <unit of observation>, <period, IST>. <n stations / days / events>. <Uncertainty definition>. Shaded: <meaning>. Source: final_dataset.parquet, script <path>. Takeaway: <one sentence>. Not shown / caution: <one sentence>.`

### 9.3 Review comment template (for the cross-reviewer)

`Item: <figure or table or number>   Re-run from clean state: yes/no   Same result: yes/no   Checklist items failed:   Wording issues (causal language, missing qualifier):   Decision: accept / fix / reject`

---

## 10. Risks and what we do about them

| Risk | What we do |
| --- | --- |
| Instructor does not approve the new window or the optional methods | Fall back to regression plus ITS only; the plan already uses those as primary |
| The data machine or Parquet file is lost | Keep two copies (shared drive and a second laptop) and the checksum in `REPRODUCE.md` |
| H2 has too few clean events | Report event by event, call H2 inconclusive by the pre-set rule, move the recommendation to "improve the evidence" |
| Someone is blocked or absent | Backups in section 2; unblock within half a day |
| Late changes break numbers | Freeze scripts at G5; after that only wording changes, and every number is re-checked by script |
| Scope creep (dashboard, Docker, extra models) | Only items marked S or C, after the Must items pass their gate |
| Causal over-claiming | The wording rule in 1.3 and the review comment template; reviewers search the draft for "caused", "reduced by", "proved" |
