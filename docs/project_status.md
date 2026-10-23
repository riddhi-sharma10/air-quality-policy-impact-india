# Project status: what is done and what is left

## The goal in one line

The final dataset is one table with one row per station per hour. Each row holds pollution readings, weather, fire features and the policy status for that hour. Everything below feeds that table.

**Study window under discussion:** 19 Feb 2025 to 30 Sep 2026 (589 days, 14,136 hours per station). The OpenAQ archive has nothing for 2023 and 2024, and only fragments of 2022, so this is the only continuous stretch.

## What the final table will contain

| Group | Columns | Source |
| --- | --- | --- |
| Identifiers | station ID, city, group (treated or control), sub-area, hour (UTC and IST) | station list |
| Pollution | PM2.5 and PM10 (µg/m³); NO, NO2, NOx, SO2, CO (ppb); O3 (µg/m³) | OpenAQ |
| Weather | wind u and v, wind speed and direction, temperature, dewpoint, pressure, boundary layer height, rain | ERA5 |
| Fire | detection count and total fire radiative power at 50, 100 and 200 km, plus an upwind version | FIRMS |
| Policy | GRAP stage in force, the GRAP schedule version, before or after each order | CAQM orders |
| Calendar | hour, weekday, season, festival flags | derived |

Row count is an estimate: with about 50 stations and about 85% hourly coverage, roughly 600,000 rows, well above the 100,000 minimum. The real number depends on the rebuilt station list.

## 1. OpenAQ (pollution): the biggest remaining job

| Done | Left |
| --- | --- |
| Station metadata for Delhi, Lucknow, Kanpur and Patna; `stations.csv` with 56 stations | Rebuild the list by hours of PM2.5 and PM10 covered inside the window. The old list used only first and last dates |
| AirNow station 8118 kept as a separate validation series | Decide multi-ID sites (R K Puram, Anand Vihar) and the close pairs (Lodhi Road, Gurugram) |
| AWS CLI works; archive layout understood | Bulk download all kept stations, 2025 to 2026 |
| Test downloads for stations 6358 and 2456 inspected | Aggregate to the clock hour with one rule (Delhi values repeat across four stamps; Lucknow has real 15-minute data), and keep the number of readings per hour |
| Findings: each pollutant has one unit in the window; PM2.5 hours present 85.2% (Delhi) and 89.9% (Lucknow); gases appear in ppb; NOx and local wind start 8 Oct 2025 | Resolve the open points: about 9% of the :15 stamps change in Delhi, and 8.5% of hours hold more than one value |
| | Test whether a timestamp marks the start or end of the hour. This is untested |
| | Quality checks: negatives, flatlines, spikes, missing hours; report counts |
| | Validate CPCB PM2.5 against AirNow 8118 |
| | Output `pollution_hourly` and its data dictionary |

## 2. ERA5 (weather)

| Done | Left |
| --- | --- |
| Account and licence; limits learned (7 variables cost about 1,008 per day, so at most 120 days per request); each request returns an instant and an accum file | Test the wide box (N 29.5, S 25, W 76.5, E 85.75) in the form: does the size bar change with the area? |
| Delhi 2022: Jan–Apr and May–Jul downloaded, renamed and checked (2,880 and 2,208 steps, 8 × 7 grid, expver 1) | Request the window: about 7 requests (2025 Feb–Apr, May–Jul, Aug–Oct, Nov–Dec; 2026 Jan–Mar, Apr–Jun, Jul–Sep), two or three at a time |
| `inspect_era5.py` works and exits non-zero on failure | Decide the two queued 2022 requests: Nov–Dec 2022 has no pollution data, so consider cancelling it |
| Understood: time is UTC; precipitation is the hour ending at the timestamp, so sum hourly values | Update the checker and the download script for the new window and area (both still assume Delhi 2022) |
| | Extract values at each station's nearest grid cell |
| | Choose the time alignment (pollution and ERA5 are 30 minutes apart) |
| | Convert units; compute wind speed and direction; pick the wind-direction convention and test it |
| | Mark the newest months as preliminary (ERA5T) |
| | Compare ERA5 with the stations' own local temperature and wind (available from Oct 2025) |

The CDS queue is the bottleneck. Today it held about 10,000 queued requests, and priority drops if you hold many at once.

## 3. FIRMS (fires)

| Done | Left |
| --- | --- |
| Request 829739 downloaded: archive file (857,474 rows, to 30 Jun 2026) and near-real-time file (1,369 rows, from 1 Jul 2026) | Resolve the night-detection date check (UTC against IST dates); the earlier report's two statements conflict |
| Quality checks passed: no duplicates, all rows inside the box, plausible seasons | Rerun `build_fire_features.py` for the new station list and window |
| `build_fire_features.py` written; independent brute-force test matched on 28 of 28 cases | Read lines 76, 78, 111 to 114 and 160 yourself and explain them |
| Rules set: IST dates, no-detection dates are missing and not zero, near-real-time rows flagged | Upwind-weighted feature: needs ERA5 wind and a tested direction convention |
| | Decide the lag (same day, previous 24 and 48 hours) so fires can't "explain" earlier readings |
| | Keep `fire_features_daily.csv` out of Git; document how to regenerate it |
| | State the limit that the window has only one burning season (Oct–Nov 2025) |

## 4. Policy orders (CAQM GRAP): nothing built yet

| Done | Left |
| --- | --- |
| Located the CAQM site; some order dates noted from search snippets | Compile the table from the PDFs: order date, stage, invoked or revoked, area, order number, link |
| | Cover every order from February 2025 to September 2026 (only parts have been seen so far) |
| | Record the GRAP schedule version for each order (revised 13 Dec 2024 and 21 Nov 2025) |
| | Turn the table into an hourly stage flag, including revoke and re-invoke cases |

## 5. Merging and finishing

| Step | Status |
| --- | --- |
| Join pollution, weather (station to nearest grid cell, aligned hour), fire (station and IST date) and policy (date and area) | Not started |
| Row count, duplicates, missing-value summary, data dictionary, provenance log | Partly: log started |
| EDA, difference-in-differences, event study, placebo tests, model, SHAP, MLflow | Not started |
| Report, slides, public GitHub repository | Not started |

## Decisions that block progress

1. Regenerate the OpenAQ key. It has appeared in several pasted commands.
2. Choose the hour-aggregation rule and the time alignment.

## Suggested order

1. Regenerate the key and settle the night-detection check.
2. Rebuild the station list on hours covered, then bulk-download OpenAQ.
3. Test the ERA5 wide box and submit the window requests in small batches.
4. While ERA5 queues: compile the GRAP table, rerun the fire features, run the start-versus-end test.
5. Merge, check, then analyse.

The semester ends on 24 Nov, about four weeks away. The merge needs ERA5, so submit those requests as soon as the window is settled.
