# Reia Baid: subtasks (GRAP intervention and policy analysis, H2)

Part of `docs/FINAL_DELIVERABLE_PLAN.md` (section 4.5 and the shared tasks). Tick boxes as you go. Dates are placeholders until the real deadlines are known; the semester ends 24 Nov 2026.

**H2:** PM2.5 falls after GRAP activation relative to the trend predicted by weather and fires alone.

**Before every subtask (the gate from the plan, section 1.1):** (1) open the files in "Review first"; (2) print shape, date range and missing counts of the data you will use and check them against `docs/final_dataset_dictionary.md`; (3) write a pre-task note in `docs/work_log/RB_<date>_<id>.md` with at least two options and your choice; (4) if the item says **DECISION**, wait for MK's yes; (5) after the work, run the acceptance checks and send it to MK for review.

Inputs: `data/processed/final_dataset.parquet`, `data/processed/grap_hourly.csv`, `data/processed/grap_orders.csv`, `data/processed/grap_gaps.csv`, `docs/grap_hourly_dictionary.md`.
Scripts go in `src/analysis/`, tables in `outputs/tables/`, figures in `outputs/figures/` (standards: plan section 6).

---

## T0.1 Deviation note to the instructor (10 to 11 Nov)

- [ ] **T0.1.1 Collect the facts.** Window and why (no OpenAQ data for 2023 and 2024; one burning season), hourly instead of daily, rows and variables (763,344 and 70), time-blocked validation instead of by-year, the H1 lag range (lag1 and lag2 only, unless RS builds lag3), control cities, optional methods. *Review first:* the Stage 1 summary PDF, README Limitations, plan section 0.
- [ ] **T0.1.2 Write `docs/deviation_note.md`**, one page, one table: proposal said / we did / why / what we ask the instructor to approve. Options: (A) email text only; (B) a short document attached to the email. Recommended: B.
- [ ] **T0.1.3 Get review** from all three teammates, send it, save the instructor's reply in the repo (`docs/instructor_reply.md` or a PDF).
- *Done when:* the reply is saved, or a follow-up date is set. Until then, use regression and ITS only.

## B1 GRAP event table (12 to 14 Nov)

- [ ] **B1.1 Review the stage history.** Read `grap_hourly.csv` and the `grap_orders.csv` rows. Confirm you can list all 30 changes (14 up, 16 down) and that they match the run output.
- [ ] **B1.2 Build the event list script** `src/analysis/10_grap_events.py`. One row per stage change with: `event_id`, `ts_ist`, `direction`, `stage_before`, `stage_after`, `order_date`, `time_source` (meeting, pib_posted, assumed), `grap_uncertain` at that hour, `grap_inferred`.
- [ ] **B1.3 Add context columns.**
  - [ ] Mean PM2.5 of the Delhi-NCR (treated) stations for the 7 days before, after dropping `network_outage` hours.
  - [ ] Share of valid PM2.5 hours in the 7 days before and the 7 days after.
  - [ ] Number of outage hours inside the window `[-7 d, +7 d]`.
  - [ ] Distance in days to the previous and the next stage change.
  - [ ] Weather summary of the 7 days before (mean wind speed, boundary layer height, rain).
- [ ] **B1.4 Choose the primary event set (DECISION, reviewer MK).** Options: (A) all 30 changes; (B) invocations to Stage II or higher with at least 7 clean days either side; (C) grouped by stage. Recommended: B for the main result, A and C descriptive. Write the rule in the pre-task note *before* you see results.
- [ ] **B1.5 Flag exclusions.** `overlaps_other_change` (another change within 7 days), `overlaps_outage` (any outage hours in the window), `usable_primary` (true/false) with a reason column.
- [ ] **B1.6 Spot check.** Open 10 events in the order PDFs (`data/raw/caqm_grap_pdfs/`) or the PIB text from `grap_orders.csv` and check date, stage and time source. Record the checks in `docs/work_log/`.
- [ ] **B1.7 Figure F3** (with MA): daily mean PM2.5 for treated and control stations with the GRAP stage as a strip below and the outage periods shaded. Follow the checklist in plan section 6.1.
- *Output:* `outputs/tables/grap_events.csv`, F3.
- *Done when:* every event reconciles with the orders, the number of usable events is stated with the reason for each exclusion, and MK has signed off.

