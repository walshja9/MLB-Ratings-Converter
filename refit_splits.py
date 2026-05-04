"""Refit Contact L, Power L, Power R, Contact R using proper split data."""
import json, sys, os, numpy as np, warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_recal_cache.json")) as f:
    cache = json.load(f)
with open(os.path.join(ROOT, "show_truth.json")) as f:
    truth = json.load(f)

h_truth = truth["hitters"]


def trust(pa, threshold=200):
    return min(pa / threshold, 1.0)


def fit(x, y):
    x, y = np.array(x, float), np.array(y, float)
    A = np.column_stack([x, np.ones(len(x))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    r = float(np.corrcoef(x, y)[0, 1])
    return coefs, rmse, r, pred


def fit_multi(X, y):
    X, y = np.array(X, float), np.array(y, float)
    A = np.column_stack([X, np.ones(len(y))])
    coefs, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coefs
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    return coefs, rmse, pred


# ============================================================
# CONTACT R: split BA vs RHP
# ============================================================
print("=" * 60)
print("  CONTACT R: SPLIT BA vs RHP")
print("=" * 60)

x, y = [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("con_r") is None:
        continue
    splits = h["raw_data"].get("splits") or {}
    rhp = splits.get("vs_RHP", {})
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)
    ba_vr = rhp.get("BA")
    pa_vr = rhp.get("PA", 0)
    eff_ba = trust(pa) * bat.get("BA", 0.248) + (1 - trust(pa)) * 0.248
    if ba_vr is not None and pa_vr > 30:
        tr = min(pa_vr / 150, 1.0)
        contact_ba = tr * ba_vr + (1 - tr) * eff_ba
    else:
        contact_ba = eff_ba
    x.append(contact_ba)
    y.append(t["con_r"])
coefs, rmse, r, _ = fit(x, y)
print(f"  BA_vR: {coefs[0]:.1f}*BA + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f} N={len(x)}")
print(f"  (Current: 268*BA + 4.8, RMSE=6.9)")


# ============================================================
# CONTACT L: split BA vs LHP (mirror of Contact R)
# ============================================================
print("\n" + "=" * 60)
print("  CONTACT L: SPLIT BA vs LHP")
print("=" * 60)

x, y, names = [], [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("con_l") is None:
        continue
    splits = h["raw_data"].get("splits") or {}
    lhp = splits.get("vs_LHP", {})
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)
    ba_vl = lhp.get("BA")
    pa_vl = lhp.get("PA", 0)
    eff_ba = trust(pa) * bat.get("BA", 0.248) + (1 - trust(pa)) * 0.248
    if ba_vl is not None and pa_vl > 30:
        tl = min(pa_vl / 120, 1.0)
        contact_ba = tl * ba_vl + (1 - tl) * eff_ba
    else:
        contact_ba = eff_ba
    x.append(contact_ba)
    y.append(t["con_l"])
    names.append(name)
coefs, rmse, r, pred = fit(x, y)
print(f"  BA_vL: {coefs[0]:.1f}*BA + {coefs[1]:.1f}   RMSE={rmse:.1f} r={r:.3f} N={len(x)}")
print(f"  (Current: 212.7*BA_vL + 18.7, RMSE=10.4)")

# Worst misses
print("\n  Worst misses:")
for i in sorted(range(len(names)), key=lambda i: -abs(pred[i] - y[i]))[:8]:
    err = pred[i] - y[i]
    h = cache["hitters"][names[i]]
    lhp = (h["raw_data"].get("splits") or {}).get("vs_LHP", {})
    print(f"    {names[i]:25s} gen={pred[i]:5.0f} show={y[i]:3.0f} err={err:+5.0f} BA_vL={lhp.get('BA', '?')} PA_vL={lhp.get('PA', '?')}")


# ============================================================
# POWER R: split ISO vs RHP + HR rate
# ============================================================
print("\n" + "=" * 60)
print("  POWER R: SPLIT ISO vs RHP + HR RATE")
print("=" * 60)

X, y = [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("pwr_r") is None:
        continue
    splits = h["raw_data"].get("splits") or {}
    rhp = splits.get("vs_RHP", {})
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)

    t_pa = trust(pa)
    eff_iso = t_pa * bat.get("ISO", 0.155) + (1 - t_pa) * 0.155
    hr_rate = t_pa * (bat.get("HR", 0) / max(pa, 1)) + (1 - t_pa) * 0.030

    iso_vr = rhp.get("ISO")
    pa_vr = rhp.get("PA", 0)
    if iso_vr is not None and pa_vr > 30:
        tr = min(pa_vr / 200, 1.0)
        iso_blend = tr * iso_vr + (1 - tr) * eff_iso
    else:
        iso_blend = eff_iso

    X.append([iso_blend, hr_rate])
    y.append(t["pwr_r"])

coefs, rmse, _ = fit_multi(X, y)
print(f"  ISO_vR + HR: {coefs[0]:.1f}*ISO + {coefs[1]:.1f}*HR + {coefs[2]:.1f}   RMSE={rmse:.1f} N={len(y)}")

# Compare with overall ISO
X2, y2 = [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("pwr_r") is None:
        continue
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)
    t_pa = trust(pa)
    eff_iso = t_pa * bat.get("ISO", 0.155) + (1 - t_pa) * 0.155
    hr_rate = t_pa * (bat.get("HR", 0) / max(pa, 1)) + (1 - t_pa) * 0.030
    X2.append([eff_iso, hr_rate])
    y2.append(t["pwr_r"])
coefs2, rmse2, _ = fit_multi(X2, y2)
print(f"  Overall ISO + HR: {coefs2[0]:.1f}*ISO + {coefs2[1]:.1f}*HR + {coefs2[2]:.1f}   RMSE={rmse2:.1f} N={len(y2)}")
print(f"  (Current: 6.3*ISO + 623.8*HR + 49.3, RMSE=8.6)")


# ============================================================
# POWER L: split ISO vs LHP + HR rate
# ============================================================
print("\n" + "=" * 60)
print("  POWER L: SPLIT ISO vs LHP + HR RATE")
print("=" * 60)

X, y, names = [], [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("pwr_l") is None:
        continue
    splits = h["raw_data"].get("splits") or {}
    lhp = splits.get("vs_LHP", {})
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)

    t_pa = trust(pa)
    eff_iso = t_pa * bat.get("ISO", 0.155) + (1 - t_pa) * 0.155
    hr_rate = t_pa * (bat.get("HR", 0) / max(pa, 1)) + (1 - t_pa) * 0.030

    iso_vl = lhp.get("ISO")
    pa_vl = lhp.get("PA", 0)
    if iso_vl is not None and pa_vl > 30:
        tl = min(pa_vl / 120, 1.0)
        iso_blend = tl * iso_vl + (1 - tl) * eff_iso
    else:
        iso_blend = eff_iso

    X.append([iso_blend, hr_rate])
    y.append(t["pwr_l"])
    names.append(name)

coefs, rmse, pred = fit_multi(X, y)
print(f"  ISO_vL + HR: {coefs[0]:.1f}*ISO + {coefs[1]:.1f}*HR + {coefs[2]:.1f}   RMSE={rmse:.1f} N={len(y)}")

# Compare with overall
X2, y2 = [], []
for name, h in cache["hitters"].items():
    if name not in h_truth:
        continue
    t = h_truth[name]
    if t.get("pwr_l") is None:
        continue
    bat = h["raw_data"]["batting"]
    pa = bat.get("PA", 0)
    t_pa = trust(pa)
    eff_iso = t_pa * bat.get("ISO", 0.155) + (1 - t_pa) * 0.155
    hr_rate = t_pa * (bat.get("HR", 0) / max(pa, 1)) + (1 - t_pa) * 0.030
    X2.append([eff_iso, hr_rate])
    y2.append(t["pwr_l"])
coefs2, rmse2, _ = fit_multi(X2, y2)
print(f"  Overall ISO + HR: {coefs2[0]:.1f}*ISO + {coefs2[1]:.1f}*HR + {coefs2[2]:.1f}   RMSE={rmse2:.1f} N={len(y2)}")
print(f"  (Current: -60.7*ISO + 929.9*HR + 43.8, RMSE=10.1)")

# Worst misses
print("\n  Worst misses:")
for i in sorted(range(len(names)), key=lambda i: -abs(pred[i] - y[i]))[:8]:
    err = pred[i] - y[i]
    h = cache["hitters"][names[i]]
    lhp = (h["raw_data"].get("splits") or {}).get("vs_LHP", {})
    print(f"    {names[i]:25s} gen={pred[i]:5.0f} show={y[i]:3.0f} err={err:+5.0f} ISO_vL={lhp.get('ISO', '?')} PA_vL={lhp.get('PA', '?')}")
