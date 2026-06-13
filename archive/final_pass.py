"""Final pass: regenerate all ratings with current formulas, measure RMSE,
identify remaining improvement opportunities, and refit OVR."""
import json, sys, os, numpy as np, warnings
warnings.filterwarnings("ignore")

_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_card import (
    calculate_ratings, calculate_overalls, estimate_ovr_hitter,
    calculate_pitcher_ratings, calculate_pitcher_overalls, estimate_ovr_pitcher,
)
from scipy.optimize import nnls

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_recal_cache.json")) as f:
    cache = json.load(f)
with open(os.path.join(ROOT, "show_truth.json")) as f:
    truth = json.load(f)

h_truth = truth["hitters"]
p_truth = truth["pitchers"]

HITTER_ATTR_MAP = {
    "contact_right": ("con_r", "Contact R"),
    "contact_left": ("con_l", "Contact L"),
    "power_right": ("pwr_r", "Power R"),
    "power_left": ("pwr_l", "Power L"),
    "vision": ("vision", "Vision"),
    "discipline": ("disc", "Discipline"),
    "batting_clutch": ("clutch", "Clutch"),
    "fielding": ("fielding", "Fielding"),
    "arm_strength": ("arm_str", "Arm Str"),
    "arm_accuracy": ("arm_acc", "Arm Acc"),
    "speed": ("speed", "Speed"),
    "stealing": ("stealing", "Stealing"),
    "br_aggressiveness": ("br_agg", "BR Agg"),
    "durability": ("dur", "Durability"),
}

PITCHER_ATTR_MAP = {
    "h_per_9_left": ("h9_l", "H/9 L"),
    "h_per_9_right": ("h9_r", "H/9 R"),
    "k_per_9_left": ("k9_l", "K/9 L"),
    "k_per_9_right": ("k9_r", "K/9 R"),
    "hr_per_9": ("hr9", "HR/9"),
    "pitching_clutch": ("clutch", "Pit Clutch"),
    "control": ("ctrl", "Control"),
    "velocity": ("velo", "Velocity"),
    "break_": ("brk", "Break"),
    "stamina": ("stam", "Stamina"),
}

# ============================================================
# REGENERATE HITTER RATINGS
# ============================================================
print("Regenerating hitter ratings with all current formulas...\n")
hitter_gen = {}
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    data = {
        "name": name, "year": 2025,
        "batting": h["raw_data"]["batting"],
        "career_avg": None, "career_yearly": {},
        "sprint_speed": h["raw_data"].get("sprint_speed"),
        "fielding_oaa": h["raw_data"].get("fielding_oaa", {}),
        "position": h["ratings"].get("position", "OF"),
        "splits": h["raw_data"].get("splits"),
        "avg_ev": h["raw_data"].get("avg_ev"),
        "barrel_stats": None,  # not in cache yet
        "catcher_stats": None,
    }
    try:
        ratings = calculate_ratings(data, mode="season")
        overalls = calculate_overalls(ratings)
        ovr = estimate_ovr_hitter(ratings, overalls)
        hitter_gen[name] = {"ratings": ratings, "overalls": overalls, "ovr": ovr}
    except Exception as e:
        print(f"  ERROR {name}: {e}")

# ============================================================
# REGENERATE PITCHER RATINGS
# ============================================================
print("Regenerating pitcher ratings with all current formulas...\n")
pitcher_gen = {}
for name, p in cache["pitchers"].items():
    if name not in p_truth:
        continue
    pit = p["raw_data"]["pitching"]
    sc = p["raw_data"].get("statcast") or {}
    role = "SP" if pit.get("GS", 0) > pit.get("G", 0) * 0.4 else "RP"
    data = {
        "name": name, "year": 2025, "is_pitcher": True,
        "pitching": pit,
        "career_avg": None, "career_yearly": {},
        "role": role,
        "sprint_speed": None,
        "statcast": sc,
    }
    try:
        ratings = calculate_pitcher_ratings(data, mode="season")
        overalls = calculate_pitcher_overalls(ratings)
        ovr = estimate_ovr_pitcher(ratings, overalls)
        pitcher_gen[name] = {"ratings": ratings, "overalls": overalls, "ovr": ovr}
    except Exception as e:
        print(f"  ERROR {name}: {e}")

