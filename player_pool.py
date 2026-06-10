"""Player pool — persistence for cards created via any path (real / custom /
scouting), so they survive restarts and can feed the simulation.

Design notes:
- Storage is a single JSON file (`player_pool.json`), written atomically. Matches
  the project's existing file-based data; fine for a hand-built pool. Migrate to
  SQLite if/when a full season needs queries.
- Each entry stores the RAW INPUTS (`form`) plus a cached computed `card`. The form
  lets custom/scouting players be RE-DERIVED on load, so saved players automatically
  benefit from future calibration tweaks; the cached card gives instant display.
- IDENTITY (name/team) is decoupled from the stat SOURCE. A real player's ratings
  can be saved under a fictional name/team — that keeps the *game* license-clean
  while the *tool* is free to convert real MLB stats.
"""

import json
import os
import time
import uuid

_POOL_PATH = os.path.join(os.path.dirname(__file__), "player_pool.json")


def _load():
    if not os.path.exists(_POOL_PATH):
        return []
    try:
        with open(_POOL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(entries):
    """Write the whole pool atomically (tmp + os.replace) so a crash mid-write
    can never corrupt the existing file."""
    tmp = _POOL_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, _POOL_PATH)


def list_players():
    """Lightweight summaries for the roster view, sorted by OVR desc."""
    out = []
    for e in _load():
        card = e.get("card", {})
        out.append({
            "id": e.get("id"),
            "name": e.get("name"),
            "team": e.get("team"),
            "position": card.get("position"),
            "type": card.get("type"),
            "ovr": card.get("ovr"),
            "year": e.get("year"),
            "source": e.get("source"),
            "saved_at": e.get("saved_at"),
        })
    out.sort(key=lambda x: (x.get("ovr") or 0), reverse=True)
    return out


def get_player(pid):
    for e in _load():
        if e.get("id") == pid:
            return e
    return None


def save_player(name, team, source, form, card):
    """Append a new pool entry. Returns the stored entry (with its new id)."""
    entries = _load()
    entry = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "team": team,
        "source": source,                 # "real" | "custom" | "scouting"
        "form": form,                      # raw inputs -> re-derivable
        "card": card,                      # cached computed card
        "year": card.get("year"),
        "saved_at": int(time.time()),
    }
    entries.append(entry)
    _save_all(entries)
    return entry


def delete_player(pid):
    entries = _load()
    remaining = [e for e in entries if e.get("id") != pid]
    if len(remaining) == len(entries):
        return False
    _save_all(remaining)
    return True
