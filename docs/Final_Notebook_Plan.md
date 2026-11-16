# Final notebook prompt: build the whole analysis notebook, phase by phase

This file is the **prompt** for building `notebooks/air_quality_policy_impact.ipynb`. Give it to Claude (or follow it by hand). It replaces the earlier member-by-member notebook plan; that version is still in git history (commit `5874f5a`). **The whole notebook is built and run by one person on one laptop**, so there are no owners, reviewers, part files, shared Drive folders or hand-offs: just phases, done in order.

It is based on `docs/FINAL_DELIVERABLE_PLAN.md` (methods in section 4, hypotheses and decision rules in 5.4, figure standards in 6) and on `docs/final_dataset_dictionary.md` (column meanings and units). The work is split into **phases in the order they must be done**, not by person.

**How to run this prompt:** build **one phase at a time**. After each phase, stop, state which cells were added and what each output shows, and wait for "continue". Never build the next phase before the current one runs cleanly from top to bottom.

---

## 1. Task

You are building one Jupyter notebook that answers the project question:

> *Do burning and emission restrictions reduce air pollution in Northern India? A multi-source analysis of stubble fires, weather and GRAP interventions.*

It follows **BADIR** (Business question, Analysis plan, Data, Insights, Recommendations) and must run top to bottom on a single local machine (Jupyter or VS Code). No Colab, no Google Drive. It starts from one file, `data/processed/final_dataset.parquet` (already on the laptop), and does the EDA first, then the visualisations, then the two hypotheses, then the status and recommendations.

**Hypotheses (from the Stage 1 proposal)**
- **H1:** higher upwind fire counts in the previous 1 to 3 days are associated with higher PM2.5, controlling for wind, temperature, humidity and boundary-layer height.
- **H2:** PM2.5 falls after GRAP activation relative to the trend predicted by weather and fires alone.

### 1.1 The four key questions (where the notebook goes deeper)

| # | Question | Why it matters | Frozen criterion it feeds | Phases | First-pass finding (the notebook is the source of truth) |
| --- | --- | --- | --- | --- | --- |
| **Q1** (H1) | How big is the association between upwind fires and PM2.5 once weather is controlled? | It is the test of H1 itself and the number stakeholders ask for first, in plain units ("% change in PM2.5 per +5 upwind detections") | Criterion 1: primary coefficient above 0 with the decision interval excluding 0 | 8 and **8B.1 to 8B.5** | +9.5% per +5 detections [+1.4, +18.3]; shrinks to +5.5% [-0.9, +12.3] with month effects; the lag correlations show no timing |
| **Q2** (H1) | How much do fires add beyond weather? (RQ1) | Shows whether fires matter in practice, not only whether a coefficient is non-zero | Criterion 3: the fire model has a lower test error than the weather-only model | 8 and **8B.6 to 8B.9** | RMSE gain 0.91 ug/m3 (about 2%); both regressions are worse than simple persistence on the test period |
| **Q3** (H2) | After activation, is PM2.5 lower than the weather-and-fire model predicts? | H2 stated as a test: actual minus predicted over days 1 to 3 and 4 to 7, pooled with an interval | Criterion 1 of H2 (and at least 3 usable events) | 9 and **9B.1 to 9B.4** | -21.7% [-39.8, +1.3] for the one primary event, but its counterfactual failed the hold-out check (error 90%): zero usable events |
| **Q4** (H2) | Is the fall just mean reversion? | A stage is invoked when pollution is already high, so PM2.5 tends to fall anyway; this is the check that stops a false "supported" | Placebo criterion: real events in the lowest 10% of the placebo distribution | 9 and **9B.5 to 9B.8** | Only 2 comparable placebo dates under the frozen rule; control cities show departures of similar size on the same dates |

The robustness runs are the second criterion for both hypotheses (75% sign agreement). They support Q1 to Q4 and are run as support, not as headline questions.

**Audience of the notebook:** the course instructor, who has not seen the data. Every step must be understandable without asking the authors.

---

## 2. Fixed facts about the data (do not re-derive; read them from the data in the notebook, do not hard-code)

- `final_dataset.parquet`: 763,344 rows = 54 stations x 14,136 hourly rows, 70 columns, 19 Feb 2025 to 30 Sep 2026, time in IST. `hour_ist` is the **start** of the PM2.5 hour.
- **39 treated** stations (Delhi, Ghaziabad, Noida, Gurugram; GRAP applies) and **15 control** stations (Patna, Lucknow, Kanpur).
- Outcome: `pm25` (ug/m3). Outage flag: `network_outage` (true when fewer than half the stations report; this is *missing data, not clean air*). Policy: `grap_stage_applied` (0 to 4), with quality flags `grap_uncertain` and `grap_inferred`.
- Weather: `u10, v10, wind_speed, wind_from_deg, t2m_c, d2m_c, sp_hpa, blh_m, tp_mm`. Fire (previous days only, there is no same-day column): `n_nh_{50,100,200}km_lag{1,2}`, `frp_nh_*`, `n_up_nh_100km_45deg_lag1`, `frp_up_nh_100km_45deg_lag1`, `fire_day_status`, `fire_is_nrt`.
- Gas units are mislabelled "ppb" in the archive. Use the dictionary: `no`, `no2` in ug/m3, `nox` in ppm. Gases are secondary variables.
- **Weak spots the notebook must state honestly:** only one burning season (low power for H1); GRAP is switched on because pollution is already high (reverse causation, regression to the mean); Stage III/IV is rare and sits almost entirely in Nov 2025 to Jan 2026 (H2 rests on a handful of events); a network-wide outage (about 10 to 20 Jan 2026) overlaps some Stage III/IV hours; control cities differ in weather, fire exposure and local rules, so they are a comparison and not a clean counterfactual.

**State of the notebook (16 Nov 2026):** Phases 0 to 9 are built, run top to bottom and verified (292 cells, 25 figures, 39 tables in `outputs/`). **Still to do:** the two deeper phases **8B and 9B** (added below to answer the four key questions of section 1.1), then Phases 10, 11 and 12. Reuse existing cells and helpers (`group_day`, `valid_station_day`, `cluster_ols`, `build_series`, `fit_counterfactual`, `effect_from_fit` and the frozen constants of table T07b); do not rewrite them. Keep the project colours: treated `#D55E00`, control `#0072B2`, grey `#999999` for outages and missing data.

