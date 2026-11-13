# 1. Stakeholders, decisions and KPIs  `[BADIR: B]`

**Business question.** Do burning and emission restrictions reduce air pollution in northern India? We ask it for two things the authorities can act on: (H1) are upwind stubble fires on the previous days associated with higher PM2.5 once the weather is accounted for, and (H2) is PM2.5 lower after a GRAP stage is invoked than the weather-and-fire model would predict. Evidence: 54 CPCB stations, hourly, 19 Feb 2025 to 30 Sep 2026 (IST), with one burning season and one winter. Findings are associations, not proven effects.

## 1.1 Who decides what, and what the data can support

| Stakeholder | Decision they make | Hypothesis it links to | Can this data support it? |
| --- | --- | --- | --- |
| **CAQM** (Commission for Air Quality Management in NCR and adjoining areas) and its GRAP Sub-Committee | When to invoke or revoke each GRAP stage; whether the staged measures are worth their cost; how early to act | H2 (after-activation PM2.5 versus the weather-and-fire prediction); H1 (fire counts as an early signal) | **Partly.** Delhi-NCR stations, 30 stage changes, most of Stage III/IV in one winter (971 hours). The design cannot separate the effect from the fact that GRAP is invoked when pollution is already high. |
| **State pollution control boards and DPCC** (Delhi, Uttar Pradesh, Bihar) | Where to enforce, how to keep the monitoring network running | Data quality finding (not H1 or H2) | **Yes, for monitoring.** All stations were empty from 10 Jan 18:00 to 20 Jan 18:00 IST 2026 (241 hours) and a further 687 hours elsewhere; 112 of the 971 Stage III/IV hours fall inside outages. **No, for enforcement targets**: no source data. |
| **City health departments** (Delhi-NCR; Patna, Lucknow, Kanpur as comparison) | When to issue health advisories and open clinics | KPI 2 (days above 60 ug/m3); H1 (fires the day before as an early signal) | **Partly.** We can describe how many days exceed the standard and how that varies with fires the day before; we have no health data. |
| **Punjab and Haryana agriculture departments** (stubble management, farmer support) | How to reduce burning at source | H1 | **Outside the data.** No stations in Punjab or Haryana; fires are counted near our stations, not attributed to a state. We make no state-specific claim. |
| **Control-city boards** (Patna, Lucknow, Kanpur) | Their own local action plans | None | **Comparison only.** They are outside the NCR but have different weather, fire exposure and their own plans, so they are not a clean counterfactual. |

## 1.2 KPIs

Every KPI is computed from `data/processed/final_dataset.parquet` by `src/analysis/01b_kpi_baselines.py` (table `outputs/tables/T00_kpi_baselines.csv`). A valid hour has `pm25` present and `network_outage` False; a valid station-day has at least 18 valid hours; a group-day averages the valid station-days and counts when at least half of the group's stations are valid. Winter sample: 1 Oct 2025 to 28 Feb 2026 (IST). Baselines are descriptions of the period, not effects.

| # | KPI | Definition and columns | Baseline, winter sample | Feeds |
| --- | --- | --- | --- | --- |
| 1 | Daily mean PM2.5 | Mean of valid station-days per group and day. `pm25`, `network_outage`, `group` | Treated 163.4 ug/m3 (129 valid days); control 65.1 ug/m3 (130 days) | Context for H1, H2 |
| 2 | Days above the 24-hour standard | Share of valid group-days above 60 ug/m3 (India NAAQS). `pm25` | Treated 122 of 129 days (94.6%); control 87 of 130 days (66.9%) | Health and GRAP decisions |
| 3 | PM2.5 response in days 1 to 3 after a stage change | Actual minus the weather-and-fire prediction, in ug/m3 and %, per event and pooled. `grap_stage_applied`, `hours_since_stage_change`, `last_change_direction`, `pm25`, weather and fire columns | Not computed yet: the value comes from the H2 analysis (RB, B2) | H2 |
| 4 | PM2.5 change per additional upwind fire detection the day before | Coefficient with 95% CI from the H1 regression. `n_up_nh_100km_45deg_lag1`, `pm25`, weather columns | Not computed yet (MK, K2). Context: in Oct to Nov 2025 treated stations had on average 4.7 upwind detections per station-day (max 28, at least one on 71.7% of station-days) | H1 |
| 5 | Monitoring completeness | Share of station-hours with valid PM2.5; network outage hours. `pm25`, `network_outage` | 86.8% of station-hours valid; 928 of 14,136 hours (6.6%) are network outages; 84.0% of station-days valid | Data quality, monitoring (F16) |

## 1.3 Constraints that limit what we claim

- One burning season, so H1 has low power; "inconclusive" is a valid result.
- GRAP is invoked because pollution is high, so a fall afterwards is not automatically an effect.
- GRAP applies to the whole NCR at once; the control cities are a comparison, not a clean counterfactual.
- Missing data is correlated with treatment (112 of 971 Stage III/IV hours are in outages).
- Wording: "associated with", never "GRAP reduced PM2.5 by X" without the qualifier and the interval.

## 1.4 Slide (Stage 2, slide 1 content)

**Title:** Who acts on air-quality evidence, and what can our data support?
Text (4 lines): CAQM decides GRAP stages (H2) · State boards and health departments use the monitoring and exceedance KPIs (data quality, KPI 2) · Source-state stubble policy is outside the data · All findings are associations from one burning season.

*Sources: final_dataset.parquet; script `src/analysis/01b_kpi_baselines.py`; outage counts from `src/validate_final_dataset.py`. Unchecked: the descriptions of what each agency decides are general knowledge of CAQM and GRAP and need a source citation before the report.*
