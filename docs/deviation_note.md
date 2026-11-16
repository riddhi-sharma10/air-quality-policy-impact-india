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

## 3. What does not change

The dataset meets the stated minimums (763,344 rows, 70 columns, four independent sources, no Kaggle data), the hypotheses and decision rules were frozen in Phase 7 before the models were fitted, and the statuses are reported as the rules give them (H1 met by the frozen rule but weak, H2 inconclusive).
