# air-quality-policy-impact-india
Northern India has severe pollution spikes every autumn and winter, and authorities respond with restrictions on stubble burning, construction and vehicles. It is unclear whether those restrictions lower measured pollution or whether weather would have reduced it anyway.

This project integrates hourly air quality readings (CPCB via OpenAQ), satellite fire detections (NASA FIRMS) and weather data (ERA5) into one dataset. It estimates the policy effect with difference-in-differences, and uses boosted models with SHAP to find what drives the spikes. The aim is to help a pollution control board decide where and when to enforce restrictions.


## Repository layout
- `src/` scripts (`build_station_table.py` builds the station list from the OpenAQ JSON files)
- `data/raw/openaq_api/` OpenAQ v3 station lists (kept in the repo, small)
- `data/processed/` station tables produced by the scripts
- `src/build_grap_hourly.py` turns `data/processed/grap_orders.csv` (GRAP orders compiled by hand from the CAQM PDFs and PIB releases, with a `verification` column) and `grap_gaps.csv` into an hourly stage flag, `grap_hourly.csv`
- `docs/provenance_log.csv` where every dataset came from and when

## Re-downloading large data
Large downloads are git-ignored (`data/raw/openaq_archive/`, `data/raw/era5/`, `data/raw/firms/`). To rebuild them, follow the rows in `docs/provenance_log.csv`. API keys are never committed: set them as environment variables or put them in a local `.env` file (also git-ignored).

- **CAQM GRAP orders:** the order and schedule PDFs are in `data/raw/caqm_grap_pdfs/` (git-ignored, 32 files, 116 MB). Each source address is in the `pdf_url` column of `data/processed/grap_orders.csv`; download one with `curl -L -o <file> "<pdf_url>"`. Orders before 2 Apr 2025 are not on the CAQM site and come from PIB press releases (release numbers in the `pib_prid` column).

## Regenerating the GRAP stage flag
`data/processed/grap_hourly.csv` (one row per IST hour, 19 Feb 2025 to 30 Sep 2026, stage 0 to 4 for the whole NCR) is built from the order table:

```
python src/build_grap_hourly.py
```

An invocation of Stage k sets the stage to k and a revocation of Stage k sets it to k-1. Most orders say "with immediate effect" and give no time of day, so each change takes effect at the order's meeting time if stated, otherwise at the time PIB posted its release, otherwise at 12:00 IST; hours on such dates and inside the missing-order gap in `grap_gaps.csv` are flagged `uncertain`, and the two stretches the orders only imply (19 to 23 Feb 2025 and 16 Jun to 13 Oct 2025) are flagged `inferred`. Columns are described in `docs/grap_hourly_dictionary.md`; tests: `python -m pytest tests/test_grap_hourly.py -q`. The script prints its checks and exits non-zero if one fails.

## Regenerating the fire features
The fire tables are derived, large (about 25 MB) and git-ignored (`data/processed/fire_*.csv`). They are rebuilt from the FIRMS files, the station list and (for the upwind feature) the hourly station wind table `data/processed/era5_station_hourly.csv`, which `src/extract_era5_stations.py` builds from `data/raw/era5_points/`.

Inputs: `data/raw/firms/fire_archive_SV-C2_829739.csv` (857,474 rows) and `data/raw/firms/fire_nrt_SV-C2_829739.csv` (1,369 rows), a station CSV with `id`, `latitude`, `longitude`, and for the upwind step `data/processed/era5_station_hourly.csv` (54 stations, hourly u10 and v10, UTC). The scripts check that 858,843 detections are read.

```
# 1. daily counts and FRP per station, IST date and radius (2 extra days at the start are needed for the lags)
python src/build_fire_features.py --stations data/processed/stations_final.csv --start 2025-02-17 --end 2026-09-30 --out data/processed/fire_features_daily.csv
# 2. lagged versions, trimmed to the study window
python src/add_fire_lags.py --features data/processed/fire_features_daily.csv --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_lags.csv
# 3. upwind counts (reads data/processed/era5_station_hourly.csv; stations without wind there are skipped)
python src/build_upwind_features.py --stations data/processed/stations_final.csv --wind-days 1 --out data/processed/fire_upwind_daily.csv
# (the 2022 Delhi test files need --wind-source grid: gridded era5_delhi_*_instant.nc in data/raw/era5/; the default is --wind-source table)
# tests
python tests/test_fire_geometry.py
python -m pytest tests/test_upwind_points.py -q
```
`data/processed/stations_final.csv` is the station list for the study window (54 stations, chosen on hours covered); the older `stations.csv` has 56, including the duplicates 10900 and 11607 that were dropped. Expected rows: step 1 is stations x 591 dates x 3 radii (54 stations: 95,742; the table built on the old 56-station list has 99,288); step 2 is stations x 589 dates x 3 radii (54 stations: 95,418); step 3 is stations with wind x dates with a full wind day x 3 radii x 3 half-angles (54 stations x 588 dates, 20 Feb 2025 to 30 Sep 2026: 285,768; with `--wind-days 2` it starts on 21 Feb and has 285,282; the 2022 Delhi test with `--wind-source grid`: 41 stations, 77,859). The upwind table starts on 20 Feb 2025 because the weather table starts at 05:30 IST on 19 Feb, so IST 19 Feb has no full day of wind. Its fire columns are empty (NaN) on the 22 dates with no detection anywhere (10,692 rows) and `is_nrt` marks the preliminary rows from 1 Jul 2026. The upwind table holds same-day values, like `lag0`: for an hourly reading use the previous IST day. The output of the last run is in `docs/upwind_run_output.txt`. Only `lag1` and `lag2` may be used to explain an hourly reading. Every script prints its checks as PASS or FAIL and exits with a non-zero code if one fails.