**Environment note:** parts of `statsmodels` are blocked by a security policy on the laptop, so the notebook uses `patsy` with `statsmodels.regression.linear_model` and computes other statistics (autocorrelation, bootstrap) by hand. `scikit-learn` works (checked). Test any new library with a one-line import before building on it.

---

## 3. Hard rules for every phase

### 3.1 Cell layout: every output gets the same four-part pattern

1. **Markdown intro** (2 to 5 lines): the question this step answers, the sample used, and what a reader should look for.
2. **Code cell** that does **one thing** (one table or one figure). Not everything in one cell.
3. **The output** (table, figure or printed numbers).
4. **Markdown explanation** straight after the output (see 3.4).

Never put data loading, cleaning, calculation and plotting in one cell. A figure is usually two cells: one that prepares the numbers into a small table and prints it, and one that plots that table.

### 3.2 Code style: moderate, readable, commented

- Beginner-friendly pandas and matplotlib: `groupby`, `pivot_table`, `merge`, `np.where`, `ax.bar`, `ax.plot`, `sns.heatmap`, `statsmodels` formulas. No classes, no decorators, no nested functions, no one-line clever tricks.
- **At most about 25 lines per code cell.** If longer, split it.
- A comment on every block saying *why*, not just *what*. Start each cell with a one-line comment, e.g. `# Step 5.2: monthly median PM2.5 by group`.
- Meaningful names (`pm25_daily`, `valid_hours`), not `a`, `tmp2`.
- A handful of small helper functions only, defined **once** in Phase 0 and reused (listed in 3.5). Do not import from `src/`; the reader must see all the logic in the notebook.
- No hard-coded numbers that come from the data. Constants (thresholds, window lengths) sit at the top of their phase in one visible cell.
- One seed for everything random: `SEED = 20261115`.
- After any calculation that matters, an `assert` or a printed check (row counts add up, the plotted number equals the table number).

### 3.3 Visual standards: nothing unlabelled, every value readable

Every figure must have **all** of these:

- **Title** that says what is shown, the unit of observation and the period, e.g. "Daily mean PM2.5, treated vs control stations, Feb 2025 to Sep 2026 (IST)".
- **Axis labels with quantity and unit**: "PM2.5 (ug/m3)", "Date (IST)", "Share of hours with data (%)". Log axes say "log scale".
- **Legend** naming every colour, line style, marker and shaded area (including "Network outage (no data)" and GRAP stage shading).
- **Values written on the graph.**
  - **Bar charts:** the value on top of every bar (`ax.bar_label(bars, fmt="%.1f")`; counts as integers with thousands separators, percentages with a % sign). Bars start at zero.
  - **Heatmaps:** the number inside every cell (`annot=True`, `fmt`), with a colour-bar label.
  - **Line charts:** label the key points directly (peak, minimum, start and end values, the value at a threshold) with `ax.annotate`; add a value table below when many lines are shown.
  - **Forest and coefficient plots:** the estimate and the 95% interval written next to each marker, and n on the right.
  - **Histograms and ECDFs:** the share above the 60 ug/m3 standard written beside the threshold line.
- **n shown:** number of stations, days or events behind each element, in the title, legend or an annotation.
- **Uncertainty defined** whenever shown ("95% CI", "5th to 95th percentile", "IQR").
- **Missing data is a gap, outages are grey bands, never zero and never interpolated.**
- Colour-blind-safe palette, same colour meaning in every figure; no dual y-axes unless unavoidable (then each axis coloured to match its line and the reason is stated).
- Font size at least 11 for labels and 9 for value labels; no text on top of data; `tight_layout()`; `figsize` big enough that nothing overlaps (tall for heatmaps).
- A **caption line** under the figure in markdown: `F05. <what>, <unit of observation>, <period, IST>. n = <...>. <uncertainty>. Source: final_dataset.parquet.`
- Save every figure with `save_fig(fig, "F05_seasonal_profile")` (PNG at 200 dpi and SVG) and every table with `save_table(df, "T02_missingness")`.

### 3.4 Explanation rule: every output is explained in a markdown cell

After **every** table and figure, add a markdown cell with three short parts:

1. **What it shows:** one or two sentences in plain words (what is on each axis, what the colours mean).
2. **What we learn:** the main takeaway, with the key numbers. Numbers must come from variables, not be typed by hand. Do this with a small code cell that renders markdown, for example:
   ```python
   # Takeaway: numbers come from the variables above, so the text can never drift from the output
   from IPython.display import Markdown, display
   display(Markdown(f"**What we learn:** treated stations average **{m_t:.0f} ug/m3** against **{m_c:.0f} ug/m3** at control stations ({gap:.0f} ug/m3 higher)."))
   ```
3. **What it does not show:** one limitation or caution (association only, one season, outage gap, etc.).

Use **"is associated with"**, never "caused", "reduced by" or "proved". Plain language; explain any term the first time it appears (for example *lag*, *clustered standard error*, *counterfactual*).

### 3.5 Helper cell (Phase 0, define once, reuse everywhere)

Keep these small and commented: `load_df()` (read the parquet, parse `hour_ist`, add `date_ist`), `save_fig(fig, name)`, `save_table(df, name)`, `label_bars(ax, fmt)` (writes values on bar tops), `show_takeaway(text)` (renders markdown), `valid_station_day(df, min_hours)` and `group_day(...)` (Phase 4), `cluster_ols(formula, data, cluster)` (Phase 7).

### 3.6 Scientific rules (from the deliverable plan)

