"""Pull 2025 pitching stats for our 5 pitchers and map to Show attributes."""
import json
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from numpy.linalg import lstsq
from pybaseball import pitching_stats, statcast_pitcher

# Our 5 pitchers
PITCHERS = {
    "Garrett Crochet": {"role": "SP", "throws": "L"},
    "Tarik Skubal":    {"role": "SP", "throws": "L"},
    "Nolan McLean":    {"role": "SP", "throws": "R"},
    "Jeff Hoffman":    {"role": "RP", "throws": "R"},
    "Payton Tolle":    {"role": "SP", "throws": "L"},
}

SHOW_RATINGS = {
    "Garrett Crochet": {"h9_l": 90, "h9_r": 74, "k9_l": 92, "k9_r": 99, "hr9": 65, "pit_clutch": 80, "control": 89, "velocity": 99, "break_": 90, "stamina": 87},
    "Tarik Skubal":    {"h9_l": 84, "h9_r": 85, "k9_l": 93, "k9_r": 99, "hr9": 74, "pit_clutch": 94, "control": 88, "velocity": 99, "break_": 73, "stamina": 90},
    "Nolan McLean":    {"h9_l": 71, "h9_r": 62, "k9_l": 85, "k9_r": 73, "hr9": 70, "pit_clutch": 62, "control": 54, "velocity": 98, "break_": 99, "stamina": 77},
    "Jeff Hoffman":    {"h9_l": 72, "h9_r": 87, "k9_l": 80, "k9_r": 86, "hr9": 61, "pit_clutch": 62, "control": 69, "velocity": 99, "break_": 99, "stamina": 25},
    "Payton Tolle":    {"h9_l": 52, "h9_r": 51, "k9_l": 67, "k9_r": 84, "hr9": 40, "pit_clutch": 72, "control": 72, "velocity": 87, "break_": 69, "stamina": 62},
}

MLBAM_IDS = {
    "Garrett Crochet": 676979,
    "Tarik Skubal": 669373,
    "Nolan McLean": 808281,
    "Jeff Hoffman": 656546,
    "Payton Tolle": 700165,
}


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
    return {"r": round(r, 3), "m": round(c[0], 2), "b": round(c[1], 1), "rmse": round(rmse, 1), "preds": preds}


# ================================================================
# PULL FANGRAPHS PITCHING STATS
# ================================================================
print("Pulling 2025 FanGraphs pitching stats...")
pitch_df = pitching_stats(2025, qual=0)

stats = {}
names = list(PITCHERS.keys())

print(f"\nAvailable pitching columns (sample):")
key_cols = [c for c in pitch_df.columns if any(k in c.lower() for k in
            ["era", "fip", "whip", "k/9", "bb/9", "hr/9", "ip", "h/9",
             "k%", "bb%", "fbv", "velo", "stuff", "lob", "war"])]
print(f"  {key_cols[:30]}")

for name in names:
    row = find_pitcher(pitch_df, name)
    if row is None:
        print(f"  WARNING: {name} not found")
        continue

    s = {
        "W": int(row.get("W", 0)),
        "L": int(row.get("L", 0)),
        "ERA": round(float(row.get("ERA", 0)), 2),
        "FIP": round(float(row.get("FIP", 0)), 2),
        "IP": round(float(row.get("IP", 0)), 1),
        "G": int(row.get("G", 0)),
        "GS": int(row.get("GS", 0)),
        "K_per_9": round(float(row.get("K/9", 0)), 1),
        "BB_per_9": round(float(row.get("BB/9", 0)), 1),
        "HR_per_9": round(float(row.get("HR/9", 0)), 2),
        "H_per_9": round(float(row.get("H/9", 0)), 1),
        "K_pct": round(float(row.get("K%", 0)) * 100, 1),
        "BB_pct": round(float(row.get("BB%", 0)) * 100, 1),
        "WHIP": round(float(row.get("WHIP", 0)), 3),
        "LOB_pct": round(float(row.get("LOB%", 0)) * 100, 1) if row.get("LOB%") else None,
        "WAR": round(float(row.get("WAR", 0)), 1),
    }

    # Try to get velocity
    fbv = row.get("FBv")
    if fbv and not (isinstance(fbv, float) and math.isnan(fbv)):
        s["FB_velo"] = round(float(fbv), 1)
    else:
        s["FB_velo"] = None

    stats[name] = s
    print(f"  {name:<20} {s['IP']:>5.1f}IP  {s['ERA']:.2f}ERA  {s['K_per_9']:.1f}K/9  {s['BB_per_9']:.1f}BB/9  {s['HR_per_9']:.2f}HR/9  FBv={s['FB_velo']}")


# ================================================================
# PULL STATCAST FOR SPLITS AND VELO
# ================================================================
print("\nPulling Statcast data for splits...")