## Final dataset
One row per station per IST hour (54 stations x 14,136 hours = 763,344 rows, 70 columns): pollution, weather, fire, GRAP policy and calendar columns. It is built by one script from the processed tables and written only if all of its checks pass (the last run is saved in `docs/final_dataset_run_output.txt`):

```
python src/build_final_dataset.py        # writes data/processed/final_dataset.csv and final_dataset.parquet (git-ignored)
python -m pytest tests -q                # the tests, including one full run on the real files
```
Inputs: `stations_final.csv`, `pollution_hourly.csv`, `era5_station_hourly.csv`, `fire_features_daily.csv`, `fire_upwind_daily.csv`, `grap_hourly.csv` (all in `data/processed/`, git-ignored except the station and GRAP tables) and the raw FIRMS files. Every column, unit, join rule and missing-value meaning is in `docs/final_dataset_dictionary.md`. Two settings in the script control the time alignment (`ERA5_STAMP_OFFSET_HOURS`, `NONPM_ALIGN_LAG_ROWS`); the analysis should repeat the main model with the weather offset at +1 and -1. The archive labels all the gas columns ppb, which is wrong: NO and NO2 are µg/m³ and NOx is ppm (confirmed against CPCB's protocol and a fit), and CO and SO2 are probably mg/m³ and µg/m³; the dictionary has the details. Nothing is rescaled.

## Limitations
- **Fire data:** the study window (2025-02-19 to 2026-09-30) contains only one stubble-burning season (October-November 2025), so any test of a fire effect has low statistical power. Fire detections are an incomplete measure: the satellite sees a place only when it passes overhead and cloud or heavy smoke can hide fires, so a day with no rows can mean no fire or no usable pass, which the data cannot tell apart (such days are stored as missing, not zero). The fall in October detections in the downloaded FIRMS box between 2022 (23,859) and 2025 (8,475) is not evidence of any policy effect, because it was not compared with a control group or adjusted for weather or satellite coverage. Detections from 1 July 2026 are near-real-time (preliminary) and may be replaced by the final product. The daily upwind feature is approximate: it uses ERA5 wind on a 0.25-degree grid (about 28 km), averaged over a day, as a stand-in for smoke transport over tens to hundreds of kilometres, and it is not a trajectory model.
- **Treated group:** treated stations = government monitors within 25 km of central Delhi (centre 28.61, 77.21), which includes parts of the NCR. The OpenAQ API caps the search radius at 25 km, so the list covers a circle around central Delhi, not the whole NCR. Stations in places such as Meerut, Sonipat, Bahadurgarh or Panipat are outside it. GRAP applies to the whole NCR and every station in the treated list lies inside it, which is what makes them treated.
- **Inference:** only one treated area and three control cities are available, so cluster-robust standard errors are unreliable here. Inference will use a placebo test (assigning treatment to each control city in turn) and will report station-level and city-level errors side by side. Method to be confirmed with the instructor.

## Analysis notebook
`notebooks/air_quality_policy_impact.ipynb` runs the whole analysis from `data/processed/final_dataset.parquet` (git-ignored; build it with the scripts above or copy it in). Two ways to run it:

```
python run_all.py --from-final          # runs every cell in one fresh process; executed copy in outputs/executed_notebook.ipynb
```

or open the notebook, restart the kernel and run all cells from the repository root or from `notebooks/`. It writes every figure (PNG and SVG) to `outputs/figures`, every table to `outputs/tables`, and the station-day analysis tables to `data/processed/analysis_*.parquet` (git-ignored). A run takes about 5 minutes. Cell 12.1 lists everything saved and fails if a figure has no caption; cell 12.4 runs the final checklist. Tested on Windows with Python 3.10 (and in a copy made from the tracked files plus the parquet only); **not yet tested in Google Colab**: there, clone the repository, copy the parquet into `data/processed/`, and expect `shap` to be missing (one cell skips it). The plan is in `docs/Final_Notebook_Plan.md`; requirement checks in `docs/methods_check.md`.

## App, MLflow log and deviation note
`app/streamlit_app.py` is a read-only Streamlit app over `outputs/` (timeline, model metrics, a next-day advisory from the persistence-plus-weather model with its test error, hypothesis status): `pip install -r requirements.txt`, then `streamlit run app/streamlit_app.py` from the repository root after the notebook has run. A `Dockerfile` builds the same app (not tested here). `scripts/log_mlflow.py` logs the persistence-plus-weather model, its parameters and test metrics to MLflow (SQLite file `mlflow.db`, git-ignored) and stops if it does not reproduce the notebook's scores. `docs/deviation_note.md` lists the deviations from the Stage 1 summary for instructor approval.
