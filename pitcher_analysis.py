"""
Pitcher attribute reverse engineering.
Same approach as hitters: find correlations between real stats and Show ratings.
"""

import numpy as np
from numpy.linalg import lstsq

# ================================================================
# PITCHER DATA
# ================================================================

pitchers = {
    "Garrett Crochet": {
        "ovr": 99, "team": "BOS", "throws": "L", "role": "SP",
        "pitching_ovr": 87,
        "h9_l": 90, "h9_r": 74, "k9_l": 92, "k9_r": 99,
        "hr9": 65, "pit_clutch": 80, "control": 89,
        "velocity": 99, "break_": 90, "stamina": 87,
        "fielding": 46, "dur": 67,
    },
    "Tarik Skubal": {
        "ovr": 99, "team": "DET", "throws": "L", "role": "SP",
        "pitching_ovr": 88,
        "h9_l": 84, "h9_r": 85, "k9_l": 93, "k9_r": 99,
        "hr9": 74, "pit_clutch": 94, "control": 88,
        "velocity": 99, "break_": 73, "stamina": 90,
        "fielding": 54, "dur": 65,
    },
    "Nolan McLean": {
        "ovr": 82, "team": "NYM", "throws": "R", "role": "SP",
        "pitching_ovr": 75,
        "h9_l": 71, "h9_r": 62, "k9_l": 85, "k9_r": 73,
        "hr9": 70, "pit_clutch": 62, "control": 54,
        "velocity": 98, "break_": 99, "stamina": 77,
        "fielding": 60, "dur": 68,
    },
    "Jeff Hoffman": {
        "ovr": 80, "team": "TOR", "throws": "R", "role": "RP",
        "pitching_ovr": 74,
        "h9_l": 72, "h9_r": 87, "k9_l": 80, "k9_r": 86,
        "hr9": 61, "pit_clutch": 62, "control": 69,
        "velocity": 99, "break_": 99, "stamina": 25,
        "fielding": 44, "dur": 75,
    },
    "Payton Tolle": {
        "ovr": 69, "team": "BOS", "throws": "L", "role": "SP",
        "pitching_ovr": 66,
        "h9_l": 52, "h9_r": 51, "k9_l": 67, "k9_r": 84,
        "hr9": 40, "pit_clutch": 72, "control": 72,
        "velocity": 87, "break_": 69, "stamina": 62,
        "fielding": 58, "dur": 82,
    },
}

names = list(pitchers.keys())


