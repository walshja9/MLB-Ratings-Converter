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