- **Valid hour:** `pm25` present and not `network_outage`. **Valid station-day:** at least 18 of 24 valid hours (sensitivity: 12 and 20). A group-day counts when at least half of that group's stations are valid.
- **Primary missing-data rule:** drop outage hours. Short-gap interpolation (up to 3 hours, never across an outage) is a sensitivity run only.
- **Winter sample (main for H1 and H2):** 1 Oct 2025 to 28 Feb 2026. The full window is a sensitivity run.
- **Decision rules for H1 and H2 are fixed before any model is fitted** (the table in Phase 1) and are not changed afterwards. Anything added after seeing results is labelled "added after seeing results".
- Report effect sizes with **95% confidence intervals**, the unit of observation and what the standard errors are clustered on. Say how many specifications were tried.
- **"Inconclusive" is a valid result.** Write it plainly if the data say so.
- Time-blocked validation (train Feb to Dec 2025, test Jan to Sep 2026); by-year validation is impossible with this window.
- Only methods from the course handout. Anything else is labelled "extension" and kept optional.
- **Extension analyses (Phases 8B and 9B).** Every analysis there is **added after seeing results**: its cell heading says so ("ADDED AFTER SEEING RESULTS"), it is counted in the list of runs tried (table `T07d2`, an extension of `T07d`), and it **cannot change the frozen status**: Phase 10 applies the Phase 7 rules to the frozen runs only, and shows extension results in a separate block as supporting or weakening evidence. Choices between alternatives (for example which counterfactual model to use) are made on **pre-event accuracy only** (the hold-out rule), never by looking at the estimated effect. Subgroup tables state how many subgroups were examined and make no claim of a difference unless the interaction interval excludes zero. No new decision rule is introduced.

---

## 4. The phases

Each phase lists its cells in order. Priority: **M** must, **S** should, **C** could. If time is short, cut C, then S, never M.

### Phase 0: Setup and loading (M)

| Cell | Type | Content |
| --- | --- | --- |
| 0.1 | markdown | Title, one-paragraph project summary, table of phases, how to run (local, from the repo root), "results are associations, not proven causes" |
| 0.2 | code | Local paths only (parquet at `data/processed/final_dataset.parquet`, outputs in `outputs/`), `SEED`, create `outputs/figures` and `outputs/tables` |
| 0.3 | code | Imports, plotting theme, colour constants `COL`, `GREY`, global font sizes |
| 0.4 | code | Helper functions from 3.5 |
| 0.5 | code | `df = load_df()`; print shape, stations, hours, date range, groups |
| 0.6 | code | Core checks with `assert`: 54 x 14,136 rows, 39 treated and 15 control, unique (`station_id`, `hour_ist`), `pm25` between 0 and 1000, no same-day fire column |
| 0.7 | markdown | Explain in words what the file is and what the checks proved |

### Phase 1: Business question, hypotheses, KPIs, decision rules (M)

| Cell | Type | Content |
| --- | --- | --- |
| 1.1 | markdown | **Stakeholder table:** CAQM, state boards, city health departments; the decision each makes; the evidence this analysis can offer; "outside our data" where true (no stations in Punjab or Haryana, so no state-specific stubble claims) |
| 1.2 | markdown | Business problem, objective, key questions, **H1 and H2** stated as in section 1 |
| 1.3 | code | **KPI table computed from `df`:** daily mean PM2.5 (treated, control), days above 60 ug/m3, data completeness, outage hours. KPIs for the 3-day response to a stage change are added after Phase 8. Output: `T00_kpis` |
| 1.4 | markdown | Explain every KPI: definition, unit, source column, how a stakeholder would use it |
| 1.5 | markdown | **Decision-rule table (frozen before results):** supported, not supported and inconclusive for H1 and for H2, as in the deliverable plan section 5.4. State: "these rules were written before the models were fitted" |
| 1.6 | markdown | **Evaluation strategy:** winter sample, valid-day rule, time-blocked split, clustered standard errors, placebo checks |

### Phase 2: Understand the data: sources and structure (M)

| Cell | Type | Content |
| --- | --- | --- |
| 2.1 | markdown + code | **Sources table T1** (provider, columns, coverage, resolution, join key, unit), read from `docs/provenance_log.csv` if present, else typed from the dictionary |
| 2.2 | code | **F0 data-integration flow:** boxes from raw sources to the final table with row counts at each step (take the counts from `docs/final_dataset_run_output.txt`); label every arrow with its join key |
| 2.3 | markdown | Explain the join logic: stations spine, pollution by hour, weather by nearest cell, fire by station and IST date, GRAP by hour; why fire has only lags; the time alignment settings |
| 2.4 | code | `head()`, data types count, column groups (identifiers, pollution, weather, fire, policy, calendar) |
| 2.5 | code | **Bar chart:** stations per group and sub-area, **count written on every bar** |
| 2.6 | markdown | Explanation of the structure and the station balance (39 vs 15 and why that matters) |

### Phase 3: Data quality: missing data, outages, cleaning, validation (M)

| Cell | Type | Content |
| --- | --- | --- |
| 3.1 | code | **T2 missingness by column** (count and %) for the key columns |
| 3.2 | code | **Bar chart:** % missing per key column, **% written on every bar** |
| 3.3 | markdown | Explain which columns are mostly complete, which are sparse (`nox`, local sensors), and why the first 5 hours have no weather |
| 3.4 | code | **Outage table:** each outage run (start, end, hours) from `network_outage` |
| 3.5 | code | **Bar chart:** hours per outage run, **hours written on top**; the January 2026 run highlighted |
| 3.6 | code | **Stage III/IV hours inside outages:** count them in the cell and print the share (cross-check against `src/validate_final_dataset.py`) |
| 3.7 | markdown | Explain the outage: why it is missing data and not clean air, how it is handled (dropped in the primary run), and why this matters because it overlaps with the strongest GRAP stages |
| 3.8 | code | **Cleaning summary** from `data/processed/pollution_quality_report.csv` as a table, plus a bar chart of values set to empty per column with **counts on the bars** |
| 3.9 | code | **Validation cell:** re-run the checks of `src/validate_final_dataset.py` (or the main ones) on the loaded file; print PASS or FAIL per check and the total |
| 3.10 | markdown | State the missing-data rule, the valid-day rule, and the two caveats: `n_pm25` is a raw count, and gas units are mislabelled |

### Phase 4: Prepare analysis tables (M)

