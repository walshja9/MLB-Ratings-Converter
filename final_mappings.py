"""
Final mapping analysis with corrected career data.
Tests every attribute with optimal blending weights.
"""
import json
import numpy as np
from numpy.linalg import lstsq

with open("player_2025_stats_v2.json") as f:
    stats = json.load(f)
with open("player_2025_splits.json") as f:
    splits = json.load(f)
with open("career_data_fixed.json") as f:
    career = json.load(f)

career_avg = career["career_avg"]
career_fld = career["career_fielding"]

show = {
    "Juan Soto":              {"con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88, "vision": 72, "disc": 99, "clutch": 83, "fielding": 53, "arm_str": 71, "arm_acc": 70, "speed": 42, "stealing": 77, "br_agg": 77, "dur": 98, "bunt": 38, "drag": 56},
    "Byron Buxton":           {"con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84, "vision": 50, "disc": 50, "clutch": 78, "fielding": 83, "arm_str": 78, "arm_acc": 71, "speed": 99, "stealing": 75, "br_agg": 61, "dur": 84, "bunt": 35, "drag": 25},
    "Vladimir Guerrero Jr.":  {"con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73, "vision": 85, "disc": 84, "clutch": 92, "fielding": 55, "arm_str": 59, "arm_acc": 62, "speed": 45, "stealing": 16, "br_agg": 26, "dur": 98, "bunt": 35, "drag": 25},
    "Yordan Alvarez":         {"con_r": 76, "con_l": 80, "pwr_r": 99, "pwr_l": 93, "vision": 80, "disc": 80, "clutch": 86, "fielding": 54, "arm_str": 50, "arm_acc": 51, "speed": 24, "stealing": 37, "br_agg": 18, "dur": 80, "bunt": 35, "drag": 30},
    "Pete Crow-Armstrong":    {"con_r": 73, "con_l": 45, "pwr_r": 78, "pwr_l": 60, "vision": 59, "disc": 39, "clutch": 69, "fielding": 99, "arm_str": 97, "arm_acc": 90, "speed": 93, "stealing": 83, "br_agg": 84, "dur": 92, "bunt": 82, "drag": 80},
    "Bobby Witt Jr.":         {"con_r": 88, "con_l": 96, "pwr_r": 71, "pwr_l": 51, "vision": 78, "disc": 52, "clutch": 99, "fielding": 99, "arm_str": 75, "arm_acc": 82, "speed": 99, "stealing": 82, "br_agg": 81, "dur": 98, "bunt": 35, "drag": 25},
    "Xander Bogaerts":        {"con_r": 75, "con_l": 82, "pwr_r": 53, "pwr_l": 47, "vision": 78, "disc": 58, "clutch": 44, "fielding": 85, "arm_str": 55, "arm_acc": 73, "speed": 59, "stealing": 65, "br_agg": 63, "dur": 87, "bunt": 38, "drag": 25},
    "Matt Shaw":              {"con_r": 49, "con_l": 65, "pwr_r": 49, "pwr_l": 73, "vision": 65, "disc": 63, "clutch": 25, "fielding": 62, "arm_str": 55, "arm_acc": 75, "speed": 83, "stealing": 56, "br_agg": 71, "dur": 91, "bunt": 35, "drag": 44},
    "Hyeseong Kim":           {"con_r": 72, "con_l": 68, "pwr_r": 39, "pwr_l": 40, "vision": 45, "disc": 35, "clutch": 76, "fielding": 79, "arm_str": 64, "arm_acc": 66, "speed": 78, "stealing": 70, "br_agg": 73, "dur": 88, "bunt": 56, "drag": 25},
    "Adley Rutschman":        {"con_r": 60, "con_l": 91, "pwr_r": 58, "pwr_l": 59, "vision": 81, "disc": 70, "clutch": 63, "fielding": 74, "arm_str": 94, "arm_acc": 64, "speed": 45, "stealing": 3, "br_agg": 2, "dur": 86, "bunt": 35, "drag": 25},
    "Trea Turner":            {"con_r": 61, "con_l": 84, "pwr_r": 81, "pwr_l": 58, "vision": 63, "disc": 73, "clutch": 47, "fielding": 76, "arm_str": 90, "arm_acc": 57, "speed": 83, "stealing": 99, "br_agg": 75, "dur": 90, "bunt": 35, "drag": 25},
    "Elly De La Cruz":        {"con_r": 58, "con_l": 78, "pwr_r": 55, "pwr_l": 70, "vision": 53, "disc": 46, "clutch": 70, "fielding": 72, "arm_str": 80, "arm_acc": 92, "speed": 85, "stealing": 99, "br_agg": 99, "dur": 99, "bunt": 40, "drag": 36},
    "Esteury Ruiz":           {"con_r": 52, "con_l": 56, "pwr_r": 25, "pwr_l": 52, "vision": 34, "disc": 42, "clutch": 61, "fielding": 65, "arm_str": 65, "arm_acc": 42, "speed": 70, "stealing": 90, "br_agg": 99, "dur": 81, "bunt": 64, "drag": 25},
    "Aaron Judge":            {"con_r": 90, "con_l": 92, "pwr_r": 99, "pwr_l": 99, "vision": 42, "disc": 99, "clutch": 91, "fielding": 61, "arm_str": 80, "arm_acc": 78, "speed": 50, "stealing": 36, "br_agg": 51, "dur": 97, "bunt": 35, "drag": 25},
    "Dillon Dingler":         {"con_r": 54, "con_l": 65, "pwr_r": 86, "pwr_l": 46, "vision": 61, "disc": 58, "clutch": 38, "fielding": 37, "arm_str": 85, "arm_acc": 99, "speed": 59, "stealing": 5, "br_agg": 6, "dur": 84, "bunt": 35, "drag": 25},
    "Steward Berroa":         {"con_r": 46, "con_l": 50, "pwr_r": 33, "pwr_l": 38, "vision": 38, "disc": 37, "clutch": 39, "fielding": 72, "arm_str": 72, "arm_acc": 85, "speed": 75, "stealing": 80, "br_agg": 80, "dur": 82, "bunt": 35, "drag": 25},
    "Steven Kwan":            {"con_r": 78, "con_l": 81, "pwr_r": 51, "pwr_l": 39, "vision": 99, "disc": 64, "clutch": 93, "fielding": 80, "arm_str": 72, "arm_acc": 99, "speed": 54, "stealing": 47, "br_agg": 61, "dur": 92, "bunt": 49, "drag": 85},
    "George Valera":          {"con_r": 55, "con_l": 41, "pwr_r": 60, "pwr_l": 38, "vision": 40, "disc": 72, "clutch": 47, "fielding": 63, "arm_str": 60, "arm_acc": 54, "speed": 77, "stealing": 46, "br_agg": 26, "dur": 73, "bunt": 49, "drag": 47},
}
names = list(show.keys())


def fit(x, y):
    x, y = np.array(x, float), np.array(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return {"r": 0, "m": 0, "b": 0, "rmse": 99, "preds": np.zeros(len(x))}
    r = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = lstsq(A, y, rcond=None)
    preds = c[0] * x + c[1]
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    return {"r": round(r, 4), "m": round(c[0], 2), "b": round(c[1], 1), "rmse": round(rmse, 1), "preds": preds}


def best_blend(vals_2025, vals_career, target):
    """Find optimal blend weight between 2025 and career."""
    best_w, best_rmse, best_result, best_vals = None, 99, None, None
    for w in np.arange(0, 1.05, 0.05):
        blended = [w * vals_2025[i] + (1 - w) * vals_career[i] for i in range(len(names))]
        r = fit(blended, target)
        if r["rmse"] < best_rmse:
            best_w, best_rmse, best_result, best_vals = round(w, 2), r["rmse"], r, blended
    return best_w, best_result, best_vals


def print_detail(label, x_vals, y_vals, r, fmt=".3f"):
    print(f"\n  {label}")
    print(f"  r={r['r']:.3f}  RMSE={r['rmse']:.1f}  Formula: {r['m']}x + {r['b']}")
    print(f"  {'Player':<25} {'Stat':>7} {'Show':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 52)
    for i, n in enumerate(names):
        pred = r["m"] * x_vals[i] + r["b"]
        err = pred - y_vals[i]
        flag = " ***" if abs(err) > 10 else ""
        print(f"  {n:<25} {x_vals[i]:>7{fmt}} {y_vals[i]:>5} {pred:>5.0f} {err:>+5.0f}{flag}")


# ================================================================
print("=" * 75)
print("  COMPREHENSIVE ATTRIBUTE MAPPING - CORRECTED DATA")
print("=" * 75)

results = {}

# --- VISION (already A+, just confirm) ---
k_pct = [stats[n]["K_pct"] for n in names]
vision = [show[n]["vision"] for n in names]
r_vis = fit(k_pct, vision)
results["Vision"] = ("K%", r_vis, k_pct, ".1f")
print_detail("VISION <- K%", k_pct, vision, r_vis, ".1f")

# --- SPEED ---
sprint = [stats[n]["sprint_speed"] for n in names]
speed = [show[n]["speed"] for n in names]
r_spd = fit(sprint, speed)
results["Speed"] = ("Sprint Speed", r_spd, sprint, ".1f")
print_detail("SPEED <- Sprint Speed", sprint, speed, r_spd, ".1f")

# --- DISCIPLINE ---
bb_pct = [stats[n]["BB_pct"] for n in names]
disc = [show[n]["disc"] for n in names]
r_disc = fit(bb_pct, disc)
results["Discipline"] = ("BB%", r_disc, bb_pct, ".1f")
print_detail("DISCIPLINE <- BB%", bb_pct, disc, r_disc, ".1f")

# --- CONTACT R (blend BA vs RHP + career BA) ---
con_r = [show[n]["con_r"] for n in names]
ba_r_2025 = [splits[n]["vs_RHP"]["BA"] for n in names]
ba_career = [career_avg[n]["BA"] for n in names]
w_cr, r_cr, vals_cr = best_blend(ba_r_2025, ba_career, con_r)
results["Contact R"] = (f"BA_vR blend ({w_cr:.0%}/{1-w_cr:.0%})", r_cr, vals_cr, ".3f")
print_detail(f"CONTACT R <- {w_cr:.0%} BA_vR + {1-w_cr:.0%} career BA", vals_cr, con_r, r_cr)

# --- CONTACT L (blend OBP vs LHP + career OBP) ---
con_l = [show[n]["con_l"] for n in names]
obp_l_2025 = [splits[n]["vs_LHP"]["OBP"] for n in names]
obp_career = [career_avg[n]["OBP"] for n in names]
w_cl, r_cl, vals_cl = best_blend(obp_l_2025, obp_career, con_l)
results["Contact L"] = (f"OBP blend ({w_cl:.0%}/{1-w_cl:.0%})", r_cl, vals_cl, ".3f")
print_detail(f"CONTACT L <- {w_cl:.0%} OBP_vL + {1-w_cl:.0%} career OBP", vals_cl, con_l, r_cl)

# --- POWER R (blend 2025 ISO + career ISO) ---
pwr_r = [show[n]["pwr_r"] for n in names]
iso_2025 = [stats[n]["ISO"] for n in names]
iso_career = [career_avg[n]["ISO"] for n in names]
w_pr, r_pr, vals_pr = best_blend(iso_2025, iso_career, pwr_r)
results["Power R"] = (f"ISO blend ({w_pr:.0%}/{1-w_pr:.0%})", r_pr, vals_pr, ".3f")
print_detail(f"POWER R <- {w_pr:.0%} 2025 ISO + {1-w_pr:.0%} career ISO", vals_pr, pwr_r, r_pr)

# --- POWER L (same blend) ---
pwr_l = [show[n]["pwr_l"] for n in names]
w_pl, r_pl, vals_pl = best_blend(iso_2025, iso_career, pwr_l)
results["Power L"] = (f"ISO blend ({w_pl:.0%}/{1-w_pl:.0%})", r_pl, vals_pl, ".3f")
print_detail(f"POWER L <- {w_pl:.0%} 2025 ISO + {1-w_pl:.0%} career ISO", vals_pl, pwr_l, r_pl)

# --- FIELDING (recency-weighted OAA) ---
fld = [show[n]["fielding"] for n in names]
weights_yr = {"2022": 0.1, "2023": 0.15, "2024": 0.3, "2025": 0.45}
oaa_weighted = []
for n in names:
    if n in career_fld:
        tw, to = 0, 0
        for yk, data in career_fld[n].items():
            oaa = data.get("OAA")
            if oaa is not None and yk in weights_yr:
                w = weights_yr[yk]
                to += oaa * w
                tw += w
        oaa_weighted.append(to / tw if tw > 0 else 0)
    else:
        oaa_weighted.append(0)

r_fld = fit(oaa_weighted, fld)
results["Fielding"] = ("Recency-weighted OAA", r_fld, oaa_weighted, ".1f")
print_detail("FIELDING <- Recency-weighted OAA", oaa_weighted, fld, r_fld, ".1f")

# --- STEALING ---
stealing = [show[n]["stealing"] for n in names]
sb_2025 = [float(stats[n]["SB"]) for n in names]
# Also try career SB rate
sb_career_rate = []
for n in names:
    total_sb = career_avg[n].get("total_SB", stats[n]["SB"])
    total_g = career_avg[n].get("total_G", stats[n]["G"])
    sb_career_rate.append(total_sb / max(total_g, 1) * 162)  # per 162 games

w_stl, r_stl, vals_stl = best_blend(sb_2025, sb_career_rate, stealing)
results["Stealing"] = (f"SB blend ({w_stl:.0%}/{1-w_stl:.0%})", r_stl, vals_stl, ".1f")
print_detail(f"STEALING <- {w_stl:.0%} 2025 SB + {1-w_stl:.0%} career SB/162", vals_stl, stealing, r_stl, ".1f")

# --- DURABILITY ---
dur = [show[n]["dur"] for n in names]
gp_2025 = [float(stats[n]["G"]) for n in names]
gp_career_avg = [career_avg[n].get("total_G", stats[n]["G"]) / len(career_avg[n].get("years", ["2025"])) for n in names]
w_dur, r_dur, vals_dur = best_blend(gp_2025, gp_career_avg, dur)
results["Durability"] = (f"GP blend ({w_dur:.0%}/{1-w_dur:.0%})", r_dur, vals_dur, ".0f")
print_detail(f"DURABILITY <- {w_dur:.0%} 2025 GP + {1-w_dur:.0%} career avg GP", vals_dur, dur, r_dur, ".0f")

# --- BR AGGRESSIVENESS ---
br_agg = [show[n]["br_agg"] for n in names]
# Multi-var: SB + Sprint
X_br = np.column_stack([sb_2025, sprint, np.ones(len(names))])
c_br, _, _, _ = lstsq(X_br, np.array(br_agg, float), rcond=None)
preds_br = X_br @ c_br
rmse_br = np.sqrt(np.mean((np.array(br_agg, float) - preds_br) ** 2))
ss_res = np.sum((np.array(br_agg, float) - preds_br) ** 2)
ss_tot = np.sum((np.array(br_agg, float) - np.mean(br_agg)) ** 2)
r2_br = np.sqrt(max(1 - ss_res / ss_tot, 0))  # pseudo-r
print(f"\n  BR AGGRESSIVENESS <- SB + Sprint Speed")
print(f"  R={r2_br:.3f}  RMSE={rmse_br:.1f}  Formula: {c_br[0]:.2f}*SB + {c_br[1]:.1f}*Sprint + {c_br[2]:.1f}")
print(f"  {'Player':<25} {'SB':>4} {'Sprint':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 55)
for i, n in enumerate(names):
    err = preds_br[i] - br_agg[i]
    flag = " ***" if abs(err) > 10 else ""
    print(f"  {n:<25} {sb_2025[i]:>4.0f} {sprint[i]:>6.1f} {br_agg[i]:>5} {preds_br[i]:>5.0f} {err:>+5.0f}{flag}")

# --- CLUTCH ---
clutch = [show[n]["clutch"] for n in names]
# Test career wRC+ (measure of sustained offensive quality)
# Career BA
ba_car_vals = [career_avg[n]["BA"] for n in names]
ba_25 = [stats[n]["BA"] for n in names]
w_clut2, r_clut2, vals_clut2 = best_blend(ba_25, ba_car_vals, clutch)
r_clut2_detail = fit(vals_clut2, clutch)
print(f"\n  CLUTCH <- BA blend ({w_clut2:.0%}/{1-w_clut2:.0%}): r={r_clut2_detail['r']:.3f}  RMSE={r_clut2_detail['rmse']:.1f}")

# Career wOBA
woba_car = [career_avg[n]["wOBA"] for n in names]
woba_25 = [stats[n]["wOBA"] for n in names]
w_clut3, r_clut3, vals_clut3 = best_blend(woba_25, woba_car, clutch)
r_clut3_detail = fit(vals_clut3, clutch)
print(f"  CLUTCH <- wOBA blend ({w_clut3:.0%}/{1-w_clut3:.0%}): r={r_clut3_detail['r']:.3f}  RMSE={r_clut3_detail['rmse']:.1f}")

# Career OBP
obp_car_vals = [career_avg[n]["OBP"] for n in names]
obp_25 = [stats[n]["OBP"] for n in names]
w_clut4, r_clut4, vals_clut4 = best_blend(obp_25, obp_car_vals, clutch)
r_clut4_detail = fit(vals_clut4, clutch)
print(f"  CLUTCH <- OBP blend ({w_clut4:.0%}/{1-w_clut4:.0%}): r={r_clut4_detail['r']:.3f}  RMSE={r_clut4_detail['rmse']:.1f}")

# Print best clutch detail
best_clutch = max([(r_clut2_detail, vals_clut2, "BA blend"),
                   (r_clut3_detail, vals_clut3, "wOBA blend"),
                   (r_clut4_detail, vals_clut4, "OBP blend")],
                  key=lambda x: abs(x[0]["r"]))
print_detail(f"CLUTCH <- {best_clutch[2]} (best)", best_clutch[1], clutch, best_clutch[0])


# ================================================================
# FINAL SUMMARY
# ================================================================
print("\n" + "=" * 75)
print("  FINAL MAPPING SCORECARD")
print("=" * 75)

all_results = [
    ("Vision",       results["Vision"][0],       results["Vision"][1]),
    ("Speed",        results["Speed"][0],         results["Speed"][1]),
    ("Discipline",   results["Discipline"][0],    results["Discipline"][1]),
    ("Contact R",    results["Contact R"][0],     results["Contact R"][1]),
    ("Fielding",     results["Fielding"][0],      results["Fielding"][1]),
    ("Contact L",    results["Contact L"][0],     results["Contact L"][1]),
    ("Power R",      results["Power R"][0],       results["Power R"][1]),
    ("Power L",      results["Power L"][0],       results["Power L"][1]),
    ("Stealing",     results["Stealing"][0],      results["Stealing"][1]),
    ("Durability",   results["Durability"][0],    results["Durability"][1]),
]

print(f"\n  {'Attribute':<15} {'Stat Input':<35} {'r':>6} {'RMSE':>6}  Grade")
print("  " + "-" * 72)
for attr, stat, r in sorted(all_results, key=lambda x: -abs(x[2]["r"])):
    corr = abs(r["r"])
    grade = "A+" if corr >= 0.95 else "A" if corr >= 0.85 else "B" if corr >= 0.7 else "C" if corr >= 0.5 else "F"
    print(f"  {attr:<15} {stat:<35} {r['r']:>+.3f} {r['rmse']:>5.1f}  {grade}")

print(f"\n  MULTI-VARIABLE:")
print(f"  {'BR Agg':<15} {'SB + Sprint Speed':<35} {r2_br:>+.3f} {rmse_br:>5.1f}  {'A' if r2_br > 0.85 else 'B' if r2_br > 0.7 else 'C'}")

print(f"\n  REPUTATION-BASED (not reliably stat-derivable):")
print(f"  - Batting Clutch (best: {best_clutch[2]}, r={best_clutch[0]['r']:.3f}, RMSE={best_clutch[0]['rmse']:.1f})")
print(f"  - Bunting / Drag Bunt (archetype/scouting)")
print(f"  - Arm Strength / Arm Accuracy (scouting)")
print(f"  - Reaction stats (position templates)")
