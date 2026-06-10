"""
MLB The Show 26 - Player Card Generator (Web App)
Local Flask app that generates Show-style rating cards from real MLB stats.
"""

import sys
import os

# Optional: if you keep your pybaseball venv in a sibling project, point at it
# via the MLB_SHOW_VENV_SITE env var. Otherwise we use the active interpreter.
_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

import warnings
warnings.filterwarnings("ignore")

from flask import Flask, render_template, request, jsonify, make_response

# Import our card generator logic
sys.path.insert(0, os.path.dirname(__file__))
from generate_card import (
    pull_all_data, pull_all_pitcher_data,
    calculate_ratings, calculate_overalls,
    calculate_pitcher_ratings, calculate_pitcher_overalls,
    detect_player_type, estimate_ovr_hitter, estimate_ovr_pitcher,
    build_custom_data, scouting_to_stats, scouting_to_pitcher_stats,
    stat_blend_weight,
)
import player_pool
import prospect_store
from prospect_mapper import prospect_to_form

app = Flask(__name__)

# Cache player names for autocomplete
_player_cache = {}  # {year: [names]}


def load_player_names(year=2025):
    """Load all player names from BBRef for autocomplete."""
    if _player_cache.get(year):
        return _player_cache[year]

    print(f"  Loading player names for {year}...")
    from bbref_scraper import bbref_batting_df, bbref_pitching_df

    names = set()
    try:
        bat = bbref_batting_df(year)
        names.update(bat["Name"].dropna().tolist())
    except Exception as e:
        print(f"    bat load failed: {e}")
    try:
        pit = bbref_pitching_df(year)
        names.update(pit["Name"].dropna().tolist())
    except Exception as e:
        print(f"    pit load failed: {e}")

    sorted_names = sorted(names)
    _player_cache[year] = sorted_names
    print(f"  Loaded {len(sorted_names)} player names for {year}.")
    return sorted_names


def assemble_card(data, is_pitcher, name, year, position=None, mode="season", rating_overrides=None):
    """Run ratings + overalls on a prepared `data` dict and shape the card JSON.

    Shared by the real-player path (data from pull_all_*) and the custom path
    (data from build_custom_data) so both return an identical structure.
    rating_overrides (scouting mode) lets us set attributes the stat engine
    can't infer from a synthetic line — e.g. projected durability and arm,
    derived from scouting grades."""
    if is_pitcher:
        ratings = calculate_pitcher_ratings(data, mode=mode)
        if rating_overrides:
            ratings.update(rating_overrides)
        overalls = calculate_pitcher_overalls(ratings)
        ovr = estimate_ovr_pitcher(ratings, overalls)
        sc = data.get("statcast", {})
        return {
            "type": "pitcher",
            "name": name,
            "year": year,
            "team": data["pitching"].get("team", ""),
            "position": ratings.get("role", "SP"),
            "ovr": ovr,
            "ratings": ratings,
            "overalls": overalls,
            "arsenal": sc.get("arsenal", []),
            "arsenal_estimated": sc.get("arsenal_estimated", False),
            "throws": sc.get("throws", "R"),
        }
    ratings = calculate_ratings(data, position, mode=mode)
    if rating_overrides:
        ratings.update(rating_overrides)
    overalls = calculate_overalls(ratings)
    ovr = estimate_ovr_hitter(ratings, overalls)
    return {
        "type": "hitter",
        "name": name,
        "year": year,
        "team": data["batting"].get("team", ""),
        "position": ratings["position"],
        "ovr": ovr,
        "ratings": ratings,
        "overalls": overalls,
    }


