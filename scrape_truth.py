"""
Scrape per-attribute player ratings from theshowratings.com.

Builds a comprehensive ground-truth dataset for calibrating the rating engine.
Pulls player lists by position, then scrapes individual player pages for all
attributes (hitting, fielding, pitching, baserunning, durability).

Output: show_truth.json with separate hitter and pitcher dicts keyed by player name.

Usage:
  python scrape_truth.py                    # full scrape (~3-5 min)
  python scrape_truth.py --hitters-only     # hitters only
  python scrape_truth.py --pitchers-only    # pitchers only
  python scrape_truth.py --max-per-pos 10   # limit per position (for testing)
  python scrape_truth.py --player "Aaron Judge"  # single player test
"""

import sys
import os
import re
import json
import time
import argparse
from urllib.parse import urljoin

_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://www.theshowratings.com"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "show_truth.json")
REQUEST_DELAY = 1.0  # seconds between requests — be polite

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "desktop": True}
)


# ================================================================
# ATTRIBUTE NAME MAPPING
# ================================================================
# Map theshowratings.com attribute names → our internal key names.
# Handles both the full name and abbreviation forms.

HITTER_ATTR_MAP = {
    "contact vs right": "con_r",
    "con r": "con_r",
    "contact vs left": "con_l",
    "con l": "con_l",
    "power vs right": "pwr_r",
    "pwr r": "pwr_r",
    "power vs left": "pwr_l",
    "pwr l": "pwr_l",
    "vision": "vision",
    "plate discipline": "disc",
    "disc": "disc",
    "batting clutch": "clutch",
    "bat clutch": "clutch",
    "bunting": "bunt",
    "drag bunt": "drag",
    "drg bunt": "drag",
    "durability": "dur",
    "fielding": "fielding",
    "arm strength": "arm_str",
    "arm str": "arm_str",
    "arm accuracy": "arm_acc",
    "arm acc": "arm_acc",
    "reaction left": "react_l",
    "reac l": "react_l",
    "reaction right": "react_r",
    "reac r": "react_r",
    "reaction forward": "react_f",
    "reac f": "react_f",
    "reaction back": "react_b",
    "reac b": "react_b",
    "speed": "speed",
    "stealing": "stealing",
    "baserunning aggressiveness": "br_agg",
    "br agg": "br_agg",
}

PITCHER_ATTR_MAP = {
    "hits per 9 vs l": "h9_l",
    "h/9 l": "h9_l",
    "h/9 vs l": "h9_l",
    "hits per 9 vs r": "h9_r",
    "h/9 r": "h9_r",
    "h/9 vs r": "h9_r",
    "strikeouts per 9 vs l": "k9_l",
    "k/9 l": "k9_l",
    "k/9 vs l": "k9_l",
    "strikeouts per 9 vs r": "k9_r",
    "k/9 r": "k9_r",
    "k/9 vs r": "k9_r",
    "home runs per 9": "hr9",
    "hr/9": "hr9",
    "pitching clutch": "clutch",
    "pit clutch": "clutch",
    "control": "ctrl",
    "velocity": "velo",
    "break": "brk",
    "stamina": "stam",
    # Pitchers also have fielding/hitting/baserunning on the site
    "durability": "dur",
    "fielding": "fielding",
    "speed": "speed",
}


# ================================================================
# FETCHING HELPERS
# ================================================================

def fetch_page(url):
    """Fetch a page with rate limiting and error handling."""
    time.sleep(REQUEST_DELAY)
    try:
        r = _scraper.get(url, timeout=30)
        if r.status_code != 200:
            print(f"    WARNING: {r.status_code} for {url}")
            return None
        return r.text
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}")
        return None


def parse_player_list(html):
    """Parse a position list page and extract player slugs + names + OVRs."""
    soup = BeautifulSoup(html, "html.parser")
    players = []

    # Find all links that point to player pages
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Player page links are like /player-slug (no /lists/, /teams/, etc.)
        if not href:
            continue
        # Normalize to just the path
        if href.startswith(BASE_URL):
            path = href[len(BASE_URL):]
        elif href.startswith("/"):
            path = href
        else:
            continue

        # Skip non-player links
        if any(path.startswith(p) for p in ["/lists", "/teams", "/countries",
                                             "/about", "/privacy", "/contact",
                                             "/wp-", "/#", "/page"]):
            continue
        if path in ("/", ""):
            continue

        slug = path.strip("/")
        # Player slugs are lowercase, hyphenated names (no further slashes)
        if "/" in slug or not slug:
            continue
        # Skip if slug looks like a generic page
        if slug in ("about", "privacy-policy", "contact", "search"):
            continue

        name = a.get_text(strip=True)
        if not name or len(name) < 3:
            continue

        players.append({"slug": slug, "name": name})

    # Deduplicate by slug
    seen = set()
    unique = []
    for p in players:
        if p["slug"] not in seen:
            seen.add(p["slug"])
            unique.append(p)

    return unique


