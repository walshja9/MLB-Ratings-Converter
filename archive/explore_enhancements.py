"""Explore K/9 fixes, barrel% for power, and blocking data."""
import json, sys, os, numpy as np, warnings
warnings.filterwarnings("ignore")

_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_recal_cache.json")) as f:
    cache = json.load(f)
with open(os.path.join(ROOT, "show_truth.json")) as f:
    truth = json.load(f)

p_truth = truth["pitchers"]
h_truth = truth["hitters"]


def fit(x, y):
    x, y = np.array(x, float), np.array(y, float)
    A = np.column_stack([x, np.ones(len(x))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    r = float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else 0
    return coefs, rmse, r, pred


def fit_multi(X, y):
    X, y = np.array(X, float), np.array(y, float)
    A = np.column_stack([X, np.ones(len(y))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    return coefs, rmse, pred


# ============================================================
# K/9: FIT WITHOUT DAMPENING (let regression handle range)
# ============================================================
print("=" * 60)
print("  K/9 SPLIT REFIT (NO DAMPENING)")
print("=" * 60)

for side, t_key in [("L", "k9_l"), ("R", "k9_r")]:
    x, y, names = [], [], []
    for name, p in cache["pitchers"].items():
        if name not in p_truth:
            continue
        sc = p["raw_data"].get("statcast") or {}
        split = sc.get("vs_LHB" if side == "L" else "vs_RHB", {})
        kpct = split.get("K_pct")
        show_val = p_truth[name].get(t_key)
        if kpct is None or show_val is None or split.get("PA", 0) < 30:
            continue
        x.append(kpct)
        y.append(show_val)
        names.append(name)

    coefs, rmse, r, pred = fit(x, y)
    bias = float(np.mean(np.array(pred) - np.array(y)))
    print(f"\n  K/9 vs {side}: {coefs[0]:.2f}*K% + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f} bias={bias:+.1f} N={len(x)}")

    # Show worst misses
    errs = [(names[i], pred[i], y[i], pred[i] - y[i]) for i in range(len(names))]
    for n, p, s, e in sorted(errs, key=lambda t: -abs(t[3]))[:5]:
        print(f"    {n:25s} gen={p:.0f} show={s:.0f} err={e:+.0f}")


# ============================================================
# BARREL% / HARD-HIT% FOR POWER
# ============================================================
print("\n" + "=" * 60)
print("  BARREL% AND HARD-HIT% FOR POWER")
print("=" * 60)

from pybaseball import statcast_batter_exitvelo_barrels
bb = statcast_batter_exitvelo_barrels(2025, minBBE=50)


def normalize(name):
    parts = name.split(", ")
    if len(parts) == 2:
        return (parts[1] + " " + parts[0]).replace(" Jr.", "").replace(" Sr.", "").strip()
    return name


bb["norm_name"] = bb["last_name, first_name"].apply(normalize)

rows = []
for _, row in bb.iterrows():
    name = row["norm_name"]
    t = h_truth.get(name)
    if t is None:
        for tname in h_truth:
            clean = tname.replace(" Jr.", "").replace(" Sr.", "").strip()
            if name == clean:
                t = h_truth[tname]
                name = tname
                break
    if t is None or t.get("pwr_r") is None:
        continue
    rows.append({
        "name": name,
        "brl_pct": row["brl_percent"],
        "brl_pa": row["brl_pa"],
        "ev95pct": row["ev95percent"],
        "avg_ev": row["avg_hit_speed"],
        "max_ev": row["max_hit_speed"],
        "t_pwr_r": t["pwr_r"],
        "t_pwr_l": t["pwr_l"],
        "t_con_r": t.get("con_r"),
    })

print(f"\n  Matched hitters with barrel data: {len(rows)}")

# Power R variants
for label, get_x in [
    ("barrel% alone", lambda r: [r["brl_pct"]]),
    ("hard-hit% alone", lambda r: [r["ev95pct"]]),
    ("max EV alone", lambda r: [r["max_ev"]]),
    ("barrel/PA alone", lambda r: [r["brl_pa"]]),
]:
    x = [get_x(r)[0] for r in rows]
    y = [r["t_pwr_r"] for r in rows]
    coefs, rmse, r, _ = fit(x, y)
    print(f"  Pwr R ({label:20s}): {coefs[0]:+.2f}*X + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f}")

# Multi-feature Power R
for label, get_X in [
    ("brl% + maxEV", lambda r: [r["brl_pct"], r["max_ev"]]),
    ("brl% + ev95%", lambda r: [r["brl_pct"], r["ev95pct"]]),
    ("brl/PA + maxEV", lambda r: [r["brl_pa"], r["max_ev"]]),
]:
    X = [get_X(r) for r in rows]
    y = [r["t_pwr_r"] for r in rows]
    coefs, rmse, _ = fit_multi(X, y)
    labels = label.split(" + ")
    parts = " + ".join(f"{coefs[i]:+.2f}*{labels[i]}" for i in range(len(labels)))
    print(f"  Pwr R ({label:20s}): {parts} + {coefs[-1]:.1f}   RMSE={rmse:.1f}")

# Power L
print()
for label, get_x in [
    ("barrel% alone", lambda r: [r["brl_pct"]]),
    ("barrel/PA alone", lambda r: [r["brl_pa"]]),
]:
    x = [get_x(r)[0] for r in rows]
    y = [r["t_pwr_l"] for r in rows]
    coefs, rmse, r, _ = fit(x, y)
    print(f"  Pwr L ({label:20s}): {coefs[0]:+.2f}*X + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f}")


# ============================================================
# BLOCKING: try scraping Statcast blocking directly
# ============================================================
print("\n" + "=" * 60)
print("  BLOCKING FORMULA EXPLORATION")
print("=" * 60)

# We have blocking truth from show_truth.json for catchers
# Try correlating with available stats from the cache
catchers_with_block = {}
for name, h in h_truth.items():
    if "blocking" in h and h["blocking"] > 0:
        catchers_with_block[name] = h

print(f"\n  Catchers with blocking truth: {len(catchers_with_block)}")

# Check what stats we have for catchers in cache
block_rows = []
for name, h in cache["hitters"].items():
    if name not in catchers_with_block:
        continue
    t = catchers_with_block[name]
    bat = h["raw_data"]["batting"]
    oaa = h["raw_data"].get("fielding_oaa", {})

    # Try: games played (more games = better blocking?), assists, errors
    block_rows.append({
        "name": name,
        "g": bat.get("G", 0),
        "pa": bat.get("PA", 0),
        "t_blocking": t["blocking"],
        "t_fielding": t["fielding"],
    })

print(f"  Catchers with cached stats + blocking truth: {len(block_rows)}")

# Simple: games -> blocking
if block_rows:
    x = [r["g"] for r in block_rows]
    y = [r["t_blocking"] for r in block_rows]
    coefs, rmse, r, _ = fit(x, y)
    print(f"  Blocking (G alone): {coefs[0]:.3f}*G + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f} N={len(x)}")

    # Fielding truth -> blocking truth (are they correlated in Show?)
    x = [r["t_fielding"] for r in block_rows]
    y = [r["t_blocking"] for r in block_rows]
    coefs, rmse, r, _ = fit(x, y)
    print(f"  Blocking (Show fielding): {coefs[0]:.3f}*F + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f}")
