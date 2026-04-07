"""
OVR coefficient recalibration after the BBRef migration.

Generates cards for the calibration set via the current (BBRef-fed) pipeline,
collects sub-attribute features + true Show OVR targets, and fits new linear
coefficients for estimate_ovr_hitter / estimate_ovr_pitcher via lstsq.

Prints per-player residuals BEFORE recommending a coefficient swap. We do not
edit generate_card.py from this script — coefficients are reported and
hand-applied after review.
"""

import sys
import warnings
import numpy as np

import os
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
)

YEAR = 2025

# Targets from CLAUDE.md. Duran excluded — no listed target.
HITTERS = [
    ("Juan Soto",            None, 98),
    ("Bobby Witt Jr.",       None, 99),
    ("Byron Buxton",         None, 95),
    ("Vladimir Guerrero Jr.",None, 94),
    ("Yordan Alvarez",       None, 91),
    ("Pete Crow-Armstrong",  None, 87),
    ("Adley Rutschman",      None, 84),
    ("Xander Bogaerts",      None, 80),
    ("Matt Shaw",            None, 74),
    ("Hyeseong Kim",         None, 74),
    ("Chandler Simpson",     None, 72),
]

# Pitchers — some surnames in CLAUDE.md are ambiguous; my best guesses noted.
PITCHERS = [
    ("Garrett Crochet", 94),
    ("Tarik Skubal",    96),
    ("Ranger Suárez",   88),
    ("Cole Ragans",     83),
    ("Nolan McLean",    82),
    ("Pablo López",     82),
    ("Pete Fairbanks",  81),
    ("Will Smith",      81),
    ("Jeff Hoffman",    80),
    ("Connolly Early",  76),
    # "Tolle" — still unidentified; skipping
]


def collect_hitter(name, position, target):
    print(f"\n--- {name} ({YEAR}) target={target}")
    data = pull_all_data(name, YEAR)
    if data is None:
        print(f"  SKIP: data pull failed")
        return None
    ratings  = calculate_ratings(data, position_override=position, mode="season")
    overalls = calculate_overalls(ratings)

    core_hit = float(np.mean([
        ratings["contact_right"], ratings["contact_left"],
        ratings["power_right"],   ratings["power_left"],
        ratings["vision"],        ratings["discipline"],
        ratings["batting_clutch"],
    ]))
    feats = {
        "core_hit":   core_hit,
        "fielding":   overalls["fielding"],
        "speed":      ratings["speed"],
        "durability": overalls["durability"],
    }
    pred_old = estimate_ovr_hitter(ratings, overalls)
    print(f"  feats: core_hit={feats['core_hit']:.1f} fld={feats['fielding']} "
          f"spd={feats['speed']} dur={feats['durability']}  "
          f"old_pred={pred_old}  target={target}  resid_old={target - pred_old:+d}")
    return name, feats, target, pred_old


def collect_pitcher(name, target):
    print(f"\n--- {name} ({YEAR}) target={target}")
    data = pull_all_pitcher_data(name, YEAR)
    if data is None:
        print(f"  SKIP: data pull failed")
        return None
    ratings  = calculate_pitcher_ratings(data, mode="season")
    overalls = calculate_pitcher_overalls(ratings)

    feats = {
        "pitching":   overalls["pitching"],
        "fielding":   overalls["fielding"],
        "durability": overalls["durability"],
    }
    pred_old = estimate_ovr_pitcher(ratings, overalls)
    print(f"  feats: pit={feats['pitching']} fld={feats['fielding']} "
          f"dur={feats['durability']}  "
          f"old_pred={pred_old}  target={target}  resid_old={target - pred_old:+d}")
    return name, feats, target, pred_old


def fit(features_keys, samples, label):
    """Two fits, side by side:
       - lstsq: unconstrained linear least squares (may zero out features)
       - nnls : non-negative least squares (forces all weights >= 0)
    Samples are tuples (name, feats, target, pred_old)."""
    from scipy.optimize import nnls

    X = np.array([[s[1][k] for k in features_keys] for s in samples], dtype=float)
    y = np.array([s[2] for s in samples], dtype=float)
    X_aug = np.hstack([X, np.ones((len(X), 1))])

    # --- Unconstrained lstsq ---
    coefs_ls, *_ = np.linalg.lstsq(X_aug, y, rcond=None)
    pred_ls  = X_aug @ coefs_ls
    rmse_ls  = float(np.sqrt(np.mean((y - pred_ls) ** 2)))

    # --- NNLS (non-negative weights, intercept fixed to 0) ---
    coefs_nn, _ = nnls(X, y)
    pred_nn = X @ coefs_nn
    rmse_nn = float(np.sqrt(np.mean((y - pred_nn) ** 2)))

    print(f"\n========== {label} fit ==========")
    print(f"  features: {features_keys}")
    print(f"  N = {len(samples)}")

    print(f"\n  [lstsq] RMSE = {rmse_ls:.2f}")
    for k, c in zip(features_keys, coefs_ls[:-1]):
        print(f"    {k:12s} = {c:+.4f}")
    print(f"    {'intercept':12s} = {coefs_ls[-1]:+.4f}")

    print(f"\n  [nnls]  RMSE = {rmse_nn:.2f}  (no intercept, weights >= 0)")
    for k, c in zip(features_keys, coefs_nn):
        print(f"    {k:12s} = {c:+.4f}")

    # Old-coefficient RMSE for comparison
    old_rmse = float(np.sqrt(np.mean([(s[2] - s[3]) ** 2 for s in samples])))
    print(f"\n  [old]   RMSE = {old_rmse:.2f}  (current generate_card.py)")

    print(f"\n  per-player residuals:")
    print(f"    {'name':25s} {'target':>6s}  {'old':>4s}  {'lstsq':>6s} {'nn':>6s}  "
          f"{'r_old':>6s} {'r_ls':>6s} {'r_nn':>6s}")
    for (name, feats, tgt, pred_old), p_ls, p_nn in zip(samples, pred_ls, pred_nn):
        print(f"    {name[:25]:25s} {tgt:6d}  {pred_old:4d}  "
              f"{p_ls:6.1f} {p_nn:6.1f}  "
              f"{tgt-pred_old:+6.1f} {tgt-p_ls:+6.1f} {tgt-p_nn:+6.1f}")

    return coefs_ls, coefs_nn, rmse_ls, rmse_nn, old_rmse


def main():
    print("Collecting hitter samples...")
    hitters = []
    for name, pos, tgt in HITTERS:
        s = collect_hitter(name, pos, tgt)
        if s is not None:
            hitters.append(s)

    print("\nCollecting pitcher samples...")
    pitchers = []
    for name, tgt in PITCHERS:
        s = collect_pitcher(name, tgt)
        if s is not None:
            pitchers.append(s)

    if hitters:
        fit(["core_hit", "fielding", "speed", "durability"], hitters, "HITTER OVR")
    if pitchers:
        fit(["pitching", "fielding", "durability"], pitchers, "PITCHER OVR")


if __name__ == "__main__":
    main()
