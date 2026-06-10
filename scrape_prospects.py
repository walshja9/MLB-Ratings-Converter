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
    "ARI": ("dbacks", "Arizona Diamondbacks"),
    "ATH": ("athletics", "Athletics"),
    "ATL": ("braves", "Atlanta Braves"),
    "BAL": ("orioles", "Baltimore Orioles"),
    "BOS": ("redsox", "Boston Red Sox"),
    "CHC": ("cubs", "Chicago Cubs"),
    "CIN": ("reds", "Cincinnati Reds"),
    "CLE": ("guardians", "Cleveland Guardians"),
    "COL": ("rockies", "Colorado Rockies"),
    "CWS": ("whitesox", "Chicago White Sox"),
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
    "TOR": ("bluejays", "Toronto Blue Jays"),
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


# ----------------------------------------------------------------------------
# FanGraphs Board (enrichment: FV, level, age, present/future grades)
# ----------------------------------------------------------------------------

FG_BOARD_URL = "https://www.fangraphs.com/prospects/the-board/2026-prospect-list"
FG_CSV_PATH = os.path.join(_DIR, "fangraphs_board.csv")


def capture_fg_board(headless=True):
    """Capture the Board's JSON API response via Playwright (Cloudflare-safe).
    Returns the raw JSON payload or None."""
    from playwright.sync_api import sync_playwright
    captured = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page()

        def on_response(resp):
            if "api" not in resp.url or "json" not in resp.headers.get("content-type", ""):
                return
            try:
                body = resp.json()
            except Exception:
                return
            blob = json.dumps(body)[:300000].lower()
            if '"fv"' in blob or '"cfv"' in blob or "future value" in blob:
                captured.append({"url": resp.url, "json": body})

        page.on("response", on_response)
        page.goto(FG_BOARD_URL, timeout=90000)
        page.wait_for_timeout(8000)
        browser.close()
    if not captured:
        return None
    # Prefer the largest payload (the full board, not a summary widget)
    captured.sort(key=lambda c: len(json.dumps(c["json"])), reverse=True)
    return captured[0]["json"]


FG_CACHE_PATH = os.path.join(_DIR, "fg_board_cache.json")


