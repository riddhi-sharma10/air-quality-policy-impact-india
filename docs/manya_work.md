# Manya Awasthi (MA): work done and work left

Role: problem definition, data quality, MLOps. Reviewer: RS. Backup: RS.
Branch: `manya_work`. Last updated 15 Nov 2026.

**Reset on 15 Nov 2026.** The pollution EDA was never done, and everything produced after the final dataset was built without it. So all analysis after the final dataset is redone from scratch in the notebook, in the order EDA, then hypotheses (`docs/Final_Notebook_Plan.md`). The results, tables, figures, scripts and tests I produced after the dataset were removed from this branch (they remain in the git history and on the other branches if anyone needs to look). The dashboard plan is in `docs/Dashboard.md`.

## 1. What stays from my earlier work

| Item | Why it stays |
| --- | --- |
| `src/validate_final_dataset.py`, `tests/test_validate_final_dataset.py`, `docs/validation_run_output.txt` | They check the final dataset itself (51 checks on the file), not an analysis result |
| `docs/work_log/README.md` (template), `ma_2026-11-13_M2.md` (validation note) | Process documents; the M2 note is about the dataset check |
| `report/01_stakeholder_and_kpis.md` (stakeholder table, constraints, slide text) | Words and structure are reused in notebook Part 1; the baseline numbers were removed and are recomputed there |
| `docs/work_log/ma_2026-11-13_M1.md` | Options and risks for the stakeholder page; a note says the KPI script was removed |
| The corrections to `docs/FINAL_DELIVERABLE_PLAN.md` (112 Stage III/IV hours inside outages, 94 + 18; the January outage runs 10 Jan 18:00 to 20 Jan 18:00 IST, 241 hours) | These are facts about the dataset, not analysis results; the notebook recomputes them and compares |
| The findings about the dataset (outage, `n_pm25` is a raw count, `network_pm25_share` has 3 decimals, `wind_speed` equals sqrt(u10^2 + v10^2) only to about 1e-3) | Dataset properties, useful when writing the dictionary and data-quality section |

## 2. What was removed

KPI baselines (script, table, tests); input drift and model monitoring (scripts, tables T09a to T09c, figure F16, tests); the formal hypothesis status (script, table T07, `report/09_hypothesis_status.md`); the figure registry (it only held F16); the work-log notes for M4 and G4. Any value in my earlier notes (KPI baselines, H1 and H2 status, drift counts) is no longer a result of this branch.

## 3. What is left for me (notebook plan, section 5.1)

| Block | Priority | Output |
| --- | --- | --- |
| Part 1 stakeholders, hypotheses, KPIs computed live, decision rules table | M | T00 |
| 2.3 missingness, outage, cleaning, validation cell | M | T2 |
| 3.2 availability heatmap, 3.3 station map, 3.4 PM2.5 and GRAP timeline (with RB) | M, S, M | F1, F2, F3 |
| 3.9 EDA findings table and interpretations (input to the frozen H1 and H2 plans) | M | findings table |
| 6.1 and 6.2 robustness overview and hypothesis status (after MK's and RB's primary results) | M | T7 |
| 6.3 monitoring and drift | S | F16, T9 |
| Review of RS's blocks (0, 2.1, 2.2, 3.1, 3.5 to 3.7, 8) | M | review notes |

Waits for: RS's station-day table (3.1) before the EDA figures; MK's and RB's primary results before 6.2.

## 4. What I need from other members
- **RS:** the setup and helper cell, the station-day table (3.1), review of my validation script and stakeholder page, and `xarray` in `requirements.txt` (two test files cannot load without it).
- **MK and RB:** their frozen analysis plans (18 Nov, before fitting) and primary results (20 Nov) so I can write the status.

## 5. How to rerun what remains
```
python src/validate_final_dataset.py > docs/validation_run_output.txt   # 51 checks, needs data/processed/final_dataset.parquet
python -m pytest tests/test_validate_final_dataset.py -q
```
