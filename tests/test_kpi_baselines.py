"""Tests for src/analysis/01b_kpi_baselines.py: the valid-day and group-day rules, on a tiny table made by hand."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("kpi", ROOT / "src" / "analysis" / "01b_kpi_baselines.py")
kpi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kpi)


def hours(station, group, date, n_valid, value, outage_hours=0):
    """24 hourly rows of one station-day: n_valid hours with `value`, the rest empty; the first `outage_hours` are outage."""
    t = pd.date_range(date, periods=24, freq="h")
    pm = [value] * n_valid + [float("nan")] * (24 - n_valid)
    out = [i < outage_hours for i in range(24)]
    return pd.DataFrame({"station_id": station, "group": group, "hour_ist": t, "pm25": pm, "network_outage": out})


def test_a_day_needs_18_valid_hours():
    df = pd.concat([hours(1, "treated", "2025-11-01", 18, 100.0), hours(2, "treated", "2025-11-01", 17, 100.0)])
    sd = kpi.station_days(df)
    assert list(sd["station_id"]) == [1] and sd["valid_hours"].iloc[0] == 18 and sd["pm25_mean"].iloc[0] == 100.0


def test_outage_hours_are_not_valid_hours():
    sd = kpi.station_days(hours(1, "treated", "2025-11-01", 24, 50.0, outage_hours=7))   # 17 valid hours left
    assert sd.empty
    sd = kpi.station_days(hours(1, "treated", "2025-11-01", 24, 50.0, outage_hours=6))   # 18 valid hours left
    assert len(sd) == 1


def test_group_day_needs_half_of_the_stations_and_averages_valid_days():
    df = pd.concat([hours(1, "treated", "2025-11-01", 24, 100.0), hours(2, "treated", "2025-11-01", 24, 200.0),
                    hours(3, "treated", "2025-11-01", 0, 0.0), hours(4, "treated", "2025-11-01", 0, 0.0),
                    hours(1, "treated", "2025-11-02", 24, 100.0), hours(2, "treated", "2025-11-02", 0, 0.0),
                    hours(3, "treated", "2025-11-02", 0, 0.0), hours(4, "treated", "2025-11-02", 0, 0.0)])
    gd = kpi.group_days(kpi.station_days(df), {"treated": 4})
    assert list(gd["date"]) == [pd.Timestamp("2025-11-01")]          # 2 of 4 valid on day 1, 1 of 4 on day 2
    assert gd["pm25_group_mean"].iloc[0] == 150.0