def load_fg_rows():
    """FG Board rows. Priority: manual CSV export > disk cache of a prior
    capture > live Playwright capture (HEADED — Cloudflare blocks headless).
    Returns list of dicts or [] (FG is enrichment — empty is non-fatal)."""
    if os.path.exists(FG_CSV_PATH):
        import csv
        with open(FG_CSV_PATH, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        print(f"  FG: using manual CSV ({len(rows)} rows)")
        return rows
    if os.path.exists(FG_CACHE_PATH):
        with open(FG_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(rows, list) and rows:
            print(f"  FG: using cached capture ({len(rows)} rows)")
            return rows
    try:
        payload = capture_fg_board(headless=False)
    except Exception as e:
        print(f"  FG Playwright failed: {e}")
        payload = None
    if payload is None:
        print("  WARNING: no FG data (export The Board CSV to prospect_data/fangraphs_board.csv)")
        return []
    with open(FG_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def parse_grade_pair(val):
    """FG '30/60' (present/future) -> (30, 60). Plain '55' -> (None, 55).
    Blank/None -> (None, None)."""
    if val is None:
        return None, None
    s = str(val).strip()
    if not s:
        return None, None
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            return int(float(a)), int(float(b))
        except ValueError:
            return None, None
    try:
        return None, int(float(s))
    except ValueError:
        return None, None


# Canonical grade key -> FG column aliases (CSV export label, board API field).
_FG_HIT_COLS = {"hit": ("Hit",), "power": ("Game Pwr", "Game"),
                "run": ("Spd",), "field": ("Fld",), "arm": ("Arm",)}
_FG_PITCH_COLS = {"fb": ("FB",), "sl": ("SL",), "cb": ("CB",), "ch": ("CH",),
                  "fc": ("CT",), "fs": ("SPL",), "control": ("CMD",)}
_PITCH_POS_TOKENS = ("RHP", "LHP", "P", "SP", "RP", "SIRP", "MIRP")

# FG org abbreviations that differ from ours (TEAMS keys).
_FG_ORG_ALIASES = {"CHW": "CWS", "KCR": "KC", "SDP": "SD", "SFG": "SF",
                   "TBR": "TB", "WSN": "WSH", "OAK": "ATH", "AZ": "ARI"}


def _fg_get(row, *names):
    """Fetch the first present key among names (exact, then lowercase)."""
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    lower = {str(k).lower(): v for k, v in row.items()}
    for n in names:
        v = lower.get(n.lower())
        if v not in (None, ""):
            return v
    return None


def parse_fg_row(row):
    """One FG Board row -> {name, org, fv, age, level, is_pitcher, role?,
    present: {...}, future: {...}} with canonical grade keys. None if unusable."""
    name = _fg_get(row, "Name", "playerName")
    org = _fg_get(row, "Org", "Team", "org") or ""
    if not name:
        return None
    name = str(name).strip()
    org = str(org).strip().upper()
    org = _FG_ORG_ALIASES.get(org, org)
    _, fv = parse_grade_pair(_fg_get(row, "FV", "cFV"))
    pos = str(_fg_get(row, "Pos", "Position", "pos") or "").strip().upper()
    is_pitcher = pos in _PITCH_POS_TOKENS
    cols = _FG_PITCH_COLS if is_pitcher else _FG_HIT_COLS
    present, future = {}, {}
    for key, aliases in cols.items():
        p, f = parse_grade_pair(_fg_get(row, *aliases))
        if p is not None:
            present[key] = p
        if f is not None:
            future[key] = f
    out = {"name": name, "org": org, "fv": fv, "is_pitcher": is_pitcher,
           "present": present, "future": future}
    age_raw = _fg_get(row, "Age")
    try:
        out["age"] = round(float(age_raw), 1) if age_raw is not None else None
    except (ValueError, TypeError):
        out["age"] = None
    lvl = _fg_get(row, "Current Level", "mlevel", "Level")
    out["level"] = str(lvl).strip() if lvl else None
    if is_pitcher and pos in ("SIRP", "MIRP", "RP"):
        out["role"] = "RP"
    return out


def cmd_capture(slug):
    os.makedirs(_FIXTURE_DIR, exist_ok=True)
    payload = extract_pipeline_data(fetch_pipeline_html(slug))
    path = os.path.join(_FIXTURE_DIR, f"pipeline_{slug}_0.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": f"https://www.mlb.com/milb/prospects/{slug}",
                   "json": payload}, f, indent=1)
    print(f"saved {path}: {len(payload['rankings'])} rankings, "
          f"{len(payload['persons'])} persons")


# ----------------------------------------------------------------------------
# Merge + validation + orchestration
# ----------------------------------------------------------------------------

_SUFFIXES = (" jr", " sr", " ii", " iii", " iv")


def normalize_match_name(name):
    s = "".join(c for c in unicodedata.normalize("NFD", name or "")
                if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z ]", "", s).strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return re.sub(r"\s+", " ", s)


def merge_fg(teams, fg_rows, aliases):
    """Layer FG Board data onto Pipeline prospects in place.
    Match on normalized name + org. aliases maps FG name -> Pipeline name.
    Returns list of unmatched FG rows ({name, org}) for the report."""
    index = {}
    for abbrev, t in teams.items():
        for p in t["prospects"]:
            index[(normalize_match_name(p["name"]), abbrev)] = p

    unmatched = []
    for row in fg_rows:
        if not row:
            continue
        name = aliases.get(row["name"], row["name"])
        key = (normalize_match_name(name), row.get("org", ""))
        p = index.get(key)
        if p is None:
            unmatched.append({"name": row["name"], "org": row.get("org", "")})
            continue
        if row.get("fv") is not None:
            p["fv"] = row["fv"]
            p["fv_source"] = "fangraphs"
        for k, v in (row.get("future") or {}).items():
            if k != "raw_power":          # canonical schema has no raw_power slot
                p["grades"][k] = v
        if row.get("present"):
            p["grades_present"] = {k: v for k, v in row["present"].items()
                                   if k != "raw_power"}
        if row.get("age") is not None:
            p["age"] = row["age"]
        if row.get("level"):
            p["level"] = row["level"]
        if row.get("role") == "RP":
            p["role"] = "RP"
    return unmatched


_EXPECTED_HIT = ("hit", "power", "run", "arm", "field")
_EXPECTED_PIT = ("fb", "control")


def validate_teams(teams):
    """Fill missing expected grades with 50 + set grades_incomplete.
    Returns human-readable warnings (short teams, incomplete prospects)."""
    warnings = []
    for abbrev, t in teams.items():
        n = len(t["prospects"])
        if n != 30:
            warnings.append(f"{abbrev}: {n} prospects (expected 30)")
        for p in t["prospects"]:
            expected = _EXPECTED_PIT if p.get("is_pitcher") else _EXPECTED_HIT
            missing = [k for k in expected if p["grades"].get(k) is None]
            if missing:
                p["grades_incomplete"] = True
                for k in missing:
                    p["grades"][k] = 50
                warnings.append(f"{abbrev}/{p['name']}: defaulted {','.join(missing)}")
            else:
                p.setdefault("grades_incomplete", False)
    return warnings


def scrape_team(abbrev, slug):
    """Fetch + parse one team's Top 30. Raises on failure."""
    payload = extract_pipeline_data(fetch_pipeline_html(slug))
    prospects = parse_pipeline_payload(payload)
    if not prospects:
        raise RuntimeError(f"no prospects parsed for {abbrev} ({slug})")
    return prospects


def main(single_team=None):
    os.makedirs(_DIR, exist_ok=True)
    aliases = {}
    alias_path = os.path.join(_DIR, "name_aliases.json")
    if os.path.exists(alias_path):
        with open(alias_path, "r", encoding="utf-8") as f:
            aliases = json.load(f)

    # Merge into any existing dataset so partial re-runs (one team, retries
    # after a failure) don't clobber the teams already scraped.
    out_path = os.path.join(_DIR, "teams.json")
    teams = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                teams = json.load(f).get("teams", {})
        except ValueError:
            teams = {}
    wanted = None if single_team is None else set(single_team.split(","))
    items = [(a, s) for a, (s, _) in TEAMS.items()
             if wanted is None or s in wanted or a in wanted]
    for abbrev, slug in items:
        print(f"Scraping {abbrev} ({slug})...")
        try:
            teams[abbrev] = {"name": TEAMS[abbrev][1],
                             "prospects": scrape_team(abbrev, slug)}
            print(f"  {len(teams[abbrev]['prospects'])} prospects")
        except Exception as e:
            print(f"  FAILED {abbrev}: {e}")
        time.sleep(2)   # be polite

    print("Loading FanGraphs Board...")
    fg_rows = [parse_fg_row(r) for r in load_fg_rows()]
    unmatched = merge_fg(teams, [r for r in fg_rows if r], aliases)
    if unmatched:
        rpt = os.path.join(_DIR, "fg_unmatched.json")
        with open(rpt, "w", encoding="utf-8") as f:
            json.dump(unmatched, f, indent=1)
        print(f"  {len(unmatched)} FG rows unmatched -> {rpt} (fix via name_aliases.json)")

    for w in validate_teams(teams):
        print(f"  WARN: {w}")

    from datetime import date
    out = {"season": 2026, "scraped": date.today().isoformat(), "teams": teams}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    total = sum(len(t["prospects"]) for t in teams.values())
    print(f"Wrote {out_path}: {len(teams)} teams, {total} prospects")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", metavar="SLUG", help="capture extracted payload for one team")
    ap.add_argument("--team", metavar="SLUG", help="scrape a single team (debug)")
    args = ap.parse_args()
    if args.capture:
        cmd_capture(args.capture)
        sys.exit(0)
    main(single_team=args.team)
