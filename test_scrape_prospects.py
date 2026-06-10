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
