# Methods and requirements check (task T0.2)

Written 16 Nov 2026 after reading two documents: the **ADS End-Term Project Guidelines** (4 pages) and the group's **one-page summary** (`ADS Project One-Page Summary`). What could and could not be checked is stated for each point.

## 1. What could not be checked

The guidelines say to apply the methods **prescribed in the ADS course handout** and **not to go beyond the prescribed course scope**. **The course handout itself was not available**, so it is not known whether each method below is on its topic list. The one-page summary states that "all methods come from the ADS handout topic list" and names them; that statement is the only evidence available. **Action: confirm the list in section 2 against the handout, or ask the instructor, before submission.**

## 2. Methods used in the notebook against the proposal

| Method | Named in the one-page summary? | Where in the notebook | Handout status |
| --- | --- | --- | --- |
| Descriptive statistics, EDA, KPIs | yes (EDA, KPIs) | Phases 1, 3 to 6 | not confirmed |
| Regression with station and weekday effects, clustered standard errors | not by name (the summary names causal tests and models) | 8.3 to 8.5 | not confirmed |
| Time-blocked train and test split, RMSE against baselines | not by name | 8.6 | not confirmed |
| Block bootstrap, placebo dates, robustness runs | placebo dates and alternative radii: yes | 8.7, 9.7, 9.10 | not confirmed |
| Difference-in-differences with an event study | yes | 9B.3 (extension) | not confirmed |
| Gradient boosting with tuning | yes (calibration not done) | 8B.9 (optional extension) | not confirmed |
| SHAP | yes | 8B.9 | not confirmed |
| Permutation importance | not named | 8B.9 | not confirmed (an alternative to SHAP) |
| Ridge shrinkage, segmented regression, spike-day and mean-reversion benchmarks | not named | 9.9, 9B.2, 9B.5, 9B.6 | not confirmed; all are regression-based |
| Drift monitoring (PSI, KS) | yes ("drift monitoring") | 10.4 | not confirmed |

**Methods named in the summary that were not run:** propensity score matching, regression discontinuity, LIME, a fairness check across station types, MLflow tracking and a model API, Spark. Reasons are in `T12c_methods_status` (notebook cell 12.3b). If the instructor requires any of them, they would still have to be added; if the handout does not list the extension methods above, the extension cells (Phases 8B and 9B, marked "ADDED AFTER SEEING RESULTS") can be removed without changing the frozen results.

## 3. Requirements of the guidelines against the project

| Requirement | Status | Evidence |
| --- | --- | --- |
| Final dataset at least 100,000 rows | met: 763,344 rows | `docs/validation_run_output.txt` |
| At least 20 variables (40 or more preferred) | met: 70 columns | same file, `docs/final_dataset_dictionary.md` |
| No Kaggle | met: no Kaggle source in the provenance log | `docs/provenance_log.csv` |
| Multiple credible sources | met: OpenAQ/CPCB, NASA FIRMS, ERA5 (ECMWF), CAQM and PIB orders | `docs/provenance_log.csv` |
| Provenance (links, dates, coverage) | met | `docs/provenance_log.csv` |
| One consistent dataset (SSOT) with join keys, units, duplicates, missing values, quality checks | met | `docs/final_dataset_dictionary.md`, notebook Phases 2 and 3, tables T01b and T02 |
| BADIR structure | met | notebook phase headings |
| Association distinguished from causation | met | wording rules and the final checklist (12.4) |
| Unsupported or inconclusive outcomes treated as valid | met | H2 is inconclusive (10.2) |
| Deviations documented, instructor approval for deviations from mandatory requirements | **open** | see section 4 |

## 4. Deviations that may need the instructor's approval

* **Time window.** The proposal planned 2 to 3 years from 2019 onward. The final table runs from 19 Feb 2025 to 30 Sep 2026 (about 1.6 years, 14,136 hours per station, 54 stations), because that is the span for which station data, the GRAP stage record and the weather and fire series could all be assembled. The row and variable minimums are met. Whether the shorter span needs approval is for the instructor to say.
* **Methods outside the handout list**, if any (section 2).
* **Methods promised and not run** (section 2).

## 5. Final submission requirements against the repository

| Requirement of the guidelines | Where |
| --- | --- |
| 1. Problem, research questions, hypotheses | notebook Phase 1 |
| 2. Sources, provenance, integration | notebook Phase 2, `docs/provenance_log.csv`, `docs/final_dataset_dictionary.md` |
| 3. Final dataset or a reproducible procedure | the table is **not in the repository** (git-ignored, about 197 MB as parquet); the procedure is in `README.md` and `src/` (raw downloads need provider access keys) |
| 4. Data-quality checks and EDA | notebook Phases 3, 5, 6; `docs/validation_run_output.txt` |
| 5. Methods and hypothesis assessments | notebook Phases 7 to 10 |
| 6. Evidence, findings, limitations | notebook Phases 8B, 9B, 10, 11.4 |
| 7. Recommendations and roadmap | notebook Phase 11 |
| 8. Reproducible code and documentation | `run_all.py`, the notebook, `src/`, `tests/`, `README.md` |
