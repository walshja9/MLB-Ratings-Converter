"""
Refit all attribute formulas using cached recalibration data + scraped truth.
Reads _recal_cache.json (generated ratings + raw stats) and show_truth.json
(Show 26 ground truth), then runs least-squares regression on each formula.

Outputs new coefficients that can be applied to generate_card.py.

Usage: python refit_formulas.py
"""

import json
import os
import sys
import numpy as np

_venv_site = os.environ.get("MLB_SHOW_VENV_SITE")
if _venv_site and os.path.isdir(_venv_site):
    sys.path.insert(0, _venv_site)

ROOT = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(ROOT, "_recal_cache.json")) as f:
    cache = json.load(f)
with open(os.path.join(ROOT, "show_truth.json")) as f:
    truth = json.load(f)

hitters = cache["hitters"]
h_truth = truth["hitters"]
pitchers = cache["pitchers"]
p_truth = truth["pitchers"]


def trust(pa, threshold=200):
    return min(pa / threshold, 1.0)


def fit_linear(x, y, label):
    """Fit y = m*x + b, print results."""
    x, y = np.array(x, float), np.array(y, float)
    A = np.column_stack([x, np.ones(len(x))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    r = float(np.corrcoef(x.flatten() if x.ndim > 1 else x, y)[0, 1]) if x.ndim == 1 else 0
    return coefs, rmse, len(x)


def fit_multi(X, y, labels):
    """Fit y = X @ coefs + b, print results."""
    X, y = np.array(X, float), np.array(y, float)
    A = np.column_stack([X, np.ones(len(y))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    return coefs, rmse, len(y)


# ==========================================================
# Build hitter rows
# ==========================================================
h_rows = []
for name, h in hitters.items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    bat = h["raw_data"]["batting"]
    sprint = h["raw_data"].get("sprint_speed")
    splits = h["raw_data"].get("splits") or {}
    avg_ev = h["raw_data"].get("avg_ev")
    pa = bat.get("PA", 0) or 0
    if pa < 50:
        continue
    g = max(bat.get("G", 0) or 0, 1)
    h_rows.append({
        "name": name, "pa": pa, "g": g,
        "k_pct": bat.get("K_pct", 25), "bb_pct": bat.get("BB_pct", 8),
        "ba": bat.get("BA", 0.248), "iso": bat.get("ISO", 0.155),
        "hr": bat.get("HR", 0), "sb": bat.get("SB", 0),
        "war": bat.get("WAR", 0) or 0,
        "sprint": sprint, "avg_ev": avg_ev,
        "ba_vr": splits.get("vs_RHP", {}).get("BA"),
        "ba_vl": splits.get("vs_LHP", {}).get("BA"),
        "iso_vr": splits.get("vs_RHP", {}).get("ISO"),
        "iso_vl": splits.get("vs_LHP", {}).get("ISO"),
        "risp_ba": splits.get("risp_ba"),
        "risp_pa": splits.get("risp_pa", 0),
        "truth": t,
    })

print(f"Usable hitters: {len(h_rows)}")
print()
print("=" * 70)
print("  HITTER FORMULA REFITS")
print("=" * 70)

# ============ VISION ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("vision") is None:
        continue
    t = trust(r["pa"])
    eff_k = t * r["k_pct"] + (1 - t) * 25.0
    x.append(eff_k)
    y.append(r["truth"]["vision"])
coefs, rmse, n = fit_linear(x, y, "Vision")
print(f"  Vision:      {coefs[0]:+.3f} * eff_K + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ DISCIPLINE ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("disc") is None:
        continue
    t = trust(r["pa"])
    eff_bb = t * r["bb_pct"] + (1 - t) * 8.0
    x.append(eff_bb)
    y.append(r["truth"]["disc"])
coefs, rmse, n = fit_linear(x, y, "Discipline")
print(f"  Discipline:  {coefs[0]:+.3f} * eff_BB + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ CONTACT R (Statcast) ============
X, y = [], []
for r in h_rows:
    if r["truth"].get("con_r") is None or r["avg_ev"] is None or r["pa"] < 100:
        continue
    t = trust(r["pa"])
    ba_vr = r["ba_vr"] if r["ba_vr"] is not None else r["ba"]
    eff_ba = t * ba_vr + (1 - t) * (t * r["ba"] + (1 - t) * 0.248)
    X.append([eff_ba, r["avg_ev"]])
    y.append(r["truth"]["con_r"])
coefs, rmse, n = fit_multi(X, y, ["BA_vR", "EV"])
print(f"  Contact R:   {coefs[0]:.1f}*BA + {coefs[1]:.2f}*EV + {coefs[2]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ CONTACT R (no EV, season) ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("con_r") is None:
        continue
    t = trust(r["pa"])
    ba_vr = r["ba_vr"] if r["ba_vr"] is not None else r["ba"]
    eff_ba = t * ba_vr + (1 - t) * 0.248
    x.append(eff_ba)
    y.append(r["truth"]["con_r"])
coefs, rmse, n = fit_linear(x, y, "Contact R (BA only)")
print(f"  Contact R (BA only): {coefs[0]:.1f}*BA + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ CONTACT L ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("con_l") is None:
        continue
    t = trust(r["pa"])
    eff_ba = t * r["ba"] + (1 - t) * 0.248
    ba_vl = r["ba_vl"] if r["ba_vl"] is not None else eff_ba
    x.append(ba_vl)
    y.append(r["truth"]["con_l"])
coefs, rmse, n = fit_linear(x, y, "Contact L")
print(f"  Contact L:   {coefs[0]:.1f}*BA_vL + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ POWER R ============
X, y = [], []
for r in h_rows:
    if r["truth"].get("pwr_r") is None:
        continue
    t = trust(r["pa"])
    eff_iso = t * r["iso"] + (1 - t) * 0.155
    hr_rate = t * (r["hr"] / max(r["pa"], 1)) + (1 - t) * 0.030
    X.append([eff_iso, hr_rate])
    y.append(r["truth"]["pwr_r"])
coefs, rmse, n = fit_multi(X, y, ["ISO", "HR_rate"])
print(f"  Power R:     {coefs[0]:.1f}*ISO + {coefs[1]:.1f}*HR_rate + {coefs[2]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ POWER L ============
X, y = [], []
for r in h_rows:
    if r["truth"].get("pwr_l") is None:
        continue
    t = trust(r["pa"])
    eff_iso = t * r["iso"] + (1 - t) * 0.155
    hr_rate = t * (r["hr"] / max(r["pa"], 1)) + (1 - t) * 0.030
    X.append([eff_iso, hr_rate])
    y.append(r["truth"]["pwr_l"])
coefs, rmse, n = fit_multi(X, y, ["ISO", "HR_rate"])
print(f"  Power L:     {coefs[0]:.1f}*ISO + {coefs[1]:.1f}*HR_rate + {coefs[2]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ SPEED (Statcast) ============
X, y = [], []
for r in h_rows:
    if r["truth"].get("speed") is None or r["sprint"] is None:
        continue
    sb162 = min(r["sb"] / r["g"] * 162.0, 60.0)
    X.append([r["sprint"], sb162])
    y.append(r["truth"]["speed"])
coefs, rmse, n = fit_multi(X, y, ["Sprint", "SB162"])
print(f"  Speed:       {coefs[0]:.2f}*Sprint + {coefs[1]:.2f}*SB162 + {coefs[2]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ STEALING (active) ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("stealing") is None:
        continue
    sb162 = min(r["sb"] / r["g"] * 162.0, 60.0)
    if sb162 >= 2:
        x.append(sb162)
        y.append(r["truth"]["stealing"])
coefs, rmse, n = fit_linear(x, y, "Stealing (active)")
print(f"  Stealing:    {coefs[0]:.2f}*SB162 + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ BR AGG (active) ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("br_agg") is None:
        continue
    sb162 = min(r["sb"] / r["g"] * 162.0, 60.0)
    if sb162 >= 2:
        x.append(sb162)
        y.append(r["truth"]["br_agg"])
coefs, rmse, n = fit_linear(x, y, "BR Agg (active)")
print(f"  BR Agg:      {coefs[0]:.2f}*SB162 + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ DURABILITY ============
x, y = [], []
for r in h_rows:
    if r["truth"].get("dur") is None:
        continue
    x.append(r["g"])
    y.append(r["truth"]["dur"])
coefs, rmse, n = fit_linear(x, y, "Durability")
print(f"  Durability:  {coefs[0]:.3f}*G + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ BATTING CLUTCH (Statcast) ============
X, y = [], []
for r in h_rows:
    if r["truth"].get("clutch") is None:
        continue
    if r["risp_ba"] is not None and r["risp_pa"] > 30:
        risp_t = min(r["risp_pa"] / 100, 1.0)
        eff_risp = risp_t * r["risp_ba"] + (1 - risp_t) * r["ba"]
        X.append([r["ba"], r["war"], eff_risp])
        y.append(r["truth"]["clutch"])
coefs, rmse, n = fit_multi(X, y, ["BA", "WAR", "RISP"])
print(f"  Clutch:      {coefs[0]:.1f}*BA + {coefs[1]:.1f}*WAR + {coefs[2]:.1f}*RISP + {coefs[3]:.1f}   RMSE={rmse:.1f}  N={n}")

# ==========================================================
# PITCHER REFITS
# ==========================================================
p_rows = []
for name, p in pitchers.items():
    if name not in p_truth:
        continue
    t = p_truth[name]
    pit = p["raw_data"]["pitching"]
    sc = p["raw_data"].get("statcast") or {}
    ip = pit.get("IP", 0)
    if ip < 10:
        continue
    p_rows.append({
        "name": name, "ip": ip,
        "g": pit.get("G", 0), "gs": pit.get("GS", 0),
        "k9": pit.get("K_per_9", 8), "bb9": pit.get("BB_per_9", 3),
        "hr9": pit.get("HR_per_9", 1.2), "h9": pit.get("H_per_9", 9),
        "k_pct": pit.get("K_pct", 22), "bb_pct": pit.get("BB_pct", 8),
        "whip": pit.get("WHIP", 1.3), "war": pit.get("WAR", 2) or 0,
        "fb_velo": sc.get("avg_fb_velo") or pit.get("FB_velo") or 93,
        "vs_lhb_ba": (sc.get("vs_LHB") or {}).get("BA"),
        "vs_rhb_ba": (sc.get("vs_RHB") or {}).get("BA"),
        "vs_lhb_kpct": (sc.get("vs_LHB") or {}).get("K_pct"),
        "vs_rhb_kpct": (sc.get("vs_RHB") or {}).get("K_pct"),
        "truth": t,
    })

print(f"\nUsable pitchers: {len(p_rows)}")
print()
print("=" * 70)
print("  PITCHER FORMULA REFITS")
print("=" * 70)

# ============ VELOCITY ============
x, y = [], []
for r in p_rows:
    if r["truth"].get("velo") is None:
        continue
    x.append(r["fb_velo"])
    y.append(r["truth"]["velo"])
coefs, rmse, n = fit_linear(x, y, "Velocity")
print(f"  Velocity:    {coefs[0]:.2f}*FBvelo + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ CONTROL ============
X, y = [], []
for r in p_rows:
    if r["truth"].get("ctrl") is None:
        continue
    X.append([r["bb9"], r["whip"]])
    y.append(r["truth"]["ctrl"])
coefs, rmse, n = fit_multi(X, y, ["BB9", "WHIP"])
print(f"  Control:     {coefs[0]:.2f}*BB9 + {coefs[1]:.1f}*WHIP + {coefs[2]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ HR/9 ============
x, y = [], []
for r in p_rows:
    if r["truth"].get("hr9") is None:
        continue
    x.append(r["hr9"])
    y.append(r["truth"]["hr9"])
coefs, rmse, n = fit_linear(x, y, "HR/9")
print(f"  HR/9:        {coefs[0]:.2f}*HR9 + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ H/9 SPLITS ============
for side, ba_key, t_key in [("L", "vs_lhb_ba", "h9_l"), ("R", "vs_rhb_ba", "h9_r")]:
    x, y = [], []
    for r in p_rows:
        ba = r[ba_key]
        if r["truth"].get(t_key) is None or ba is None:
            continue
        x.append(ba)
        y.append(r["truth"][t_key])
    if len(x) < 5:
        continue
    coefs, rmse, n = fit_linear(x, y, f"H/9 vs {side}")
    print(f"  H/9 vs {side}:   {coefs[0]:.1f}*BA + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ K/9 SPLITS ============
for side, k_key, t_key in [("L", "vs_lhb_kpct", "k9_l"), ("R", "vs_rhb_kpct", "k9_r")]:
    x, y = [], []
    for r in p_rows:
        kpct = r[k_key]
        if r["truth"].get(t_key) is None or kpct is None:
            continue
        x.append(kpct)
        y.append(r["truth"][t_key])
    if len(x) < 5:
        continue
    coefs, rmse, n = fit_linear(x, y, f"K/9 vs {side}")
    print(f"  K/9 vs {side}:   {coefs[0]:.2f}*K%% + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ STAMINA (SP vs RP) ============
for label, g_key, filter_fn in [
    ("SP", "gs", lambda r: r["gs"] > 0),
    ("RP", "g", lambda r: r["gs"] == 0),
]:
    x, y = [], []
    for r in p_rows:
        if r["truth"].get("stam") is None or not filter_fn(r):
            continue
        x.append(r[g_key])
        y.append(r["truth"]["stam"])
    if len(x) < 3:
        continue
    coefs, rmse, n = fit_linear(x, y, f"Stamina {label}")
    print(f"  Stamina {label}: {coefs[0]:.3f}*{g_key.upper()} + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

# ============ PITCHING CLUTCH ============
x, y = [], []
for r in p_rows:
    if r["truth"].get("clutch") is None:
        continue
    x.append(r["war"])
    y.append(r["truth"]["clutch"])
coefs, rmse, n = fit_linear(x, y, "Pit Clutch")
print(f"  Pit Clutch:  {coefs[0]:.2f}*WAR + {coefs[1]:.1f}   RMSE={rmse:.1f}  N={n}")

print()
print("=" * 70)
print("  SUMMARY: Old vs New Coefficients")
print("=" * 70)
print("  Apply new coefficients to generate_card.py to reduce RMSE.")
print("  Run recalibrate_all.py --skip-pull after applying to verify.")
