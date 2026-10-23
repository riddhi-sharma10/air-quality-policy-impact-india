# air-quality-policy-impact-india
Northern India has severe pollution spikes every autumn and winter, and authorities respond with restrictions on stubble burning, construction and vehicles. It is unclear whether those restrictions lower measured pollution or whether weather would have reduced it anyway.

This project integrates hourly air quality readings (CPCB via OpenAQ), satellite fire detections (NASA FIRMS) and weather data (ERA5) into one dataset. It estimates the policy effect with difference-in-differences, and uses boosted models with SHAP to find what drives the spikes. The aim is to help a pollution control board decide where and when to enforce restrictions.


## Repository layout
- `src/` scripts (`build_station_table.py` builds the station list from the OpenAQ JSON files)
- `data/raw/openaq_api/` OpenAQ v3 station lists (kept in the repo, small)
- `data/processed/` station tables produced by the scripts
- `docs/provenance_log.csv` where every dataset came from and when

## Re-downloading large data
Large downloads are git-ignored (`data/raw/openaq_archive/`, `data/raw/era5/`, `data/raw/firms/`). To rebuild them, follow the rows in `docs/provenance_log.csv`. API keys are never committed: set them as environment variables or put them in a local `.env` file (also git-ignored).

## Limitations
- **Treated group:** treated stations = government monitors within 25 km of central Delhi (centre 28.61, 77.21), which includes parts of the NCR. The OpenAQ API caps the search radius at 25 km, so the list covers a circle around central Delhi, not the whole NCR. Stations in places such as Meerut, Sonipat, Bahadurgarh or Panipat are outside it. GRAP applies to the whole NCR and every station in the treated list lies inside it, which is what makes them treated.
- **Inference:** only one treated area and three control cities are available, so cluster-robust standard errors are unreliable here. Inference will use a placebo test (assigning treatment to each control city in turn) and will report station-level and city-level errors side by side. Method to be confirmed with the instructor.