def _blend_with_stats(scout_result, form, position):
    """If the prospect's age + actual stats are given, blend the scouting card's
    stat-derivable attributes with stat-derived ones, weighted by age vs level
    (young-for-level -> trust stats; old -> trust scouting). HITTING and FIELDING
    blend independently (give either, or both). Defense translates more directly
    than the bat -- being old-for-level inflates hitting numbers, not fielding --
    so defensive stats earn a bit more trust (+0.15 on the weight). Adds a
    confidence band from how far the two views disagree. No age/stats -> unchanged."""
    def f(key, default=0.0):
        try:
            return float(form.get(key) or default)
        except (ValueError, TypeError):
            return default

    age = f("age")
    if age <= 0:
        return scout_result
    ba = f("b_ba")
    has_hit = ba > 0
    FIELD_KEYS = ("po", "a", "e", "dp", "ch", "oaa", "drs")
    has_fld = any((form.get(k) or "").strip() for k in FIELD_KEYS)
    if not has_hit and not has_fld:
        return scout_result

    level = (form.get("level") or "MLB").strip()
    iso, kpct, bbpct = f("b_iso", 0.15), f("b_kpct", 22), f("b_bbpct", 8.5)
    base_ba = ba if has_hit else 0.260
    stat_form = {
        "BA": str(base_ba), "ISO": str(iso), "SLG": str(round(base_ba + iso, 3)),
        "OBP": str(round(min(0.5, base_ba + bbpct / 100 + 0.02), 3)),
        "HR": str(max(0, round(iso * 110))), "3B": "2", "SB": "6", "CS": "1",
        "BB_pct": str(bbpct), "K_pct": str(kpct),
        "PA": "560", "G": "140", "WAR": "3.0", "level": level, "full_confidence": "on",
    }
    # Pass through any actual fielding inputs so build_custom_data computes a real
    # stat-derived fielding rating (traditional line via Rtot, or OAA/DRS override).
    for k in FIELD_KEYS:
        v = (form.get(k) or "").strip()
        if v:
            stat_form[k] = v
    stat_r = calculate_ratings(build_custom_data(stat_form, False, position), position, mode="season")
    scout_r, scout_ovr = scout_result["ratings"], scout_result["ovr"]

    HIT = ("contact_left", "contact_right", "power_left", "power_right",
           "vision", "discipline", "batting_clutch")
    FLD = ("fielding", "reaction_left", "reaction_right", "reaction_forward", "reaction_back")
    w = stat_blend_weight(age, level)
    field_w = min(0.90, w + 0.15)

    # Swap the stat-derived attrs we're actually blending onto the scouting card
    # so stat_ovr stays apples-to-apples with scout_ovr and the blend stays in range.
    stat_view = dict(scout_r)
    blended = dict(scout_r)
    if has_hit:
        for a in HIT:
            stat_view[a] = stat_r[a]
            blended[a] = round(w * stat_r[a] + (1 - w) * scout_r[a])
    if has_fld:
        for a in FLD:
            if a in stat_r and a in scout_r:
                stat_view[a] = stat_r[a]
                blended[a] = round(field_w * stat_r[a] + (1 - field_w) * scout_r[a])

    stat_ovr = estimate_ovr_hitter(stat_view, calculate_overalls(stat_view))
    overalls = calculate_overalls(blended)
    bovr = estimate_ovr_hitter(blended, overalls)
    band = max(3, round(abs(stat_ovr - scout_ovr) * 0.5))
    scout_result.update({
        "ratings": blended, "overalls": overalls, "ovr": bovr,
        "ovr_low": max(40, bovr - band), "ovr_high": min(99, bovr + band),
        "blend": {"stat_pct": round((w if has_hit else field_w) * 100),
                  "scout_ovr": scout_ovr, "stat_ovr": stat_ovr},
    })
    return scout_result


def generate_card_data(player_name, year, is_pitcher=None, position=None, mode="season"):
    """Generate a full card for a player. Auto-detects pitcher if not specified.
    mode: 'season' = single season only, 'career' = career blended."""
    # Auto-detect if not specified
    if is_pitcher is None:
        player_type = detect_player_type(player_name, year)
        is_pitcher = (player_type == "pitcher")

    if is_pitcher:
        data = pull_all_pitcher_data(player_name, year)
        if data is None:
            return None, f"Could not find pitcher '{player_name}' in {year}"
    else:
        data = pull_all_data(player_name, year)
        if data is None:
            return None, f"Could not find '{player_name}' in {year}"

    return assemble_card(data, is_pitcher, player_name, year, position, mode), None


