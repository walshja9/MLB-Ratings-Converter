"""Refit hitter OVR across the full talent range (mirror of the pitcher refit).

The calibration only used the top ~130 hitters (cache OVR 78-99), so the hitter
OVR formula may over-rate the mid/low tier just like the pitcher one did. Reuse
cached top hitters + pull the sub-78 MLB hitters (truth OVR 55-78) and refit.
"""

import json
import numpy as np
from generate_card import pull_all_data, calculate_ratings, calculate_overalls

YEAR = 2025
truth = json.load(open("show_truth.json"))["hitters"]
cache = json.load(open("_recal_cache.json"))["hitters"]


def core(r):
    return float(np.mean([r["contact_right"], r["contact_left"], r["power_right"],
                          r["power_left"], r["vision"], r["discipline"], r["batting_clutch"]]))


rows = []  # (core, field, speed, dur, ovr)
for n, c in cache.items():
    if n in truth and truth[n].get("ovr", 0) > 0:
        rows.append((core(c["ratings"]), c["overalls"]["fielding"], c["ratings"]["speed"],
                     c["overalls"]["durability"], truth[n]["ovr"]))

have = set(cache)
targets = [n for n, v in truth.items() if 55 <= v.get("ovr", 0) < 78 and n not in have]
print(f"cache rows: {len(rows)} | new sub-78 targets: {len(targets)}", flush=True)

pulled = 0
for i, n in enumerate(targets):
    try:
        d = pull_all_data(n, YEAR)
        if d is None:
            continue
        r = calculate_ratings(d, None, "season")
        o = calculate_overalls(r)
        rows.append((core(r), o["fielding"], r["speed"], o["durability"], truth[n]["ovr"]))
        pulled += 1
    except Exception:
        continue
    if (i + 1) % 40 == 0:
        print(f"  {i + 1}/{len(targets)} pulled {pulled}", flush=True)

CH, FL, SP, DU, Y = [np.array(x, float) for x in zip(*rows)]
print(f"\ntotal rows: {len(rows)} (pulled {pulled}), OVR range {Y.min():.0f}-{Y.max():.0f}")
cur = np.clip(0.667 * CH + 0.024 * FL + 0.038 * SP + 0.091 * DU + 25.4, 0, 99)
print(f"current: RMSE={np.sqrt(np.mean((cur - Y) ** 2)):.2f} bias={np.mean(cur - Y):+.1f}")
A = np.vstack([CH, FL, SP, DU, np.ones_like(CH)]).T
(a, f, s, d, b), *_ = np.linalg.lstsq(A, Y, rcond=None)
pred = np.clip(a * CH + f * FL + s * SP + d * DU + b, 0, 99)
print(f"REFIT: {a:.4f}*core +{f:.4f}*field +{s:.4f}*speed +{d:.4f}*dur {b:+.2f}")
print(f"  RMSE={np.sqrt(np.mean((pred - Y) ** 2)):.2f} bias={np.mean(pred - Y):+.1f}")
for cc in [50, 60, 70, 80, 90]:
    n_ = round(a * cc + f * 55 + s * 50 + d * 78 + b)
    c_ = round(0.667 * cc + 0.024 * 55 + 0.038 * 50 + 0.091 * 78 + 25.4)
    print(f"  core {cc} -> new {n_} | current {c_}")
json.dump([list(r) for r in rows], open("_ovr_hitter_pairs.json", "w"))