| Cell | Type | Content |
| --- | --- | --- |
| 4.1 | markdown | Why we move from hourly to daily: noise, autocorrelation, and the fire variable is daily |
| 4.2 | code | Mark valid hours; count valid hours per station-day |
| 4.3 | code | **Station-day table** (daily mean PM2.5, valid hours, daily weather, fire columns, max GRAP stage and the stage at 12:00). Keep days with at least 18 valid hours. Also build the 12-hour and 20-hour variants |
| 4.4 | code | **Group-day series** for treated and control (mean over stations, with 95% band over stations, number of stations) |
| 4.5 | code | **Checks:** the row counts add up; recompute 5 station-days by hand from the hourly data and `assert` they match |
| 4.6 | code | Save `analysis_station_day.parquet` and print its column list |
| 4.7 | markdown | Document the table: columns, unit, how many station-days were kept or dropped and why |

### Phase 5: EDA, numbers first (M)

| Cell | Type | Content |
| --- | --- | --- |
| 5.1 | code | **Summary statistics** of PM2.5 by group (mean, median, standard deviation, 5th, 95th, 99th percentile, share of days above 60 ug/m3) |
| 5.2 | code | Same by month and by season |
| 5.3 | code | **GRAP stage frequency:** hours and days at each stage, by month |
| 5.4 | code | **Fire distribution:** median, 99th percentile, maximum and standard deviation of `n_up_nh_100km_45deg_lag1` for treated stations in the winter sample (this fixes the unit of the H1 effect: "per +10" or "per 1 SD") |
| 5.5 | code | **Correlation matrix** of PM2.5, weather and fire variables (daily, treated, winter) |
| 5.6 | markdown | Explain each table in words: PM2.5 level and spread, how rare Stage III/IV is, how skewed the fire counts are |

### Phase 6: EDA, visualisation (M unless marked)

For each figure follow section 3.1 to 3.4 exactly: markdown intro, prepare-data cell, plot cell, markdown explanation with caption. Specifications:

| ID | Pri | Figure | Required labels and values |
| --- | --- | --- | --- |
| F1 | M | **Data availability heatmap:** months (x) by sub-area (y), colour = % of hours with PM2.5. A second, station-level version (small font) in a following cell | Percent written in every cell; colour-bar "Share of hours with PM2.5 (%)"; outage months marked; treated and control separated |
| F2 | S | **Station map:** longitude and latitude, coloured by group, city labels, 25 km circle around central Delhi, "no basemap, coordinates in degrees" | Number of stations written next to each city label |
| F3 | M | **PM2.5 and GRAP timeline:** top panel daily mean PM2.5 for treated and control with 95% band over stations; bottom strip with the GRAP stage as steps; outages grey on both | 60 ug/m3 standard as a labelled line; peak value and date annotated for each group; stage numbers written in the strip; legend for outage and stages |
| F4 | S | **Seasonal profile:** monthly median PM2.5 as bars with IQR error bars, by group | Median written on top of every bar; n stations per month in a table row or under the axis |
| F5 | S | **Diurnal profile:** mean PM2.5 by hour of day, winter vs monsoon, by group, 95% CI | Peak and lowest hour annotated with values; legend for season and group |
| F6 | M | **Distribution:** histogram or ECDF on a log axis by group, with the 60 ug/m3 standard | Share of hours above 60 ug/m3 written for each group beside the line; median written; axis "PM2.5 (ug/m3, log scale)" |
| F7 | M | **Fire time series:** daily detections within 100 km (treated stations mean) with the burning season shaded; `outage` days and `zero_assumed` days marked in different symbols | Maximum and its date annotated; shading, markers and units in the legend |
| F7b | S | **Weather panels:** monthly mean of wind speed, temperature, boundary-layer height (3 small bars panels, same x-axis) | Value on top of every bar; units in each panel title |
| F7c | S | **GRAP stage bar chart:** hours at each stage, treated stations | Count written on every bar; note that stages are not randomly assigned |

After the figures:

| Cell | Type | Content |
| --- | --- | --- |
| 6.x | markdown | One explanation cell per figure (section 3.4) |

### Phase 7: EDA findings table and the frozen analysis plan (M)

| Cell | Type | Content |
| --- | --- | --- |
| 7.1 | code + markdown | **EDA findings table** ("what the EDA tells H1 and H2"): PM2.5 level and spread by group, how often each GRAP stage occurs and when, the fire season, the January gap, treated versus control. Numbers come from variables. Output: `T_eda_findings` |
| 7.2 | markdown | **Frozen H1 plan** (written before any model is fitted): outcome (log PM2.5, station-day, winter sample); primary specification; effect unit (decided in 5.4); sensitivity list; diagnostics; decision rule |
| 7.3 | markdown | **Frozen H2 plan:** event rule (Stage II or higher with at least 7 clean days either side); effect windows (days 1 to 3 and 4 to 7); 12-hour buffer around each change; fit window (60 days, excluding days within 7 days of another change); counterfactual model; placebo rule; decision rule |
| 7.4 | markdown | Reminder of the number of specifications planned, so that the report can say how many were tried |

### Phase 8: H1, fire and PM2.5 (M unless marked)

Method: deliverable plan section 4.4 (K1 to K4). Everything below uses the winter sample unless stated.

