<!-- reasoning_effort: 99 — always use near-maximum deliberation -->

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
| Vision | `-3.07 * K% + 126.9` (dampened toward 25% K for PA<200) | r=0.909, RMSE=7.6 |
| Speed | `15.02 * Sprint + 0.10 * SB/162 - 356.5` (Statcast, regressed for G<30) or `9.42 * FG_Spd + 19.1` (pre-2015) or SB-based (pre-2002) | RMSE=~13.6 |
| Discipline | `4.86 * BB% + 17.2` (dampened toward 8% BB for PA<200) | r=0.835, RMSE=10.7 |
| Fielding | `1.65 * OAA + per-position intercept` (OAA/RngR/Rdrs path) or `1.38 * FG_Def + 67.3` (pre-OAA) or position baseline | refit 6/4 |
| Contact R | `320.5 * BA_vR - 12.2` (BA dampened; career-blended 0.55/0.45 in career mode) | refit 6/4 |
| Contact L | `251.9 * BA_vs_LHP + 5.8` (trust-blended) | refit 6/4 |
| Power R | `130.1 * ISO_blend + 358.4 * HR_rate_R + 30.4` (barrel-blended 0.6/0.4 when Barrel% available) | refit 6/4 |
| Power L | `55.1 * ISO_L + 504.6 * HR_rate_L + 38.6` (barrel-blended 0.5/0.5 when Barrel% available) | refit 6/4 |
| Stealing | Tiered: SB/162<2 → `3 + 0.04*Speed`; else → `2.0*SB/162 + 9`. Cap SB/162 at 60. | r=0.916, RMSE=13.4 |
| Durability | Season: `0.17 * GP + 72` (floor 78, dampened) / Career: `0.16 * blended_GP + 72` | RMSE=4.9 |
| Batting Clutch | `-161.7 * BA + 2.2 * WAR + 239.4 * RISP_BA + 39.1` (Statcast era) or `93 * BA + 2.6 * WAR + 34` (pre-Statcast). Dampened toward 50 for PA<150. | RMSE=~16.5 |
| Arm Strength | rARM-based for OF only, position default for IF/C | RMSE=11.5 |
| Arm Accuracy | ErrR-based when available, else position default | RMSE=16.1 (r=0.17, scouting) |
| Reactions (L/R/F/B) | OAA or RngR -> base reaction, then position-specific directional weights | |
| Bunting/Drag Bunt | Position defaults (do NOT affect OVR) | |

> Coefficients last refit 6/4/2026; keep this table in sync with `generate_card.py`.

**Fielding OAA per-position intercepts** (`raw_fld = clamp(1.65 * weighted_OAA + intercept)`):
`{"1B": 64, "LF": 64, "RF": 64, "OF": 64, "DH": 64, "2B": 70, "3B": 70, "SS": 73, "CF": 73, "C": 71}`
(default 70). Raw fielding is blended with the position baseline via the innings-based `def_trust` ramp.

### Hitter OVR Formula (refit 6/4/2026)
```
OVR = 0.8165 * CoreHitting + 0.1476 * FieldingOVR + 0.0236 * Speed + 0.1957 * Durability + _POS_OVR_ADJ
```
CoreHitting = avg of Contact R/L, Power R/L, Vision, Discipline, Clutch (excludes Bunt/Drag Bunt).
`_POS_OVR_ADJ = {"C": 2, "1B": -1, "2B": -1, "3B": -2, "LF": -1, "DH": -1}` (default 0).
The fielding term is now nonzero (a small position-defense credit on top of hitting/speed/durability).

### Sample Size Dampening (Hitters)
All rate stats (K%, BB%, BA, ISO) are regressed toward league averages for PA < 200:
`effective_stat = trust * raw_stat + (1-trust) * league_avg` where `trust = min(PA/200, 1.0)`.
Sprint speed regressed toward position baseline for G < 30.

### Directional Reactions
Base reaction from OAA (`1.5 * OAA + 65`) or RngR (`2.0 * RngR + 65`), then multiplied by position weights. Career mode uses recency-weighted OAA across years. Gated by innings played (0% trust <50 inn, ramps to 100% at 500+ inn).

