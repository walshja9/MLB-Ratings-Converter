"""Regression tests for reliever stamina (plan 002).

Before the fix, the RP stamina branch only fired when ``GS == 0``. An opener or
swingman (e.g. 5 starts in 50 games) is classified ``RP`` by the role detector
(``GS > G*0.4`` -> SP) yet fell through to the STARTER stamina formula
(~78), instead of the ~26 a bullpen arm should get. The fix routes every ``RP``
to the reliever baseline regardless of a handful of starts.

Modeled on the pitcher-data construction in test_custom_card.py.
"""

from generate_card import calculate_pitcher_ratings


def _make_pitcher(gs, g, role):
    """Minimal pitcher data dict shaped as pull_all_data would produce."""
    return {
        "name": "Test Arm", "year": 2024, "is_pitcher": True,
        "pitching": {
            "W": 5, "L": 4, "ERA": 3.50, "FIP": 3.60, "IP": 80.0,
            "G": g, "GS": gs, "SV": 0,
            "K_per_9": 9.5, "BB_per_9": 2.8, "HR_per_9": 0.95, "H_per_9": 7.5,
            "K_pct": 26.0, "BB_pct": 7.0, "WHIP": 1.15, "WAR": 1.5,
            "LOB_pct": 75.0, "FB_velo": 95.0, "team": "TST",
        },
        "career_avg": None, "career_yearly": {},
        "statcast": {"throws": "R"},
        "role": role, "sprint_speed": None,
    }


def _role_for(gs, g):
    """Mirror the role classifier in generate_card.py (GS > G*0.4 -> SP)."""
    return "SP" if gs > g * 0.4 else "RP"


def test_opener_gets_reliever_stamina():
    # The bug case: 5 starts in 50 games -> classified RP, must get RP stamina,
    # NOT the ~78 the starter formula would have produced.
    assert _role_for(5, 50) == "RP"
    r = calculate_pitcher_ratings(_make_pitcher(gs=5, g=50, role="RP"), "season")
    assert r["stamina"] < 40


def test_pure_reliever_gets_reliever_stamina():
    assert _role_for(0, 65) == "RP"
    r = calculate_pitcher_ratings(_make_pitcher(gs=0, g=65, role="RP"), "season")
    assert r["stamina"] < 40


def test_starter_unaffected():
    assert _role_for(30, 32) == "SP"
    r = calculate_pitcher_ratings(_make_pitcher(gs=30, g=32, role="SP"), "season")
    assert r["stamina"] > 70
