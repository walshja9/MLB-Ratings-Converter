"""Scrape MLB Pipeline team Top 30 lists + FanGraphs Board into
prospect_data/teams.json (canonical schema in docs/superpowers/specs/
2026-06-09-prospect-hub-design.md).

The Pipeline team page (mlb.com/milb/prospects/<slug>) is server-rendered with
an HTML-escaped Apollo GraphQL cache embedded in it. We unescape the page,
raw_decode the rankings array + Person entities out of the cache, and read the
tool grades from each prospect's bio text ("Scouting grades: Hit: 50 | ...").

Usage:
  python scrape_prospects.py --capture yankees   # save extracted payload to fixtures/
  python scrape_prospects.py --team yankees      # scrape one team (debug)
  python scrape_prospects.py                     # full 30-team run + FG merge
"""

import argparse
import html as _htmllib
import json
import os
import re
import sys
import time
import unicodedata
from json import JSONDecoder

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prospect_data")
_FIXTURE_DIR = os.path.join(_DIR, "fixtures")

# abbrev -> (mlb.com slug, display name)
TEAMS = {
    "ARI": ("diamondbacks", "Arizona Diamondbacks"),
    "ATH": ("athletics", "Athletics"),
    "ATL": ("braves", "Atlanta Braves"),
    "BAL": ("orioles", "Baltimore Orioles"),
    "BOS": ("red-sox", "Boston Red Sox"),
    "CHC": ("cubs", "Chicago Cubs"),
    "CIN": ("reds", "Cincinnati Reds"),
    "CLE": ("guardians", "Cleveland Guardians"),
    "COL": ("rockies", "Colorado Rockies"),
    "CWS": ("white-sox", "Chicago White Sox"),
    "DET": ("tigers", "Detroit Tigers"),
    "HOU": ("astros", "Houston Astros"),
    "KC":  ("royals", "Kansas City Royals"),
    "LAA": ("angels", "Los Angeles Angels"),
    "LAD": ("dodgers", "Los Angeles Dodgers"),
    "MIA": ("marlins", "Miami Marlins"),
    "MIL": ("brewers", "Milwaukee Brewers"),
    "MIN": ("twins", "Minnesota Twins"),
    "NYM": ("mets", "New York Mets"),
    "NYY": ("yankees", "New York Yankees"),
    "PHI": ("phillies", "Philadelphia Phillies"),
    "PIT": ("pirates", "Pittsburgh Pirates"),
    "SD":  ("padres", "San Diego Padres"),
    "SEA": ("mariners", "Seattle Mariners"),
    "SF":  ("giants", "San Francisco Giants"),
    "STL": ("cardinals", "St. Louis Cardinals"),
    "TB":  ("rays", "Tampa Bay Rays"),
    "TEX": ("rangers", "Texas Rangers"),
    "TOR": ("blue-jays", "Toronto Blue Jays"),
    "WSH": ("nationals", "Washington Nationals"),
}


