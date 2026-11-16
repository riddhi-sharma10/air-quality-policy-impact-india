"""Read-only app over the saved outputs of the analysis notebook.

Run from the repository root:   streamlit run app/streamlit_app.py
It reads only outputs/tables and outputs/figures (made by `python run_all.py --from-final`); it fits nothing and reads no raw data.
Pages: the PM2.5, fire and GRAP timeline; the model metrics; a next-day advisory from the simple persistence-plus-weather model; the hypothesis status.
Every number is association in one winter of observational data, not proof that fires or GRAP caused a change.
"""
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES, FIGURES = os.path.join(ROOT, "outputs", "tables"), os.path.join(ROOT, "outputs", "figures")
TREATED, CONTROL, GREY = "#D55E00", "#0072B2", "#999999"
THRESHOLD = 60                                   # the national 24-hour PM2.5 standard, ug/m3


@st.cache_data
def table(name, **kwargs):
    path = os.path.join(TABLES, name + ".csv")
    return pd.read_csv(path, **kwargs) if os.path.exists(path) else None


def advisory(coefficients, inputs):
    """Next-day PM2.5 from yesterday's PM2.5 and the weather: exp(linear predictor) times the smearing factor (log scale regression)."""
    c = coefficients["Coefficient"]
    wind_from = np.radians(inputs["wind_from_deg"])
    x = {"Intercept": 1.0, "log_yday": np.log(inputs["yesterday"]), "wind_speed": inputs["wind_speed"], "wind_dir_sin": np.sin(wind_from), "wind_dir_cos": np.cos(wind_from),
         "t2m_c": inputs["t2m_c"], "rh_pct": inputs["rh_pct"], "blh_m": inputs["blh_m"], "tp_mm": inputs["tp_mm"], "sp_hpa": inputs["sp_hpa"]}
    return float(np.exp(sum(c[k] * v for k, v in x.items())) * c["smearing factor"])


def category(prediction, rmse):
    """Advice from the prediction and its test error: clear only when the whole error band is on one side of the standard."""
    if prediction - rmse > THRESHOLD:
        return "High: above the 60 ug/m3 standard even at the low end of the error band"
    if prediction + rmse < THRESHOLD:
        return "Low: below the 60 ug/m3 standard even at the high end of the error band"
    return "Uncertain: the error band includes the 60 ug/m3 standard"


def timeline_page():
    st.header("PM2.5, fire counts and the GRAP stage")
    daily = table("T04_group_day", parse_dates=["date_ist"])
    if daily is None:
        st.warning("T04_group_day.csv not found: run `python run_all.py --from-final` first."); return
    low, high = daily["date_ist"].min().date(), daily["date_ist"].max().date()
    start, end = st.slider("Dates", min_value=low, max_value=high, value=(low, high))
    shown = daily[daily["date_ist"].between(pd.Timestamp(start), pd.Timestamp(end))]
    treated, control = shown[shown["group"] == "treated"], shown[shown["group"] == "control"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1.3, 1]})
    axes[0].plot(treated["date_ist"], treated["pm25"], color=TREATED, lw=1.3, label="Treated stations (GRAP applies)")
    axes[0].plot(control["date_ist"], control["pm25"], color=CONTROL, lw=1.3, label="Control cities")
    axes[0].axhline(THRESHOLD, color="black", ls=":", lw=1); axes[0].text(shown["date_ist"].min(), THRESHOLD, " 60 ug/m3 standard", va="bottom", fontsize=9)
    axes[0].set_ylabel("Daily mean PM2.5 (ug/m3)"); axes[0].legend(loc="upper right")
    axes[1].plot(treated["date_ist"], treated["n_up_nh_100km_45deg_lag1"], color=GREY, lw=1); axes[1].set_ylabel("Upwind fire count\n(previous day)")
    axes[2].step(treated["date_ist"], treated["stage_max"], color=TREATED, where="post"); axes[2].set_ylabel("GRAP stage"); axes[2].set_yticks(range(5)); axes[2].set_xlabel("Date (IST)")
    fig.tight_layout(); st.pyplot(fig)
    st.caption("Missing days are gaps, not zeros. A stage is invoked because pollution is already high, so the chart shows association, not effect.")