| Cell | Type | Content |
| --- | --- | --- |
| 8.1 | code + figure | **Lag correlation (F8, T3):** correlation of the Delhi-NCR daily mean PM2.5 with fire counts at lag 0 to 5 days. Lag 0 drawn in a different colour and labelled "diagnostic, not used". **Correlation value written above each bar, 95% CI as error bars, n days in the title** |
| 8.2 | markdown | Explain: fires lead PM2.5, correlation is not a model, the CI is wide |
| 8.3 | code | **Primary regression (T4):** `log(pm25) ~ n_up_nh_100km_45deg_lag1 + wind speed + wind direction terms + t2m_c + humidity (from t2m_c, d2m_c) + blh_m + tp_mm + sp_hpa + hour and day effects + station fixed effects`; standard errors clustered by station (and by date as a check); `cluster_ols()` helper |
| 8.4 | code | Convert the coefficient to **plain units** (for example "% change in PM2.5 per +10 upwind detections") with its 95% CI; print n observations, days and stations |
| 8.5 | markdown | Explain the coefficient in a sentence a non-statistician understands, and say what "association" means here |
| 8.6 | code + figure | **Diagnostics (F10, S):** residuals vs fitted, residual ACF, Q-Q plot, in one panel set; variance inflation factors as a table |
| 8.7 | code + figure | **Prediction (F11):** train Feb to Dec 2025, test Jan to Sep 2026; baselines: climatology by month, persistence, weather only; RMSE, MAE and R2 for each in a table. **Bar chart of RMSE per model with values on top**, and a predicted vs actual scatter with the 1:1 line and RMSE and n written on it |
| 8.8 | markdown | Explain: how much do fires add beyond weather (the answer to RQ1) |
| 8.9 | code + figure | **Robustness (T4g, F9, S):** drop outage vs interpolate short gaps; drop `fire_is_nrt` rows; drop `outage` fire days; leave one station out; leave one city out; other radius and angle; full window; placebo (future fire lag, expected about zero). **Forest plot: estimate and 95% CI written next to each marker, same x-axis, n on the right, vertical zero line** |
| 8.10 | markdown | Interpretation in plain units, how many checks agree in sign, and what H1 does **not** show (one season, low power, association only). Inconclusive is allowed |

### Phase 8B: H1 in depth: size, shape, where it holds, and how much fires add (M for 8B.6 and 8B.10, C for 8B.9, S for the rest)

**Questions answered:** **Q1** (how big is the association once weather is controlled?) and **Q2** (how much do fires add beyond weather?). Build it right after Phase 8 and before Phase 9, reusing the Phase 8 objects (`primary_frame`, `formula`, `cluster_ols`, `h1_frame`, `fit_h1`, `pct`, the frozen constants). Read section 3.6: every cell here is an **extension added after seeing results**, labelled as such, counted in `T07d2`, and unable to change the frozen status. Give each cell the usual four parts (intro, one-thing code cell, output, explanation with *what it shows / what we learn / what it does not show*).

**What the first pass left open.** The primary effect is +9.5% per +5 detections but it halves when month effects are added, the lag correlations show no timing, and fire adds only about 2% to prediction while both regressions lose to persistence. These cells ask *why*, *where* and *how much in practice*.

| Cell | Pri | Content |
| --- | --- | --- |
| 8B.0 | M | **Markdown:** the two questions, the extension rule of 3.6, the list of cells below. Start `T07d2` (the runs added after seeing results) and append to it in every cell |
| 8B.1 | S | **Dose-response shape (F18).** Replace the linear fire term by bins of the upwind count (0, 1 to 2, 3 to 5, 6 to 10, above 10), same controls and fixed effects, date-clustered 95% intervals, reference bin = 0. Plot the effect per bin (% change in PM2.5) with the value and the number of station-days written on every bar. Test linearity (a joint test that the bins follow a straight line, or a quadratic term). *Question:* is "+9.5% per +5" a straight line or carried by a few high-fire days? |
| 8B.2 | S | **Where does the association hold? (F19, T04i).** Interactions of the fire term with: month group (Oct to Nov against Dec to Feb), sub-area (Delhi against the rest), wind regime (calm against windy at the median wind speed), boundary-layer height (below and above the median) and wind-from sector (north-west against other). Report the effect per +5 in each subgroup with its interval and n in a forest plot with the values written. State how many subgroups were examined and claim a difference only where the interaction interval excludes zero |
| 8B.3 | S | **Season confounding in detail (F20).** Why does the effect shrink with month effects? Fit a ladder of specifications: station and weekday effects (primary), plus month effects, plus **week effects**, plus **date effects** (identified only from differences *between stations on the same day*). Also split the fire variable into its month mean and its deviation from the month mean (within-between). Forest plot of the effect per +5 across the ladder, values written. *Question:* does the association survive when everything common to a day or a week is removed? |
| 8B.4 | S | **Timing at regression level (T04j).** The lag correlations could not show timing. Fit the all-direction 100 km count with two separate terms: the previous day (`lag1`) and the day before that (`lag2 - lag1`), and report both coefficients, their sum, and the comparison with the upwind lag-1 model. Make clear that the upwind variable exists only for lag 1. *Question:* is the association carried by yesterday's fires, by the day before, or by both? |
| 8B.5 | S | **What it means in practice (T04k, F21).** Scenario table from the primary model, winter treated sample: mean PM2.5 and share of station-days above 60 ug/m3 under (a) observed fires, (b) fires capped at the winter median, (c) fires reduced by half, (d) fires set to zero. Intervals from a date-block bootstrap of the coefficient. Bar chart with values written. Label it "association-based scenario, not a policy forecast" and repeat the caveats (proxy for smoke, one winter, nearby fires only) |
| 8B.6 | M | **How much do fires add beyond weather? Variance decomposition (T08d, F22).** Hierarchical R-squared: station and weekday effects only, then plus weather, then plus fire. Report the increment from fire with a date-block bootstrap interval, and put it beside the out-of-sample RMSE gain of Phase 8. Bar chart of R-squared by block, values written. This is the in-sample half of Q2 |
| 8B.7 | S | **Does fire add information in the months it matters? Blocked cross-validation (T08e, F23).** Leave one month out (train on all other months, test on the left-out month), for weather only, weather plus fire, and each of these plus yesterday's PM2.5. Report the RMSE gain from fire for every month with a date-block bootstrap interval and highlight Oct to Feb. State that this is an *explanation* design (it uses future months in training) and not a forecast |
| 8B.8 | S | **Better baselines under the frozen split (T08f).** Under the frozen train and test periods add the persistence-plus-weather and persistence-plus-weather-plus-fire models and report whether they beat persistence and whether fire adds anything on top. Show the monthly error table again with these models. This explains in numbers why the frozen weather models failed (extrapolation to a colder January) and what a fair predictive comparison looks like |
| 8B.9 | C | **Boosted-model comparison (extension; run only if `docs/methods_check.md` or the instructor allows it, otherwise skip with a note).** `HistGradientBoostingRegressor` on log PM2.5 with the same features and split; tune only on blocked folds *inside the training period*; compare test RMSE with the linear models; permutation importance of the feature groups (weather, fire, station) on the test period, with values on the bars (F24, T08g); try `shap` with a one-line import test and use it only if it loads. State that trees cannot extrapolate beyond the training range, so January stays hard, and that importance is not an effect size |
| 8B.10 | M | **Markdown: answers to Q1 and Q2 in plain words.** For each: the frozen-run answer from Phase 8, what the extensions add (shape, where, timing, season, practical size, share explained), and what they do not show. State that the frozen criteria and the status are unchanged, list the cells added in `T07d2`, and say how this feeds Phase 10 (supporting block of T7, the KPI "share of variation explained by fire beyond weather") |

