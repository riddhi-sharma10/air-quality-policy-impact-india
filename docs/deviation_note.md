# Deviation note for the instructor (task T0.1)

Project: *Do burning and emission restrictions reduce air pollution in Northern India?* (Group 3). This note lists where the final work departs from the Stage 1 one-page summary, and **asks for written approval** of each point. The notebook is `notebooks/air_quality_policy_impact.ipynb`; the numbers below are from its saved tables.

## 1. Deviations from the Stage 1 summary

| # | Stage 1 summary | What was done | Why | Approval asked |
| --- | --- | --- | --- | --- |
| 1 | 2 to 3 years of data from 2019 onward | **19 Feb 2025 to 30 Sep 2026** (about 1.6 years, 14,136 hours per station, **one burning season**) | The OpenAQ archive has no usable data for 2023 and 2024 and only fragments of 2022 (`docs/project_status.md`); this is the only continuous stretch for which station data, the GRAP stage record and the weather and fire series could all be assembled | Yes: the shorter window and the single winter, which limit every result to one season |
| 2 | Hourly station table | Hourly data for the final table and the quality checks; the **analysis is on daily station values** (a station-day needs at least 18 valid hours) | The 60 ug/m3 standard applies to a 24-hour mean, and hours within a day are strongly correlated | Yes |
| 3 | Validation by year | **Time-blocked split**: train to 31 Dec 2025, test from 1 Jan 2026; date-block bootstraps | One year is too short for a by-year split; random splits would leak the season | Yes |
| 4 | Treated stations (NCR) against comparison stations | **Control cities added**: Patna, Lucknow and Kanpur (15 stations) as an outside-the-NCR comparison; they differ in weather, sources and local rules and are used as a comparison, not a twin | A comparison group is needed for the difference-in-differences and placebo checks | Yes |
| 5 | Fire lags of 1 to 3 days | The **upwind** fire variable exists for the previous day only (lag 1); the all-direction counts have lags 1 and 2, and a day-3 count was built for the all-direction 100 km count only (8B.4b) | The upwind feature was built for the previous day only (`src/build_upwind_features.py --wind-days 1`) | Yes |
| 6 | PM2.5 and PM10 | **PM2.5 only**; PM10 is in the final table but was not analysed | Time; PM2.5 is the standard and the hypothesis variable | Yes |
| 7 | Stations in the source states | **No stations in Punjab or Haryana** burning districts: the stations are in Delhi-NCR, Patna, Lucknow and Kanpur | The final station list has no monitors there; the reason is not documented in the notebook | Noted: no state-specific stubble claims are made |

## 2. Methods

* **Used and named in the Stage 1 summary:** difference-in-differences with an event study (9B.3), placebo dates, alternative fire radii, gradient boosting with tuning (8B.9), SHAP, drift monitoring (10.4).
* **Used but not named in the summary** (all regression-based or descriptive): regression with station effects and clustered standard errors, ridge shrinkage, segmented regression, a mean-reversion regression and a spike-day benchmark, permutation importance.
* **Named in the summary and not run:** propensity score matching, regression discontinuity (no numeric trigger in the data), LIME, a fairness check across station types (no station-type field; a geographic equity check by sub-area was done instead, 11.5), Spark, and a model API. A small MLflow logging script (`scripts/log_mlflow.py`) and a Streamlit app (`app/streamlit_app.py`) are provided.
* **The ADS course handout was not available when this note was written**, so whether each method above is on its topic list is not confirmed. **Please confirm which of the methods in this section are inside the course scope**; the extension cells (Phases 8B and 9B) are labelled "ADDED AFTER SEEING RESULTS" and can be removed without changing the frozen results.

## 2a. Analyses added after the frozen results (exploratory)

H1 and H2 are the frozen hypotheses (the proposal's fire and GRAP questions, RQ2 and RQ1 in 12.3). After the frozen results, two further hypotheses were added to the notebook and two analyses were kept out of it. All were chosen after seeing results, none changes the frozen H1 or H2 status, and Phase 10C of the notebook puts H1 to H4 in one table (`T14e`).

| Name | Kind | Where | Result by its own rule | Note |
| --- | --- | --- | --- | --- |
| **H3** ventilation index (boundary-layer height and wind speed) and PM2.5; answers the proposal's H3 directly | extension, post-hoc | notebook, Phase 8C (`T04q`, `T08j`, F34) | SUPPORTED: -19.1% PM2.5 per +1 SD of ventilation [-22.8, -15.3] | falls to -1.9% when temperature is added, so weather terms cannot be separated |
| **H4** (formerly E1): regional PM2.5 level and persistent differences between stations | exploratory hypothesis, post-hoc | notebook, Phase 10B (`T14a` to `T14e`, F35 to F38) | SUPPORTED (post-hoc rule): H4a median 83% of day-to-day variance shared with other stations; H4b early-late correlation of station excesses 0.80 [0.65, 0.88] | the rule was written after a first look at the data; 42% of the spread between stations lies between network owners, so differences may be instrument calibration rather than local pollution; says nothing about traffic, industrial or residential stations; to be confirmed on the next winter |
| **X1** fires in April and May | exploratory, outside the notebook | `docs/exploratory_analyses_not_in_notebook.md` | inconclusive (an informative null) | kept out of the notebook |
| **X2** traffic and dust tracers on Stage III and IV days | exploratory, outside the notebook | `docs/exploratory_analyses_not_in_notebook.md` | inconclusive | kept out of the notebook |

**Change to the proposal's hypotheses (approval asked).** The proposal's H4 (do effects differ between traffic, industrial and residential stations?) was dropped because the stations table has no station-type field. It is replaced by H4 (formerly E1): regional level and persistent station differences, exploratory, post-hoc, rule written after a first look at the data. Please confirm.

## 3. What does not change

The dataset meets the stated minimums (763,344 rows, 70 columns, four independent sources, no Kaggle data), the hypotheses and decision rules were frozen in Phase 7 before the models were fitted, and the statuses are reported as the rules give them (H1 met by the frozen rule but weak, H2 inconclusive).