def metrics_page():
    st.header("Model metrics on unseen days")
    scores = table("T08f_prediction_scores_extended")
    if scores is None:
        st.warning("T08f_prediction_scores_extended.csv not found."); return
    st.dataframe(scores.round(2), hide_index=True)
    st.bar_chart(scores.set_index("Model")["RMSE"])
    st.caption("Test period: 1 Jan to 30 Sep 2026. RMSE and MAE in ug/m3 (lower is better); R-squared higher is better. Repeating yesterday's value beats the weather-only regressions.")


def advisory_page():
    st.header("Next-day advisory (persistence plus weather)")
    coefficients = table("T08i_advisory_model", index_col=0)
    if coefficients is None:
        st.warning("T08i_advisory_model.csv not found."); return
    rmse = float(coefficients.loc["test RMSE (ug/m3)", "Coefficient"])
    col1, col2 = st.columns(2)
    with col1:
        yesterday = st.number_input("PM2.5 yesterday (ug/m3)", 1.0, 1000.0, 100.0)
        t2m_c = st.number_input("Mean temperature (deg C)", -5.0, 45.0, 15.0)
        wind_speed = st.number_input("Mean wind speed (m/s)", 0.0, 15.0, 2.0)
        wind_from = st.number_input("Wind from (degrees, 0 to 360)", 0.0, 360.0, 300.0)
    with col2:
        rh_pct = st.number_input("Relative humidity (%)", 0.0, 100.0, 60.0)
        blh_m = st.number_input("Boundary-layer height (m)", 20.0, 3000.0, 300.0)
        tp_mm = st.number_input("Rain (mm in the day)", 0.0, 100.0, 0.0)
        sp_hpa = st.number_input("Surface pressure (hPa)", 900.0, 1050.0, 990.0)
    prediction = advisory(coefficients, {"yesterday": yesterday, "t2m_c": t2m_c, "wind_speed": wind_speed, "wind_from_deg": wind_from, "rh_pct": rh_pct, "blh_m": blh_m, "tp_mm": tp_mm, "sp_hpa": sp_hpa})
    st.metric("Predicted PM2.5 tomorrow", f"{prediction:.0f} ug/m3", f"+/- {rmse:.0f} (test RMSE)", delta_color="off")
    st.write(category(prediction, rmse))
    st.caption("A simple regression of log PM2.5 on log yesterday and the day's weather, without station effects; the error band is the test RMSE of unseen days in 2026. "
               "It uses the observed weather of the target day (a forecast adds error), misses cold extremes, and rests on one winter: a pilot aid, not a validated forecast.")


def status_page():
    st.header("Hypothesis status by the frozen rules")
    status = table("T10_hypothesis_status")
    if status is None:
        st.warning("T10_hypothesis_status.csv not found."); return
    st.dataframe(status, hide_index=True)
    st.write("H1 (upwind fire counts and PM2.5): the frozen rule is met but the evidence is weak. H2 (GRAP and PM2.5): inconclusive, with no usable counterfactual.")
    picture = os.path.join(FIGURES, "F15b_robustness_overview.png")
    if os.path.exists(picture):
        st.image(picture)


st.set_page_config(page_title="Air quality, fires and GRAP", layout="wide")
st.title("Do burning and emission restrictions reduce PM2.5 in Northern India?")
st.caption("Read-only view of the notebook outputs. Associations in observational data from one winter; not proof of cause.")
page = st.sidebar.radio("Page", ["Timeline", "Model metrics", "Next-day advisory", "Hypothesis status"])
{"Timeline": timeline_page, "Model metrics": metrics_page, "Next-day advisory": advisory_page, "Hypothesis status": status_page}[page]()
