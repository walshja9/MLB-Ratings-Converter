"""
Pitcher attribute mapping v2 - 9 pitchers.
Pull real stats and find formulas for each pitching attribute.
"""
import json
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from numpy.linalg import lstsq
from pybaseball import pitching_stats, statcast_pitcher

# ================================================================
# ALL 9 PITCHERS
# ================================================================
pitchers = {
    "Garrett Crochet": {"ovr": 99, "throws": "L", "role": "SP",
        "h9_l": 90, "h9_r": 74, "k9_l": 92, "k9_r": 99, "hr9": 65, "pit_clutch": 80,
        "control": 89, "velocity": 99, "break_": 90, "stamina": 87},
    "Tarik Skubal": {"ovr": 99, "throws": "L", "role": "SP",
        "h9_l": 84, "h9_r": 85, "k9_l": 93, "k9_r": 99, "hr9": 74, "pit_clutch": 94,
        "control": 88, "velocity": 99, "break_": 73, "stamina": 90},
    "Nolan McLean": {"ovr": 82, "throws": "R", "role": "SP",
        "h9_l": 71, "h9_r": 62, "k9_l": 85, "k9_r": 73, "hr9": 70, "pit_clutch": 62,
        "control": 54, "velocity": 98, "break_": 99, "stamina": 77},
    "Jeff Hoffman": {"ovr": 80, "throws": "R", "role": "RP",
        "h9_l": 72, "h9_r": 87, "k9_l": 80, "k9_r": 86, "hr9": 61, "pit_clutch": 62,
        "control": 69, "velocity": 99, "break_": 99, "stamina": 25},
    "Payton Tolle": {"ovr": 69, "throws": "L", "role": "SP",
        "h9_l": 52, "h9_r": 51, "k9_l": 67, "k9_r": 84, "hr9": 40, "pit_clutch": 72,
        "control": 72, "velocity": 87, "break_": 69, "stamina": 62},
    "Ranger Suarez": {"ovr": 88, "throws": "L", "role": "SP",
        "h9_l": 71, "h9_r": 59, "k9_l": 81, "k9_r": 68, "hr9": 74, "pit_clutch": 53,
        "control": 79, "velocity": 67, "break_": 98, "stamina": 85},
    "Cole Ragans": {"ovr": 83, "throws": "L", "role": "SP",
        "h9_l": 53, "h9_r": 83, "k9_l": 65, "k9_r": 88, "hr9": 68, "pit_clutch": 50,
        "control": 63, "velocity": 80, "break_": 99, "stamina": 81},
    "Pablo Lopez": {"ovr": 82, "throws": "R", "role": "SP",
        "h9_l": 50, "h9_r": 75, "k9_l": 57, "k9_r": 70, "hr9": 65, "pit_clutch": 63,
        "control": 80, "velocity": 90, "break_": 77, "stamina": 83},
    "Pete Fairbanks": {"ovr": 81, "throws": "R", "role": "RP",
        "h9_l": 80, "h9_r": 91, "k9_l": 74, "k9_r": 66, "hr9": 78, "pit_clutch": 88,
        "control": 65, "velocity": 90, "break_": 99, "stamina": 25},
    "Shane Smith": {"ovr": 81, "throws": "R", "role": "SP",
        "h9_l": 70, "h9_r": 80, "k9_l": 64, "k9_r": 74, "hr9": 66, "pit_clutch": 63,
        "control": 54, "velocity": 99, "break_": 82, "stamina": 75},
}

names = list(pitchers.keys())
show = pitchers


