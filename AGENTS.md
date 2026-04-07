# MLB The Show 26 - Reverse Engineer Player Ratings

## Project Goal
Build a tool that generates MLB The Show-style player rating cards from any historical MLB season stats. Users input a player name + year, and the tool outputs a full attribute card with ratings 0-99.

## Project Location
`C:\Users\Alex\Codex Context\MLB The Show 26 - Reverse Engineer Player Ratings\`

## How to Run

### Web App (recommended)
```bash
"C:/Users/Alex/Codex Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" "C:/Users/Alex/Codex Context/MLB The Show 26 - Reverse Engineer Player Ratings/app.py"
```
Then open **http://localhost:5000** in your browser.

### Features
- **Auto-detect pitcher vs hitter** — compares IP vs PA with strict name matching
- **Season vs Career mode** — Season uses only that year's stats; Career blends with history
- **Autocomplete search** — loads player names per-year from FanGraphs
- **OVR badge** — diamond-shaped, color-coded by tier (diamond/gold/silver/bronze)
- **Compare mode** — two players side by side
- **Pitch arsenal** — per-pitch velocity, usage%, break rating (0-99), spin rate (Statcast era)
- **Save/copy cards**
- **Works for any era** — 1897 Nap Lajoie through 2025 Bobby Witt Jr.

### CLI
```bash
"C:/Users/Alex/Codex Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Juan Soto" 2025
"C:/Users/Alex/Codex Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Garrett Crochet" 2025 --pitcher
"C:/Users/Alex/Codex Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" generate_card.py "Barry Bonds" 2001 --position LF -v
```

## Dependencies
- Python with pybaseball + Flask (in Robert Stock venv)
- numpy

## Hitter Attribute Formulas

| Attribute | Formula | Source |
|-----------|---------|--------|
| Vision | `-2.55 * K% + 121.3` | r=0.994 |
| Speed | `15.01 * Sprint - 353.5` (Statcast) or `9.42 * FG_Spd + 19.1` (pre-2015) or SB-based (pre-2002) | r=0.989 / 0.879 |
| Discipline | `4.86 * BB% + 17.2` | r=0.982 |
| Fielding | `2.09 * OAA + 68.6` or `1.38 * FG_Def + 67.3` (pre-OAA) or position baseline | r=0.953 / 0.825 |
| Contact R | `374.6 * BA + 2.30 * Exit_Velo - 217.4` (Statcast) or `551.97 * BA_blend - 69.7` | r=0.945 |
| Contact L | `289.21 * OBP_blend - 19.1` | r=0.827 |
| Power R | `336.17 * ISO_blend + 3.9` (recency-weighted or season-only) | r=0.935 |
| Power L | `244.42 * ISO_blend + 17.4` | r=0.821 |
| Stealing | `0.6 * (1.88*SB + 18.5) + 0.4 * Speed` | r=0.939 |
| Durability | Season: `0.52 * GP + 15` / Career: `0.16 * blended_GP + 69.9` | |
| Batting Clutch | `509.5 * BA + 0.36 * wRC+ - 103.2` | r²=0.612 |
| Arm Strength | rARM-based for OF, position default for IF | |
| Arm Accuracy | ErrR-based when available, else position default | |
| Reactions (L/R/F/B) | OAA or RngR -> base reaction, then position-specific directional weights | |
| Bunting/Drag Bunt | Position defaults (do NOT affect OVR) | |

### Hitter OVR Formula
```
OVR = 0.78 * CoreHitting + 0.17 * FieldingOVR + 0.07 * Speed + 0.16 * Durability + 1.8
```
CoreHitting = avg of Contact R/L, Power R/L, Vision, Discipline, Clutch (excludes Bunt/Drag Bunt).
RMSE=3.7. BWJ: 96 pred vs 99 actual.

### Directional Reactions
Base reaction from OAA (`1.5 * OAA + 65`) or RngR (`2.0 * RngR + 65`), then multiplied by position weights:
- SS: L=0.85, R=1.15, F=1.05, B=0.90
- 3B: L=0.90, R=0.95, F=1.15, B=0.90
- CF: L=1.00, R=0.95, F=0.90, B=0.90
- etc.

### Season vs Career Mode
- **Season**: uses single-year stats only. Power from that year's ISO splits. Fielding from that year's OAA. Durability = `0.52 * GP + 15` (steeper curve).
- **Career**: blends with multi-year history. Recency-weighted ISO for power. Multi-year OAA for fielding. Flatter durability curve.

## Pitcher Attribute Formulas

| Attribute | Formula |
|-----------|---------|
| HR/9 | `-13.87 * HR/9 + 82.7` (dampened) |
| H/9 splits | `-250 * BA_against + 130` per split (dampened) |
| K/9 splits | `2.2 * K%_split + 15` per split (dampened) |
| Control | `-4.44 * BB% + 104.9` (dampened) |
| Velocity | `3.14 * FB_Velo - 208.2` |
| Stamina | SP: `1.47 * GS + 46.1` / RP: fixed at 25 |
| Break | Usage-weighted avg of per-pitch break ratings from Statcast arsenal |
| Clutch | `3.52 * WAR + 60.8` (dampened) |

**Sample size dampener**: `trust = min(career_IP / 200, 1.0)`. Low-IP pitchers regressed toward 65.

### Pitcher OVR Formula
```
OVR = 1.21 * PitchingOVR + 0.14 * FieldingOVR - 0.13 * Durability - 4.6
```
RMSE=2.7. Skubal: 97 pred vs 96 actual. Tolle: 76 exact match.

## Pre-Statcast Data Tiers
| Era | Speed | Fielding | Contact | Reactions | Arsenal |
|-----|-------|----------|---------|-----------|---------|
| 2015+ | Sprint Speed | OAA | BA + Exit Velo | OAA-based | Full pitch data |
| 2003-2014 | FG Spd | FG Def + RngR | BA only | RngR-based | None |
| Pre-2003 | SB estimate | Position default | BA only | Position default | None |

## File Structure
- `app.py` — Flask web app (localhost:5000)
- `generate_card.py` — Core logic (hitter + pitcher ratings, OVR formulas, data pulling)
- `templates/index.html` — Web UI (Oswald font, diamond OVR badges, attribute bars, arsenal section)
- Analysis scripts: `player_data.py`, `pitcher_analysis_v2.py`, `final_mappings.py`, `blended_analysis.py`, etc.
- Data: `player_2025_stats_v2.json`, `player_2025_splits.json`, `career_data_fixed.json`

## Calibration Players
- **Hitters (11)**: Soto (98), BWJ (99), Buxton (95), Vlad Jr (94), Yordan (91), PCA (87), Adley (84), Bogaerts (80), Shaw (74), Kim (74), Simpson (72)
- **Pitchers (11)**: Crochet (94), Skubal (96), Suarez (88), Ragans (83), McLean (82), Lopez (82), Fairbanks (81), Smith (81), Hoffman (80), Early (76), Tolle (69)

## Known Limitations
1. Pre-Statcast eras lack exit velo, sprint speed, OAA — uses tiered fallbacks
2. Bunting/Drag Bunt are position defaults (don't affect OVR)
3. Pitcher Velocity formula overrates soft-tossers (<93 mph)
4. OVR formula is linear — five-tool players like BWJ still slightly underpredicted
5. Name collisions handled by strict matching + IP vs PA comparison
6. NaN-safe for very old eras (1890s+)

## Next Steps
- [ ] Deploy to Render for public access
- [ ] True image export (html2canvas -> PNG)
- [ ] Per-pitch individual ratings (like Show 26's new system)
- [ ] Improve pitcher Velocity for soft-tossers
- [ ] More calibration players for OVR formula refinement
- [ ] Mobile responsiveness polish
