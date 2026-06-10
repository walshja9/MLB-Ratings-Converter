import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_prospects import parse_pipeline_payload, slugify

FIXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "prospect_data", "fixtures")


def _fixture():
    name = [f for f in os.listdir(FIXDIR) if f.startswith("pipeline_")][0]
    with open(os.path.join(FIXDIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_pipeline_returns_30_canonical_prospects():
    prospects = parse_pipeline_payload(_fixture()["json"])
    assert len(prospects) == 30
    ranks = [p["rank"] for p in prospects]
    assert ranks == sorted(ranks) and ranks[0] == 1
    for p in prospects:
        assert p["id"] and p["name"] and p["pos"]
        assert isinstance(p["is_pitcher"], bool)
        assert isinstance(p["grades"], dict) and p["grades"]
        if p["is_pitcher"]:
            assert "control" in p["grades"]
            assert p["role"] in ("SP", "RP")
        else:
            assert "hit" in p["grades"]


def test_slugify():
    assert slugify("Jesús Madé") == "jesus-made"
    assert slugify("George Lombard Jr.") == "george-lombard-jr"


# ---- FanGraphs Board parsing ----

import csv

from scrape_prospects import parse_fg_row, parse_grade_pair


def _fg_rows():
    path = os.path.join(FIXDIR, "fg_board_sample.csv")
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_parse_grade_pair():
    assert parse_grade_pair("30/60") == (30, 60)
    assert parse_grade_pair("55") == (None, 55)
    assert parse_grade_pair("") == (None, None)
    assert parse_grade_pair(None) == (None, None)


def test_parse_fg_hitter():
    r = parse_fg_row(_fg_rows()[0])
    assert r["org"] == "TST" and r["fv"] == 60 and not r["is_pitcher"]
    assert r["future"]["hit"] == 60 and r["present"]["hit"] == 30
    assert r["future"]["run"] == 60
    assert r["level"] == "AA"


def test_parse_fg_reliever_role():
    r = parse_fg_row(_fg_rows()[2])
    assert r["is_pitcher"] and r["role"] == "RP"
    assert r["future"]["fb"] == 70


# ---- Merge + validation ----

from scrape_prospects import merge_fg, normalize_match_name, validate_teams


def test_normalize_match_name():
    assert normalize_match_name("Jesús Madé") == normalize_match_name("Jesus Made")
    assert normalize_match_name("George Lombard Jr.") == normalize_match_name("george lombard")


def test_merge_fg_layers_fv_and_grades():
    teams = {"TST": {"name": "T", "prospects": [
        {"id": "a", "name": "Sample Hitter", "is_pitcher": False,
         "grades": {"hit": 55, "power": 50, "run": 55, "arm": 50, "field": 55, "overall": 55},
         "fv": 55, "fv_source": "pipeline"},
    ]}}
    fg = [{"name": "Sample Hitter", "org": "TST", "fv": 60, "is_pitcher": False,
           "age": 20.4, "level": "AA",
           "present": {"hit": 30}, "future": {"hit": 60, "power": 55, "run": 60}}]
    unmatched = merge_fg(teams, fg, aliases={})
    p = teams["TST"]["prospects"][0]
    assert p["fv"] == 60 and p["fv_source"] == "fangraphs"
    assert p["grades"]["hit"] == 60          # FG future grades override Pipeline
    assert p["grades"]["arm"] == 50          # Pipeline kept where FG has no grade
    assert p["grades_present"] == {"hit": 30}
    assert p["age"] == 20.4 and p["level"] == "AA"
    assert unmatched == []


def test_merge_fg_unmatched_reported_and_alias_applied():
    teams = {"TST": {"name": "T", "prospects": [
        {"id": "a", "name": "Bobby Smith", "is_pitcher": False,
         "grades": {"hit": 50}, "fv": 50, "fv_source": "pipeline"}]}}
    fg = [{"name": "Robert Smith", "org": "TST", "fv": 55, "is_pitcher": False,
           "present": {}, "future": {}}]
    unmatched = merge_fg(teams, fg, aliases={})
    assert unmatched and unmatched[0]["name"] == "Robert Smith"
    unmatched = merge_fg(teams, fg, aliases={"Robert Smith": "Bobby Smith"})
    assert unmatched == []
    assert teams["TST"]["prospects"][0]["fv"] == 55


def test_validate_flags_short_teams_and_missing_grades():
    teams = {"TST": {"name": "T", "prospects": [
        {"id": "a", "name": "A", "is_pitcher": False, "grades": {"hit": 50}}]}}
    warnings = validate_teams(teams)
    assert any("TST" in w and "1" in w for w in warnings)       # short team
    p = teams["TST"]["prospects"][0]
    assert p["grades_incomplete"] is True
    assert p["grades"]["power"] == 50                            # filled default
