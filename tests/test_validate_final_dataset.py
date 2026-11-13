"""Tests for src/validate_final_dataset.py (task M2).
The validator must PASS on the real file and FAIL on deliberately broken copies of it.
Run:  python tests/test_validate_final_dataset.py   (or pytest tests/test_validate_final_dataset.py)
The real file is data/processed/final_dataset.parquet (git-ignored); the tests that need it are skipped
when it is not on this machine."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import validate_final_dataset as v  # noqa: E402

REAL = v.DEFAULT_PATH
needs_real = pytest.mark.skipif(not REAL.exists(), reason="final_dataset.parquet is not on this machine")


@pytest.fixture(scope="module")
def real():
    return v.load(REAL)


def failed(df):
    """Names of the checks that fail on df."""
    return [name for ok, name, _ in v.run_checks(df).rows if ok is False]


@needs_real
def test_real_file_passes_every_check(real):
    rep = v.run_checks(real)
    assert rep.n_fail == 0, "\n".join(rep.lines())
    assert rep.n_pass >= 25


@needs_real
def test_dropping_a_row_fails(real):
    bad = real.drop(index=real.index[1000]).reset_index(drop=True)
    names = failed(bad)
    assert any("row count" in n for n in names)
    assert any("14,136 hours" in n for n in names)


@needs_real
def test_changing_a_value_out_of_range_fails(real):
    bad = real.copy()
    bad.loc[bad.index[5000], "pm25"] = 5000.0
    assert any("inside their limits" in n for n in failed(bad))


@needs_real
def test_filling_an_empty_cell_fails_the_missing_count(real):
    bad = real.copy()
    i = bad.index[bad["pm25"].isna()][0]
    bad.loc[i, "pm25"] = 10.0
    assert any("empty cells per column" in n for n in failed(bad))


@needs_real
def test_a_duplicated_key_fails(real):
    bad = real.copy()
    bad.loc[bad.index[10], "hour_ist"] = bad.loc[bad.index[9], "hour_ist"]
    bad.loc[bad.index[10], "station_id"] = bad.loc[bad.index[9], "station_id"]
    assert any("is unique" in n for n in failed(bad))


@needs_real
def test_a_same_day_fire_column_fails(real):
    bad = real.copy()
    bad["n_nh_100km_lag0"] = bad["n_nh_100km_lag1"]
    names = failed(bad)
    assert any("70 columns" in n for n in names)
    bad2 = real.rename(columns={"n_nh_100km_lag1": "n_nh_100km_same_day"})
    assert any("lag0 or same-day fire column" in n for n in failed(bad2))


@needs_real
def test_changing_a_station_group_fails(real):
    bad = real.copy()
    sid = bad.loc[bad["group"] == "control", "station_id"].iloc[0]
    bad.loc[bad["station_id"] == sid, "group"] = "treated"
    assert any("39 treated and 15 control" in n for n in failed(bad))


@needs_real
def test_breaking_the_outage_flag_fails(real):
    bad = real.copy()
    bad.loc[bad["network_outage"], "network_outage"] = False
    names = failed(bad)
    assert any("network_outage is exactly" in n for n in names)
    assert any("928 outage hours" in n for n in names)


@needs_real
def test_applying_grap_to_a_control_station_fails(real):
    bad = real.copy()
    i = bad.index[(bad["group"] == "control") & (bad["grap_stage"] > 0)][0]
    bad.loc[i, "grap_stage_applied"] = bad.loc[i, "grap_stage"]
    assert any("grap_stage_applied" in n for n in failed(bad))


@needs_real
def test_command_line_exit_codes(real, tmp_path):
    script = ROOT / "src" / "validate_final_dataset.py"
    ok = subprocess.run([sys.executable, str(script), str(REAL)], capture_output=True, text=True)
    assert ok.returncode == 0 and "RESULT: PASS" in ok.stdout
    bad_path = tmp_path / "broken.parquet"
    real.drop(index=real.index[:1]).to_parquet(bad_path)
    bad = subprocess.run([sys.executable, str(script), str(bad_path)], capture_output=True, text=True)
    assert bad.returncode == 1 and "RESULT: FAIL" in bad.stdout
    missing = subprocess.run([sys.executable, str(script), str(tmp_path / "nope.parquet")], capture_output=True, text=True)
    assert missing.returncode == 2


def test_an_empty_or_wrong_table_fails_without_crashing():
    rep = v.run_checks(pd.DataFrame({"station_id": [1], "hour_ist": [pd.Timestamp("2025-02-19")]}))
    assert rep.n_fail > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