## B2 H2 interrupted time series (14 to 19 Nov)

- [ ] **B2.1 Build the analysis series.** Daily mean PM2.5 for the treated group and for each control city, from valid hours only (a day needs at least 18 of 24 valid hours; if RS's `analysis_station_day.parquet` is not ready, compute it yourself from the Parquet file and tell RS so the two match). Also the daily weather means and the fire columns (`n_up_nh_100km_45deg_lag1`).
- [ ] **B2.2 Pre-set the rules (write them in the pre-task note before running):** effect windows (days 1 to 3 and days 4 to 7 after activation), buffer of 12 hours around the change, pre-period length (60 days before, excluding days within 7 days of another change), what counts as valid.
- [ ] **B2.3 Choose the primary method (DECISION, reviewer MK).** Options:
  - (A) segmented regression on the daily series (level and slope change at activation), with weather and fire controls;
  - (B) counterfactual: fit a weather-and-fire model on the pre-period, predict the post-period, compare actual with predicted;
  - (C) treated minus control, before and after (only if the handout covers it).
  Recommended: B primary (it matches H2's wording), A cross-check, C sensitivity.
- [ ] **B2.4 Fit the weather-and-fire model** (method B). `log(pm25) ~ wind speed + wind direction terms + temperature + humidity (from t2m and d2m) + blh + rain + pressure + fire (upwind lag1) + day-of-week`. Check the pre-period fit (R2, residual plot, residual autocorrelation) before using it to predict. State the minimum pre-period fit you will accept (for example R2 of at least 0.4 on the held-out last 14 pre-days).
- [ ] **B2.5 Predict and compare per event.** For each usable event: actual minus predicted for days 1 to 3 and 4 to 7, with a 95% interval from the prediction error (for example residual bootstrap by blocks of days, so autocorrelation is respected).
- [ ] **B2.6 Pool the events.** Options: (A) median of event effects with a bootstrap over events; (B) a random-effects mean. With 5 to 8 events say plainly that the interval is wide. Do not pool events that overlap each other.
- [ ] **B2.7 Cross-check with segmented regression** (method A) on the same events. Report whether the sign and size agree.
- [ ] **B2.8 Placebo events (the mean-reversion check).**
  - [ ] Treated stations: dates with a 7-day pre-level as high as the real events but no stage change within 7 days, picked by a fixed rule before looking at outcomes.
  - [ ] Control cities: the real event dates, same method. (Patna, Lucknow and Kanpur had no GRAP stage changes, so any "effect" there shows how much falls after a spike anyway.)
  - [ ] Compare each real event with the placebo distribution (share of placebos with a larger fall).
- [ ] **B2.9 Figures.**
  - [ ] **F12** one panel per event: actual (line), counterfactual (dashed) with 95% band, activation as a vertical line, 7 days before and after, outage hours shaded, same y-axis for all panels, ug/m3 and IST on the axes.
  - [ ] **F13** forest plot of effects per event and pooled, ug/m3 and %, ordered by date, zero line.
  - [ ] **F14** placebo distribution with the real events marked and the share of placebos below each.
- [ ] **B2.10 Tables.** T6a: per-event results (dates, n valid days, pre-fit R2, effect days 1 to 3 and 4 to 7 with CI).
- *Output:* `src/analysis/11_h2_its.py`, `outputs/tables/T06a_h2_events.csv`, F12 to F14.
- *Done when:* MK re-runs the script from the Parquet file and gets the same effects (3 significant figures), every figure passes the checklist, and the plot numbers match the table.

## B3 H2 robustness (18 to 20 Nov)

- [ ] **B3.1 Write the list of checks before running them** (in the pre-task note):
  - [ ] exclude `grap_uncertain` and `grap_inferred` hours, and use a 24-hour buffer around changes;
  - [ ] effect windows of 3, 5, 7 and 14 days;
  - [ ] only stations with at least 90% PM2.5 coverage;
  - [ ] leave out each sub-area in turn (Delhi, Ghaziabad, Noida, Gurugram);
  - [ ] counterfactual model with and without fire terms;
  - [ ] Stage I only versus Stage III/IV;
  - [ ] drop events whose window overlaps the 11 to 20 Jan 2026 outage;
  - [ ] drop the single largest event;
  - [ ] weather offset +1 and -1 hours (ask RS to provide the alternative weather columns).
- [ ] **B3.2 Run each check with the same code,** changing only one setting at a time. Save results in one long table: check, setting, n events, pooled effect, 95% CI.
- [ ] **B3.3 Figure F15.** Forest plot of the pooled effect under every check on one common x-axis, zero line, sample sizes on the right.
- [ ] **B3.4 Assign the status of H2 using the pre-set rules (plan section 5.4).** Ask MA to write the status from your table, since the person who runs the models should not choose the label.
- *Output:* `outputs/tables/T06b_h2_robustness.csv`, F15, status paragraph.
- *Done when:* the table has every check, no check was added or dropped after seeing results (or the change is written down and explained), and the status matches the rules.

## B4 Recommendations and roadmap (20 to 22 Nov)

- [ ] **B4.1 List findings and their status** (from T6 and T7: supported, not supported or inconclusive) with the sizes and intervals.
- [ ] **B4.2 Draft three to five recommendations (options: A recommendations tied one to one to findings; B a broader memo; recommended: A).** For each: the finding and its status; confidence; what we are **not** claiming; the action; responsible stakeholder (CAQM, state board, city health department); timeline; measurable indicator; data needed.
- [ ] **B4.3 Rules check.** No recommendation on an inconclusive finding except "collect this data" or "run this trial". Nothing on Punjab, Haryana or farmers (no stations there). No causal wording without the qualifier ("consistent with", "associated with").
- [ ] **B4.4 Roadmap table** (Stage 3 slide 4): action, rests on, owner, timeline (before winter 2026-27, within a year), indicator and target, data needed. Include evidence-improvement actions: keep stations reporting through outages, record the exact time of each GRAP order, extend data over several winters, a paired or staggered enforcement design.
- [ ] **B4.5 Limitations paragraph** with MA: one season, endogeneity of the stage, few events, outage overlap, control cities not comparable, time alignment, fire measurement, preliminary (NRT) data from July 2026.
- [ ] **B4.6 Slides** Stage 3 slides 2 to 4: implications, impact and limitations, roadmap. One message per slide, one figure at most, numbers from the tables.
- *Output:* `report/07_recommendations_roadmap.md`, slides.
- *Done when:* each recommendation names the table or figure it relies on and MA and MK have read it for over-claiming.

## Shared with the team

- [ ] **S1 Review MK's H1 work** (gate G3): re-run the H1 scripts, compare coefficients to 3 significant figures, tick the figure checklist for F7 to F11. Reply with accept, fix or reject.
- [ ] **S2 Backup for MK:** if MK is blocked, take over the lag analysis (K1) first.
- [ ] **S3 Hypothesis refinement session** (all four, 30 minutes, about 14 Nov): confirm the H1 and H2 wording and the decision rules in plan section 5.4. Rules are frozen after this.
- [ ] **S4 Report sections 5 (H2 methods), 7 (H2 results), 10 and 11** (write from your tables only; no typed numbers).
- [ ] **S5 Viva preparation (22 to 23 Nov):** answer the questions in plan section 8, especially: how does the design handle GRAP being triggered by pollution, how many events does H2 rest on, what happens without the largest event, what is in the January 2026 outage window.

---

## Dependencies (what you need from others, and what they need from you)

| You need | From | By |
| --- | --- | --- |
| Instructor reply on the deviation | instructor | before B2 results are written up |
| `analysis_station_day.parquet` (or compute your own) | RS (R4) | 14 Nov |
| Alternative weather offset columns for B3 | RS | 18 Nov |
| Decision on primary event set and H2 method | MK | before B1.4 and B2.3 |
| Figure F3 co-design | MA | 13 Nov |

| Others need | From you | By |
| --- | --- | --- |
| Event list and flags | MA, MK | 14 Nov |
| H2 results and robustness for slides and the findings table | all | 20 Nov |
| Recommendations and roadmap | all | 22 Nov |

## Weekly checklist for yourself

- [ ] Pre-task note written before each subtask (with two or more options)
- [ ] Decision items confirmed by MK
- [ ] Scripts run from a clean start, with a fixed seed for every bootstrap
- [ ] Every figure ticked on the checklist, then reviewed by MK
- [ ] Rules and windows frozen before results are viewed
- [ ] Wording checked for causal over-claiming
