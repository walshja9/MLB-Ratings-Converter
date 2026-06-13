"""
Pull 2025 platoon splits for our 10 players using Statcast pitch-by-pitch data.
Computes BA, SLG, ISO vs RHP and vs LHP.
"""

import json
import warnings
warnings.filterwarnings("ignore")

from pybaseball import statcast_batter
import pandas as pd

# Load player IDs
with open("player_mlbam_ids.json") as f:
    player_ids = json.load(f)

# 2025 season dates
START = "2025-03-20"
END = "2025-10-01"


def compute_splits(df):
    """Compute batting splits vs RHP and LHP from statcast data."""
    results = {}

    for hand, label in [("R", "vs_RHP"), ("L", "vs_LHP")]:
        subset = df[df["p_throws"] == hand]

        # Filter to at-bats (exclude walks, HBP, sac bunts, etc.)
        ab_events = [
            "single", "double", "triple", "home_run",
            "strikeout", "field_out", "grounded_into_double_play",
            "force_out", "fielders_choice", "fielders_choice_out",
            "double_play", "strikeout_double_play", "triple_play",
            "field_error",
        ]

        at_bats = subset[subset["events"].isin(ab_events)]
        all_pa = subset[subset["events"].notna()]

        if len(at_bats) == 0:
            results[label] = {"PA": 0, "AB": 0, "BA": 0, "SLG": 0, "ISO": 0, "OBP": 0, "BB_pct": 0, "K_pct": 0}
            continue

        hits = at_bats[at_bats["events"].isin(["single", "double", "triple", "home_run"])]
        singles = len(at_bats[at_bats["events"] == "single"])
        doubles = len(at_bats[at_bats["events"] == "double"])
        triples = len(at_bats[at_bats["events"] == "triple"])
        homers = len(at_bats[at_bats["events"] == "home_run"])
        total_bases = singles + 2 * doubles + 3 * triples + 4 * homers

        n_ab = len(at_bats)
        n_pa = len(all_pa)
        n_hits = len(hits)
        n_bb = len(all_pa[all_pa["events"].isin(["walk"])])
        n_hbp = len(all_pa[all_pa["events"].isin(["hit_by_pitch"])])
        n_k = len(all_pa[all_pa["events"].str.contains("strikeout", na=False)])

        ba = n_hits / n_ab if n_ab > 0 else 0
        slg = total_bases / n_ab if n_ab > 0 else 0
        iso = slg - ba
        obp = (n_hits + n_bb + n_hbp) / n_pa if n_pa > 0 else 0
        bb_pct = n_bb / n_pa if n_pa > 0 else 0
        k_pct = n_k / n_pa if n_pa > 0 else 0

        results[label] = {
            "PA": n_pa,
            "AB": n_ab,
            "H": n_hits,
            "HR": homers,
            "BA": round(ba, 3),
            "SLG": round(slg, 3),
            "ISO": round(iso, 3),
            "OBP": round(obp, 3),
            "BB_pct": round(bb_pct * 100, 1),
            "K_pct": round(k_pct * 100, 1),
        }

    return results


if __name__ == "__main__":
    all_splits = {}

    for name, mlbam_id in player_ids.items():
        print(f"Pulling statcast data for {name} (ID: {mlbam_id})...")
        try:
            df = statcast_batter(START, END, mlbam_id)
            if df.empty:
                print(f"  WARNING: No data for {name}")
                continue

            splits = compute_splits(df)
            all_splits[name] = splits

            for label in ["vs_RHP", "vs_LHP"]:
                s = splits[label]
                print(f"  {label}: {s['PA']:>4} PA, .{str(s['BA'])[2:]:>3} BA, .{str(s['SLG'])[2:]:>3} SLG, .{str(s['ISO'])[2:]:>3} ISO, {s['BB_pct']:>4.1f}% BB, {s['K_pct']:>4.1f}% K")

        except Exception as e:
            print(f"  ERROR: {e}")

    # Save
    with open("player_2025_splits.json", "w") as f:
        json.dump(all_splits, f, indent=2)
    print(f"\nSaved splits for {len(all_splits)} players to player_2025_splits.json")

    # Summary table
    print(f"\n{'='*85}")
    print(f"{'Player':<22} {'':>4} {'PA':>4} {'BA':>6} {'SLG':>6} {'ISO':>6} {'BB%':>6} {'K%':>6}")
    print("-" * 85)
    for name in player_ids:
        if name in all_splits:
            for label in ["vs_RHP", "vs_LHP"]:
                s = all_splits[name][label]
                prefix = name if label == "vs_RHP" else ""
                print(f"{prefix:<22} {label:>7} {s['PA']:>4} {s['BA']:>6.3f} {s['SLG']:>6.3f} {s['ISO']:>6.3f} {s['BB_pct']:>5.1f}% {s['K_pct']:>5.1f}%")