@app.route("/")
def index():
    # No-cache so the phone always picks up the latest UI (active development).
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/players")
def players():
    """Return player names for autocomplete, optionally filtered by year."""
    year = request.args.get("year", 2025, type=int)
    query = request.args.get("q", "").strip().lower()
    all_names = load_player_names(year)
    if query:
        filtered = [n for n in all_names if query in n.lower()][:20]
    else:
        filtered = all_names[:50]
    return jsonify(filtered)


@app.route("/generate", methods=["POST"])
def generate():
    player_name = request.form.get("player_name", "").strip()
    year = request.form.get("year", "").strip()
    is_pitcher_str = request.form.get("is_pitcher", "")
    position = request.form.get("position", "").strip() or None
    mode = request.form.get("mode", "season")  # "season" or "career"

    if not player_name or not year:
        return jsonify({"error": "Player name and year are required"}), 400

    try:
        year = int(year)
    except ValueError:
        return jsonify({"error": "Year must be a number"}), 400

    # "auto" means auto-detect, "on" means forced pitcher, "" means forced hitter
    if is_pitcher_str == "auto":
        is_pitcher = None
    elif is_pitcher_str == "on":
        is_pitcher = True
    else:
        is_pitcher = False

    try:
        result, error = generate_card_data(player_name, year, is_pitcher, position, mode=mode)
        if error:
            return jsonify({"error": error}), 404
        result["mode"] = mode
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _custom_card(form):
    """form (dict-like) -> custom card. Raises ValueError on bad input."""
    is_pitcher = form.get("is_pitcher", "") == "on"
    name = (form.get("name") or "").strip() or "Custom Player"
    try:
        year = int(form.get("year") or 0)
    except (ValueError, TypeError):
        raise ValueError("Year must be a number")

    # Reject the one input that breaks a formula (divide-by-zero on rate stats).
    label = "IP" if is_pitcher else "PA"
    try:
        bulk = float(form.get(label) or 0)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a number")
    if bulk <= 0:
        raise ValueError(f"{label} must be greater than 0")

    position = (form.get("position") or "").strip() or None
    data = build_custom_data(form, is_pitcher, position)
    result = assemble_card(data, is_pitcher, name, year, position, mode="season")
    result["mode"] = "season"
    result["custom"] = True
    result["level"] = (form.get("level") or "MLB").strip()
    return result


# Tool grades come in (future_key, present_key) pairs. The single visible grade
# is the FUTURE (projection); an optional Present grade yields a "Now" rating.
_HIT_TOOLS = [("g_hit", "g_hit_p"), ("g_power", "g_power_p"), ("g_eye", "g_eye_p"),
              ("g_speed", "g_speed_p"), ("g_field", "g_field_p"), ("g_arm", "g_arm_p")]
_PITCH_TOOLS = [("g_fb", "g_fb_p"), ("g_break", "g_break_p"),
                ("g_off", "g_off_p"), ("g_command", "g_command_p")]


def _grade_ovr(form, position, is_pitcher):
    """OVR from grades ALONE (no stat blend) — used for the Present 'Now' rating."""
    if is_pitcher:
        card = assemble_card(build_custom_data(scouting_to_pitcher_stats(form), True),
                             True, "x", 2026, None, mode="season")
    else:
        sf = scouting_to_stats(form)
        ov = {}
        if sf.get("_proj_dur"):
            ov["durability"] = float(sf["_proj_dur"])
        if sf.get("_proj_arm"):
            ov["arm_strength"] = float(sf["_proj_arm"])
        card = assemble_card(build_custom_data(sf, False, position), False, "x", 2026,
                             position, mode="season", rating_overrides=ov)
    return card["ovr"]


