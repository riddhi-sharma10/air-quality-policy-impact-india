# Data dictionary: `data/processed/grap_hourly.csv`

One row per IST hour for 19 Feb 2025 to 30 Sep 2026: 589 days × 24 = **14,136 rows**, 6 columns. It says which GRAP (Graded Response Action Plan) stage was in force across the whole NCR. There is no station column: every station gets the same value for the same hour. Built by `src/build_grap_hourly.py` from `grap_orders.csv` and `grap_gaps.csv`; tests are in `tests/test_grap_hourly.py`.

| Column | Meaning | Values |
| --- | --- | --- |
| `ts_ist` | The **start** of the hour, IST, as `YYYY-MM-DD HH:MM` (the hour 18:00 to 19:00 is `18:00`). Same start-of-hour convention as `hour_ist` in `pollution_hourly.csv`, but the text format differs (that file writes `2025-02-19 00:00:00`), so parse both with `pd.to_datetime` before joining | |
| `grap_stage` | The stage in force at that instant, from the orders. 0 means no GRAP stage invoked | 0, 1, 2, 3, 4 |
| `schedule_version` | The version of the GRAP rules in force at that instant (see below) | `13-Dec-2024`, `21-Nov-2025`, `Sep-2026` |
| `uncertain` | True when the stage at this hour may be wrong around a change: the hour is on a date whose order has no stated time, or inside a missing-order gap | True / False |
| `uncertain_reason` | Why, when `uncertain` is True | `order time not known (PIB posting time or assumed)` or `known gap in orders`; empty otherwise |
| `inferred` | True when the stage follows from the orders around it, not from an order that names this stretch | True / False |

## How the stage is built

- **Invoking Stage k sets the stage to k.** Revoking Stage k sets it to k−1, because the orders say "revoke Stage III and intensify Stage I and II". Higher stages include the lower ones.
- **Orders on the same day are applied in file order.** On 13 Dec 2025 Stage III then Stage IV came the same day, so the stage goes 2, 3, 4.
- **Hour convention.** `grap_stage` is the stage in force at the start of the hour. An hour that contains a change keeps the old stage; the first row at the new stage is the first hour that starts at or after the change. Example: the Stage-II revocation of 24 Feb 2025 was posted by PIB at 18:22, so the `18:00` row is 2 and the `19:00` row is 1.
- **Time of a change.** In order of preference: the time stated in the order (`effective_time_ist`, three orders: the Sub-Committee meeting times of 13 Dec 2025 at 10:00 and 18:30, and 17 Jan 2026 at 20:15), the time PIB posted its press release (an upper bound, since the order comes first), or 12:00 as an assumption. Almost all orders say "with immediate effect" and give no time.

## The two flags

| Flag | Hours | Share | What to do with it |
| --- | --- | --- | --- |
| `uncertain` | 960 | 6.8% | The date of a change is certain, its hour is not. Keep them in the main run, and repeat the analysis without them as a robustness check |
| `inferred` | 3,000 | 21.2% | The date range is in `grap_gaps.csv` with the reason (below). Keep them, and state the assumption |

The two never overlap.

**Inferred stretches (`kind = inferred` in `grap_gaps.csv`):**
- **19 to 23 Feb 2025 (120 hours, stage 2).** The window opens at Stage II because the PIB release of 24 Feb 2025 says Stage II had been in force since 22 Oct 2024. The order itself was not read.
- **16 Jun to 13 Oct 2025 (2,880 hours, stage 0).** The CAQM site lists no order between the Stage-I revocation of 15 Jun and the Stage-I invocation of 14 Oct, so stage 0 follows from the absence of invocations.

**Missing-order gap (`kind = missing_order`):**
- **25 Feb to 6 Mar 2025 (240 hours, flagged `uncertain`).** PIB says on 24 Feb that Stage I remained invoked, and on 7 Mar invokes it again, so a Stage-I revocation must exist in between. No source gives its date. The value in the file is 1 (Stage I stays on); it may have been 0 for part of this stretch.

## Hours by stage

| Stage | Hours | Share |
| --- | --- | --- |
| 0 | 8,067 | 57.1% |
| 1 | 2,995 | 21.2% |
| 2 | 2,103 | 14.9% |
| 3 | 651 | 4.6% |
| 4 | 320 | 2.3% |

By schedule: `13-Dec-2024` 6,612 hours, `21-Nov-2025` 7,488 hours, `Sep-2026` 36 hours (the last day and a half of the window).

## Using it in the merge

- Join on the hour only, after parsing both columns as datetimes: `pd.to_datetime(pollution.hour_ist) == pd.to_datetime(grap.ts_ist)`. A plain string join matches nothing.
- GRAP applies inside the NCR. The control cities (Patna, Lucknow, Kanpur) are outside it, so create `grap_stage_applied`, equal to `grap_stage` for treated stations and 0 for control stations. Keep the raw `grap_stage` as well.
- Stages III and IV together are 971 hours (6.9%), almost all in Nov 2025 to Jan 2026, so most of the policy variation sits in one winter.
- The stage is called because pollution is high, so a plain correlation of PM2.5 with `grap_stage` will look positive. Use it for description, and the difference-in-differences for the effect.

## Known limits

- Order times are mostly unknown (see above), so hour-level precision exists only around three orders.
- One missing order (25 Feb to 6 Mar 2025).
- The 11 Nov 2025 Stage-III invocation (no. 1444) is not on the CAQM site as a file, only its clarification (no. 1445). The date and stage are confirmed by PIB.
- The order of 21 Oct 2026 is in `grap_orders.csv` but falls after the window, so it does not appear here.
