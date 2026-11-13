# 5. Methods: H2 (GRAP escalations)  [BADIR: Analysis]

**Status: draft by RB, 14 Nov 2026. Numbers come from `outputs/tables/`; the decisions behind each step are in `docs/work_log/RB_2026-11-10_B1.md`, `_B2.md`, `_B3.md`. B1.4 and B2.3 were confirmed by MK on 13 Nov 2026.**

## 5.1 Question and hypothesis
H2: PM2.5 falls after GRAP activation relative to the trend predicted by weather and fires alone. The test is a weather-and-fire counterfactual (a form of interrupted time series): fit the pre-escalation relationship, predict the days after, and compare the prediction with what happened.

## 5.2 Data
`final_dataset.parquet` (763,344 station-hours; 54 stations; 19 Feb 2025 to 30 Sep 2026, IST). The treated group is the 39 stations in Delhi-NCR; the 15 stations in Patna, Lucknow and Kanpur are the control cities. Each group becomes a **daily series**:
- PM2.5 hours inside a network-wide outage are removed first; a station-day needs at least 18 valid hours; a group-day needs at least half of the group's stations valid, and is the mean of the station-day means.
- Weather is the mean over the group's station-hours (ERA5, nearest 0.25-degree cell); rain is a daily total; relative humidity is computed from temperature and dewpoint.
- Fire is the upwind count within 100 km and 45 degrees of the previous IST day (`n_up_nh_100km_45deg_lag1`), so no detection after the day can explain it.

## 5.3 Events
The 30 stage changes in `grap_hourly.csv` (14 up, 16 down) are matched one to one with the order table. Changes 24 hours apart or less form one **episode** (28 episodes). A **primary event** is an invocation episode that takes the stage to 2 or higher, has no other stage change in the 7 days before or in days 1 to 3 after its last change, and has at least 40 valid days of PM2.5 in the 60 days before and 3 of 3 valid days after. The **relaxed set** allows a gap of 3 days before and 2 of 3 valid days after. The primary set is **11 Nov 2025 (stage 2 to 3) and 13 Dec 2025 (stage 2 to 4)**; the relaxed set adds 19 Oct 2025 (stage 1 to 2). The rule was written before any PM2.5 outcome around an event was seen.

**Rule change after a first run (amendment A1).** The first version of the rule also excluded any event with a network-outage hour between 14 days before and 7 days after. Because the 928 outage hours are spread over 170 short runs, that left no event at all. Outage hours in the window are now reported but are not an exclusion; the valid-day rules deal with missing data. The change was prompted by the table of exclusions and not by any PM2.5 value, and the first-run result (zero events) is kept in the work log.

## 5.4 Counterfactual model
For each event, `log(daily PM2.5) = a + b1 log(boundary layer height) + b2 wind speed + b3 temperature + b4 relative humidity + b5 rain flag + b6 log(1 + upwind fire count) + error`, fitted by least squares on the 60 days before the first change. Days without PM2.5 or a covariate, and the 3 days after any other stage change, are left out. There is no lagged PM2.5 (it would carry post-event values into the prediction) and no stage variable. The model predicts days 1 to 3 (primary window) and days 4 to 7 (secondary) after the last change; the day of the change is never used, because the hour of most orders is unknown (27 of the 30 change times are uncertain).

The **effect** is the mean of log(actual) minus log(predicted) over the window, shown as a percent change and in µg/m³. The **95% interval** is the mean effect plus or minus a t-multiple of the standard deviation of leave-block-out cross-validation errors in the fit window (blocks as long as the window). The cross-validated R² must be at least 0.40; otherwise the counterfactual is flagged **weak** and not pooled. Events are pooled only when at least two pass.

## 5.5 Checks
- **Placebo events (mean reversion).** GRAP is raised after pollution is already high, so PM2.5 tends to fall afterwards anyway. The same method is run on dates with a similar pre-level (0.75 to 1.33 times the event's 7-day mean) and no upward stage change from 3 days before to 8 days after. The share of placebo effects at or below the real effect is reported.
- **Segmented regression** (cross-check): log PM2.5 on the same controls, a time trend and an indicator for days 1 to 7 after the last change, on days -30 to +7, with Newey-West errors (3 lags).
- **Control cities:** the same method on the Patna, Lucknow and Kanpur series (descriptive).
- **Robustness (16 rows per event):** dropping flagged fit days, a 24-hour buffer, windows of 5, 7 and 14 days, well-covered stations only, leaving out each sub-area, no fire term, valid-day thresholds of 12 and 20 hours, fit windows of 45 and 90 days. The weather offset of plus and minus one hour is **not yet run** (needs weather columns from RS).
- **Power simulation.** The exact method is applied to simulated events with a known fall (real weather and fire series, AR(1) noise with the observed residual standard deviation of 0.39 and lag-1 autocorrelation of 0.57; 300 simulations per point).
- **Tests.** 13 automated tests (`tests/test_h2_analysis.py`), including recovery of a known effect and interval coverage on synthetic data.

## 5.6 Decision rule for the H2 status (set in advance)
**Supported** only if the pooled days 1 to 3 effect is below 0 with a 95% interval that excludes 0, each primary event lies at or below the 10th percentile of its placebo distribution, and the sign is negative in at least 75% of the robustness checks. **Not supported** if the interval excludes 0 on the positive side or rules out a fall of 10% or more. Otherwise **inconclusive**. The formal label is written by MA (gate G4).
