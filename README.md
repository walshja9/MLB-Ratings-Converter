# MLB The Show 26 — Player Card Generator

A reverse-engineered MLB The Show 26 rating system. Type a player name and a year, get back a Show-style attribute card built from real MLB stats.

Works for any season from the deadball era to today — Nap Lajoie 1897, Sandy Koufax 1965, Barry Bonds 1995, Bobby Witt Jr. 2025.

## What it does

- Pulls real MLB stats from Baseball-Reference and Baseball Savant (Statcast)
- Maps them to MLB The Show 26 attributes (Vision, Discipline, Power L/R, Contact L/R, Speed, Fielding, Reactions, Arm, Pitcher Velocity, Break, Control, Stamina, etc.)
- Generates a full card with a 0–99 OVR badge, color-coded by tier
- Compare two players side by side
- Auto-detects pitcher vs hitter
- Pre-Statcast eras get era-appropriate fallbacks (Total Zone for fielding, SB-based speed, manual arsenal overrides for pre-2008 pitchers)

<img width="2551" height="1307" alt="image" src="https://github.com/user-attachments/assets/b996773d-9164-4d94-90a8-3689bcab655f" />


## Quick start

```bash
git clone https://github.com/<you>/mlb-show-card-generator.git
cd mlb-show-card-generator
python -m venv venv
venv/Scripts/activate            # Windows
# source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

Defaults to localhost only. To reach it from your phone on the same WiFi, set `MLBSHOW_EXPOSE_LAN=1` before running — this exposes write endpoints to your whole network.

CLI works too:
```bash
python generate_card.py "Juan Soto" 2025
python generate_card.py "Tarik Skubal" 2025 --pitcher
python generate_card.py "Barry Bonds" 1995 --position LF
```

## How the ratings work

Each Show attribute is mapped to a real stat with the strongest correlation:

| Attribute     | Formula                                                       |
|---------------|---------------------------------------------------------------|
| Vision        | `-2.55 * K% + 121.3`                                          |
| Discipline    | `4.86 * BB% + 17.2`                                           |
| Contact R     | `374.6 * BA + 2.30 * Exit_Velo - 217.4` (Statcast era)        |
| Contact L     | `347.6 * blended_BA - 13.7` (PA-trust-weighted vs LHP)        |
| Power R/L     | `~336 * ISO + 4` / `~244 * ISO + 17`                          |
| Speed         | `15.01 * Sprint_Speed - 353.5` or SB-based fallback           |
| Stealing      | `0.6 * (1.88*SB + 18.5) + 0.4 * Speed`                        |
| Fielding      | OAA → DRS (Rdrs) → Total Zone (Rtot) → position baseline      |
| Pitcher Velo  | `3.14 * FB_Velo - 208.2`                                      |
| Pitcher Ctrl  | `-4.44 * BB% + 104.9`                                         |
| Pitcher K/9   | `2.2 * K%_split + 15` per LHB/RHB split                       |

The OVR formulas were fit by least squares against a hand-labeled calibration set of real Show 26 cards (regression refit 2026-04-07 after migrating off FanGraphs).

## Data sources

- **Baseball Savant (Statcast)** — sprint speed, exit velocity, OAA, pitch arsenal, pitch-by-pitch splits. 2015+.
- **Baseball-Reference** — season batting/pitching/fielding leaderboards, including Total Zone (Rtot) and DRS (Rdrs) for the eras where they're available. Scraped directly via `cloudscraper` + `pandas.read_html` in `bbref_scraper.py`.
- **Chadwick Bureau** — player ID lookups (`pybaseball.playerid_lookup`).

FanGraphs is unreachable as of 2026-04 (Cloudflare interactive challenge). FG-only metrics like `Spd`, `BsR`, `Def`, and `RngR` are returned as `NaN` and the ratings code falls back to alternative inputs gracefully.

## Pre-Statcast tiers

| Era       | Speed                  | Fielding             | Contact                | Pitch Arsenal |
|-----------|------------------------|----------------------|------------------------|---------------|
| 2015+     | Sprint Speed           | OAA                  | BA + Exit Velo         | Statcast      |
| 2003–2014 | SB-based fallback      | DRS (BBRef Rdrs)     | BA only                | None          |
| 1953–2002 | SB-based fallback      | Total Zone (Rtot)    | BA only                | Manual override |
| Pre-1953  | SB-based fallback      | Position baseline    | BA only                | Manual override |

## Pitch arsenals before Statcast

For pitchers before the 2008 pitch-tracking era, real arsenals are stored in `pitcher_arsenals.json`. Cards display these with an "EST." badge so you don't mistake reference arsenals for measured data. Add your own by appending to the JSON — no code change needed.

## Project structure

```
generate_card.py        # Core: data pulls, attribute formulas, OVR estimation
app.py                  # Flask web app (localhost:5000)
bbref_scraper.py        # Direct Baseball-Reference scraper
pitcher_arsenals.json   # Manual pre-2008 arsenals
recalibrate.py          # OVR coefficient refitter (NNLS)
templates/              # Web UI templates
```

## Caveats

- The OVR formulas are fit on a small calibration set (~11 hitters, ~10 pitchers). Speed-first hitters are systematically under-predicted because the calibration set lacks variance separating speed from contact ability. Working on growing the set.
- Pre-2008 pitcher arsenals are reference estimates from scouting sources, not measured pitch data. Marked clearly in the UI.
- Pitcher Break is heuristic-based — no measurable stat correlates strongly with Show's Break rating.
- Pitcher Velocity overrates soft-tossers under ~93 mph.

## Running tests

Install test dependencies (pytest is already in the shared venv, but this makes it explicit):

```bash
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pip install -r requirements-dev.txt
```

Run the suite with one command from the repo root:

```bash
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q
```

All 170 tests should pass. The configuration lives in `pytest.ini`; `conftest.py` adds the project root to `sys.path` automatically so no manual path setup is needed. CI runs the same command on every push and pull request via `.github/workflows/tests.yml`.

## License

MIT. Built for fun. Not affiliated with Sony, San Diego Studio, or MLB.