def fit(x, y):
    x, y = np.array(x, float), np.array(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return {"r": 0, "m": 0, "b": 0, "rmse": 99, "preds": np.zeros(len(x)), "n": len(x)}
    r = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = lstsq(A, y, rcond=None)
    preds = c[0] * x + c[1]
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    return {"r": round(r, 3), "m": round(c[0], 2), "b": round(c[1], 1), "rmse": round(rmse, 1), "preds": preds, "n": len(x)}


def find_pitcher(df, name):
    match = df[df["Name"] == name]
    if match.empty:
        for part in name.split():
            if len(part) > 3:
                match = df[df["Name"].str.contains(part, case=False, na=False)]
                if len(match) >= 1:
                    break
    if len(match) > 1:
        match = match.sort_values("IP", ascending=False).head(1)
    return match.iloc[0] if not match.empty else None


# ================================================================
# PULL STATS
# ================================================================
print("Pulling 2025 FanGraphs pitching stats...")
pitch_df = pitching_stats(2025, qual=0)

stats = {}
for name in names:
    row = find_pitcher(pitch_df, name)
    if row is None:
        print(f"  WARNING: {name} not found")
        continue

    s = {
        "IP": round(float(row.get("IP", 0)), 1),
        "G": int(row.get("G", 0)),
        "GS": int(row.get("GS", 0)),
        "ERA": round(float(row.get("ERA", 0)), 2),
        "FIP": round(float(row.get("FIP", 0)), 2),
        "K_per_9": round(float(row.get("K/9", 0)), 1),
        "BB_per_9": round(float(row.get("BB/9", 0)), 1),
        "HR_per_9": round(float(row.get("HR/9", 0)), 2),
        "H_per_9": round(float(row.get("H/9", 0)), 1),
        "K_pct": round(float(row.get("K%", 0)) * 100, 1),
        "BB_pct": round(float(row.get("BB%", 0)) * 100, 1),
        "WHIP": round(float(row.get("WHIP", 0)), 3),
        "WAR": round(float(row.get("WAR", 0)), 1),
        "LOB_pct": round(float(row.get("LOB%", 0)) * 100, 1) if row.get("LOB%") else None,
    }

    fbv = row.get("FBv")
    s["FB_velo"] = round(float(fbv), 1) if fbv and not (isinstance(fbv, float) and math.isnan(fbv)) else None

    stats[name] = s
    role = pitchers[name]["role"]
    print(f"  {name:<20} {role} {s['IP']:>6.1f}IP  {s['ERA']:.2f}ERA  {s['K_per_9']:.1f}K/9  {s['BB_per_9']:.1f}BB/9  {s['HR_per_9']:.2f}HR/9  FBv={s['FB_velo']}")

# Pull Statcast velo data
print("\nPulling Statcast velo data...")
MLBAM_IDS = {
    "Garrett Crochet": 676979, "Tarik Skubal": 669373, "Nolan McLean": 808281,
    "Jeff Hoffman": 656546, "Payton Tolle": 700165, "Ranger Suarez": 624133,
    "Cole Ragans": 666818, "Pablo Lopez": 641154, "Pete Fairbanks": 664126,
    "Shane Smith": 694297,
}

for name, mlbam_id in MLBAM_IDS.items():
    if name not in stats:
        continue
    try:
        df = statcast_pitcher("2025-03-20", "2025-10-01", mlbam_id)
        if df.empty:
            continue

        # Fastball velo (4-Seam + Sinker)
        fb = df[df["pitch_type"].isin(["FF", "SI"])]
        if not fb.empty and "release_speed" in fb.columns:
            stats[name]["avg_fb_velo"] = round(fb["release_speed"].mean(), 1)
            stats[name]["max_fb_velo"] = round(fb["release_speed"].max(), 1)
            print(f"  {name:<20} Avg={stats[name]['avg_fb_velo']}  Max={stats[name]['max_fb_velo']}")

        # Splits vs LHB and RHB
        for hand, label in [("L", "vs_LHB"), ("R", "vs_RHB")]:
            subset = df[(df["stand"] == hand) & df["events"].notna()]
            if len(subset) < 10:
                continue
            ab_events = ["single", "double", "triple", "home_run", "strikeout",
                         "field_out", "grounded_into_double_play", "force_out",
                         "fielders_choice", "fielders_choice_out", "double_play",
                         "strikeout_double_play", "field_error"]
            at_bats = subset[subset["events"].isin(ab_events)]
            all_pa = subset
            if len(at_bats) == 0:
                continue
            hits = len(at_bats[at_bats["events"].isin(["single", "double", "triple", "home_run"])])
            hrs = len(at_bats[at_bats["events"] == "home_run"])
            ks = len(all_pa[all_pa["events"].str.contains("strikeout", na=False)])
            bbs = len(all_pa[all_pa["events"] == "walk"])
            n_pa = len(all_pa)
            n_ab = len(at_bats)
            stats[name][label] = {
                "PA": n_pa, "BA": round(hits / n_ab, 3) if n_ab else 0,
                "K_pct": round(ks / n_pa * 100, 1) if n_pa else 0,
                "BB_pct": round(bbs / n_pa * 100, 1) if n_pa else 0,
                "HR_pct": round(hrs / n_pa * 100, 1) if n_pa else 0,
            }
    except Exception as e:
        print(f"  {name}: ERROR - {e}")


# ================================================================
# MAPPING ANALYSIS
# ================================================================
print(f"\n{'=' * 75}")
print("  PITCHER ATTRIBUTE MAPPING (10 pitchers)")
print("=" * 75)

valid_names = [n for n in names if n in stats]

# --- VELOCITY: avg FB velo ---
print("\n--- VELOCITY ---")
velo_real = [stats[n].get("avg_fb_velo") or stats[n].get("FB_velo") or 0 for n in valid_names]
velo_show = [show[n]["velocity"] for n in valid_names]
r = fit(velo_real, velo_show)
print(f"  Avg FB Velo -> Velocity: r={r['r']:.3f}  RMSE={r['rmse']:.1f}  ({r['m']}x + {r['b']})")
for i, n in enumerate(valid_names):
    pred = r["m"] * velo_real[i] + r["b"]
    flag = " ***" if abs(pred - velo_show[i]) > 10 else ""
    print(f"    {n:<20} FBv={velo_real[i]:>5.1f}  Show={velo_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-velo_show[i]:>+5.0f}{flag}")

# Also try max velo
max_velo = [stats[n].get("max_fb_velo", 0) or 0 for n in valid_names]
r_max = fit(max_velo, velo_show)
print(f"  Max FB Velo -> Velocity: r={r_max['r']:.3f}  RMSE={r_max['rmse']:.1f}  ({r_max['m']}x + {r_max['b']})")

# --- CONTROL ---
print("\n--- CONTROL ---")
bb_pct = [stats[n]["BB_pct"] for n in valid_names]
control_show = [show[n]["control"] for n in valid_names]
r_ctrl = fit(bb_pct, control_show)
print(f"  BB% -> Control: r={r_ctrl['r']:.3f}  RMSE={r_ctrl['rmse']:.1f}  ({r_ctrl['m']}x + {r_ctrl['b']})")
for i, n in enumerate(valid_names):
    pred = r_ctrl["m"] * bb_pct[i] + r_ctrl["b"]
    flag = " ***" if abs(pred - control_show[i]) > 10 else ""
    print(f"    {n:<20} BB%={bb_pct[i]:>5.1f}  Show={control_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-control_show[i]:>+5.0f}{flag}")

# Also try BB/9
bb9 = [stats[n]["BB_per_9"] for n in valid_names]
r_ctrl9 = fit(bb9, control_show)
print(f"  BB/9 -> Control: r={r_ctrl9['r']:.3f}  RMSE={r_ctrl9['rmse']:.1f}  ({r_ctrl9['m']}x + {r_ctrl9['b']})")

# --- STAMINA ---
print("\n--- STAMINA ---")
ip = [stats[n]["IP"] for n in valid_names]
gs = [stats[n]["GS"] for n in valid_names]
stamina_show = [show[n]["stamina"] for n in valid_names]

r_ip = fit(ip, stamina_show)
print(f"  IP -> Stamina: r={r_ip['r']:.3f}  RMSE={r_ip['rmse']:.1f}")

r_gs = fit(gs, stamina_show)
print(f"  GS -> Stamina: r={r_gs['r']:.3f}  RMSE={r_gs['rmse']:.1f}  ({r_gs['m']}x + {r_gs['b']})")
for i, n in enumerate(valid_names):
    pred = r_gs["m"] * gs[i] + r_gs["b"]
    flag = " ***" if abs(pred - stamina_show[i]) > 10 else ""
    print(f"    {n:<20} GS={gs[i]:>3}  IP={ip[i]:>6.1f}  Show={stamina_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-stamina_show[i]:>+5.0f}{flag}")

# IP per GS (average start length)
ip_per_gs = [stats[n]["IP"] / max(stats[n]["GS"], 1) for n in valid_names]
r_ipgs = fit(ip_per_gs, stamina_show)
print(f"  IP/GS -> Stamina: r={r_ipgs['r']:.3f}  RMSE={r_ipgs['rmse']:.1f}  ({r_ipgs['m']}x + {r_ipgs['b']})")

# --- K/9 ---
print("\n--- K/9 (overall) ---")
k9_real = [stats[n]["K_per_9"] for n in valid_names]
k9_show_avg = [(show[n]["k9_l"] + show[n]["k9_r"]) / 2 for n in valid_names]
r_k9 = fit(k9_real, k9_show_avg)
print(f"  K/9 -> K/9 Show avg: r={r_k9['r']:.3f}  RMSE={r_k9['rmse']:.1f}  ({r_k9['m']}x + {r_k9['b']})")
for i, n in enumerate(valid_names):
    pred = r_k9["m"] * k9_real[i] + r_k9["b"]
    flag = " ***" if abs(pred - k9_show_avg[i]) > 10 else ""
    print(f"    {n:<20} K/9={k9_real[i]:>5.1f}  ShowAvg={k9_show_avg[i]:>5.1f}  Pred={pred:>5.0f}  Err={pred-k9_show_avg[i]:>+5.0f}{flag}")

# K% instead
k_pct = [stats[n]["K_pct"] for n in valid_names]
r_kpct = fit(k_pct, k9_show_avg)
print(f"  K% -> K/9 Show avg: r={r_kpct['r']:.3f}  RMSE={r_kpct['rmse']:.1f}")

# --- H/9 ---
print("\n--- H/9 (overall) ---")
h9_real = [stats[n]["H_per_9"] for n in valid_names]
h9_show_avg = [(show[n]["h9_l"] + show[n]["h9_r"]) / 2 for n in valid_names]
r_h9 = fit(h9_real, h9_show_avg)
print(f"  H/9 -> H/9 Show avg: r={r_h9['r']:.3f}  RMSE={r_h9['rmse']:.1f}  ({r_h9['m']}x + {r_h9['b']})")
for i, n in enumerate(valid_names):
    pred = r_h9["m"] * h9_real[i] + r_h9["b"]
    flag = " ***" if abs(pred - h9_show_avg[i]) > 10 else ""
    print(f"    {n:<20} H/9={h9_real[i]:>5.1f}  ShowAvg={h9_show_avg[i]:>5.1f}  Pred={pred:>5.0f}  Err={pred-h9_show_avg[i]:>+5.0f}{flag}")

# Try WHIP instead
whip = [stats[n]["WHIP"] for n in valid_names]
r_whip = fit(whip, h9_show_avg)
print(f"  WHIP -> H/9 Show avg: r={r_whip['r']:.3f}  RMSE={r_whip['rmse']:.1f}")

# BA against (from H/9 and IP)
ba_against = [stats[n]["H_per_9"] / (stats[n]["H_per_9"] + 27 / stats[n].get("WHIP", 1.2) * 3) if stats[n].get("WHIP") else 0 for n in valid_names]

# --- HR/9 ---
print("\n--- HR/9 ---")
hr9_real = [stats[n]["HR_per_9"] for n in valid_names]
hr9_show = [show[n]["hr9"] for n in valid_names]
r_hr9 = fit(hr9_real, hr9_show)
print(f"  HR/9 -> HR/9 Show: r={r_hr9['r']:.3f}  RMSE={r_hr9['rmse']:.1f}  ({r_hr9['m']}x + {r_hr9['b']})")
for i, n in enumerate(valid_names):
    pred = r_hr9["m"] * hr9_real[i] + r_hr9["b"]
    flag = " ***" if abs(pred - hr9_show[i]) > 10 else ""
    print(f"    {n:<20} HR/9={hr9_real[i]:>5.2f}  Show={hr9_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-hr9_show[i]:>+5.0f}{flag}")

# --- PITCHING CLUTCH ---
print("\n--- PITCHING CLUTCH ---")
pit_clutch = [show[n]["pit_clutch"] for n in valid_names]
# Try LOB%, ERA, FIP
for stat_name, vals in [
    ("ERA", [stats[n]["ERA"] for n in valid_names]),
    ("FIP", [stats[n]["FIP"] for n in valid_names]),
    ("LOB%", [stats[n].get("LOB_pct", 0) or 0 for n in valid_names]),
    ("WAR", [stats[n]["WAR"] for n in valid_names]),
]:
    r_test = fit(vals, pit_clutch)
    print(f"  {stat_name} -> Pit Clutch: r={r_test['r']:.3f}  RMSE={r_test['rmse']:.1f}")

# ================================================================
# FINAL SUMMARY
# ================================================================
print(f"\n{'=' * 75}")
print("  PITCHER MAPPING SCORECARD")
print("=" * 75)

all_results = [
    ("Velocity", "Avg FB Velo", r),
    ("Control", "BB%", r_ctrl),
    ("Control", "BB/9", r_ctrl9),
    ("Stamina", "GS", r_gs),
    ("Stamina", "IP/GS", r_ipgs),
    ("Stamina", "IP", r_ip),
    ("K/9 avg", "K/9", r_k9),
    ("K/9 avg", "K%", r_kpct),
    ("H/9 avg", "H/9", r_h9),
    ("H/9 avg", "WHIP", r_whip),
    ("HR/9", "HR/9", r_hr9),
]

print(f"\n  {'Attribute':<15} {'Stat':<12} {'r':>6} {'RMSE':>6}")
print("  " + "-" * 42)
for attr, stat, res in sorted(all_results, key=lambda x: -abs(x[2]["r"])):
    print(f"  {attr:<15} {stat:<12} {res['r']:>+.3f} {res['rmse']:>5.1f}")
