"""
Comprehensive per-attribute recalibration.

Pulls live data for every calibration player via the BBRef/Statcast pipeline,
generates ratings with the current formulas, compares each attribute against
the real Show 26 ground truth, and re-fits every formula.

Outputs:
  1. Per-attribute error table (generated vs Show, residual, RMSE, r)
  2. New regression coefficients for each attribute
  3. OVR refit (same as recalibrate.py but with the expanded set)

Usage:
  python recalibrate_all.py               # full run (pulls data, ~5 min)
  python recalibrate_all.py --skip-pull   # reuse cached results from last run
"""

import sys
import os
import json
import argparse
import warnings
import numpy as np
from scipy.optimize import nnls

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

warnings.filterwarnings("ignore")

from generate_card import (
    pull_all_data, pull_all_pitcher_data,
    calculate_ratings, calculate_overalls,
    calculate_pitcher_ratings, calculate_pitcher_overalls,
    estimate_ovr_hitter, estimate_ovr_pitcher,
    clamp,
)

YEAR = 2025
CACHE_FILE = os.path.join(os.path.dirname(__file__), "_recal_cache.json")
TRUTH_FILE = os.path.join(os.path.dirname(__file__), "show_truth.json")

# ================================================================
# GROUND TRUTH: loaded from show_truth.json (scraped from theshowratings.com)
# ================================================================

