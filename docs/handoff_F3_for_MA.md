# Hand-off to MA: event list and stage shading for F3

From RB, 14 Nov 2026. Everything is in the repo on branch `reia/h2-work` and is reproduced by `python src/analysis/10_grap_events.py` (reads `data/processed/final_dataset.parquet`, `grap_hourly.csv`, `grap_orders.csv`).

## Files
| What | File |
| --- | --- |
| The 30 stage changes with order date, time source and episode | `outputs/tables/grap_changes.csv` |
| The 28 episodes (merged changes), exclusion reasons, `usable_primary` / `usable_relaxed`, and the long-outage flags | `outputs/tables/grap_events.csv` |
| Every network-wide outage run (170 runs, 928 hours) with the 24-hour long flag | `outputs/tables/outage_runs.csv` |
| F3 itself (PNG and SVG) and the code that draws the stage strip (`figure_f3`) | `outputs/figures/F03_pm25_grap_timeline.*`, `src/analysis/10_grap_events.py` |
| Column meanings | `docs/h2_outputs_dictionary.md` |

## The corrected outage window
The long January 2026 outage is **10 Jan 17:00 to 20 Jan 18:00 IST (242 hours)** (the data shows 0% of stations reporting for the whole run); notes that said "11 to 20 Jan" were wrong. Long runs (24 hours or more): 9 to 11 Apr 2025 (61 h), 10 to 20 Jan 2026 (242 h), 16 to 17 Feb 2026 (27 h), 23 to 25 Jun 2026 (53 h), 27 to 28 Aug 2026 (32 h). In `grap_events.csv`, `overlaps_long_outage` is true for an episode when one of these runs lies within 14 days before to 7 days after it; `long_outage_in_window` gives the dates. 94 of the 971 Stage III/IV hours fall inside the January run, and 112 inside any outage.

## How F3 marks things
- Treated (vermillion) and control (blue) lines are daily means of station means (day valid with 18 of 24 hours; group-day valid when at least half of the group's stations are valid); the band is the 95% interval across stations that day.
- Grey bands mark days with 12 or more outage hours. The stage strip is the NCR stage at 12:00 IST (control cities have no GRAP stage). Dashed lines mark the two primary events.
- If you want the long runs only, or the 24-hour flag instead of the 12-hour-a-day rule, change `out = treated["outage_hours"] >= 12` in `figure_f3`, or read `outage_runs.csv` and shade `start` to `end` of the rows with `long = True`.
