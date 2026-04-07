"""
Pull 2025 MLB stats v2 - Fixed data quality:
- BB%/K% at full precision (not rounded)
- Sprint speed with correct player matching
- FanGraphs Spd metric as backup
- Proper Yordan Alvarez matching
"""

import json
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from pybaseball import batting_stats, statcast_sprint_speed, fielding_stats

TARGET_PLAYERS = [
    "Juan Soto",
    "Byron Buxton",
    "Vladimir Guerrero Jr.",
    "Yordan Alvarez",
    "Pete Crow-Armstrong",
    "Bobby Witt Jr.",
    "Xander Bogaerts",
    "Matt Shaw",
    "Hyeseong Kim",
    "Adley Rutschman",
]

# Statcast sprint speed name fragments (last name to match on)
SPRINT_NAMES = {
    "Juan Soto": "Soto, Juan",
    "Byron Buxton": "Buxton, Byron",
    "Vladimir Guerrero Jr.": "Guerrero Jr., Vladimir",
    "Yordan Alvarez": "Alvarez, Yordan",
    "Pete Crow-Armstrong": "Crow-Armstrong, Pete",
    "Bobby Witt Jr.": "Witt Jr., Bobby",
    "Xander Bogaerts": "Bogaerts, Xander",
    "Matt Shaw": "Shaw, Matt",
    "Hyeseong Kim": "Kim, Hyeseong",
    "Adley Rutschman": "Rutschman, Adley",
}


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if math.isnan(obj) else float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def pull_all():
    # --- Batting ---
    print("Pulling 2025 batting stats...")
    bat = batting_stats(2025, qual=0)

    # --- Sprint Speed ---
    print("Pulling 2025 sprint speed...")
    sprint_df = statcast_sprint_speed(2025)

    # --- Fielding ---
    print("Pulling 2025 fielding stats...")
    fld = fielding_stats(2025, qual=0)

    results = {}

    for name in TARGET_PLAYERS:
        # Find in batting
        match = bat[bat["Name"] == name]
        if match.empty:
            # Try partial match
            for part in name.split():
                match = bat[bat["Name"].str.contains(part, case=False, na=False)]
                if len(match) == 1:
                    break
        if match.empty:
            print(f"  WARNING: {name} not found in batting")
            continue
        if len(match) > 1:
            # Take the one with most PA
            match = match.sort_values("PA", ascending=False).head(1)

        row = match.iloc[0]

        # BB% and K% - keep full precision
        bb_pct = float(row["BB%"]) * 100  # convert 0.178 -> 17.8
        k_pct = float(row["K%"]) * 100

        # Sprint speed - exact name match
        sprint_name = SPRINT_NAMES.get(name, "")
        sprint_match = sprint_df[sprint_df["last_name, first_name"] == sprint_name]
        sprint_speed = float(sprint_match.iloc[0]["sprint_speed"]) if not sprint_match.empty else None
        hp_to_1b = float(sprint_match.iloc[0]["hp_to_1b"]) if not sprint_match.empty else None

        # FanGraphs speed metric
        fg_spd = float(row.get("Spd", 0))

        # Fielding
        fld_match = fld[fld["Name"] == name]
        if fld_match.empty:
            for part in name.split():
                fld_match = fld[fld["Name"].str.contains(part, case=False, na=False)]
                if len(fld_match) >= 1:
                    break
        drs = int(fld_match.iloc[0].get("DRS", 0)) if not fld_match.empty else None

        # OAA from fielding stats
        oaa = None
        if not fld_match.empty and "OAA" in fld_match.columns:
            oaa_val = fld_match.iloc[0].get("OAA")
            oaa = int(oaa_val) if oaa_val is not None and not (isinstance(oaa_val, float) and math.isnan(oaa_val)) else None

        results[name] = {
            "G": int(row["G"]),
            "PA": int(row["PA"]),
            "AB": int(row["AB"]),
            "H": int(row["H"]),
            "HR": int(row["HR"]),
            "SB": int(row["SB"]),
            "CS": int(row.get("CS", 0)),
            "BA": round(float(row["AVG"]), 3),
            "OBP": round(float(row["OBP"]), 3),
            "SLG": round(float(row["SLG"]), 3),
            "ISO": round(float(row["ISO"]), 3),
            "BB_pct": round(bb_pct, 1),
            "K_pct": round(k_pct, 1),
            "wOBA": round(float(row["wOBA"]), 3),
            "wRC_plus": round(float(row["wRC+"]), 0),
            "WAR": round(float(row["WAR"]), 1),
            "Clutch": round(float(row.get("Clutch", 0)), 2),
            "sprint_speed": sprint_speed,
            "hp_to_1b": hp_to_1b,
            "fg_spd": round(fg_spd, 1),
            "DRS": drs,
            "OAA": oaa,
            "Contact_pct": round(float(row.get("Contact%", 0)) * 100, 1) if row.get("Contact%") else None,
        }

        r = results[name]
        print(f"  {name:<25} .{str(r['BA'])[2:]:<4} {r['HR']:>2}HR  BB%={r['BB_pct']:>5.1f}  K%={r['K_pct']:>5.1f}  Sprint={r['sprint_speed']}  DRS={r['DRS']}")

    return results


if __name__ == "__main__":
    data = pull_all()

    with open("player_2025_stats_v2.json", "w") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)
    print(f"\nSaved {len(data)} players to player_2025_stats_v2.json")

    # Detailed table
    print(f"\n{'='*95}")
    print(f"{'Player':<25} {'BA':>5} {'OBP':>5} {'SLG':>5} {'ISO':>5} {'BB%':>5} {'K%':>5} {'wRC+':>5} {'Sprint':>6} {'DRS':>4} {'GP':>4}")
    print("-" * 95)
    for name, r in data.items():
        print(f"{name:<25} {r['BA']:.3f} {r['OBP']:.3f} {r['SLG']:.3f} {r['ISO']:.3f} {r['BB_pct']:>5.1f} {r['K_pct']:>5.1f} {r['wRC_plus']:>5.0f} {r['sprint_speed'] or 0:>6.1f} {r['DRS'] or 0:>4} {r['G']:>4}")
