# Exploratory analyses that are not in the notebook

Written 16 Nov 2026. Two analyses were run on the final dataset after the frozen H1 and H2 results and were **kept out of the notebook** because they did not reach a supported result. The third extension analysis, **H3 (ventilation), was supported and is in the notebook, Phase 8C.** None of these changes the frozen status of H1 or H2.

Both analyses are exploratory ("added after seeing results"). The rules were written in the header of `src/exploratory_analyses.py` before the models were run. Reproduce: `python run_all.py --from-final` (builds the daily tables), then `python src/exploratory_analyses.py`; tests: `python -m pytest tests/test_exploratory_analyses.py -q`. Outputs are in `outputs/exploratory/` (tables `X1*`, `X2*`, `X_status`, `X_runs`; figures `X1`, `X2`, `X2b`), separate from `outputs/tables` so the notebook's figure inventory is unaffected.

| Analysis | Rule result | Main number | One-line reading |
| --- | --- | --- | --- |
| **X1** fires in April–May | **Inconclusive** (an informative null) | −0.5% per +5 upwind detections [−1.4, +0.4] | No positive fire association inside the season with the most fire variation |
| **X2** traffic and dust tracers after Stage III/IV | **Inconclusive** (CO ratio interval just includes 0) | NO2/PM2.5 −17.1% [−28.8, −3.4]; CO/PM2.5 −9.0% [−17.4, +0.3]; PM10/PM2.5 −9.8% [−17.7, −1.2] | Suggestive for NO2 and dust, not for CO; an association |

## X1: upwind fires and PM2.5 inside the April–May season

**Why.** The frozen H1 sample (Oct 2025 to Feb 2026) mixes the fire season with the smog season. April–May has far more day-to-day fire variation (up to 177 upwind detections against 28 in Oct–Nov) and two seasons are in the window (2025 and 2026).

**Rule (set first).** The frozen H1 model (treated stations, previous-day upwind count within 100 km and 45°, eight weather controls, station and weekday effects, errors clustered by date) on April–May 2025 and 2026. Supported if above 0 with the 95% interval excluding 0 and the same sign in at least 75% of sensitivity runs. As a code check, the same function on the frozen winter sample returns +9.53%, identical to the frozen result.

**Result (3,838 station-days, 109 dates).** −0.5% per +5 detections [−1.4, +0.4], p = 0.29. All 7 sensitivity runs have the same sign: week effects −1.3% [−2.3, −0.3]; 2025 only −2.7% [−4.3, −1.0]; 2026 only −0.1% [−1.2, +1.1]; fire radiative power −1.1% per SD [−4.5, +2.5]; all-direction 200 km count −2.1% per SD [−6.7, +2.6]. The next-day placebo is +0.3% [−0.5, +1.0].

**Out-of-sample (added after the first result).** Train April–May 2025, test April–May 2026 (1,987 station-days): weather controls only, RMSE 26.1 µg/m³; adding upwind fire, RMSE 29.6 µg/m³. Fire makes the prediction worse (table `X1b`).

**Reading.** In the season with the most fire variation there is no positive association; the interval rules out an effect larger than about +0.4% per +5 detections. It points the same way as the seasonal ladder in H1 (+9.5% in winter, +1.7% with date effects): the winter association is mostly seasonal. Reasons it may differ (not tested): a different crop residue and smaller smoke source, better ventilation in spring, and low PM2.5 so that smoke is a small part of it.

**Why it is not in the notebook.** It did not support H1 and would need its own frozen rule in Phase 7 to sit beside it. It can be cited in the report as an exploratory check that agrees with the seasonal ladder.

## X2: traffic and dust tracers on Stage III/IV days

**Why.** Stage III/IV restricts trucks, vehicles and construction. If it works as designed, traffic gases (NO2, CO) and the coarse-dust share (PM10/PM2.5) should fall relative to PM2.5.

