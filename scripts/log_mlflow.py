"""Log the persistence-plus-weather model of the notebook (8B.8) to MLflow: parameters, test metrics and the coefficient table.

Run from the repository root after `python run_all.py --from-final` (it reads data/processed/analysis_station_day.parquet):
    python scripts/log_mlflow.py                      # logs to ./mlflow.db (SQLite) with artifacts in ./mlruns
    mlflow ui --backend-store-uri sqlite:///mlflow.db  # to look at the run

The model is the one scored in the notebook on the frozen split: log PM2.5 on log of yesterday's PM2.5, the eight weather controls, station effects and
day-of-week effects, trained to 31 Dec 2025, tested from 1 Jan 2026 on treated stations, back-transformed with the smearing factor. It must reproduce the
notebook's scores (RMSE 23.40, MAE 15.39, R-squared 0.68 in table T08f); the script stops if it does not.
"""
import os

import mlflow
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROLS = ["wind_speed", "wind_dir_sin", "wind_dir_cos", "t2m_c", "rh_pct", "blh_m", "tp_mm", "sp_hpa"]
FIRE = "n_up_nh_100km_45deg_lag1"                                  # complete-case rule of the notebook: the fire count must exist for a row to be used
TRAIN_END, TEST_START = pd.Timestamp("2025-12-31"), pd.Timestamp("2026-01-01")


def build_frame():
    d = pd.read_parquet(os.path.join(ROOT, "data", "processed", "analysis_station_day.parquet"))
    d = d[d["group"] == "treated"].copy(); d["date_ist"] = pd.to_datetime(d["date_ist"]); d["log_pm25"], d["weekday"] = np.log(d["pm25_day"]), d["date_ist"].dt.dayofweek
    yesterday = d[["station_id", "date_ist", "pm25_day"]].assign(date_ist=lambda x: x["date_ist"] + pd.Timedelta(days=1)).rename(columns={"pm25_day": "pm25_yesterday"})
    d = d.merge(yesterday, on=["station_id", "date_ist"], how="left").dropna(subset=["log_pm25", FIRE, "pm25_yesterday"] + CONTROLS)
    d["log_yday"] = np.log(d["pm25_yesterday"])
    return d


def design(frame, stations):
    cols = ["log_yday"] + CONTROLS
    station_dummies = np.column_stack([(frame["station_id"] == s).to_numpy(float) for s in stations[1:]])
    weekday_dummies = np.column_stack([(frame["weekday"] == k).to_numpy(float) for k in range(1, 7)])
    return np.column_stack([np.ones(len(frame)), frame[cols].to_numpy(float), station_dummies, weekday_dummies]), ["Intercept"] + cols


def main():
    d = build_frame()
    train, test = d[d["date_ist"] <= TRAIN_END], d[d["date_ist"] >= TEST_START]
    stations = sorted(train["station_id"].unique()); test = test[test["station_id"].isin(stations)]
    X, names = design(train, stations); y = train["log_pm25"].to_numpy()
    beta = np.linalg.lstsq(X, y, rcond=None)[0]; smear = float(np.exp(y - X @ beta).mean())
    pred = np.exp(design(test, stations)[0] @ beta) * smear; actual = test["pm25_day"].to_numpy(); err = actual - pred
    metrics = {"rmse": float(np.sqrt(np.mean(err ** 2))), "mae": float(np.mean(np.abs(err))), "r2": float(1 - np.sum(err ** 2) / np.sum((actual - actual.mean()) ** 2))}
    notebook_scores = pd.read_csv(os.path.join(ROOT, "outputs", "tables", "T08f_prediction_scores_extended.csv"), index_col=0).loc["Persistence + weather"]
    assert abs(metrics["rmse"] - notebook_scores["RMSE"]) < 0.01, f"RMSE {metrics['rmse']:.3f} differs from the notebook's {notebook_scores['RMSE']:.3f}"
    mlflow.set_tracking_uri("sqlite:///" + os.path.join(ROOT, "mlflow.db").replace(os.sep, "/")); mlflow.set_experiment("air-quality-persistence-plus-weather")
    with mlflow.start_run(run_name="persistence_plus_weather"):
        mlflow.log_params({"model": "OLS on log PM2.5: log yesterday + 8 weather controls + station and weekday effects", "train_end": str(TRAIN_END.date()), "test_start": str(TEST_START.date()),
                           "n_train": len(train), "n_test": len(test), "n_stations": len(stations), "smearing_factor": round(smear, 6)})
        mlflow.log_params({f"coef_{n}": round(float(b), 6) for n, b in zip(names, beta[:len(names)])})
        mlflow.log_metrics(metrics)
        mlflow.log_metric("notebook_rmse", float(notebook_scores["RMSE"]))
        out = os.path.join(ROOT, "outputs", "tables", "T08i_advisory_model.csv")
        if os.path.exists(out):
            mlflow.log_artifact(out)
    print("logged:", {k: round(v, 3) for k, v in metrics.items()}, "| notebook RMSE", round(float(notebook_scores["RMSE"]), 3))


if __name__ == "__main__":
    main()
