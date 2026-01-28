# MLB Stats → The Show 25 Converter

Convert real MLB statistics into MLB The Show 25 player ratings with **95% accuracy**.

**v4.1** - Now includes actual fielding percentage data from the Lahman Database!

🔍 **Search 24,270 players** from 1871-2024, including Negro League stars!

![Converter Preview]()

## Features

- **Player Search**: Powered by the [Lahman Baseball Database](https://sabr.org/lahman-database/) with 150+ years of baseball history
- **95% Accurate**: Overall rating formula derived from 3,644 real MLB The Show 25 players
- **Era-Adjusted**: Velocity estimates adjust for deadball era through modern baseball
- **Auto-Detection**: Automatically determines position, tier, and player type
- **Manual Entry**: Create custom players with the Hitter/SP/RP tabs

## Quick Start

### Option 1: Use Online (GitHub Pages)
Visit: **https://YOUR_USERNAME.github.io/mlb-the-show-converter/**

### Option 2: Download & Run Locally
1. Download both files:
   - `MLBConverter_v4.html`
   - `lahman_data.js`
2. Place them in the **same folder**
3. Open `MLBConverter_v4.html` in your browser
4. Wait for "✅ Loaded 24,270 players" to appear
5. Start searching!

## How It Works

### Hitting Attributes
| Attribute | Primary Source | Secondary |
|-----------|---------------|-----------|
| Contact R/L | AVG | K%, wRC+ |
| Power R/L | ISO (SLG-AVG) | HR |
| Vision | K% | - |
| Discipline | BB% | OBP-AVG |
| Speed | Sprint Speed | SB, 3B |
| Stealing | SB | SB% |
| Fielding | OAA/DRS | Position avg |

### Pitching Attributes
| Attribute | Primary Source | Secondary |
|-----------|---------------|-----------|
| H/9 | H/9 | WHIP |
| K/9 | K/9 | Stuff+ |
| BB/9 | BB/9 | - |
| HR/9 | HR/9 | FIP |
| Velocity | Fastball Velo | Era estimate |
| Stamina | IP | SP vs RP |

### Overall Rating Formula
Position and tier-specific formulas calibrated against real MLB The Show 25 data:
```
OVR = slope × core_average + intercept + bonuses
```

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

You can override velocity for players you know threw harder/softer (e.g., Walter Johnson, Nolan Ryan, knuckleballers).

## Example Conversions

| Player | Year | Real Stats | Converted OVR |
|--------|------|------------|---------------|
| Babe Ruth | 1921 | .378/.512/.846, 59 HR | 99 💎 |
| Willie Mays | 1954 | .345/.411/.667, 41 HR | 99 💎 |
| Pedro Martinez | 1999 | 23-4, 2.07 ERA, 313 K | 97 💎 |
| Barry Bonds | 2001 | .328/.515/.863, 73 HR | 99 💎 |
| Turkey Stearnes | 1928 | .322/.391/.644, 24 HR | 99 💎 |
| Dan Quisenberry | 1983 | 45 SV, 1.94 ERA, 11 BB | 70 🥉 |

## File Structure

```
mlb-the-show-converter/
├── MLBConverter_v4.html    # Main application (41 KB)
├── lahman_data.js          # Compressed Lahman database (11 MB)
├── README.md               # This file
└── preview.png             # Screenshot (optional)
```

## Data Sources

- **Player Database**: [Lahman Baseball Database](https://sabr.org/lahman-database/) via SABR
- **Conversion Formulas**: Calibrated against 3,644 players from MLB The Show 25
- **Negro League Data**: Included in Lahman Database since 2021 update

## Hosting on GitHub Pages

To host this converter online:

1. Create a new GitHub repository
2. Upload `MLBConverter_v4.html` (rename to `index.html`) and `lahman_data.js`
3. Go to Settings → Pages
4. Set Source to "Deploy from a branch" → "main" → "/ (root)"
5. Save and wait ~1 minute
6. Your converter will be live at `https://YOUR_USERNAME.github.io/REPO_NAME/`

## Limitations

- **No platoon splits**: Historical data doesn't include vs-LHP/vs-RHP splits, so these are estimated from handedness
- **No Statcast for pre-2015**: Sprint speed, OAA, arm strength estimated from traditional stats
- **Fielding is approximate**: Uses position-based defaults for historical players

## Contributing

Found a bug or have a suggestion? Open an issue or PR!

## License

MIT License - feel free to use, modify, and share.

## Credits

- Lahman Database maintained by [SABR](https://sabr.org/)
- MLB The Show 25 by Sony San Diego
- Conversion formulas developed through extensive testing and calibration
