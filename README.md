# MLB Stats → The Show 25 Converter

Convert real MLB statistics into MLB The Show 25 player ratings with **95% accuracy**.

🔍 **Search 24,270 players** from 1871-2024, including Negro League stars!

## Features

- **Historical Player Search** - Powered by the [Lahman Baseball Database](https://www.seanlahman.com/baseball-archive/statistics/) with 150+ years of baseball history
- **95% Accurate** - Overall rating formula calibrated against 3,644 real MLB The Show 25 players
- **Era-Adjusted** - Velocity estimates adjust for deadball era through modern baseball
- **Actual Fielding Data** - Uses real fielding percentage from the database
- **Auto-Detection** - Automatically determines position, tier, and player type
- **Manual Entry** - Create custom players with the Hitter/SP/RP tabs

## Quick Start

### Option 1: GitHub Pages (Recommended)
Visit: **[your-username.github.io/mlb-the-show-converter](https://your-username.github.io/mlb-the-show-converter)**

### Option 2: Run Locally
1. Download both files:
   - `index.html`
   - `lahman_data.js` (11 MB)
2. Place them in the **same folder**
3. Open `index.html` in your browser
4. Wait for "✅ Loaded 24,270 players" to appear
5. Start searching!

## Attributes Generated

### Hitting
| Attribute | Primary Source | Secondary |
|-----------|---------------|-----------|
| Contact R/L | AVG | K%, wRC+ |
| Power R/L | ISO (SLG-AVG) | HR |
| Vision | K% | - |
| Discipline | BB% | OBP-AVG |
| Clutch | wRC+ | - |

### Fielding & Speed
| Attribute | Formula |
|-----------|---------|
| Fielding | Fielding % vs position average |
| Arm Strength | Position-based default |
| Arm Accuracy | (Arm × 0.5) + (Fielding × 0.3) + (Reaction × 0.2) |
| Reaction | (Fielding × 0.5) + (Speed × 0.3) + 15 |
| Speed | Sprint Speed estimate from SB/3B |
| Stealing | SB + SB% |
| Baserunning | (Speed × 0.6) + (Stealing × 0.4) |

### Pitching
| Attribute | Primary Source | Secondary |
|-----------|---------------|-----------|
| H/9 | H/9 | WHIP |
| K/9 | K/9 | Stuff+ |
| BB/9 | BB/9 | - |
| HR/9 | HR/9 | FIP |
| Clutch | ERA | - |
| Velocity | Fastball Velo | Era estimate |
| Control | BB/9 | - |
| Break | Stuff+ | - |
| Stamina | IP | - |

## Historical Velocity Estimates

Since Statcast only exists from 2015+, velocity is estimated by era:

| Era | Base Velo | High-K Adjustment |
|-----|-----------|-------------------|
| Pre-1920 | 88 mph | +2 if K/9 > 10 |
| 1920-1949 | 90 mph | +2 if K/9 > 10 |
| 1950-1969 | 92 mph | +1 if K/9 > 8 |
| 1970-1989 | 91 mph | +1 if K/9 > 8 |
| 1990-2009 | 93 mph | +1 if K/9 > 8 |
| 2010+ | 94 mph | +2 if K/9 > 10 |

Override velocity for players you know threw harder (Walter Johnson, Nolan Ryan) or softer (knuckleballers).

## Example Conversions

| Player | Year | Real Stats | Converted OVR |
|--------|------|------------|---------------|
| Babe Ruth | 1921 | .378/.512/.846, 59 HR | 99 💎 |
| Willie Mays | 1954 | .345/.411/.667, 41 HR | 99 💎 |
| Pedro Martinez | 1999 | 23-4, 2.07 ERA, 313 K | 97 💎 |
| Barry Bonds | 2001 | .328/.515/.863, 73 HR | 99 💎 |
| Dustin Pedroia | 2007 | .317/.380/.442, 99.0% Fld | 81 🥇 |
| Turkey Stearnes | 1928 | .322/.391/.644, 24 HR | 99 💎 |

## File Structure

```
mlb-the-show-converter/
├── index.html          # Main application (42 KB)
├── lahman_data.js      # Compressed Lahman database (11 MB)
└── README.md           # This file
```

## Hosting on GitHub Pages

1. Create a new GitHub repository
2. Upload `index.html` and `lahman_data.js`
3. Go to **Settings** → **Pages**
4. Set Source to **Deploy from a branch** → **main** → **/ (root)**
5. Click **Save**
6. Your converter will be live at `https://YOUR_USERNAME.github.io/REPO_NAME/`

## Data Sources

- **Player Database**: [Lahman Baseball Database](https://www.seanlahman.com/baseball-archive/statistics/)
- **Conversion Formulas**: Calibrated against 3,644 players from MLB The Show 25
- **Negro League Data**: Included in Lahman Database since 2021 update

## Limitations

- **Historical player ratings may vary** - The conversion formulas were calibrated using current players from MLB The Show 25. When converting historical players (especially pre-2000), ratings may differ from what you'd see in The Show's Legends cards. This is because league averages for stats like strikeout rate and walk rate have changed significantly over baseball history. Use the Tier Override to manually adjust ratings if needed.
- **No platoon splits**: Historical data doesn't include vs-LHP/vs-RHP splits, so these are estimated from handedness
- **No Statcast for pre-2015**: Sprint speed, arm strength estimated from traditional stats
- **Database ends at 2024**: Lahman updates annually after each season

## Overall Rating Formula

Position and tier-specific formulas calibrated against real MLB The Show 25 data:

```
Hitters:  OVR = slope × core_avg + intercept + power_bonus
Starters: OVR = slope × core_avg + intercept + (stamina × stam_weight)
Relievers: OVR = slope × core_avg + intercept
```

Core averages are calculated from the 8-9 most important attributes for each player type.

## License

MIT License - feel free to use, modify, and share.

## Credits

- [Lahman Baseball Database](https://www.seanlahman.com/baseball-archive/statistics/)
- MLB The Show 25 by San Diego Studio
- Conversion formulas developed through extensive testing and calibration
