"""Tests for src/build_grap_hourly.py. Run:  python -m pytest tests/test_grap_hourly.py -q"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from build_grap_hourly import build_hourly, load_gaps, load_orders, prepare_orders, stage_changes  # noqa: E402

NO_GAPS = pd.DataFrame({"start_date": pd.to_datetime([]), "end_date": pd.to_datetime([]), "kind": []})


def orders(rows):
    """rows: (date, action, stage, time, pib_time); a None time means the order states none."""
    df = pd.DataFrame(rows, columns=["order_date", "action", "stage", "effective_time_ist", "pib_posted_ist"])
    df["schedule_version"] = "v1"
    return prepare_orders(df, "12:00")


def stage_at(hourly, ts):
    return int(hourly.loc[hourly["ts_ist"] == pd.Timestamp(ts), "grap_stage"].iloc[0])


def test_revoke_sets_stage_to_k_minus_one():
    o = orders([("2025-01-01", "invoke", 3, "08:00", None), ("2025-01-03", "revoke", 3, "08:00", None)])
    h, _, _ = build_hourly(o, NO_GAPS, "2025-01-02", "2025-01-04")
    assert stage_at(h, "2025-01-02 12:00") == 3
    assert stage_at(h, "2025-01-04 00:00") == 2          # Stage III revoked: Stage I and II stay


def test_same_day_stage_three_then_four_with_meeting_times():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None),
                ("2025-01-05", "invoke", 3, "10:00", None),
                ("2025-01-05", "invoke", 4, "18:30", None)])
    h, _, _ = build_hourly(o, NO_GAPS, "2025-01-02", "2025-01-06")
    assert stage_at(h, "2025-01-05 09:00") == 2
    assert stage_at(h, "2025-01-05 10:00") == 3          # a row starting exactly at the change takes the new stage
    assert stage_at(h, "2025-01-05 17:00") == 3
    assert stage_at(h, "2025-01-05 18:00") == 3          # the hour containing 18:30 keeps the stage at its start
    assert stage_at(h, "2025-01-05 19:00") == 4


def test_pib_posting_time_used_when_order_has_no_time():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None), ("2025-01-05", "revoke", 2, None, "18:22")])
    h, _, _ = build_hourly(o, NO_GAPS, "2025-01-02", "2025-01-06")
    assert stage_at(h, "2025-01-05 18:00") == 2
    assert stage_at(h, "2025-01-05 19:00") == 1


def test_assumed_noon_used_when_no_time_at_all():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None), ("2025-01-05", "revoke", 2, None, None)])
    h, _, _ = build_hourly(o, NO_GAPS, "2025-01-02", "2025-01-06")
    assert stage_at(h, "2025-01-05 11:00") == 2
    assert stage_at(h, "2025-01-05 12:00") == 1


def test_uncertain_only_on_dates_without_an_order_time():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None),
                ("2025-01-03", "revoke", 2, None, "18:22"),
                ("2025-01-05", "invoke", 3, "10:00", None)])
    h, _, _ = build_hourly(o, NO_GAPS, "2025-01-02", "2025-01-06")
    day = h["ts_ist"].dt.normalize()
    assert h.loc[day == pd.Timestamp("2025-01-03"), "uncertain"].all()       # PIB time only
    assert not h.loc[day == pd.Timestamp("2025-01-05"), "uncertain"].any()   # meeting time stated
    assert not h.loc[day == pd.Timestamp("2025-01-02"), "uncertain"].any()


def test_gap_rows_are_uncertain_and_inferred_rows_are_not():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None)])
    gaps = pd.DataFrame({"start_date": pd.to_datetime(["2025-01-03", "2025-01-05"]),
                         "end_date": pd.to_datetime(["2025-01-03", "2025-01-05"]),
                         "kind": ["missing_order", "inferred"]})
    h, _, _ = build_hourly(o, gaps, "2025-01-02", "2025-01-06")
    day = h["ts_ist"].dt.normalize()
    missing = h[day == pd.Timestamp("2025-01-03")]
    inferred = h[day == pd.Timestamp("2025-01-05")]
    assert missing["uncertain"].all() and (missing["uncertain_reason"] == "known gap in orders").all()
    assert not missing["inferred"].any()
    assert inferred["inferred"].all() and not inferred["uncertain"].any()
    assert not h.loc[day == pd.Timestamp("2025-01-02"), ["uncertain", "inferred"]].any().any()


def test_revoking_a_stage_that_was_not_in_force_gives_a_warning():
    o = orders([("2025-01-01", "invoke", 2, "08:00", None), ("2025-01-02", "revoke", 3, "08:00", None)])
    _, warnings = stage_changes(o)
    assert len(warnings) == 1 and "revokes Stage-3" in warnings[0]


def test_schedule_row_changes_version_but_not_stage():
    df = pd.DataFrame({"order_date": ["2025-01-01", "2025-01-03"], "action": ["invoke", "schedule"],
                       "stage": [2, None], "effective_time_ist": ["08:00", "10:00"],
                       "pib_posted_ist": [None, None], "schedule_version": ["old", "new"]})
    h, _, _ = build_hourly(prepare_orders(df, "12:00"), NO_GAPS, "2025-01-02", "2025-01-04")
    before = h[h["ts_ist"] == pd.Timestamp("2025-01-03 09:00")].iloc[0]
    after = h[h["ts_ist"] == pd.Timestamp("2025-01-03 10:00")].iloc[0]
    assert (before["schedule_version"], before["grap_stage"]) == ("old", 2)
    assert (after["schedule_version"], after["grap_stage"]) == ("new", 2)


def test_window_before_first_order_is_rejected():
    o = orders([("2025-01-05", "invoke", 1, "08:00", None)])
    with pytest.raises(ValueError):
        build_hourly(o, NO_GAPS, "2025-01-01", "2025-01-06")


def test_real_orders_build_the_full_study_window():
    o = load_orders("12:00")
    assert o["order_date"].is_monotonic_increasing
    assert set(o["action"]) <= {"invoke", "revoke", "schedule"}
    assert o.loc[o["action"] != "schedule", "stage"].between(1, 4).all()
    h, _, _ = build_hourly(o, load_gaps(), "2025-02-19", "2026-09-30")
    assert len(h) == 589 * 24 == 14136
    assert h["ts_ist"].is_unique and h["grap_stage"].between(0, 4).all()
    assert int(h.loc[0, "grap_stage"]) == 2              # the window opens at Stage II (PIB, 24 Feb 2025)
    assert int(h["grap_stage"].iloc[-1]) == 0            # last order in the window is the 29 May 2026 revocation
