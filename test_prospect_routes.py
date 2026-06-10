import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prospect_store
from app import app

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "prospect_data", "teams.sample.json")


def _point_at_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(prospect_store, "_TEAMS_PATH", FIXTURE)
    monkeypatch.setattr(prospect_store, "_PROGRESS_PATH", str(tmp_path / "progress.json"))
    prospect_store.invalidate_cache()


def test_index_lists_teams_with_done_counts(tmp_path, monkeypatch):
    _point_at_fixture(tmp_path, monkeypatch)
    prospect_store.set_done("TST", "sample-hitter", True)
    r = app.test_client().get("/prospects")
    assert r.status_code == 200
    teams = r.get_json()["teams"]
    assert teams[0]["abbrev"] == "TST"
    assert teams[0]["count"] == 3
    assert teams[0]["done"] == 1


def test_index_missing_data_404(tmp_path, monkeypatch):
    monkeypatch.setattr(prospect_store, "_TEAMS_PATH", str(tmp_path / "nope.json"))
    prospect_store.invalidate_cache()
    r = app.test_client().get("/prospects")
    assert r.status_code == 404
    assert "scrape_prospects" in r.get_json()["error"]


def test_team_list_has_ovr_and_flags(tmp_path, monkeypatch):
    _point_at_fixture(tmp_path, monkeypatch)
    r = app.test_client().get("/prospects/TST")
    assert r.status_code == 200
    rows = r.get_json()["prospects"]
    assert len(rows) == 3
    hitter = rows[0]
    assert hitter["id"] == "sample-hitter"
    assert 40 <= hitter["ovr"] <= 99
    assert hitter["ovr_now"] is not None        # present grades -> Now OVR
    sparse = rows[2]
    assert sparse["grades_incomplete"] is True


def test_team_unknown_404(tmp_path, monkeypatch):
    _point_at_fixture(tmp_path, monkeypatch)
    assert app.test_client().get("/prospects/NOPE").status_code == 404


def test_prospect_card_shape(tmp_path, monkeypatch):
    _point_at_fixture(tmp_path, monkeypatch)
    r = app.test_client().get("/prospects/TST/sample-pitcher")
    assert r.status_code == 200
    card = r.get_json()
    assert card["type"] == "pitcher"
    assert card["scouting"] is True
    assert card["prospect"]["rank"] == 2
    assert card["prospect"]["bats"] == "R"


def test_card_displays_now_when_present_grades_exist(tmp_path, monkeypatch):
    # sample-hitter has grades_present -> displayed card = NOW (attributes +
    # overall from present grades), potential kept as ovr_future
    _point_at_fixture(tmp_path, monkeypatch)
    card = app.test_client().get("/prospects/TST/sample-hitter").get_json()
    assert card["display"] == "now"
    assert card["ovr"] == card["ovr_now"]
    assert card["ovr_future"] > card["ovr"]          # 30/35 present << 60/55 future
    # attributes must be the present-grade ones: a 30-grade hit reads far below
    # the future card's 60-grade hit
    assert card["ratings"]["contact_right"] < 60


def test_card_displays_potential_when_no_present_grades(tmp_path, monkeypatch):
    # sample-pitcher has no grades_present -> future card, flagged as potential
    _point_at_fixture(tmp_path, monkeypatch)
    card = app.test_client().get("/prospects/TST/sample-pitcher").get_json()
    assert card["display"] == "potential"
    assert "ovr_now" not in card


def test_done_toggle(tmp_path, monkeypatch):
    _point_at_fixture(tmp_path, monkeypatch)
    c = app.test_client()
    r = c.post("/prospects/done", data={"team": "TST", "id": "sample-hitter", "done": "1"})
    assert r.status_code == 200
    assert prospect_store.load_progress()["TST"]["sample-hitter"] is True
    c.post("/prospects/done", data={"team": "TST", "id": "sample-hitter", "done": "0"})
    assert prospect_store.load_progress() == {}