def fit(x, y, label=""):
    x, y = np.array(x, float), np.array(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return {"r": 0, "m": 0, "b": 0, "rmse": 99}
    r = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = lstsq(A, y, rcond=None)
    preds = c[0] * x + c[1]
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    return {"r": round(r, 3), "m": round(c[0], 2), "b": round(c[1], 1), "rmse": round(rmse, 1), "preds": preds}


# ================================================================
# VERIFY CATEGORY FORMULAS
# ================================================================

print("=" * 70)
print("  PITCHER CATEGORY FORMULA VERIFICATION")
print("=" * 70)

for name, p in pitchers.items():
    pitch_attrs = [p["h9_l"], p["h9_r"], p["k9_l"], p["k9_r"], p["hr9"],
                   p["pit_clutch"], p["control"], p["velocity"], p["break_"], p["stamina"]]
    avg = np.mean(pitch_attrs)
    print(f"  {name:<20} Pitching OVR: {p['pitching_ovr']}  Avg: {avg:.1f}  Delta: {p['pitching_ovr'] - avg:+.1f}")


# ================================================================
# TOTAL ATTRIBUTES CHECK
# ================================================================
print(f"\n{'=' * 70}")
print("  TOTAL ATTRIBUTES - PITCHER CHECK")
print("=" * 70)

totals_stated = {
    "Garrett Crochet": 1373,
    "Tarik Skubal": 1445,
    "Nolan McLean": 1559,
    "Jeff Hoffman": 1410,
    "Payton Tolle": None,  # not provided
}

# Crochet full attrs from original data
crochet_all = [90,74,92,99,65,80,89,99,90,87,  # pitching (10)
               46,77,48,43,43,43,43,            # fielding (7)
               0,0,0,0,2,0,0,35,8,             # hitting (9)
               38,8,7,                           # baserunning (3)
               67]                               # durability (1)
print(f"  Crochet: sum={sum(crochet_all)}, stated=1373, diff={1373-sum(crochet_all):+d}")

skubal_all = [84,85,93,99,74,94,88,99,73,90,   # pitching
              54,68,56,50,50,50,50,              # fielding
              0,0,0,0,0,0,0,36,9,               # hitting
              42,22,14,                          # baserunning
              65]                                # durability
print(f"  Skubal:  sum={sum(skubal_all)}, stated=1445, diff={1445-sum(skubal_all):+d}")

mclean_all = [71,62,85,73,70,62,54,98,99,77,   # pitching
              60,52,49,50,50,50,50,              # fielding
              38,40,34,38,26,49,37,30,20,       # hitting
              31,19,17,                          # baserunning
              68]                                # durability
print(f"  McLean:  sum={sum(mclean_all)}, stated=1559, diff={1559-sum(mclean_all):+d}")

hoffman_all = [72,87,80,86,61,62,69,99,99,25,  # pitching
               44,72,45,60,60,60,60,            # fielding
               3,5,0,0,19,5,5,89,35,           # hitting
               25,0,8,                          # baserunning
               75]                              # durability
print(f"  Hoffman: sum={sum(hoffman_all)}, stated=1410, diff={1410-sum(hoffman_all):+d}")


# ================================================================
# ATTRIBUTE PATTERNS
# ================================================================
print(f"\n{'=' * 70}")
print("  PITCHER ATTRIBUTE COMPARISON")
print("=" * 70)

attrs = ["h9_l", "h9_r", "k9_l", "k9_r", "hr9", "pit_clutch",
         "control", "velocity", "break_", "stamina"]

header = f"  {'Attribute':<15}"
for n in names:
    short = n.split()[-1][:8]
    header += f" {short:>8}"
print(header)
print("  " + "-" * (15 + 9 * len(names)))

for attr in attrs:
    line = f"  {attr:<15}"
    for n in names:
        line += f" {pitchers[n][attr]:>8}"
    print(line)

print()
line = f"  {'OVR':<15}"
for n in names:
    line += f" {pitchers[n]['ovr']:>8}"
print(line)

line = f"  {'Pitch OVR':<15}"
for n in names:
    line += f" {pitchers[n]['pitching_ovr']:>8}"
print(line)

line = f"  {'Role':<15}"
for n in names:
    line += f" {pitchers[n]['role']:>8}"
print(line)

line = f"  {'Throws':<15}"
for n in names:
    line += f" {pitchers[n]['throws']:>8}"
print(line)


# ================================================================
# KEY OBSERVATIONS
# ================================================================
print(f"\n{'=' * 70}")
print("  KEY OBSERVATIONS")
print("=" * 70)

# Stamina: SP vs RP
print("\n  STAMINA by role:")
for n in names:
    print(f"    {n:<20} {pitchers[n]['role']}  Stamina={pitchers[n]['stamina']}")

# Velocity: all 4 SPs have 87-99, Hoffman (RP) also 99
print("\n  VELOCITY:")
for n in names:
    print(f"    {n:<20} Velocity={pitchers[n]['velocity']}")

# H/9 split pattern: LHP have higher H/9 vs L (same-side), lower vs R
print("\n  H/9 SPLIT PATTERN (same-side vs opposite):")
for n in names:
    throws = pitchers[n]["throws"]
    if throws == "L":
        same = pitchers[n]["h9_l"]
        opp = pitchers[n]["h9_r"]
    else:
        same = pitchers[n]["h9_r"]
        opp = pitchers[n]["h9_l"]
    print(f"    {n:<20} Throws {throws}  Same-side H/9={same}  Opp H/9={opp}  (same > opp: {same > opp})")

# K/9 split pattern
print("\n  K/9 SPLIT PATTERN (same-side vs opposite):")
for n in names:
    throws = pitchers[n]["throws"]
    if throws == "L":
        same = pitchers[n]["k9_l"]
        opp = pitchers[n]["k9_r"]
    else:
        same = pitchers[n]["k9_r"]
        opp = pitchers[n]["k9_l"]
    print(f"    {n:<20} Throws {throws}  Same-side K/9={same}  Opp K/9={opp}  (opp > same: {opp > same})")
