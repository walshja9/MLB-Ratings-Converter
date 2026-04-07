"""
Pull 2025 MLB stats for our 10 players using pybaseball.
Maps real stats to MLB The Show attribute categories.
"""

import json
import math
import warnings
warnings.filterwarnings("ignore")
import numpy as np


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if math.isnan(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

from pybaseball import (
    batting_stats,
    batting_stats_bref,
    statcast_sprint_speed,
    fielding_stats,
)

# Our 10 players - using FanGraphs names
TARGET_PLAYERS = {
    "Juan Soto": "OF",
    "Byron Buxton": "OF",
    "Vladimir Guerrero Jr.": "1B",
    "Yordan Alvarez": "LF",
    "Pete Crow-Armstrong": "OF",
    "Bobby Witt Jr.": "SS",
    "Xander Bogaerts": "SS",
    "Matt Shaw": "3B",
    "Hyeseong Kim": "2B",
    "Adley Rutschman": "C",
}


def pull_batting_stats():
    """Pull 2025 batting stats from FanGraphs."""
    print("Pulling 2025 batting stats from FanGraphs...")
    df = batting_stats(2025, qual=0)

    results = {}
    for name in TARGET_PLAYERS:
        # Try exact match first, then partial
        match = df[df["Name"] == name]
        if match.empty:
            match = df[df["Name"].str.contains(name.split()[1], case=False, na=False)]
        if match.empty:
            print(f"  WARNING: Could not find {name}")
            continue

        row = match.iloc[0]
        stats = {
            "name": name,
            "team": row.get("Team", ""),
            "G": int(row.get("G", 0)),
            "PA": int(row.get("PA", 0)),
            "AB": int(row.get("AB", 0)),
            "H": int(row.get("H", 0)),
            "HR": int(row.get("HR", 0)),
            "SB": int(row.get("SB", 0)),
            "BA": round(row.get("AVG", 0), 3),
            "OBP": round(row.get("OBP", 0), 3),
            "SLG": round(row.get("SLG", 0), 3),
            "OPS": round(row.get("OBP", 0) + row.get("SLG", 0), 3),
            "ISO": round(row.get("ISO", 0), 3),
            "BB_pct": round(row.get("BB%", 0), 1) if isinstance(row.get("BB%", 0), (int, float)) else row.get("BB%", ""),
            "K_pct": round(row.get("K%", 0), 1) if isinstance(row.get("K%", 0), (int, float)) else row.get("K%", ""),
            "wOBA": round(row.get("wOBA", 0), 3),
            "wRC_plus": round(row.get("wRC+", 0), 1),
            "WAR": round(row.get("WAR", 0), 1),
        }
        results[name] = stats
        print(f"  Found {name}: .{str(stats['BA'])[2:]} / .{str(stats['OBP'])[2:]} / .{str(stats['SLG'])[2:]}, {stats['HR']} HR, {stats['WAR']} WAR")

    return results


def pull_sprint_speed():
    """Pull 2025 Statcast sprint speed data."""
    print("\nPulling 2025 sprint speed from Statcast...")
    try:
        df = statcast_sprint_speed(2025)
        results = {}
        for name in TARGET_PLAYERS:
            # Sprint speed uses slightly different name formats
            match = df[df["last_name, first_name"].str.contains(name.split()[-1], case=False, na=False)]
            if not match.empty:
                speed = match.iloc[0].get("hp_to_1b", None)
                sprint = match.iloc[0].get("sprint_speed", None)
                results[name] = {
                    "hp_to_1b": round(speed, 2) if speed else None,
                    "sprint_speed": round(sprint, 1) if sprint else None,
                }
                print(f"  {name}: sprint speed = {results[name]['sprint_speed']}")
            else:
                print(f"  WARNING: No sprint data for {name}")
        return results
    except Exception as e:
        print(f"  Sprint speed pull failed: {e}")
        return {}


def pull_fielding():
    """Pull 2025 fielding stats from FanGraphs."""
    print("\nPulling 2025 fielding stats from FanGraphs...")
    try:
        df = fielding_stats(2025, qual=0)
        results = {}
        for name in TARGET_PLAYERS:
            match = df[df["Name"] == name]
            if match.empty:
                match = df[df["Name"].str.contains(name.split()[1], case=False, na=False)]
            if not match.empty:
                row = match.iloc[0]
                results[name] = {
                    "DRS": row.get("DRS", None),
                    "UZR": round(row.get("UZR", 0), 1) if row.get("UZR") else None,
                    "OAA": row.get("OAA", None),
                    "Pos": row.get("Pos", ""),
                }
                print(f"  {name}: DRS={results[name]['DRS']}, UZR={results[name]['UZR']}")
            else:
                print(f"  WARNING: No fielding data for {name}")
        return results
    except Exception as e:
        print(f"  Fielding pull failed: {e}")
        return {}


if __name__ == "__main__":
    all_data = {}

    batting = pull_batting_stats()
    sprint = pull_sprint_speed()
    fielding = pull_fielding()

    # Combine
    for name in TARGET_PLAYERS:
        all_data[name] = {
            "position": TARGET_PLAYERS[name],
            "batting": batting.get(name, {}),
            "sprint": sprint.get(name, {}),
            "fielding": fielding.get(name, {}),
        }

    # Save to JSON
    output_path = "player_2025_stats.json"
    with open(output_path, "w") as f:
        json.dump(all_data, f, indent=2, cls=NumpyEncoder)
    print(f"\nSaved to {output_path}")

    # Print summary table
    print(f"\n{'='*80}")
    print(f"{'Player':<22} {'BA':>6} {'OBP':>6} {'SLG':>6} {'HR':>4} {'BB%':>6} {'K%':>6} {'wRC+':>6} {'WAR':>5}")
    print("-" * 80)
    for name in TARGET_PLAYERS:
        b = batting.get(name, {})
        if b:
            print(f"{name:<22} {b['BA']:>6.3f} {b['OBP']:>6.3f} {b['SLG']:>6.3f} {b['HR']:>4} {str(b['BB_pct']):>6} {str(b['K_pct']):>6} {b['wRC_plus']:>6.0f} {b['WAR']:>5.1f}")