def _present_ovr(form, position, is_pitcher):
    """If any Present tool grade is given, return the OVR from a grade form where
    each tool = its present grade (future as the fallback). Else None."""
    pform = dict(form)
    any_present = False
    for fut, pres in (_PITCH_TOOLS if is_pitcher else _HIT_TOOLS):
        pv = (form.get(pres) or "").strip()
        if pv:
            any_present = True
            pform[fut] = pv
    return _grade_ovr(pform, position, is_pitcher) if any_present else None


def _fv_to_ovr(fv):
    """Heuristic FanGraphs FV -> OVR anchor (NOT yet Show-validated). Linear:
    50 FV (avg regular) -> 73, 60 -> 80, 70 -> 87, 40 -> 66."""
    return max(40, min(99, round(0.7 * fv + 38)))


def _scouting_card(form):
    """form (dict-like) of 20-80 tool grades -> prospect card. Supports present +
    future grades (Now->Potential range) and an optional FV overall anchor."""
    name = (form.get("name") or "Prospect").strip()
    try:
        year = int(form.get("year") or 2026)
    except (ValueError, TypeError):
        year = 2026
    is_pitcher = form.get("is_pitcher", "") == "on"
    if is_pitcher:
        position = None
        stat_form = scouting_to_pitcher_stats(form)
        data = build_custom_data(stat_form, is_pitcher=True)
        result = assemble_card(data, True, name, year, None, mode="season")
    else:
        position = (form.get("position") or "OF").strip() or "OF"
        stat_form = scouting_to_stats(form)
        overrides = {}
        if stat_form.get("_proj_dur"):
            overrides["durability"] = float(stat_form["_proj_dur"])
        if stat_form.get("_proj_arm"):
            overrides["arm_strength"] = float(stat_form["_proj_arm"])
        data = build_custom_data(stat_form, is_pitcher=False, position=position)
        result = assemble_card(data, False, name, year, position, mode="season",
                               rating_overrides=overrides)
        result = _blend_with_stats(result, form, position)

    # Present grades -> "Now" OVR -> Now->Potential range (Future = the headline OVR).
    now_ovr = _present_ovr(form, position, is_pitcher)
    if now_ovr is not None:
        result["ovr_now"] = now_ovr
        result["ovr_future"] = result["ovr"]

    # FV (FanGraphs Future Value) anchors the headline/Future OVR toward the
    # FV-implied level. Heuristic (no Show truth yet) -> flagged 'est' in the UI.
    try:
        fv = float(form.get("fv") or 0)
    except (ValueError, TypeError):
        fv = 0
    if fv > 0:
        fv_ovr = _fv_to_ovr(fv)
        old = result["ovr"]
        anchored = round(0.5 * old + 0.5 * fv_ovr)
        delta = anchored - old
        result["fv"] = int(fv) if fv == int(fv) else fv
        result["fv_ovr"] = fv_ovr
        result["ovr"] = anchored
        if "ovr_future" in result:
            result["ovr_future"] = anchored
        # Recenter the WHOLE range by the FV delta (FV calibrates the player's
        # overall level), so Now stays below Potential instead of the top
        # collapsing onto it. Also shift the blend band.
        for k in ("ovr_now", "ovr_low", "ovr_high"):
            if k in result:
                result[k] = max(40, min(99, result[k] + delta))

    result["mode"] = "season"
    result["custom"] = True
    result["scouting"] = True
    return result


def _real_card(form):
    """form with player_name/year/is_pitcher -> real-player card (re-pulls)."""
    name = (form.get("player_name") or form.get("name") or "").strip()
    if not name:
        raise ValueError("Player name is required")
    try:
        year = int(form.get("year") or 2025)
    except (ValueError, TypeError):
        raise ValueError("Year must be a number")
    isp = form.get("is_pitcher", "auto")
    is_pitcher = None if isp == "auto" else (isp == "on")
    position = (form.get("position") or "").strip() or None
    mode = form.get("mode", "season")
    result, err = generate_card_data(name, year, is_pitcher, position, mode=mode)
    if err:
        raise ValueError(err)
    result["mode"] = mode
    return result


