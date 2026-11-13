# 10. Recommendations and implementation roadmap  [BADIR: Recommendations]

**Status: draft by RB (task B4), 14 Nov 2026. Depends on the formal status labels MA writes at gate G4; both hypotheses are provisionally INCONCLUSIVE.**

## 10.1 What the evidence allows
| Finding | Provisional status | What it allows |
| --- | --- | --- |
| H2: PM2.5 after GRAP escalations vs the weather-and-fire prediction | Inconclusive (2 analysable events; method detects a 30% fall 18% of the time; 80% power needs about 65%) | Only "collect this data" and "run this trial" recommendations |
| H1: upwind fires and PM2.5 (MK): +11.8% per +10 upwind detections, interval -3.0 to +28.9, n = 4,757 station-days, winter 2025-26; the all-days estimate is -0.7% (-2.6 to +1.1); fire adds 0.6 points of R² after weather | Inconclusive (provisional) | Same |
| Data: 928 PM2.5 outage hours in 170 runs; the 242-hour outage of 10 to 20 Jan 2026 covers 94 of the 971 Stage III/IV hours (112 are inside some outage); 27 of 30 stage-change times unknown; one order missing; no 2023 and 2024 archive | Established (counted from the data) | Recommendations on data and records, which are findings and not hypotheses |

**Rule for this section:** a recommendation may not rest on an inconclusive hypothesis except as a request for data or a trial. We make no recommendation to start, stop, relax or tighten any GRAP stage or any enforcement action, and none about Punjab or Haryana (we have no stations there; fires there enter only as upwind inputs).

## 10.2 Recommendations
Each one names its finding, the confidence, what we are **not** claiming, the action, the responsible stakeholder, the timeline, the indicator and the data needed.

### R1. Keep monitors reporting through escalations (collect data)
- **Finding:** network-wide PM2.5 outages total 928 hours in 170 runs; five runs last 24 hours or more. The longest (10 Jan 17:00 to 20 Jan 18:00 IST 2026, 242 hours) covers both January 2026 escalations (16 and 17 Jan) and 94 of the 971 Stage III/IV hours. Those escalations cannot be analysed. **Confidence: high** (counted from the data).
- **Not claiming:** that the outage was avoidable or whose responsibility it was.
- **Action:** a second data path (backup upload or direct feed) for the continuous monitors, and an alert when fewer than half of the stations report for 3 hours.
- **Responsible:** CPCB and the state or UT pollution control boards that own the monitors (DPCC, UPPCB, BSPCB, HSPCB); CAQM to ask for it.
- **Timeline:** alerting before January 2027 if feasible; backup path before winter 2027-28.
- **Indicator:** share of hours with at least half of the stations reporting, during Stage III and IV, at least 99%; no outage run of 24 hours or more during an active stage.
- **Data needed:** the outage log of the data pipeline (cause and duration).

### R2. Record the exact time of every GRAP order and publish an order log (collect data)
- **Finding:** 27 of the 30 stage changes in 2025 to 2026 have no time of day in the order ("with immediate effect"); the time is taken from the press release or assumed. One stage-I revocation (24 Feb to 7 Mar 2025) was not found; the original stage III order of 11 Nov 2025 is only on the CAQM site as its clarification. **Confidence: high.**
- **Not claiming:** that any order was wrongly issued.
- **Action:** state the time of effect in each order and publish a single table (date, time, stage, action, link) for all orders.
- **Responsible:** CAQM (Sub-Committee on GRAP).
- **Timeline:** from the next order.
- **Indicator:** 100% of orders carry a time of effect to the minute and a permanent link; the order log is downloadable as a table.
- **Data needed:** none beyond the orders.

### R3. Record the forecast behind each invocation (collect data)
- **Finding:** stages are raised on a forecast of worsening air. A fall after an escalation therefore cannot be separated from what the forecast already implied, and our counterfactual cannot see the forecast. **Confidence: high** that this limits any evaluation; it is the main threat to H2.
- **Not claiming:** that the forecasts were wrong.
- **Action:** record, for each invocation and revocation, the forecast value, its issue time and its source, and publish it with the order.
- **Responsible:** CAQM with the forecast providers (IITM, IMD).
- **Timeline:** from the next order.
- **Indicator:** forecast value available for 100% of invocations; at least 3 winters recorded.
- **Data needed:** the forecast archive at the time of each order.