### Phase 9: H2, GRAP and PM2.5 (M unless marked)

Method: deliverable plan section 4.5 (B1 to B3).

| Cell | Type | Content |
| --- | --- | --- |
| 9.1 | code | **Event table (T5):** every GRAP stage change from `grap_stage_applied`: date and hour, direction, stage before and after, `time_source` if available, `grap_uncertain`, pre-change 7-day PM2.5, outage hours inside the window, overlap flag, usable flag with reason. Reconcile the number of changes with `data/processed/grap_orders.csv` and print the match |
| 9.2 | code + figure | **Events on the timeline:** F3 with event markers; **bar chart of changes by month and direction with counts on the bars**; usable and unusable events in different colours |
| 9.3 | markdown | Explain how many events are usable and why the rest were excluded; say plainly that this is a small number |
| 9.4 | code | **Counterfactual model per event:** fit `log(pm25)` on weather and fire (plus day of week) in the fit window, check the fit on held-out days, predict days 1 to 7 after activation; effect = actual minus predicted; 95% interval by block resampling (use `SEED`) |
| 9.5 | code + figure | **Per-event panels (F12):** actual (line) versus counterfactual (dashed) with 95% band, activation line, 7 days before and after, outage hours grey. **Effect size and CI written in each panel title** |
| 9.6 | code + figure | **Effect per event (F13, T6a):** forest plot, ordered by date, with the pooled estimate; value and interval written next to each marker; pool only events that pass the fit rule |
| 9.7 | code + figure | **Placebo check (F14, T6c):** days as polluted as the real events but without a stage invoked; the same dates in the control cities. Histogram of placebo effects with the real events as labelled vertical lines and **the share of placebos below each real event written on the plot** |
| 9.8 | markdown | Explain the mean-reversion problem (stages are raised when pollution is already high) and what the placebo shows |
| 9.9 | code | **Cross-check (S):** segmented regression on the daily Delhi-NCR series, level and slope change at activation |
| 9.10 | code + figure | **Robustness (T6e, F15):** exclude `grap_uncertain` and `grap_inferred` hours; windows of 3, 5, 7, 14 days; stations with at least 90% coverage; leave one sub-area out; with and without fire terms; Stage I versus Stage III/IV; drop events overlapping the January outage; drop the largest event. One forest plot, common axis, values written |
| 9.11 | code + figure | **Power simulation (C, F17):** how large a true fall would this method detect with this number of events |
| 9.12 | markdown | Interpretation: never "GRAP reduced PM2.5 by X"; say that the model cannot see the forecast that triggers a stage; "inconclusive" may be mostly a statement about power |

### Phase 9B: H2 in depth: why the counterfactual failed, a difference-in-differences check, and mean reversion (M for 9B.1, 9B.5 and 9B.9, S for the rest, C for 9B.4)

**Questions answered:** **Q3** (is PM2.5 lower after activation than the weather-and-fire model predicts?) and **Q4** (is the fall just mean reversion?). Build it right after Phase 9 and before Phase 10, reusing the Phase 9 objects (`series_treated`, `series_control`, `build_series`, `fit_counterfactual`, `effect_from_fit`, `event_effects`, `placebo_effects`, the event table and the frozen constants). Read section 3.6: every cell is an **extension added after seeing results**, counted in `T07d2`, and unable to change the frozen status.

**What the first pass left open.** Only one event qualifies under the primary rule, its counterfactual failed the hold-out rule (error 90%: the ten days before it are the steep run-up of a smog episode), only two comparable placebo dates exist, and the control cities show departures of similar size on the same dates. These cells ask *why the model failed*, *whether a better pre-event model exists*, *what a difference-in-differences with the control cities says*, and *how much of the fall mean reversion alone would give*.

**Rule for alternative counterfactuals.** An alternative may replace the frozen model for an event only if it passes the **same hold-out rule** (error at most 25%), and it is chosen on pre-event accuracy over all events and placebo dates, never on the effect it gives. Both the frozen result and the alternative result are always shown.

