"""Refit pitcher OVR across the full talent range.

Reuses the already-pulled top arms in _recal_cache.json and pulls the sub-80
MLB arms (truth OVR 60-82) the team scrape added, then fits OVR ~ pitching.
"""

import json
import numpy as np
from generate_card import (pull_all_pitcher_data, calculate_pitcher_ratings,
                           calculate_pitcher_overalls)

YEAR = 2025
truth = json.load(open("show_truth.json"))["pitchers"]
cache = json.load(open("_recal_cache.json"))["pitchers"]

pairs = []  # (pitching_overall, truth_ovr)
for n, c in cache.items():
    if n in truth and truth[n].get("ovr", 0) > 0:
        pairs.append((c["overalls"]["pitching"], truth[n]["ovr"]))

have = set(cache)
targets = [n for n, v in truth.items() if 60 <= v.get("ovr", 0) < 82 and n not in have]
print(f"cache pairs: {len(pairs)} | new sub-82 targets to pull: {len(targets)}", flush=True)

pulled = 0
for i, n in enumerate(targets):
    try:
        d = pull_all_pitcher_data(n, YEAR)
        if d is None:
            continue
        r = calculate_pitcher_ratings(d, "season")
        o = calculate_pitcher_overalls(r)
        pairs.append((o["pitching"], truth[n]["ovr"]))
        pulled += 1
    except Exception:
        continue
    if (i + 1) % 40 == 0:
        print(f"  {i + 1}/{len(targets)} pulled {pulled}", flush=True)

P = np.array([p[0] for p in pairs], float)
Y = np.array([p[1] for p in pairs], float)
print(f"\ntotal pairs: {len(pairs)} (pulled {pulled} new)")
print(f"pitching cat range {P.min():.0f}-{P.max():.0f}, OVR range {Y.min():.0f}-{Y.max():.0f}")

A = np.vstack([P, np.ones_like(P)]).T
(a, b), *_ = np.linalg.lstsq(A, Y, rcond=None)
pred = np.clip(a * P + b, 0, 99)
print(f"FULL-RANGE refit: OVR = {a:.4f}*pitch {b:+.2f}  RMSE={np.sqrt(np.mean((pred - Y) ** 2)):.2f} bias={np.mean(pred - Y):+.1f}")
# current formula for comparison
cur = np.clip(0.990 * P + 8.4, 0, 99)
print(f"current 0.990*p+8.4: RMSE={np.sqrt(np.mean((cur - Y) ** 2)):.2f} bias={np.mean(cur - Y):+.1f}")
for cat in [55, 60, 68, 72, 80, 86]:
    print(f"  cat {cat} -> new {round(a * cat + b)} | current {round(0.990 * cat + 8.4)}")
json.dump([list(p) for p in pairs], open("_ovr_pitcher_pairs.json", "w"))
