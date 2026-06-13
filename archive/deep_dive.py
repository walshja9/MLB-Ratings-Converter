"""Deep dive on weak mappings: Contact L, Power, Fielding, Clutch, BR Agg"""
import json, numpy as np
from numpy.linalg import lstsq

with open("player_2025_stats_v2.json") as f:
    stats = json.load(f)
with open("player_2025_splits.json") as f:
    splits = json.load(f)

show = {
    "Juan Soto":              {"con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88, "clutch": 83, "fielding": 53, "stealing": 77, "br_agg": 77, "bunt": 38, "drag": 56},
    "Byron Buxton":           {"con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84, "clutch": 78, "fielding": 83, "stealing": 75, "br_agg": 61, "bunt": 35, "drag": 25},
    "Vladimir Guerrero Jr.":  {"con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73, "clutch": 92, "fielding": 55, "stealing": 16, "br_agg": 26, "bunt": 35, "drag": 25},
    "Yordan Alvarez":         {"con_r": 80, "con_l": 99, "pwr_r": 93, "pwr_l": 80, "clutch": 99, "fielding": 50, "stealing": 18, "br_agg": 16, "bunt": 35, "drag": 30},
    "Pete Crow-Armstrong":    {"con_r": 73, "con_l": 45, "pwr_r": 78, "pwr_l": 60, "clutch": 69, "fielding": 99, "stealing": 83, "br_agg": 84, "bunt": 82, "drag": 80},
    "Bobby Witt Jr.":         {"con_r": 88, "con_l": 96, "pwr_r": 71, "pwr_l": 51, "clutch": 99, "fielding": 99, "stealing": 82, "br_agg": 81, "bunt": 35, "drag": 25},
    "Xander Bogaerts":        {"con_r": 75, "con_l": 82, "pwr_r": 53, "pwr_l": 47, "clutch": 44, "fielding": 85, "stealing": 65, "br_agg": 63, "bunt": 38, "drag": 25},
    "Matt Shaw":              {"con_r": 49, "con_l": 65, "pwr_r": 49, "pwr_l": 73, "clutch": 25, "fielding": 62, "stealing": 56, "br_agg": 71, "bunt": 35, "drag": 44},
    "Hyeseong Kim":           {"con_r": 72, "con_l": 68, "pwr_r": 39, "pwr_l": 40, "clutch": 76, "fielding": 79, "stealing": 70, "br_agg": 73, "bunt": 56, "drag": 25},
    "Adley Rutschman":        {"con_r": 60, "con_l": 91, "pwr_r": 58, "pwr_l": 59, "clutch": 63, "fielding": 74, "stealing": 3, "br_agg": 2, "bunt": 35, "drag": 25},
}
names = list(show.keys())

bats = {"Juan Soto": "L", "Byron Buxton": "R", "Vladimir Guerrero Jr.": "R",
    "Yordan Alvarez": "L", "Pete Crow-Armstrong": "L", "Bobby Witt Jr.": "R",
    "Xander Bogaerts": "R", "Matt Shaw": "R", "Hyeseong Kim": "L", "Adley Rutschman": "S"}

positions = {"Juan Soto": "Corner OF", "Byron Buxton": "CF", "Vladimir Guerrero Jr.": "1B",
    "Yordan Alvarez": "DH/LF", "Pete Crow-Armstrong": "CF",
    "Bobby Witt Jr.": "SS", "Xander Bogaerts": "SS", "Matt Shaw": "3B",
    "Hyeseong Kim": "2B", "Adley Rutschman": "C"}


def fit(x, y):
    x, y = np.array(x, float), np.array(y, float)
    corr = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = lstsq(A, y, rcond=None)
    preds = c[0]*x + c[1]
    rmse = np.sqrt(np.mean((y-preds)**2))
    return corr, c[0], c[1], rmse, preds


# ================================================================
# CONTACT L
# ================================================================
print("=" * 75)
print("  HANDEDNESS vs CONTACT SPLIT PATTERN")
print("=" * 75)
header = f"  {'Player':<25} {'Bats':>4} {'ConR':>5} {'ConL':>5} {'Diff':>5}  {'BA_vR':>6} {'BA_vL':>6}"
print(header)
print("  " + "-" * 60)
for n in names:
    diff = show[n]["con_l"] - show[n]["con_r"]
    print(f"  {n:<25} {bats[n]:>4} {show[n]['con_r']:>5} {show[n]['con_l']:>5} {diff:>+5}  {splits[n]['vs_RHP']['BA']:.3f} {splits[n]['vs_LHP']['BA']:.3f}")

print(f"\n  KEY: L-batters tend to have ConL < ConR (weak vs same-hand)")
print(f"       R-batters tend to have ConL > ConR (strong vs opposite)")

# Test multiple approaches
con_l = [show[n]["con_l"] for n in names]
approaches = {
    "BA vs LHP": [splits[n]["vs_LHP"]["BA"] for n in names],
    "OBP vs LHP": [splits[n]["vs_LHP"]["OBP"] for n in names],
    "Overall BA": [stats[n]["BA"] for n in names],
    "wOBA": [stats[n]["wOBA"] for n in names],
}

print(f"\n  Contact L correlation test:")
for label, vals in approaches.items():
    r, _, _, rmse, _ = fit(vals, con_l)
    print(f"    {label:<15} r={r:>+.3f}  RMSE={rmse:.1f}")

# Best: OBP vs LHP
obp_l = approaches["OBP vs LHP"]
r, m, b, rmse, preds = fit(obp_l, con_l)
print(f"\n  Best single-stat: OBP vs LHP")
print(f"  Formula: Contact_L = {m:.1f} * OBP_vs_LHP + {b:.1f}")
print(f"  r={r:.3f}  RMSE={rmse:.1f}")
print(f"\n  {'Player':<25} {'OBP_vL':>6} {'PA':>4} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 52)
for i, n in enumerate(names):
    pa = splits[n]["vs_LHP"]["PA"]
    print(f"  {n:<25} {obp_l[i]:.3f} {pa:>4} {con_l[i]:>5} {preds[i]:>5.0f} {preds[i]-con_l[i]:>+5.0f}")


# ================================================================
# POWER - exclude Yordan (injury outlier), test approaches
# ================================================================
print("\n" + "=" * 75)
print("  POWER R - EXCLUDING YORDAN (48 GP injury year)")
print("=" * 75)

pwr_r = [show[n]["pwr_r"] for n in names]
pwr_l = [show[n]["pwr_l"] for n in names]

# ISO vs RHP excluding Yordan
names_no_y = [n for n in names if n != "Yordan Alvarez"]
iso_r_ny = [splits[n]["vs_RHP"]["ISO"] for n in names_no_y]
pwr_r_ny = [show[n]["pwr_r"] for n in names_no_y]
r, m, b, rmse, preds = fit(iso_r_ny, pwr_r_ny)
print(f"  ISO vs RHP (excl Yordan): r={r:.3f}  RMSE={rmse:.1f}")
print(f"  Formula: Power_R = {m:.1f} * ISO_vs_RHP + {b:.1f}")
print(f"\n  {'Player':<25} {'ISO_vR':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 50)
for i, n in enumerate(names_no_y):
    print(f"  {n:<25} {iso_r_ny[i]:.3f} {pwr_r_ny[i]:>5} {preds[i]:>5.0f} {preds[i]-pwr_r_ny[i]:>+5.0f}")
# Show Yordan prediction with this formula
yordan_iso_r = splits["Yordan Alvarez"]["vs_RHP"]["ISO"]
yordan_pred = m * yordan_iso_r + b
print(f"  {'Yordan Alvarez (excl)':<25} {yordan_iso_r:.3f} {93:>5} {yordan_pred:>5.0f} {yordan_pred-93:>+5.0f}  <-- needs career blend")

# ISO vs LHP excluding tiny samples
iso_l_ny = [splits[n]["vs_LHP"]["ISO"] for n in names_no_y]
pwr_l_ny = [show[n]["pwr_l"] for n in names_no_y]
# Also exclude Kim (21 PA vs LHP)
names_no_yk = [n for n in names if n not in ("Yordan Alvarez", "Hyeseong Kim")]
iso_l_nyk = [splits[n]["vs_LHP"]["ISO"] for n in names_no_yk]
pwr_l_nyk = [show[n]["pwr_l"] for n in names_no_yk]
r2, m2, b2, rmse2, preds2 = fit(iso_l_nyk, pwr_l_nyk)
print(f"\n  ISO vs LHP (excl Yordan+Kim): r={r2:.3f}  RMSE={rmse2:.1f}")
print(f"  Formula: Power_L = {m2:.1f} * ISO_vs_LHP + {b2:.1f}")
print(f"\n  {'Player':<25} {'ISO_vL':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 50)
for i, n in enumerate(names_no_yk):
    print(f"  {n:<25} {iso_l_nyk[i]:.3f} {pwr_l_nyk[i]:>5} {preds2[i]:>5.0f} {preds2[i]-pwr_l_nyk[i]:>+5.0f}")


# ================================================================
# FIELDING
# ================================================================
print("\n" + "=" * 75)
print("  FIELDING - POSITION + METRICS ANALYSIS")
print("=" * 75)

fld = [show[n]["fielding"] for n in names]
drs = [stats[n].get("DRS") or 0 for n in names]
oaa = [stats[n].get("OAA") or 0 for n in names]

for stat_name, vals in [("DRS", drs), ("OAA", oaa)]:
    r, _, _, rmse, _ = fit(vals, fld)
    print(f"  {stat_name} -> Fielding: r={r:.3f}  RMSE={rmse:.1f}")

print(f"\n  {'Player':<25} {'Pos':<12} {'Fld':>4} {'DRS':>4} {'OAA':>4}")
print("  " + "-" * 52)
for n in names:
    print(f"  {n:<25} {positions[n]:<12} {show[n]['fielding']:>4} {stats[n].get('DRS',0) or 0:>+4} {stats[n].get('OAA',0) or 0:>4}")

print("\n  CONCLUSION: Fielding rating is NOT driven by single-year DRS/OAA.")
print("  It correlates with position archetype + career scouting data.")
print("  For the tool: use position-based baselines + multi-year defensive metrics.")


# ================================================================
# CLUTCH
# ================================================================
print("\n" + "=" * 75)
print("  CLUTCH - TESTING ALL AVAILABLE STATS")
print("=" * 75)

clutch = [show[n]["clutch"] for n in names]
test_stats = {
    "wOBA": [stats[n]["wOBA"] for n in names],
    "wRC+": [stats[n]["wRC_plus"] for n in names],
    "OPS": [stats[n]["OBP"] + stats[n]["SLG"] for n in names],
    "WAR": [stats[n]["WAR"] for n in names],
    "FG Clutch": [stats[n]["Clutch"] for n in names],
    "BA": [stats[n]["BA"] for n in names],
    "ISO": [stats[n]["ISO"] for n in names],
}

for label, vals in sorted(test_stats.items(), key=lambda x: -abs(fit(x[1], clutch)[0])):
    r, _, _, rmse, _ = fit(vals, clutch)
    print(f"  {label:<12} -> Clutch: r={r:>+.3f}  RMSE={rmse:.1f}")

# Best: wOBA
woba = test_stats["wOBA"]
r, m, b, rmse, preds = fit(woba, clutch)
print(f"\n  Best: wOBA -> Clutch = {m:.1f}*wOBA + {b:.1f}  (r={r:.3f})")
print(f"\n  {'Player':<25} {'wOBA':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 50)
for i, n in enumerate(names):
    print(f"  {n:<25} {woba[i]:.3f} {clutch[i]:>5} {preds[i]:>5.0f} {preds[i]-clutch[i]:>+5.0f}")


# ================================================================
# BR AGGRESSIVENESS
# ================================================================
print("\n" + "=" * 75)
print("  BASERUNNING AGGRESSIVENESS")
print("=" * 75)

br_agg = [show[n]["br_agg"] for n in names]
sprint = [stats[n]["sprint_speed"] for n in names]
sb = [stats[n]["SB"] for n in names]

r_spd, _, _, rmse_spd, _ = fit(sprint, br_agg)
r_sb, m_sb, b_sb, rmse_sb, preds_sb = fit(sb, br_agg)
print(f"  Sprint Speed -> BR Agg: r={r_spd:.3f}  RMSE={rmse_spd:.1f}")
print(f"  SB count -> BR Agg:     r={r_sb:.3f}  RMSE={rmse_sb:.1f}")

# Multi: SB + Sprint
X = np.column_stack([np.array(sb), np.array(sprint), np.ones(len(names))])
c, _, _, _ = lstsq(X, np.array(br_agg, float), rcond=None)
preds_m = X @ c
rmse_m = np.sqrt(np.mean((np.array(br_agg, float) - preds_m) ** 2))
print(f"  SB + Sprint combined:   RMSE={rmse_m:.1f}")
print(f"  Formula: {c[0]:.2f}*SB + {c[1]:.1f}*Sprint + {c[2]:.1f}")
print(f"\n  {'Player':<25} {'SB':>4} {'Sprint':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
print("  " + "-" * 55)
for i, n in enumerate(names):
    print(f"  {n:<25} {sb[i]:>4} {sprint[i]:>6.1f} {br_agg[i]:>5} {preds_m[i]:>5.0f} {preds_m[i]-br_agg[i]:>+5.0f}")


# ================================================================
# FINAL SUMMARY
# ================================================================
print("\n" + "=" * 75)
print("  COMPLETE MAPPING STATUS")
print("=" * 75)

solved = [
    ("Vision",       "K%",             -0.994, 1.5,  "-2.55*K% + 121.3"),
    ("Speed",        "Sprint Speed",    0.989, 3.6,  "15.01*Sprint - 353.5"),
    ("Discipline",   "BB%",             0.982, 3.7,  "4.86*BB% + 17.2"),
    ("Contact R",    "BA vs RHP",       0.879, 5.9,  "430.4*BA_vR - 35.8"),
    ("Stealing",     "SB count",        0.896, 12.8, "1.88*SB + 18.5"),
    ("Durability",   "Games Played",    0.804, 3.6,  "0.13*GP + 74.6"),
]

print(f"\n  SOLVED (usable in tool):")
print(f"  {'Attribute':<15} {'Stat':<18} {'r':>6} {'RMSE':>6}  Formula")
print("  " + "-" * 70)
for attr, stat, r, rmse, formula in solved:
    print(f"  {attr:<15} {stat:<18} {r:>+.3f} {rmse:>5.1f}  {formula}")

print(f"\n  NEEDS WORK:")
print(f"  {'Attribute':<15} {'Issue'}")
print("  " + "-" * 60)
print(f"  {'Contact L':<15} OBP vs LHP is best (r=0.822) but small samples hurt")
print(f"  {'Power R':<15} ISO vs RHP great without Yordan (r=0.955) - needs career blend")
print(f"  {'Power L':<15} ISO vs LHP decent without outliers (r={r2:.3f})")
print(f"  {'Fielding':<15} Not stat-driven - position + scouting based")
print(f"  {'Clutch':<15} Weakly correlates with wOBA - likely reputation-based")
print(f"  {'BR Agg':<15} SB + Sprint combined works (RMSE={rmse_m:.1f})")
print(f"  {'Bunting':<15} Not analyzed yet - likely scouting/archetype based")
