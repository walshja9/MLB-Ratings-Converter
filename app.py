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
    """If the prospect's age + actual rate stats are given, blend the scouting
    card's hitting attributes with stat-derived ones, weighted by age vs level
    (young-for-level -> trust stats; old -> trust scouting). Adds a confidence
    band from how far the two views disagree. No age/stats -> unchanged."""
    def f(key, default=0.0):
        try:
            return float(form.get(key) or default)
        except ValueError:
            return default

    age, ba = f("age"), f("b_ba")
    if age <= 0 or ba <= 0:
        return scout_result

    level = (form.get("level") or "MLB").strip()
    iso, kpct, bbpct = f("b_iso", 0.15), f("b_kpct", 22), f("b_bbpct", 8.5)
    stat_form = {
        "BA": str(ba), "ISO": str(iso), "SLG": str(round(ba + iso, 3)),
        "OBP": str(round(min(0.5, ba + bbpct / 100 + 0.02), 3)),
        "HR": str(max(0, round(iso * 110))), "3B": "2", "SB": "6", "CS": "1",
        "BB_pct": str(bbpct), "K_pct": str(kpct),
        "PA": "560", "G": "140", "WAR": "3.0", "level": level, "full_confidence": "on",
    }
    stat_r = calculate_ratings(build_custom_data(stat_form, False, position), position, mode="season")
    scout_r, scout_ovr = scout_result["ratings"], scout_result["ovr"]
    HIT = ("contact_left", "contact_right", "power_left", "power_right",
           "vision", "discipline", "batting_clutch")
    # The two views differ only in HITTING (the stat line carries no
    # field/speed/durability info), so swap just those onto the scouting card
    # to keep stat_ovr apples-to-apples with scout_ovr and the blend in range.
    stat_view = dict(scout_r)
    for a in HIT:
        stat_view[a] = stat_r[a]
    stat_ovr = estimate_ovr_hitter(stat_view, calculate_overalls(stat_view))
    w = stat_blend_weight(age, level)
    blended = dict(scout_r)
    for a in HIT:
        blended[a] = round(w * stat_r[a] + (1 - w) * scout_r[a])
    overalls = calculate_overalls(blended)
    bovr = estimate_ovr_hitter(blended, overalls)
    band = max(3, round(abs(stat_ovr - scout_ovr) * 0.5))
    scout_result.update({
        "ratings": blended, "overalls": overalls, "ovr": bovr,
        "ovr_low": max(40, bovr - band), "ovr_high": min(99, bovr + band),
        "blend": {"stat_pct": round(w * 100), "scout_ovr": scout_ovr, "stat_ovr": stat_ovr},
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


@app.route("/generate_custom", methods=["POST"])
def generate_custom():
    """Generate a card from hand-entered (custom player) stats."""
    form = request.form
    is_pitcher = form.get("is_pitcher", "") == "on"
    name = (form.get("name") or "").strip() or "Custom Player"

    try:
        year = int(form.get("year") or 0)
    except ValueError:
        return jsonify({"error": "Year must be a number"}), 400

    # Reject the one input that breaks a formula (divide-by-zero on rate stats).
    bulk = form.get("IP") if is_pitcher else form.get("PA")
    try:
        if float(bulk or 0) <= 0:
            return jsonify({"error": f"{'IP' if is_pitcher else 'PA'} must be greater than 0"}), 400
    except ValueError:
        return jsonify({"error": f"{'IP' if is_pitcher else 'PA'} must be a number"}), 400

    position = (form.get("position") or "").strip() or None
    try:
        data = build_custom_data(form, is_pitcher, position)
        result = assemble_card(data, is_pitcher, name, year, position, mode="season")
        result["mode"] = "season"
        result["custom"] = True
        result["level"] = (form.get("level") or "MLB").strip()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate_scouting", methods=["POST"])
def generate_scouting():
    """Generate a card from 20-80 scouting tool grades (prospect mode)."""
    form = request.form
    name = (form.get("name") or "Prospect").strip()
    try:
        year = int(form.get("year") or 2026)
    except ValueError:
        year = 2026
    is_pitcher = form.get("is_pitcher", "") == "on"
    try:
        if is_pitcher:
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
        result["mode"] = "season"
        result["custom"] = True
        result["scouting"] = True
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
