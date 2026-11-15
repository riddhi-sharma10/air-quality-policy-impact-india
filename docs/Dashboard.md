# Dashboard plan: pages, content, data and owners

Project: *Do Burning and Emission Restrictions Reduce Air Pollution in Northern India?* (Group 3).
Follows `docs/FINAL_DELIVERABLE_PLAN.md` (task R5, section 6 figure standards, section 7 deliverables) and the notebook plan `docs/Final_Notebook_Plan.md`. Written 15 Nov 2026. **Adjust dates to the real deadlines.**
Members: **MA** Manya Awasthi, **MK** Mehak Kumar, **RS** Riddhi Sharma, **RB** Reia Baid.

---

## 1. What the dashboard is for

The deliverable plan lists the dashboard as a **Should** item (R5, owner RS): "a static HTML or notebook-free dashboard with the main charts", built **after** the Must items pass their gates, tested by a script that checks it shows the same numbers as the report. It has two jobs:

1. **Decision view for the stakeholders** in `report/01_stakeholder_and_kpis.md` (CAQM, state boards and DPCC, city health departments): what the data say, how sure we are, what to do next.
2. **Backup for the viva and Stage 3 presentation:** every headline number one click from its source table, script and caveat.

It is **read-only over the finished outputs**. It does not fit models and does not read the 360 MB CSV. It shows what the notebook and the scripts already saved.

### What it must never do

- Show a number that is not in `outputs/tables/` (the numbers test in section 6 enforces this).
- Say "GRAP reduced PM2.5". Hypothesis status is shown as **Supported / Not supported / Inconclusive** by the pre-set rules (plan 5.4), with the interval beside it.
- Hide missing data. Outage periods are grey gaps, never zero and never interpolated.

---

## 2. Recommended build

| Option | What | When | Verdict |
| --- | --- | --- | --- |
| **A. Static HTML (recommended)** | `src/dashboard/build_dashboard.py` reads `outputs/tables/*.csv` and `outputs/figures/*.svg` and writes `dashboard/index.html` plus one page per section. Interactive charts from small exported CSVs (about 1 MB). Opens by double click or from GitHub Pages | Core pages by 20 Nov, rest by 22 Nov | Matches R5 option A. No server, nothing to deploy, reviewer can open it on any laptop |
| B. Streamlit app | Same pages, live widgets | Only after G5 has passed | R5: only if A is done. Needs a server and one more dependency |
| C. Docker image of A or B | Packaging | Only if time remains | R5 "Could" |

**Recommendation: A.** Charts that already exist as figures (F3, F7 to F17) are embedded as SVG. Only four things need new exported data (section 5), so the dashboard stays small.

**DECISION (RS proposes, MA reviews, 16 Nov):** static images only, or SVG plus a few interactive filters (group, city, date range) on the PM2.5 explorer. Recommended: **filters on page 5 only**, everything else static.

---

## 3. Navigation map

```
 Overview ──┬─ Stakeholders and KPIs
 (page 1)   │
            ├─ DATA        3 Data and provenance ── 4 Data quality
            │
            ├─ EXPLORE     5 PM2.5 and GRAP explorer ── 6 Fires
            │
            ├─ RESULTS     7 H1 fire ── 8 H2 GRAP ── 9 Status and robustness ── 10 Monitoring
            │
            └─ ACT         11 Recommendations and roadmap ── 12 Limitations and reproduce
```

A fixed top bar carries the page names. A banner on every page reads: **"Associations from one burning season and one winter, not proven effects."** The footer carries the build time, the data file and its checksum.

---

## 4. Pages

Priority: **Core** (the story, build first), **Standard** (needed for a complete product), **Extra** (only if Core and Standard pass review). BADIR tags follow plan 7.1.

### Page 1 Overview `[Core, BADIR: B, I]` owner RS

*Question:* what did we ask, what did we find, how sure are we?
- Header: project title, window (19 Feb 2025 to 30 Sep 2026, IST, hourly), 54 stations (39 treated, 15 control), 763,344 rows. Numbers from the dataset summary, not typed.
- **Two status cards:** H1 and H2, each with the status word from the T7 table (Supported, Not supported or Inconclusive), the primary estimate and its 95% interval in plain units (H1 from T4, H2 from T6a), and a one-line reason. Values are read from the tables at build time, never typed.
- **KPI tiles** from `T00_kpi_baselines.csv`: mean daily PM2.5 treated vs control, share of days above 60 ug/m3, monitoring completeness.
- **Three "what to know" lines:** one burning season, GRAP is triggered by high pollution, outages cluster in January.
- *Source:* T7, T00, T4, T6a (notebook outputs), `docs/final_dataset_run_output.txt`.
- *Does not show:* any causal claim.