for name, mlbam_id in MLBAM_IDS.items():
    print(f"  {name}...")
    try:
        df = statcast_pitcher("2025-03-20", "2025-10-01", mlbam_id)
        if df.empty:
            continue

        # Fastball velocity (4-Seam, Sinker)
        fb_pitches = df[df["pitch_type"].isin(["FF", "SI"])]
        if not fb_pitches.empty and "release_speed" in fb_pitches.columns:
            avg_velo = fb_pitches["release_speed"].mean()
            max_velo = fb_pitches["release_speed"].max()
            stats[name]["avg_fb_velo"] = round(avg_velo, 1)
            stats[name]["max_fb_velo"] = round(max_velo, 1)
            print(f"    Velo: avg={avg_velo:.1f}, max={max_velo:.1f}")

        # Breaking ball spin/movement
        breaking = df[df["pitch_type"].isin(["SL", "CU", "KC", "SV", "ST"])]
        if not breaking.empty and "pfx_z" in breaking.columns:
            avg_break_z = breaking["pfx_z"].mean()  # vertical movement
            avg_break_x = breaking["pfx_x"].mean()  # horizontal movement
            total_break = np.sqrt(avg_break_z**2 + avg_break_x**2)
            stats[name]["avg_break"] = round(total_break, 2)
            print(f"    Break: total_movement={total_break:.2f}")

        # Splits: vs LHB and vs RHB
        for hand, label in [("L", "vs_LHB"), ("R", "vs_RHB")]:
            subset = df[(df["stand"] == hand) & df["events"].notna()]
            if len(subset) < 10:
                continue

            ab_events = ["single", "double", "triple", "home_run",
                         "strikeout", "field_out", "grounded_into_double_play",
                         "force_out", "fielders_choice", "fielders_choice_out",
                         "double_play", "strikeout_double_play", "field_error"]
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

            ba_against = hits / n_ab if n_ab > 0 else 0
            k_pct = ks / n_pa * 100 if n_pa > 0 else 0
            bb_pct = bbs / n_pa * 100 if n_pa > 0 else 0
            hr_pct = hrs / n_pa * 100 if n_pa > 0 else 0

            stats[name][label] = {
                "PA": n_pa, "BA": round(ba_against, 3),
                "K_pct": round(k_pct, 1), "BB_pct": round(bb_pct, 1),
                "HR_pct": round(hr_pct, 1),
            }
            print(f"    {label}: PA={n_pa}, BA={ba_against:.3f}, K%={k_pct:.1f}, BB%={bb_pct:.1f}")

    except Exception as e:
        print(f"    ERROR: {e}")

# ================================================================
# MAPPING ANALYSIS
# ================================================================
print(f"\n{'=' * 70}")
print("  PITCHING ATTRIBUTE MAPPING ANALYSIS")
print("=" * 70)

show = SHOW_RATINGS

# --- VELOCITY ---
print("\n  VELOCITY:")
fb_velo = [stats[n].get("avg_fb_velo") or stats[n].get("FB_velo") or 0 for n in names]
velo_show = [show[n]["velocity"] for n in names]
r = fit(fb_velo, velo_show)
print(f"  Avg FB Velo -> Velocity: r={r['r']:.3f}  RMSE={r['rmse']:.1f}  ({r['m']}x + {r['b']})")
for i, n in enumerate(names):
    pred = r["m"] * fb_velo[i] + r["b"]
    print(f"    {n:<20} Velo={fb_velo[i]:>5.1f}  Show={velo_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-velo_show[i]:>+5.0f}")

# --- CONTROL (BB/9 or BB%) ---
print("\n  CONTROL:")
bb9 = [stats[n]["BB_per_9"] for n in names]
control_show = [show[n]["control"] for n in names]
r_ctrl = fit(bb9, control_show)
print(f"  BB/9 -> Control: r={r_ctrl['r']:.3f}  RMSE={r_ctrl['rmse']:.1f}  ({r_ctrl['m']}x + {r_ctrl['b']})")

bb_pct = [stats[n]["BB_pct"] for n in names]
r_ctrl2 = fit(bb_pct, control_show)
print(f"  BB% -> Control:  r={r_ctrl2['r']:.3f}  RMSE={r_ctrl2['rmse']:.1f}  ({r_ctrl2['m']}x + {r_ctrl2['b']})")

best_ctrl = r_ctrl if abs(r_ctrl["r"]) > abs(r_ctrl2["r"]) else r_ctrl2
best_ctrl_vals = bb9 if abs(r_ctrl["r"]) > abs(r_ctrl2["r"]) else bb_pct
best_ctrl_label = "BB/9" if abs(r_ctrl["r"]) > abs(r_ctrl2["r"]) else "BB%"
for i, n in enumerate(names):
    pred = best_ctrl["m"] * best_ctrl_vals[i] + best_ctrl["b"]
    print(f"    {n:<20} {best_ctrl_label}={best_ctrl_vals[i]:>5.1f}  Show={control_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-control_show[i]:>+5.0f}")

