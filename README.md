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

An invocation of Stage k sets the stage to k and a revocation of Stage k sets it to k-1. Most orders say "with immediate effect" and give no time of day, so each change takes effect at the order's meeting time if stated, otherwise at the time PIB posted its release, otherwise at 12:00 IST; hours on such dates and inside the known gap in `grap_gaps.csv` are flagged `uncertain`. The script prints its checks and exits non-zero if one fails.

## Regenerating the fire features
The fire tables are derived, large (about 25 MB) and git-ignored (`data/processed/fire_*.csv`). They are rebuilt from the FIRMS files, the station list and (for the upwind feature) ERA5 winds.

Inputs: `data/raw/firms/fire_archive_SV-C2_829739.csv` (857,474 rows) and `data/raw/firms/fire_nrt_SV-C2_829739.csv` (1,369 rows), a station CSV with `id`, `latitude`, `longitude`, and for the upwind step `data/raw/era5/era5_delhi_*_instant.nc`. The scripts check that 858,843 detections are read.

```
# 1. daily counts and FRP per station, IST date and radius (2 extra days at the start are needed for the lags)
python src/build_fire_features.py --stations data/processed/stations_window.csv --start 2025-02-17 --end 2026-09-30 --out data/processed/fire_features_daily.csv
# 2. lagged versions, trimmed to the study window
python src/add_fire_lags.py --features data/processed/fire_features_daily.csv --start 2025-02-19 --end 2026-09-30 --out data/processed/fire_features_lags.csv
# 3. upwind counts (needs ERA5 u10 and v10 covering the dates; stations outside the ERA5 box are skipped)
python src/build_upwind_features.py --stations data/processed/stations_window.csv --wind-days 1 --out data/processed/fire_upwind_daily.csv
# tests
python tests/test_fire_geometry.py
```
`stations_window.csv` is the rebuilt station list for the study window; until it exists use `data/processed/stations.csv` (56 stations). Expected rows: step 1 is stations x 591 dates x 3 radii (56 stations: 99,288); step 2 is stations x 589 dates x 3 radii (56 stations: 98,952); step 3 is stations in the ERA5 box x dates with a full wind day x 3 radii x 3 half-angles (41 Delhi stations, ERA5 Jan-Jul 2022: 77,859). Every script prints its checks as PASS or FAIL and exits with a non-zero code if one fails.

## Limitations
- **Fire data:** the study window (2025-02-19 to 2026-09-30) contains only one stubble-burning season (October-November 2025), so any test of a fire effect has low statistical power. Fire detections are an incomplete measure: the satellite sees a place only when it passes overhead and cloud or heavy smoke can hide fires, so a day with no rows can mean no fire or no usable pass, which the data cannot tell apart (such days are stored as missing, not zero). The fall in October detections in the downloaded FIRMS box between 2022 (23,859) and 2025 (8,475) is not evidence of any policy effect, because it was not compared with a control group or adjusted for weather or satellite coverage. Detections from 1 July 2026 are near-real-time (preliminary) and may be replaced by the final product. The daily upwind feature is approximate: it uses ERA5 wind on a 0.25-degree grid (about 28 km), averaged over a day, as a stand-in for smoke transport over tens to hundreds of kilometres, and it is not a trajectory model.
- **Treated group:** treated stations = government monitors within 25 km of central Delhi (centre 28.61, 77.21), which includes parts of the NCR. The OpenAQ API caps the search radius at 25 km, so the list covers a circle around central Delhi, not the whole NCR. Stations in places such as Meerut, Sonipat, Bahadurgarh or Panipat are outside it. GRAP applies to the whole NCR and every station in the treated list lies inside it, which is what makes them treated.
- **Inference:** only one treated area and three control cities are available, so cluster-robust standard errors are unreliable here. Inference will use a placebo test (assigning treatment to each control city in turn) and will report station-level and city-level errors side by side. Method to be confirmed with the instructor.