def _card_from_source(source, form):
    """Dispatch a (source, form) pair to the matching card builder."""
    if source == "scouting":
        return _scouting_card(form)
    if source == "real":
        return _real_card(form)
    return _custom_card(form)


@app.route("/generate_custom", methods=["POST"])
def generate_custom():
    """Generate a card from hand-entered (custom player) stats."""
    try:
        return jsonify(_custom_card(request.form))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate_scouting", methods=["POST"])
def generate_scouting():
    """Generate a card from 20-80 scouting tool grades (prospect mode)."""
    try:
        return jsonify(_scouting_card(request.form))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---- Player pool (persistence) ----

@app.route("/pool/save", methods=["POST"])
def pool_save():
    """Save the current card to the player pool. Re-derives server-side from the
    submitted inputs so the cached card is authoritative, then stores form+card.
    Identity (save_name/save_team) is decoupled from the stat source."""
    form = request.form.to_dict()
    source = (form.get("source") or "custom").strip()
    try:
        card = _card_from_source(source, form)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    name = (form.get("save_name") or card.get("name") or "Player").strip()
    team = (form.get("save_team") or card.get("team") or "").strip()
    entry = player_pool.save_player(name, team, source, form, card)
    return jsonify({"ok": True, "id": entry["id"], "name": name, "ovr": card.get("ovr")})


@app.route("/pool", methods=["GET"])
def pool_list():
    """List saved players (lightweight summaries, OVR-sorted)."""
    return jsonify(player_pool.list_players())


@app.route("/pool/<pid>", methods=["GET"])
def pool_get(pid):
    """Load a saved player. Custom/scouting are RE-DERIVED from raw inputs so they
    pick up calibration improvements; real players serve the cached card."""
    entry = player_pool.get_player(pid)
    if not entry:
        return jsonify({"error": "Player not found"}), 404
    source = entry.get("source", "custom")
    card = entry.get("card")
    if source in ("custom", "scouting") and entry.get("form"):
        try:
            card = _card_from_source(source, entry["form"])
        except Exception:
            card = entry.get("card")  # fall back to cached on any derivation error
    card = dict(card or {})
    card["name"] = entry.get("name")           # honor the (editable) pool identity
    if entry.get("team"):
        card["team"] = entry.get("team")
    card["pool_id"] = pid
    return jsonify(card)


@app.route("/pool/<pid>", methods=["DELETE"])
def pool_delete(pid):
    ok = player_pool.delete_player(pid)
    return jsonify({"ok": ok}), (200 if ok else 404)


# ---- Prospect hub ----

def _prospect_card_json(team, p):
    """Run a prospect's grades through the scouting engine; attach hub metadata.

    Prospects are displayed as their NOW card (attributes + overall from the
    present grades) so what Alex keys into The Show is current ability — the
    game's own development system handles the future. The potential (future
    grade) OVR stays available as ovr_future. FV anchoring is applied on the
    future card (FV describes future value) and ovr_now is shifted by the same
    delta, so we keep the future card's ovr_now rather than re-anchoring.
    Prospects without present grades keep the future card, flagged 'potential'."""
    form = prospect_to_form(p, team)
    card = _scouting_card(form)
    if card.get("ovr_now") is not None:
        tools = _PITCH_TOOLS if p.get("is_pitcher") else _HIT_TOOLS
        nform = dict(form)
        for fut, pres in tools:
            if nform.get(pres):
                nform[fut] = nform[pres]
                nform[pres] = ""
        now_card = _scouting_card(nform)
        card["ratings"] = now_card["ratings"]
        card["overalls"] = now_card["overalls"]
        if now_card.get("arsenal"):
            card["arsenal"] = now_card["arsenal"]
        card["ovr"] = card["ovr_now"]
        card["display"] = "now"
    else:
        card["display"] = "potential"
    card["prospect"] = {
        "team": team, "id": p.get("id"), "rank": p.get("rank"),
        "pos": p.get("pos"), "age": p.get("age"),
        "bats": p.get("bats"), "throws": p.get("throws"),
        "height": p.get("height"), "weight": p.get("weight"),
        "eta": p.get("eta"), "level": p.get("level"),
        "fv": p.get("fv"), "fv_source": p.get("fv_source"),
        "grades_incomplete": bool(p.get("grades_incomplete")),
    }
    return card