def load_truth_data():
    """Load ground truth from show_truth.json. Falls back to legacy hardcoded set."""
    if os.path.exists(TRUTH_FILE):
        with open(TRUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        hitters = data.get("hitters", {})
        pitchers = data.get("pitchers", {})
        meta = data.get("metadata", {})
        print(f"  Loaded truth data: {len(hitters)} hitters, {len(pitchers)} pitchers")
        print(f"  Source: {meta.get('source', '?')}, scraped: {meta.get('scraped_at', '?')}")
        return hitters, pitchers
    else:
        print("  WARNING: show_truth.json not found. Run scrape_truth.py first.")
        print("  Falling back to legacy hardcoded truth (18 hitters, 10 pitchers).")
        return _LEGACY_HITTER_TRUTH, _LEGACY_PITCHER_TRUTH


# Legacy fallback (original 18 hitters + 10 pitchers from manual data entry)
_LEGACY_HITTER_TRUTH = {
    "Juan Soto":              {"ovr": 98, "con_r": 85, "con_l": 75, "pwr_r": 99, "pwr_l": 88, "vision": 72, "disc": 99, "clutch": 83, "fielding": 53, "arm_str": 71, "arm_acc": 70, "speed": 42, "stealing": 77, "br_agg": 77, "dur": 98, "bunt": 38, "drag": 56},
    "Byron Buxton":           {"ovr": 95, "con_r": 70, "con_l": 87, "pwr_r": 85, "pwr_l": 84, "vision": 50, "disc": 50, "clutch": 78, "fielding": 83, "arm_str": 78, "arm_acc": 71, "speed": 99, "stealing": 75, "br_agg": 61, "dur": 84, "bunt": 35, "drag": 25},
    "Vladimir Guerrero Jr.":  {"ovr": 94, "con_r": 93, "con_l": 99, "pwr_r": 73, "pwr_l": 73, "vision": 85, "disc": 84, "clutch": 92, "fielding": 55, "arm_str": 59, "arm_acc": 62, "speed": 45, "stealing": 16, "br_agg": 26, "dur": 98, "bunt": 35, "drag": 25},
    "Aaron Judge":            {"ovr": 99, "con_r": 90, "con_l": 92, "pwr_r": 99, "pwr_l": 99, "vision": 42, "disc": 99, "clutch": 91, "fielding": 61, "arm_str": 80, "arm_acc": 78, "speed": 50, "stealing": 36, "br_agg": 51, "dur": 97, "bunt": 35, "drag": 25},
}

_LEGACY_PITCHER_TRUTH = {
    "Garrett Crochet":      {"ovr": 94, "h9_l": 81, "h9_r": 86, "k9_l": 63, "k9_r": 92, "hr9": 72, "clutch": 64, "ctrl": 64, "velo": 99, "brk": 81, "stam": 90},
    "Tarik Skubal":         {"ovr": 96, "h9_l": 89, "h9_r": 91, "k9_l": 77, "k9_r": 88, "hr9": 79, "clutch": 95, "ctrl": 82, "velo": 77, "brk": 84, "stam": 99},
    "Yoshinobu Yamamoto":   {"ovr": 95, "h9_l": 91, "h9_r": 84, "k9_l": 76, "k9_r": 89, "hr9": 72, "clutch": 82, "ctrl": 68, "velo": 98, "brk": 99, "stam": 83},
}

# These get populated at runtime by load_truth_data()
HITTER_TRUTH = {}
PITCHER_TRUTH = {}


# ================================================================
# DATA COLLECTION
# ================================================================

def collect_hitter(name):
    """Pull data and generate ratings for one hitter. Returns dict or None."""
    print(f"\n{'='*60}")
    print(f"  HITTER: {name} ({YEAR})")
    print(f"{'='*60}")
    try:
        data = pull_all_data(name, YEAR)
        if data is None:
            print(f"  SKIP: data pull failed for {name}")
            return None
        ratings = calculate_ratings(data, mode="season")
        overalls = calculate_overalls(ratings)
        ovr = estimate_ovr_hitter(ratings, overalls)
        return {
            "name": name,
            "ratings": ratings,
            "overalls": overalls,
            "ovr": ovr,
            "raw_data": {
                "batting": data["batting"],
                "sprint_speed": data.get("sprint_speed"),
                "splits": data.get("splits"),
                "avg_ev": data.get("avg_ev"),
                "fielding_oaa": {k: v for k, v in (data.get("fielding_oaa") or {}).items()
                                 if not str(k).startswith("_")},
            },
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def collect_pitcher(name):
    """Pull data and generate ratings for one pitcher. Returns dict or None."""
    print(f"\n{'='*60}")
    print(f"  PITCHER: {name} ({YEAR})")
    print(f"{'='*60}")
    try:
        data = pull_all_pitcher_data(name, YEAR)
        if data is None:
            print(f"  SKIP: data pull failed for {name}")
            return None
        ratings = calculate_pitcher_ratings(data, mode="season")
        overalls = calculate_pitcher_overalls(ratings)
        ovr = estimate_ovr_pitcher(ratings, overalls)
        return {
            "name": name,
            "ratings": ratings,
            "overalls": overalls,
            "ovr": ovr,
            "raw_data": {
                "pitching": data["pitching"],
                "statcast": data.get("statcast") or {},
            },
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def collect_all(skip_pull=False, max_hitters=None, max_pitchers=None):
    """Collect generated ratings for all calibration players.
    If max_hitters/max_pitchers set, only process that many (sorted by OVR desc)."""
    if skip_pull and os.path.exists(CACHE_FILE):
        print(f"Loading cached results from {CACHE_FILE}...")
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    results = {"hitters": {}, "pitchers": {}}

    # Sort by OVR descending so we get the best players first (most calibration value)
    hitter_names = sorted(HITTER_TRUTH.keys(),
                          key=lambda n: HITTER_TRUTH[n].get("ovr", 0), reverse=True)
    pitcher_names = sorted(PITCHER_TRUTH.keys(),
                           key=lambda n: PITCHER_TRUTH[n].get("ovr", 0), reverse=True)

    if max_hitters:
        hitter_names = hitter_names[:max_hitters]
    if max_pitchers:
        pitcher_names = pitcher_names[:max_pitchers]

    print(f"\n  Will process {len(hitter_names)} hitters, {len(pitcher_names)} pitchers")

    for i, name in enumerate(hitter_names):
        print(f"\n  [{i+1}/{len(hitter_names)}]", end="")
        r = collect_hitter(name)
        if r:
            results["hitters"][name] = r

    for i, name in enumerate(pitcher_names):
        print(f"\n  [{i+1}/{len(pitcher_names)}]", end="")
        r = collect_pitcher(name)
        if r:
            results["pitchers"][name] = r

    # Cache results
    with open(CACHE_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nCached results to {CACHE_FILE}")

    return results


# ================================================================
# ANALYSIS: PER-ATTRIBUTE COMPARISON
# ================================================================

HITTER_ATTR_MAP = {
    # attribute_key_in_ratings: (show_key_in_truth, display_name)
    "contact_right":    ("con_r",    "Contact R"),
    "contact_left":     ("con_l",    "Contact L"),
    "power_right":      ("pwr_r",    "Power R"),
    "power_left":       ("pwr_l",    "Power L"),
    "vision":           ("vision",   "Vision"),
    "discipline":       ("disc",     "Discipline"),
    "batting_clutch":   ("clutch",   "Clutch"),
    "fielding":         ("fielding", "Fielding"),
    "arm_strength":     ("arm_str",  "Arm Str"),
    "arm_accuracy":     ("arm_acc",  "Arm Acc"),
    "speed":            ("speed",    "Speed"),
    "stealing":         ("stealing", "Stealing"),
    "br_aggressiveness":("br_agg",   "BR Agg"),
    "durability":       ("dur",      "Durability"),
}

PITCHER_ATTR_MAP = {
    "h_per_9_left":     ("h9_l",   "H/9 L"),
    "h_per_9_right":    ("h9_r",   "H/9 R"),
    "k_per_9_left":     ("k9_l",   "K/9 L"),
    "k_per_9_right":    ("k9_r",   "K/9 R"),
    "hr_per_9":         ("hr9",    "HR/9"),
    "pitching_clutch":  ("clutch", "Pit Clutch"),
    "control":          ("ctrl",   "Control"),
    "velocity":         ("velo",   "Velocity"),
    "break_":           ("brk",    "Break"),
    "stamina":          ("stam",   "Stamina"),
}


def analyze_attribute(attr_name, display_name, generated, show_truth, players):
    """Compare one attribute across all players. Returns stats dict."""
    pairs = []  # (name, gen, show, residual)
    for name in players:
        gen_val = generated.get(name)
        show_val = show_truth.get(name)
        if gen_val is not None and show_val is not None:
            pairs.append((name, gen_val, show_val, gen_val - show_val))

    if len(pairs) < 3:
        return None

    gen_arr = np.array([p[1] for p in pairs], dtype=float)
    show_arr = np.array([p[2] for p in pairs], dtype=float)
    resid_arr = gen_arr - show_arr

    rmse = float(np.sqrt(np.mean(resid_arr ** 2)))
    mae = float(np.mean(np.abs(resid_arr)))
    r = float(np.corrcoef(gen_arr, show_arr)[0, 1]) if len(pairs) >= 3 else 0
    bias = float(np.mean(resid_arr))

    return {
        "name": display_name,
        "n": len(pairs),
        "rmse": rmse,
        "mae": mae,
        "r": r,
        "bias": bias,
        "pairs": pairs,
    }


def print_attr_report(stats, title):
    """Print detailed per-attribute report."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

    # Summary table
    print(f"\n  {'Attribute':<14} {'N':>3} {'RMSE':>6} {'MAE':>5} {'Bias':>6} {'r':>6}  Grade")
    print(f"  {'-'*58}")

    sorted_stats = sorted(stats, key=lambda s: s["rmse"])
    for s in sorted_stats:
        grade = ("A+" if s["rmse"] <= 5 else "A" if s["rmse"] <= 8 else
                 "B" if s["rmse"] <= 12 else "C" if s["rmse"] <= 16 else "F")
        print(f"  {s['name']:<14} {s['n']:>3} {s['rmse']:>5.1f} {s['mae']:>5.1f} "
              f"{s['bias']:>+5.1f} {s['r']:>+.3f}  {grade}")

    avg_rmse = np.mean([s["rmse"] for s in stats])
    avg_r = np.mean([s["r"] for s in stats])
    print(f"  {'-'*58}")
    print(f"  {'AVERAGE':<14} {'':>3} {avg_rmse:>5.1f} {'':>5} {'':>6} {avg_r:>+.3f}")

    # Worst misses (|residual| > 15)
    print(f"\n  WORST MISSES (|error| > 15):")
    print(f"  {'Player':<25} {'Attr':<14} {'Gen':>4} {'Show':>4} {'Err':>5}")
    print(f"  {'-'*56}")
    all_misses = []
    for s in stats:
        for name, gen, show, resid in s["pairs"]:
            if abs(resid) > 15:
                all_misses.append((abs(resid), name, s["name"], gen, show, resid))
    for _, name, attr, gen, show, resid in sorted(all_misses, reverse=True):
        print(f"  {name:<25} {attr:<14} {gen:>4} {show:>4} {resid:>+5.0f}")

    if not all_misses:
        print(f"  (none)")


def print_per_player_detail(stats):
    """Print per-player attribute detail for one stat."""
    s = stats
    print(f"\n  {s['name']} (N={s['n']}, RMSE={s['rmse']:.1f}, r={s['r']:.3f}, bias={s['bias']:+.1f}):")
    print(f"    {'Player':<25} {'Gen':>4} {'Show':>4} {'Err':>5}")
    print(f"    {'-'*42}")
    for name, gen, show, resid in sorted(s["pairs"], key=lambda p: -abs(p[3])):
        flag = " ***" if abs(resid) > 15 else " *" if abs(resid) > 10 else ""
        print(f"    {name:<25} {gen:>4} {show:>4} {resid:>+5.0f}{flag}")


# ================================================================
# REGRESSION REFIT
# ================================================================

def refit_linear(x, y, label):
    """Fit y = m*x + b, report coefficients and improvement opportunity."""
    x, y = np.array(x, float), np.array(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 4:
        return None

    A = np.column_stack([x, np.ones(len(x))])
    coefs, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    preds = A @ coefs
    rmse = float(np.sqrt(np.mean((y - preds) ** 2)))
    r = float(np.corrcoef(x, y)[0, 1])

    return {
        "label": label,
        "m": round(coefs[0], 4),
        "b": round(coefs[1], 1),
        "rmse": round(rmse, 1),
        "r": round(r, 4),
        "n": len(x),
    }


def refit_ovr(features_keys, samples, label):
    """Refit OVR formula using NNLS. samples: list of (feats_dict, target)."""
    X = np.array([[s[0][k] for k in features_keys] for s in samples], dtype=float)
    y = np.array([s[1] for s in samples], dtype=float)

    # NNLS (non-negative weights, no intercept)
    coefs_nn, _ = nnls(X, y)
    pred_nn = X @ coefs_nn
    rmse_nn = float(np.sqrt(np.mean((y - pred_nn) ** 2)))

    # lstsq with intercept
    X_aug = np.hstack([X, np.ones((len(X), 1))])
    coefs_ls, *_ = np.linalg.lstsq(X_aug, y, rcond=None)
    pred_ls = X_aug @ coefs_ls
    rmse_ls = float(np.sqrt(np.mean((y - pred_ls) ** 2)))

    print(f"\n{'='*70}")
    print(f"  {label} OVR REFIT (N={len(samples)})")
    print(f"{'='*70}")

    print(f"\n  [NNLS] RMSE={rmse_nn:.2f} (no intercept, weights >= 0)")
    for k, c in zip(features_keys, coefs_nn):
        print(f"    {k:12s} = {c:+.4f}")

    print(f"\n  [lstsq] RMSE={rmse_ls:.2f}")
    for k, c in zip(features_keys, coefs_ls[:-1]):
        print(f"    {k:12s} = {c:+.4f}")
    print(f"    {'intercept':12s} = {coefs_ls[-1]:+.4f}")

    print(f"\n  Per-player:")
    print(f"    {'Name':<25} {'Target':>6} {'NNLS':>6} {'lstsq':>6} {'r_nn':>6} {'r_ls':>6}")
    for (feats, tgt), p_nn, p_ls in zip(samples, pred_nn, pred_ls):
        name = feats.get("_name", "?")
        print(f"    {name:<25} {tgt:>6} {p_nn:>6.1f} {p_ls:>6.1f} "
              f"{tgt-p_nn:>+6.1f} {tgt-p_ls:>+6.1f}")

    return {
        "nnls_coefs": {k: round(float(c), 4) for k, c in zip(features_keys, coefs_nn)},
        "nnls_rmse": round(rmse_nn, 2),
        "lstsq_coefs": {k: round(float(c), 4) for k, c in zip(features_keys, coefs_ls[:-1])},
        "lstsq_intercept": round(float(coefs_ls[-1]), 2),
        "lstsq_rmse": round(rmse_ls, 2),
    }


# ================================================================
# MAIN
# ================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pull", action="store_true",
                        help="Reuse cached data from last run")
    parser.add_argument("--detail", action="store_true",
                        help="Print per-player detail for every attribute")
    parser.add_argument("--refresh-truth", action="store_true",
                        help="Re-scrape truth data from theshowratings.com before refitting")
    parser.add_argument("--max-hitters", type=int, default=None,
                        help="Limit hitters to process (sorted by OVR desc)")
    parser.add_argument("--max-pitchers", type=int, default=None,
                        help="Limit pitchers to process (sorted by OVR desc)")
    args = parser.parse_args()

    # 0. Optionally refresh truth data from the web
    global HITTER_TRUTH, PITCHER_TRUTH
    if args.refresh_truth:
        print("\n  Refreshing truth data from theshowratings.com...")
        from scrape_truth import scrape_all, save_truth
        h, p = scrape_all()
        save_truth(h, p)
        HITTER_TRUTH, PITCHER_TRUTH = h, p
    else:
        HITTER_TRUTH, PITCHER_TRUTH = load_truth_data()

    # 1. Collect data
    results = collect_all(skip_pull=args.skip_pull,
                          max_hitters=args.max_hitters,
                          max_pitchers=args.max_pitchers)
    hitters = results["hitters"]
    pitchers = results["pitchers"]

    print(f"\n\nCollected: {len(hitters)} hitters, {len(pitchers)} pitchers")
    print(f"Hitter truth: {len(HITTER_TRUTH)} players")
    print(f"Pitcher truth: {len(PITCHER_TRUTH)} players")

    # 2. Per-attribute analysis — HITTERS
    hitter_stats = []
    for rat_key, (show_key, display) in HITTER_ATTR_MAP.items():
        gen_vals = {}
        show_vals = {}
        for name in HITTER_TRUTH:
            if name in hitters:
                gen_vals[name] = hitters[name]["ratings"].get(rat_key)
            show_vals[name] = HITTER_TRUTH[name].get(show_key)

        s = analyze_attribute(rat_key, display, gen_vals, show_vals,
                              [n for n in HITTER_TRUTH if n in hitters])
        if s:
            hitter_stats.append(s)
            if args.detail:
                print_per_player_detail(s)

    print_attr_report(hitter_stats, "HITTER ATTRIBUTE ACCURACY")

    # 3. Per-attribute analysis — PITCHERS
    pitcher_stats = []
    for rat_key, (show_key, display) in PITCHER_ATTR_MAP.items():
        gen_vals = {}
        show_vals = {}
        for name in PITCHER_TRUTH:
            if name in pitchers:
                gen_vals[name] = pitchers[name]["ratings"].get(rat_key)
            show_vals[name] = PITCHER_TRUTH[name].get(show_key)

        s = analyze_attribute(rat_key, display, gen_vals, show_vals,
                              [n for n in PITCHER_TRUTH if n in pitchers])
        if s:
            pitcher_stats.append(s)
            if args.detail:
                print_per_player_detail(s)

    print_attr_report(pitcher_stats, "PITCHER ATTRIBUTE ACCURACY")

    # 4. OVR analysis
    print(f"\n{'='*80}")
    print(f"  OVR ACCURACY")
    print(f"{'='*80}")

    # Hitter OVR
    h_ovr_pairs = []
    for name in HITTER_TRUTH:
        if name in hitters:
            gen_ovr = hitters[name]["ovr"]
            show_ovr = HITTER_TRUTH[name]["ovr"]
            h_ovr_pairs.append((name, gen_ovr, show_ovr, gen_ovr - show_ovr))

    if h_ovr_pairs:
        h_rmse = float(np.sqrt(np.mean([p[3]**2 for p in h_ovr_pairs])))
        print(f"\n  Hitter OVR (N={len(h_ovr_pairs)}, RMSE={h_rmse:.1f}):")
        print(f"    {'Name':<25} {'Gen':>4} {'Show':>4} {'Err':>5}")
        print(f"    {'-'*42}")
        for name, gen, show, resid in sorted(h_ovr_pairs, key=lambda p: -abs(p[3])):
            flag = " ***" if abs(resid) > 5 else ""
            print(f"    {name:<25} {gen:>4} {show:>4} {resid:>+5}{flag}")

    # Pitcher OVR
    p_ovr_pairs = []
    for name in PITCHER_TRUTH:
        if name in pitchers:
            gen_ovr = pitchers[name]["ovr"]
            show_ovr = PITCHER_TRUTH[name]["ovr"]
            p_ovr_pairs.append((name, gen_ovr, show_ovr, gen_ovr - show_ovr))

    if p_ovr_pairs:
        p_rmse = float(np.sqrt(np.mean([p[3]**2 for p in p_ovr_pairs])))
        print(f"\n  Pitcher OVR (N={len(p_ovr_pairs)}, RMSE={p_rmse:.1f}):")
        print(f"    {'Name':<25} {'Gen':>4} {'Show':>4} {'Err':>5}")
        print(f"    {'-'*42}")
        for name, gen, show, resid in sorted(p_ovr_pairs, key=lambda p: -abs(p[3])):
            flag = " ***" if abs(resid) > 5 else ""
            print(f"    {name:<25} {gen:>4} {show:>4} {resid:>+5}{flag}")

    # 5. OVR REFIT
    if h_ovr_pairs:
        h_samples = []
        for name in HITTER_TRUTH:
            if name not in hitters:
                continue
            r = hitters[name]["ratings"]
            o = hitters[name]["overalls"]
            core_hit = float(np.mean([
                r["contact_right"], r["contact_left"],
                r["power_right"], r["power_left"],
                r["vision"], r["discipline"],
                r["batting_clutch"],
            ]))
            feats = {
                "_name": name,
                "core_hit": core_hit,
                "fielding": o["fielding"],
                "speed": r["speed"],
                "durability": o["durability"],
            }
            h_samples.append((feats, HITTER_TRUTH[name]["ovr"]))

        refit_ovr(["core_hit", "fielding", "speed", "durability"], h_samples, "HITTER")

    if p_ovr_pairs:
        p_samples = []
        for name in PITCHER_TRUTH:
            if name not in pitchers:
                continue
            o = pitchers[name]["overalls"]
            feats = {
                "_name": name,
                "pitching": o["pitching"],
                "fielding": o["fielding"],
                "durability": o["durability"],
            }
            p_samples.append((feats, PITCHER_TRUTH[name]["ovr"]))

        refit_ovr(["pitching", "fielding", "durability"], p_samples, "PITCHER")

    # 6. Summary
    print(f"\n\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  Hitters:  {len(hitters)}/{len(HITTER_TRUTH)} collected")
    print(f"  Pitchers: {len(pitchers)}/{len(PITCHER_TRUTH)} collected")
    if hitter_stats:
        worst = max(hitter_stats, key=lambda s: s["rmse"])
        best = min(hitter_stats, key=lambda s: s["rmse"])
        print(f"  Best hitter attr:  {best['name']} (RMSE={best['rmse']:.1f})")
        print(f"  Worst hitter attr: {worst['name']} (RMSE={worst['rmse']:.1f})")
    if pitcher_stats:
        worst = max(pitcher_stats, key=lambda s: s["rmse"])
        best = min(pitcher_stats, key=lambda s: s["rmse"])
        print(f"  Best pitcher attr:  {best['name']} (RMSE={best['rmse']:.1f})")
        print(f"  Worst pitcher attr: {worst['name']} (RMSE={worst['rmse']:.1f})")
    if h_ovr_pairs:
        print(f"  Hitter OVR RMSE:  {h_rmse:.1f}")
    if p_ovr_pairs:
        print(f"  Pitcher OVR RMSE: {p_rmse:.1f}")

    print(f"\n  Next steps:")
    print(f"  - Attributes with RMSE > 12 need formula rework")
    print(f"  - Attributes with |bias| > 5 have systematic over/under-prediction")
    print(f"  - Run with --detail to see per-player breakdowns")
    print()


if __name__ == "__main__":
    main()
