"""
Blended mapping analysis: use career data + 2025 season with proper weighting.
Tests whether blending improves the weak mappings (Power, Contact L, Fielding).
"""
import json
import numpy as np
from numpy.linalg import lstsq

with open("player_2025_stats_v2.json") as f:
    stats_2025 = json.load(f)
with open("player_2025_splits.json") as f:
    splits = json.load(f)
with open("career_data.json") as f:
    career = json.load(f)

show = {
    "Juan Soto":              {"con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88, "vision": 72, "disc": 99, "clutch": 83, "fielding": 53, "arm_str": 71, "arm_acc": 70, "speed": 42, "stealing": 77, "br_agg": 77, "dur": 98, "bunt": 38, "drag": 56},
    "Byron Buxton":           {"con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84, "vision": 50, "disc": 50, "clutch": 78, "fielding": 83, "arm_str": 78, "arm_acc": 71, "speed": 99, "stealing": 75, "br_agg": 61, "dur": 84, "bunt": 35, "drag": 25},
    "Vladimir Guerrero Jr.":  {"con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73, "vision": 85, "disc": 84, "clutch": 92, "fielding": 55, "arm_str": 59, "arm_acc": 62, "speed": 45, "stealing": 16, "br_agg": 26, "dur": 98, "bunt": 35, "drag": 25},
    "Yordan Alvarez":         {"con_r": 80, "con_l": 99, "pwr_r": 93, "pwr_l": 80, "vision": 80, "disc": 86, "clutch": 99, "fielding": 50, "arm_str": 51, "arm_acc": 73, "speed": 37, "stealing": 18, "br_agg": 16, "dur": 80, "bunt": 35, "drag": 30},
    "Pete Crow-Armstrong":    {"con_r": 73, "con_l": 45, "pwr_r": 78, "pwr_l": 60, "vision": 59, "disc": 39, "clutch": 69, "fielding": 99, "arm_str": 97, "arm_acc": 90, "speed": 93, "stealing": 83, "br_agg": 84, "dur": 92, "bunt": 82, "drag": 80},
    "Bobby Witt Jr.":         {"con_r": 88, "con_l": 96, "pwr_r": 71, "pwr_l": 51, "vision": 78, "disc": 52, "clutch": 99, "fielding": 99, "arm_str": 75, "arm_acc": 82, "speed": 99, "stealing": 82, "br_agg": 81, "dur": 98, "bunt": 35, "drag": 25},
    "Xander Bogaerts":        {"con_r": 75, "con_l": 82, "pwr_r": 53, "pwr_l": 47, "vision": 78, "disc": 58, "clutch": 44, "fielding": 85, "arm_str": 55, "arm_acc": 73, "speed": 59, "stealing": 65, "br_agg": 63, "dur": 87, "bunt": 38, "drag": 25},
    "Matt Shaw":              {"con_r": 49, "con_l": 65, "pwr_r": 49, "pwr_l": 73, "vision": 65, "disc": 63, "clutch": 25, "fielding": 62, "arm_str": 55, "arm_acc": 75, "speed": 83, "stealing": 56, "br_agg": 71, "dur": 91, "bunt": 35, "drag": 44},
    "Hyeseong Kim":           {"con_r": 72, "con_l": 68, "pwr_r": 39, "pwr_l": 40, "vision": 45, "disc": 35, "clutch": 76, "fielding": 79, "arm_str": 64, "arm_acc": 66, "speed": 78, "stealing": 70, "br_agg": 73, "dur": 88, "bunt": 56, "drag": 25},
    "Adley Rutschman":        {"con_r": 60, "con_l": 91, "pwr_r": 58, "pwr_l": 59, "vision": 81, "disc": 70, "clutch": 63, "fielding": 74, "arm_str": 94, "arm_acc": 64, "speed": 45, "stealing": 3, "br_agg": 2, "dur": 86, "bunt": 35, "drag": 25},
}
names = list(show.keys())

career_avg = career["career_avg"]
career_fielding = career["career_fielding"]


def fit(x, y, label=""):
    x, y = np.array(x, float), np.array(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return {"corr": 0, "m": 0, "b": 0, "rmse": 99, "preds": []}
    corr = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = lstsq(A, y, rcond=None)
    preds = c[0] * x + c[1]
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    return {"corr": round(corr, 3), "m": round(c[0], 2), "b": round(c[1], 1), "rmse": round(rmse, 1), "preds": preds}


def print_results(label, stat_name, x_vals, y_vals, r, fmt=".3f"):
    print(f"\n  {label}: r={r['corr']:.3f}  RMSE={r['rmse']:.1f}")
    print(f"  Formula: {r['m']}*{stat_name} + {r['b']}")
    print(f"  {'Player':<25} {'Stat':>7} {'Show':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 52)
    for i, n in enumerate(names):
        pred = r["m"] * x_vals[i] + r["b"]
        print(f"  {n:<25} {x_vals[i]:>7{fmt}} {y_vals[i]:>5} {pred:>5.0f} {pred - y_vals[i]:>+5.0f}")


# ================================================================
# POWER R - Career ISO blending
# ================================================================
print("=" * 75)
print("  POWER R: Career-Blended ISO")
print("=" * 75)

pwr_r = [show[n]["pwr_r"] for n in names]

# 2025 only (baseline)
iso_2025 = [stats_2025[n]["ISO"] for n in names]
r_2025 = fit(iso_2025, pwr_r)
print(f"\n  2025-only ISO -> Power R: r={r_2025['corr']:.3f}  RMSE={r_2025['rmse']:.1f}")

# Career avg ISO
iso_career = [career_avg[n]["ISO"] for n in names]
r_career = fit(iso_career, pwr_r)
print(f"  Career ISO -> Power R:    r={r_career['corr']:.3f}  RMSE={r_career['rmse']:.1f}")

# Blended: 60% 2025 + 40% career (test different weights)
best_blend = None
best_rmse = 99
for w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    blended = [w * iso_2025[i] + (1 - w) * iso_career[i] for i in range(len(names))]
    r = fit(blended, pwr_r)
    if r["rmse"] < best_rmse:
        best_rmse = r["rmse"]
        best_blend = w
        best_r = r
        best_vals = blended

print(f"  Best blend: {best_blend:.0%} 2025 + {1-best_blend:.0%} career")
print_results(f"Power R (blended {best_blend:.0%}/{1-best_blend:.0%})", "ISO_blend", best_vals, pwr_r, best_r)


# ================================================================
# POWER L - Career ISO blending
# ================================================================
print("\n" + "=" * 75)
print("  POWER L: Career-Blended ISO")
print("=" * 75)

pwr_l = [show[n]["pwr_l"] for n in names]

# Use overall ISO as proxy for Power L since LHP split samples are tiny
# But blend with career
iso_blend_l = best_vals  # same blended ISO
r_pl = fit(iso_blend_l, pwr_l)
print(f"  Blended ISO -> Power L: r={r_pl['corr']:.3f}  RMSE={r_pl['rmse']:.1f}")
print_results("Power L (blended ISO)", "ISO_blend", iso_blend_l, pwr_l, r_pl)


# ================================================================
# CONTACT R - Career BA blending
# ================================================================
print("\n" + "=" * 75)
print("  CONTACT R: Career-Blended BA vs RHP")
print("=" * 75)

con_r = [show[n]["con_r"] for n in names]

# 2025 split BA vs RHP
ba_r_2025 = [splits[n]["vs_RHP"]["BA"] for n in names]
r_2025_cr = fit(ba_r_2025, con_r)
print(f"  2025 BA vs RHP -> Contact R: r={r_2025_cr['corr']:.3f}  RMSE={r_2025_cr['rmse']:.1f}")

# Career BA (overall, more stable)
ba_career = [career_avg[n]["BA"] for n in names]
r_career_cr = fit(ba_career, con_r)
print(f"  Career BA -> Contact R:      r={r_career_cr['corr']:.3f}  RMSE={r_career_cr['rmse']:.1f}")

# Blended
best_blend_cr = None
best_rmse_cr = 99
for w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    blended = [w * ba_r_2025[i] + (1 - w) * ba_career[i] for i in range(len(names))]
    r = fit(blended, con_r)
    if r["rmse"] < best_rmse_cr:
        best_rmse_cr = r["rmse"]
        best_blend_cr = w
        best_r_cr = r
        best_vals_cr = blended

print(f"  Best blend: {best_blend_cr:.0%} 2025 + {1-best_blend_cr:.0%} career")
print_results(f"Contact R ({best_blend_cr:.0%}/{1-best_blend_cr:.0%})", "BA_blend", best_vals_cr, con_r, best_r_cr)


# ================================================================
# CONTACT L - Career BA blending
# ================================================================
print("\n" + "=" * 75)
print("  CONTACT L: Blended approaches")
print("=" * 75)

con_l = [show[n]["con_l"] for n in names]

# Use career BA as proxy
r_career_cl = fit(ba_career, con_l)
print(f"  Career BA -> Contact L:      r={r_career_cl['corr']:.3f}  RMSE={r_career_cl['rmse']:.1f}")

# OBP vs LHP (was 0.822)
obp_l = [splits[n]["vs_LHP"]["OBP"] for n in names]
r_obp_l = fit(obp_l, con_l)
print(f"  OBP vs LHP -> Contact L:     r={r_obp_l['corr']:.3f}  RMSE={r_obp_l['rmse']:.1f}")

# Career OBP
obp_career = [career_avg[n]["OBP"] for n in names]
r_obp_career = fit(obp_career, con_l)
print(f"  Career OBP -> Contact L:     r={r_obp_career['corr']:.3f}  RMSE={r_obp_career['rmse']:.1f}")

# Blend OBP vs LHP with career OBP
best_blend_cl = None
best_rmse_cl = 99
for w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    blended = [w * obp_l[i] + (1 - w) * obp_career[i] for i in range(len(names))]
    r = fit(blended, con_l)
    if r["rmse"] < best_rmse_cl:
        best_rmse_cl = r["rmse"]
        best_blend_cl = w
        best_r_cl = r
        best_vals_cl = blended

print(f"  Best blend: {best_blend_cl:.0%} OBP_vL + {1-best_blend_cl:.0%} career OBP")
print_results(f"Contact L ({best_blend_cl:.0%}/{1-best_blend_cl:.0%})", "OBP_blend", best_vals_cl, con_l, best_r_cl)


# ================================================================
# FIELDING - Multi-year OAA
# ================================================================
print("\n" + "=" * 75)
print("  FIELDING: Multi-year OAA")
print("=" * 75)

fld = [show[n]["fielding"] for n in names]

# 2025 OAA only
oaa_2025 = []
for n in names:
    if n in career_fielding and 2025 in career_fielding[n]:
        val = career_fielding[n][2025].get("OAA")
        oaa_2025.append(val if val is not None else 0)
    else:
        oaa_2025.append(0)

r_oaa_2025 = fit(oaa_2025, fld)
print(f"  2025 OAA -> Fielding:    r={r_oaa_2025['corr']:.3f}  RMSE={r_oaa_2025['rmse']:.1f}")

# Career avg OAA (simple average across years)
oaa_career_avg = []
for n in names:
    if n in career_fielding:
        vals = [career_fielding[n][str(y) if str(y) in career_fielding[n] else y].get("OAA")
                for y in career_fielding[n] if career_fielding[n][y].get("OAA") is not None]
        oaa_career_avg.append(np.mean(vals) if vals else 0)
    else:
        oaa_career_avg.append(0)

r_oaa_career = fit(oaa_career_avg, fld)
print(f"  Career avg OAA -> Fld:   r={r_oaa_career['corr']:.3f}  RMSE={r_oaa_career['rmse']:.1f}")

# Recency-weighted OAA (more recent years count more)
oaa_weighted = []
weights_by_year = {2022: 0.1, 2023: 0.15, 2024: 0.3, 2025: 0.45}
for n in names:
    if n in career_fielding:
        total_w = 0
        total_oaa = 0
        for y_key, data in career_fielding[n].items():
            y = int(y_key)
            oaa_val = data.get("OAA")
            if oaa_val is not None and y in weights_by_year:
                w = weights_by_year[y]
                total_oaa += oaa_val * w
                total_w += w
        oaa_weighted.append(total_oaa / total_w if total_w > 0 else 0)
    else:
        oaa_weighted.append(0)

r_oaa_weighted = fit(oaa_weighted, fld)
print(f"  Recency-weighted OAA:    r={r_oaa_weighted['corr']:.3f}  RMSE={r_oaa_weighted['rmse']:.1f}")

# Print best
best_oaa = max([(r_oaa_2025, oaa_2025, "2025 OAA"),
                (r_oaa_career, oaa_career_avg, "Career avg OAA"),
                (r_oaa_weighted, oaa_weighted, "Weighted OAA")],
               key=lambda x: abs(x[0]["corr"]))

print(f"\n  Best: {best_oaa[2]}")
print_results(f"Fielding ({best_oaa[2]})", "OAA", best_oaa[1], fld, best_oaa[0], fmt=".1f")


# ================================================================
# CLUTCH - Career wOBA / BA blending
# ================================================================
print("\n" + "=" * 75)
print("  CLUTCH: Career-Blended")
print("=" * 75)

clutch = [show[n]["clutch"] for n in names]

woba_2025 = [stats_2025[n]["wOBA"] for n in names]
woba_career = [career_avg[n]["wOBA"] for n in names]
ba_2025 = [stats_2025[n]["BA"] for n in names]
ba_career_vals = [career_avg[n]["BA"] for n in names]

for stat_name, vals_25, vals_car in [
    ("wOBA", woba_2025, woba_career),
    ("BA", ba_2025, ba_career_vals),
]:
    r_25 = fit(vals_25, clutch)
    r_car = fit(vals_car, clutch)
    print(f"  2025 {stat_name} -> Clutch:   r={r_25['corr']:.3f}  RMSE={r_25['rmse']:.1f}")
    print(f"  Career {stat_name} -> Clutch: r={r_car['corr']:.3f}  RMSE={r_car['rmse']:.1f}")

    # Blend
    best_w = None
    best_rm = 99
    for w in [0.3, 0.4, 0.5, 0.6, 0.7]:
        blended = [w * vals_25[i] + (1 - w) * vals_car[i] for i in range(len(names))]
        r = fit(blended, clutch)
        if r["rmse"] < best_rm:
            best_rm = r["rmse"]
            best_w = w
            best_blend_r = r
            best_blend_v = blended
    print(f"  Best blend {stat_name}: {best_w:.0%}/{1-best_w:.0%}  r={best_blend_r['corr']:.3f}  RMSE={best_blend_r['rmse']:.1f}")


# ================================================================
# FINAL COMPREHENSIVE SUMMARY
# ================================================================
print("\n" + "=" * 75)
print("  FINAL MAPPING QUALITY - ALL ATTRIBUTES")
print("=" * 75)

# Recompute confirmed formulas with career blending where applicable
vision_vals = [stats_2025[n]["K_pct"] for n in names]
speed_vals = [stats_2025[n]["sprint_speed"] for n in names]
disc_vals = [stats_2025[n]["BB_pct"] for n in names]
gp_vals = [stats_2025[n]["G"] for n in names]
sb_vals = [stats_2025[n]["SB"] for n in names]

all_mappings = [
    ("Vision",       "K%",              vision_vals, [show[n]["vision"] for n in names]),
    ("Speed",        "Sprint Speed",    speed_vals,  [show[n]["speed"] for n in names]),
    ("Discipline",   "BB%",             disc_vals,   [show[n]["disc"] for n in names]),
    ("Contact R",    "BA_vR blend",     best_vals_cr, con_r),
    ("Power R",      "ISO blend",       best_vals, pwr_r),
    ("Fielding",     best_oaa[2],       best_oaa[1], fld),
    ("Contact L",    "OBP blend",       best_vals_cl, con_l),
    ("Stealing",     "SB count",        [float(x) for x in sb_vals], [show[n]["stealing"] for n in names]),
    ("Durability",   "GP",              [float(x) for x in gp_vals], [show[n]["dur"] for n in names]),
    ("Power L",      "ISO blend",       best_vals, pwr_l),
]

print(f"\n  {'Attribute':<15} {'Stat':<18} {'r':>6} {'RMSE':>6}  Grade")
print("  " + "-" * 55)
for attr, stat, x, y in sorted(all_mappings, key=lambda t: -abs(fit(t[2], t[3])["corr"])):
    r = fit(x, y)
    grade = "A+" if abs(r["corr"]) >= 0.95 else "A" if abs(r["corr"]) >= 0.85 else "B" if abs(r["corr"]) >= 0.7 else "C" if abs(r["corr"]) >= 0.5 else "F"
    print(f"  {attr:<15} {stat:<18} {r['corr']:>+.3f} {r['rmse']:>5.1f}  {grade}")

print(f"\n  NOT STAT-DERIVABLE (scouting/reputation):")
print(f"  - Batting Clutch")
print(f"  - Bunting / Drag Bunt")
print(f"  - Arm Strength / Arm Accuracy")
print(f"  - Reaction stats (position-specific templates)")
