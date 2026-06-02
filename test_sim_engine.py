"""Tests for the Layer B sim engine."""

import random
import sim_engine as S


def _lineup(rating_dict):
    return [dict(rating_dict, name=f"b{i}") for i in range(9)]


ELITE_BAT = {"contact_left": 88, "contact_right": 88, "power_left": 85,
             "power_right": 85, "vision": 85, "discipline": 82}
POOR_BAT = {"contact_left": 45, "contact_right": 45, "power_left": 40,
            "power_right": 40, "vision": 48, "discipline": 45}
ACE_ARM = {"k_per_9_left": 90, "k_per_9_right": 90, "h_per_9_left": 88,
           "h_per_9_right": 88, "control": 88, "hr_per_9": 88}


# ---- PA model ----

def test_pa_probs_sum_to_one():
    p = S.pa_probabilities(S.AVG_BATTER, S.AVG_PITCHER)
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert all(0 <= v <= 1 for v in p.values())


def test_avg_matchup_near_league_rates():
    p = S.pa_probabilities(S.AVG_BATTER, S.AVG_PITCHER)
    assert abs(p["K"] - S.LG["K"]) < 0.02
    assert abs(p["BB"] - S.LG["BB"]) < 0.02


def test_elite_batter_beats_poor():
    def obp(b):
        d = S.pa_probabilities(b, S.AVG_PITCHER)
        return d["1B"] + d["2B"] + d["3B"] + d["HR"] + d["BB"] + d["HBP"]
    assert obp(ELITE_BAT) > obp(S.AVG_BATTER) > obp(POOR_BAT)
    assert S.pa_probabilities(ELITE_BAT, S.AVG_PITCHER)["HR"] > S.pa_probabilities(POOR_BAT, S.AVG_PITCHER)["HR"]


def test_ace_pitcher_suppresses():
    # vs an average batter, an ace allows fewer baserunners than an average arm.
    def on_base(pit):
        d = S.pa_probabilities(S.AVG_BATTER, pit)
        return d["1B"] + d["2B"] + d["3B"] + d["HR"] + d["BB"]
    assert on_base(ACE_ARM) < on_base(S.AVG_PITCHER)


# ---- Game ----

def test_game_box_is_valid():
    rng = random.Random(3)
    t = S.make_team("T", _lineup(S.AVG_BATTER), dict(S.AVG_PITCHER))
    box = S.simulate_game(t, t, rng)
    assert box["away"]["runs"] >= 0 and box["home"]["runs"] >= 0
    assert box["away"]["runs"] != box["home"]["runs"]      # no ties
    assert box["innings"] >= 9
    assert box["winner"] in ("T",)


def test_seed_is_deterministic():
    t = S.make_team("T", _lineup(S.AVG_BATTER), dict(S.AVG_PITCHER))
    a = S.simulate_game(t, t, random.Random(42))
    b = S.simulate_game(t, t, random.Random(42))
    assert a["away"]["runs"] == b["away"]["runs"] and a["home"]["runs"] == b["home"]["runs"]


def test_average_runs_per_game_realistic():
    rng = random.Random(2)
    t = S.make_team("T", _lineup(S.AVG_BATTER), dict(S.AVG_PITCHER))
    games = 600
    total = sum(sum(S.simulate_game(t, t, rng)[s]["runs"] for s in ("away", "home")) for _ in range(games))
    rpg = total / (2 * games)
    assert 3.6 < rpg < 5.4, f"runs/game {rpg:.2f} outside realistic band"


def test_better_team_wins_more():
    rng = random.Random(11)
    elite = S.make_team("Elite", _lineup(ELITE_BAT), dict(ACE_ARM))
    poor = S.make_team("Poor", _lineup(POOR_BAT), dict(S.AVG_PITCHER))
    wins = sum(1 for _ in range(400) if S.simulate_game(poor, elite, rng)["winner"] == "Elite")
    assert wins / 400 > 0.85