# --- STAMINA (IP) ---
print("\n  STAMINA:")
ip = [stats[n]["IP"] for n in names]
stamina_show = [show[n]["stamina"] for n in names]
r_stam = fit(ip, stamina_show)
print(f"  IP -> Stamina: r={r_stam['r']:.3f}  RMSE={r_stam['rmse']:.1f}  ({r_stam['m']}x + {r_stam['b']})")
for i, n in enumerate(names):
    pred = r_stam["m"] * ip[i] + r_stam["b"]
    print(f"    {n:<20} IP={ip[i]:>6.1f}  Show={stamina_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-stamina_show[i]:>+5.0f}")

# --- K/9 (overall) ---
print("\n  K/9 (overall avg of L+R splits):")
k9_show_avg = [(show[n]["k9_l"] + show[n]["k9_r"]) / 2 for n in names]
k9_real = [stats[n]["K_per_9"] for n in names]
r_k9 = fit(k9_real, k9_show_avg)
print(f"  K/9 -> K/9 Show avg: r={r_k9['r']:.3f}  RMSE={r_k9['rmse']:.1f}  ({r_k9['m']}x + {r_k9['b']})")
for i, n in enumerate(names):
    pred = r_k9["m"] * k9_real[i] + r_k9["b"]
    show_avg = k9_show_avg[i]
    print(f"    {n:<20} K/9={k9_real[i]:>5.1f}  ShowAvg={show_avg:>5.1f}  Pred={pred:>5.0f}  Err={pred-show_avg:>+5.0f}")

# --- H/9 (overall) ---
print("\n  H/9 (overall avg of L+R splits):")
h9_show_avg = [(show[n]["h9_l"] + show[n]["h9_r"]) / 2 for n in names]
h9_real = [stats[n]["H_per_9"] for n in names]
r_h9 = fit(h9_real, h9_show_avg)
print(f"  H/9 -> H/9 Show avg: r={r_h9['r']:.3f}  RMSE={r_h9['rmse']:.1f}  ({r_h9['m']}x + {r_h9['b']})")
for i, n in enumerate(names):
    pred = r_h9["m"] * h9_real[i] + r_h9["b"]
    show_avg = h9_show_avg[i]
    print(f"    {n:<20} H/9={h9_real[i]:>5.1f}  ShowAvg={show_avg:>5.1f}  Pred={pred:>5.0f}  Err={pred-show_avg:>+5.0f}")

# --- HR/9 ---
print("\n  HR/9:")
hr9_real = [stats[n]["HR_per_9"] for n in names]
hr9_show = [show[n]["hr9"] for n in names]
r_hr9 = fit(hr9_real, hr9_show)
print(f"  HR/9 -> HR/9 Show: r={r_hr9['r']:.3f}  RMSE={r_hr9['rmse']:.1f}  ({r_hr9['m']}x + {r_hr9['b']})")
for i, n in enumerate(names):
    pred = r_hr9["m"] * hr9_real[i] + r_hr9["b"]
    print(f"    {n:<20} HR/9={hr9_real[i]:>5.2f}  Show={hr9_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-hr9_show[i]:>+5.0f}")

# --- BREAK ---
print("\n  BREAK:")
if any(stats[n].get("avg_break") for n in names):
    break_real = [stats[n].get("avg_break", 0) for n in names]
    break_show = [show[n]["break_"] for n in names]
    r_brk = fit(break_real, break_show)
    print(f"  Total movement -> Break: r={r_brk['r']:.3f}  RMSE={r_brk['rmse']:.1f}")
    for i, n in enumerate(names):
        pred = r_brk["m"] * break_real[i] + r_brk["b"]
        print(f"    {n:<20} Break={break_real[i]:>5.2f}  Show={break_show[i]:>3}  Pred={pred:>5.0f}  Err={pred-break_show[i]:>+5.0f}")

# --- SUMMARY ---
print(f"\n{'=' * 70}")
print("  PITCHER MAPPING SUMMARY")
print("=" * 70)
all_results = [
    ("Velocity", "FB Velo", r),
    ("Control", best_ctrl_label, best_ctrl),
    ("Stamina", "IP", r_stam),
    ("K/9 avg", "K/9", r_k9),
    ("H/9 avg", "H/9", r_h9),
    ("HR/9", "HR/9", r_hr9),
]

print(f"\n  {'Attribute':<15} {'Stat':<10} {'r':>6} {'RMSE':>6}")
print("  " + "-" * 40)
for attr, stat, res in sorted(all_results, key=lambda x: -abs(x[2]["r"])):
    print(f"  {attr:<15} {stat:<10} {res['r']:>+.3f} {res['rmse']:>5.1f}")