| Cell | Pri | Content |
| --- | --- | --- |
| 9B.0 | M | **Markdown:** the two questions, the rule above, the extension rule of 3.6 and the list of cells below |
| 9B.1 | M | **Why did the counterfactual fail? (T06g, F25).** For each fitted event: number of fit days, number of parameters, condition number of the design, hold-out error, and the share of hold-out error that comes from the last three days before the event. Figure: for each event, actual and fitted PM2.5 over the fit window with the hold-out days marked and the error written. Show that the failure comes from fitting 16 parameters on 26 to 48 days and predicting a run-up unlike the earlier days |
| 9B.2 | S | **Alternative counterfactuals (T06i, F26).** Declare four alternatives *before* looking at their effects: (a) a parsimonious weather model (wind speed, boundary-layer height, temperature, upwind fire; no wind direction, rain, pressure, humidity or weekday terms); (b) the frozen model with ridge shrinkage, the penalty chosen by leave-one-out inside the fit window; (c) a **control-city counterfactual**: the treated log PM2.5 regressed on the control cities' log PM2.5 of the same day alone (regional shocks such as Diwali cancel because the control cities had no GRAP); (d) the control cities **plus** the parsimonious weather terms. The method carried forward is the one with the lowest median hold-out error over events and placebo dates; for 9B.4 a fallback to the method that passes for the most upward changes is declared in the notebook before any effect is computed. Report the hold-out error of every method for every event and for the placebo dates, as a bar chart with values written (F26), and say which events become usable |
| 9B.3 | S | **Difference-in-differences event study with the control cities (T06j, F27).** Outcome: the daily difference between treated and control log PM2.5 (days where both are valid). Event-time coefficients for days -10 to +14 relative to the baseline of days -7 to -1, for each event and pooled over the event sets. **Pre-trend check:** a joint test that the coefficients for days -10 to -2 are zero. Plot the coefficients with intervals, activation and buffer marked and values written at selected days. With so few events, give intervals by event and make no pooled claim beyond what the events support. This is the proposal's difference-in-differences logic; state its assumption (parallel trends) and that the control cities differ in weather and local rules |
| 9B.4 | C | **Pooled event-time profile of all upward activations (T06k, F28).** Using the best method that passes the hold-out rule, the average of actual minus counterfactual from day -7 to day +14 over all 14 upward changes (events overlap, so cluster by episode), split by stage size (Stage I against II or higher), n per day written. *Question:* do PM2.5 falls follow activations in general? |
| 9B.5 | M | **Mean-reversion benchmark with a large sample, no model needed (T06l, F29).** Define *spike days* in the treated series: the mean of the previous seven days within 15% of the real event's and a rising trend of similar size, with no stage change within **3 days** (relaxed from 7 because the frozen rule leaves two dates; say so). For each spike day compute the **raw** change (as built: the comparison sets are **event-specific**, days whose pre-level is within 30% of that event's and whose trend points the same way, because the strict set around the primary event has only one date; the strict and broad sets of the primary event are also reported): mean PM2.5 over days 1 to 3 after the buffer against the mean over the 3 days before the buffer. Show the distribution of these raw changes, mark the real events (and the same dates in the control cities), and write the share of spike days below each real event and n. This answers Q4 without a counterfactual model |
| 9B.6 | S | **How much fall does mean reversion alone predict? (T06m).** On all winter days, regress the log change in PM2.5 over the next three days on the current deviation from the 60-day mean and the recent trend (treated and control series separately, days without a stage change nearby). Predict the expected fall for each real event's pre-level and trend, and report the **excess fall beyond mean reversion** (actual minus expected) with a block-bootstrap interval |
| 9B.7 | S | **Control-city placebo over all dates (T06m2).** Run the chosen counterfactual method on the *control* series at all spike-like dates (no GRAP applies there) to get a null distribution of the method's "effects" from many more dates than the frozen placebo. Show where the real events lie in it |
| 9B.8 | S | **Power with matched noise, and how much data would be enough (T06n, F30).** Redo the power curve using the empirical null (as built: the raw changes after all rising days and the control-city placebo effects at all rising control dates, which gives more dates than the spike sets of 9B.5 and 9B.7) instead of the bootstrap null: probability of detecting a true fall of 10, 20, 30 and 40% with 1, 2, 4 and 8 events. Report the minimum detectable fall for each number of events and the **number of events (winters) needed for 80% power at a 15% fall**. This feeds the recommendations of Phase 11 (what data would make H2 testable) |
| 9B.9 | M | **Markdown: answers to Q3 and Q4 in plain words.** Frozen-run answer from Phase 9, what the alternatives, the difference-in-differences and the mean-reversion benchmark add, and what they do not show. Never write "GRAP reduced PM2.5 by X%". State that the frozen criteria and status are unchanged, list the cells added in `T07d2`, and say how this feeds Phase 10 (supporting block of T7, the KPI "3-day response after a stage change") and Phase 11 |

### Phase 10: Synthesis: robustness overview, hypothesis status, monitoring (M, 10.4 is S)

*Order of the work after Phase 9:* **8B, 9B, then 10, 11, 12.** Phase 10 uses the saved tables of 8B and 9B for its supporting block.

| Cell | Type | Content |
| --- | --- | --- |
| 10.1 | code + figure | **Robustness overview (figure F15b):** for H1 and for H2, number of checks with the same sign; **stacked or grouped bars with counts written on them**. No new models |
| 10.2 | code | **Hypothesis status table (T7):** apply the Phase 1 decision rules to the saved tables; one row per criterion: rule, observed value, met or not, table it comes from. The status text is generated from the table. **Add a second block, "supporting evidence from Phases 8B and 9B (exploratory, not part of the decision)"**, with one line per extension result (dose-response, season ladder, timing, variance share, blocked cross-validation, alternative counterfactuals, difference-in-differences, mean-reversion benchmark, power) saying whether it supports or weakens each frozen criterion. The extension block never changes the status |
| 10.3 | markdown | Plain-language status for H1 and H2 (supported, not supported, inconclusive) and the reasons. For each of the four key questions Q1 to Q4 of section 1.1, one short paragraph: the answer, how sure we are, the main caveat |
| 10.4 | code + figure | **Monitoring and drift (F16, T9):** write thresholds first (for example PSI at least 0.25 or KS at least 0.20 flags an input-month; model error above 1.5 times a reference RMSE flags a month). **As built:** the unit is the day (about 30 days per month), the reference is the same calendar month and its two neighbours in the training period, the KS flag level is the larger of 0.20 and the 5% critical value shared over the nine inputs, and the PSI (0.25) is shown for information with its no-drift level, because a fixed PSI or KS threshold flags every month at this sample size (documented in the notebook; the 1.5 times RMSE rule is unchanged). Compare input distributions between training and test periods; monthly RMSE of the prediction model. **Month on the x-axis, units on the y-axis, thresholds drawn and labelled, values written on the bars** |
| 10.5 | code | **Complete the KPI table `T00_kpis`** (Phase 1 promised two model-based KPIs): the **3-day response of PM2.5 after a stage change** (from the H2 results, with its interval and the event count) and the **share of variation explained by fire beyond weather** (from 8B.6). Print the table again with these rows |
| 10.6 | code | **Final list of runs tried:** finish `T07d2` (every extension of Phases 8B and 9B) next to `T07d`, and print the totals so the report can say how many specifications were tried and how many agree |

### Phase 11: Recommendations and roadmap (M)

