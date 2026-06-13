"""
Map 2025 real stats to MLB The Show 26 franchise ratings.
Find the conversion formulas for each attribute.
"""

import json
import numpy as np

# Load real stats
with open("player_2025_stats.json") as f:
    real_stats = json.load(f)
with open("player_2025_splits.json") as f:
    splits = json.load(f)

# Show ratings from player_data.py
show_ratings = {
    "Juan Soto": {
        "con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88,
        "vision": 72, "disc": 99, "clutch": 83, "bunt": 38, "drag": 56,
        "fielding": 53, "arm_str": 71, "arm_acc": 70,
        "speed": 42, "stealing": 77, "br_agg": 77, "dur": 98,
    },
    "Byron Buxton": {
        "con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84,
        "vision": 50, "disc": 50, "clutch": 78, "bunt": 35, "drag": 25,
        "fielding": 83, "arm_str": 78, "arm_acc": 71,
        "speed": 99, "stealing": 75, "br_agg": 61, "dur": 84,
    },
    "Vladimir Guerrero Jr.": {
        "con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73,
        "vision": 85, "disc": 84, "clutch": 92, "bunt": 35, "drag": 25,
        "fielding": 55, "arm_str": 59, "arm_acc": 62,
        "speed": 45, "stealing": 16, "br_agg": 26, "dur": 98,
    },
    "Yordan Alvarez": {
        "con_r": 80, "con_l": 99, "pwr_r": 93, "pwr_l": 80,
        "vision": 80, "disc": 86, "clutch": 99, "bunt": 35, "drag": 30,
        "fielding": 50, "arm_str": 51, "arm_acc": 73,
        "speed": 37, "stealing": 18, "br_agg": 16, "dur": 80,
    },
    "Pete Crow-Armstrong": {
        "con_r": 73, "con_l": 45, "pwr_r": 78, "pwr_l": 60,
        "vision": 59, "disc": 39, "clutch": 69, "bunt": 82, "drag": 80,
        "fielding": 99, "arm_str": 97, "arm_acc": 90,
        "speed": 93, "stealing": 83, "br_agg": 84, "dur": 92,
    },
    "Bobby Witt Jr.": {
        "con_r": 88, "con_l": 96, "pwr_r": 71, "pwr_l": 51,
        "vision": 78, "disc": 52, "clutch": 99, "bunt": 35, "drag": 25,
        "fielding": 99, "arm_str": 75, "arm_acc": 82,
        "speed": 99, "stealing": 82, "br_agg": 81, "dur": 98,
    },
    "Xander Bogaerts": {
        "con_r": 75, "con_l": 82, "pwr_r": 53, "pwr_l": 47,
        "vision": 78, "disc": 58, "clutch": 44, "bunt": 38, "drag": 25,
        "fielding": 85, "arm_str": 55, "arm_acc": 73,
        "speed": 59, "stealing": 65, "br_agg": 63, "dur": 87,
    },
    "Matt Shaw": {
        "con_r": 49, "con_l": 65, "pwr_r": 49, "pwr_l": 73,
        "vision": 65, "disc": 63, "clutch": 25, "bunt": 35, "drag": 44,
        "fielding": 62, "arm_str": 55, "arm_acc": 75,
        "speed": 83, "stealing": 56, "br_agg": 71, "dur": 91,
    },
    "Hyeseong Kim": {
        "con_r": 72, "con_l": 68, "pwr_r": 39, "pwr_l": 40,
        "vision": 45, "disc": 35, "clutch": 76, "bunt": 56, "drag": 25,
        "fielding": 79, "arm_str": 64, "arm_acc": 66,
        "speed": 78, "stealing": 70, "br_agg": 73, "dur": 88,
    },
    "Adley Rutschman": {
        "con_r": 60, "con_l": 91, "pwr_r": 58, "pwr_l": 59,
        "vision": 81, "disc": 70, "clutch": 63, "bunt": 35, "drag": 25,
        "fielding": 74, "arm_str": 94, "arm_acc": 64,
        "speed": 45, "stealing": 3, "br_agg": 2, "dur": 86,
    },
}


def correlate(stat_values, rating_values, label):
    """Compute correlation and linear fit between a stat and a rating."""
    x = np.array(stat_values, dtype=float)
    y = np.array(rating_values, dtype=float)

    # Remove any NaN/None pairs
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    if len(x) < 3:
        return None

    corr = np.corrcoef(x, y)[0, 1]

    # Linear fit: y = mx + b
    A = np.column_stack([x, np.ones(len(x))])
    coeffs, residuals, _, _ = np.linalg.lstsq(A, y, rcond=None)
    m, b = coeffs
    rmse = np.sqrt(np.mean((y - (m * x + b)) ** 2))

    return {
        "correlation": round(corr, 3),
        "slope": round(m, 2),
        "intercept": round(b, 2),
        "rmse": round(rmse, 1),
        "n": len(x),
    }


