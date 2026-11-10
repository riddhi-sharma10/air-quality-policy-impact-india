# H2 analysis outputs: what each file holds

Made by `src/analysis/` (run order below) from `data/processed/final_dataset.parquet`. All dates are IST calendar dates. PM2.5 is in µg/m³. "Effect" means actual minus the weather-and-fire counterfactual on the log scale, also shown as a percent change (`pct` = 100 x (exp(effect) - 1)). Rules and decisions: `docs/work_log/RB_2026-11-10_B1.md`, `_B2.md`, `_B3.md`.

## Run order (needs `pandas numpy scipy statsmodels matplotlib pyarrow`)

```
python src/analysis/10_grap_events.py     # B1: grap_changes.csv, grap_events.csv, figure F3
python src/analysis/11_h2_its.py          # B2: T06a to T06d, figures F12 to F14
python src/analysis/12_h2_robustness.py   # B3: T06e, T06f, figure F15
python src/analysis/13_h2_power.py        # power simulation: T06g, figure F17 (about 2 minutes)
python -m pytest tests/test_h2_analysis.py -q
```
`common.py` builds the daily series (rules in its header). Random seed `20261110`. Rerunning gives identical tables.

## Tables (`outputs/tables/`)

| File | One row is | Main columns |
| --- | --- | --- |
| `grap_changes.csv` | one of the 30 GRAP stage changes | `ts_ist`, `stage_before`, `stage_after`, `direction`, `time_uncertain` (true when the order time is not known), `time_source` (meeting, pib_posted, assumed), `verification`, `episode_id` |
| `grap_events.csv` | an episode (changes 24 h apart or less merged; 28 episodes) | `date_first`, `date_last`, `stage_before/after`, `pm25_pre7_mean` (treated stations, 7 days before), `valid_days_pre60`, `valid_days_post1_3`, `outage_hours_window` (reported, not an exclusion), `days_since_previous_episode`, `days_to_next_episode`, `usable_primary`, `usable_relaxed`, `exclusion_reason_*`. `pm25_post1_3_mean_RAW_DESCRIPTIVE` is a raw mean, never an effect |
| `T06a_h2_events.csv` | an event in the primary or relaxed set | `n_fit_days`, `cv_r2` (leave-block-out R², needs 0.40), `weak_counterfactual`, then `w1_3_*` (days 1 to 3) and `w4_7_*` (days 4 to 7): `effect_log`, `se_log`, `pct` with `pct_lo`/`pct_hi` (95% interval), `ug_diff` (µg/m³), `n_days`; `placebo_n`, `placebo_share_at_or_below`; `segmented_*` (cross-check) |
| `T06b_h2_pooled.csv` | the pooled estimate | written only when at least 2 primary events pass the counterfactual rule (not the case so far, so the file is absent) |
| `T06c_h2_placebo.csv` | a placebo date (high pollution, no escalation) | `date` of the real event it belongs to, `placebo_effect_pct` |
| `T06d_h2_control_cities.csv` | an event, run on the control cities (Patna, Lucknow, Kanpur) | same columns as T06a |
| `T06e_h2_robustness.csv` | a check x event | `check`, `event_date`, `stage`, `window`, `n_fit_days`, `cv_r2`, `weak_counterfactual`, `pct`, `pct_lo`, `pct_hi`, `ug_diff` |
| `T06f_h2_robustness_summary.csv` | an event | number of checks, share with a negative estimate, min, median and max of `pct` |
| `T06g_h2_power.csv` | a simulated true fall | `true_effect_pct`, `n_sims`, `interval_covers_truth`, `share_interval_below_zero` (power) |

## Figures (`outputs/figures/`, PNG 300 dpi and SVG; registry in `outputs/figure_registry.csv`)

F03 PM2.5 and GRAP timeline; F12 actual versus counterfactual per event; F13 effect per event; F14 placebo distribution; F15 robustness; F17 power. (F16 is reserved for the monitoring figure.)

## How to read the results

- The interval is from leave-block-out cross-validation in the 60-day fit window. It does not include the uncertainty from having only a few events.
- A positive effect is not evidence that GRAP raises PM2.5: stages are raised on a forecast of worsening air, which the model cannot see.
- `weak_counterfactual` events (CV R² below 0.40) are shown but never pooled.
- T06g shows what the method could detect: in simulation, a true fall of 30% is found about 18% of the time and a fall of 50% about 46% of the time. An "inconclusive" result is therefore mostly a statement about power, not evidence of no effect.
