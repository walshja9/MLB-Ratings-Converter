"""Pull Statcast batted ball quality data + barrel rates for contact formula improvement."""
from pybaseball import statcast_batter_expected_stats, playerid_lookup, statcast_batter
import warnings
import json
import numpy as np
warnings.filterwarnings("ignore")

# Expected stats (xBA, xSLG, xwOBA)
df = statcast_batter_expected_stats(2025, minPA=50)

MLBAM_IDS = {
    "Juan Soto": 665742,
    "Byron Buxton": 621439,
    "Vladimir Guerrero Jr.": 665489,
    "Yordan Alvarez": 670541,
    "Pete Crow-Armstrong": 691718,
    "Bobby Witt Jr.": 677951,
    "Xander Bogaerts": 593428,
    "Matt Shaw": 807713,
    "Hyeseong Kim": 808975,
    "Adley Rutschman": 668939,
    "Chandler Simpson": 700165,
}

STATCAST_NAMES = {
    "Juan Soto": "Soto, Juan",
    "Byron Buxton": "Buxton, Byron",
    "Vladimir Guerrero Jr.": "Guerrero Jr., Vladimir",
    "Yordan Alvarez": "Alvarez, Yordan",
    "Pete Crow-Armstrong": "Crow-Armstrong, Pete",
    "Bobby Witt Jr.": "Witt Jr., Bobby",
    "Xander Bogaerts": "Bogaerts, Xander",
    "Matt Shaw": "Shaw, Matt",
    "Hyeseong Kim": "Kim, Hyeseong",
    "Adley Rutschman": "Rutschman, Adley",
    "Chandler Simpson": "Simpson, Chandler",
}

show_con_r = {
    "Juan Soto": 85, "Byron Buxton": 70, "Vladimir Guerrero Jr.": 93,
    "Yordan Alvarez": 80, "Pete Crow-Armstrong": 73, "Bobby Witt Jr.": 88,
    "Xander Bogaerts": 75, "Matt Shaw": 49, "Hyeseong Kim": 72,
    "Adley Rutschman": 60, "Chandler Simpson": 81,
}

results = {}

for name, sc_name in STATCAST_NAMES.items():
    match = df[df["last_name, first_name"] == sc_name]
    if match.empty:
        # Try partial
        last = name.split()[-1]
        match = df[df["last_name, first_name"].str.contains(last, na=False)]
    if match.empty:
        print(f"  {name}: NOT FOUND in expected stats")
        continue

    row = match.iloc[0]
    results[name] = {
        "ba": float(row["ba"]),
        "est_ba": float(row["est_ba"]),
        "xba_diff": float(row["est_ba_minus_ba_diff"]),
        "slg": float(row["slg"]),
        "est_slg": float(row["est_slg"]),
        "woba": float(row["woba"]),
        "est_woba": float(row["est_woba"]),
    }

# Now pull batted ball data (exit velo, hard hit rate, barrel rate) from statcast
print("\nPulling batted ball quality from Statcast...")
for name, mlbam_id in MLBAM_IDS.items():
    try:
        data = statcast_batter("2025-03-20", "2025-10-01", mlbam_id)
        if data.empty:
            continue

        # Filter to batted balls (in play)
        batted = data[data["launch_speed"].notna()]
        if len(batted) == 0:
            continue

        avg_ev = batted["launch_speed"].mean()
        hard_hit = (batted["launch_speed"] >= 95).mean() * 100  # hard hit %
        barrel = (batted["launch_speed_angle"].apply(
            lambda x: 1 if x is not None else 0
        ) if "launch_speed_angle" in batted.columns else 0)

        # Barrel rate from barrel flag if available
        if "barrel" in batted.columns:
            barrel_pct = batted["barrel"].mean() * 100
        else:
            barrel_pct = None

        if name not in results:
            results[name] = {}
        results[name]["avg_ev"] = round(avg_ev, 1)
        results[name]["hard_hit_pct"] = round(hard_hit, 1)
        results[name]["barrel_pct"] = round(barrel_pct, 1) if barrel_pct else None
        results[name]["n_batted"] = len(batted)

        print(f"  {name:<25} AvgEV={avg_ev:.1f}  HardHit%={hard_hit:.1f}  Barrels={barrel_pct}")
    except Exception as e:
        print(f"  {name}: ERROR - {e}")

# ================================================================
# ANALYSIS: Does exit velocity or xBA improve Contact R?
# ================================================================
print("\n" + "=" * 70)
print("  CONTACT R: Testing batted ball quality inputs")
print("=" * 70)

names = list(show_con_r.keys())
con_r = [show_con_r[n] for n in names]

