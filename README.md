# air-quality-policy-impact-india
Northern India has severe pollution spikes every autumn and winter, and authorities respond with restrictions on stubble burning, construction and vehicles. It is unclear whether those restrictions lower measured pollution or whether weather would have reduced it anyway.

This project integrates hourly air quality readings (CPCB via OpenAQ), satellite fire detections (NASA FIRMS) and weather data (ERA5) into one dataset. It estimates the policy effect with difference-in-differences, and uses boosted models with SHAP to find what drives the spikes. The aim is to help a pollution control board decide where and when to enforce restrictions.
