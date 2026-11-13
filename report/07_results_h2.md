# 7. Results: H2 (GRAP escalations)  [BADIR: Insights]

**Status: draft by RB, 14 Nov 2026. Provisional status: INCONCLUSIVE (MK agrees on 13 Nov; MA writes the formal label at gate G4). Figures F3, F12 to F15, F17; tables T06a to T06g.**

## 7.1 Headline
**H2 is inconclusive.** Of the 30 stage changes, only two escalations (11 Nov 2025 and 13 Dec 2025) pass the rules for a primary event, and only one of them has a usable counterfactual. No event shows PM2.5 below the weather-and-fire prediction. This is not evidence that GRAP has no effect: **the method could detect a 30% fall only about 18% of the time, and needs a fall of about 65% for 80% power** (section 7.5). A positive value in any table below is not evidence that GRAP raises PM2.5: stages are raised on a forecast of worsening air, which the model cannot see.

## 7.2 Events (T06a, F12, F13)
Effect on days 1 to 3 after the escalation: actual PM2.5 against the weather-and-fire prediction (95% interval in brackets).

| Event | Fit days | Cross-validated R² | Days 1 to 3 | Days 4 to 7 | Placebo dates / share at or below the real effect | Segmented cross-check (days 1 to 7) | Control cities, same method |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **11 Nov 2025**, stage 2→3 (primary) | 49 | 0.56 | **+23% [-48, +190]**; actual 268 vs predicted 237 µg/m³ (2 valid days) | +6% [-60, +181] | 23 / 0.52 | -2% [-34, +46] | -3.5% [-42, +61] |
| **13 Dec 2025**, stage 2→4 (primary, **weak counterfactual**) | 41 | 0.02 | +30% [-22, +118]; actual 277 vs predicted 212 µg/m³ | +17% [-29, +91] | 13 / 0.23 | +28% [+13, +44] | +0.4% [-44, +81] |
| 19 Oct 2025, stage 1→2 (relaxed set; **day before Diwali**) | 56 | 0.50 | +269% [+137, +473] | +94% [+11, +238] | 8 / 1.00 | +50% [+14, +98] | +91% [+49, +144] |

- **11 Nov 2025** is the only primary event with an adequate counterfactual. Its interval spans a fall of 48% to a rise of 190%, so it neither shows a fall nor rules one out. Raising the stage from 2 to 3 happened in a long high-pollution spell: 23 placebo dates with no escalation also have a median effect of +18%, and about half of them are at or below the real effect.
- **13 Dec 2025** has no usable counterfactual: the weather model does not predict that period (cross-validated R² 0.02) and its 60-day fit window contains four earlier stage changes (14 Oct, 19 Oct, 11 Nov and 26 Nov). The segmented cross-check gives +28% with an interval above zero, which is consistent with the PM2.5 spike of 13 to 14 Dec (about 375 µg/m³) that accompanied the escalation, not with an effect of GRAP.
- **19 Oct 2025** is the day before Diwali (20 Oct); the rise is the festival. The control cities show a similar rise (+91%). It is in the relaxed set only and is not evidence either way.
- **No pooled estimate** can be reported: fewer than two primary events pass the cross-validated R² rule (F13).
- The two January 2026 escalations (16 and 17 Jan) cannot be analysed: both fall entirely inside the network-wide outage of 10 Jan 17:00 to 20 Jan 18:00 IST (242 hours, no PM2.5 at any station).

## 7.3 Robustness (T06e, T06f, F15)
- **11 Nov 2025:** 15 of 16 checks give an estimate (dropping the flagged fit days leaves only 17 valid fit days). The estimates run from -4% to +29% (median +23%); **every interval includes 0**. The estimate is negative in 1 of 15 checks (the 24-hour buffer: -4%, interval -59% to +127%).
- **13 Dec 2025:** 15 of 16 checks have a weak counterfactual; estimates +14% to +66%, every interval includes 0.
- Dropping Delhi (6 stations left), Ghaziabad, Noida or Gurugram, using only the 11 stations with 90% or better PM2.5 coverage, changing the valid-day threshold, the fit length or removing the fire term keeps the 11 Nov estimate between +19% and +29% (all intervals include 0).
- Not run: the weather offset of plus and minus one hour (needs RS). Not applicable: stage I against stage III/IV, dropping events that overlap the January 2026 outage (none do), dropping the largest event (one event remains).

By the decision rule in section 5.6: not **supported** (no pooled fall; negative sign in 1 of 15 checks against the 75% required) and not **not supported** (the interval of the adequate event does not rule out a fall of 10% or more). **Inconclusive.**

## 7.4 Mean reversion (T06c, F14)
High-pollution dates with no escalation also have PM2.5 above the model's prediction in the following days (median +18% for the 11 Nov comparison set, +90% for the 13 Dec set). The real events do not stand out from these dates (share at or below the real effect: 0.52 and 0.23), so the data show no sign of a fall that is specific to an escalation.

## 7.5 What the method can detect (T06g, F17)
Simulating a known fall on real weather and fire series with the observed noise: the 95% interval contains the true effect 90 to 94% of the time and the estimates are unbiased, but the intervals are wide. A true fall of 10% is detected in 5% of simulated events, 20% in 11%, **30% in 18%**, 40% in 33%, **50% in 46%**, 60% in 70% and 70% in 89%. Eighty percent power needs a fall of about 65%. Anything smaller than about a 50% fall would usually be missed; whether the effect of GRAP is that large is not something these data can show. An inconclusive result from two events was therefore a likely outcome, and it does not show that GRAP is ineffective.

## 7.6 Wording to reuse (slides and report)
> H2 is inconclusive. Two GRAP escalations can be analysed, and neither shows PM2.5 below the weather-and-fire prediction. The method detects a 30% fall only 18% of the time, so this does not show that GRAP does not work. A positive number is not evidence that GRAP raises PM2.5: stages are raised on a forecast of worsening air.