**Rule (set first).** Treated stations on days with Stage III or IV in force for at least half the hours, against control cities, with station and date effects, Oct 2025 to Feb 2026; station-days with at least 18 valid hours of each pollutant; outage hours dropped. Supported if NO2/PM2.5 and CO/PM2.5 both fall with the decision interval (the wider of the date-clustered and station-clustered intervals) excluding 0 and the same sign in at least 75% of sensitivity runs. Gas units are mislabelled in the archive, so only relative changes are read.

**Result (6,459 station-days, 1,350 on Stage III/IV days).**

| Outcome | Change on Stage III/IV days | Decision interval |
| --- | --- | --- |
| NO2 / PM2.5 | −17.1% | [−28.8, −3.4] |
| CO / PM2.5 | −9.0% | [−17.4, +0.3] |
| PM10 / PM2.5 (coarse dust share) | −9.8% | [−17.7, −1.2] |
| PM2.5 (reference) | +41.1% | [+25.4, +58.8] |
| NO2 (reference) | +16.9% | [+1.4, +34.7] |
| CO (reference) | +28.8% | [+16.0, +42.9] |

By the pre-set rule the result is inconclusive because the CO ratio interval touches 0. The 4 sensitivity runs (12 and 20 valid hours, dropping the 10 to 20 Jan outage, Delhi stations only) share the sign; using Stage II or higher gives larger falls in all three ratios.

**Why it must not be read as "GRAP cut traffic".** PM2.5 rose far more than the gases on these days (+41% against +17% and +29%), so a falling ratio can come from the smog episode itself. **Stress test (added after the first result):** treated stations only, days when the group's mean PM2.5 was at least 150 µg/m³, comparing Stage III/IV days with equally polluted days: NO2/PM2.5 −17.0% [−25.2, −7.9]; CO/PM2.5 −3.5% [−12.9, +6.9]; PM10/PM2.5 −6.5% [−9.7, −3.1]; NO2 level +2.8% [−6.4, +12.9]; PM2.5 level +23.8% [+13.6, +35.0]. The NO2 and dust-share falls survive; the CO result does not.

**Placebo (added after the first result).** The Stage III/IV timeline was moved by 12 to 60 days (16 shifts, same model). The real effect lies outside the placebo range for NO2/PM2.5 (real −17.1%, placebo −15.0% to +27.9%, 0 of 16 as low or lower) and for PM10/PM2.5 (real −9.8%, placebo −9.2% to +9.3%, 0 of 16), and inside it for CO/PM2.5 (real −9.0%, placebo −20.7% to +25.3%, 4 of 16 as low or lower). Stage periods last weeks, so the shifted timelines overlap the real ones a little and the placebo is not perfectly clean.

**Reading.** Suggestive evidence that the NO2 and coarse-dust shares were relatively lower on Stage III/IV days, consistent with traffic and dust restrictions, but not conclusive: the stages fall in November to January, when heating and biomass burning also raise PM2.5 relative to NO2. It does not establish that GRAP reduced traffic.

**Why it is not in the notebook.** The pre-set rule did not reach "supported" and the design (control cities on different weather) is weaker than the frozen H2 design. It can be quoted in the report as an exploratory mechanism check.

## Specifications tried (to add to the "runs tried" count)

| Analysis | Model fits |
| --- | --- |
| X1: 10 regression runs, 2 out-of-sample fits | 12 |
| X2: 42 regression fits (7 runs by 6 outcomes), 48 placebo-shift fits | 90 |
| Total | 102 |

H3 (notebook, Phase 8C) is counted separately in table `T07d2`.

## What to tell the instructor
Add to the deviation note: three exploratory analyses were run after the frozen results; the supported one (H3, ventilation) is in the notebook, and the two that did not reach a supported result are documented here. None changes the frozen H1 or H2 status; rules were written before running; the stress test, out-of-sample check and placebo were added after the first X1 and X2 results.
