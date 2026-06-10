import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prospect_mapper import prospect_to_form

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "prospect_data", "teams.sample.json")


def _load(pid):
    with open(FIXTURE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return next(p for p in data["teams"]["TST"]["prospects"] if p["id"] == pid)


def test_hitter_mapping():
    form = prospect_to_form(_load("sample-hitter"), "TST")
    assert form["is_pitcher"] == ""
    assert form["position"] == "SS"
    assert form["g_hit"] == "60"
    assert form["g_power"] == "55"
    assert form["g_speed"] == "60"
    assert form["g_field"] == "60"
    assert form["g_arm"] == "55"
    assert form["g_eye"] == "60"          # no eye grade -> tracks hit
    assert form["g_hit_p"] == "30"        # present grades flow to _p fields
    assert form["g_power_p"] == "35"
    assert form["fv"] == "60"
    assert form["level"] == "AA"
    assert form["name"] == "Sample Hitter"
    assert form["team"] == "TST"


def test_pitcher_mapping_best_breaking_and_offspeed():
    form = prospect_to_form(_load("sample-pitcher"), "TST")
    assert form["is_pitcher"] == "on"
    assert form["role"] == "SP"
    assert form["throws"] == "R"
    assert form["g_fb"] == "70"
    assert form["g_break"] == "60"        # max(sl 60, cb 50)
    assert form["g_off"] == "45"          # ch only
    assert form["g_command"] == "50"
    assert form["fv"] == "50"


def test_missing_grades_become_blank_strings():
    p = {"id": "x", "name": "X", "pos": "C", "is_pitcher": False,
         "grades": {"hit": 55}, "level": "A"}
    form = prospect_to_form(p, "TST")
    assert form["g_power"] == ""          # engine defaults blanks to 50
    assert form["g_eye"] == "55"
    assert form["fv"] == ""


def test_position_normalization():
    p = {"id": "x", "name": "X", "pos": "UTL", "is_pitcher": False,
         "grades": {"hit": 50}}
    assert prospect_to_form(p, "TST")["position"] == "2B"
    p["pos"] = "INF"
    assert prospect_to_form(p, "TST")["position"] == "2B"
    p["pos"] = "OF"
    assert prospect_to_form(p, "TST")["position"] == "OF"