### Page 2 Stakeholders and KPIs `[Standard, BADIR: B]` owner MA

*Question:* who decides what, and what can our data support?
- Stakeholder table: CAQM and GRAP Sub-Committee, state boards and DPCC, city health departments, Punjab and Haryana agriculture departments, control-city boards; columns: decision, linked hypothesis, "can the data support it" (**Partly / Yes for monitoring / Outside the data**).
- KPI table with the five KPIs, definition, columns used and baseline; two KPIs (3 and 4) filled from H2 and H1 results once final.
- *Source:* `report/01_stakeholder_and_kpis.md` (words only), T00, T4, T6a.
- *Does not show:* what any agency actually decided (descriptions still need a source citation, an open item from M1).

### Page 3 Data and provenance `[Standard, BADIR: D]` owner RS

*Question:* where does each number come from, and are the sources joined consistently (SSOT)?
- **F0** join-flow diagram with row counts per step.
- **T1** sources table: provider, columns, retrieval date, coverage, licence, resolution, join key, unit. Rows from `docs/provenance_log.csv`.
- **F2** station map (longitude and latitude, colour by group, 25 km circle around central Delhi, no basemap).
- Time-alignment box: `hour_ist` is the START of the PM2.5 hour; ERA5 offset setting; gas columns realigned one hour; fire uses the previous IST day only. Gas unit note: archive labels are wrong, units from the dictionary.
- *Source:* `docs/provenance_log.csv`, `docs/final_dataset_dictionary.md`, `docs/final_dataset_run_output.txt`, `data/processed/stations_final.csv`.
- *Does not show:* raw files (not in Git).

### Page 4 Data quality `[Standard, BADIR: D]` owner MA

*Question:* how complete is the PM2.5 record, and what did we do about the gaps?
- **F1** availability heatmap (stations by month, share of hours with PM2.5, outage months marked).
- **T2** missingness table (by station and month, filterable).
- **Outage panel:** the 10 Jan 18:00 to 20 Jan 18:00 IST 2026 outage (241 hours), 928 outage hours in all, **112 of 971 Stage III/IV hours inside an outage** (94 + 18).
- Cleaning summary from `pollution_quality_report.csv`; missing-data rule (drop outage hours primary, short-gap interpolation as sensitivity, never across an outage).
- **Validation badge:** "51 checks passed, 0 failed" from `docs/validation_run_output.txt`, with the date it was run.
- *Does not show:* sensor accuracy (validation against AirNow station 8118 is described, r = 0.954 for the Delhi median).

### Page 5 PM2.5 and GRAP explorer `[Core, BADIR: A, D]` owner RB (F3 with MA)

*Question:* how does PM2.5 move over time, and when were GRAP stages in force?
- **Main chart F3:** daily mean PM2.5, treated and control (95% band over stations), GRAP stage strip below on the shared x-axis, outage periods grey. **Filters:** group, city (Delhi 25 km, Patna, Lucknow, Kanpur), date range, burning season only.
- Tabs for **F4** seasonal profile (monthly median and IQR), **F5** diurnal profile (winter vs monsoon), **F6** distribution with the 60 ug/m3 standard line.
- Threshold reading box: days above 60 ug/m3 for the filtered selection.
- *Source:* exported `D01_daily_group_series.csv` (daily mean and band per group and city, valid-day rule, section 5), `grap_changes.csv`, `grap_events.csv`, F4 to F6 tables.
- *Does not show:* that a stage change caused a change (stages follow pollution).

### Page 6 Fires `[Standard, BADIR: A, D]` owner MK

*Question:* when and where were the fires, and how do they line up with PM2.5?
- **F7** daily detections within 100 km (Delhi treated stations), burning season shaded, no-pass and `zero_assumed` days marked differently.
- **F8** lag correlation of daily PM2.5 with fire counts at lag 0 to 5 days, with 95% bars; **lag 0 labelled "diagnostic, not used"**.
- Box: fires enter the model only at lag 1 and 2; why (no same-day column exists).
- Small table (from the F7 cell): distribution of upwind detections per station-day in the burning season (median, 99th percentile, maximum, share with at least one detection).
- *Source:* `T03_h1_lag_correlations.csv`, F7 data, `fire_day_status` counts.
- *Does not show:* the source state of the fires (no Punjab or Haryana claim).