print(f"Regenerated: {len(hitter_gen)} hitters, {len(pitcher_gen)} pitchers\n")

# ============================================================
# HITTER ACCURACY
# ============================================================
print("=" * 70)
print("  HITTER ATTRIBUTE ACCURACY (ALL CURRENT FORMULAS)")
print("=" * 70)
print(f"  {'Attribute':<14} {'N':>3} {'RMSE':>6} {'Bias':>6} {'r':>6}  Grade")
print("  " + "-" * 52)

h_stats = []
for rat_key, (show_key, display) in HITTER_ATTR_MAP.items():
    errs, gens, shows = [], [], []
    for name in hitter_gen:
        gen = hitter_gen[name]["ratings"].get(rat_key)
        show = h_truth[name].get(show_key)
        if gen is not None and show is not None:
            errs.append(gen - show)
            gens.append(gen)
            shows.append(show)
    if len(errs) < 3:
        continue
    rmse = float(np.sqrt(np.mean(np.array(errs) ** 2)))
    bias = float(np.mean(errs))
    r = float(np.corrcoef(gens, shows)[0, 1])
    grade = "A+" if rmse <= 5 else "A" if rmse <= 8 else "B" if rmse <= 12 else "C" if rmse <= 16 else "F"
    h_stats.append((rmse, display, len(errs), bias, r, grade, rat_key))

for rmse, display, n, bias, r, grade, _ in sorted(h_stats):
    print(f"  {display:<14} {n:>3} {rmse:>5.1f} {bias:>+5.1f} {r:>+.3f}  {grade}")
avg_rmse = np.mean([s[0] for s in h_stats])
print("  " + "-" * 52)
print(f"  {'AVERAGE':<14} {'':>3} {avg_rmse:>5.1f}")

# ============================================================
# PITCHER ACCURACY
# ============================================================
print("\n" + "=" * 70)
print("  PITCHER ATTRIBUTE ACCURACY (ALL CURRENT FORMULAS)")
print("=" * 70)
print(f"  {'Attribute':<14} {'N':>3} {'RMSE':>6} {'Bias':>6} {'r':>6}  Grade")
print("  " + "-" * 52)

p_stats = []
for rat_key, (show_key, display) in PITCHER_ATTR_MAP.items():
    errs, gens, shows = [], [], []
    for name in pitcher_gen:
        gen = pitcher_gen[name]["ratings"].get(rat_key)
        show = p_truth[name].get(show_key)
        if gen is not None and show is not None:
            errs.append(gen - show)
            gens.append(gen)
            shows.append(show)
    if len(errs) < 3:
        continue
    rmse = float(np.sqrt(np.mean(np.array(errs) ** 2)))
    bias = float(np.mean(errs))
    r = float(np.corrcoef(gens, shows)[0, 1]) if len(gens) > 2 else 0
    grade = "A+" if rmse <= 5 else "A" if rmse <= 8 else "B" if rmse <= 12 else "C" if rmse <= 16 else "F"
    p_stats.append((rmse, display, len(errs), bias, r, grade, rat_key))

for rmse, display, n, bias, r, grade, _ in sorted(p_stats):
    print(f"  {display:<14} {n:>3} {rmse:>5.1f} {bias:>+5.1f} {r:>+.3f}  {grade}")
avg_rmse = np.mean([s[0] for s in p_stats])
print("  " + "-" * 52)
print(f"  {'AVERAGE':<14} {'':>3} {avg_rmse:>5.1f}")

# ============================================================
# OVR ACCURACY + REFIT
# ============================================================
print("\n" + "=" * 70)
print("  OVR REFIT")
print("=" * 70)

# Hitter OVR
h_ovr_errs = []
for name in hitter_gen:
    gen = hitter_gen[name]["ovr"]
    show = h_truth[name].get("ovr")
    if show is not None:
        h_ovr_errs.append((name, gen, show, gen - show))
h_rmse = float(np.sqrt(np.mean([e[3] ** 2 for e in h_ovr_errs])))
print(f"\n  Hitter OVR (current): RMSE={h_rmse:.1f} N={len(h_ovr_errs)}")

