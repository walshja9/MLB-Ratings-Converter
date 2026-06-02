"""Layer B — baseball sim engine.

Consumes the same 0-99 rating dicts the card generator produces (Layer A) and
simulates plate appearances -> innings -> a 9-inning box score. The plate
appearance model combines batter and pitcher ratings with log5 (the standard
batter-vs-pitcher odds method), anchored so league-average ratings (~65)
reproduce league-average rates.

MVP scope: one pitcher per side (no bullpen/fatigue), simple base advancement,
platoon splits averaged. Steals, GIDP, sac flies, and bullpen come later.
"""

import random

# League baselines (approx. modern MLB), per plate appearance unless noted.
LG = {
    "K": 0.225,       # strikeout rate
    "BB": 0.085,      # walk rate
    "HBP": 0.010,     # hit-by-pitch rate
    "BABIP": 0.295,   # hits / balls in play (non-HR contact)
    "HRPC": 0.047,    # home runs / contacted PA (non-K/BB/HBP)
}
ANCHOR = 65  # rating that maps to a league-average rate

# Reference dicts (every relevant rating = ANCHOR) -> league-average player.
AVG_BATTER = {"contact_left": ANCHOR, "contact_right": ANCHOR, "power_left": ANCHOR,
              "power_right": ANCHOR, "vision": ANCHOR, "discipline": ANCHOR}
AVG_PITCHER = {"k_per_9_left": ANCHOR, "k_per_9_right": ANCHOR, "h_per_9_left": ANCHOR,
               "h_per_9_right": ANCHOR, "control": ANCHOR, "hr_per_9": ANCHOR}


def _clip(p, lo=0.0005, hi=0.9995):
    return max(lo, min(hi, p))


def _rate(rating, base, slope):
    """Linear map from a 0-99 rating to a probability, anchored at ANCHOR."""
    return _clip(base + (rating - ANCHOR) * slope)


def _log5(b, p, lg):
    """Combine a batter rate b and pitcher rate p relative to league lg."""
    num = b * p / lg
    den = num + (1 - b) * (1 - p) / (1 - lg)
    return _clip(num / den)


def batter_profile(r):
    contact = (r.get("contact_left", 50) + r.get("contact_right", 50)) / 2
    power = (r.get("power_left", 50) + r.get("power_right", 50)) / 2
    return {
        "K": _rate(r.get("vision", 50), LG["K"], -0.0045),     # more vision -> fewer K
        "BB": _rate(r.get("discipline", 50), LG["BB"], 0.0032),
        "BABIP": _rate(contact, LG["BABIP"], 0.0030),
        "HRPC": _rate(power, LG["HRPC"], 0.0017),
        "XBH": _clip(0.32 + (power - ANCHOR) * 0.004),         # share of non-HR hits that go for extra bases
    }


def pitcher_profile(r):
    k = (r.get("k_per_9_left", 50) + r.get("k_per_9_right", 50)) / 2
    h = (r.get("h_per_9_left", 50) + r.get("h_per_9_right", 50)) / 2
    return {
        "K": _rate(k, LG["K"], 0.0045),
        "BB": _clip(LG["BB"] + (ANCHOR - r.get("control", 50)) * 0.0032),   # more control -> fewer BB
        "BABIP": _clip(LG["BABIP"] + (ANCHOR - h) * 0.0028),                # higher h/9 rating -> fewer hits
        "HRPC": _clip(LG["HRPC"] + (ANCHOR - r.get("hr_per_9", 50)) * 0.0017),
    }


def pa_probabilities(batter, pitcher):
    """Outcome probabilities for one plate appearance (sums to 1)."""
    b, p = batter_profile(batter), pitcher_profile(pitcher)
    pK = _log5(b["K"], p["K"], LG["K"])
    pBB = _log5(b["BB"], p["BB"], LG["BB"])
    pHBP = LG["HBP"]
    contacted = max(0.0, 1 - pK - pBB - pHBP)
    pHR = contacted * _log5(b["HRPC"], p["HRPC"], LG["HRPC"])
    in_play = contacted - pHR
    babip = _log5(b["BABIP"], p["BABIP"], LG["BABIP"])
    hits = in_play * babip
    pOUT = in_play - hits
    xbh = b["XBH"]
    p2B = hits * xbh * 0.84
    p3B = hits * xbh * 0.16
    p1B = hits - p2B - p3B
    return {"K": pK, "BB": pBB, "HBP": pHBP, "HR": pHR,
            "3B": p3B, "2B": p2B, "1B": p1B, "OUT": pOUT}


_PA_ORDER = ["K", "BB", "HBP", "HR", "3B", "2B", "1B", "OUT"]