| Cell | Type | Content |
| --- | --- | --- |
| 11.1 | markdown | **T8 recommendations (three to five):** each tied to one finding. Columns: finding it rests on and its status, what we are not claiming, action, responsible stakeholder (CAQM, state board, city health department), timeline (before winter 2026-27, within a year), indicator and target, data needed |
| 11.2 | markdown | **Rule (and use of the deeper phases):** use the power result of 9B.8 (events or winters needed for 80% power) to state precisely what data would make H2 testable. No policy recommendation where the evidence is inconclusive; use "collect this data" or "run this trial" instead (keep stations reporting through outages, log the exact time of each GRAP order, extend over several winters, staggered or paired-city design) |
| 11.3 | code + figure | **Roadmap timeline** (one chart or table): actions on a time axis with the responsible stakeholder (CAQM, state board, city health department) and indicator labelled |
| 11.4 | markdown | **Limitations and assumptions:** one season, reverse causation, outage overlap, control cities, ERA5 resolution, unit labels, deviations from the proposal (window and hourly data, time-blocked validation, lag range) |

### Phase 12: Deployment, final checks and reconciliation (12.1 and 12.3 are M, 12.2 is S)

| Cell | Type | Content |
| --- | --- | --- |
| 12.1 | code | **Output inventory:** list every saved figure and table with its file name; fail if a figure is missing its caption |
| 12.2 | markdown | Where the dashboard and reproduction steps are (`docs/Dashboard.md`, `python run_all.py --from-final`) |
| 12.3 | markdown | **Final checklist** (section 5) ticked in the notebook |
| 12.4 | code (optional) | **Reconciliation with the earlier pass**, only if wanted: the earlier scripts gave H1 about +11.8% per +10 detections (CI -3.0 to +28.9) and H2 inconclusive. Show a table of notebook value, earlier value, same or different, reason. Differences are not errors. The outage counts and the validation result **must** match because they come straight from the data. Do not tune the notebook to match |

---

## 5. Final checklist (tick every item before saying the notebook is done)

- [ ] "Restart and run all" passes top to bottom on the laptop (kernel restarted); the runtime is printed
- [ ] Every figure has title, axis labels with units, legend, n, uncertainty definition, and **values written on bars, cells, points or lines**
- [ ] Every table and figure is followed by a markdown explanation: what it shows, what we learn, what it does not show
- [ ] No code cell longer than about 25 lines; each has a header comment and comments on non-obvious lines; no cell mixes loading, calculation and plotting
- [ ] No typed numbers: every number in the text comes from a variable or a saved table
- [ ] Treated `#D55E00`, control `#0072B2` everywhere; outage hours are grey gaps, never interpolated
- [ ] Decision rules were written before the models and are unchanged; the number of specifications tried is stated
- [ ] Wording search finds no "caused", "reduced by" or "proved" without a qualifier
- [ ] Time is IST in every axis; units match the dictionary
- [ ] Every figure and table is saved in `outputs/` with its ID; the inventory cell passes
- [ ] The honest limitations (one season, reverse causation, outage overlap, control cities) appear in the interpretation cells, not only at the end
- [ ] Every analysis of Phases 8B and 9B is labelled "ADDED AFTER SEEING RESULTS", is listed in `T07d2`, and none changes the frozen status; alternative counterfactuals were chosen on hold-out accuracy only
- [ ] Each of the four key questions Q1 to Q4 of section 1.1 has a plain-words answer in the notebook with its number, its caveat and the figure or table it rests on
- [ ] The proposal's four research questions are mapped to the notebook's results in one table, and every method of the summary that was not run is listed with the reason (see the alignment note)

---

## 6. Order and what to cut

Do the phases in numeric order. **EDA (Phases 3 to 6) comes before any model**, and the frozen plans (Phase 7) are written before any model is fitted, because the EDA decides the specifications (is a log scale needed, how big a "+n fires" is, how often each stage occurs, where the outage sits).

If time runs out, cut in this order: the boosted-model comparison (8B.9), the pooled event-time profile (9B.4), the better baselines (8B.8), the control-city placebo over all dates (9B.7), the heterogeneity cells (8B.2), the timing cell (8B.4), power simulation (9.11), monitoring chart (10.4), full robustness grids (reduce to 5 or 6 checks each), diagnostics figure (8.6), F2, F5, F4, F7b, F7c, reconciliation (12.4). **Never cut:** data quality (Phase 3), the frozen plans, the primary H1 and H2 results, the status table, the explanation cells, and the four cells that answer the key questions directly: **8B.6** (how much fires add beyond weather), **9B.1** (why the counterfactual failed), **9B.5** (the mean-reversion benchmark) and the answer cells **8B.10** and **9B.9**.

**Build order and time.** 8B and 9B come between Phases 9 and 10. The report and slides are due 16 to 22 Nov, so build the M cells first (8B.6, 9B.1, 9B.5, 8B.10, 9B.9), then 8B.1, 8B.3, 9B.2 and 9B.3, and the remaining S and C cells only if time allows.

## 7. Output behaviour for the assistant

- Write the notebook with `nbformat` or the notebook edit tool; keep the existing Part 0 cells where they meet the rules.
- After each phase: list the new cell numbers, run them if data is available, report any failure, and state what each output shows.
- If a column named here is missing from the data, stop and say so; do not invent one.
- If a result is surprising or contradicts the plan, say so in the explanation cell instead of adjusting the method.
- When a step needs a file that is not in the repo (the parquet is git-ignored, `era5_station_hourly.csv` for the offset check), say what is missing and skip that cell with a clear markdown note.

---

## Build status (updated after Phase 12)

All twelve phases are built in `notebooks/air_quality_policy_impact.ipynb`. The final checklist of section 5 is evaluated by code in cell 12.4 and saved as `outputs/tables/T12d_final_checklist.csv`: the items that code can confirm pass; **two are not ticked because a person must do them**: "Restart and run all passes on the laptop (kernel restarted)", and "no typed numbers" (the fixed explanation texts should be read once). `run_all.py --from-final` exists in the repository root. Not built: the dashboard itself (`docs/Dashboard.md` is a plan). `docs/methods_check.md` is written but the course handout itself was not available, so whether the extension methods are on its topic list is still to be confirmed. Differences from this plan are noted in the notebook where they occur (12.3 maps the proposal's research questions and lists methods not run).