# Refit hitter OVR with NNLS
h_samples = []
for name in hitter_gen:
    r = hitter_gen[name]["ratings"]
    o = hitter_gen[name]["overalls"]
    show_ovr = h_truth[name].get("ovr")
    if show_ovr is None:
        continue
    core_hit = float(np.mean([
        r["contact_right"], r["contact_left"],
        r["power_right"], r["power_left"],
        r["vision"], r["discipline"],
        r["batting_clutch"],
    ]))
    h_samples.append(([core_hit, o["fielding"], r["speed"], o["durability"]], show_ovr, name))

X = np.array([s[0] for s in h_samples], dtype=float)
y = np.array([s[1] for s in h_samples], dtype=float)
coefs_nn, _ = nnls(X, y)
pred_nn = X @ coefs_nn
rmse_nn = float(np.sqrt(np.mean((y - pred_nn) ** 2)))
print(f"  Hitter OVR (NNLS refit): RMSE={rmse_nn:.1f}")
print(f"    core_hitting = {coefs_nn[0]:.4f}")
print(f"    fielding     = {coefs_nn[1]:.4f}")
print(f"    speed        = {coefs_nn[2]:.4f}")
print(f"    durability   = {coefs_nn[3]:.4f}")

# Worst misses
print(f"\n  Worst hitter OVR misses:")
for name, gen, show, err in sorted(h_ovr_errs, key=lambda x: -abs(x[3]))[:10]:
    nnls_pred = float(X[next(i for i, s in enumerate(h_samples) if s[2] == name)] @ coefs_nn)
    print(f"    {name:25s} cur={gen:3d} nnls={nnls_pred:5.1f} show={show:3d} cur_err={err:+3d} nnls_err={nnls_pred-show:+5.1f}")

# Pitcher OVR
p_ovr_errs = []
for name in pitcher_gen:
    gen = pitcher_gen[name]["ovr"]
    show = p_truth[name].get("ovr")
    if show is not None:
        p_ovr_errs.append((name, gen, show, gen - show))
p_rmse = float(np.sqrt(np.mean([e[3] ** 2 for e in p_ovr_errs])))
print(f"\n  Pitcher OVR (current): RMSE={p_rmse:.1f} N={len(p_ovr_errs)}")

p_samples = []
for name in pitcher_gen:
    o = pitcher_gen[name]["overalls"]
    show_ovr = p_truth[name].get("ovr")
    if show_ovr is None:
        continue
    p_samples.append(([o["pitching"], o["fielding"], o["durability"]], show_ovr, name))

X = np.array([s[0] for s in p_samples], dtype=float)
y = np.array([s[1] for s in p_samples], dtype=float)
coefs_nn, _ = nnls(X, y)
pred_nn = X @ coefs_nn
rmse_nn = float(np.sqrt(np.mean((y - pred_nn) ** 2)))
print(f"  Pitcher OVR (NNLS refit): RMSE={rmse_nn:.1f}")
print(f"    pitching     = {coefs_nn[0]:.4f}")
print(f"    fielding     = {coefs_nn[1]:.4f}")
print(f"    durability   = {coefs_nn[2]:.4f}")

# ============================================================
# REMAINING OPPORTUNITIES ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("  REMAINING IMPROVEMENT OPPORTUNITIES")
print("=" * 70)

# For each attribute with RMSE > 8, analyze what's driving the error
for rmse, display, n, bias, r, grade, rat_key in sorted(h_stats, reverse=True):
    if rmse <= 8:
        break
    show_key = [sk for rk, (sk, d) in HITTER_ATTR_MAP.items() if rk == rat_key][0]
    errs = []
    for name in hitter_gen:
        gen = hitter_gen[name]["ratings"].get(rat_key)
        show = h_truth[name].get(show_key)
        if gen is not None and show is not None:
            errs.append((name, gen, show, gen - show))
    errs.sort(key=lambda x: -abs(x[3]))
    top3 = errs[:3]
    print(f"\n  {display} (RMSE={rmse:.1f}, bias={bias:+.1f}):")
    print(f"    Biggest misses: {', '.join(f'{n} ({e:+d})' for n, g, s, e in top3)}")
    # Is it systematic (bias) or random?
    if abs(bias) > 3:
        print(f"    -> Systematic {('over' if bias > 0 else 'under')}-prediction by {abs(bias):.1f} pts")
    else:
        print(f"    -> Random error (no systematic bias)")
