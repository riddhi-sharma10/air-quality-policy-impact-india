"""Tests for src/fire_empty_days.py (the G1 rule for dates with no detection). Run:  python tests/test_fire_empty_days.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fire_empty_days import apply_zero_days, classify_dates  # noqa: E402


def totals(start, values):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


def test_isolated_monsoon_day_between_quiet_days_is_cloud():
    t = totals("2025-07-03", [94, 6, 0, 2, 1])
    s = classify_dates(t)
    assert s["2025-07-05"] == "zero_assumed"
    assert (s.drop(pd.Timestamp("2025-07-05")) == "observed").all()


def test_two_day_monsoon_run_is_still_cloud():
    s = classify_dates(totals("2025-08-01", [5, 0, 0, 3]))
    assert s.tolist() == ["observed", "zero_assumed", "zero_assumed", "observed"]


def test_three_day_run_is_an_outage_even_in_the_monsoon():
    s = classify_dates(totals("2026-07-10", [31, 0, 0, 0, 9]))
    assert s.tolist() == ["observed", "outage", "outage", "outage", "observed"]


def test_empty_day_outside_the_monsoon_is_an_outage():
    # 12 Nov 2025: neighbours had 1,286 and 838 detections; also March and April
    assert classify_dates(totals("2025-11-11", [1286, 0, 838])).iloc[1] == "outage"
    assert classify_dates(totals("2026-03-09", [243, 0, 5])).iloc[1] == "outage"
    assert classify_dates(totals("2026-04-28", [440, 0, 0, 809])).iloc[1:3].tolist() == ["outage", "outage"]


def test_a_busy_neighbour_makes_it_an_outage():
    # 2 Jun 2026: neighbours 17 and 114 (limit is under 100 on both sides), also the day before at exactly 100
    assert classify_dates(totals("2026-06-01", [17, 0, 114])).iloc[1] == "outage"
    assert classify_dates(totals("2025-07-01", [100, 0, 5])).iloc[1] == "outage"
    assert classify_dates(totals("2025-07-01", [99, 0, 5])).iloc[1] == "zero_assumed"


def test_a_run_at_the_edge_of_the_data_is_an_outage():
    assert classify_dates(totals("2025-07-01", [0, 4, 5])).iloc[0] == "outage"
    assert classify_dates(totals("2025-07-01", [4, 5, 0])).iloc[2] == "outage"


def test_run_spanning_the_end_of_the_monsoon_is_an_outage():
    s = classify_dates(totals("2025-09-29", [3, 0, 0, 4]))      # 30 Sep and 1 Oct: October is not monsoon
    assert s.iloc[1] == "outage" and s.iloc[2] == "outage"


def test_missing_dates_are_refused():
    t = totals("2025-07-01", [1, 2, 3]).drop(pd.Timestamp("2025-07-02"))
    with pytest.raises(ValueError):
        classify_dates(t)


def test_real_study_window_gives_8_cloud_days_and_14_outage_days():
    root = Path(__file__).resolve().parent.parent
    files = [root / "data" / "raw" / "firms" / n for n in ("fire_archive_SV-C2_829739.csv", "fire_nrt_SV-C2_829739.csv")]
    if not all(f.exists() for f in files):
        pytest.skip("needs the raw FIRMS files")
    from build_fire_features import load_detections
    det, _ = load_detections()
    c = det.groupby("ist_date").size()
    c = c.reindex(pd.date_range(c.index.min(), c.index.max(), freq="D"), fill_value=0)
    w = classify_dates(c)["2025-02-17":"2026-09-30"]
    assert (w == "zero_assumed").sum() == 8 and (w == "outage").sum() == 14
    assert [d.strftime("%Y-%m-%d") for d in w[w == "zero_assumed"].index] == [
        "2025-07-05", "2025-07-07", "2025-07-14", "2025-07-18", "2025-07-30", "2025-08-25", "2026-07-20", "2026-08-04"]


def test_apply_zero_days_zeroes_only_cloud_days():
    status = pd.Series(["observed", "zero_assumed", "outage"], index=pd.date_range("2025-07-01", periods=3, freq="D"))
    df = pd.DataFrame({"ist_date": status.index, "n_nh": [4.0, np.nan, np.nan], "frp_nh": [1.0, np.nan, np.nan], "other": [9, 9, 9]})
    out = apply_zero_days(df, status, ["n_nh", "frp_nh"])
    assert out["n_nh"].tolist()[:2] == [4.0, 0.0] and np.isnan(out.loc[2, "n_nh"])
    assert out["frp_nh"].tolist()[:2] == [1.0, 0.0] and out["other"].tolist() == [9, 9, 9]
    assert np.isnan(df.loc[1, "n_nh"])        # the input is not changed


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
