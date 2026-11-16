"""Checks on the exploratory analyses (src/exploratory_analyses.py, outputs/exploratory) and on the notebook's H3 section (Phase 8C)."""
import os
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "outputs")


def table(name, folder="exploratory"):
    path = os.path.join(BASE, folder, "tables") if folder == "exploratory" else os.path.join(BASE, "tables")
    return pd.read_csv(os.path.join(path, name + ".csv"))


def test_x1_winter_reference_matches_frozen_primary():
    t = table("X1_aprmay_fire")
    ref = t[t["Run"].str.startswith("Reference")].iloc[0]["Effect (%)"]
    frozen = table("T04b_h1_effect_plain_units", "main").iloc[0]["Estimate"]
    assert abs(ref - frozen) < 0.05            # same model and sample as the frozen H1, so the same number


def test_status_table_has_the_two_exploratory_analyses():
    st = table("X_status")
    assert len(st) == 2 and set(st["Status by the pre-set rule"]) <= {"SUPPORTED", "NOT SUPPORTED", "INCONCLUSIVE"}


def test_tracer_table_has_every_run_and_outcome_with_ordered_intervals():
    t = table("X2_tracers")
    assert t["Outcome"].nunique() == 6 and t["Run"].nunique() == 7
    assert (t["Decision CI low"] <= t["Effect (%)"]).all() and (t["Effect (%)"] <= t["Decision CI high"]).all()


def test_placebo_and_out_of_sample_tables_are_complete():
    pl = table("X2b_tracer_placebo_shifts")
    assert set(pl["Outcome"]) == {"NO2 / PM2.5", "CO / PM2.5", "PM10 / PM2.5"} and pl["Shift (days)"].abs().min() >= 12
    ev = table("X1b_aprmay_out_of_sample")
    assert len(ev) == 2 and (ev["Test RMSE (ug/m3)"] > 0).all()


def test_h3_notebook_tables_exist_and_are_consistent():
    runs = table("T04q_h3_ventilation_runs", "main")
    assert len(runs) == 7 and runs.iloc[0]["Run"].startswith("PRIMARY")
    assert (runs["CI low"] <= runs["Effect (%)"]).all() and (runs["Effect (%)"] <= runs["CI high"]).all()
    oos = table("T08j_h3_out_of_sample", "main")
    assert len(oos) == 4 and (oos["Test RMSE (ug/m3)"] > 0).all()
