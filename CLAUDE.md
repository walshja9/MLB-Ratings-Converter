# MLB The Show 26 - Reverse Engineer Player Ratings

## Project Goal
Build a tool that generates MLB The Show-style player rating cards from any historical MLB season stats. Users input a player name + year, and the tool outputs a full attribute card with ratings 0-99.

## Project Location
`C:\Users\Alex\Claude Context\MLB The Show 26 - Reverse Engineer Player Ratings\`

## How to Run

### Web App (recommended)
```bash
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" "C:/Users/Alex/Claude Context/MLB The Show 26 - Reverse Engineer Player Ratings/app.py"
```
Then open **http://localhost:5000** in your browser.

### Features
- **Auto-detect pitcher vs hitter** — compares IP vs PA with strict name matching
- **Season vs Career mode** — Season uses only that year's stats; Career blends with history
- **Autocomplete search** — loads player names per-year from FanGraphs (may hit rate limits with heavy use)
- **OVR badge** — diamond-shaped, color-coded by tier (diamond/gold/silver/bronze)
- **Compare mode** — two players side by side
- **Pitch arsenal** — per-pitch velocity, usage%, break rating (0-99), spin rate (Statcast era)
- **Save/copy cards**
- **Works for any era** — 1897 Nap Lajoie through 2025 Bobby Witt Jr.

### CLI
```bash
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Juan Soto" 2025
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Garrett Crochet" 2025 --pitcher
"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Barry Bonds" 2001 --position LF -v
```

## Dependencies
- Python with pybaseball + Flask (in Robert Stock venv)
- numpy

## Hitter Attribute Formulas

| Attribute | Formula | Source |
|-----------|---------|--------|
| Vision | `-2.55 * K% + 121.3` | r=0.994 |
| Speed | `15.01 * Sprint - 353.5` (Statcast) or `9.42 * FG_Spd + 19.1` (pre-2015) or SB-based (pre-2002) | r=0.989 / 0.879 |
| Discipline | `4.86 * BB% + 17.2` | r=0.964 |
| Fielding | `2.09 * OAA + 68.6` or `1.38 * FG_Def + 67.3` (pre-OAA) or position baseline | r=0.953 / 0.825 |
| Contact R | `374.6 * BA + 2.30 * Exit_Velo - 217.4` (Statcast) or `551.97 * BA_blend - 69.7` | r=0.945 |
| Contact L | `289.21 * OBP_blend - 19.1` | r=0.827 |
| Power R | `336.17 * ISO_blend + 3.9` (recency-weighted or season-only) | r=0.935 |
| Power L | `244.42 * ISO_blend + 17.4` | r=0.821 |
| Stealing | `0.6 * (1.88*SB + 18.5) + 0.4 * Speed` | r=0.939 |
| Durability | Season: `0.52 * GP + 15` / Career: `0.16 * blended_GP + 69.9` | |
| Batting Clutch | `520*BA + 135*RISP_premium - 67` (when 50+ RISP PA) or `520*BA - 67` | r=0.706 with RISP |
| Arm Strength | rARM-based for OF, position default for IF | |
| Arm Accuracy | ErrR-based when available, else position default | |
| Reactions (L/R/F/B) | OAA or RngR -> base reaction, then position-specific directional weights | |
| Bunting/Drag Bunt | Position defaults (do NOT affect OVR) | |

### Hitter OVR Formula
```
OVR = 0.78 * CoreHitting + 0.17 * FieldingOVR + 0.07 * Speed + 0.16 * Durability + 1.8
```
CoreHitting = avg of Contact R/L, Power R/L, Vision, Discipline, Clutch (excludes Bunt/Drag Bunt).

### Directional Reactions
Base reaction from OAA (`1.5 * OAA + 65`) or RngR (`2.0 * RngR + 65`), then multiplied by position weights. Career mode uses recency-weighted OAA across years. Gated by innings played (0% trust <50 inn, ramps to 100% at 500+ inn).

### Fielding Innings Gate
Multi-position players are aggregated across all position entries per year (e.g. Duran's LF+CF+RF innings sum). Trust factor: `max(0, min((innings - 50) / 450, 1.0))`. Below 50 innings = position baseline only (prevents DH types from getting inflated fielding from tiny samples).

### Season vs Career Mode
- **Season**: single-year stats only. Power from that year's ISO splits. Fielding from that year's OAA. Durability = `0.52 * GP + 15`. Stamina = `1.47 * GS + 46.1` (current year GS only).
- **Career**: blends with multi-year history. Recency-weighted ISO for power. Multi-year OAA for fielding/reactions. Flatter durability curve. Stamina blends current GS with career avg.

## Pitcher Attribute Formulas

| Attribute | Formula |
|-----------|---------|
| HR/9 | `-13.87 * HR/9 + 82.7` (dampened) |
| H/9 splits | `-250 * BA_against + 130` per split (dampened) |
| K/9 splits | `2.2 * K%_split + 15` per split (dampened) |
| Control | `-4.44 * BB% + 104.9` (dampened) |
| Velocity | `3.14 * FB_Velo - 208.2` |
| Stamina | SP season: `1.47 * GS + 46.1` / SP career: blended / RP: fixed 25 |
| Break | Pitch diversity heuristic: `75 + (num_pitches-2)*3 + offspeed_usage*0.2` (dampened). Not stat-derivable (r<0.4 with all metrics). |
| Clutch | `3.52 * WAR + 60.8` (dampened) |

**Sample size dampener**: `trust = min(career_IP / 200, 1.0)`. Low-IP pitchers regressed toward 65.

### Pitcher OVR Formula
```
OVR = 1.21 * PitchingOVR + 0.14 * FieldingOVR - 0.13 * Durability - 4.6
```

## Pre-Statcast Data Tiers
| Era | Speed | Fielding | Contact | Reactions | Arsenal |
|-----|-------|----------|---------|-----------|---------|
| 2015+ | Sprint Speed | OAA | BA + Exit Velo | OAA-based | Full pitch data |
| 2003-2014 | FG Spd | FG Def + RngR | BA only | RngR-based | None |
| Pre-2003 | SB estimate | Position default | BA only | Position default | None |

## Code Quality (Codex Review — 2026-03-31)
All findings from automated review have been fixed:
- **P1**: Pre-Statcast fielding fallback now correctly checks for integer year keys before taking OAA branch. 2003-2014 players properly use FG Def.
- **P1**: Pitcher stamina in season mode now uses only current year GS, not career blend.
- **P2**: Compare error messages sanitized via textContent. Autocomplete uses DOM API (createElement/addEventListener) instead of innerHTML/inline onclick.
- **MLBAM lookup**: Now accepts year parameter and filters to players active in that year to prevent name collisions (e.g. Josh Hamilton pitcher vs hitter in 2007).

## File Structure
- `app.py` — Flask web app (localhost:5000)
- `generate_card.py` — Core logic (hitter + pitcher ratings, OVR formulas, data pulling)
- `templates/index.html` — Web UI (Oswald font, diamond OVR badges, attribute bars, arsenal section)
- Analysis scripts: `player_data.py`, `pitcher_analysis_v2.py`, `final_mappings.py`, `blended_analysis.py`, etc.
- Data: `player_2025_stats_v2.json`, `player_2025_splits.json`, `career_data_fixed.json`

## Calibration Players
- **Hitters (12)**: Soto (98), BWJ (99), Buxton (95), Vlad Jr (94), Yordan (91), PCA (87), Adley (84), Bogaerts (80), Shaw (74), Kim (74), Simpson (72), Duran (Show fielding verified)
- **Pitchers (11)**: Crochet (94→95 gen), Skubal (96→97 gen), Suarez (88), Ragans (83), McLean (82), Lopez (82), Fairbanks (81), Smith (81), Hoffman (80), Early (76), Tolle (69→76 exact)

## Known Limitations
1. Pre-Statcast eras lack exit velo, sprint speed, OAA — uses tiered fallbacks
2. Bunting/Drag Bunt are position defaults (don't affect OVR)
3. Pitcher Velocity formula overrates soft-tossers (<93 mph)
4. Pitcher Break is heuristic-based (no stat correlates >0.4)
5. Batting Clutch uses RISP BA premium but single-season is noisy (career RISP would be better but requires multiple years of Statcast pulls)
6. FanGraphs rate limiting with heavy use — need local data caching for deployment
7. NaN-safe for very old eras (1890s+)

## Next Steps
- [ ] Build local data cache (SQLite or JSON) to avoid FanGraphs rate limits and enable deployment
- [ ] Deploy to Render for public access
- [ ] True image export (html2canvas -> PNG)
- [ ] Per-pitch individual ratings (like Show 26's new system)
- [ ] Improve pitcher Velocity for soft-tossers
- [ ] More calibration players for OVR formula refinement
- [ ] Mobile responsiveness polish
- [ ] Automated tests for season-vs-career logic
