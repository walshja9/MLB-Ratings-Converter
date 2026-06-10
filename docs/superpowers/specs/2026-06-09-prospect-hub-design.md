# Prospect Hub — Design Spec (2026-06-09)

## Goal
Recreate/edit all 30 teams' Top 30 prospects in MLB The Show. The app generates
Show-style rating cards for ~900 prospects from scouting grades; Alex reads them
on his phone while editing players in-game on console, checking off prospects as
he enters them.

## Approach (B — approved)
Separate committed prospect dataset + cards generated on-the-fly through the
existing scouting engine. No engine changes. Player pool stays untouched.

## Components

### 1. `scrape_prospects.py` (standalone batch script, run manually)
- **MLB Pipeline** (spine, all ~900): per-team Top 30 — rank, name, position,
  age, bats/throws, height/weight, ETA, tool grades (hitters:
  Hit/Power/Run/Arm/Field + Overall; pitchers: per-pitch + Control + Overall).
  Fetch tiers: plain JSON fetch → cloudscraper → Playwright visible browser
  (same fallback philosophy as `fielding_stats`).
- **FanGraphs Board** (enrichment): FV, level, age, present/future grades.
  Fetch via existing Playwright pattern; fallback = manual CSV export ingested
  from `prospect_data/fangraphs_board.csv`.
- **Merge**: normalized name (strip accents/suffixes) + org match. Unmatched FG
  names → written to a report file for hand-fixing via `prospect_data/name_aliases.json`.
  Pipeline-only players: FV stand-in = Pipeline Overall grade, `fv_source: "pipeline"`.
- **Output**: `prospect_data/teams.json` (committed). Refresh = re-run script.
- **Validation**: expect 30/team (warn, don't fail); prospects missing grades
  default those grades to 50 and carry `grades_incomplete: true`.

### 2. `prospect_mapper.py` (new module)
Prospect entry → the form dict `_scouting_card()` already accepts. Engine untouched.
- Hitters: hit→g_hit, power→g_power, speed→g_speed, field→g_field, arm→g_arm.
  Eye = Hit grade unless FG supplies one (documented assumption).
- Pitchers: FB→g_fb; best of CB/SL/sweeper/slurve→g_break; best of CH/splitter→g_off;
  Control→g_command. Role SP unless FG flags reliever.
- FG present grades → existing `_p` fields (Now/Potential range). FV → existing anchor.
- Pass through age + level so the existing age-vs-level stat blend stays available later.

### 3. Routes (`app.py`)
- `GET /prospects` — 30 teams + done-counts.
- `GET /prospects/<team>` — ranked list: rank, name, pos, age, FV, OVR, done.
  OVR computed on the fly (pure math, no network).
- `GET /prospects/<team>/<id>` — full card; same JSON shape as existing cards so
  the front-end renderer works unmodified.
- `POST /prospects/done` — toggle `{team, id, done}` → `prospect_data/progress.json`.

### 4. UI (new "Prospects" tab in `templates/index.html`)
Team grid with progress badges (e.g. 14/30) → team list rows with
done-checkboxes (optimistic toggle) → tap row → existing card view (FV badge +
Now→Potential range). Mobile-first.

### 5. Error handling & tests
- Missing `teams.json` → tab shows "run scrape_prospects.py" message.
- ⚠ badge on `grades_incomplete` prospects.
- Tests: grade mapping (hitter / pitcher / missing grades / RP), name matching,
  done-toggle route. Scraper parsing tested against saved fixtures, never live network.

## Known risk
The Pipeline scrape is the only unproven piece (JS-heavy React site); which fetch
tier works is unknown until implementation. Everything downstream of `teams.json`
is independent of it. Worst case: Playwright for both sources or one-time manual assist.

## Out of scope
Printable team sheets, auto-refresh scheduling, engine/calibration changes.
