"""Translate canonical prospect entries (prospect_data/teams.json) into the
form dict consumed by app._scouting_card -> the existing scouting engine.
Pure functions only - no I/O."""

_BREAK_KEYS = ("cb", "sl", "st", "sv", "kc", "cs", "sc")
_OFF_KEYS = ("ch", "fs", "sp")
_POS_NORMALIZE = {"UTL": "2B", "INF": "2B", "UT": "2B", "IF": "2B"}


def _g(grades, key):
    v = grades.get(key)
    return str(v) if v is not None else ""


def _best(grades, keys):
    vals = [grades[k] for k in keys if grades.get(k) is not None]
    return str(max(vals)) if vals else ""


def prospect_to_form(p, team_abbrev, year=2026):
    """One prospect dict -> the flat form dict _scouting_card() accepts.
    Missing grades map to blank strings (the engine defaults those to 50)."""
    grades = p.get("grades") or {}
    present = p.get("grades_present") or {}
    form = {
        "name": p.get("name") or "Prospect",
        "team": team_abbrev,
        "year": str(year),
        "level": p.get("level") or "MLB",
        "fv": str(p["fv"]) if p.get("fv") is not None else "",
        "age": str(p["age"]) if p.get("age") is not None else "",
    }
    if p.get("is_pitcher"):
        form["is_pitcher"] = "on"
        form["role"] = p.get("role") or "SP"
        form["throws"] = p.get("throws") or "R"
        form["g_fb"] = _g(grades, "fb")
        form["g_break"] = _best(grades, _BREAK_KEYS)
        form["g_off"] = _best(grades, _OFF_KEYS)
        form["g_command"] = _g(grades, "control")
        form["g_fb_p"] = _g(present, "fb")
        form["g_break_p"] = _best(present, _BREAK_KEYS)
        form["g_off_p"] = _best(present, _OFF_KEYS)
        form["g_command_p"] = _g(present, "control")
    else:
        raw_pos = (p.get("pos") or "OF").upper()
        form["is_pitcher"] = ""
        form["position"] = _POS_NORMALIZE.get(raw_pos, raw_pos)
        form["g_hit"] = _g(grades, "hit")
        form["g_power"] = _g(grades, "power")
        form["g_eye"] = _g(grades, "eye") or _g(grades, "hit")
        form["g_speed"] = _g(grades, "run")
        form["g_field"] = _g(grades, "field")
        form["g_arm"] = _g(grades, "arm")
        form["g_hit_p"] = _g(present, "hit")
        form["g_power_p"] = _g(present, "power")
        form["g_eye_p"] = _g(present, "eye") or _g(present, "hit")
        form["g_speed_p"] = _g(present, "run")
        form["g_field_p"] = _g(present, "field")
        form["g_arm_p"] = _g(present, "arm")
    return form
