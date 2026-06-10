import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prospect_store


def _setup(tmp_path, monkeypatch, teams=None):
    monkeypatch.setattr(prospect_store, "_TEAMS_PATH", str(tmp_path / "teams.json"))
    monkeypatch.setattr(prospect_store, "_PROGRESS_PATH", str(tmp_path / "progress.json"))
    prospect_store.invalidate_cache()
    if teams is not None:
        with open(tmp_path / "teams.json", "w", encoding="utf-8") as f:
            json.dump(teams, f)


def test_load_teams_missing_returns_none(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert prospect_store.load_teams() is None


def test_load_teams_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"season": 2026, "teams": {"TST": {"name": "T", "prospects": []}}})
    data = prospect_store.load_teams()
    assert data["season"] == 2026
    assert "TST" in data["teams"]


def test_progress_toggle_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert prospect_store.load_progress() == {}
    prospect_store.set_done("TST", "sample-hitter", True)
    assert prospect_store.load_progress()["TST"]["sample-hitter"] is True
    prospect_store.set_done("TST", "sample-hitter", False)
    assert "sample-hitter" not in prospect_store.load_progress().get("TST", {})