if __name__ == "__main__":
    names = list(show_ratings.keys())

    # ================================================================
    # CONTACT vs R  <->  BA vs RHP
    # ================================================================
    print("=" * 75)
    print("  ATTRIBUTE MAPPING ANALYSIS")
    print("=" * 75)

    # Build comparison data
    mappings = []

    # --- CONTACT ---
    print("\n--- CONTACT vs RIGHT (Show) vs BA vs RHP (Real) ---")
    ba_r = [splits[n]["vs_RHP"]["BA"] for n in names]
    con_r = [show_ratings[n]["con_r"] for n in names]
    result = correlate(ba_r, con_r, "Contact R vs BA vs RHP")
    print(f"  Correlation: {result['correlation']}")
    print(f"  Formula: Contact_R = {result['slope']} * BA_vs_RHP + {result['intercept']}")
    print(f"  RMSE: {result['rmse']}")

    print(f"\n  {'Player':<22} {'BA_vR':>6} {'ConR':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result["slope"] * ba_r[i] + result["intercept"]
        print(f"  {n:<22} {ba_r[i]:>6.3f} {con_r[i]:>5} {pred:>5.0f} {pred - con_r[i]:>+5.0f}")

    print("\n--- CONTACT vs LEFT (Show) vs BA vs LHP (Real) ---")
    ba_l = [splits[n]["vs_LHP"]["BA"] for n in names]
    con_l = [show_ratings[n]["con_l"] for n in names]
    result_cl = correlate(ba_l, con_l, "Contact L vs BA vs LHP")
    print(f"  Correlation: {result_cl['correlation']}")
    print(f"  Formula: Contact_L = {result_cl['slope']} * BA_vs_LHP + {result_cl['intercept']}")
    print(f"  RMSE: {result_cl['rmse']}")

    print(f"\n  {'Player':<22} {'BA_vL':>6} {'ConL':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_cl["slope"] * ba_l[i] + result_cl["intercept"]
        print(f"  {n:<22} {ba_l[i]:>6.3f} {con_l[i]:>5} {pred:>5.0f} {pred - con_l[i]:>+5.0f}")

    # --- POWER ---
    print("\n--- POWER vs RIGHT (Show) vs ISO vs RHP (Real) ---")
    iso_r = [splits[n]["vs_RHP"]["ISO"] for n in names]
    pwr_r = [show_ratings[n]["pwr_r"] for n in names]
    result_pr = correlate(iso_r, pwr_r, "Power R vs ISO vs RHP")
    print(f"  Correlation: {result_pr['correlation']}")
    print(f"  Formula: Power_R = {result_pr['slope']} * ISO_vs_RHP + {result_pr['intercept']}")
    print(f"  RMSE: {result_pr['rmse']}")

    print(f"\n  {'Player':<22} {'ISO_vR':>6} {'PwrR':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_pr["slope"] * iso_r[i] + result_pr["intercept"]
        print(f"  {n:<22} {iso_r[i]:>6.3f} {pwr_r[i]:>5} {pred:>5.0f} {pred - pwr_r[i]:>+5.0f}")

    print("\n--- POWER vs LEFT (Show) vs ISO vs LHP (Real) ---")
    iso_l = [splits[n]["vs_LHP"]["ISO"] for n in names]
    pwr_l = [show_ratings[n]["pwr_l"] for n in names]
    result_pl = correlate(iso_l, pwr_l, "Power L vs ISO vs LHP")
    print(f"  Correlation: {result_pl['correlation']}")
    print(f"  Formula: Power_L = {result_pl['slope']} * ISO_vs_LHP + {result_pl['intercept']}")
    print(f"  RMSE: {result_pl['rmse']}")

    print(f"\n  {'Player':<22} {'ISO_vL':>6} {'PwrL':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_pl["slope"] * iso_l[i] + result_pl["intercept"]
        print(f"  {n:<22} {iso_l[i]:>6.3f} {pwr_l[i]:>5} {pred:>5.0f} {pred - pwr_l[i]:>+5.0f}")

    # --- VISION (inverse of K%) ---
    print("\n--- VISION (Show) vs K% (Real) ---")
    k_pct = [real_stats[n]["batting"]["K_pct"] * 100 if real_stats[n]["batting"]["K_pct"] < 1 else real_stats[n]["batting"]["K_pct"] for n in names]
    vision = [show_ratings[n]["vision"] for n in names]
    result_v = correlate(k_pct, vision, "Vision vs K%")
    print(f"  Correlation: {result_v['correlation']}")
    print(f"  Formula: Vision = {result_v['slope']} * K% + {result_v['intercept']}")
    print(f"  RMSE: {result_v['rmse']}")

    print(f"\n  {'Player':<22} {'K%':>6} {'Vis':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_v["slope"] * k_pct[i] + result_v["intercept"]
        print(f"  {n:<22} {k_pct[i]:>5.1f}% {vision[i]:>5} {pred:>5.0f} {pred - vision[i]:>+5.0f}")

    # --- PLATE DISCIPLINE (BB%) ---
    print("\n--- PLATE DISCIPLINE (Show) vs BB% (Real) ---")
    bb_pct = [real_stats[n]["batting"]["BB_pct"] * 100 if real_stats[n]["batting"]["BB_pct"] < 1 else real_stats[n]["batting"]["BB_pct"] for n in names]
    disc = [show_ratings[n]["disc"] for n in names]
    result_d = correlate(bb_pct, disc, "Disc vs BB%")
    print(f"  Correlation: {result_d['correlation']}")
    print(f"  Formula: Discipline = {result_d['slope']} * BB% + {result_d['intercept']}")
    print(f"  RMSE: {result_d['rmse']}")

    print(f"\n  {'Player':<22} {'BB%':>6} {'Disc':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_d["slope"] * bb_pct[i] + result_d["intercept"]
        print(f"  {n:<22} {bb_pct[i]:>5.1f}% {disc[i]:>5} {pred:>5.0f} {pred - disc[i]:>+5.0f}")

    # --- SPEED ---
    print("\n--- SPEED (Show) vs Sprint Speed (Real) ---")
    sprint = [real_stats[n]["sprint"].get("sprint_speed", 0) if real_stats[n].get("sprint") else 0 for n in names]
    speed = [show_ratings[n]["speed"] for n in names]
    result_s = correlate(sprint, speed, "Speed vs Sprint Speed")
    print(f"  Correlation: {result_s['correlation']}")
    print(f"  Formula: Speed = {result_s['slope']} * Sprint_Speed + {result_s['intercept']}")
    print(f"  RMSE: {result_s['rmse']}")

    print(f"\n  {'Player':<22} {'Sprint':>6} {'Spd':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_s["slope"] * sprint[i] + result_s["intercept"]
        print(f"  {n:<22} {sprint[i]:>6.1f} {speed[i]:>5} {pred:>5.0f} {pred - speed[i]:>+5.0f}")

    # --- DURABILITY ---
    print("\n--- DURABILITY (Show) vs Games Played (Real) ---")
    games = [real_stats[n]["batting"]["G"] for n in names]
    dur = [show_ratings[n]["dur"] for n in names]
    result_dur = correlate(games, dur, "Durability vs GP")
    print(f"  Correlation: {result_dur['correlation']}")
    print(f"  Formula: Durability = {result_dur['slope']} * GP + {result_dur['intercept']}")
    print(f"  RMSE: {result_dur['rmse']}")

    print(f"\n  {'Player':<22} {'GP':>5} {'Dur':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_dur["slope"] * games[i] + result_dur["intercept"]
        print(f"  {n:<22} {games[i]:>5} {dur[i]:>5} {pred:>5.0f} {pred - dur[i]:>+5.0f}")

    # --- FIELDING ---
    print("\n--- FIELDING (Show) vs DRS (Real) ---")
    drs = [real_stats[n]["fielding"].get("DRS", 0) or 0 for n in names]
    fld = [show_ratings[n]["fielding"] for n in names]
    result_fld = correlate(drs, fld, "Fielding vs DRS")
    print(f"  Correlation: {result_fld['correlation']}")
    print(f"  Formula: Fielding = {result_fld['slope']} * DRS + {result_fld['intercept']}")
    print(f"  RMSE: {result_fld['rmse']}")

    print(f"\n  {'Player':<22} {'DRS':>5} {'Fld':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 50)
    for i, n in enumerate(names):
        pred = result_fld["slope"] * drs[i] + result_fld["intercept"]
        print(f"  {n:<22} {drs[i]:>5} {fld[i]:>5} {pred:>5.0f} {pred - fld[i]:>+5.0f}")

    # --- SUMMARY ---
    print("\n" + "=" * 75)
    print("  MAPPING SUMMARY")
    print("=" * 75)
    all_results = [
        ("Contact R", "BA vs RHP", result),
        ("Contact L", "BA vs LHP", result_cl),
        ("Power R", "ISO vs RHP", result_pr),
        ("Power L", "ISO vs LHP", result_pl),
        ("Vision", "K% (inv)", result_v),
        ("Discipline", "BB%", result_d),
        ("Speed", "Sprint Speed", result_s),
        ("Durability", "Games Played", result_dur),
        ("Fielding", "DRS", result_fld),
    ]

    print(f"\n  {'Attribute':<15} {'Real Stat':<15} {'Corr':>6} {'RMSE':>6} {'Formula'}")
    print("  " + "-" * 70)
    for attr, stat, r in all_results:
        print(f"  {attr:<15} {stat:<15} {r['correlation']:>+6.3f} {r['rmse']:>6.1f}   {r['slope']}x + {r['intercept']}")