### Fielding Innings Gate
Multi-position players are aggregated across all position entries per year (e.g. Duran's LF+CF+RF innings sum). Trust factor: `max(0, min((innings - 50) / 450, 1.0))`. Below 50 innings = position baseline only (prevents DH types from getting inflated fielding from tiny samples).

### Season vs Career Mode
- **Season**: single-year stats only. Power from that year's ISO splits. Fielding from that year's OAA. Durability = `0.17 * GP + 72`. Stamina = `0.62 * GS + 75` (current year GS only).
- **Career**: blends with multi-year history. Recency-weighted ISO for power. Multi-year OAA for fielding/reactions. Flatter durability curve. Stamina blends current GS with career avg.

## Pitcher Attribute Formulas

| Attribute | Formula | RMSE |
|-----------|---------|------|
| HR/9 | `-7.0 * HR/9 + 96.3` (dampen-aware refit, 1pt HR/9 = 7pts rating) | 6.1 |
| H/9 splits | L: `-215.5 * BA_vL + 128.8`, R: `-49.6 * BA_vR + 98.3` (dampen-aware refit) | L: 6.9, R: 6.1 |
| K/9 splits | `2.2 * K%_split + 15` per split (dampened) | L: 11.3, R: 7.9 |
| Control | `-0.7 * BB/9 - 71.2 * WHIP + 149.9` (WHIP dominates) | 9.5 |
| Velocity | `3.1 * FB_Velo - 214` (partly reputation-based, r≈0.58) | 9.4 |
| Stamina | SP: `0.62 * GS + 75` / RP: `4.8 * G - 268` | 7.6 |
| Break | Pitch diversity heuristic: `75 + (num_pitches-2)*3 + offspeed_usage*0.2` (dampened). Not stat-derivable (r<0.4 with all metrics). | 7.6 |
| Clutch | `2.7 * WAR + 59.3` (dampen-aware refit) | 4.1 |

**Sample size dampener**: `trust = min(career_IP / 200, 1.0)`. Low-IP pitchers regressed toward 65.

### Pitcher OVR Formula (refit 6/4/2026, RMSE ~4.13)
```
OVR = 1.074 * PitchingOVR + 4.6
```
Refit 6/4 (slope 0.990->1.074, intercept 8.4->4.6) after the K/9 + H/9 split decompression.
Fielding/durability weights = 0; pitching dominates. Crochet 94, Skubal 95.

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
- **Hitters (20 with per-attribute truth)**: Soto (98), BWJ (99), Judge (99), Buxton (95), Vlad Jr (94), Yordan (91), Turner (91), PCA (87), Elly (87), Adley (84), Dingler (83), Kwan (82), Bogaerts (80), Shaw (74), Kim (74), Simpson (72), Valera (68), Ruiz (64), Berroa (63), Duran (Show fielding verified)
- **Pitchers (12)**: Skubal (96), Yamamoto (95), Crochet (94), Suarez (88), Ragans (83), Lopez (82), McLean (82), Fairbanks (81), Smith (81), Hoffman (80), Messick (77), Early (76), Tolle (69)
- **Recalibration script**: `recalibrate_all.py` — pulls live data, compares per-attribute, refits all formulas. Use `--skip-pull` to reuse cached data, `--detail` for per-player breakdowns.

## Calibration Accuracy (2026-04-20, N=18 hitters, 10 pitchers)

### Hitter Attributes (avg RMSE: ~11.6, was 12.6)
| Grade | Attributes |
|-------|-----------|
| A+ (≤5) | Durability (4.9) |
| A (5-8) | Vision (7.6) |
| B (8-12) | Contact R (8.8), Discipline (10.7), Arm Str (11.5), BR Agg (11.9), Fielding (11.9), Contact L (12.0) |
| C (12-16) | Power L (~13.3, was 16.2), Stealing (13.4), Speed (~13.6, was 14.7) |
| F (>16) | Arm Acc (16.1, scouting), Clutch (~16.5, was 18.3, reputation), Power R (~17.5, was 19.1) |

### Pitcher Attributes (avg RMSE: ~7.9, was 9.4)
| Grade | Attributes |
|-------|-----------|
| A+ (≤5) | Pit Clutch (4.1, was 8.6) |
| A (5-8) | HR/9 (6.0, was 11.7), H/9 R (6.1, was 8.7), H/9 L (6.9, was 10.6), Stamina (7.6), Break (7.6), K/9 R (7.9) |
| B (8-12) | Velocity (9.4), Control (9.5, was 10.5), K/9 L (11.3) |

### OVR Accuracy
| | RMSE | Notes |
|--|------|-------|
| Hitter OVR | 4.2 | Worst: Yordan -9 (injury/reputation), Shaw +8 |
| Pitcher OVR | 3.6 | Worst: Tolle +9 (prospect, low IP) |

## Known Limitations
1. Pre-Statcast eras lack exit velo, sprint speed, OAA — uses tiered fallbacks
2. Bunting/Drag Bunt are position defaults (don't affect OVR)
3. Pitcher Velocity is partly reputation-based (r≈0.58) — Crochet gets 99 in Show despite similar mph to Skubal who gets 77
4. Pitcher Break is heuristic-based (no stat correlates >0.4)
5. Batting Clutch is partly reputation-based (r≈0.54) — Shaw/Turner/Dingler get Show values (25/47/38) that no stat can predict
6. Power R/L improved with HR rate but still has large errors for career-reputation players (Yordan 99 vs ~61, Dingler 86 vs ~56)
7. Arm Accuracy is essentially a scouting attribute (r=0.17)
8. FanGraphs rate limiting with heavy use — need local data caching for deployment
9. NaN-safe for very old eras (1890s+)

## Next Steps
- [ ] Build local data cache (SQLite or JSON) to avoid FanGraphs rate limits and enable deployment
- [ ] Deploy to Render for public access
- [ ] True image export (html2canvas -> PNG)
- [ ] Per-pitch individual ratings (like Show 26's new system)
- [ ] More calibration players (especially catchers, utility players)
- [ ] Mobile responsiveness polish
- [ ] Automated tests for season-vs-career logic
- [ ] Power R/L: explore split SLG or HR-rate based approach for better split power