### Page 7 H1: fire and PM2.5 `[Core, BADIR: A, I]` owner MK

*Question:* are upwind fires on the previous day associated with higher PM2.5 after weather?
- **Headline card:** the primary estimate in plain units, in the form "x% PM2.5 per +n upwind detections, 95% CI [lo, hi], N station-days, D days, S stations", with n chosen from the EDA (not the plan's +50), and the status word. All values read from T4.
- **F9** coefficient plot across specifications and robustness checks (vertical zero line, n on the right).
- **F10** diagnostics, **F11** predicted versus actual on the test period; baselines table (climatology, persistence, weather only, fire plus weather) with RMSE, MAE and R2 in ug/m3 on the test period.
- Expandable "how to read this": the specification, the clustering, why one season gives wide intervals.
- *Source:* T4 and its companions (diagnostics, prediction, robustness), made by notebook Part 4.
- *Does not show:* a causal effect or an effect size we could rule out (the interval includes 0 and +29%).

### Page 8 H2: GRAP effect `[Core, BADIR: A, I]` owner RB

*Question:* is PM2.5 lower after a GRAP stage is invoked than weather and fires alone would predict?
- **Event table (T5):** every GRAP stage change and episode, with a flag for primary events and the reason for each exclusion (counts from the table).
- **F12** actual versus counterfactual per event, **F13** effect per event with 95% interval, **F14** placebo distribution with the real events marked, **F15** robustness forest plot, **F17** power curve.
- Warning panel: "GRAP is invoked on a forecast of worsening air, which the model cannot see. A fall or a rise after activation is not by itself an effect." If the power simulation (F17, optional) exists, a power line: how large a true fall the method could detect with this number of events.
- *Source:* T5, T6a (events), T6c (placebo), T6e (robustness), T6g (power, if made), from notebook Part 5.
- *Does not show:* a pooled estimate unless enough events pass the counterfactual fit rule; the page states how many do.

### Page 9 Hypothesis status and robustness `[Core, BADIR: I]` owner MA

*Question:* by the rules written before the results, what is the status of H1 and H2?
- **T7** status table: for each hypothesis, each plan 5.4 criterion, the observed value, met or not, and the source table; status word at the end of each block. Generated from the T7 table made in notebook Part 6, never typed.
- The three-status rule box (Supported / Not supported / Inconclusive) shown first, so a reader sees the rules before the results.
- Robustness summary: for each hypothesis, the number of checks with the same sign as the primary result out of the number run (counts from the tables); links to F9 and F15.
- *Source:* T7, T4 robustness table, T6e.
- *Does not show:* any status changed after the results (the rules are frozen in `report/09_hypothesis_status.md`).

### Page 10 Monitoring `[Standard, BADIR: I]` owner MA

*Question:* is the data feeding the model drifting, and does model error grow over time?
- **F16:** monthly RMSE and drift statistics for key inputs with the thresholds drawn (PSI 0.25, KS D 0.20, 1.5 times the reference RMSE).
- Tables T9a (input drift between training and test periods) and T9c (model error by month), made in notebook Part 6.3.
- Reading box (text from the cell's interpretation): which months, if any, are flagged; a reminder that drift alone does not show the model got worse and that a short reference period has little power.
- *Source:* T9a, T9c.
- *Does not show:* retraining or deployment decisions (A is a monitoring script, not a pipeline).

### Page 11 Recommendations and roadmap `[Core, BADIR: R]` owner RB (MA reviews)

*Question:* what should CAQM and the boards do, how sure are we, and what would change our mind?
- **T8** recommendation cards: finding, status, what we are **not** claiming, action, responsible stakeholder, timeline (before winter 2026-27, within a year), indicator and target, data needed, the table or figure it rests on.
- Rule shown on the page: where the evidence is inconclusive the recommendation is "collect this data" or "run this trial" (keep stations reporting through outages, log the exact time of each GRAP order, extend over several winters, staggered or paired-city enforcement design).
- Roadmap strip for Stage 3 slide 4.
- *Source:* `report/07_recommendations_roadmap.md` (RB), T7, T8.
- *Does not show:* source-state measures (stubble management, farmer compensation): outside our data.

### Page 12 Limitations and reproduce `[Standard, BADIR: I]` owner RS

*Question:* what are the limits of this work, and how can anyone reproduce it?
- Limitations list (plan section 0 Known facts, re-worded for a reader): one season, GRAP triggered by pollution, 971 Stage III/IV hours mostly in one winter, outage overlap, uncertain and inferred GRAP hours (6.8% and 21%), control cities not a clean counterfactual.
- Deviations from the proposal and their approval status (`docs/deviation_note.md`): window, hourly, time-blocked validation, lag range.
- Reproduce box: steps from `REPRODUCE.md`, the checksum of `final_dataset.parquet`, the order of scripts, link to the notebook.
- **Figure registry** table from `outputs/figure_registry.csv` (id, script, author, reviewer, status).
- Glossary (GRAP stages, PM2.5, ug/m3, IST, upwind, lag, counterfactual, CI).
- *Source:* `docs/FINAL_DELIVERABLE_PLAN.md` section 0, `docs/deviation_note.md`, `outputs/figure_registry.csv`.

### Optional extras `[Extra]`

| Page | Idea | Owner | Condition |
| --- | --- | --- | --- |
| City comparison | Small multiples for Delhi, Patna, Lucknow, Kanpur: winter mean, days above 60, completeness | MA | Pages 1 to 12 reviewed |
| Event explorer | Pick one GRAP episode, see its F12 panel and counterfactual table | RB | Page 8 done |
| Station drill-down | One station's PM2.5 with outage gaps and local weather | RS | Page 5 filters done |

---

## 5. Data contract: what each page reads

All values come from files in the repository that **the notebook writes** (`outputs/tables/`, `outputs/figures/`). The analysis after the final dataset is being redone from scratch (`docs/Final_Notebook_Plan.md`), so **nothing exists yet** except the two items marked below. Earlier-pass tables and figures on other branches are not used by the dashboard.

| Output | Made by notebook | Page(s) | Owner | Due (adjust) |
| --- | --- | --- | --- | --- |
| T00 KPI baselines | Part 1 | 1, 2 | MA | 17 Nov |
| T1 sources, F0 join flow | Part 2.1 | 3 | RS | 21 Nov |
| T2 missingness, F1 availability, F2 map | Part 2.3, 3.2, 3.3 | 3, 4 | MA | 17 Nov |
| F3 PM2.5 and GRAP timeline | 3.4 | 5 | MA with RB | 17 Nov |
| F4 seasonal, F5 diurnal, F6 distribution | 3.5 to 3.7 | 5 | RS | 17 Nov |
| F7 fire time series, F8 lag correlation, T3 | 3.8, 4.1 | 6 | MK | 17 to 20 Nov |
| T4 H1 regression, F9, F10, F11 and companions | Part 4 | 7, 9 | MK | 20 to 21 Nov |
| T5 GRAP events, T6a events, T6c placebo, T6e robustness, F12 to F15 (F17 optional) | Part 5 | 5, 8, 9 | RB | 20 to 21 Nov |
| T7 hypothesis status | 6.2 | 1, 9 | MA | 21 Nov |
| F16 monitoring, T9a, T9c | 6.3 | 10 | MA | 21 Nov (optional) |
| T8 recommendations | Part 7 | 11 | RB | 21 Nov |
| Figure registry | all parts | 12 | RS | 22 Nov |
| Dataset summary (rows, stations, dates, validation count) | `final_dataset.parquet`, `docs/validation_run_output.txt` | 1, 3, 4, 12 | RS | **exists today** |
| Provenance and dictionary | `docs/provenance_log.csv`, `docs/final_dataset_dictionary.md` | 3, 12 | RS | **exists today** |

Table and figure file names follow plan 5.3 (`outputs/figures/F<nn>_<name>.png/.svg`, `outputs/tables/T<nn>_<name>.csv`). The dashboard finds a file by its ID prefix, so the exact name suffix is the notebook author's choice.

**New small exports for the dashboard** (made by `src/dashboard/export_data.py` from `final_dataset.parquet` or `analysis_station_day.parquet`; each under about 1 MB):

| File | One row is | Used by |
| --- | --- | --- |
| `D01_daily_group_series.csv` | group (or city) by day: mean PM2.5, SE, number of valid station-days, GRAP stage, outage flag | page 5 |
| `D02_monthly_profile.csv` | group by month: median, Q1, Q3, n stations | page 5 (F4) |
| `D03_diurnal_profile.csv` | group by season by hour: mean, 95% CI, n | page 5 (F5) |
| `D04_dataset_summary.json` | rows, stations, groups, date range, checksum, outage counts, validation counts | pages 1, 3, 4, 12 |

Nothing else is read from the large files. The valid-day rule is the frozen one from the notebook (at least 18 of 24 valid hours; a group-day counts when at least half of the group's stations are valid).

---

## 6. Rules and tests

### 6.1 Rules for every page

- **BADIR tag** and the owner initials in the page header.
- **Caption** in the plan 9.2 template on every figure: what, unit of observation, period (IST), n, uncertainty definition, source and script, takeaway, caution.
- **Figure checklist** (plan 6.1): title, axis units, legend, n, uncertainty defined, gaps not zeros, IST, same scale across comparable panels, colour-blind-safe palette, readable at slide size.
- **Colours:** treated `#D55E00` (vermillion), control `#0072B2` (blue) on every page. Greys for outage and missing. Dark mode follows the same pair with equal contrast.
- **Wording:** "associated with" unless a design supports more. Status words only from T7.
- **Responsive layout:** works at phone width (single column), no horizontal scroll, text at least 14 px on the page, figures at least 12 pt when placed on a slide.
- **Source line** on every page: tables and scripts used, and the build time.

### 6.2 Tests (RS writes, MA reviews)

`tests/test_dashboard_numbers.py` and `python src/dashboard/build_dashboard.py --check`:

1. Every number printed on a page equals the value in its source table (parsed from the built HTML).
2. The status words on pages 1 and 9 equal the T7 table.
3. Every figure file referenced exists; every figure has a caption with the required fields.
4. No page mentions "caused", "reduced by" or "proved" without a qualifier (search).
5. The page set matches the list in section 4 (no missing or stray page).
6. A deliberately edited table (change one coefficient) makes the test fail.
7. The build runs from a clean checkout with only `outputs/` and `docs/`, with no access to the Parquet file, except for the export step.

---

## 7. Work division for the dashboard

| Member | Builds | Reviews |
| --- | --- | --- |
| **RS** | The build framework (`build_dashboard.py`, template, navigation, banner), the export script (D01 to D04), pages **1, 3, 12**, the numbers test, hosting and the Part 8 notebook link | Pages 2, 4, 9, 10 (MA's) |
| **MA** | Pages **2, 4, 9, 10**, the plain-language caption check, T7 text | Pages 1, 3, 12 (RS's) and page 11 |
| **MK** | Pages **6, 7** (copy, captions, "how to read this" boxes) | Pages 5, 8, 11 (RB's) |
| **RB** | Pages **5, 8, 11**, the F3 stage strip, recommendations T8 | Pages 6, 7 (MK's) |

Pairs follow plan 1.2 (MA to RS, MK to RB). A page is done when its reviewer has opened the built page from a clean checkout and ticked the figure checklist.

### 7.1 Build order and dates (adjust)

| Step | Date | What |
| --- | --- | --- |
| D0 | 16 Nov | Framework and page 1 (Overview) layout built on **placeholder values** and the dataset summary, which exists today. Decision on interactivity |
| D1 | 18 Nov | Export script; pages 5 (F3 first; F4 to F6 once MA finishes the EDA) and 9 with real tables |
| D2 | 19 to 20 Nov | After G3: pages 7 and 8. Core pages 1, 5, 7, 8, 9 done. **Stop here if Must items are late** |
| D3 | 21 Nov | Standard pages 2, 3, 4, 6, 10, 12; page 11 as soon as T8 exists |
| D4 | 22 Nov | Numbers test passes, all reviewed. **Freeze with the scripts at G5**; after that only wording |
| D5 | 23 to 24 Nov | Rehearse the demo; check the build on a second machine (G7) |

### 7.2 Risks

| Risk | What we do |
| --- | --- |
| Dashboard takes time from Must items | It is a Should item (R5). Do Core pages only until G3 and G4 are signed |
| An output is not made yet (F1, F2, F4 to F6, F0, T1, T8) | Page shows "pending" with the owner's name; the build fails in `--check` mode so it cannot ship that way |
| Numbers on the page drift from the report | The numbers test (section 6.2); freeze at G5 |
| Two colour schemes (MK and RB scripts differ) | Fix before D2 (notebook plan N0.5); the page template uses one palette |
| Heavy files make the page slow | Embed SVG only for figures; exports under 1 MB; no Parquet in the browser |
| Over-claiming in a headline | Status words only from T7; wording search in the tests |
