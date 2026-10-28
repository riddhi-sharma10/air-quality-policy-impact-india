# What to do now (tasks #3 FIRMS and #4 Policy orders)

Written 24 Oct 2026. Tick the boxes as you go. Deadline: 24 Nov.

## The short version

- **#4 Policy orders is finished** except one missing 2025 order that nobody can find so far (step 6, optional).
- **#3 FIRMS is finished as code.** What is left is *running it* on a computer that has the raw satellite files, then reading two pieces of code so you can explain them.
- The computer with the data is your teammate's. Everything below that says "on the data computer" is run there, or by you if the files are copied to you.

| # | Step | Who | Needs |
| --- | --- | --- | --- |
| 1 | Open the pull request | you | a browser |
| 2 | Run the fire scripts | on the data computer | raw FIRMS files |
| 3 | Download the weather files (ERA5) | you or teammate | free Copernicus account |
| 4 | Run the upwind step | on the data computer | step 3 finished |
| 5 | Read two pieces of code | you | 15 minutes |
| 6 | Look for the one missing order | optional | a browser |

---

## Step 1. Open the pull request

- [ ] Open <https://github.com/riddhi-sharma10/air-quality-policy-impact-india/pull/new/grap-policy-orders>
- Base branch: `main`. Click **Create pull request** (not the draft option).
- Title: `Add GRAP policy orders table and hourly stage flag`
- Description: what changed (the GRAP orders table, gaps file, hourly flag script, doc updates; plus the FIRMS status update, the fire scripts now using `stations_final.csv`, and the fire table untracked), and for reviewers: most orders give no time of day so 6.8% of hours are flagged `uncertain`, and one order (a Stage-I revocation between 24 Feb and 7 Mar 2025) is missing.

---

## Step 2. Run the fire scripts (#3) on the data computer

**What you need on that computer:** the folder `data/raw/firms/` containing these two files:

- `fire_archive_SV-C2_829739.csv` (857,474 rows)
- `fire_nrt_SV-C2_829739.csv` (1,369 rows)

If they are not in the project folder, copy them there. They are git-ignored, so they will never come from GitHub.

**Set up once** (open a terminal in the project folder):

```bash
git switch grap-policy-orders
```

```bash
git pull
```

```bash
pip install pandas numpy scikit-learn matplotlib xarray netCDF4 pytest
```

**Run these three, in this order.** Each one prints lines marked PASS or FAIL. If any line says FAIL, stop and send me the whole output.

1. Daily fire counts for the 54 final stations (takes a few minutes):

```bash
python src/build_fire_features.py --stations data/processed/stations_final.csv --start 2025-02-17 --end 2026-09-30 --out data/processed/fire_features_daily.csv
```

Expected: **95,742 rows** (54 stations x 591 dates x 3 radii). Today's file on the old 56-station list has 99,288.

2. Lagged versions (previous day and previous two days):

```bash
python src/add_fire_lags.py --features data/processed/fire_features_daily.csv --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_lags.csv
```

Expected: **95,418 rows** (54 x 589 x 3).

3. The night-date check. This proves night detections land on the right Indian date. Save its output:

```bash
python src/check_night_dates.py > night_check_output.txt
```

Open `night_check_output.txt` and send me the text, or keep it for your report.

4. The tests:

```bash
python -m pytest tests/test_fire_geometry.py -q
```

Expected: all pass.

**Do not commit the CSV files.** They are too big and git ignores them. Only share the PASS/FAIL output and the row counts.

---

## Step 3. Download the weather files (ERA5)

Nothing weather-related can finish until this is done, and it is the slowest step, so start it early. You can do this while step 2 runs.

**One-time setup**

1. Make a free account at <https://cds.climate.copernicus.eu> and accept the licence for "ERA5 hourly data on single levels".
2. On your profile page copy your API key.
3. Create a file called `.cdsapirc` in your user folder (`C:\Users\<your name>\.cdsapirc`) containing exactly two lines, with your own key in place of the placeholder:

