# Data dictionary: `data/processed/pollution_hourly.csv`

One row per station per hour for 19 Feb 2025 to 30 Sep 2026 (IST): 14,136 hours × 54 stations from `stations_final.csv`, plus AirNow 8118 (validation only, PM2.5) = 777,480 rows. Every hour is present; missing data is an empty cell. Regenerate with `python src/build_pollution_hourly.py` (needs the downloaded archive, see `src/download_openaq_archive.py`).

| Column | Meaning | Unit |
| --- | --- | --- |
| station_id | OpenAQ location ID (joins to `stations_final.csv`) | |
| hour_ist | Hour BEGINNING, IST clock time (primary time key) | |
| hour_utc | `hour_ist` − 5:30, so it falls at :30 past the UTC hour. Aligning with ERA5 (on the hour) is decided at merge time | UTC |
| stamp_hour_ist | Raw archive stamp hour (= `hour_ist` + 1 h). Kept so the label shift can be undone | |
| pm25, pm10 | Particulate matter | µg/m³ |
| no, no2, nox, so2, co | Gases (the archive reports all of them in ppb, including CO) | ppb |
| o3 | Ozone | µg/m³ |
| local_temp_c, local_rh, local_wind_speed | The station's own sensors, where present (46 of 55 stations; wind from 8 Oct 2025). For the ERA5 comparison | °C, %, m/s |
| n_pm25 … n_o3 | Number of readings averaged into that hour (0 = no data) | count |
| network_pm25_share | Share of the 54 kept stations with PM2.5 in that hour (same value on every row of the hour) | 0 to 1 |
| network_outage | True when `network_pm25_share` < 0.5: a network-wide outage, not clean air. 928 of 14,136 hours (6.6%); longest 11 to 20 Jan 2026 | |

## Rules
- **Outages are flagged, not removed.** Default for analysis: drop `network_outage` hours (leaves 662,378 PM2.5 rows from 54 stations). Other options (keep them, or fill) are a modelling choice.
- **Aggregation:** mean of the readings stamped HH:00 to HH:45. Several sensors of one parameter at a station are averaged per stamp first.
- **Delhi PM values are hourly numbers repeated on four stamps**; Lucknow, Kanpur and Patna report true 15-minute values. The mean treats both the same. About 8% of Delhi PM hours hold more than one value (the value changed mid-hour); these are averaged.
- **Hour 00 IST** in the CPCB files has only the :45 stamp (00:00 to 00:30 never appear), so `n_*` is 1 for that hour.
- **Label shift:** archive stamps mark the END of the interval, so values grouped under stamp hour H are labelled `hour_ist` = H − 1 h. Evidence: AirNow 8118 is clearly end-stamped (files for day D run 01:00 to 00:00 next day), and the median of Delhi stations correlates best with 8118 at lag 0 after the shift (r = 0.954 vs 0.950 and 0.930 at ±1 h; hour-to-hour changes 0.525 vs 0.408 and 0.321). Moderate confidence for the CPCB Delhi feeds. For the true 15-minute feeds the same convention was confirmed from the daily temperature cycle: the local temperature phase of Lucknow, Kanpur and Patna vs Delhi differs from the longitude (sun-time) expectation by only 0.08, −0.23 and 0.33 hours, far from a 1 h offset.
- **QC (nothing else is removed):** negative values → empty; PM2.5 > 1000 or PM10 > 2000 µg/m³ → empty; PM runs of 24 or more identical hours → empty (stuck sensor); spikes (change > 300 µg/m³ in one hour) are only counted. Counts per station and parameter are in `pollution_quality_report.csv`.
- **Units:** one unit per parameter across all stations (`pollution_units.csv`).
