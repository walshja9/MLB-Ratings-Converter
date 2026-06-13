"""Stat-parsing robustness tests (plan 007).

Covers three classes of fragility on the FanGraphs/BBRef data path:
  1. NaN -> int() crash in the count-column casts.
  2. KeyError on missing sort columns (PA / IP).
  3. (control-flow logging is verified only by "no test asserts on stderr".)

The pitcher pull's ``safe_int`` is a function-local helper (not importable at
module scope; promoting it is out of scope per plan 007 / overlaps 009). We test:
  - the ``safe_int`` *semantics* against the exact spec the plan defines, and
  - the real, importable selection guards (``find_pitcher_fg`` / ``find_player``)
    with frames that lack the sort column,
  - that a NaN-bearing pitcher row parses cleanly through ``pull_season_pitching``
    by stubbing the network so only the parse path runs.
"""

import math

import pandas as pd

import generate_card
from generate_card import find_pitcher_fg, find_player


# ---- safe_int semantics (spec replicated; helper is function-local) ----

def _safe_int(val, default=0):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def test_safe_int_nan_returns_default():
    assert _safe_int(float("nan")) == 0


def test_safe_int_none_returns_default():
    assert _safe_int(None) == 0


def test_safe_int_str_parses():
    assert _safe_int("12") == 12


def test_safe_int_float_truncates():
    assert _safe_int(5.0) == 5


def test_safe_int_garbage_returns_default():
    assert _safe_int("not-a-number") == 0


# ---- missing sort-column guards do not raise (KeyError-safe) ----

def test_find_pitcher_fg_without_ip_column_does_not_raise():
    df = pd.DataFrame([{"Name": "Joe Arm", "W": 3}, {"Name": "Joe Arm", "W": 5}])
    row = find_pitcher_fg(df, "Joe Arm")  # no "IP" column -> falls back to first row
    assert row is not None
    assert row["W"] == 3


def test_find_player_without_pa_column_does_not_raise():
    df = pd.DataFrame([{"Name": "Joe Bat", "HR": 1}, {"Name": "Joe Bat", "HR": 9}])
    row = find_player(df, "Joe Bat")  # no "PA" column -> falls back to first row
    assert row is not None
    assert row["HR"] == 1


# ---- NaN-bearing pitcher row parses without raising and yields int 0s ----

def test_pitcher_row_with_nan_counts_parses_cleanly(monkeypatch):
    nan = float("nan")
    row = pd.Series({
        "Name": "NaN Arm", "W": nan, "L": nan, "G": nan, "GS": nan, "SV": nan,
        "ERA": nan, "FIP": nan, "IP": nan, "K/9": nan, "BB/9": nan,
        "HR/9": nan, "H/9": nan, "K%": nan, "BB%": nan, "WHIP": nan,
        "WAR": nan, "LOB%": nan, "FBv": nan, "Team": "TST",
    })
    # Stub the network so only the parse path runs.
    monkeypatch.setattr(generate_card, "pitching_stats", lambda y: pd.DataFrame())
    monkeypatch.setattr(generate_card, "find_pitcher_fg", lambda df, name: row)

    result = generate_card.pull_season_pitching("NaN Arm", 2024)
    assert result is not None
    # NaN count columns coerce to integer 0, no ValueError raised.
    for k in ("W", "L", "G", "GS", "SV"):
        assert result[k] == 0
        assert isinstance(result[k], int)
    # NaN FBv -> None (not a crash).
    assert result["FB_velo"] is None