@app.route("/prospects")
def prospects_index():
    data = prospect_store.load_teams()
    if not data:
        return jsonify({"error": "No prospect data — run scrape_prospects.py first."}), 404
    progress = prospect_store.load_progress()
    teams = []
    for abbrev in sorted(data["teams"].keys()):
        t = data["teams"][abbrev]
        team_prog = progress.get(abbrev, {})
        teams.append({
            "abbrev": abbrev, "name": t.get("name", abbrev),
            "count": len(t.get("prospects", [])),
            "done": sum(1 for v in team_prog.values() if v),
        })
    return jsonify({"season": data.get("season"), "teams": teams})


@app.route("/prospects/<team>")
def prospects_team(team):
    data = prospect_store.load_teams()
    if not data:
        return jsonify({"error": "No prospect data — run scrape_prospects.py first."}), 404
    t = data["teams"].get(team)
    if not t:
        return jsonify({"error": f"Unknown team '{team}'"}), 404
    team_prog = prospect_store.load_progress().get(team, {})
    rows = []
    for p in t.get("prospects", []):
        card = _prospect_card_json(team, p)
        rows.append({
            "id": p.get("id"), "rank": p.get("rank"), "name": p.get("name"),
            "pos": p.get("pos"), "age": p.get("age"), "level": p.get("level"),
            "eta": p.get("eta"), "fv": p.get("fv"), "fv_source": p.get("fv_source"),
            "is_pitcher": bool(p.get("is_pitcher")),
            "ovr": card.get("ovr"),
            "ovr_now": card.get("ovr_now"),
            "ovr_future": card.get("ovr_future", card.get("ovr")),
            "grades_incomplete": bool(p.get("grades_incomplete")),
            "done": bool(team_prog.get(p.get("id"))),
        })
    return jsonify({"team": team, "name": t.get("name", team), "prospects": rows})


@app.route("/prospects/<team>/<pid>")
def prospects_card(team, pid):
    data = prospect_store.load_teams()
    if not data:
        return jsonify({"error": "No prospect data — run scrape_prospects.py first."}), 404
    t = data["teams"].get(team)
    if not t:
        return jsonify({"error": f"Unknown team '{team}'"}), 404
    p = next((x for x in t.get("prospects", []) if x.get("id") == pid), None)
    if not p:
        return jsonify({"error": f"Prospect '{pid}' not found"}), 404
    return jsonify(_prospect_card_json(team, p))


@app.route("/prospects/done", methods=["POST"])
def prospects_done():
    team = (request.form.get("team") or "").strip()
    pid = (request.form.get("id") or "").strip()
    if not team or not pid:
        return jsonify({"error": "team and id are required"}), 400
    done = request.form.get("done") == "1"
    prospect_store.set_done(team, pid, done)
    return jsonify({"ok": True, "team": team, "id": pid, "done": done})


@app.route("/compare", methods=["POST"])
def compare():
    """Generate two cards for comparison."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    results = []
    for player in data.get("players", []):
        name = player.get("name", "").strip()
        year = player.get("year", 2025)
        position = player.get("position") or None

        if not name:
            continue

        try:
            year = int(year)
        except (ValueError, TypeError):
            continue

        cmp_mode = player.get("mode", "season")
        result, error = generate_card_data(name, year, is_pitcher=None, position=position, mode=cmp_mode)
        if error:
            results.append({"error": error, "name": name, "year": year})
        else:
            results.append(result)

    return jsonify({"cards": results})


if __name__ == "__main__":
    print("\n  MLB The Show 26 - Card Generator")
    print("  http://localhost:5000\n")
    import socket
    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"  Also available on your network: http://{local_ip}:5000\n")
    app.run(debug=False, port=5000, host="0.0.0.0")
