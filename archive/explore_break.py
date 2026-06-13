"""Explore Break formula using Statcast pitch movement data."""
import json, sys, os, numpy as np, warnings
warnings.filterwarnings("ignore")

_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_card import pull_pitcher_statcast, lookup_mlbam_id

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_recal_cache.json")) as f:
    cache = json.load(f)
with open(os.path.join(ROOT, "show_truth.json")) as f:
    truth = json.load(f)

p_truth = truth["pitchers"]

# Pull fresh Statcast arsenal data for each cached pitcher
rows = []
for name, p in cache["pitchers"].items():
    if name not in p_truth:
        continue
    show_brk = p_truth[name].get("brk")
    if show_brk is None:
        continue

    pit = p["raw_data"]["pitching"]
    sc_cached = p["raw_data"].get("statcast") or {}

    # We need the arsenal data — pull it fresh
    print(f"Pulling arsenal for {name}...")
    mlbam_id = lookup_mlbam_id(name, 2025)
    if not mlbam_id:
        print(f"  No MLBAM ID, skipping")
        continue

    sc = pull_pitcher_statcast(mlbam_id, 2025)
    arsenal = sc.get("arsenal", [])
    if not arsenal:
        print(f"  No arsenal data, skipping")
        continue

    # Compute break metrics
    total_break_all = []
    h_breaks = []
    v_breaks = []
    weighted_break = 0
    total_usage = 0
    max_break = 0
    num_high_break = 0  # pitches with >15 inches total break
    offspeed_break = []

    for pitch in arsenal:
        tb = pitch.get("total_break_inches")
        hb = pitch.get("h_break")
        vb = pitch.get("v_break")
        usage = pitch.get("usage", 0)
        code = pitch.get("code", "")

        if tb is not None:
            total_break_all.append(tb)
            weighted_break += tb * usage
            total_usage += usage
            max_break = max(max_break, tb)
            if tb > 15:
                num_high_break += 1
            if code not in ("FF", "SI"):
                offspeed_break.append(tb)

        if hb is not None:
            h_breaks.append(abs(hb))
        if vb is not None:
            v_breaks.append(abs(vb))

    if not total_break_all:
        print(f"  No break measurements")
        continue

    avg_break = np.mean(total_break_all)
    avg_weighted_break = weighted_break / total_usage if total_usage > 0 else 0
    avg_offspeed_break = np.mean(offspeed_break) if offspeed_break else 0
    num_pitches = len([p for p in arsenal if p["usage"] > 5])
    offspeed_usage = sum(p["usage"] for p in arsenal if p["code"] not in ("FF",))

    rows.append({
        "name": name,
        "show_brk": show_brk,
        "avg_break": avg_break,
        "weighted_break": avg_weighted_break,
        "max_break": max_break,
        "avg_offspeed_break": avg_offspeed_break,
        "num_pitches": num_pitches,
        "num_high_break": num_high_break,
        "offspeed_usage": offspeed_usage,
        "avg_h_break": np.mean(h_breaks) if h_breaks else 0,
        "avg_v_break": np.mean(v_breaks) if v_breaks else 0,
    })

    print(f"  avg_break={avg_break:.1f} weighted={avg_weighted_break:.1f} max={max_break:.1f} "
          f"offspeed_break={avg_offspeed_break:.1f} pitches={num_pitches} show={show_brk}")


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


print(f"\n{'='*60}")
print(f"  BREAK FORMULA CANDIDATES (N={len(rows)})")
print(f"{'='*60}\n")

# Single-feature candidates
for label, get_x in [
    ("avg_break (all pitches)", lambda r: r["avg_break"]),
    ("weighted_break (usage-weighted)", lambda r: r["weighted_break"]),
    ("max_break", lambda r: r["max_break"]),
    ("avg_offspeed_break", lambda r: r["avg_offspeed_break"]),
    ("num_pitches (>5% usage)", lambda r: r["num_pitches"]),
    ("offspeed_usage%", lambda r: r["offspeed_usage"]),
    ("num_high_break (>15in)", lambda r: r["num_high_break"]),
    ("avg_h_break", lambda r: r["avg_h_break"]),
    ("avg_v_break", lambda r: r["avg_v_break"]),
]:
    x = [get_x(r) for r in rows]
    y = [r["show_brk"] for r in rows]
    coefs, rmse, r, _ = fit(x, y)
    print(f"  {label:40s}: {coefs[0]:+.2f}*X + {coefs[1]:.1f}  RMSE={rmse:.1f} r={r:.3f}")

# Multi-feature candidates
print()
for label, get_X in [
    ("weighted_break + num_pitches", lambda r: [r["weighted_break"], r["num_pitches"]]),
    ("avg_offspeed_break + offspeed_usage", lambda r: [r["avg_offspeed_break"], r["offspeed_usage"]]),
    ("max_break + num_pitches + offspeed_usage", lambda r: [r["max_break"], r["num_pitches"], r["offspeed_usage"]]),
    ("weighted_break + offspeed_usage", lambda r: [r["weighted_break"], r["offspeed_usage"]]),
    ("avg_break + num_pitches + offspeed_usage", lambda r: [r["avg_break"], r["num_pitches"], r["offspeed_usage"]]),
]:
    X = [get_X(r) for r in rows]
    y = [r["show_brk"] for r in rows]
    coefs, rmse, pred = fit_multi(X, y)
    feats = label.split(" + ")
    terms = " + ".join(f"{coefs[i]:+.2f}*{feats[i]}" for i in range(len(feats)))
    print(f"  {label:50s}: {terms} + {coefs[-1]:.1f}  RMSE={rmse:.1f}")

# Per-player detail for best model
print(f"\n{'='*60}")
print(f"  BEST MODEL: PER-PLAYER DETAIL")
print(f"{'='*60}\n")

# Use whichever model has best RMSE
X = [[r["weighted_break"], r["offspeed_usage"]] for r in rows]
y = [r["show_brk"] for r in rows]
coefs, rmse, pred = fit_multi(X, y)
print(f"  weighted_break + offspeed_usage: RMSE={rmse:.1f}")
print(f"  {coefs[0]:+.2f}*wt_break + {coefs[1]:+.2f}*offspd% + {coefs[2]:.1f}\n")

for r, p in sorted(zip(rows, pred), key=lambda x: -abs(x[1] - x[0]["show_brk"])):
    err = p - r["show_brk"]
    flag = " ***" if abs(err) > 10 else ""
    print(f"  {r['name']:25s} gen={p:5.1f} show={r['show_brk']:3d} err={err:+5.1f} "
          f"wt_brk={r['weighted_break']:5.1f} offspd={r['offspeed_usage']:5.1f}{flag}")