```
url: https://cds.climate.copernicus.eu/api
key: PASTE-YOUR-KEY-HERE
```

Never paste the key into a chat, a command, or a file inside the project.

4. Install the downloader:

```bash
pip install "cdsapi>=0.7.4"
```

**Download**

See which of the 7 periods are missing:

```bash
python src/download_era5.py --list
```

Download everything that is missing (leave the terminal open; it queues one request at a time, which can take hours):

```bash
python src/download_era5.py --all
```

If the queue is slow, open two or three terminals and give each a different period label from `--list`, for example:

```bash
python src/download_era5.py 2025_02-04 2025_05-07
```

Then check what arrived (it reports missing files as failures, so it doubles as a progress check):

```bash
python src/inspect_era5_window.py
```

If the first request is rejected for being too large, tell me the exact error. I will split the area into two requests.

Last, turn the grid files into one table per station:

```bash
python src/extract_era5_stations.py
```

---

## Step 4. Run the upwind step (#3)

Only after step 3 finished and `inspect_era5_window.py` passes:

```bash
python src/build_upwind_features.py --stations data/processed/stations_final.csv --wind-days 1 --out data/processed/fire_upwind_daily.csv
```

This keeps only fires that lie in the direction the wind is blowing from. Send me the row count and any FAIL lines.

---

## Step 5. Read two pieces of code (your part of #3)

Open `src/build_fire_features.py` and be able to explain these in your own words.

**A. Lines 78 to 83: turning satellite time into Indian date**

- The satellite file gives time in UTC (world time) as a number without the leading zero: 6:20 comes as `620`.
- `zfill(4)` pads it to `0620` so the computer reads hours and minutes correctly. Without it `620` would be read as "62:0".
- India is 5 hours 30 minutes ahead of UTC, so the script adds that offset *before* taking the date.
- Why it matters: the night satellite pass happens about 19:00 to 22:00 UTC, which is already after midnight in India. A fire seen at 19:30 UTC on the 5th is at 01:00 on the **6th** in India, so it must be counted on the 6th.

**B. Lines 120 to 123: finding the fires near each station**

- The script wants every fire within 50, 100 and 200 km of each station, out of 858,843 fires.
- `BallTree` is a fast way to search points on the globe. With the `haversine` setting it works in *radians*, not degrees, which is why the latitudes and longitudes are converted with `np.radians`.
- The search radius must also be in radians. A distance in km divided by the Earth's radius (6371 km) gives that angle.
- It searches once at 200 km and keeps the distances; the 50 km and 100 km counts are just the nearest of those, so no extra searches are needed.

---

## Step 6 (optional). Find the one missing policy order (#4)

The table has no order for a Stage-I revocation somewhere between **24 Feb 2025 and 7 Mar 2025**. We know it must exist because on 7 Mar Stage-I was invoked again, so it had been lifted first.

If you want to close it: search the Press Information Bureau (<https://pib.gov.in>) or the CAQM site for "CAQM revokes Stage-I of GRAP" with a date in that window. If you find a date, send me the date and the link and I will add the row and rerun the hourly flag. If nobody can find it, leave it. It is written up as a known gap and only affects those ten days.

---

## Rules for the repository

- Commit only code and documents. Never commit data files (`data/raw/...` or the big CSVs).
- Do not add anyone as a co-author in commit messages.
- Work on the branch `grap-policy-orders` until the pull request is merged, then pull `main`.

## Checklist

- [ ] Pull request opened
- [ ] Step 2 done: 95,742 and 95,418 rows, no FAIL lines, night check saved
- [ ] Step 3 started (ERA5 queue is running)
- [ ] Step 4 done after ERA5 arrives
- [ ] Step 5: can explain both code spots
- [ ] Step 6 attempted or skipped on purpose
