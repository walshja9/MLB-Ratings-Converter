import pytest

from generate_card import calculate_ratings, clamp, POSITION_DEFAULTS


def _make_data(year=2010, position="CF", sprint_speed=None, fg_spd=None, fielding=None,
               pa=520, sb=7, cs=7, triples=6):
    batting = {
        "G": 130,
        "PA": pa,
        "BA": 0.270,
        "OBP": 0.340,
        "SLG": 0.420,
        "ISO": 0.150,
        "HR": 15,
        "3B": triples,
        "SB": sb,
        "CS": cs,
        "BB_pct": 8.0,
        "K_pct": 20.0,
        "wOBA": 0.340,
        "WAR": 2.0,
        "fg_spd": fg_spd,
        "bsr": None,
        "team": "TST",
    }
    return {
        "name": "Test Player",
        "year": year,
        "batting": batting,
        "career_avg": None,
        "career_yearly": {},
        "sprint_speed": sprint_speed,
        "fielding_oaa": fielding or {},
        "position": position,
        "splits": {},
        "avg_ev": None,
    }


def test_statcast_speed_path_unchanged():
    data = _make_data(year=2025, position="CF", sprint_speed=30.0, sb=3, cs=1, triples=1)
    ratings = calculate_ratings(data, mode="season")
    # Current Statcast speed formula (6/4 refit): 15.02*sprint + 0.10*SB/162 - 356.5.
    # SB/162 derived from the same inputs the model uses (G=130, SB=3).
    games = max(data["batting"]["G"], 1)
    sb_per_162 = min(data["batting"]["SB"] / games * 162.0, 60.0)
    assert ratings["speed"] == clamp(max(15.02 * 30.0 + 0.10 * sb_per_162 - 356.5, 15))


def test_pre_tracking_speed_uses_more_than_sb_count():
    data = _make_data(year=2007, position="CF", sprint_speed=None, fg_spd=None, sb=7, cs=7, triples=6)
    ratings = calculate_ratings(data, mode="season")
    # Old SB-only fallback would have landed at 39 here; the new proxy should
    # recognize a mobile CF with lots of attempts/triples as clearly above that.
    assert ratings["speed"] >= 75


def test_pre_tracking_speed_keeps_slow_corner_bats_out_of_cf_band():
    data = _make_data(year=2007, position="LF", sprint_speed=None, fg_spd=None, sb=0, cs=0, triples=0, pa=550)
    ratings = calculate_ratings(data, mode="season")
    assert ratings["speed"] == 38


def test_rarm_and_errr_paths_still_win():
    year = 2012
    defaults = POSITION_DEFAULTS["RF"]
    fielding = {
        f"rarm_{year}": 4,
        f"errr_{year}": 2,
        f"inn_{year}": 1000,
        f"ass_{year}": 20,
        f"err_{year}": 6,
        f"ch_{year}": 280,
    }
    data = _make_data(year=year, position="RF", fielding=fielding)
    ratings = calculate_ratings(data, mode="season")
    assert ratings["arm_strength"] == clamp(3.9 * 4 + defaults["arm_str"])
    assert ratings["arm_accuracy"] == clamp(3.0 * 2 + defaults["arm_acc"])


def test_bbref_outfield_arm_proxies_raise_arm_ratings():
    year = 2007
    defaults = POSITION_DEFAULTS["RF"]
    fielding = {
        f"ass_{year}": 15,
        f"err_{year}": 2,
        f"ch_{year}": 250,
        f"inn_{year}": 1100,
    }
    data = _make_data(year=year, position="RF", fielding=fielding, sb=5, cs=2, triples=3)
    ratings = calculate_ratings(data, mode="season")
    assert ratings["arm_strength"] > defaults["arm_str"]
    assert ratings["arm_accuracy"] > defaults["arm_acc"]
