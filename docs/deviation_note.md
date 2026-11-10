# Deviations from the Stage 1 proposal: request for approval

Project: *Do Burning and Emission Restrictions Reduce Air Pollution in Northern India? A Multi-Source Analysis of Stubble Fires, Weather and GRAP Interventions* (Group 3: Manya Awasthi 240932, Riddhi Sharma 240604, Mehak Kumar 240536, Reia Baid 240602).
Date: 10 Nov 2026. To: the course instructor. Status: **draft, to be reviewed by the team before sending.**

The research questions and hypotheses are unchanged (RQ1/H1: upwind fires and PM2.5 after weather controls; RQ2/H2: PM2.5 after GRAP activation relative to the weather-and-fire prediction). The Stage 1 summary said "Deviations for instructor approval: none currently". While building the dataset we found four things that differ from the proposal. Each is listed below with the reason and what we ask. We are asking for each one separately.

## Summary table

| # | Proposal said | What we did | Why | We ask you to approve |
| --- | --- | --- | --- | --- |
| 1 | Winter months (Oct to Feb) of 2018 to 2025; about 1,000 winter days; about 50k daily rows | One continuous window, **19 Feb 2025 to 30 Sep 2026**, **hourly** data: 763,344 rows, 70 columns, 54 stations (39 in Delhi-NCR, 15 control stations in Patna, Lucknow and Kanpur) | The OpenAQ archive of CPCB data has nothing for 2023 and 2024 and only fragments of 2022 for our stations, so 2025 to 2026 is the only continuous stretch. Hourly data was available and gives a much larger sample than the proposal's 50k daily rows (the 100,000-row minimum is met) | The window and the hourly resolution |
| 2 | Out-of-sample validation by train/test **by year** | **Time-blocked split**: train on 19 Feb to 31 Dec 2025, test on 1 Jan to 30 Sep 2026 (plus an expanding-window check) | The window holds one burning season and one winter, so a by-year split would leave a test set with no comparable season | The time-blocked split |
| 3 | H1: fire counts in the **previous 1 to 3 days** | The built fire features are `lag1` (previous day) and `lag2` (previous two days); the upwind feature is `lag1`. All use only detections strictly before the date of the reading | We rebuilt the fire features so that no same-day detection can explain an hourly reading. A 3-day lag needs a rebuild from the raw FIRMS file | Either (a) H1 is stated as "previous 1 to 2 days", or (b) we add a 3-day lag. We prefer (a) unless you want (b) |
| 4 | Methods: EDA, correlation and lag analysis, multiple regression with controls, interrupted time series. No control group | The same methods, plus **control cities** (Patna, Lucknow, Kanpur; outside the NCR, so GRAP does not apply) used as a comparison and for placebo events | GRAP is triggered by pollution itself, so a before and after comparison alone cannot separate the policy from what pollution does after a spike. The controls and placebo events are the check | Use of the control cities and placebo events. Please also tell us whether difference-in-differences, boosted models with SHAP, or experiment tracking (MLflow) are within the course handout. **If not, we will not use them** |

## Things that did not change (for completeness)

- **Sources:** CPCB continuous monitors (through the OpenAQ archive; one AirNow station is used only to validate CPCB PM2.5), NASA FIRMS VIIRS fire detections, ERA5 reanalysis for weather (ERA5 rather than IMD), CAQM GRAP orders (and PIB press releases for orders before 2 Apr 2025). No Kaggle data. Provenance is in `docs/provenance_log.csv`.
- **Single dataset (SSOT):** one table, one row per station per IST hour; join keys, units, duplicate handling and missing-value rules are in `docs/final_dataset_dictionary.md`; the build runs 45 checks.

## Limits we will state in the report (so you know what the results can and cannot support)

- **One burning season** (Oct to Nov 2025) and one winter. H1 has low statistical power, so "inconclusive" is a likely and legitimate outcome.
- **GRAP is triggered by pollution**, so a fall after activation is partly regression to the mean. We report H2 event by event, with placebo events, and word results as "consistent with" or "associated with", not as causal effects.
- **Few events**: almost all Stage III and IV hours fall between Nov 2025 and Jan 2026, so H2 rests on a small number of episodes.
- **Order times:** most GRAP orders say "with immediate effect" and give no time of day, so about 7% of hours are flagged uncertain and one order (a Stage-I revocation between 24 Feb and 7 Mar 2025) could not be found. We repeat the analysis without these hours.
- **A monitor outage** on 11 to 20 Jan 2026 (no PM2.5 at any station) overlaps part of the Stage III and IV period. These hours are excluded and the overlap is reported.
- **Control cities** are far from Delhi and differ in weather and fire exposure; they are a comparison, not a perfect counterfactual.
- **Stakeholders:** we have no stations in Punjab or Haryana, so we cannot make state-specific claims for those boards. Fires there enter only as upwind inputs.

## If a request is not approved

| Request | Fallback |
| --- | --- |
| 1 (window) | Not applicable: no other continuous data exists. We would ask what the instructor wants instead |
| 2 (time-blocked split) | A single chronological split with the same train and test dates |
| 3 | We apply whichever option you choose |
| 4 | Regression and interrupted time series only, no control group, no difference-in-differences, no boosted models |

## Please reply with

1. Approved / not approved for each of items 1 to 4.
2. For item 3, option (a) or (b).
3. For item 4, which of difference-in-differences, boosted models with SHAP, and MLflow are in scope.

*Contact: Reia Baid (240602). The team's reply file will be saved as `docs/instructor_reply.md`.*
