"""
Re-pull career data with STRICT name matching only.
No partial matches - exact Name == target only.
"""
import json
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from pybaseball import batting_stats, fielding_stats

TARGET = [
    "Juan Soto", "Byron Buxton", "Vladimir Guerrero Jr.", "Yordan Alvarez",
    "Pete Crow-Armstrong", "Bobby Witt Jr.", "Xander Bogaerts", "Matt Shaw",
    "Hyeseong Kim", "Adley Rutschman",
]


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if math.isnan(obj) else round(float(obj), 3)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)


def safe_val(row, col):
    v = row.get(col)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


# ================================================================
# STRICT career batting
# ================================================================
career_batting = {}
career_fielding = {}

for year in [2022, 2023, 2024, 2025]:
    print(f"Pulling {year}...")

    bat = batting_stats(year, qual=0)
    fld = fielding_stats(year, qual=0)

    for name in TARGET:
        # STRICT exact match only
        match = bat[bat["Name"] == name]
        if match.empty:
            continue
        if len(match) > 1:
            match = match.sort_values("PA", ascending=False).head(1)

        row = match.iloc[0]
        pa = int(row["PA"])
        if pa < 10:
            continue

        if name not in career_batting:
            career_batting[name] = {}

        career_batting[name][str(year)] = {
            "G": int(row["G"]),
            "PA": pa,
            "BA": round(float(row["AVG"]), 3),
            "OBP": round(float(row["OBP"]), 3),
            "SLG": round(float(row["SLG"]), 3),
            "ISO": round(float(row["ISO"]), 3),
            "HR": int(row["HR"]),
            "SB": int(row["SB"]),
            "CS": int(row.get("CS", 0)),
            "BB_pct": round(float(row["BB%"]) * 100, 1),
            "K_pct": round(float(row["K%"]) * 100, 1),
            "wOBA": round(float(row["wOBA"]), 3),
            "wRC_plus": round(float(row["wRC+"]), 0),
            "WAR": round(float(row["WAR"]), 1),
            "Clutch": round(float(row.get("Clutch", 0)), 2),
        }
        d = career_batting[name][str(year)]
        print(f"  {name:<25} {year}: .{str(d['BA'])[2:]:<4} {d['HR']:>2}HR  {pa:>3}PA  OK")

        # Fielding - strict match
        fld_match = fld[fld["Name"] == name]
        if not fld_match.empty:
            if len(fld_match) > 1:
                fld_match = fld_match.sort_values("G", ascending=False).head(1)
            frow = fld_match.iloc[0]
            if name not in career_fielding:
                career_fielding[name] = {}
            career_fielding[name][str(year)] = {
                "OAA": safe_val(frow, "OAA"),
                "DRS": safe_val(frow, "DRS"),
                "ARM": safe_val(frow, "ARM"),
                "Def": safe_val(frow, "Def"),
                "Inn": safe_val(frow, "Inn"),
                "Pos": safe_val(frow, "Pos"),
            }


# ================================================================
# Compute career averages (PA-weighted)
# ================================================================
print("\n" + "=" * 70)
print("  CORRECTED CAREER AVERAGES")
print("=" * 70)

career_avg = {}
for name in TARGET:
    if name not in career_batting:
        print(f"  {name}: NO DATA")
        continue

    total_pa = 0
    weighted = {"BA": 0, "OBP": 0, "SLG": 0, "ISO": 0, "BB_pct": 0, "K_pct": 0, "wOBA": 0}
    total_hr = 0
    total_sb = 0
    total_g = 0

    for year, d in career_batting[name].items():
        pa = d["PA"]
        total_pa += pa
        total_hr += d["HR"]
        total_sb += d["SB"]
        total_g += d["G"]
        for stat in weighted:
            weighted[stat] += d[stat] * pa

    career_avg[name] = {stat: round(v / total_pa, 3) for stat, v in weighted.items()}
    career_avg[name]["total_PA"] = total_pa
    career_avg[name]["total_HR"] = total_hr
    career_avg[name]["total_SB"] = total_sb
    career_avg[name]["total_G"] = total_g
    career_avg[name]["years"] = sorted(career_batting[name].keys())

    c = career_avg[name]
    yrs = c["years"]
    print(f"  {name:<25} .{str(c['BA'])[2:]:<4} ISO=.{str(c['ISO'])[2:]:<4} "
          f"BB%={c['BB_pct']:>5.1f} K%={c['K_pct']:>5.1f}  "
          f"({total_pa}PA, {len(yrs)} yrs: {','.join(yrs)})")

# ================================================================
# Corrected career fielding
# ================================================================
print(f"\n{'=' * 70}")
print("  CORRECTED CAREER FIELDING (OAA)")
print("=" * 70)

for name in TARGET:
    if name not in career_fielding:
        print(f"  {name:<25} NO FIELDING DATA")
        continue
    years = sorted(career_fielding[name].keys())
    oaa_vals = []
    for y in years:
        oaa = career_fielding[name][y].get("OAA")
        if oaa is not None:
            oaa_vals.append(oaa)
    oaa_parts = ", ".join(f"{y}:{career_fielding[name][y].get('OAA')}" for y in years)
    avg = np.mean(oaa_vals) if oaa_vals else 0
    print(f"  {name:<25} OAA: {oaa_parts}  Avg: {avg:.1f}")


# ================================================================
# Save
# ================================================================
output = {
    "career_batting": career_batting,
    "career_avg": career_avg,
    "career_fielding": career_fielding,
}

with open("career_data_fixed.json", "w") as f:
    json.dump(output, f, indent=2, cls=NumpyEncoder)
print(f"\nSaved corrected career data to career_data_fixed.json")
