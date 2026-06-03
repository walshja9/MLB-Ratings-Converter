"""
MLB The Show 26 - Historical Player Card Generator
Generates Show-style player rating cards from real MLB season stats.

Usage: python generate_card.py "Juan Soto" 2025
       python generate_card.py "Barry Bonds" 2001 --position LF
       python generate_card.py "Garrett Crochet" 2025 --pitcher
"""

import sys
import os
import json
import argparse
import warnings
import time

# Optional: if you keep your pybaseball venv in a sibling project, point at it
# via the MLB_SHOW_VENV_SITE env var. Otherwise we use the active interpreter.
_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

# --- Manual pre-2008 pitcher arsenal overrides ---
_ARSENAL_OVERRIDES = None

def _load_arsenal_overrides():
    global _ARSENAL_OVERRIDES
    if _ARSENAL_OVERRIDES is not None:
        return _ARSENAL_OVERRIDES
    path = os.path.join(os.path.dirname(__file__), "pitcher_arsenals.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _ARSENAL_OVERRIDES = json.load(f)
    except Exception as e:
        print(f"  WARNING: Could not load pitcher_arsenals.json: {e}")
        _ARSENAL_OVERRIDES = {}
    return _ARSENAL_OVERRIDES


# Default Show-style break rating per pitch type (0-99). Used for pre-2008
# manual arsenal overrides where no measured movement data exists. Override
# any individual pitch by adding a "break" field to its JSON entry.
_DEFAULT_BREAK_BY_TYPE = {
    "KN": 92,  # knuckleball
    "EP": 95,  # eephus
    "SC": 82,  # screwball
    "CU": 75,  # curveball
    "KC": 75,  # knuckle curve
    "CS": 72,  # slow curve
    "SV": 72,  # slurve
    "ST": 75,  # sweeper
    "SL": 70,  # slider
    "FS": 72,  # splitter
    "SP": 72,  # splitter (alt code)
    "CH": 60,  # changeup
    "FC": 58,  # cutter
    "SI": 52,  # sinker
    "FF": 42,  # 4-seam
}

# Pitch code -> display name (module-level mirror of the map in
# pull_pitcher_statcast, for custom arsenals where no Statcast pull happens).
_PITCH_NAMES = {
    "FF": "4-Seam FB", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
    "ST": "Sweeper", "CU": "Curveball", "CH": "Changeup", "FS": "Splitter",
    "SP": "Splitter", "KC": "Knuckle Curve", "SV": "Slurve", "KN": "Knuckleball",
    "SC": "Screwball", "EP": "Eephus", "CS": "Slow Curve",
}


def get_arsenal_override(player_name, year):
    """Look up a manual arsenal for a pitcher. Returns dict with throws + arsenal,
    or None. Year-specific entry under 'years' takes precedence over default.

    Per-pitch break_rating is populated from the JSON 'break' field if present,
    otherwise from the pitch-type heuristic above."""
    overrides = _load_arsenal_overrides()
    entry = overrides.get(player_name)
    if not entry or not isinstance(entry, dict):
        return None
    year_entry = (entry.get("years") or {}).get(str(year))
    arsenal = (year_entry or entry).get("arsenal")
    throws = (year_entry or entry).get("throws") or entry.get("throws", "R")
    if not arsenal:
        return None

    # Populate break_rating per pitch (manual override > pitch-type default)
    enriched = []
    for p in arsenal:
        p2 = dict(p)
        if "break_rating" not in p2:
            manual = p2.pop("break", None)
            if manual is not None:
                p2["break_rating"] = int(manual)
            else:
                p2["break_rating"] = _DEFAULT_BREAK_BY_TYPE.get(p2.get("code", ""), 55)
        enriched.append(p2)

    return {"throws": throws, "arsenal": enriched, "estimated": True}

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pybaseball import (
    statcast_sprint_speed,
    statcast_batter,
    statcast_pitcher,
    playerid_lookup,
)

# FanGraphs may be behind a Cloudflare interactive challenge.
# We use BBRef scraping as a fallback when FG is unreachable.
# Batting/pitching always use BBRef; fielding tries FG first (for rARM,
# RngR, ErrR, Def) and falls back to BBRef (DRS + Total Zone only).
from bbref_scraper import (
    bbref_batting_df  as batting_stats,
    bbref_pitching_df as pitching_stats,
    bbref_fielding_df as fielding_stats_bbref,
)

# ---------- FG fielding disk cache + Playwright fetch ----------
# Cache dir lives next to this file; one JSON per year.
_FG_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fg_fielding_cache")
os.makedirs(_FG_CACHE_DIR, exist_ok=True)

# Track whether FG fielding (live) is reachable this session.
_fg_fielding_ok: bool | None = None  # None = untested, True/False = tested


def _fg_cache_path(year: int) -> str:
    return os.path.join(_FG_CACHE_DIR, f"{year}.json")


def _fg_load_cache(year: int):
    """Load cached FG fielding data from disk. Returns DataFrame or None."""
    import json as _json
    path = _fg_cache_path(year)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            rows = _json.load(f)
        if not rows:
            return None
        return pd.DataFrame(rows)
    except Exception:
        return None


def _fg_save_cache(year: int, df):
    """Persist FG fielding DataFrame to disk cache."""
    import json as _json
    path = _fg_cache_path(year)
    try:
        df.to_json(path, orient="records", indent=1)
    except Exception:
        pass


def _fg_fielding_via_playwright(year: int):
    """Hit the FanGraphs JSON API using Playwright (real browser) to bypass
    Cloudflare's JS challenge.  Returns a DataFrame with columns matching
    FG naming (Name, Pos, Inn, rARM, RngR, ErrR, Def, OAA, etc.) or None
    on failure.  Only works when a visible browser can be spawned (CLI use)."""
    import re as _re
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    url = (
        f"https://www.fangraphs.com/api/leaders/major-league/data"
        f"?pos=all&stats=fld&lg=all&qual=0"
        f"&season={year}&season1={year}&month=0&ind=0&team="
        f"&pageitems=5000&pagenum=1&type=1"
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)
            body = page.inner_text("body")
            browser.close()
        import json
        payload = json.loads(body)
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not rows:
            return None
        df = pd.DataFrame(rows)
        # Strip HTML tags from Name/Team columns (FG wraps them in <a> tags)
        for col in ("Name", "Team"):
            if col in df.columns:
                df[col] = df[col].astype(str).apply(
                    lambda x: _re.sub(r"<[^>]+>", "", x)
                )
        # FG API uses "ARM" for rARM — rename to match downstream code
        rename = {
            "PlayerName": "Name", "TeamName": "Team",
            "ARM": "rARM", "Position": "Pos",
        }
        for old, new in rename.items():
            if old in df.columns and new not in df.columns:
                df.rename(columns={old: new}, inplace=True)
        # Persist to cache so the web app can use it without Playwright
        _fg_save_cache(year, df)
        return df
    except Exception:
        return None


def fielding_stats(year: int):
    """FG fielding with disk cache + Playwright live fetch + BBRef fallback.
    Priority: 1) disk cache  2) Playwright (CLI only)  3) BBRef."""
    global _fg_fielding_ok

    # 1) Check disk cache first (works from Flask and CLI)
    cached = _fg_load_cache(year)
    if cached is not None:
        print(f"    (fielding source: FanGraphs [cached])")
        return cached

    # 2) Try live Playwright fetch (only works with visible browser)
    if _fg_fielding_ok is not False:
        try:
            df = _fg_fielding_via_playwright(year)
            if df is not None and not df.empty:
                _fg_fielding_ok = True
                print(f"    (fielding source: FanGraphs)")
                return df
        except Exception:
            pass
        _fg_fielding_ok = False

    # 3) Fall back to BBRef (DRS + TZ only)
    print(f"    (FanGraphs fielding unavailable — using BBRef)")
    return fielding_stats_bbref(year)

# ================================================================
# CONSTANTS
# ================================================================

FIELDING_YEAR_WEIGHTS = {0: 0.45, -1: 0.30, -2: 0.15, -3: 0.10}

POSITION_DEFAULTS = {
    "C":  {"arm_str": 80, "arm_acc": 65, "react_l": 0, "react_r": 0, "react_f": 0, "react_b": 0, "clutch": 65, "bunt": 35, "drag": 25},
    "1B": {"arm_str": 58, "arm_acc": 62, "react_l": 65, "react_r": 60, "react_f": 50, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 25},
    "2B": {"arm_str": 60, "arm_acc": 70, "react_l": 65, "react_r": 70, "react_f": 75, "react_b": 60, "clutch": 65, "bunt": 45, "drag": 35},
    "SS": {"arm_str": 68, "arm_acc": 75, "react_l": 55, "react_r": 80, "react_f": 80, "react_b": 70, "clutch": 65, "bunt": 35, "drag": 25},
    "3B": {"arm_str": 65, "arm_acc": 72, "react_l": 55, "react_r": 60, "react_f": 75, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 35},
    "LF": {"arm_str": 60, "arm_acc": 65, "react_l": 60, "react_r": 55, "react_f": 55, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 30},
    "CF": {"arm_str": 75, "arm_acc": 70, "react_l": 70, "react_r": 65, "react_f": 60, "react_b": 60, "clutch": 65, "bunt": 45, "drag": 40},
    "RF": {"arm_str": 75, "arm_acc": 70, "react_l": 60, "react_r": 60, "react_f": 55, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 25},
    "DH": {"arm_str": 55, "arm_acc": 65, "react_l": 45, "react_r": 45, "react_f": 45, "react_b": 45, "clutch": 65, "bunt": 35, "drag": 25},
    "OF": {"arm_str": 68, "arm_acc": 68, "react_l": 63, "react_r": 60, "react_f": 57, "react_b": 60, "clutch": 65, "bunt": 38, "drag": 30},
}

TRACKING_SPEED_BASELINES = {
    "C": 18, "1B": 28, "2B": 48, "SS": 50, "3B": 40,
    "LF": 38, "CF": 52, "RF": 40, "DH": 15, "OF": 44,
}

ARM_ASSIST_BASELINES = {
    "C": 1.0, "1B": 2.0, "2B": 4.5, "SS": 4.0, "3B": 2.5,
    "LF": 4.0, "CF": 6.0, "RF": 8.0, "OF": 5.5,
}

ARM_STRENGTH_SLOPES = {
    "C": 0.8, "1B": 0.8, "2B": 0.6, "SS": 0.7, "3B": 1.0,
    "LF": 2.2, "CF": 1.8, "RF": 1.9, "OF": 2.0,
}

ARM_ERROR_BASELINES = {
    "C": 0.020, "1B": 0.018, "2B": 0.040, "SS": 0.045, "3B": 0.040,
    "LF": 0.015, "CF": 0.012, "RF": 0.015, "OF": 0.015,
}


def clamp(val):
    return max(0, min(99, round(val)))


def estimate_speed_no_tracking(bat, pos):
    """Fallback speed model for eras without Statcast sprint speed or FG Spd.
    Uses steal attempts, efficiency, triples, and position archetype so
    athletic non-runners don't collapse to the old SB-only floor."""
    sb = float(bat.get("SB", 0) or 0)
    cs = float(bat.get("CS", 0) or 0)
    pa = max(float(bat.get("PA", 0) or 0), 1.0)
    triples = float(bat.get("3B", 0) or 0)
    attempts = sb + cs
    baseline = TRACKING_SPEED_BASELINES.get(pos, TRACKING_SPEED_BASELINES["OF"])
    triples_per_600 = 600.0 * triples / pa

    speed = baseline
    speed += 1.2 * attempts
    speed += 1.5 * min(triples_per_600, 8.0)
    if attempts >= 5:
        speed += 10.0 * ((sb / attempts) - 0.67)

    return clamp(speed)


def estimate_arm_strength_from_bbref(pos, defaults, assists, innings):
    """Fallback arm-strength proxy for BBRef-era players without rARM.
    Only meaningful for outfielders — assist rate correlates with arm strength
    for OF but not for IF/C where assists reflect range/plays made."""
    # IF and C: return position default. Assist rate doesn't measure arm
    # strength for these positions (SS with 300 assists != strong arm).
    if pos not in ("LF", "CF", "RF", "OF"):
        return defaults["arm_str"]

    if assists is None or innings is None or innings <= 0:
        return defaults["arm_str"]

    # Normalize to assists per 1200 innings (~full season for OF)
    assist_rate = 1200.0 * assists / innings
    baseline = ARM_ASSIST_BASELINES.get(pos, ARM_ASSIST_BASELINES["OF"])
    slope = ARM_STRENGTH_SLOPES.get(pos, ARM_STRENGTH_SLOPES["OF"])
    raw = defaults["arm_str"] + slope * (assist_rate - baseline)
    trust = min(innings / 900.0, 1.0)
    return clamp(defaults["arm_str"] * (1 - trust) + raw * trust)


def estimate_arm_accuracy_from_bbref(pos, defaults, errors, chances):
    """Fallback arm-accuracy proxy from BBRef fielding chances/errors.
    Only meaningful for outfielders — for IF/C, error rate reflects fielding
    skill more than arm accuracy specifically."""
    if pos not in ("LF", "CF", "RF", "OF"):
        return defaults["arm_acc"]

    if errors is None or chances is None or chances <= 0:
        return defaults["arm_acc"]

    err_rate = errors / chances
    baseline = ARM_ERROR_BASELINES.get(pos, ARM_ERROR_BASELINES["OF"])
    raw = defaults["arm_acc"] + (baseline - err_rate) * 350.0
    trust = min(chances / 250.0, 1.0)
    return clamp(defaults["arm_acc"] * (1 - trust) + raw * trust)


def detect_player_type(player_name, year):
    """Auto-detect if a player is a pitcher or hitter for a given year.
    Compares IP vs PA for the exact name match to avoid wrong-player collisions.
    Returns 'pitcher' or 'hitter'."""
    print(f"  Auto-detecting player type for {player_name} ({year})...")
    ip = 0
    pa = 0

    # Check pitching stats — strict name match only
    try:
        pit_df = pitching_stats(year)
        match = pit_df[pit_df["Name"] == player_name]
        if not match.empty:
            ip = float(match.sort_values("IP", ascending=False).iloc[0]["IP"])
    except Exception:
        pass

    # Check batting stats — strict name match only
    try:
        bat_df = batting_stats(year)
        match = bat_df[bat_df["Name"] == player_name]
        if not match.empty:
            pa = int(match.sort_values("PA", ascending=False).iloc[0]["PA"])
    except Exception:
        pass

    # If found in both, compare: pitcher if IP > PA/3 (rough heuristic)
    # A full-time hitter has ~600 PA and maybe 0 IP
    # A full-time pitcher has ~180 IP and maybe 50 PA
    if ip > 0 and pa > 0:
        # Pitcher if IP is substantial and PA is low relative to a hitter
        if ip >= 20 and pa < 100:
            print(f"    -> Pitcher ({ip:.0f} IP, {pa} PA)")
            return "pitcher"
        elif pa >= 100:
            print(f"    -> Hitter ({pa} PA, {ip:.0f} IP)")
            return "hitter"

    if ip >= 20:
        print(f"    -> Pitcher ({ip:.0f} IP)")
        return "pitcher"

    print(f"    -> Hitter ({pa} PA)")
    return "hitter"


def estimate_ovr_hitter(ratings, overalls):
    """Estimate hitter OVR from sub-attributes.

    Anchored on NOTABLE players (the population this tool actually rates), not
    the full MLB pool. A full-range refit including ~380 fringe hitters was
    tried but under-rated the good players/prospects users build (it dropped
    Bohrofen from 84 to 73 vs his Show 87), so it was reverted to this fit.
    """
    core_hitting = np.mean([
        ratings["contact_right"], ratings["contact_left"],
        ratings["power_right"], ratings["power_left"],
        ratings["vision"], ratings["discipline"],
        ratings["batting_clutch"],
    ])
    ovr = (0.8165 * core_hitting +
           0.1476 * overalls["fielding"] +
           0.0236 * ratings["speed"] +
           0.1957 * overalls["durability"])
    return clamp(ovr)


def estimate_ovr_pitcher(ratings, overalls):
    """Estimate pitcher OVR from the pitching category.

    Anchored on NOTABLE players (theshowratings top lists) — the population this
    tool is actually used to rate (stars/regulars/prospects), NOT the full MLB
    pool. A full-range refit including ~470 fringe/AAAA arms (OVR 47-78) was
    tried but it under-rated the good players users actually build, so it was
    reverted. Keeps the real fix (pitcher fielding was a near-constant ~52, a
    spurious +38 term). Maps a 72 grade -> 80 (Perry's Show OVR).
    """
    ovr = 0.990 * overalls["pitching"] + 8.4
    return clamp(ovr)


# ================================================================
# DATA PULLING
# ================================================================

def find_player(df, name):
    """Find player in a FanGraphs dataframe by name."""
    match = df[df["Name"] == name]
    if not match.empty:
        return match.iloc[0] if len(match) == 1 else match.sort_values("PA", ascending=False).iloc[0]
    # Partial match
    for part in name.split():
        if len(part) > 3 and part not in ("Jr.", "Sr.", "III", "II"):
            m = df[df["Name"].str.contains(part, case=False, na=False)]
            if len(m) == 1:
                return m.iloc[0]
            if len(m) > 1:
                return m.sort_values("PA", ascending=False).iloc[0]
    return None


def lookup_mlbam_id(player_name, year=None):
    """Look up a player's MLBAM ID for Statcast queries.
    Handles accented characters and filters by active year to avoid name collisions."""
    import unicodedata

    def strip_accents(s):
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    def add_common_accents(s):
        """Generate common accented variations of a name.
        Uses unicode escapes to be encoding-safe across editors/tools."""
        variations = [s]
        # Encoding-safe accent map: \u00e1=á, \u00e9=é, \u00ed=í, \u00f3=ó, \u00fa=ú, \u00f1=ñ
        replacements = {
            "a": "\u00e1", "e": "\u00e9", "i": "\u00ed",
            "o": "\u00f3", "u": "\u00fa", "n": "\u00f1",
        }
        for plain, accented in replacements.items():
            if plain in s.lower():
                variations.append(s.replace(plain, accented).replace(plain.upper(), accented.upper()))
        return variations

    def pick_best(result, year):
        """Pick the player active in the requested year, or most recent."""
        if result.empty:
            return None
        if year:
            # Filter to players active in the requested year
            active = result[
                (result["mlb_played_first"].fillna(9999).astype(int) <= year) &
                (result["mlb_played_last"].fillna(0).astype(int) >= year)
            ]
            if not active.empty:
                return int(active.iloc[0]["key_mlbam"])
        # Fallback: most recent player
        result = result.sort_values("mlb_played_last", ascending=False)
        return int(result.iloc[0]["key_mlbam"])

    parts = player_name.replace("Jr.", "").replace("Sr.", "").replace("III", "").strip().split()
    first = parts[0]
    last = " ".join(parts[1:]) if len(parts) > 1 else parts[0]

    # Try original name, then stripped accents, then common accent additions
    name_pairs = [(last, first)]
    stripped_last = strip_accents(last)
    stripped_first = strip_accents(first)
    if stripped_last != last or stripped_first != first:
        name_pairs.append((stripped_last, stripped_first))
    for var in add_common_accents(last):
        if var != last:
            name_pairs.append((var, first))

    for try_last, try_first in name_pairs:
        try:
            result = playerid_lookup(try_last, try_first)
            mlbam = pick_best(result, year)
            if mlbam:
                return mlbam
        except Exception:
            pass

    # Last resort: search by last name only
    try:
        result = playerid_lookup(last)
        if not result.empty:
            match = result[result["name_first"].str.contains(first, case=False, na=False)]
            mlbam = pick_best(match, year)
            if mlbam:
                return mlbam
    except Exception:
        pass

    return None


def pull_season_batting(player_name, year):
    """Pull single-season batting stats from FanGraphs."""
    print(f"  Pulling {year} batting stats...")
    df = batting_stats(year)
    row = find_player(df, player_name)
    if row is None:
        print(f"    WARNING: {player_name} not found in {year} batting")
        return None

    import math as _math

    def safe_int(val, default=0):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return default
        return int(val)

    def safe_float(val, default=0.0):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return default
        return float(val)

    fg_spd = row.get("Spd")
    fg_spd = round(float(fg_spd), 1) if fg_spd and not (isinstance(fg_spd, float) and _math.isnan(fg_spd)) else None
    bsr = row.get("BsR")
    bsr = round(float(bsr), 1) if bsr and not (isinstance(bsr, float) and _math.isnan(bsr)) else None

    return {
        "G": safe_int(row.get("G")),
        "PA": safe_int(row.get("PA")),
        "BA": round(safe_float(row.get("AVG")), 3),
        "OBP": round(safe_float(row.get("OBP")), 3),
        "SLG": round(safe_float(row.get("SLG")), 3),
        "ISO": round(safe_float(row.get("ISO")), 3),
        "HR": safe_int(row.get("HR")),
        "3B": safe_int(row.get("3B")),
        "SB": safe_int(row.get("SB")),
        "CS": safe_int(row.get("CS")),
        "BB_pct": round(safe_float(row.get("BB%")) * 100, 1),
        "K_pct": round(safe_float(row.get("K%")) * 100, 1),
        "wOBA": round(safe_float(row.get("wOBA")), 3),
        "WAR": round(safe_float(row.get("WAR")), 1),
        "fg_spd": fg_spd,
        "bsr": bsr,
        "team": str(row.get("Team", "?")),
    }


def pull_career_batting(player_name, year, num_years=4):
    """Pull multi-year batting stats and compute PA-weighted career averages.
    Starts from target year and works backwards. Stops if player not found (rookie detection)."""
    yearly = {}
    # Pull target year first (most important), then go backwards
    for y in range(year, year - num_years, -1):
        try:
            print(f"  Pulling {y} batting stats (career)...")
            df = batting_stats(y)
            # Strict name match only for career years to avoid wrong-player bugs
            match = df[df["Name"] == player_name]
            if match.empty:
                if y == year:
                    # For the target year, try partial match as fallback
                    row = find_player(df, player_name)
                else:
                    # For prior years, strict match only — stop if not found
                    print(f"    {player_name} not found in {y}, stopping career search.")
                    break
            else:
                row = match.iloc[0] if len(match) == 1 else match.sort_values("PA", ascending=False).iloc[0]

            if row is not None:
                import math as _m
                _pa = row.get("PA")
                if _pa is None or (isinstance(_pa, float) and _m.isnan(_pa)):
                    _pa = 0
                else:
                    _pa = int(_pa)
                if _pa >= 10:
                    def _sf(v, d=0.0):
                        return d if (v is None or (isinstance(v, float) and _m.isnan(v))) else float(v)
                    def _si(v, d=0):
                        return d if (v is None or (isinstance(v, float) and _m.isnan(v))) else int(v)
                    yearly[y] = {
                        "PA": _pa,
                        "BA": round(_sf(row.get("AVG")), 3),
                        "OBP": round(_sf(row.get("OBP")), 3),
                        "SLG": round(_sf(row.get("SLG")), 3),
                        "ISO": round(_sf(row.get("ISO")), 3),
                        "G": _si(row.get("G")),
                        "SB": _si(row.get("SB")),
                    }
        except Exception:
            break

    if not yearly:
        return None, {}

    # PA-weighted averages
    total_pa = sum(d["PA"] for d in yearly.values())
    avg = {}
    for stat in ["BA", "OBP", "SLG", "ISO"]:
        avg[stat] = sum(d[stat] * d["PA"] for d in yearly.values()) / total_pa

    avg["total_PA"] = total_pa
    avg["total_G"] = sum(d["G"] for d in yearly.values())
    avg["total_SB"] = sum(d["SB"] for d in yearly.values())
    avg["num_years"] = len(yearly)
    avg["avg_G_per_year"] = avg["total_G"] / len(yearly)

    return avg, yearly


def pull_sprint_speed(player_name, year):
    """Pull Statcast sprint speed."""
    print(f"  Pulling {year} sprint speed...")
    try:
        df = statcast_sprint_speed(year)
        # Build search name: "Last, First"
        parts = player_name.replace("Jr.", "").replace("Sr.", "").strip().split()
        first = parts[0]
        last = " ".join(parts[1:])

        # Try exact formatted match
        for suffix in ["", " Jr.", " Sr."]:
            search = f"{last}{suffix}, {first}"
            match = df[df["last_name, first_name"] == search]
            if not match.empty:
                return float(match.iloc[0]["sprint_speed"])

        # Partial match on last name
        match = df[df["last_name, first_name"].str.contains(last, case=False, na=False)]
        if len(match) == 1:
            return float(match.iloc[0]["sprint_speed"])
        if len(match) > 1:
            # Try to narrow with first name
            narrow = match[match["last_name, first_name"].str.contains(first, case=False, na=False)]
            if not narrow.empty:
                return float(narrow.iloc[0]["sprint_speed"])
            return float(match.iloc[0]["sprint_speed"])
    except Exception as e:
        print(f"    Sprint speed error: {e}")

    return None


CANONICAL_POSITIONS = {"RF", "LF", "CF", "1B", "2B", "SS", "3B", "C", "DH"}

_BBREF_POS_CODE = {
    "1": "P",  "2": "C",  "3": "1B", "4": "2B", "5": "3B",
    "6": "SS", "7": "LF", "8": "CF", "9": "RF",
    "O": "CF", "D": "DH", "H": "DH",
}


def normalize_position(raw):
    """Map a raw BBRef Pos string to a canonical position token.
    Handles: leading asterisks (*1B), slash composites (1B/OF),
    hyphen composites (1B-2B), outfield aliases (OF, LF-RF), and
    pre-1900 BBRef compact codes like '*3O/5' where positions are
    single-character digits (1=P..9=RF, O=OF, D/H=DH) concatenated.
    """
    if not raw:
        return "OF"
    s = str(raw).strip()
    if s.startswith("*"):
        s = s[1:]
    if "/" in s:
        s = s.split("/")[0]
    if "-" in s:
        s = s.split("-")[0]
    s = s.strip()
    if s in CANONICAL_POSITIONS:
        return s
    if s == "OF":
        return "CF"
    # Pre-1900 compact format: first char is the primary position code.
    if s and s[0] in _BBREF_POS_CODE:
        return _BBREF_POS_CODE[s[0]]
    return "OF"


def pull_career_fielding(player_name, year, num_years=4):
    """Pull multi-year fielding stats (OAA) and detect primary position.
    Aggregates across all position entries for multi-position players.
    Starts from target year backwards. Stops if player not found."""
    import math as _math
    yearly_oaa = {}
    position = None

    def safe_float(val):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return None
        return float(val)

    for y in range(year, year - num_years, -1):
        try:
            print(f"  Pulling {y} fielding stats...")
            df = fielding_stats(y)
            # Get ALL rows for this player (may have multiple position entries)
            matches = df[df["Name"] == player_name]
            if matches.empty:
                if y == year:
                    # Try partial match for target year
                    row = find_player(df, player_name)
                    if row is not None:
                        import pandas as pd
                        matches = pd.DataFrame([row])
                    else:
                        continue
                else:
                    break  # Player not in league yet

            if matches.empty:
                continue

            # Aggregate across all position entries for this year
            # Sum: Inn, OAA, DRS. Use innings-weighted average for rate stats.
            total_inn = 0
            total_oaa = 0
            total_def = 0
            total_rarm = 0
            total_rngr = 0
            total_errr = 0
            total_rdrs = 0
            total_rtot = 0
            total_assists = 0
            total_errors = 0
            total_chances = 0
            has_oaa = False
            has_def = False
            has_rarm = False
            has_rngr = False
            has_errr = False
            has_rdrs = False
            has_rtot = False
            has_assists = False
            has_errors = False
            has_chances = False
            best_pos = None
            best_inn = 0

            for _, row in matches.iterrows():
                inn = safe_float(row.get("Inn")) or 0
                total_inn += inn

                oaa = safe_float(row.get("OAA"))
                if oaa is not None:
                    total_oaa += oaa
                    has_oaa = True

                def_v = safe_float(row.get("Def"))
                if def_v is not None:
                    total_def += def_v
                    has_def = True

                rarm = safe_float(row.get("rARM"))
                if rarm is not None:
                    total_rarm += rarm
                    has_rarm = True

                rngr = safe_float(row.get("RngR"))
                if rngr is not None:
                    total_rngr += rngr
                    has_rngr = True

                errr = safe_float(row.get("ErrR"))
                if errr is not None:
                    total_errr += errr
                    has_errr = True

                assists = safe_float(row.get("A"))
                if assists is not None:
                    total_assists += assists
                    has_assists = True

                errors = safe_float(row.get("E"))
                if errors is not None:
                    total_errors += errors
                    has_errors = True

                chances = safe_float(row.get("Ch"))
                if chances is not None:
                    total_chances += chances
                    has_chances = True

                # BBRef-specific defensive metrics (era-specific inputs).
                # Rdrs = DRS (post-2003); Rtot = Total Zone (deeper history).
                rdrs = safe_float(row.get("Rdrs"))
                if rdrs is not None:
                    total_rdrs += rdrs
                    has_rdrs = True

                rtot = safe_float(row.get("Rtot"))
                if rtot is not None:
                    total_rtot += rtot
                    has_rtot = True

                # Track primary position (most innings)
                pos_val = str(row.get("Pos", ""))
                if inn > best_inn and pos_val not in ("DH", ""):
                    best_inn = inn
                    best_pos = normalize_position(pos_val)

            # Store aggregated values
            if has_oaa:
                yearly_oaa[y] = total_oaa
            if has_def:
                yearly_oaa[f"def_{y}"] = total_def
            if has_rarm:
                yearly_oaa[f"rarm_{y}"] = total_rarm
            if has_rngr:
                yearly_oaa[f"rngr_{y}"] = total_rngr
            if has_errr:
                yearly_oaa[f"errr_{y}"] = total_errr
            if has_rdrs:
                yearly_oaa[f"rdrs_{y}"] = total_rdrs
            if has_rtot:
                yearly_oaa[f"rtot_{y}"] = total_rtot
            if has_assists:
                yearly_oaa[f"ass_{y}"] = total_assists
            if has_errors:
                yearly_oaa[f"err_{y}"] = total_errors
            if has_chances:
                yearly_oaa[f"ch_{y}"] = total_chances
            if total_inn > 0:
                yearly_oaa[f"inn_{y}"] = total_inn

            if y == year and best_pos:
                position = best_pos

        except Exception:
            break

    return yearly_oaa, position


def pull_statcast_data(mlbam_id, year):
    """Pull Statcast pitch-by-pitch data and compute splits + exit velocity."""
    print(f"  Pulling {year} Statcast data (this may take a moment)...")
    start = f"{year}-03-20"
    end = f"{year}-10-01"

    try:
        df = statcast_batter(start, end, mlbam_id)
        if df.empty:
            return None, None, None
    except Exception as e:
        print(f"    Statcast error: {e}")
        return None, None, None

    # --- Splits ---
    splits = {}
    for hand, label in [("R", "vs_RHP"), ("L", "vs_LHP")]:
        subset = df[df["p_throws"] == hand]
        ab_events = [
            "single", "double", "triple", "home_run",
            "strikeout", "field_out", "grounded_into_double_play",
            "force_out", "fielders_choice", "fielders_choice_out",
            "double_play", "strikeout_double_play", "triple_play",
            "field_error",
        ]
        at_bats = subset[subset["events"].isin(ab_events)]
        all_pa = subset[subset["events"].notna()]

        if len(at_bats) == 0:
            splits[label] = {"PA": 0, "BA": 0, "OBP": 0, "ISO": 0}
            continue

        hits = at_bats[at_bats["events"].isin(["single", "double", "triple", "home_run"])]
        singles = len(at_bats[at_bats["events"] == "single"])
        doubles = len(at_bats[at_bats["events"] == "double"])
        triples = len(at_bats[at_bats["events"] == "triple"])
        homers = len(at_bats[at_bats["events"] == "home_run"])
        total_bases = singles + 2 * doubles + 3 * triples + 4 * homers

        n_ab = len(at_bats)
        n_pa = len(all_pa)
        n_hits = len(hits)
        n_bb = len(all_pa[all_pa["events"] == "walk"])
        n_hbp = len(all_pa[all_pa["events"] == "hit_by_pitch"])

        ba = n_hits / n_ab if n_ab > 0 else 0
        slg = total_bases / n_ab if n_ab > 0 else 0
        obp = (n_hits + n_bb + n_hbp) / n_pa if n_pa > 0 else 0

        splits[label] = {
            "PA": n_pa,
            "BA": round(ba, 3),
            "OBP": round(obp, 3),
            "ISO": round(slg - ba, 3),
        }

    # --- Exit Velocity ---
    batted = df[df["launch_speed"].notna()]
    avg_ev = float(batted["launch_speed"].mean()) if len(batted) > 0 else None

    # --- RISP BA (for clutch rating) ---
    ab_events = [
        "single", "double", "triple", "home_run",
        "strikeout", "field_out", "grounded_into_double_play",
        "force_out", "fielders_choice", "fielders_choice_out",
        "double_play", "strikeout_double_play", "triple_play",
        "field_error",
    ]
    risp = df[(df["on_2b"].notna()) | (df["on_3b"].notna())]
    risp_ab = risp[risp["events"].isin(ab_events)]
    risp_hits = risp_ab[risp_ab["events"].isin(["single", "double", "triple", "home_run"])]
    risp_pa = len(risp[risp["events"].notna()])
    risp_ba = len(risp_hits) / len(risp_ab) if len(risp_ab) > 0 else None
    splits["risp_ba"] = round(risp_ba, 3) if risp_ba is not None else None
    splits["risp_pa"] = risp_pa

    return splits, avg_ev, len(df)


def pull_barrel_stats(player_name, year):
    """Pull Statcast barrel% and hard-hit% data for a hitter."""
    print(f"  Pulling {year} barrel stats...")
    try:
        from pybaseball import statcast_batter_exitvelo_barrels
        df = statcast_batter_exitvelo_barrels(year, minBBE=30)
        if df.empty:
            return None

        # Match by name: "Last, First" format
        parts = player_name.replace("Jr.", "").replace("Sr.", "").strip().split()
        first = parts[0]
        last = " ".join(parts[1:])

        match = None
        for suffix in ["", " Jr.", " Sr."]:
            search = f"{last}{suffix}, {first}"
            m = df[df["last_name, first_name"] == search]
            if not m.empty:
                match = m.iloc[0]
                break

        if match is None:
            m = df[df["last_name, first_name"].str.contains(last, case=False, na=False)]
            if len(m) == 1:
                match = m.iloc[0]
            elif len(m) > 1:
                narrow = m[m["last_name, first_name"].str.contains(first, case=False, na=False)]
                if not narrow.empty:
                    match = narrow.iloc[0]

        if match is None:
            return None

        import math as _math
        def sf(val):
            if val is None or (isinstance(val, float) and _math.isnan(val)):
                return None
            return float(val)

        result = {
            "brl_percent": sf(match.get("brl_percent")),
            "brl_pa": sf(match.get("brl_pa")),
            "ev95percent": sf(match.get("ev95percent")),
            "avg_ev": sf(match.get("avg_hit_speed")),
            "max_ev": sf(match.get("max_hit_speed")),
        }
        if result["brl_percent"] is not None:
            print(f"    Barrels: {result['brl_percent']}%, hard-hit: {result['ev95percent']}%, maxEV: {result['max_ev']}")
        return result
    except Exception as e:
        print(f"    Barrel stats error: {e}")
        return None


def pull_catcher_stats(player_name, year):
    """Pull Statcast catcher metrics: pop time, arm speed, blocking.
    Only available for catchers in the Statcast era (2015+)."""
    print(f"  Pulling {year} catcher stats...")
    try:
        from pybaseball import statcast_catcher_poptime
        pt = statcast_catcher_poptime(year, min_2b_att=1)
        if pt.empty:
            return None

        # Match player by name: entity_name is "Last, First"
        parts = player_name.replace("Jr.", "").replace("Sr.", "").strip().split()
        first = parts[0]
        last = " ".join(parts[1:])

        match = None
        for suffix in ["", " Jr.", " Sr."]:
            search = f"{last}{suffix}, {first}"
            m = pt[pt["entity_name"] == search]
            if not m.empty:
                match = m.iloc[0]
                break

        if match is None:
            # Partial last name match
            m = pt[pt["entity_name"].str.contains(last, case=False, na=False)]
            if len(m) == 1:
                match = m.iloc[0]
            elif len(m) > 1:
                narrow = m[m["entity_name"].str.contains(first, case=False, na=False)]
                if not narrow.empty:
                    match = narrow.iloc[0]

        if match is None:
            print(f"    Catcher stats not found for {player_name}")
            return None

        import math as _math
        def sf(val):
            if val is None or (isinstance(val, float) and _math.isnan(val)):
                return None
            return float(val)

        result = {
            "pop_2b": sf(match.get("pop_2b_sba")),
            "arm_mph": sf(match.get("maxeff_arm_2b_3b_sba")),
            "exchange": sf(match.get("exchange_2b_3b_sba")),
            "attempts_2b": int(match.get("pop_2b_sba_count", 0)),
        }
        print(f"    Catcher: pop={result['pop_2b']}, arm={result['arm_mph']}mph, "
              f"exchange={result['exchange']}, attempts={result['attempts_2b']}")
        return result
    except Exception as e:
        print(f"    Catcher stats error: {e}")
        return None


def pull_all_data(player_name, year):
    """Orchestrate all data pulls and return consolidated stats dict."""
    print(f"\nPulling data for {player_name} ({year})...")

    data = {"name": player_name, "year": year}

    # Season batting
    data["batting"] = pull_season_batting(player_name, year)
    if data["batting"] is None:
        print("ERROR: Could not find player in batting stats.")
        return None

    # Career batting
    data["career_avg"], data["career_yearly"] = pull_career_batting(player_name, year)

    # Sprint speed
    data["sprint_speed"] = pull_sprint_speed(player_name, year)

    # Career fielding
    data["fielding_oaa"], data["position"] = pull_career_fielding(player_name, year)

    # MLBAM ID for Statcast
    print("  Looking up player ID...")
    mlbam_id = lookup_mlbam_id(player_name, year)
    if mlbam_id:
        data["splits"], data["avg_ev"], _ = pull_statcast_data(mlbam_id, year)
    else:
        print(f"    WARNING: Could not find MLBAM ID for {player_name}")
        data["splits"] = None
        data["avg_ev"] = None

    # Barrel% / hard-hit% data (Statcast era)
    if year >= 2015:
        data["barrel_stats"] = pull_barrel_stats(player_name, year)
    else:
        data["barrel_stats"] = None

    # Catcher-specific Statcast data (pop time, arm speed)
    pos = data.get("position") or "OF"
    if pos == "C" and year >= 2015:
        data["catcher_stats"] = pull_catcher_stats(player_name, year)
    else:
        data["catcher_stats"] = None

    return data


# ================================================================
# PITCHER DATA PULLING
# ================================================================

PITCHER_FIELDING_DEFAULTS = {
    "fielding": 50, "arm_str": 65, "arm_acc": 50,
    "react_l": 50, "react_r": 50, "react_f": 50, "react_b": 50,
}


def find_pitcher_fg(df, name):
    """Find pitcher in FanGraphs dataframe, sort by IP instead of PA."""
    match = df[df["Name"] == name]
    if not match.empty:
        return match.iloc[0] if len(match) == 1 else match.sort_values("IP", ascending=False).iloc[0]
    for part in name.split():
        if len(part) > 3 and part not in ("Jr.", "Sr.", "III", "II"):
            m = df[df["Name"].str.contains(part, case=False, na=False)]
            if len(m) == 1:
                return m.iloc[0]
            if len(m) > 1:
                return m.sort_values("IP", ascending=False).iloc[0]
    return None


def pull_season_pitching(player_name, year):
    """Pull single-season pitching stats from FanGraphs."""
    print(f"  Pulling {year} pitching stats...")
    import math as _math
    df = pitching_stats(year)
    row = find_pitcher_fg(df, player_name)
    if row is None:
        print(f"    WARNING: {player_name} not found in {year} pitching")
        return None

    def safe_float(val, default=0):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return default
        return float(val)

    fbv = safe_float(row.get("FBv"), None)

    return {
        "W": int(row.get("W", 0)),
        "L": int(row.get("L", 0)),
        "ERA": round(safe_float(row.get("ERA")), 2),
        "FIP": round(safe_float(row.get("FIP")), 2),
        "IP": round(safe_float(row.get("IP")), 1),
        "G": int(row.get("G", 0)),
        "GS": int(row.get("GS", 0)),
        "SV": int(row.get("SV", 0)),
        "K_per_9": round(safe_float(row.get("K/9")), 1),
        "BB_per_9": round(safe_float(row.get("BB/9")), 1),
        "HR_per_9": round(safe_float(row.get("HR/9")), 2),
        "H_per_9": round(safe_float(row.get("H/9")), 1),
        "K_pct": round(safe_float(row.get("K%")) * 100, 1),
        "BB_pct": round(safe_float(row.get("BB%")) * 100, 1),
        "WHIP": round(safe_float(row.get("WHIP")), 3),
        "WAR": round(safe_float(row.get("WAR")), 1),
        "LOB_pct": round(safe_float(row.get("LOB%")) * 100, 1),
        "FB_velo": round(fbv, 1) if fbv else None,
        "team": str(row.get("Team", "?")),
    }


def pull_career_pitching(player_name, year, num_years=4):
    """Pull multi-year pitching stats for career blending.
    Starts from target year backwards. Stops if player not found (rookie detection)."""
    import math as _math
    yearly = {}
    for y in range(year, year - num_years, -1):
        try:
            print(f"  Pulling {y} pitching stats (career)...")
            df = pitching_stats(y)
            match = df[df["Name"] == player_name]
            if match.empty:
                if y == year:
                    row = find_pitcher_fg(df, player_name)
                else:
                    print(f"    {player_name} not found in {y}, stopping career search.")
                    break
            else:
                row = match.iloc[0] if len(match) == 1 else match.sort_values("IP", ascending=False).iloc[0]

            if row is not None and float(row.get("IP", 0)) >= 5:
                yearly[y] = {
                    "IP": round(float(row.get("IP", 0)), 1),
                    "G": int(row.get("G", 0)),
                    "GS": int(row.get("GS", 0)),
                    "ERA": round(float(row.get("ERA", 0)), 2),
                    "K_per_9": round(float(row.get("K/9", 0)), 1),
                    "BB_per_9": round(float(row.get("BB/9", 0)), 1),
                    "HR_per_9": round(float(row.get("HR/9", 0)), 2),
                    "H_per_9": round(float(row.get("H/9", 0)), 1),
                    "K_pct": round(float(row.get("K%", 0)) * 100, 1),
                    "BB_pct": round(float(row.get("BB%", 0)) * 100, 1),
                }
        except Exception:
            break

    if not yearly:
        return None, {}

    # IP-weighted averages
    total_ip = sum(d["IP"] for d in yearly.values())
    avg = {}
    for stat in ["ERA", "K_per_9", "BB_per_9", "HR_per_9", "H_per_9", "K_pct", "BB_pct"]:
        avg[stat] = sum(d[stat] * d["IP"] for d in yearly.values()) / total_ip

    avg["total_IP"] = total_ip
    avg["total_GS"] = sum(d["GS"] for d in yearly.values())
    avg["total_G"] = sum(d["G"] for d in yearly.values())
    avg["num_years"] = len(yearly)
    avg["avg_GS_per_year"] = avg["total_GS"] / len(yearly)

    return avg, yearly


def pull_pitcher_statcast(mlbam_id, year):
    """Pull Statcast data for pitcher: velocity, splits vs LHB/RHB."""
    print(f"  Pulling {year} Statcast pitcher data...")
    start = f"{year}-03-20"
    end = f"{year}-10-01"

    try:
        df = statcast_pitcher(start, end, mlbam_id)
        if df.empty:
            return {}
    except Exception as e:
        print(f"    Statcast error: {e}")
        return {}

    result = {}

    # Detect pitcher handedness from pitch data
    if "p_throws" in df.columns:
        throws_mode = df["p_throws"].mode()
        if not throws_mode.empty:
            result["throws"] = str(throws_mode.iloc[0])

    # Fastball velocity
    fb = df[df["pitch_type"].isin(["FF", "SI"])]
    if not fb.empty and "release_speed" in fb.columns:
        result["avg_fb_velo"] = round(float(fb["release_speed"].mean()), 1)
        result["max_fb_velo"] = round(float(fb["release_speed"].max()), 1)

    # All-pitch average velocity
    if "release_speed" in df.columns:
        all_velo = df[df["release_speed"].notna()]
        if not all_velo.empty:
            result["avg_all_velo"] = round(float(all_velo["release_speed"].mean()), 1)

    # Splits vs LHB and RHB
    for hand, label in [("L", "vs_LHB"), ("R", "vs_RHB")]:
        subset = df[(df["stand"] == hand) & df["events"].notna()]
        if len(subset) < 10:
            continue
        ab_events = ["single", "double", "triple", "home_run", "strikeout",
                     "field_out", "grounded_into_double_play", "force_out",
                     "fielders_choice", "fielders_choice_out", "double_play",
                     "strikeout_double_play", "field_error"]
        at_bats = subset[subset["events"].isin(ab_events)]
        all_pa = subset
        if len(at_bats) == 0:
            continue
        hits = len(at_bats[at_bats["events"].isin(["single", "double", "triple", "home_run"])])
        ks = len(all_pa[all_pa["events"].str.contains("strikeout", na=False)])
        bbs = len(all_pa[all_pa["events"] == "walk"])
        n_pa = len(all_pa)
        n_ab = len(at_bats)
        result[label] = {
            "PA": n_pa,
            "BA": round(hits / n_ab, 3) if n_ab else 0,
            "K_pct": round(ks / n_pa * 100, 1) if n_pa else 0,
            "BB_pct": round(bbs / n_pa * 100, 1) if n_pa else 0,
        }

    # Pitch arsenal: per-pitch type stats
    PITCH_NAMES = {
        "FF": "4-Seam FB", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
        "ST": "Sweeper", "CU": "Curveball", "CH": "Changeup", "FS": "Splitter",
        "KC": "Knuckle Curve", "SV": "Slurve", "KN": "Knuckleball",
        "SC": "Screwball", "EP": "Eephus", "CS": "Slow Curve",
    }

    pitch_data = df[df["pitch_type"].notna() & (df["pitch_type"] != "UN")]
    total_pitches = len(pitch_data)
    arsenal = []

    if total_pitches > 0:
        for pt in pitch_data["pitch_type"].unique():
            subset = pitch_data[pitch_data["pitch_type"] == pt]
            count = len(subset)
            pct = count / total_pitches * 100
            if pct < 1.0:
                continue  # skip junk pitches

            pitch_info = {
                "code": pt,
                "name": PITCH_NAMES.get(pt, pt),
                "usage": round(pct, 1),
                "count": count,
            }

            if "release_speed" in subset.columns:
                velo = subset["release_speed"].dropna()
                if not velo.empty:
                    pitch_info["velo"] = round(float(velo.mean()), 1)

            if "pfx_x" in subset.columns and "pfx_z" in subset.columns:
                h_break = subset["pfx_x"].dropna()
                v_break = subset["pfx_z"].dropna()
                if not h_break.empty and not v_break.empty:
                    h_avg = float(h_break.mean()) * 12  # feet to inches
                    v_avg = float(v_break.mean()) * 12
                    total_inches = (h_avg**2 + v_avg**2)**0.5
                    pitch_info["h_break"] = round(h_avg, 1)
                    pitch_info["v_break"] = round(v_avg, 1)
                    pitch_info["total_break_inches"] = round(total_inches, 1)
                    # Convert to 0-99 scale: ~3in = 20, ~10in = 55, ~15in = 75, ~20in = 99
                    pitch_info["break_rating"] = max(0, min(99, round(total_inches * 4.7 + 5)))

            if "release_spin_rate" in subset.columns:
                spin = subset["release_spin_rate"].dropna()
                if not spin.empty:
                    pitch_info["spin"] = round(float(spin.mean()))

            arsenal.append(pitch_info)

        # Sort by usage descending
        arsenal.sort(key=lambda x: x["usage"], reverse=True)

    result["arsenal"] = arsenal

    return result


def pull_all_pitcher_data(player_name, year):
    """Orchestrate all pitcher data pulls."""
    print(f"\nPulling pitcher data for {player_name} ({year})...")

    data = {"name": player_name, "year": year, "is_pitcher": True}

    data["pitching"] = pull_season_pitching(player_name, year)
    if data["pitching"] is None:
        print("ERROR: Could not find pitcher in pitching stats.")
        return None

    data["career_avg"], data["career_yearly"] = pull_career_pitching(player_name, year)

    # Detect role: SP if >50% of games are starts
    pit = data["pitching"]
    data["role"] = "SP" if pit["GS"] > pit["G"] * 0.4 else "RP"

    # Sprint speed (pitchers have it too)
    data["sprint_speed"] = pull_sprint_speed(player_name, year)

    # MLBAM ID for Statcast
    print("  Looking up player ID...")
    mlbam_id = lookup_mlbam_id(player_name, year)
    # Statcast pitch tracking begins in 2008. For earlier seasons, skip the
    # Savant pull entirely — it occasionally returns 1-2 garbage records
    # (e.g. a stray pitchout) that pollute the arsenal.
    if mlbam_id and year >= 2008:
        data["statcast"] = pull_pitcher_statcast(mlbam_id, year)
    elif mlbam_id:
        data["statcast"] = {}
    else:
        print(f"    WARNING: Could not find MLBAM ID for {player_name}")
        data["statcast"] = {}

    # Pre-pitch-tracking era (or any year with no Statcast arsenal): try manual override.
    sc = data["statcast"]
    if not sc.get("arsenal") and year < 2008:
        override = get_arsenal_override(player_name, year)
        if override:
            print(f"  Using manual arsenal override for {player_name} (estimated)")
            sc["arsenal"] = override["arsenal"]
            sc["arsenal_estimated"] = True
            if not sc.get("throws"):
                sc["throws"] = override["throws"]

    return data


# ================================================================
# CUSTOM PLAYER INPUT (hand-entered stats -> engine data dict)
# ================================================================

# Position-average fielding constants for translating a traditional fielding
# line into a Total-Zone-style runs estimate. FLD% averages and range factors
# (plays per 9 innings) are standard sabermetric ballpark values.
_POS_FLD_AVG = {"C": 0.992, "1B": 0.994, "2B": 0.983, "SS": 0.974, "3B": 0.958,
                "LF": 0.984, "CF": 0.987, "RF": 0.984, "OF": 0.985, "DH": 0.980}
_POS_RF9 = {"2B": 4.7, "SS": 4.3, "3B": 2.7, "LF": 2.0, "CF": 2.5, "RF": 2.0, "OF": 2.2}
# Range is the dominant component of real defensive value, so weight it ~2x
# the prior values; error avoidance is de-emphasized (RUNS_PER_ERROR 0.75->0.5)
# in _fielding_runs_from_traditional. Balances the spread toward ~60/40 range/error.
_POS_RANGE_W = {"2B": 5.0, "SS": 5.0, "3B": 5.0, "LF": 5.0, "CF": 6.0, "RF": 5.0, "OF": 5.0}


def _fielding_runs_from_traditional(pos, po, a, e, dp, ch, innings):
    """Total-Zone-style runs estimate from a traditional fielding line.

    Range runs (range factor vs position average) + error-avoidance runs
    (errors vs a position-average fielder). Range is skipped for 1B/C/DH where
    putouts are routine rather than range plays. Returns a clamped Rtot-equivalent
    the engine's calibrated Rtot path turns into a FIELD/REAC rating, or None.
    """
    po = po or 0
    a = a or 0
    e = e or 0
    ch = ch if ch else (po + a + e)
    if ch <= 0 or innings <= 0:
        return None
    exp_e = (1 - _POS_FLD_AVG.get(pos, 0.980)) * ch
    err_runs = (exp_e - e) * 0.5
    range_runs = 0.0
    if pos in _POS_RF9 and innings > 0:
        rf9 = 9 * (po + a) / innings
        # Guard against an implausible rate (e.g. season totals entered with a
        # partial innings count): fall back to error-avoidance only.
        if rf9 <= _POS_RF9[pos] * 2.0:
            range_runs = (rf9 - _POS_RF9[pos]) * _POS_RANGE_W[pos]
    return max(-15.0, min(15.0, round(err_runs + range_runs, 1)))


def _parse_custom_arsenal(raw):
    """Parse the custom pitch-arsenal JSON into engine arsenal entries.

    Each input item is {code, velo?, usage?}. Output items carry name, usage
    (even split when omitted), velo, and a pitch-type break_rating. Returns []
    on missing/invalid input.
    """
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return []
    items = [it for it in items if isinstance(it, dict) and (it.get("code") or "").strip()]
    n = len(items)
    arsenal = []
    for it in items:
        code = str(it["code"]).strip().upper()
        usage = it.get("usage")
        if usage in (None, ""):
            usage = round(100.0 / n, 1) if n else 0.0
        brk = _DEFAULT_BREAK_BY_TYPE.get(code, 55)
        entry = {
            "code": code,
            "name": _PITCH_NAMES.get(code, code),
            "usage": float(usage),
            "break_rating": brk,
            # Invert the per-pitch break->inches relation (break = inches*4.7 + 5)
            # so the overall Break rating runs through the engine's movement
            # formula (tied to what's actually thrown) instead of the flat
            # count-based heuristic that floored everyone near 75.
            "total_break_inches": round((brk - 5) / 4.7, 1),
        }
        velo = it.get("velo")
        if velo not in (None, ""):
            entry["velo"] = float(velo)
        spin = it.get("spin")
        if spin not in (None, ""):
            entry["spin"] = int(round(float(spin)))
        arsenal.append(entry)
    return arsenal


# Minor-league -> MLB equivalency multipliers, applied to the entered rate stats
# before rating so a prospect's A+/AA line reads as an MLB-equivalent card. The
# directions are firm (offense discounts and K% rises going up; pitcher Ks fall
# while hits/HR/BB rise); magnitudes are estimates from published MLE research
# and are tunable — our truth set is MLB-only so they can't be calibrated here.
_MLE = {
    "MLB": {},
    "AAA": {"BA": 0.96, "ISO": 0.90, "BB_pct": 0.97, "K_pct": 1.08,
            "K_per_9": 0.92, "BB_per_9": 1.05, "HR_per_9": 1.15, "H_per_9": 1.06, "WHIP": 1.05},
    "AA":  {"BA": 0.93, "ISO": 0.82, "BB_pct": 0.95, "K_pct": 1.15,
            "K_per_9": 0.85, "BB_per_9": 1.10, "HR_per_9": 1.28, "H_per_9": 1.12, "WHIP": 1.10},
    "A+":  {"BA": 0.90, "ISO": 0.74, "BB_pct": 0.93, "K_pct": 1.22,
            "K_per_9": 0.79, "BB_per_9": 1.14, "HR_per_9": 1.40, "H_per_9": 1.18, "WHIP": 1.15},
    "A":   {"BA": 0.87, "ISO": 0.68, "BB_pct": 0.91, "K_pct": 1.30,
            "K_per_9": 0.74, "BB_per_9": 1.18, "HR_per_9": 1.52, "H_per_9": 1.24, "WHIP": 1.20},
    "A-":  {"BA": 0.85, "ISO": 0.64, "BB_pct": 0.90, "K_pct": 1.36,
            "K_per_9": 0.70, "BB_per_9": 1.20, "HR_per_9": 1.60, "H_per_9": 1.28, "WHIP": 1.23},
    "Rk":  {"BA": 0.82, "ISO": 0.58, "BB_pct": 0.88, "K_pct": 1.42,
            "K_per_9": 0.66, "BB_per_9": 1.24, "HR_per_9": 1.70, "H_per_9": 1.34, "WHIP": 1.27},
}


def scouting_to_stats(form):
    """Convert a hitter's 20-80 scouting tool grades into a synthetic full-season
    stat line, so the CALIBRATED engine can rate the player (mirrors how Show
    sets prospect ratings from scouting projection, not raw stats).

    Grade->stat anchors are FanGraphs' documented 20-80 tables (50 = MLB average):
    Hit 50->.260 / 80->.320; Power 50->~16 HR / 80->~40; Run 50->avg speed.
    K%/BB% track the Hit and Eye grades. Returns a dict shaped like the custom
    stat form, fed straight into build_custom_data().
    """
    def g(key, default=50.0):
        v = form.get(key, "")
        v = "" if v is None else str(v).strip()
        try:
            return float(v) if v != "" else default
        except ValueError:
            return default

    def lim(x, lo, hi):
        return max(lo, min(hi, x))

    hit, power, eye = g("g_hit"), g("g_power"), g("g_eye")
    run, field = g("g_speed"), g("g_field")

    ba = round(lim(0.260 + (hit - 50) * 0.002, 0.180, 0.350), 3)
    iso = round(lim(0.150 + (power - 50) * 0.0046, 0.030, 0.400), 3)
    hr = max(0, round((power - 50) * 0.85 + 16.5))
    kpct = round(lim(22 - (hit - 50) * 0.40, 8, 38), 1)
    bbpct = round(lim(8.5 + (eye - 50) * 0.22, 3, 18), 1)
    sprint = round(lim(27 + (run - 50) * 0.115, 23, 31), 1)
    sb = max(0, round((run - 45) * 1.5))
    triples = max(0, round((run - 55) * 0.15))
    oaa = round((field - 50) * 0.8)

    return {
        "name": form.get("name") or "Prospect",
        "team": form.get("team") or "CUSTOM",
        "year": form.get("year") or "2026",
        "position": form.get("position") or "OF",
        "level": form.get("level") or "MLB",
        "full_confidence": "on",          # grades ARE the talent estimate; don't regress
        "PA": "600", "G": "150", "WAR": "3.0",
        "BA": str(ba), "OBP": str(round(min(0.500, ba + bbpct / 100 + 0.020), 3)),
        "SLG": str(round(ba + iso, 3)), "ISO": str(iso),
        "HR": str(hr), "3B": str(triples), "SB": str(sb), "CS": str(max(0, round(sb * 0.18))),
        "BB_pct": str(bbpct), "K_pct": str(kpct),
        "sprint_speed": str(sprint), "oaa": str(oaa),
    }


def build_custom_data(form, is_pitcher, position=None):
    """Build the rating engine's `data` dict from a flat custom-stat form.

    This is the second producer of the same `data` shape that pull_all_data /
    pull_all_pitcher_data produce from the network. Feeding identical field
    values yields identical ratings — the engine is never touched. Optional /
    advanced fields left blank become None and drop into the engine's existing
    fallback paths (the same ones that rate pre-Statcast players).
    """

    def fnum(key, default=None):
        """Parse a form field to float; blank/invalid -> default."""
        v = form.get(key, "")
        v = "" if v is None else str(v).strip()
        if v == "":
            return default
        try:
            return float(v)
        except ValueError:
            return default

    def inum(key, default=0):
        v = fnum(key, None)
        return int(round(v)) if v is not None else default

    year = inum("year", 2025)
    name = (form.get("name") or "Custom Player").strip()
    team = (form.get("team") or "CUSTOM").strip()
    full_conf = str(form.get("full_confidence") or "").lower() in ("on", "true", "1", "yes")
    # Minor-league -> MLB-equivalent multipliers for the entered rate stats.
    mle = _MLE.get((form.get("level") or "MLB").strip(), {})

    def lv(stat, val):
        """Apply the level (MLE) multiplier for a stat to a value (or None)."""
        return None if val is None else val * mle.get(stat, 1.0)

    if is_pitcher:
        role = "RP" if (form.get("role") or "SP").upper() == "RP" else "SP"
        ip = fnum("IP", 0.0) or 0.0
        pitching = {
            "W": inum("W"), "L": inum("L"),
            "ERA": round(fnum("ERA", 0.0) or 0.0, 2),
            "FIP": round(fnum("FIP", 0.0) or 0.0, 2),
            "IP": round(ip, 1),
            "G": inum("G"), "GS": inum("GS"), "SV": inum("SV"),
            "K_per_9": round(lv("K_per_9", fnum("K_per_9", 0.0) or 0.0), 1),
            "BB_per_9": round(lv("BB_per_9", fnum("BB_per_9", 0.0) or 0.0), 1),
            "HR_per_9": round(lv("HR_per_9", fnum("HR_per_9", 0.0) or 0.0), 2),
            "H_per_9": round(lv("H_per_9", fnum("H_per_9", 0.0) or 0.0), 1),
            # K% / BB% track the K/9 and BB/9 directions across levels.
            "K_pct": round((fnum("K_pct", 0.0) or 0.0) * mle.get("K_per_9", 1.0), 1),
            "BB_pct": round((fnum("BB_pct", 0.0) or 0.0) * mle.get("BB_per_9", 1.0), 1),
            "WHIP": round(lv("WHIP", fnum("WHIP", 0.0) or 0.0), 3),
            "WAR": round(fnum("WAR", 0.0) or 0.0, 1),
            "LOB_pct": round(fnum("LOB_pct", 0.0) or 0.0, 1),
            "FB_velo": fnum("FB_velo"),
            "team": team,
        }
        statcast = {"throws": "L" if (form.get("throws") or "R").upper() == "L" else "R"}

        # Optional pitch arsenal (JSON list of {code, velo, usage}). Break is the
        # pitch-type heuristic (no measured movement); usage defaults to an even
        # split. Flagged estimated so the card shows the EST. badge.
        arsenal = _parse_custom_arsenal(form.get("arsenal"))
        if arsenal:
            statcast["arsenal"] = arsenal
            statcast["arsenal_estimated"] = True
            if pitching["FB_velo"] is None:
                ff = next((p for p in arsenal if p["code"] == "FF" and p.get("velo")), None)
                if ff:
                    pitching["FB_velo"] = ff["velo"]

        return {
            "name": name, "year": year, "is_pitcher": True,
            "pitching": pitching,
            "career_avg": None, "career_yearly": {},
            "statcast": statcast,
            "role": role,
            "sprint_speed": None,
            "full_confidence": full_conf,
        }

    # --- Hitter ---
    pos = position or (form.get("position") or "OF")
    pa = inum("PA", 0)
    g = inum("G", 0)
    ba = fnum("BA", 0.0) or 0.0
    slg = fnum("SLG")
    iso = fnum("ISO")
    if iso is None:
        iso = (slg - ba) if slg is not None else 0.0
    # Translate the rate stats to MLB-equivalent (identity at MLB level).
    ba = lv("BA", ba)
    iso = lv("ISO", iso)
    slg = ba + iso                                   # keep consistent post-translation
    obp = lv("BA", fnum("OBP", 0.0) or 0.0)
    bb_pct = lv("BB_pct", fnum("BB_pct", 0.0) or 0.0)
    k_pct = lv("K_pct", fnum("K_pct", 0.0) or 0.0)
    batting = {
        "G": g, "PA": pa,
        "BA": round(ba, 3),
        "OBP": round(obp, 3),
        "SLG": round(slg, 3),
        "ISO": round(iso, 3),
        "HR": inum("HR"), "3B": inum("3B"),
        "SB": inum("SB"), "CS": inum("CS"),
        "BB_pct": round(bb_pct, 1),
        "K_pct": round(k_pct, 1),
        "wOBA": 0.0,
        "WAR": round(fnum("WAR", 0.0) or 0.0, 1),
        "fg_spd": None, "bsr": None,
        "team": team,
    }

    data = {
        "name": name, "year": year,
        "batting": batting,
        "career_avg": None, "career_yearly": {},
        "sprint_speed": fnum("sprint_speed"),
        "position": pos,
        "avg_ev": fnum("avg_ev"),
        "catcher_stats": None,
        "full_confidence": full_conf,
    }

    # Optional platoon / RISP splits. When provided, give the split a trusted
    # sample (proportional to overall PA) so it actually influences the rating;
    # blank splits -> None -> engine uses overall BA/ISO.
    ba_r, iso_r = lv("BA", fnum("ba_vr")), lv("ISO", fnum("iso_vr"))
    ba_l, iso_l = lv("BA", fnum("ba_vl")), lv("ISO", fnum("iso_vl"))
    risp = lv("BA", fnum("risp_ba"))
    if any(x is not None for x in (ba_r, iso_r, ba_l, iso_l, risp)):
        data["splits"] = {
            "vs_RHP": {"PA": round(pa * 0.7), "OBP": 0,
                       "BA": ba_r if ba_r is not None else ba,
                       "ISO": iso_r if iso_r is not None else iso},
            "vs_LHP": {"PA": round(pa * 0.3), "OBP": 0,
                       "BA": ba_l if ba_l is not None else ba,
                       "ISO": iso_l if iso_l is not None else iso},
            "risp_ba": risp,
            "risp_pa": round(pa * 0.25) if risp is not None else 0,
        }
    else:
        data["splits"] = None

    # Optional barrel% (power signal)
    brl = fnum("brl_percent")
    if brl is not None:
        data["barrel_stats"] = {
            "brl_percent": brl, "ev95percent": fnum("ev95percent"),
            "brl_pa": None, "avg_ev": fnum("avg_ev"), "max_ev": None,
        }
    else:
        data["barrel_stats"] = None

    # Fielding. Accept either a traditional line (PO/A/E/DP + innings) or the
    # advanced metrics (OAA/DRS). The traditional line is translated into a
    # Total-Zone-style runs estimate fed through the engine's calibrated Rtot
    # path, so it drives FIELD/REAC for every position; A/E/CH also feed the
    # engine's outfield arm proxies. OAA (best) or DRS override the estimate.
    # No fielding input at all -> empty dict -> position baseline.
    oaa = fnum("oaa")
    drs = fnum("drs")
    po = fnum("po")
    a = fnum("a")
    e = fnum("e")
    dp = fnum("dp")
    ch = fnum("ch")
    trad = any(v is not None for v in (po, a, e, dp, ch))
    if trad or any(v is not None for v in (oaa, drs)):
        # Innings drives defensive trust + range normalization. Derived from
        # Games (consistent with the rest of the line) so the user never has to
        # hand-reconcile it; full season's worth earns full trust.
        innings = g * 8.5 if g and g > 0 else 1300.0
        oaa_data = {"inn_%d" % year: innings}
        if ch is None and any(v is not None for v in (po, a, e)):
            ch = (po or 0) + (a or 0) + (e or 0)
        # Outfield arm proxies (engine uses assists/errors/chances for OF only)
        if a is not None:
            oaa_data["ass_%d" % year] = a
        if e is not None:
            oaa_data["err_%d" % year] = e
        if ch is not None:
            oaa_data["ch_%d" % year] = ch
        if trad and e is not None:
            rtot = _fielding_runs_from_traditional(pos, po, a, e, dp, ch, innings)
            if rtot is not None:
                oaa_data["rtot_%d" % year] = rtot
        if drs is not None:
            oaa_data["rdrs_%d" % year] = drs
        if oaa is not None:
            oaa_data[year] = oaa            # best metric -> OAA branch wins
        data["fielding_oaa"] = oaa_data
    else:
        data["fielding_oaa"] = {}

    # Optional catcher block
    if pos == "C":
        pop, arm = fnum("pop_2b"), fnum("arm_mph")
        if pop is not None or arm is not None:
            data["catcher_stats"] = {"pop_2b": pop, "arm_mph": arm}

    return data


# ================================================================
# RATING CALCULATIONS
# ================================================================

def calculate_ratings(data, position_override=None, mode="season"):
    """Calculate all MLB The Show ratings from real stats.
    mode: 'season' = single season only, 'career' = career blended."""

    # --- Pre-OAA fielding slopes (tune here after spot-checks) ---
    RDRS_FIELD_SLOPE     = 2.5   # recalibrated — adjust after calibration
    RDRS_FIELD_INTERCEPT = 68    # intercept
    RTOT_FIELD_SLOPE     = 2.0   # recalibrated from 1.6; stays < RDRS slope
    RTOT_FIELD_INTERCEPT = 68

    # --- Pre-OAA reaction proxy slopes (tune here after spot-checks) ---
    RDRS_REACT_SLOPE = 1.2   # Rdrs as range proxy; weaker than RngR (2.0)
    RTOT_REACT_SLOPE = 1.0   # Rtot as range proxy; weakest signal

    # --- Pre-OAA trust constants ---
    RTOT_PARTIAL_TRUST = 0.4  # fixed trust when innings data absent (Bug 4)

    bat = data["batting"]
    career = data.get("career_avg") or bat  # fallback to single season
    use_career = (mode == "career" and isinstance(career, dict) and career != bat)
    splits = data.get("splits") or {}
    pos = position_override or data.get("position") or "OF"

    # Normalize position
    pos_map = {"RF": "RF", "LF": "LF", "CF": "CF", "1B": "1B", "2B": "2B",
               "SS": "SS", "3B": "3B", "C": "C", "DH": "DH"}
    pos = pos_map.get(pos, "OF")
    defaults = POSITION_DEFAULTS.get(pos, POSITION_DEFAULTS["OF"])

    ratings = {"position": pos}

    # --- SAMPLE SIZE ---
    # PA drives trust for all rate-stat formulas. Defined once here.
    pa = bat.get("PA", 0) or 0

    # --- VISION: -2.47 * K% + 118.1 ---
    # Refit on 44-player set (RMSE 5.4, was 7.6). Shallower slope + lower
    # intercept at scale — the old -3.07 was overfit to 18 players.
    LEAGUE_AVG_K = 25.0
    # Custom "full confidence": treat the entered stats as true talent and skip
    # the small-sample regression toward league average (real players never set
    # this flag, so the Converter is unaffected).
    fc = bool(data.get("full_confidence"))
    vis_trust = 1.0 if fc else min(pa / 200, 1.0)
    effective_k = vis_trust * bat["K_pct"] + (1 - vis_trust) * LEAGUE_AVG_K
    ratings["vision"] = clamp(-2.47 * effective_k + 118.1)

    # --- SPEED: Sprint speed dominant (refit RMSE 10.7 → 2.5) ---
    # At N=44, sprint speed alone explains almost everything. SB/162 drops to
    # near-zero weight (0.10 vs old 0.45). Much steeper sprint coefficient
    # (15.02 vs old 7.36) with lower intercept (-356.5 vs -147.1).
    sprint = data.get("sprint_speed")
    games_played = bat.get("G", 0) or 0
    games = max(bat["G"], 1)
    sb_per_162 = min(bat["SB"] / games * 162.0, 60.0)
    if sprint:
        raw_speed = max(15.02 * sprint + 0.10 * sb_per_162 - 356.5, 15)
        if games_played < 30 and not fc:
            # Regress toward position baseline for tiny samples
            pos_speed_baseline = TRACKING_SPEED_BASELINES.get(pos, 44)
            pos_speed_default = clamp(max(15.02 * 27.0 + 0.10 * sb_per_162 - 356.5, pos_speed_baseline))
            speed_trust = games_played / 30.0
            ratings["speed"] = clamp(speed_trust * raw_speed + (1 - speed_trust) * pos_speed_default)
        else:
            ratings["speed"] = clamp(raw_speed)
    elif bat.get("fg_spd"):
        # FanGraphs Spd metric (available back to ~2002)
        # Formula: Speed = 9.42 * FG_Spd + 19.1 (r=0.879)
        ratings["speed"] = clamp(9.42 * bat["fg_spd"] + 19.1)
        sprint = None
    else:
        # BBRef-era fallback: use attempts + triples + position archetype.
        # This avoids collapsing athletic pre-2015 players to the old SB-only floor.
        ratings["speed"] = estimate_speed_no_tracking(bat, pos)
        sprint = None

    # --- DISCIPLINE: 4.49 * BB% + 23.8 ---
    # Refit on 44-player set (RMSE 5.6, was 10.7→6.5). Slightly shallower
    # slope with higher intercept gives better calibration at scale.
    disc_trust = 1.0 if fc else min(pa / 200, 1.0)
    LEAGUE_AVG_BB = 8.0
    effective_bb = disc_trust * bat["BB_pct"] + (1 - disc_trust) * LEAGUE_AVG_BB
    ratings["discipline"] = clamp(4.49 * effective_bb + 23.8)

    # --- Sample-size regression for batting stats ---
    # When PA < 200, regress BA/ISO toward league average to prevent tiny-sample
    # extremes (Berroa: .000 BA in 6 PA → Contact 0, Show gives 46).
    LEAGUE_AVG_BA = 0.248
    LEAGUE_AVG_ISO = 0.155
    ba_trust = 1.0 if fc else min(pa / 200, 1.0)
    effective_ba = ba_trust * bat["BA"] + (1 - ba_trust) * LEAGUE_AVG_BA
    effective_iso = ba_trust * bat["ISO"] + (1 - ba_trust) * LEAGUE_AVG_ISO

    # --- CONTACT R: refit with split BA vs RHP ---
    # Old formula used overall BA in Statcast path (Turner .304 → 88 vs Show 61).
    # Show's Contact R reflects hitting quality vs RHP, so use split BA when
    # available. Refit on 18-player set: BA+EV RMSE=9.0, BA-only RMSE=10.1.
    avg_ev = data.get("avg_ev")
    # Get split BA vs RHP for Contact R (trust-blended with overall)
    ba_vr_raw = splits.get("vs_RHP", {}).get("BA")
    pa_vr = splits.get("vs_RHP", {}).get("PA", 0)
    trust_vr = min(pa_vr / 150, 1.0) if pa_vr and pa_vr > 0 else 0
    ba_for_cr = trust_vr * ba_vr_raw + (1 - trust_vr) * effective_ba if ba_vr_raw is not None else effective_ba

    # Contact R refit: EV dropped (hurts at N=44), BA-only RMSE=6.8 (was 8.2)
    if use_career:
        career_ba = career.get("BA", bat["BA"])
        blended_ba = 0.55 * ba_for_cr + 0.45 * career_ba
        ratings["contact_right"] = clamp(268 * blended_ba + 4.8)
    else:
        ratings["contact_right"] = clamp(268 * ba_for_cr + 4.8)

    # --- CONTACT L: BA-based (not OBP — keeps contact/vision/discipline cleanly separated) ---
    ba_vs_lhp = splits.get("vs_LHP", {}).get("BA", effective_ba)
    pa_vs_lhp = splits.get("vs_LHP", {}).get("PA", 0)
    trust_l = min(pa_vs_lhp / 80, 1.0) if pa_vs_lhp > 0 else 0
    if use_career:
        fallback_ba = career.get("BA", effective_ba) if isinstance(career, dict) else effective_ba
    else:
        fallback_ba = effective_ba
    contact_l_ba = trust_l * ba_vs_lhp + (1 - trust_l) * fallback_ba
    # Contact L refit: 212.7*BA + 18.7 (RMSE 10.4, was 11.4)
    ratings["contact_left"] = clamp(212.7 * contact_l_ba + 18.7)

    # --- HR RATE (used by Power R and Power L) ---
    # Dampened toward league avg (~3.0%) for small samples, same trust as BA/ISO.
    LEAGUE_AVG_HR_RATE = 0.030
    raw_hr_rate = bat["HR"] / max(pa, 1)
    hr_rate = ba_trust * raw_hr_rate + (1 - ba_trust) * LEAGUE_AVG_HR_RATE

    # --- POWER R: ISO + HR/PA refit (RMSE 19.1 → 17.5) ---
    # Adding HR rate captures sluggers whose ISO is modest but who hit bombs
    # (Turner: ISO .156 but 15 HR in 639 PA → Show 81; pure ISO gave 56).
    if use_career:
        career_iso = career.get("ISO", bat["ISO"])
        career_yearly = data.get("career_yearly", {})
        if career_yearly and len(career_yearly) > 1:
            yr_weights = {0: 0.45, -1: 0.30, -2: 0.15, -3: 0.10}
            tw, tiso = 0, 0
            for offset, w in yr_weights.items():
                y = data["year"] + offset
                if y in career_yearly:
                    tiso += career_yearly[y]["ISO"] * w
                    tw += w
            iso_blend = tiso / tw if tw > 0 else effective_iso
        else:
            iso_blend = effective_iso
    else:
        # Season only: trust-blend split ISO vs RHP toward overall ISO
        iso_vr = splits.get("vs_RHP", {}).get("ISO")
        pa_vr = splits.get("vs_RHP", {}).get("PA", 0)
        if iso_vr is not None and pa_vr > 0:
            trust_r = min(pa_vr / 200, 1.0)
            iso_blend = trust_r * iso_vr + (1 - trust_r) * effective_iso
        else:
            iso_blend = effective_iso
    # --- POWER R: split ISO vs RHP + HR rate (RMSE 8.3, was 8.6) ---
    # Using split ISO_vR gives ISO a real coefficient (87.1 vs near-zero 6.3).
    # Barrel% blended when available for robustness at scale.
    barrel = data.get("barrel_stats")
    brl_pct = barrel.get("brl_percent") if barrel else None
    pwr_r_trad = 87.1 * iso_blend + 352.5 * hr_rate + 43.4
    if brl_pct is not None and pa >= 100:
        pwr_r_barrel = 2.83 * brl_pct + 36.5
        ratings["power_right"] = clamp(0.6 * pwr_r_barrel + 0.4 * pwr_r_trad)
    else:
        ratings["power_right"] = clamp(pwr_r_trad)

    # --- POWER L: split ISO vs LHP + HR rate (RMSE 9.8, was 10.1) ---
    # Using split ISO_vL fixes the negative ISO coefficient (-60.7 → +55.1).
    # Both ISO and HR now have sensible positive weights.
    if use_career:
        iso_l = iso_blend  # career mode uses recency-weighted overall ISO
    else:
        iso_vl = splits.get("vs_LHP", {}).get("ISO")
        if iso_vl is not None and pa_vs_lhp > 0:
            trust_l_pwr = min(pa_vs_lhp / 80, 1.0)
            iso_l = trust_l_pwr * iso_vl + (1 - trust_l_pwr) * effective_iso
        else:
            iso_l = effective_iso
    pwr_l_trad = 55.1 * iso_l + 504.6 * hr_rate + 38.6
    if brl_pct is not None and pa >= 100:
        pwr_l_barrel = 2.24 * brl_pct + 38.7
        ratings["power_left"] = clamp(0.5 * pwr_l_barrel + 0.5 * pwr_l_trad)
    else:
        ratings["power_left"] = clamp(pwr_l_trad)

    # --- FIELDING: 2.09 * OAA + 74.6 (bias-corrected +6, was 68.6) ---
    # Minimum 200 innings for full trust in defensive metrics
    # Below that, blend with position baseline weighted by innings
    oaa_data = data.get("fielding_oaa", {})
    target_year = data["year"]
    pos_fielding_base = {
        "C": 70, "1B": 50, "2B": 75, "SS": 85, "3B": 65,
        "LF": 50, "CF": 75, "RF": 60, "DH": 35, "OF": 55,
    }

    # Adjust baseline down for players who barely play the field
    # Only apply DH-blend when we actually HAVE innings data — otherwise
    # we'd penalize every pre-2003 player as a DH just because FG didn't track innings
    inn_key = f"inn_{target_year}"
    has_innings_data = bool(oaa_data) and inn_key in oaa_data
    innings = oaa_data.get(inn_key, 0) if has_innings_data else 0
    games = bat["G"]
    expected_inn = games * 8.5

    if has_innings_data and games > 0:
        field_pct = innings / expected_inn if expected_inn > 0 else 0
        # Skip DH-blend when a fielding metric (Rdrs/Rtot) is present — the metric
        # itself is evidence the player is a real fielder, not a DH.
        has_rdrs_or_rtot = bool(oaa_data) and (
            f"rdrs_{target_year}" in oaa_data or f"rtot_{target_year}" in oaa_data
        )
        if field_pct < 0.3 and pos not in ("C", "DH") and not has_rdrs_or_rtot:
            # Player barely plays the field — blend baseline toward DH level
            dh_base = pos_fielding_base["DH"]
            pos_base = pos_fielding_base.get(pos, 55)
            pos_baseline = round(field_pct / 0.3 * pos_base + (1 - field_pct / 0.3) * dh_base)
        else:
            pos_baseline = pos_fielding_base.get(pos, 55)
    else:
        # No innings data (pre-2003 or data gap) — use straight position baseline
        pos_baseline = pos_fielding_base.get(pos, 55)

    # Trust factor: 0 at <50 inn, ramps to 1.0 at 500+ inn
    def_trust = 1.0 if fc else (max(0, min((innings - 50) / 450, 1.0)) if innings > 50 else 0)

    # Bug 4 fix: when innings data is absent but Rtot is available, apply a
    # fixed partial trust so Rtot meaningfully influences the fielding rating.
    if not has_innings_data and oaa_data:
        rtot_check = oaa_data.get(f"rtot_{target_year}")
        if rtot_check is not None:
            def_trust = RTOT_PARTIAL_TRUST

    # Check if we have actual OAA data (integer year keys) vs only string fallback keys
    has_oaa = any(isinstance(k, int) for k in oaa_data.keys()) if oaa_data else False

    if has_oaa:
        if use_career:
            total_w, total_oaa = 0, 0
            for offset, weight in FIELDING_YEAR_WEIGHTS.items():
                y = target_year + offset
                if y in oaa_data:
                    total_oaa += oaa_data[y] * weight
                    total_w += weight
            weighted_oaa = total_oaa / total_w if total_w > 0 else 0
            raw_fld = clamp(2.09 * weighted_oaa + 74.6)
        else:
            target_oaa = oaa_data.get(target_year)
            if target_oaa is not None:
                raw_fld = clamp(2.09 * target_oaa + 74.6)
            else:
                raw_fld = pos_baseline
        ratings["fielding"] = clamp(def_trust * raw_fld + (1 - def_trust) * pos_baseline)
    else:
        # Fall through chain: FG Def -> BBRef DRS+TZ blend -> BBRef DRS -> BBRef TZ -> baseline
        # Rdrs is essentially DRS (~-15..+20). Rtot is Total Zone (~-15..+15).
        # When both are available (2003-2019), blend them to smooth out
        # player-specific disagreements between the two systems.
        fg_def_val = oaa_data.get(f"def_{target_year}") if oaa_data else None
        rdrs_val   = oaa_data.get(f"rdrs_{target_year}") if oaa_data else None
        rtot_val   = oaa_data.get(f"rtot_{target_year}") if oaa_data else None

        rngr_val = oaa_data.get(f"rngr_{target_year}") if oaa_data else None

        if fg_def_val is not None:
            raw_fld = clamp(1.38 * fg_def_val + 73.3)
        elif rngr_val is not None:
            # RngR is the range-only UZR component (FG).  Calibrated against
            # Pedroia 2007 (RngR=0.56→73) and Sizemore 2008 (RngR=12.2→90).
            raw_fld = clamp(1.46 * rngr_val + 72.2)
        elif rdrs_val is not None and rtot_val is not None:
            # Both DRS and TZ available — blend their outputs to reduce
            # single-metric noise (e.g. DRS and UZR can disagree by 15+ runs).
            raw_from_rdrs = RDRS_FIELD_SLOPE * rdrs_val + RDRS_FIELD_INTERCEPT
            raw_from_rtot = RTOT_FIELD_SLOPE * rtot_val + RTOT_FIELD_INTERCEPT
            raw_fld = clamp(0.5 * raw_from_rdrs + 0.5 * raw_from_rtot)
        elif rdrs_val is not None:
            raw_fld = clamp(RDRS_FIELD_SLOPE * rdrs_val + RDRS_FIELD_INTERCEPT)
        elif rtot_val is not None:
            # Total Zone only — pre-2003 era or missing DRS.
            raw_fld = clamp(RTOT_FIELD_SLOPE * rtot_val + RTOT_FIELD_INTERCEPT)
        else:
            raw_fld = None

        if raw_fld is not None:
            ratings["fielding"] = clamp(def_trust * raw_fld + (1 - def_trust) * pos_baseline)
        else:
            ratings["fielding"] = pos_baseline

    # --- STEALING: refit on 18-player set (RMSE 15.9 → 8.6) ---
    # Regression found stealing ≈ 2.0*sb/162 + 9, with speed nearly zero-weight.
    # Show treats non-stealers (sb/162 < 2) as 3-7 regardless of speed.
    # sb_per_162 already computed above (capped at 60).
    speed_component = ratings["speed"]
    # Stealing refit on N=38 active stealers (RMSE 10.3, was 12.3)
    if sb_per_162 < 2:
        ratings["stealing"] = clamp(3 + 0.04 * speed_component)
    else:
        ratings["stealing"] = clamp(1.73 * sb_per_162 + 18.4)

    # --- BR AGGRESSIVENESS: refit (RMSE 14.3 → 9.9) ---
    # SB/162 dominates; sprint speed adds little beyond what SB captures.
    # Non-stealers get low floor (Rutschman 2, Dingler 6).
    # BR Agg refit on N=38 (RMSE 11.6, was 14.3)
    if sb_per_162 < 2:
        ratings["br_aggressiveness"] = clamp(3 + 0.03 * speed_component)
    else:
        ratings["br_aggressiveness"] = clamp(1.53 * sb_per_162 + 25.7)

    # --- DURABILITY ---
    # Show durability is a health/constitution rating, not just "did you play."
    # Young healthy players get 80+ even with limited MLB games.
    # The old formula (0.52*G + 15) gave 16 for a 2-game callup (Show: 82).
    # New formula: high floor (~72), gentle slope, caps near 99 at 155+ G.
    # Sample-size gate: below 50 PA, regress heavily toward position baseline.
    dur_pa_trust = min(pa / 200, 1.0)  # full trust at 200+ PA
    DUR_BASELINE = 78  # Show's implicit floor for healthy young players

    # Durability refit on N=44 (RMSE 3.9, was 5.2)
    if use_career:
        career_avg_gp = career.get("avg_G_per_year", bat["G"])
        gp = 0.55 * bat["G"] + 0.45 * career_avg_gp
        raw_dur = clamp(0.175 * gp + 67.6)
    else:
        raw_dur = clamp(0.175 * bat["G"] + 67.6)

    ratings["durability"] = clamp(dur_pa_trust * raw_dur + (1 - dur_pa_trust) * DUR_BASELINE)

    # --- ARM STRENGTH & ACCURACY ---
    # Priority: FG-era arm metrics > BBRef assists/errors/chances proxies > defaults
    oaa_data = data.get("fielding_oaa", {})
    target_year = data["year"]
    rarm = oaa_data.get(f"rarm_{target_year}")
    rngr = oaa_data.get(f"rngr_{target_year}")
    errr = oaa_data.get(f"errr_{target_year}")
    assists = oaa_data.get(f"ass_{target_year}")
    errors = oaa_data.get(f"err_{target_year}")
    chances = oaa_data.get(f"ch_{target_year}")
    arm_innings = oaa_data.get(f"inn_{target_year}")

    # --- CATCHER-SPECIFIC: arm strength from Statcast arm_mph (RMSE 2.4) ---
    catcher_stats = data.get("catcher_stats")
    if pos == "C" and catcher_stats and catcher_stats.get("arm_mph"):
        # Catcher arm: 4.95 * arm_mph - 337.6 (r=0.985, near-perfect fit)
        ratings["arm_strength"] = clamp(4.95 * catcher_stats["arm_mph"] - 337.6)
    elif pos in ("LF", "CF", "RF", "OF") and rarm is not None:
        ratings["arm_strength"] = clamp(3.9 * rarm + defaults["arm_str"])
    else:
        ratings["arm_strength"] = estimate_arm_strength_from_bbref(pos, defaults, assists, arm_innings)

    if errr is not None:
        ratings["arm_accuracy"] = clamp(3.0 * errr + defaults["arm_acc"])
    else:
        ratings["arm_accuracy"] = estimate_arm_accuracy_from_bbref(pos, defaults, errors, chances)

    # --- CATCHER-SPECIFIC: blocking and pop time ---
    if pos == "C":
        if catcher_stats and catcher_stats.get("pop_2b"):
            # Pop Time: -211.0 * pop_2b + 473.6 (RMSE 14.0, r=-0.559)
            # Partially scouting — raw pop doesn't capture everything Show uses.
            ratings["pop_time"] = clamp(-211.0 * catcher_stats["pop_2b"] + 473.6)
        else:
            ratings["pop_time"] = 55  # league average default

        # Blocking: highly correlated with Show fielding for catchers (r=0.929).
        # Formula: 0.75 * fielding + 13.3 (RMSE 5.2 on small N=5, but strong signal).
        # Uses the fielding rating we already computed above.
        ratings["blocking"] = clamp(0.75 * ratings["fielding"] + 13.3)
    else:
        ratings["pop_time"] = 0
        ratings["blocking"] = 0

    # --- REACTIONS: position-specific directional mapping ---
    # Use RngR (range) + OOZ to estimate overall reaction quality,
    # then distribute across directions based on position archetype
    # Determine base reaction from best available metric:
    # Priority: RngR (pre-2020 UZR component) > OAA (Statcast) > position default
    base_react = None

    if rngr is not None:
        # RngR: range runs, ~-10 to +15 -> 45 to 99
        base_react = clamp(2.0 * rngr + 65)
    elif oaa_data:
        if use_career:
            # Career mode: use recency-weighted OAA (same as fielding)
            total_w, total_oaa = 0, 0
            for offset, weight in FIELDING_YEAR_WEIGHTS.items():
                y = target_year + offset
                if y in oaa_data:
                    total_oaa += oaa_data[y] * weight
                    total_w += weight
            if total_w > 0:
                react_oaa = total_oaa / total_w
                base_react = clamp(1.5 * react_oaa + 65)
        else:
            # Season mode: target year OAA only
            target_oaa = oaa_data.get(target_year)
            if target_oaa is not None:
                base_react = clamp(1.5 * target_oaa + 65)

    # Bug 3 fix: use Rdrs/Rtot as range proxy when RngR/OAA are unavailable.
    # These branches are intentionally AFTER the RngR branch (RngR stays primary).
    # When both Rdrs and Rtot are available, blend them (same rationale as fielding).
    rdrs_react = oaa_data.get(f"rdrs_{target_year}") if oaa_data else None
    rtot_react = oaa_data.get(f"rtot_{target_year}") if oaa_data else None
    has_oaa_react = any(isinstance(k, int) for k in oaa_data.keys()) if oaa_data else False
    if base_react is None and not has_oaa_react:
        if rdrs_react is not None and rtot_react is not None:
            react_from_rdrs = RDRS_REACT_SLOPE * rdrs_react + 65
            react_from_rtot = RTOT_REACT_SLOPE * rtot_react + 65
            base_react = clamp(0.5 * react_from_rdrs + 0.5 * react_from_rtot)
        elif rdrs_react is not None:
            base_react = clamp(RDRS_REACT_SLOPE * rdrs_react + 65)
        elif rtot_react is not None:
            base_react = clamp(RTOT_REACT_SLOPE * rtot_react + 65)

    if base_react is not None and def_trust > 0:
        # Blend data-driven reactions with position defaults by innings confidence
        dir_weights = {
            "SS":  {"l": 0.85, "r": 1.15, "f": 1.05, "b": 0.90},
            "2B":  {"l": 0.95, "r": 1.05, "f": 1.10, "b": 0.85},
            "3B":  {"l": 0.90, "r": 0.95, "f": 1.15, "b": 0.90},
            "1B":  {"l": 1.05, "r": 0.95, "f": 0.85, "b": 0.95},
            "CF":  {"l": 1.00, "r": 1.00, "f": 0.95, "b": 0.95},
            "RF":  {"l": 0.95, "r": 0.95, "f": 0.85, "b": 0.95},
            "LF":  {"l": 0.95, "r": 0.90, "f": 0.85, "b": 0.95},
            "OF":  {"l": 0.95, "r": 0.93, "f": 0.87, "b": 0.93},
        }
        weights = dir_weights.get(pos, {"l": 1.0, "r": 1.0, "f": 1.0, "b": 0.9})

        for direction, key, default_key in [
            ("l", "reaction_left", "react_l"),
            ("r", "reaction_right", "react_r"),
            ("f", "reaction_forward", "react_f"),
            ("b", "reaction_back", "react_b"),
        ]:
            data_val = clamp(base_react * weights[direction])
            ratings[key] = clamp(def_trust * data_val + (1 - def_trust) * defaults[default_key])
    else:
        ratings["reaction_left"] = defaults["react_l"]
        ratings["reaction_right"] = defaults["react_r"]
        ratings["reaction_forward"] = defaults["react_f"]
        ratings["reaction_back"] = defaults["react_b"]

    # --- BATTING CLUTCH: BA + WAR + RISP BA refit (RMSE 18.3 → 16.5) ---
    # Adding RISP batting average captures situational performance that BA+WAR
    # miss. Negative BA coefficient encodes the "clutch differential" — given
    # equal RISP performance, a lower-BA hitter is more clutch (hits better in
    # big spots relative to overall). RISP data from Statcast (2015+); falls
    # back to BA+WAR for older players.
    war = bat.get("WAR", 0) or 0
    raw_ba = bat.get("BA", 0) or 0
    risp_ba = splits.get("risp_ba") if splits else None
    risp_pa = splits.get("risp_pa", 0) if splits else 0
    clutch_trust = 1.0 if fc else min(pa / 150, 1.0)

    # Clutch refit on N=42 (RMSE 9.3, was 13.4). BA coefficient flipped positive
    # at scale — higher BA + higher RISP = more clutch (old negative BA was overfit).
    if risp_ba is not None and risp_pa and risp_pa > 30:
        risp_trust = min(risp_pa / 100, 1.0)
        eff_risp = risp_trust * risp_ba + (1 - risp_trust) * raw_ba
        raw_clutch = 58.2 * raw_ba + 0.8 * war + 175.0 * eff_risp + 12.4
    else:
        # Pre-Statcast fallback: BA + WAR
        raw_clutch = 93 * raw_ba + 2.6 * war + 34

    ratings["batting_clutch"] = clamp(clutch_trust * raw_clutch + (1 - clutch_trust) * 50)
    ratings["bunting"] = defaults["bunt"]
    ratings["drag_bunt"] = defaults["drag"]

    return ratings


def calculate_overalls(ratings):
    """Calculate category overalls as simple averages (matching The Show's formula)."""
    hitting = [
        ratings["contact_right"], ratings["contact_left"],
        ratings["power_right"], ratings["power_left"],
        ratings["vision"], ratings["discipline"],
        ratings["batting_clutch"], ratings["bunting"], ratings["drag_bunt"],
    ]
    fielding = [
        ratings["fielding"], ratings["arm_strength"], ratings["arm_accuracy"],
        ratings["reaction_left"], ratings["reaction_right"],
        ratings["reaction_forward"], ratings["reaction_back"],
    ]
    # Catcher-specific attrs in fielding overall
    if ratings.get("blocking"):
        fielding.append(ratings["blocking"])
    if ratings.get("pop_time"):
        fielding.append(ratings["pop_time"])

    baserunning = [
        ratings["speed"], ratings["stealing"], ratings["br_aggressiveness"],
    ]

    return {
        "hitting": round(np.mean(hitting)),
        "fielding": round(np.mean(fielding)),
        "baserunning": round(np.mean(baserunning)),
        "durability": ratings["durability"],
    }


def calculate_pitcher_ratings(data, mode="season"):
    """Calculate all pitcher ratings from real stats.
    mode: 'season' = single season only, 'career' = career blended."""
    pit = data["pitching"]
    career = data.get("career_avg") or {}
    use_career = (mode == "career" and isinstance(career, dict) and career)
    sc = data.get("statcast") or {}
    role = data.get("role", "SP")

    ratings = {"position": "SP" if role == "SP" else "RP", "role": role}

    # --- SAMPLE SIZE DAMPENER ---
    if use_career:
        career_ip = career.get("total_IP", pit["IP"]) if isinstance(career, dict) else pit["IP"]
    else:
        career_ip = pit["IP"]
    fc = bool(data.get("full_confidence"))  # custom: skip small-sample regression
    trust = 1.0 if fc else min(career_ip / 200, 1.0)
    LEAGUE_AVG = 65  # default rating for an average pitcher attribute

    def dampen(raw_rating):
        """Blend raw formula output toward league average based on sample size."""
        return clamp(trust * raw_rating + (1 - trust) * LEAGUE_AVG)

    # --- VELOCITY (not dampened — velo is velo regardless of IP) ---
    # Optimal lstsq on 10 pitchers: 3.11*v - 214.1 (RMSE 9.4, r=0.576).
    # Show velocity is partly reputation-based (Crochet 96.3→99, Skubal
    # 97.5→77) so stat-derived accuracy is capped around r≈0.58.
    # Prior formula (2.8*v-193) had -8.5 bias; this restores correct slope.
    # Velocity refit on N=23 (RMSE 5.9, was 11.4). Shallower slope at scale.
    fb_velo = sc.get("avg_fb_velo") or pit.get("FB_velo") or 93.0
    ratings["velocity"] = clamp(2.19 * fb_velo - 117.3)

    # --- CONTROL: -0.7 * BB/9 - 71.2 * WHIP + 149.9 ---
    # BB/9 + WHIP combo: WHIP dominates (baserunner suppression matters more than walks alone)
    # Dampen-aware refit: RMSE 9.5 (was 10.5 with BB% alone)
    if use_career:
        career_bb9 = career.get("BB_per_9", pit["BB_per_9"])
        bb9_val = 0.5 * pit["BB_per_9"] + 0.5 * career_bb9
        career_whip = career.get("WHIP", pit["WHIP"])
        whip_val = 0.5 * pit["WHIP"] + 0.5 * career_whip
    else:
        bb9_val = pit["BB_per_9"]
        whip_val = pit["WHIP"]
    # Control refit on N=23 (RMSE 7.4, was 11.5). BB9 now dominates, WHIP positive.
    ratings["control"] = dampen(-14.04 * bb9_val + 26.0 * whip_val + 82.6)

    # --- HR/9: -7.0 * HR/9 + 96.3 ---
    # Dampen-aware refit: 1 pt HR/9 = 7 pts rating (meaningful but not too steep).
    # Old -13.87 was too steep after dampening (RMSE 13.8). Slopes -4 to -7 all
    # give RMSE ~6.1 on calibration set, so we pick -7 for conceptual soundness.
    if use_career:
        career_hr9 = career.get("HR_per_9", pit["HR_per_9"])
        hr9_val = 0.5 * pit["HR_per_9"] + 0.5 * career_hr9
    else:
        hr9_val = pit["HR_per_9"]
    # HR/9 refit on N=23 (RMSE 4.6, was 16.9). Much steeper slope at scale.
    ratings["hr_per_9"] = dampen(-27.73 * hr9_val + 95.4)

    # --- H/9 and K/9: compute per-split from Statcast BA/K% against ---
    vs_lhb = sc.get("vs_LHB", {})
    vs_rhb = sc.get("vs_RHB", {})
    has_splits = vs_lhb.get("PA", 0) >= 50 and vs_rhb.get("PA", 0) >= 50

    # Overall H/9 baseline
    if use_career:
        career_h9 = career.get("H_per_9", pit["H_per_9"])
        h9_blend = 0.5 * pit["H_per_9"] + 0.5 * career_h9
    else:
        h9_blend = pit["H_per_9"]

    # Overall K/9 baseline
    if use_career:
        career_kpct = career.get("K_pct", pit["K_pct"])
        kpct_blend = 0.5 * pit["K_pct"] + 0.5 * career_kpct
    else:
        kpct_blend = pit["K_pct"]

    if has_splits:
        # H/9 splits: NO DAMPENING when split data available (same fix as K/9).
        # Dampening caused -6 to -8 systematic bias. Coefficients from N=22 refit.
        ratings["h_per_9_left"] = clamp(-228.2 * vs_lhb["BA"] + 129.6)
        ratings["h_per_9_right"] = clamp(-187.7 * vs_rhb["BA"] + 120.7)

        # K/9 splits: NO DAMPENING when we have split data (PA >= 50).
        # Dampening was the primary cause of -8 to -10 systematic bias.
        # The regression coefficients (1.16/0.87) already compress the range
        # appropriately. Undampened RMSE: L=6.9, R=7.1 with zero bias.
        ratings["k_per_9_left"] = clamp(1.16 * vs_lhb["K_pct"] + 50.6)
        ratings["k_per_9_right"] = clamp(0.87 * vs_rhb["K_pct"] + 59.8)
    else:
        # No reliable splits — use overall and apply default platoon gap
        h9_avg = dampen(-7.86 * h9_blend + 131.1)
        k9_avg = dampen(2.5 * kpct_blend + 15)

        # Apply ~10% platoon split based on handedness
        throws = sc.get("throws", "R")
        # Platoon advantage is same-handed for BOTH hit-suppression and
        # strikeouts: a RHP is tougher on RHB (and a LHP on LHB) in each. The
        # higher H/9 rating = fewer hits, so same-hand gets the higher value in
        # both H/9 and K/9.
        if throws == "L":
            ratings["h_per_9_left"] = clamp(h9_avg * 1.08)
            ratings["h_per_9_right"] = clamp(h9_avg * 0.92)
            ratings["k_per_9_left"] = clamp(k9_avg * 1.10)
            ratings["k_per_9_right"] = clamp(k9_avg * 0.90)
        else:
            ratings["h_per_9_left"] = clamp(h9_avg * 0.92)
            ratings["h_per_9_right"] = clamp(h9_avg * 1.08)
            ratings["k_per_9_left"] = clamp(k9_avg * 0.90)
            ratings["k_per_9_right"] = clamp(k9_avg * 1.10)

    # --- STAMINA ---
    # Show gives all SPs a high baseline (~75) with modest extra credit per
    # start. Old formula (1.47*GS+46.1) under-predicted by 10-28 points for
    # SPs with shortened seasons (López 67 vs Show 95, Ragans 65 vs 90).
    # Optimal lstsq on 8 SPs: 0.62*GS + 75 (RMSE 8.4 vs old 18.5).
    # RP formula: 4.8*G - 268 fits perfectly on 2 calibration RPs, but with
    # only 2 data points we keep a conservative approach.
    # Stamina refit: SP N=20 RMSE 3.9 (was 19.4). Flatter slope — Show gives
    # most SPs similar stamina. RP formula: ~29 baseline (only 3 data points).
    if role == "RP" and pit["GS"] == 0:
        ratings["stamina"] = clamp(-0.054 * pit["G"] + 28.7)
    elif use_career:
        career_gs = career.get("avg_GS_per_year", pit["GS"]) if isinstance(career, dict) else pit["GS"]
        gs_blend = 0.4 * pit["GS"] + 0.6 * career_gs
        ratings["stamina"] = clamp(0.273 * gs_blend + 76.8)
    else:
        ratings["stamina"] = clamp(0.273 * pit["GS"] + 76.8)

    # --- BREAK: refit using Statcast pitch movement data (RMSE 8.5, was 14.8) ---
    # At N=22 with per-pitch break measurements:
    #   max_break + num_pitches + offspeed_usage -> RMSE 8.5
    # Max break on best pitch matters most. More offspeed = higher break.
    # Fewer distinct pitches (specialists) get a slight bonus.
    arsenal = sc.get("arsenal", [])
    if arsenal:
        pitch_types = [p for p in arsenal if p["usage"] > 5]
        num_pitches = len(pitch_types)
        offspeed_usage = sum(p["usage"] for p in arsenal if p["code"] not in ("FF",))

        # Compute max total break from per-pitch movement data
        max_break = 0
        for pitch in arsenal:
            tb = pitch.get("total_break_inches")
            if tb is not None and tb > max_break:
                max_break = tb

        # Break is near-uncorrelated with movement (r~0, a scouting attribute)
        # and Show breaks run high, so low-IP pitchers dampen toward the Show
        # Break mean (~78), not the generic 65 — the generic target was
        # systematically under-rating relievers (low IP -> crushed toward 65).
        BREAK_BASELINE = 78
        if max_break > 0:
            raw_break = 2.72 * max_break - 2.08 * num_pitches + 0.29 * offspeed_usage + 32.7
            ratings["break_"] = clamp(trust * clamp(raw_break) + (1 - trust) * BREAK_BASELINE)
        else:
            # No movement data — use pitch diversity heuristic as fallback
            base_break = 75 + max(0, (num_pitches - 2)) * 3 + offspeed_usage * 0.2
            ratings["break_"] = clamp(trust * clamp(base_break) + (1 - trust) * BREAK_BASELINE)
    else:
        ratings["break_"] = 80  # default when no arsenal data

    # --- PITCHING CLUTCH: 2.7 * WAR + 59.3 ---
    # Dampen-aware refit: RMSE 4.1 (was 8.6). Old coefficients (3.52/60.8) were
    # too steep after dampening compressed the range. Adding K/9 or BB/9 barely
    # helps (3.9 vs 4.1) — not worth the complexity.
    war = pit.get("WAR", 0)
    # Pit Clutch is ROLE-driven, not WAR-driven (calibration N=45: prior WAR-only
    # formula was anti-correlated, r=-0.26). Relievers get high Show clutch
    # regardless of IP, so they must NOT be IP-dampened (relievers inherently
    # have low IP, which wrongly crushed them toward 65). Fits: RP ~2*WAR+87,
    # SP ~3*WAR+64.
    if role == "RP":
        ratings["pitching_clutch"] = clamp(2.0 * war + 87)
    else:
        sp_trust = 1.0 if fc else min(career_ip / 120, 1.0)  # regress only very low-IP rookies
        ratings["pitching_clutch"] = clamp(sp_trust * (3.0 * war + 64) + (1 - sp_trust) * 64)

    # --- PITCHER FIELDING (mostly defaults) ---
    ratings["fielding"] = PITCHER_FIELDING_DEFAULTS["fielding"]
    ratings["arm_strength"] = PITCHER_FIELDING_DEFAULTS["arm_str"]
    ratings["arm_accuracy"] = PITCHER_FIELDING_DEFAULTS["arm_acc"]
    ratings["reaction_left"] = PITCHER_FIELDING_DEFAULTS["react_l"]
    ratings["reaction_right"] = PITCHER_FIELDING_DEFAULTS["react_r"]
    ratings["reaction_forward"] = PITCHER_FIELDING_DEFAULTS["react_f"]
    ratings["reaction_back"] = PITCHER_FIELDING_DEFAULTS["react_b"]

    # --- PITCHER HITTING (mostly 0) ---
    ratings["contact_right"] = 0
    ratings["contact_left"] = 0
    ratings["power_right"] = 0
    ratings["power_left"] = 0
    ratings["vision"] = 0
    ratings["discipline"] = 0
    ratings["batting_clutch"] = 0
    ratings["bunting"] = 35
    ratings["drag_bunt"] = 8

    # --- PITCHER BASERUNNING ---
    sprint = data.get("sprint_speed") or 27.0
    ratings["speed"] = clamp(max(15.01 * sprint - 353.5, 15))
    ratings["stealing"] = 8
    ratings["br_aggressiveness"] = 7

    # --- DURABILITY ---
    ratings["durability"] = clamp(0.13 * pit["G"] + 68)

    return ratings


def calculate_pitcher_overalls(ratings):
    """Calculate pitcher category overalls."""
    pitching = [
        ratings["h_per_9_left"], ratings["h_per_9_right"],
        ratings["k_per_9_left"], ratings["k_per_9_right"],
        ratings["hr_per_9"], ratings["pitching_clutch"],
        ratings["control"], ratings["velocity"],
        ratings["break_"], ratings["stamina"],
    ]
    fielding = [
        ratings["fielding"], ratings["arm_strength"], ratings["arm_accuracy"],
        ratings["reaction_left"], ratings["reaction_right"],
        ratings["reaction_forward"], ratings["reaction_back"],
    ]
    hitting = [
        ratings["contact_right"], ratings["contact_left"],
        ratings["power_right"], ratings["power_left"],
        ratings["vision"], ratings["discipline"],
        ratings["batting_clutch"], ratings["bunting"], ratings["drag_bunt"],
    ]
    baserunning = [
        ratings["speed"], ratings["stealing"], ratings["br_aggressiveness"],
    ]

    return {
        "pitching": round(np.mean(pitching)),
        "fielding": round(np.mean(fielding)),
        "hitting": round(np.mean(hitting)),
        "baserunning": round(np.mean(baserunning)),
        "durability": ratings["durability"],
    }


def display_pitcher_card(player_name, year, ratings, overalls, team=""):
    """Print a formatted pitcher card."""
    pos = ratings["position"]
    role = ratings.get("role", pos)
    W = 50

    def row(left_label, left_val, right_label=None, right_val=None):
        left = f"  {left_label:<20} {left_val:>2}"
        if right_label:
            right = f"  {right_label:<20} {right_val:>2}"
            line = f"|{left}{right}"
        else:
            line = f"|{left}"
        return f"{line:<{W}}|"

    def section_header(label, ovr):
        text = f"  {label}"
        ovr_text = f"OVR {ovr:>2}"
        pad = W - len(text) - len(ovr_text)
        return f"|{text}{' ' * pad}{ovr_text}|"

    print()
    print("+" + "=" * W + "+")
    title = f"  {player_name.upper()}"
    print(f"|{title:<{W}}|")
    subtitle = f"  {year}   {role}   {team}"
    print(f"|{subtitle:<{W}}|")
    print("+" + "-" * W + "+")

    # Pitching
    print(section_header("PITCHING", overalls["pitching"]))
    print(row("H/9 vs L", ratings["h_per_9_left"], "H/9 vs R", ratings["h_per_9_right"]))
    print(row("K/9 vs L", ratings["k_per_9_left"], "K/9 vs R", ratings["k_per_9_right"]))
    print(row("HR/9", ratings["hr_per_9"], "Pit Clutch", ratings["pitching_clutch"]))
    print(row("Control", ratings["control"], "Velocity", ratings["velocity"]))
    print(row("Break", ratings["break_"], "Stamina", ratings["stamina"]))
    print("+" + "-" * W + "+")

    # Fielding
    print(section_header("FIELDING", overalls["fielding"]))
    print(row("Fielding", ratings["fielding"], "Arm Strength", ratings["arm_strength"]))
    print(row("Arm Accuracy", ratings["arm_accuracy"], "Reaction L", ratings["reaction_left"]))
    print(row("Reaction R", ratings["reaction_right"], "Reaction F", ratings["reaction_forward"]))
    print(row("Reaction B", ratings["reaction_back"]))
    print("+" + "-" * W + "+")

    # Baserunning
    print(section_header("BASERUNNING", overalls["baserunning"]))
    print(row("Speed", ratings["speed"], "Stealing", ratings["stealing"]))
    print(row("BR Aggressiveness", ratings["br_aggressiveness"]))
    print("+" + "-" * W + "+")

    # Durability
    dur_text = f"  DURABILITY"
    dur_val = f"{overalls['durability']:>3}"
    pad = W - len(dur_text) - len(dur_val)
    print(f"|{dur_text}{' ' * pad}{dur_val}|")
    print("+" + "=" * W + "+")


def display_pitcher_verbose(data, ratings):
    """Show raw pitcher inputs."""
    pit = data["pitching"]
    print("\n  RAW INPUTS:")
    print(f"    ERA={pit['ERA']:.2f}  FIP={pit['FIP']:.2f}  IP={pit['IP']:.1f}  G={pit['G']}  GS={pit['GS']}")
    print(f"    K/9={pit['K_per_9']:.1f}  BB/9={pit['BB_per_9']:.1f}  HR/9={pit['HR_per_9']:.2f}  H/9={pit['H_per_9']:.1f}")
    print(f"    K%={pit['K_pct']:.1f}  BB%={pit['BB_pct']:.1f}  WHIP={pit['WHIP']:.3f}")
    print(f"    Role: {data.get('role', '?')}")
    sc = data.get("statcast", {})
    if sc.get("avg_fb_velo"):
        print(f"    FB Velo: avg={sc['avg_fb_velo']}, max={sc.get('max_fb_velo', '?')}")
    if sc.get("vs_LHB"):
        s = sc["vs_LHB"]
        print(f"    vs LHB: PA={s['PA']}, BA={s['BA']:.3f}, K%={s['K_pct']:.1f}")
    if sc.get("vs_RHB"):
        s = sc["vs_RHB"]
        print(f"    vs RHB: PA={s['PA']}, BA={s['BA']:.3f}, K%={s['K_pct']:.1f}")
    if data.get("career_avg"):
        ca = data["career_avg"]
        print(f"    Career: {ca.get('num_years', '?')} yrs, {ca.get('total_IP', '?'):.0f} IP")


# ================================================================
# DISPLAY
# ================================================================

def display_card(player_name, year, ratings, overalls, team=""):
    """Print a formatted MLB The Show-style rating card."""
    pos = ratings["position"]
    W = 50  # inner width

    def row(left_label, left_val, right_label=None, right_val=None):
        left = f"  {left_label:<20} {left_val:>2}"
        if right_label:
            right = f"  {right_label:<20} {right_val:>2}"
            line = f"|{left}{right}"
        else:
            line = f"|{left}"
        return f"{line:<{W}}|"

    def section_header(label, ovr):
        text = f"  {label}"
        ovr_text = f"OVR {ovr:>2}"
        pad = W - len(text) - len(ovr_text)
        return f"|{text}{' ' * pad}{ovr_text}|"

    print()
    print("+" + "=" * W + "+")
    title = f"  {player_name.upper()}"
    print(f"|{title:<{W}}|")
    subtitle = f"  {year}   {pos}   {team}"
    print(f"|{subtitle:<{W}}|")
    print("+" + "-" * W + "+")

    # Hitting
    print(section_header("HITTING", overalls["hitting"]))
    print(row("Contact vs Right", ratings["contact_right"], "Contact vs Left", ratings["contact_left"]))
    print(row("Power vs Right", ratings["power_right"], "Power vs Left", ratings["power_left"]))
    print(row("Vision", ratings["vision"], "Discipline", ratings["discipline"]))
    print(row("Batting Clutch", ratings["batting_clutch"], "Bunting", ratings["bunting"]))
    print(row("Drag Bunt", ratings["drag_bunt"]))
    print("+" + "-" * W + "+")

    # Fielding
    print(section_header("FIELDING", overalls["fielding"]))
    print(row("Fielding", ratings["fielding"], "Arm Strength", ratings["arm_strength"]))
    print(row("Arm Accuracy", ratings["arm_accuracy"], "Reaction L", ratings["reaction_left"]))
    print(row("Reaction R", ratings["reaction_right"], "Reaction F", ratings["reaction_forward"]))
    print(row("Reaction B", ratings["reaction_back"]))
    if ratings.get("blocking"):
        print(row("Blocking", ratings["blocking"], "Pop Time", ratings.get("pop_time", 0)))
    print("+" + "-" * W + "+")

    # Baserunning
    print(section_header("BASERUNNING", overalls["baserunning"]))
    print(row("Speed", ratings["speed"], "Stealing", ratings["stealing"]))
    print(row("BR Aggressiveness", ratings["br_aggressiveness"]))
    print("+" + "-" * W + "+")

    # Durability
    dur_text = f"  DURABILITY"
    dur_val = f"{overalls['durability']:>3}"
    pad = W - len(dur_text) - len(dur_val)
    print(f"|{dur_text}{' ' * pad}{dur_val}|")
    print("+" + "=" * W + "+")


def display_verbose(data, ratings):
    """Show the raw inputs used for each rating calculation."""
    bat = data["batting"]
    print("\n  RAW INPUTS:")
    print(f"    BA={bat['BA']:.3f}  OBP={bat['OBP']:.3f}  SLG={bat['SLG']:.3f}  ISO={bat['ISO']:.3f}")
    hr_rate_raw = bat['HR'] / max(bat.get('PA', 1), 1)
    print(f"    BB%={bat['BB_pct']:.1f}  K%={bat['K_pct']:.1f}  HR={bat['HR']}  HR/PA={hr_rate_raw:.3f}  SB={bat['SB']}  CS={bat.get('CS', 0)}  G={bat['G']}")
    if data.get("sprint_speed"):
        print(f"    Sprint Speed: {data['sprint_speed']:.1f}")
    if data.get("avg_ev"):
        print(f"    Avg Exit Velo: {data['avg_ev']:.1f}")
    if data.get("career_avg"):
        ca = data["career_avg"]
        print(f"    Career ISO: {ca.get('ISO', '?'):.3f}  Career BA: {ca.get('BA', '?'):.3f}  ({ca.get('num_years', '?')} yrs, {ca.get('total_PA', '?')} PA)")
    if data.get("fielding_oaa"):
        oaa_str = ", ".join(f"{y}:{v}" for y, v in sorted(data["fielding_oaa"].items(), key=lambda x: str(x[0])))
        print(f"    OAA by year: {oaa_str}")
    if data.get("splits"):
        for label in ["vs_RHP", "vs_LHP"]:
            s = data["splits"].get(label, {})
            if s:
                print(f"    {label}: PA={s.get('PA', 0)}, BA={s.get('BA', 0):.3f}, OBP={s.get('OBP', 0):.3f}, ISO={s.get('ISO', 0):.3f}")
        risp = data["splits"].get("risp_ba")
        risp_pa = data["splits"].get("risp_pa", 0)
        if risp is not None:
            print(f"    RISP: BA={risp:.3f} ({risp_pa} PA)")


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate MLB The Show-style player card from real stats")
    parser.add_argument("player_name", help="Player full name (e.g. 'Juan Soto')")
    parser.add_argument("year", type=int, help="Season year (e.g. 2025)")
    parser.add_argument("--position", "-p", help="Override position (C, 1B, 2B, SS, 3B, LF, CF, RF, DH)")
    parser.add_argument("--pitcher", action="store_true", help="Generate pitcher card")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw stat inputs")
    args = parser.parse_args()

    try:
        if args.pitcher:
            data = pull_all_pitcher_data(args.player_name, args.year)
            if data is None:
                sys.exit(1)

            ratings = calculate_pitcher_ratings(data)
            overalls = calculate_pitcher_overalls(ratings)
            team = data["pitching"].get("team", "")

            display_pitcher_card(args.player_name, args.year, ratings, overalls, team)

            if args.verbose:
                display_pitcher_verbose(data, ratings)
        else:
            data = pull_all_data(args.player_name, args.year)
            if data is None:
                sys.exit(1)

            ratings = calculate_ratings(data, args.position)
            overalls = calculate_overalls(ratings)
            team = data["batting"].get("team", "")

            display_card(args.player_name, args.year, ratings, overalls, team)

            if args.verbose:
                display_verbose(data, ratings)

    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        print(f"\nERROR: {e}")
        raise