def parse_player_page(html, player_name):
    """Parse an individual player page and extract all attribute ratings.

    Uses two parsing strategies:
    1. HTML structure: <li> elements with two <span> children (label + value)
    2. Regex fallback on raw text for sites that flatten the markup
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Extract OVR ---
    # Pattern 1: "99 MLB The Show 26 Rating" (appears in page body)
    # Pattern 2: "Overall Rating of 99"
    # Pattern 3: standalone <h2> with just the number
    ovr = None
    text = soup.get_text()

    ovr_patterns = [
        r"(\d{2,3})\s+MLB The Show\s+\d+\s+Rating",
        r"Overall Rating of\s+(\d{2,3})",
        r"(?:Overall|OVR)\s*(?:Rating)?\s*:?\s*(\d{2,3})",
    ]
    for pattern in ovr_patterns:
        m = re.search(pattern, text)
        if m:
            ovr = int(m.group(1))
            break

    # Fallback: <h2> with standalone number
    if ovr is None:
        for h2 in soup.find_all("h2"):
            h2_text = h2.get_text(strip=True)
            if re.match(r"^\d{2,3}$", h2_text):
                val = int(h2_text)
                if 1 <= val <= 99:
                    ovr = val
                    break

    # --- Parse attributes from <li> elements ---
    raw_attrs = {}

    # Strategy 1: <li> with <span> children
    for li in soup.find_all("li"):
        spans = li.find_all("span")
        if len(spans) >= 2:
            label = spans[0].get_text(strip=True)
            val_text = spans[-1].get_text(strip=True)
            if re.match(r"^\d{1,3}$", val_text):
                value = int(val_text)
                if 0 <= value <= 99:
                    # Extract abbreviation from parentheses if present
                    paren_match = re.search(r"\(([A-Z\s/0-9]+)\)", label)
                    if paren_match:
                        abbrev = paren_match.group(1).strip().lower()
                        raw_attrs[abbrev] = value
                    # Also store by cleaned full name
                    clean_name = re.sub(r"\s*\([^)]*\)\s*", "", label).strip().lower()
                    if clean_name:
                        raw_attrs[clean_name] = value

    # Strategy 2: regex fallback on full text (if strategy 1 found < 10 attrs)
    if len(raw_attrs) < 10:
        text = soup.get_text(separator="\n")
        attr_pattern = re.compile(
            r"([A-Za-z\s/]+?)\s*(?:\(([A-Z\s/0-9]+)\))?\s*(\d{1,2})\s*$",
            re.MULTILINE,
        )
        for match in attr_pattern.finditer(text):
            attr_name = match.group(1).strip()
            abbrev = (match.group(2) or "").strip()
            value = int(match.group(3))
            key_text = abbrev.lower() if abbrev else attr_name.lower()
            if key_text not in raw_attrs:
                raw_attrs[key_text] = value
            clean = attr_name.lower()
            if clean not in raw_attrs:
                raw_attrs[clean] = value

    # --- Detect player type ---
    text_lower = soup.get_text().lower()
    is_pitcher = ("pitching clutch" in text_lower or "pit clutch" in text_lower
                  or "hits per 9" in text_lower or "h/9" in text_lower)

    # Map to our internal attribute names
    if is_pitcher:
        mapped = _map_attrs(raw_attrs, PITCHER_ATTR_MAP)
        pitcher_keys = {"h9_l", "h9_r", "k9_l", "k9_r", "ctrl", "velo", "stam"}
        has_pitching = len(pitcher_keys.intersection(mapped.keys())) >= 4
        if not has_pitching:
            is_pitcher = False
            mapped = _map_attrs(raw_attrs, HITTER_ATTR_MAP)
    else:
        mapped = _map_attrs(raw_attrs, HITTER_ATTR_MAP)

    if ovr is not None:
        mapped["ovr"] = ovr

    return mapped, is_pitcher


def _map_attrs(raw_attrs, attr_map):
    """Map raw attribute names to our internal keys using the mapping dict."""
    result = {}
    for raw_key, raw_val in raw_attrs.items():
        canonical = attr_map.get(raw_key)
        if canonical and canonical not in result:
            result[canonical] = raw_val
    return result


# ================================================================
# MAIN SCRAPING LOGIC
# ================================================================

POSITION_LISTS = {
    "catchers": "/lists/catchers",
    "infielders": "/lists/infielders",
    "outfielders": "/lists/outfielders",
    "designated-hitters": "/lists/designated-hitters",
}

PITCHER_LISTS = {
    "pitchers": "/lists/pitchers",
}


def scrape_player_list(list_path, max_players=None):
    """Scrape a position list page for player slugs."""
    url = BASE_URL + list_path
    print(f"  Fetching player list: {url}")
    html = fetch_page(url)
    if not html:
        return []

    players = parse_player_list(html)
    print(f"    Found {len(players)} players")

    if max_players:
        players = players[:max_players]
    return players


def scrape_player(slug, player_name=None):
    """Scrape an individual player page for all attributes."""
    url = f"{BASE_URL}/{slug}"
    display_name = player_name or slug
    print(f"    Scraping {display_name}...", end="", flush=True)

    html = fetch_page(url)
    if not html:
        print(" FAILED")
        return None, None

    attrs, is_pitcher = parse_player_page(html, display_name)

    if not attrs or len(attrs) < 5:
        print(f" only {len(attrs)} attrs found, skipping")
        return None, None

    # Extract actual player name from page if not provided
    if not player_name:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title")
        if title:
            # Title is usually "Player Name - MLB The Show 26 Ratings"
            player_name = title.get_text().split("-")[0].strip()
            player_name = re.sub(r"\s*MLB The Show.*", "", player_name).strip()

    ovr = attrs.get("ovr", "?")
    attr_count = len([k for k in attrs if k != "ovr"])
    print(f" OVR={ovr}, {attr_count} attrs, {'pitcher' if is_pitcher else 'hitter'}")

    return {"name": player_name or slug, "attrs": attrs, "is_pitcher": is_pitcher}, is_pitcher


def scrape_all(max_per_pos=None, hitters_only=False, pitchers_only=False):
    """Scrape all position lists and individual player pages."""
    hitter_truth = {}
    pitcher_truth = {}

    # Scrape hitter positions
    if not pitchers_only:
        for pos_name, list_path in POSITION_LISTS.items():
            print(f"\n=== {pos_name.upper()} ===")
            players = scrape_player_list(list_path, max_per_pos)

            for p in players:
                # Skip if we already have this player
                if p["name"] in hitter_truth or p["name"] in pitcher_truth:
                    continue

                result, is_pitcher = scrape_player(p["slug"], p["name"])
                if result is None:
                    continue

                if is_pitcher:
                    pitcher_truth[result["name"]] = result["attrs"]
                else:
                    hitter_truth[result["name"]] = result["attrs"]

    # Scrape pitchers
    if not hitters_only:
        for pos_name, list_path in PITCHER_LISTS.items():
            print(f"\n=== {pos_name.upper()} ===")
            players = scrape_player_list(list_path, max_per_pos)

            for p in players:
                if p["name"] in pitcher_truth or p["name"] in hitter_truth:
                    continue

                result, is_pitcher = scrape_player(p["slug"], p["name"])
                if result is None:
                    continue

                if is_pitcher:
                    pitcher_truth[result["name"]] = result["attrs"]
                else:
                    hitter_truth[result["name"]] = result["attrs"]

    return hitter_truth, pitcher_truth


def scrape_single_player(player_name):
    """Scrape a single player by name (for testing)."""
    slug = player_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
    # Handle Jr., Sr., etc.
    slug = slug.replace("jr-", "jr").replace("sr-", "sr")
    slug = re.sub(r"-+", "-", slug).strip("-")

    result, is_pitcher = scrape_player(slug, player_name)
    if result:
        return {result["name"]: result["attrs"]}, is_pitcher
    return None, None


def save_truth(hitter_truth, pitcher_truth, output_path=OUTPUT_FILE):
    """Save truth data to JSON."""
    data = {
        "metadata": {
            "source": "theshowratings.com",
            "game": "MLB The Show 26",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "hitter_count": len(hitter_truth),
            "pitcher_count": len(pitcher_truth),
        },
        "hitters": hitter_truth,
        "pitchers": pitcher_truth,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved to {output_path}")
    print(f"  Hitters: {len(hitter_truth)}")
    print(f"  Pitchers: {len(pitcher_truth)}")


def load_truth(path=OUTPUT_FILE):
    """Load cached truth data from JSON."""
    if not os.path.exists(path):
        return None, None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("hitters", {}), data.get("pitchers", {})


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape MLB The Show 26 ratings from theshowratings.com")
    parser.add_argument("--max-per-pos", type=int, default=None,
                        help="Max players per position list (for testing)")
    parser.add_argument("--hitters-only", action="store_true")
    parser.add_argument("--pitchers-only", action="store_true")
    parser.add_argument("--player", type=str, default=None,
                        help="Scrape a single player by name (test mode)")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE)
    args = parser.parse_args()

    print("\n  MLB The Show 26 — Rating Scraper")
    print(f"  Source: {BASE_URL}\n")

    if args.player:
        result, is_pitcher = scrape_single_player(args.player)
        if result:
            print(f"\n  Result ({'pitcher' if is_pitcher else 'hitter'}):")
            for name, attrs in result.items():
                print(f"    {name}:")
                for k, v in sorted(attrs.items()):
                    print(f"      {k}: {v}")
        else:
            print(f"  Could not find {args.player}")
    else:
        hitters, pitchers = scrape_all(
            max_per_pos=args.max_per_pos,
            hitters_only=args.hitters_only,
            pitchers_only=args.pitchers_only,
        )
        save_truth(hitters, pitchers, args.output)
