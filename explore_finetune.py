"""Fine-tune remaining hitter formulas: Contact L, Stealing, Clutch, BR Agg, Fielding."""
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

h_truth = truth["hitters"]

# Also pull barrel data for the full truth set
from pybaseball import statcast_batter_exitvelo_barrels
print("Pulling barrel stats...")
bb = statcast_batter_exitvelo_barrels(2025, minBBE=30)

def normalize_name(name):
    parts = name.split(", ")
    if len(parts) == 2:
        return (parts[1] + " " + parts[0]).replace(" Jr.", "").replace(" Sr.", "").strip()
    return name

bb["norm_name"] = bb["last_name, first_name"].apply(normalize_name)

# Build barrel lookup
barrel_lookup = {}
for _, row in bb.iterrows():
    name = row["norm_name"]
    barrel_lookup[name] = {
        "brl_pct": row["brl_percent"],
        "brl_pa": row["brl_pa"],
        "ev95pct": row["ev95percent"],
        "avg_ev": row["avg_hit_speed"],
        "max_ev": row["max_hit_speed"],
    }
    # Also match with Jr./Sr.
    for tname in h_truth:
        clean = tname.replace(" Jr.", "").replace(" Sr.", "").strip()
        if name == clean and tname not in barrel_lookup:
            barrel_lookup[tname] = barrel_lookup[name]

print(f"Barrel data for {len(barrel_lookup)} hitters")


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


# Build full hitter rows from truth + barrel data (not just cached 44)
rows = []
for name, t in h_truth.items():
    bl = barrel_lookup.get(name)
    if bl is None:
        continue
    if t.get("con_r") is None:
        continue
    rows.append({"name": name, "truth": t, "barrel": bl})

print(f"Matched hitters with truth + barrel data: {len(rows)}\n")


# ============================================================
# CONTACT L: Currently 10.4 RMSE using BA_vL
# Try: avg_ev, barrel data, overall BA
# ============================================================
print("=" * 60)
print("  CONTACT L IMPROVEMENTS")
print("=" * 60)

# Current baseline: 212.7 * BA_vL + 18.7 (at N=44, RMSE=10.4)
# Problem: BA_vL splits are noisy. Can we do better with barrel/EV?