### R4. Run an evaluation trial of one measure (run this trial)
- **Finding:** two analysable escalations and low power (30% fall detected 18% of the time). A before-and-after comparison cannot settle whether GRAP measures work. **Confidence: high** that more of the same data will not settle it.
- **Not claiming:** that any measure should be withheld during a severe episode. The trial is for a Stage I or II measure, where a delay of its start is low-risk.
- **Action:** a pre-registered design for one measure in one winter: stagger its start across NCR districts or days (or compare paired districts), define the outcome (daily PM2.5 per station), the comparison and the analysis in advance, and size it so that a 20% fall can be detected with 80% power (our simulation shows the present design cannot).
- **Responsible:** CAQM with the NCR state governments; an academic partner for the design and analysis.
- **Timeline:** design and approval before winter 2027-28; run for at least one winter; first results the following spring.
- **Indicator:** a published analysis plan before the start; at least 80% power for a 20% fall (confirmed by simulation as in `src/analysis/13_h2_power.py`).
- **Data needed:** station data inside and outside the trial districts (R1, R5).

### R5. Build a longer, denser record (collect data)
- **Finding:** the usable window is 19 Feb 2025 to 30 Sep 2026 with a single burning season: the OpenAQ archive has nothing for 2023 and 2024. Fire detections are an incomplete measure (cloud, pass timing), the weather is a 0.25-degree reanalysis cell, and there are no stations in the source states. **Confidence: high.**
- **Not claiming:** anything about the fire contribution beyond the provisional H1 result.
- **Action:** archive the continuous-monitor data continuously (including 2023 and 2024 if it exists at CPCB); keep the final FIRMS product (the July to September 2026 rows are preliminary); add monitors or data in the source districts and comparable control cities; pair satellite detections with district-level burnt-area records and, if possible, a trajectory model.
- **Responsible:** CPCB and the state boards (archive and stations); state remote sensing centres and CAQM (burnt-area records).
- **Timeline:** archive from now; burnt-area pairing for winter 2027-28.
- **Indicator:** at least 3 winters of hourly data from at least 40 stations with 85% coverage or better (the present data has 87% coverage over one winter); a daily district burnt-area series.
- **Data needed:** as listed.

## 10.3 Roadmap (Stage 3 slide 4)
| Priority | Action | Rests on | Responsible | When | Indicator and target |
| --- | --- | --- | --- | --- | --- |
| 1 | R2 order log with time of effect | 27 of 30 times unknown | CAQM | from the next order | 100% of orders timed and linked |
| 1 | R3 forecast recorded with each invocation | forecast-driven timing (main threat) | CAQM, IITM, IMD | from the next order | 100% of invocations with a forecast value |
| 2 | R1 backup data path and outage alert | 928 outage hours; 242-hour January gap | CPCB, state boards | alert by Jan 2027; backup by winter 2027-28 | at least 99% of stage hours with at least half of the stations reporting |
| 3 | R5 longer and denser record | one winter; no 2023 and 2024 data | CPCB, state boards, remote sensing centres | archive now; pairing by winter 2027-28 | at least 3 winters, at least 40 stations, at least 85% coverage |
| 4 | R4 pre-registered trial of one Stage I or II measure | low power; endogeneity | CAQM, NCR governments, academic partner | design before winter 2027-28 | analysis plan published; at least 80% power for a 20% fall |

## 10.4 Slide text (Stage 3 slides 2 to 4)
- **Slide 2, implications:** the data does not show whether GRAP works (H2 inconclusive) or how much fires add to Delhi's winter PM2.5 (H1 inconclusive). The most useful decisions now are about evidence: time-stamped orders, recorded forecasts, uninterrupted monitoring.
- **Slide 3, impact and limits:** one winter, two analysable escalations, a method that detects a 30% fall 18% of the time; a positive number is not evidence that GRAP raises PM2.5.
- **Slide 4, roadmap:** the table in 10.3.