def fit_and_print(label, x_vals, y_vals):
    x = np.array(x_vals, float)
    y = np.array(y_vals, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3:
        print(f"  {label}: too few data points")
        return
    corr = np.corrcoef(x, y)[0, 1]
    A = np.column_stack([x, np.ones(len(x))])
    c, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    preds = c[0] * x + c[1]
    rmse = np.sqrt(np.mean((y - preds) ** 2))
    print(f"  {label:<25} r={corr:>+.3f}  RMSE={rmse:.1f}  ({c[0]:.1f}x + {c[1]:.1f})")

# BA
ba_vals = [results.get(n, {}).get("ba", float("nan")) for n in names]
fit_and_print("BA", ba_vals, con_r)

# xBA (expected BA based on exit velo + launch angle)
xba_vals = [results.get(n, {}).get("est_ba", float("nan")) for n in names]
fit_and_print("xBA (expected BA)", xba_vals, con_r)

# Avg Exit Velocity
ev_vals = [results.get(n, {}).get("avg_ev", float("nan")) for n in names]
fit_and_print("Avg Exit Velo", ev_vals, con_r)

# Hard Hit %
hh_vals = [results.get(n, {}).get("hard_hit_pct", float("nan")) for n in names]
fit_and_print("Hard Hit %", hh_vals, con_r)

# Multi: BA + Exit Velo
print(f"\n  Multi-variable tests:")
valid = [(i, n) for i, n in enumerate(names)
         if n in results and "avg_ev" in results[n] and "ba" in results[n]]
if len(valid) >= 5:
    idx = [v[0] for v in valid]
    X = np.array([[results[names[i]]["ba"], results[names[i]]["avg_ev"]] for i in idx])
    Y = np.array([con_r[i] for i in idx])
    A = np.column_stack([X, np.ones(len(X))])
    c, _, _, _ = np.linalg.lstsq(A, Y, rcond=None)
    preds = A @ c
    rmse = np.sqrt(np.mean((Y - preds) ** 2))
    ss_res = np.sum((Y - preds) ** 2)
    ss_tot = np.sum((Y - np.mean(Y)) ** 2)
    r2 = 1 - ss_res / ss_tot
    print(f"  BA + AvgEV -> Contact R: R2={r2:.3f}  RMSE={rmse:.1f}")
    print(f"  Formula: {c[0]:.1f}*BA + {c[1]:.2f}*EV + {c[2]:.1f}")

    print(f"\n  {'Player':<25} {'BA':>6} {'EV':>5} {'Show':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 52)
    for j, i in enumerate(idx):
        n = names[i]
        err = preds[j] - con_r[i]
        flag = " ***" if abs(err) > 10 else ""
        print(f"  {n:<25} {results[n]['ba']:.3f} {results[n]['avg_ev']:>5.1f} {con_r[i]:>5} {preds[j]:>5.0f} {err:>+5.0f}{flag}")

# xBA + BA combo
valid2 = [(i, n) for i, n in enumerate(names)
          if n in results and "est_ba" in results[n] and "ba" in results[n]]
if len(valid2) >= 5:
    idx2 = [v[0] for v in valid2]
    X2 = np.array([[results[names[i]]["ba"], results[names[i]]["est_ba"]] for i in idx2])
    Y2 = np.array([con_r[i] for i in idx2])
    A2 = np.column_stack([X2, np.ones(len(X2))])
    c2, _, _, _ = np.linalg.lstsq(A2, Y2, rcond=None)
    preds2 = A2 @ c2
    rmse2 = np.sqrt(np.mean((Y2 - preds2) ** 2))
    ss_res2 = np.sum((Y2 - preds2) ** 2)
    ss_tot2 = np.sum((Y2 - np.mean(Y2)) ** 2)
    r22 = 1 - ss_res2 / ss_tot2
    print(f"\n  BA + xBA -> Contact R: R2={r22:.3f}  RMSE={rmse2:.1f}")
    print(f"  Formula: {c2[0]:.1f}*BA + {c2[1]:.1f}*xBA + {c2[2]:.1f}")

    print(f"\n  {'Player':<25} {'BA':>6} {'xBA':>6} {'Show':>5} {'Pred':>5} {'Err':>5}")
    print("  " + "-" * 55)
    for j, i in enumerate(idx2):
        n = names[i]
        err = preds2[j] - con_r[i]
        flag = " ***" if abs(err) > 10 else ""
        print(f"  {n:<25} {results[n]['ba']:.3f} {results[n]['est_ba']:.3f} {con_r[i]:>5} {preds2[j]:>5.0f} {err:>+5.0f}{flag}")
