"""Pull Chandler Simpson stats and test against our formulas."""
from pybaseball import batting_stats, statcast_sprint_speed, fielding_stats
import warnings
warnings.filterwarnings("ignore")

bat = batting_stats(2025, qual=0)
match = bat[bat["Name"] == "Chandler Simpson"]
if match.empty:
    match = bat[bat["Name"].str.contains("Simpson", case=False, na=False)]
    if not match.empty:
        print("Partial matches found:")
        for _, r in match.iterrows():
            team = r.get("Team", "?")
            print(f"  {r['Name']} ({team}), PA={r['PA']}")

if not match.empty:
    row = match.iloc[0]
    name = row["Name"]
    team = row.get("Team", "?")
    ba = float(row["AVG"])
    obp = float(row["OBP"])
    slg = float(row["SLG"])
    iso = float(row["ISO"])
    hr = int(row["HR"])
    sb = int(row["SB"])
    bb_pct = float(row["BB%"]) * 100
    k_pct = float(row["K%"]) * 100
    g = int(row["G"])
    pa = int(row["PA"])
    woba = float(row["wOBA"])

    print(f"\n{name} ({team})")
    print(f"  G={g}, PA={pa}, BA={ba:.3f}, OBP={obp:.3f}, SLG={slg:.3f}")
    print(f"  ISO={iso:.3f}, HR={hr}, SB={sb}")
    print(f"  BB%={bb_pct:.1f}, K%={k_pct:.1f}")
    print(f"  wOBA={woba:.3f}")
else:
    print("NOT FOUND")
    ba = obp = slg = iso = bb_pct = k_pct = 0
    hr = sb = g = pa = 0

# Sprint speed
sprint_df = statcast_sprint_speed(2025)
smatch = sprint_df[sprint_df["last_name, first_name"].str.contains("Simpson", na=False)]
sprint_speed = None
if not smatch.empty:
    sprint_speed = float(smatch.iloc[0]["sprint_speed"])
    print(f"  Sprint Speed: {sprint_speed}")
else:
    print("  Sprint Speed: NOT FOUND")

# Fielding
fld = fielding_stats(2025, qual=0)
fmatch = fld[fld["Name"] == "Chandler Simpson"]
if fmatch.empty:
    fmatch = fld[fld["Name"].str.contains("Simpson", case=False, na=False)]
oaa = None
if not fmatch.empty:
    frow = fmatch.iloc[0]
    oaa_val = frow.get("OAA")
    oaa = float(oaa_val) if oaa_val is not None else None
    drs = frow.get("DRS")
    print(f"  OAA={oaa}, DRS={drs}")
else:
    print("  Fielding: NOT FOUND")

# ================================================================
# TEST AGAINST OUR FORMULAS
# ================================================================
print("\n" + "=" * 60)
print("  FORMULA PREDICTIONS vs ACTUAL")
print("=" * 60)

show = {
    "con_r": 81, "con_l": 84, "pwr_r": 25, "pwr_l": 25,
    "vision": 93, "disc": 37, "clutch": 80,
    "fielding": 47, "speed": 99, "stealing": 99, "br_agg": 99,
    "dur": 87, "bunt": 70, "drag": 70,
}

formulas = {
    "Vision":     ("K%", k_pct, -2.55, 121.3),
    "Discipline": ("BB%", bb_pct, 4.86, 17.2),
    "Durability": ("GP", g, 0.13, 74.6),  # simple 2025 only
}

if sprint_speed:
    formulas["Speed"] = ("Sprint", sprint_speed, 15.01, -353.5)

show_keys = {
    "Vision": "vision", "Speed": "speed", "Discipline": "disc",
    "Durability": "dur",
}

print(f"\n  {'Attribute':<15} {'Input':>8} {'Actual':>7} {'Predicted':>10} {'Error':>7}")
print("  " + "-" * 50)

for attr, (stat_name, val, m, b) in formulas.items():
    pred = m * val + b
    pred = max(0, min(99, pred))
    actual = show[show_keys[attr]]
    err = pred - actual
    flag = " ***" if abs(err) > 10 else ""
    print(f"  {attr:<15} {val:>8.1f} {actual:>7} {pred:>10.0f} {err:>+7.0f}{flag}")

# Power R: 95% career ISO (but Simpson likely has no career data pre-2025)
# Use 2025 ISO with career formula: 336.17x + 3.9
pred_pwr_r = 336.17 * iso + 3.9
print(f"  {'Power R':<15} {iso:>8.3f} {show['pwr_r']:>7} {max(0,pred_pwr_r):>10.0f} {pred_pwr_r - show['pwr_r']:>+7.0f}")

# Contact R: BA as proxy
pred_con_r = 551.97 * ba + (-69.7)
print(f"  {'Contact R':<15} {ba:>8.3f} {show['con_r']:>7} {max(0,pred_con_r):>10.0f} {pred_con_r - show['con_r']:>+7.0f}")

# Stealing: SB count
pred_stl = 1.88 * sb + 18.5
print(f"  {'Stealing':<15} {sb:>8.0f} {show['stealing']:>7} {pred_stl:>10.0f} {pred_stl - show['stealing']:>+7.0f}")

# BR Agg: SB + Sprint
if sprint_speed:
    pred_br = 1.54 * sb + 4.4 * sprint_speed + (-98.3)
    print(f"  {'BR Agg':<15} {'multi':>8} {show['br_agg']:>7} {pred_br:>10.0f} {pred_br - show['br_agg']:>+7.0f}")