# Contact L vs avg EV
x, y = [], []
for r in rows:
    y.append(r["truth"]["con_l"])
    x.append(r["barrel"]["avg_ev"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  avg_ev alone:     {coefs[0]:+.2f}*avgEV + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f} N={len(x)}")

# Contact L vs barrel%
x, y = [], []
for r in rows:
    y.append(r["truth"]["con_l"])
    x.append(r["barrel"]["brl_pct"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  barrel% alone:    {coefs[0]:+.2f}*brl%% + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")

# Contact L vs hard-hit%
x, y = [], []
for r in rows:
    y.append(r["truth"]["con_l"])
    x.append(r["barrel"]["ev95pct"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  hard-hit%% alone: {coefs[0]:+.2f}*ev95%% + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")


# ============================================================
# STEALING: Currently 11.0 RMSE using SB/162
# The Show uses scouting — try sprint speed as additional signal
# ============================================================
print("\n" + "=" * 60)
print("  STEALING IMPROVEMENTS")
print("=" * 60)

# Pull sprint speed data
from pybaseball import statcast_sprint_speed
print("Pulling sprint speed...")
ss = statcast_sprint_speed(2025)
sprint_lookup = {}
for _, row in ss.iterrows():
    name_raw = row.get("last_name, first_name", "")
    parts = name_raw.split(", ")
    if len(parts) == 2:
        clean = parts[1] + " " + parts[0]
        sprint_lookup[clean] = float(row["sprint_speed"])
        # Also try with Jr/Sr
        for tname in h_truth:
            c = tname.replace(" Jr.", "").replace(" Sr.", "").strip()
            if clean == c:
                sprint_lookup[tname] = sprint_lookup[clean]

print(f"Sprint data for {len(sprint_lookup)} players")

# Active stealers (SB/162 >= 2) with sprint speed
# Current: 1.73 * SB/162 + 18.4
steal_rows = []
for name, t in h_truth.items():
    if t.get("stealing") is None:
        continue
    sprint = sprint_lookup.get(name)
    if sprint is None:
        continue
    # Estimate SB/162 from cache if available, else from truth context
    # Use Show's speed as proxy for sprint-based SB estimate
    steal_rows.append({
        "name": name,
        "sprint": sprint,
        "show_steal": t["stealing"],
        "show_speed": t.get("speed", 50),
        "show_br_agg": t.get("br_agg", 50),
    })

print(f"Players with sprint + stealing truth: {len(steal_rows)}")

# Stealing from sprint speed alone
x, y = [], []
for r in steal_rows:
    x.append(r["sprint"])
    y.append(r["show_steal"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  sprint alone:       {coefs[0]:+.2f}*sprint + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f} N={len(x)}")

# Stealing from Show speed truth (proxy for what sprint-based speed rating would be)
x, y = [], []
for r in steal_rows:
    x.append(r["show_speed"])
    y.append(r["show_steal"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  Show speed truth:   {coefs[0]:+.2f}*speed + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")

# Sprint + speed combined for stealing
X, y = [], []
for r in steal_rows:
    X.append([r["sprint"], r["show_speed"]])
    y.append(r["show_steal"])
coefs, rmse, pred = fit_multi(X, y)
print(f"  sprint + speed:     {coefs[0]:+.2f}*sprint + {coefs[1]:+.2f}*speed + {coefs[2]:.1f}  RMSE={rmse:.1f}")


# ============================================================
# BR AGGRESSIVENESS: Currently 12.9 RMSE
# ============================================================
print("\n" + "=" * 60)
print("  BR AGGRESSIVENESS IMPROVEMENTS")
print("=" * 60)

# BR Agg from sprint speed
x, y = [], []
for r in steal_rows:
    if r["show_br_agg"] is None:
        continue
    x.append(r["sprint"])
    y.append(r["show_br_agg"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  sprint alone:       {coefs[0]:+.2f}*sprint + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f} N={len(x)}")

# BR Agg from Show speed
x, y = [], []
for r in steal_rows:
    if r["show_br_agg"] is None:
        continue
    x.append(r["show_speed"])
    y.append(r["show_br_agg"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  Show speed truth:   {coefs[0]:+.2f}*speed + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")


# ============================================================
# BATTING CLUTCH: Currently 11.2 RMSE
# Try OPS, wOBA, or other aggregate stats
# ============================================================
print("\n" + "=" * 60)
print("  BATTING CLUTCH IMPROVEMENTS")
print("=" * 60)

# Clutch is reputation-based. But at N=233 we might find a signal.
# Try: OVR (is clutch just a proxy for overall goodness?)
x, y = [], []
for name, t in h_truth.items():
    if t.get("clutch") is None or t.get("ovr") is None:
        continue
    x.append(t["ovr"])
    y.append(t["clutch"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  OVR alone (N={len(x)}):  {coefs[0]:+.2f}*OVR + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")

# Clutch from Show hitting overall
x, y = [], []
for name, t in h_truth.items():
    if t.get("clutch") is None:
        continue
    # Compute hitting avg from truth
    hit_attrs = [t.get(k, 0) for k in ["con_r", "con_l", "pwr_r", "pwr_l", "vision", "disc"]]
    if all(v is not None for v in hit_attrs):
        x.append(np.mean(hit_attrs))
        y.append(t["clutch"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  core_hitting (N={len(x)}): {coefs[0]:+.2f}*hit + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")


# ============================================================
# FIELDING FOR CATCHERS: Explore what drives catcher fielding
# ============================================================
print("\n" + "=" * 60)
print("  CATCHER FIELDING EXPLORATION")
print("=" * 60)

catchers = {name: t for name, t in h_truth.items() if t.get("blocking") is not None}
print(f"Catchers with full truth: {len(catchers)}")

# What's the distribution of catcher fielding in Show?
fld_vals = [t["fielding"] for t in catchers.values()]
print(f"  Fielding range: {min(fld_vals)}-{max(fld_vals)}, mean={np.mean(fld_vals):.0f}, std={np.std(fld_vals):.0f}")

# Catcher fielding vs OVR
x, y = [], []
for t in catchers.values():
    x.append(t.get("ovr", 70))
    y.append(t["fielding"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  Catcher fielding vs OVR: {coefs[0]:+.2f}*OVR + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")

# Catcher fielding vs blocking
x, y = [], []
for t in catchers.values():
    x.append(t["blocking"])
    y.append(t["fielding"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  Catcher fielding vs blocking: {coefs[0]:+.2f}*BLK + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")

# Catcher fielding vs arm_str
x, y = [], []
for t in catchers.values():
    x.append(t.get("arm_str", 70))
    y.append(t["fielding"])
coefs, rmse, rv, _ = fit(x, y)
print(f"  Catcher fielding vs arm_str: {coefs[0]:+.2f}*ARM + {coefs[1]:.1f}  RMSE={rmse:.1f} r={rv:.3f}")
