"""
Pull detailed fielding metrics + multi-year career data for blending.
"""
import json
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from pybaseball import batting_stats, fielding_stats, statcast_sprint_speed

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


def find_player(df, name):
    match = df[df["Name"] == name]
    if match.empty:
        for part in name.split():
            if len(part) > 3:
                match = df[df["Name"].str.contains(part, case=False, na=False)]
                if len(match) >= 1:
                    break
    if len(match) > 1:
        match = match.sort_values("G", ascending=False).head(1)
    return match


# ================================================================
# 1. DETAILED FIELDING for 2025
# ================================================================
print("=" * 70)
print("  DETAILED FIELDING METRICS (2025)")
print("=" * 70)

fld_2025 = fielding_stats(2025, qual=0)
fielding_data = {}

for name in TARGET:
    match = find_player(fld_2025, name)
    if match.empty:
        print(f"  WARNING: {name} not found in fielding")
        continue
    row = match.iloc[0]
    fielding_data[name] = {
        "OAA": safe_val(row, "OAA"),
        "DRS": safe_val(row, "DRS"),
        "ARM": safe_val(row, "ARM"),
        "FRM": safe_val(row, "FRM"),  # framing (catchers)
        "DPR": safe_val(row, "DPR"),  # double play runs
        "Def": safe_val(row, "Def"),  # total defensive value
        "Inn": safe_val(row, "Inn"),
        "Pos": safe_val(row, "Pos"),
    }
    d = fielding_data[name]
    print(f"  {name:<25} OAA={str(d['OAA']):>4} ARM={str(d['ARM']):>5} DRS={str(d['DRS']):>4} Def={str(d['Def']):>5} Pos={d['Pos']}")


# ================================================================
# 2. MULTI-YEAR BATTING (2022-2025) for career blending
# ================================================================
print(f"\n{'=' * 70}")
print("  MULTI-YEAR BATTING STATS (2022-2025)")
print("=" * 70)

career_data = {}

for year in [2022, 2023, 2024, 2025]:
    print(f"\n  Pulling {year}...")
    try:
        bat = batting_stats(year, qual=0)
        for name in TARGET:
            match = find_player(bat, name)
            if match.empty:
                continue
            row = match.iloc[0]

            if name not in career_data:
                career_data[name] = {}

            bb_pct = float(row["BB%"]) * 100
            k_pct = float(row["K%"]) * 100

            career_data[name][year] = {
                "G": int(row["G"]),
                "PA": int(row["PA"]),
                "BA": round(float(row["AVG"]), 3),
                "OBP": round(float(row["OBP"]), 3),
                "SLG": round(float(row["SLG"]), 3),
                "ISO": round(float(row["ISO"]), 3),
                "HR": int(row["HR"]),
                "SB": int(row["SB"]),
                "BB_pct": round(bb_pct, 1),
                "K_pct": round(k_pct, 1),
                "wOBA": round(float(row["wOBA"]), 3),
                "wRC_plus": round(float(row["wRC+"]), 0),
                "WAR": round(float(row["WAR"]), 1),
                "Clutch": round(float(row.get("Clutch", 0)), 2),
            }
            print(f"    {name:<25} {year}: .{str(career_data[name][year]['BA'])[2:]:<4} {career_data[name][year]['HR']:>2}HR  {career_data[name][year]['PA']:>3}PA")
    except Exception as e:
        print(f"    ERROR pulling {year}: {e}")


# ================================================================
# 3. MULTI-YEAR SPLITS (statcast) - too slow per-player
#    Instead, compute weighted career averages from season totals
# ================================================================
print(f"\n{'=' * 70}")
print("  CAREER WEIGHTED AVERAGES (PA-weighted, 2022-2025)")
print("=" * 70)

career_avg = {}
for name in TARGET:
    if name not in career_data:
        continue

    total_pa = 0
    weighted = {"BA": 0, "OBP": 0, "SLG": 0, "ISO": 0, "BB_pct": 0, "K_pct": 0, "wOBA": 0}
    total_hr = 0
    total_sb = 0
    total_g = 0

    for year, d in career_data[name].items():
        pa = d["PA"]
        if pa < 10:
            continue
        total_pa += pa
        total_hr += d["HR"]
        total_sb += d["SB"]
        total_g += d["G"]
        for stat in weighted:
            weighted[stat] += d[stat] * pa

    if total_pa == 0:
        continue

    career_avg[name] = {stat: round(v / total_pa, 3) for stat, v in weighted.items()}
    career_avg[name]["total_PA"] = total_pa
    career_avg[name]["total_HR"] = total_hr
    career_avg[name]["total_SB"] = total_sb
    career_avg[name]["total_G"] = total_g
    career_avg[name]["HR_rate"] = round(total_hr / total_pa * 100, 2)
    career_avg[name]["years"] = list(career_data[name].keys())

    c = career_avg[name]
    print(f"  {name:<25} .{str(c['BA'])[2:]:<4} .{str(c['ISO'])[2:]:<4} BB%={c['BB_pct']:>5.1f} K%={c['K_pct']:>5.1f}  ({total_pa} PA over {len(c['years'])} yrs)")


# ================================================================
# 4. MULTI-YEAR FIELDING
# ================================================================
print(f"\n{'=' * 70}")
print("  MULTI-YEAR FIELDING (2022-2025)")
print("=" * 70)

career_fielding = {}
for year in [2022, 2023, 2024, 2025]:
    try:
        fld = fielding_stats(year, qual=0)
        for name in TARGET:
            match = find_player(fld, name)
            if match.empty:
                continue
            row = match.iloc[0]
            if name not in career_fielding:
                career_fielding[name] = {}
            career_fielding[name][year] = {
                "OAA": safe_val(row, "OAA"),
                "DRS": safe_val(row, "DRS"),
                "ARM": safe_val(row, "ARM"),
                "Def": safe_val(row, "Def"),
                "Inn": safe_val(row, "Inn"),
            }
    except Exception as e:
        print(f"  ERROR {year}: {e}")

for name in TARGET:
    if name not in career_fielding:
        print(f"  {name}: no fielding data")
        continue
    years = sorted(career_fielding[name].keys())
    oaa_vals = [career_fielding[name][y]["OAA"] for y in years if career_fielding[name][y]["OAA"] is not None]
    total_oaa = sum(oaa_vals) if oaa_vals else 0
    avg_oaa = total_oaa / len(oaa_vals) if oaa_vals else 0
    oaa_str = ", ".join(f"{y}:{career_fielding[name][y]['OAA']}" for y in years)
    print(f"  {name:<25} OAA by year: {oaa_str}  Avg: {avg_oaa:.1f}")


# ================================================================
# SAVE ALL DATA
# ================================================================
output = {
    "fielding_2025": fielding_data,
    "career_batting": career_data,
    "career_avg": career_avg,
    "career_fielding": career_fielding,
}

with open("career_data.json", "w") as f:
    json.dump(output, f, indent=2, cls=NumpyEncoder)
print(f"\nSaved all career data to career_data.json")