def slugify(name):
    s = "".join(c for c in unicodedata.normalize("NFD", name)
                if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s


# ----------------------------------------------------------------------------
# MLB Pipeline
# ----------------------------------------------------------------------------

def fetch_pipeline_html(slug):
    """Plain GET of the (server-rendered) Pipeline team page. No JS needed."""
    import cloudscraper
    s = cloudscraper.create_scraper()
    r = s.get(f"https://www.mlb.com/milb/prospects/{slug}", timeout=45)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def extract_pipeline_data(raw_html):
    """Unescape the page and pull the Apollo cache pieces we need:
    the 30-entry rankings array + every Person entity. Returns
    {"rankings": [...], "persons": {"Person:806146": {...}, ...}}."""
    text = _htmllib.unescape(raw_html)
    dec = JSONDecoder()

    m = re.search(r'"getPlayerRankingsFromSelection\([^)]*\)":\s*\[', text)
    if not m:
        raise ValueError("rankings key not found in page (layout change?)")
    rankings, _ = dec.raw_decode(text, m.end() - 1)

    persons = {}
    for pm in re.finditer(r'"(Person:\d+)":\s*\{', text):
        key = pm.group(1)
        if key in persons:
            continue
        try:
            obj, _ = dec.raw_decode(text, pm.end() - 1)
        except ValueError:
            continue
        persons[key] = obj
    return {"rankings": rankings, "persons": persons}


# Pipeline bio grade label -> canonical grade key
_GRADE_LABELS = {
    "hit": "hit", "power": "power", "run": "run", "arm": "arm", "field": "field",
    "overall": "overall",
    "fastball": "fb", "slider": "sl", "curveball": "cb", "changeup": "ch",
    "cutter": "fc", "splitter": "fs", "sweeper": "st", "screwball": "sc",
    "knuckleball": "kn", "sinker": "si", "control": "control",
}


def _parse_grades_line(bio_html):
    """'<strong>Scouting grades:</strong> Hit: 50 | Power: 55 | ...' -> dict."""
    m = re.search(r"Scouting grades:\s*</strong>\s*([^<]+)", bio_html)
    if not m:
        m = re.search(r"Scouting grades:\s*([^<]+)", bio_html)
        if not m:
            return {}
    grades = {}
    for label, val in re.findall(r"([A-Za-z ]+):\s*(\d+)", m.group(1)):
        key = _GRADE_LABELS.get(label.strip().lower())
        if key:
            grades[key] = int(val)
    return grades


_PITCHER_POS = ("RHP", "LHP", "P", "SP", "RP")


def parse_pipeline_payload(payload):
    """Extracted {rankings, persons} -> list of canonical prospect dicts."""
    rankings = payload["rankings"]
    persons = payload.get("persons") or {}
    prospects = []
    for entry in rankings:
        pe = entry.get("playerEntity") or {}
        ref = (pe.get("player") or {}).get("__ref") or ""
        person = persons.get(ref, {})

        grades = {}
        for bio in pe.get("prospectBio") or []:
            grades = _parse_grades_line(bio.get("contentText") or "")
            if grades:
                break

        pos = (pe.get("position")
               or (person.get("primaryPosition") or {}).get("abbreviation") or "OF")
        pos = str(pos).upper()
        is_pitcher = pos in _PITCHER_POS or "fb" in grades

        first = person.get("useName") or ""
        last = person.get("useLastName") or ""
        name = f"{first} {last}".strip() or person.get("boxscoreName") or "Unknown"

        eta = pe.get("eta")
        try:
            eta = int(eta) if eta else None
        except (ValueError, TypeError):
            eta = None

        p = {
            "id": str(person.get("id") or slugify(name)),
            "rank": entry.get("rank"),
            "name": name,
            "pos": pos,
            "age": person.get("currentAge"),
            "bats": person.get("batSideCode"),
            "throws": person.get("pitchHandCode"),
            "height": person.get("height"),
            "weight": person.get("weight"),
            "eta": eta,
            "level": None,
            "is_pitcher": is_pitcher,
            "grades": grades,
            "fv": grades.get("overall"),
            "fv_source": "pipeline" if grades.get("overall") is not None else None,
        }
        if is_pitcher:
            p["role"] = "SP"
        prospects.append(p)
    prospects.sort(key=lambda x: x.get("rank") or 999)
    return prospects


def cmd_capture(slug):
    os.makedirs(_FIXTURE_DIR, exist_ok=True)
    payload = extract_pipeline_data(fetch_pipeline_html(slug))
    path = os.path.join(_FIXTURE_DIR, f"pipeline_{slug}_0.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": f"https://www.mlb.com/milb/prospects/{slug}",
                   "json": payload}, f, indent=1)
    print(f"saved {path}: {len(payload['rankings'])} rankings, "
          f"{len(payload['persons'])} persons")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", metavar="SLUG", help="capture extracted payload for one team")
    ap.add_argument("--team", metavar="SLUG", help="scrape a single team (debug)")
    args = ap.parse_args()
    if args.capture:
        cmd_capture(args.capture)
        sys.exit(0)
    print("full run implemented in Task 8")
