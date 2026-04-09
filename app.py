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

from flask import Flask, render_template, request, jsonify

# Import our card generator logic
sys.path.insert(0, os.path.dirname(__file__))
from generate_card import (
    pull_all_data, pull_all_pitcher_data,
    calculate_ratings, calculate_overalls,
    calculate_pitcher_ratings, calculate_pitcher_overalls,
    detect_player_type, estimate_ovr_hitter, estimate_ovr_pitcher,
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
        ratings = calculate_pitcher_ratings(data, mode=mode)
        overalls = calculate_pitcher_overalls(ratings)
        ovr = estimate_ovr_pitcher(ratings, overalls)
        team = data["pitching"].get("team", "")

        # Include pitch arsenal if available
        arsenal = data.get("statcast", {}).get("arsenal", [])
        arsenal_estimated = data.get("statcast", {}).get("arsenal_estimated", False)
        throws = data.get("statcast", {}).get("throws", "R")

        return {
            "type": "pitcher",
            "name": player_name,
            "year": year,
            "team": team,
            "position": ratings.get("role", "SP"),
            "ovr": ovr,
            "ratings": ratings,
            "overalls": overalls,
            "arsenal": arsenal,
            "arsenal_estimated": arsenal_estimated,
            "throws": throws,
        }, None
    else:
        data = pull_all_data(player_name, year)
        if data is None:
            return None, f"Could not find '{player_name}' in {year}"
        ratings = calculate_ratings(data, position, mode=mode)
        overalls = calculate_overalls(ratings)
        ovr = estimate_ovr_hitter(ratings, overalls)
        team = data["batting"].get("team", "")

        return {
            "type": "hitter",
            "name": player_name,
            "year": year,
            "team": team,
            "position": ratings["position"],
            "ovr": ovr,
            "ratings": ratings,
            "overalls": overalls,
        }, None


@app.route("/")
def index():
    return render_template("index.html")


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
