# 11. Limitations, assumptions and deviations: H2 part (shared section; H1 and data-quality parts to be added by MK and MA)

**Status: draft by RB, 14 Nov 2026.**

## 11.1 Rule change after a first run (to be stated in full, MK's request of 13 Nov)
**Amendment A1.** The rule for the primary event set was written before any PM2.5 outcome around an event was seen. The first run of it left **zero** events, because it excluded every event with any network-outage hour in the window from 14 days before to 7 days after, and the 928 outage hours are spread over 170 short runs. The condition was changed to a reported flag (the valid-day rules already deal with missing data), which gave two primary events. The change was prompted by the table of exclusions (dates and counts of outage hours), not by any PM2.5 value. It is documented in `docs/work_log/RB_2026-11-10_B1.md` section 5b, together with the first-run result. No other rule was changed after results were seen.

## 11.2 Limits of the H2 evidence
1. **Few events.** Of 30 stage changes, 2 primary events (3 in the relaxed set). One has no usable counterfactual (13 Dec 2025, cross-validated R² 0.02); one is the day before Diwali (19 Oct 2025). Only 11 Nov 2025 is adequate. No pooled estimate is possible and the intervals do not include the uncertainty from having so few events.
2. **Low power.** The method detects a true 30% fall about 18% of the time, a 50% fall about 46% of the time, and needs about a 65% fall for 80% power (F17, simulation). An inconclusive result is not evidence of no effect.
3. **Stages are raised on a forecast.** PM2.5 tends to rise around an escalation and to fall afterwards anyway (regression to the mean); the model cannot see the forecast. A positive effect is not evidence that GRAP raises PM2.5, and a negative one would not prove that it lowers it. Placebo dates (high pollution, no escalation) reduce but do not remove this problem.
4. **One winter.** All stage III and IV hours fall between Nov 2025 and Jan 2026 (971 hours), almost all in one season.
5. **Outages.** 928 outage hours in 170 runs. The 242-hour outage of 10 Jan 17:00 to 20 Jan 18:00 IST 2026 covers both January 2026 escalations and 94 of the 971 Stage III/IV hours; 112 fall inside some outage. These hours are excluded, so treated-period data is missing in a way related to the stage.
6. **Order times.** 27 of the 30 change times are uncertain (press release time or assumed noon). Day 0 of an event is never used, and a 24-hour buffer is one of the robustness checks. One stage-I revocation (24 Feb to 7 Mar 2025) is missing, and the 15 Jun to 13 Oct 2025 stage 0 is inferred from the absence of orders; the original 11 Nov 2025 stage III order exists only as its clarification (it is a primary event).
7. **Control cities** (Patna, Lucknow, Kanpur) differ from Delhi in weather and fire exposure and have their own local action plans. They are a descriptive comparison, not a counterfactual.
8. **The counterfactual model.** A daily weather-and-fire regression that explains about half of the day-to-day variation at best (cross-validated R² 0.5 to 0.56). Coefficients are not interpreted (the fire coefficient is negative in the 11 Nov fit window, where it is collinear with temperature). Cross-validation blocks are consecutive valid days and can span a gap of a day or two. Consecutive placebo dates are not independent.
9. **Weather alignment.** The check with the weather timestamp moved by plus and minus one hour has not been run (needs alternative ERA5 columns from RS). Weather is the nearest 0.25-degree reanalysis cell, not a measurement at the station.
10. **Not analysed:** the 16 revocations and the stage I invocations; the effect of individual measures (the actions of each stage are bundled).
11. **Fire data used as a control** is incomplete (cloud, pass timing) and its July to September 2026 rows are preliminary; no event in the analysis uses them.

## 11.3 Deviations from the Stage 1 proposal (approval requested in `docs/deviation_note.md`; reply pending)
Window 19 Feb 2025 to 30 Sep 2026 and hourly data instead of Oct to Feb 2018 to 2025 daily; time-blocked validation instead of by-year; H1 lag range 1 to 2 days instead of 1 to 3 (MK and MA agree); control cities and placebo events added; difference-in-differences, boosted models, SHAP and MLflow are not used unless the instructor approves.

## 11.4 Data and code corrections made during the work
- The long January 2026 outage runs from **10 Jan 17:00 to 20 Jan 18:00 IST (242 hours)**, not "11 to 20 Jan" as earlier notes said; the share of Stage III/IV hours inside it is 94 of 971 (an earlier note said 99). Corrected in the plan, the deviation note, the work logs and the data dictionaries; the table `outputs/tables/outage_runs.csv` lists every run.
- Two checks in H1 (near-real-time rows, zero-assumed days) are empty by construction in the winter sample; see `docs/work_log/RB_2026-11-14_H1-review.md`.