def simulate_pa(batter, pitcher, rng):
    probs = pa_probabilities(batter, pitcher)
    roll = rng.random()
    cum = 0.0
    for outcome in _PA_ORDER:
        cum += probs[outcome]
        if roll < cum:
            return outcome
    return "OUT"


# Base the batter reaches, and how many bases existing runners advance, per hit.
# Runners advance more than the batter on singles/doubles (a runner scores from
# second on a single, etc.) — matching real run-scoring rates.
_BATTER_ADV = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}
_RUNNER_ADV = {"1B": 2, "2B": 2, "3B": 3, "HR": 4}


def _advance_walk(bases):
    """BB/HBP: batter to first, runners advance only when forced."""
    runs = 0
    if bases[0]:
        if bases[1]:
            if bases[2]:
                runs += 1                # bases loaded -> forced in
            bases[2] = True
        bases[1] = True
    bases[0] = True
    return bases, runs


def _advance_hit(bases, outcome):
    """Hit: runners advance _RUNNER_ADV, batter ends on its _BATTER_ADV base."""
    runs = 0
    new = [False, False, False]
    radv = _RUNNER_ADV[outcome]
    badv = _BATTER_ADV[outcome]
    for i in range(2, -1, -1):
        if bases[i]:
            if i + radv >= 3:
                runs += 1
            else:
                new[i + radv] = True
    if badv >= 4:
        runs += 1                        # home run: batter scores
    else:
        new[badv - 1] = True
    return new, runs


def simulate_half_inning(lineup, pitcher, start_idx, rng, line=None):
    """Simulate one half inning. Returns (runs, hits, next_batter_idx)."""
    outs = 0
    runs = 0
    hits = 0
    bases = [False, False, False]
    idx = start_idx
    while outs < 3:
        batter = lineup[idx % len(lineup)]
        idx += 1
        outcome = simulate_pa(batter, pitcher, rng)
        if outcome == "K" or outcome == "OUT":
            outs += 1
        elif outcome in ("BB", "HBP"):
            bases, r = _advance_walk(bases)
            runs += r
        else:
            hits += 1
            bases, r = _advance_hit(bases, outcome)
            runs += r
        if line is not None:
            line.append((batter.get("name", "?"), outcome))
    return runs, hits, idx


def simulate_game(home, away, rng=None, innings=9):
    """Simulate a full game. home/away are {"name", "lineup":[9 rating dicts], "pitcher": rating dict}.
    Returns a box-score dict. Home bats second; walk-off ends the bottom half early."""
    rng = rng or random.Random()
    line_score = {"away": [], "home": []}
    away_idx = home_idx = 0
    away_runs = home_runs = away_hits = home_hits = 0

    inning = 1
    while True:
        # Top (away bats)
        r, h, away_idx = simulate_half_inning(away["lineup"], home["pitcher"], away_idx, rng)
        away_runs += r; away_hits += h
        line_score["away"].append(r)
        # Bottom (home bats) — skip if home already leads in the final scheduled inning
        if inning >= innings and home_runs > away_runs:
            line_score["home"].append("X")
            break
        r, h, home_idx = simulate_half_inning(home["lineup"], away["pitcher"], home_idx, rng)
        home_runs += r; home_hits += h
        line_score["home"].append(r)
        if inning >= innings and home_runs != away_runs:
            break
        inning += 1
        if inning > 30:  # safety valve
            break

    return {
        "away": {"name": away.get("name", "Away"), "runs": away_runs, "hits": away_hits},
        "home": {"name": home.get("name", "Home"), "runs": home_runs, "hits": home_hits},
        "line_score": line_score,
        "innings": len(line_score["away"]),
        "winner": away.get("name", "Away") if away_runs > home_runs else home.get("name", "Home"),
    }


def make_team(name, batter_ratings, pitcher_ratings):
    """Build a team from a list of 9 batter rating dicts + 1 pitcher rating dict."""
    return {"name": name, "lineup": list(batter_ratings), "pitcher": pitcher_ratings}


def format_box(box):
    a, h = box["away"], box["home"]
    lines = [f"{a['name']}  {a['runs']}  ({a['hits']} H)",
             f"{h['name']}  {h['runs']}  ({h['hits']} H)",
             f"Final/{box['innings']} - {box['winner']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo: two league-average teams, one game.
    rng = random.Random(7)
    avg_lineup = [dict(AVG_BATTER, name=f"H{i+1}") for i in range(9)]
    away = make_team("Avg A", avg_lineup, dict(AVG_PITCHER, name="P-A"))
    home = make_team("Avg B", avg_lineup, dict(AVG_PITCHER, name="P-B"))
    print(format_box(simulate_game(home, away, rng)))
