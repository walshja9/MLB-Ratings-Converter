"""
Map 2025 real stats to MLB The Show 26 franchise ratings - V2
Fixed: BB%/K% precision, sprint speed accuracy
"""

import json
import numpy as np

with open("player_2025_stats_v2.json") as f:
    stats = json.load(f)
with open("player_2025_splits.json") as f:
    splits = json.load(f)

show = {
    "Juan Soto":              {"con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88, "vision": 72, "disc": 99, "clutch": 83, "bunt": 38, "drag": 56, "fielding": 53, "arm_str": 71, "arm_acc": 70, "speed": 42, "stealing": 77, "br_agg": 77, "dur": 98},
    "Byron Buxton":           {"con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84, "vision": 50, "disc": 50, "clutch": 78, "bunt": 35, "drag": 25, "fielding": 83, "arm_str": 78, "arm_acc": 71, "speed": 99, "stealing": 75, "br_agg": 61, "dur": 84},
    "Vladimir Guerrero Jr.":  {"con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73, "vision": 85, "disc": 84, "clutch": 92, "bunt": 35, "drag": 25, "fielding": 55, "arm_str": 59, "arm_acc": 62, "speed": 45, "stealing": 16, "br_agg": 26, "dur": 98},
    "Yordan Alvarez":         {"con_r": 80, "con_l": 99, "pwr_r": 93, "pwr_l": 80, "vision": 80, "disc": 86, "clutch": 99, "bunt": 35, "drag": 30, "fielding": 50, "arm_str": 51, "arm_acc": 73, "speed": 37, "stealing": 18, "br_agg": 16, "dur": 80},
    "Pete Crow-Armstrong":    {"con_r": 73, "con_l": 45, "pwr_r": 78, "pwr_l": 60, "vision": 59, "disc": 39, "clutch": 69, "bunt": 82, "drag": 80, "fielding": 99, "arm_str": 97, "arm_acc": 90, "speed": 93, "stealing": 83, "br_agg": 84, "dur": 92},
    "Bobby Witt Jr.":         {"con_r": 88, "con_l": 96, "pwr_r": 71, "pwr_l": 51, "vision": 78, "disc": 52, "clutch": 99, "bunt": 35, "drag": 25, "fielding": 99, "arm_str": 75, "arm_acc": 82, "speed": 99, "stealing": 82, "br_agg": 81, "dur": 98},
    "Xander Bogaerts":        {"con_r": 75, "con_l": 82, "pwr_r": 53, "pwr_l": 47, "vision": 78, "disc": 58, "clutch": 44, "bunt": 38, "drag": 25, "fielding": 85, "arm_str": 55, "arm_acc": 73, "speed": 59, "stealing": 65, "br_agg": 63, "dur": 87},
    "Matt Shaw":              {"con_r": 49, "con_l": 65, "pwr_r": 49, "pwr_l": 73, "vision": 65, "disc": 63, "clutch": 25, "bunt": 35, "drag": 44, "fielding": 62, "arm_str": 55, "arm_acc": 75, "speed": 83, "stealing": 56, "br_agg": 71, "dur": 91},
    "Hyeseong Kim":           {"con_r": 72, "con_l": 68, "pwr_r": 39, "pwr_l": 40, "vision": 45, "disc": 35, "clutch": 76, "bunt": 56, "drag": 25, "fielding": 79, "arm_str": 64, "arm_acc": 66, "speed": 78, "stealing": 70, "br_agg": 73, "dur": 88},
    "Adley Rutschman":        {"con_r": 60, "con_l": 91, "pwr_r": 58, "pwr_l": 59, "vision": 81, "disc": 70, "clutch": 63, "bunt": 35, "drag": 25, "fielding": 74, "arm_str": 94, "arm_acc": 64, "speed": 45, "stealing": 3, "br_agg": 2, "dur": 86},
}

names = list(show.keys())


def fit(x_vals, y_vals, label):
    x = np.array(x_vals, dtype=float)
    y = np.array(y_vals, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return None
    corr = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    coeffs, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    m, b = coeffs
    preds = m * x + b
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    return {"corr": round(corr, 3), "m": round(m, 2), "b": round(b, 1), "rmse": round(rmse, 1)}


def print_mapping(label, stat_name, x_vals, y_vals, fmt=".3f"):
    r = fit(x_vals, y_vals, label)
    print(f"\n--- {label} (Show) vs {stat_name} (Real) ---")
    print(f"  r = {r['corr']:<+7.3f}  RMSE = {r['rmse']:<5.1f}  Formula: {r['m']}x + {r['b']}")
    print(f"  {'Player':<25} {'Stat':>7} {'Show':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 52)
    for i, n in enumerate(names):
        pred = r["m"] * x_vals[i] + r["b"]
        print(f"  {n:<25} {x_vals[i]:>7{fmt}} {y_vals[i]:>5} {pred:>5.0f} {pred - y_vals[i]:>+5.0f}")
    return r


if __name__ == "__main__":
    print("=" * 75)
    print("  ATTRIBUTE MAPPING ANALYSIS v2 (Fixed Data)")
    print("=" * 75)

    results = {}

    # --- CONTACT ---
    ba_r = [splits[n]["vs_RHP"]["BA"] for n in names]
    con_r = [show[n]["con_r"] for n in names]
    results["Contact R"] = print_mapping("Contact R", "BA vs RHP", ba_r, con_r)

    ba_l = [splits[n]["vs_LHP"]["BA"] for n in names]
    con_l = [show[n]["con_l"] for n in names]
    results["Contact L"] = print_mapping("Contact L", "BA vs LHP", ba_l, con_l)

    # --- POWER ---
    iso_r = [splits[n]["vs_RHP"]["ISO"] for n in names]
    pwr_r = [show[n]["pwr_r"] for n in names]
    results["Power R"] = print_mapping("Power R", "ISO vs RHP", iso_r, pwr_r)

    iso_l = [splits[n]["vs_LHP"]["ISO"] for n in names]
    pwr_l = [show[n]["pwr_l"] for n in names]
    results["Power L"] = print_mapping("Power L", "ISO vs LHP", iso_l, pwr_l)

    # Try SLG for power instead of ISO
    slg_r = [splits[n]["vs_RHP"]["SLG"] for n in names]
    results["Power R (SLG)"] = print_mapping("Power R (alt)", "SLG vs RHP", slg_r, pwr_r)

    # --- VISION --- K% with full precision
    k_pct = [stats[n]["K_pct"] for n in names]
    vision = [show[n]["vision"] for n in names]
    results["Vision"] = print_mapping("Vision", "K%", k_pct, vision, fmt=".1f")

    # --- DISCIPLINE --- BB% with full precision
    bb_pct = [stats[n]["BB_pct"] for n in names]
    disc = [show[n]["disc"] for n in names]
    results["Discipline"] = print_mapping("Discipline", "BB%", bb_pct, disc, fmt=".1f")

    # --- SPEED --- with corrected sprint speed
    sprint = [stats[n]["sprint_speed"] for n in names]
    speed = [show[n]["speed"] for n in names]
    results["Speed"] = print_mapping("Speed", "Sprint Speed", sprint, speed, fmt=".1f")

    # --- DURABILITY ---
    gp = [stats[n]["G"] for n in names]
    dur = [show[n]["dur"] for n in names]
    results["Durability"] = print_mapping("Durability", "Games Played", gp, dur, fmt=".0f")

    # --- FIELDING ---
    drs = [stats[n]["DRS"] or 0 for n in names]
    fld = [show[n]["fielding"] for n in names]
    results["Fielding"] = print_mapping("Fielding", "DRS", drs, fld, fmt=".0f")

    # --- STEALING ---
    sb = [stats[n]["SB"] for n in names]
    stealing = [show[n]["stealing"] for n in names]
    results["Stealing"] = print_mapping("Stealing", "SB count", sb, stealing, fmt=".0f")

    # SB success rate
    sb_rate = []
    for n in names:
        s = stats[n]
        total = s["SB"] + s["CS"]
        sb_rate.append(s["SB"] / total * 100 if total > 0 else 0)
    results["Stealing (rate)"] = print_mapping("Stealing (alt)", "SB Success %", sb_rate, stealing, fmt=".1f")

    # --- CLUTCH ---
    clutch_stat = [stats[n]["Clutch"] for n in names]
    clutch_show = [show[n]["clutch"] for n in names]
    results["Clutch"] = print_mapping("Bat Clutch", "FG Clutch", clutch_stat, clutch_show, fmt=".2f")

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 75)
    print("  MAPPING QUALITY SUMMARY")
    print("=" * 75)
    print(f"\n  {'Attribute':<20} {'Real Stat':<18} {'Corr':>6} {'RMSE':>6}  Grade")
    print("  " + "-" * 60)

    for attr, r in sorted(results.items(), key=lambda x: -abs(x[1]["corr"])):
        abs_corr = abs(r["corr"])
        if abs_corr >= 0.85:
            grade = "A"
        elif abs_corr >= 0.7:
            grade = "B"
        elif abs_corr >= 0.5:
            grade = "C"
        else:
            grade = "F"
        stat_label = attr  # simplified
        print(f"  {attr:<20} {'':18} {r['corr']:>+6.3f} {r['rmse']:>6.1f}  {grade}")
