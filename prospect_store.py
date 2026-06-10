"""Load prospect_data/teams.json and persist done-progress. The only module
that touches prospect files on disk."""

import json
import os
import threading

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prospect_data")
_TEAMS_PATH = os.path.join(_DIR, "teams.json")
_PROGRESS_PATH = os.path.join(_DIR, "progress.json")
_lock = threading.Lock()
_teams_cache = None


def invalidate_cache():
    global _teams_cache
    _teams_cache = None


def load_teams():
    """Parsed teams.json (cached), or None when the scrape hasn't run."""
    global _teams_cache
    if _teams_cache is None:
        try:
            with open(_TEAMS_PATH, "r", encoding="utf-8") as f:
                _teams_cache = json.load(f)
        except (FileNotFoundError, ValueError):
            return None
    return _teams_cache


def load_progress():
    try:
        with open(_PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def set_done(team, pid, done):
    """Toggle a prospect's done flag. Read-modify-write under a lock; done
    entries are stored as True, undone entries removed (keeps the file small)."""
    with _lock:
        progress = load_progress()
        team_map = progress.setdefault(team, {})
        if done:
            team_map[pid] = True
        else:
            team_map.pop(pid, None)
            if not team_map:
                progress.pop(team, None)
        os.makedirs(_DIR, exist_ok=True)
        with open(_PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=1)
    return progress
