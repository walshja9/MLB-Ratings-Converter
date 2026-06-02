# Custom Card Generator — Design

- **Date:** 2026-06-02
- **Status:** Approved (brainstorm), pending implementation plan
- **Sub-project of:** "Buildable baseball game" foundation (see Vision below)

## Problem

The tool generates MLB The Show–style rating cards from a real player's
season, pulled live from Statcast + Baseball-Reference. There is no way to
rate a *fictional* player. To build our own (unlicensed) baseball game, we
need to populate it with custom players — and the rating engine is exactly
what should rate them. We need a second way into the engine: enter stats by
hand instead of pulling them from the network.

## Goal

Add a **Custom Card Generator**: a form where a user enters a fictional
player's raw stats and gets a full rating card, using the existing rating
engine unchanged.

Success criterion (the core guarantee): given the *same field values* that
`pull_all_data` produces for a real player, `build_custom_data` produces a
`data` dict that makes `calculate_ratings` return **identical** output. The
custom path and the Converter path are the same engine fed by two producers.

## Non-goals (explicitly out of scope)

- **No derivation / inverse model.** We do not compute independent
  measurements (exit velo, barrel%, OAA, FB velo, arsenal) from a slash line.
  See "Advanced metrics" below.
- **No career mode.** A single hand-entered stat line has no multi-year
  history to blend. Custom is season-mode only.
- **No "face-value / no-regression" toggle.** Custom players ride the
  engine's existing sample-size dampening, same as real players.
- **No engine or renderer changes.** `calculate_ratings`,
  `calculate_pitcher_ratings`, `calculate_overalls`, and the card renderer
  are untouched. This is the guarantee that the working Converter cannot
  regress.

## Vision (context only — not built here)

The end state is a sim + playable baseball game built on this rating engine,
decomposed into layers, each its own spec → plan → build:

- **A — Player foundation** *(this spec is the first piece)*: rate players;
  two front doors — Converter (real) and Custom Generator (fictional);
  later, persist a player pool.
- **B — Sim engine**: ratings + game state → plate-appearance outcome →
  innings → box score (OOTP-style).
- **C — Management shell**: teams, lineups, schedule, season, standings.
- **D — Real-time playable layer**: pitch/swing/field in real time. A
  different discipline (game loop, rendering, physics); long-horizon Phase 2,
  likely a different stack.

The game uses custom players + generic team identities — no real clubs or
logos — which is what keeps it legally clean. The Custom Generator is both
the player-creation tool the game needs and the IP-safe path.

## Architecture — one seam

Today:

```
[name + year] → pull_all_data() ──┐
                                  ├→ calculate_ratings(data) → calculate_overalls() → card
[real network calls] ─────────────┘
```

After:

```
[name + year]   → pull_all_data() ────────┐
                                           ├→ calculate_ratings(data) → calculate_overalls() → card
[custom form]   → build_custom_data() ─────┘   (UNCHANGED downstream)
```

New surface, total:

- `build_custom_data(form, is_pitcher, position) -> data` — assembles the
  exact `data` dict shape the engine expects from form fields; optional
  fields default to `None`.
- `/generate_custom` POST route — mirrors `/generate`, swaps the data source,
  returns the **same JSON shape**.
- A "Custom Player" tab in `templates/index.html`.

The engine branches on **data presence, not year** (verified:
`sprint = data.get("sprint_speed")` → tracking formula if present, `elif
fg_spd`, `else estimate_speed_no_tracking(...)`; same pattern for splits,
`avg_ev`, `barrel_stats`, `fielding_oaa`). So a blank field at any year
falls cleanly into the existing fallback path.

## Input schema (the form)

Two tiers per player type. Required = what the formulas need to run; optional
= advanced fields that, when blank, drop into the engine's existing fallback.

### Hitter

- **Identity:** custom player name, custom team name (no real club required),
  position.
- **Required core:** PA, G, BA, OBP, SLG (or ISO), HR, 3B, SB, CS, BB%, K%,
  WAR.
- **Optional advanced:** vs-RHP BA/ISO, vs-LHP BA/ISO, RISP BA, avg exit
  velo, barrel%, hard-hit% (ev95%), sprint speed, OAA.
- **Catcher block** (shown only when position = C): pop time, arm strength
  inputs feeding the catcher attributes.

### Pitcher

- **Identity:** custom player name, custom team name, role (SP/RP).
- **Required core:** IP, G, GS, ERA, FIP, WHIP, K/9, BB/9, HR/9, H/9, K%,
  BB%, WAR.
- **Optional advanced:** FB velo, vs-RHP/LHP K% & BA, LOB%, pitch arsenal
  (type / usage% / velo per pitch).

Leaving the advanced tier blank yields a valid pre-Statcast-style card;
filling it yields a full modern card.

## Dampening & fallback behavior

- **Reuse the engine's existing dampening unchanged** —
  `trust = min(PA/200, 1)` for hitters, `min(IP/200, 1)` for pitchers. A
  custom 600-PA .300/30-HR hitter rates exactly like a real one. This
  consistency matters when these players later feed the sim (Layer B): custom
  and real rosters must be on the same footing.
- **PA / IP is required** because it drives `trust`.
- **Optional blank → `None` → existing fallback.** We write zero new fallback
  logic. The engine already auto-derives everything honestly derivable:

  | Attribute | When advanced field blank |
  |---|---|
  | Speed | `estimate_speed_no_tracking()` from SB + position |
  | Contact/Power splits | overall/career BA & ISO ("split = overall") |
  | Clutch (RISP) | overall-BA path |
  | Power | traditional ISO + HR-rate (no barrel%) |
  | Fielding | position baseline (no OAA) |

## Advanced metrics — no derivation engine

Independent measurements (exit velo, barrel%, hard-hit%, OAA, FB velo,
arsenal) are **not** computed from core stats. Reasons:

1. **Scope creep** — it is an inverse model we'd have to build and calibrate
   (the slider/back-solve approach already rejected).
2. **False precision** — a rating that looks measured but is guessed.
3. **Double-counting** — Contact R is `240·BA_vR + 2.09·EV − 168`; faking EV
   from ISO smuggles power info into the contact rating.

They stay optional. Honestly-derivable attributes are handled by the existing
fallbacks above.

## UI & route integration

- **Tab toggle** in `index.html`: **Real Player** (existing search) /
  **Custom Player** (new form).
- **Same render path.** `/generate_custom` returns the same JSON shape as
  `/generate`, so the existing card-render JS displays it with no new
  rendering code. Custom name/team flow into the card's name/team line.
- **Validation** kept to what can break a formula:
  - Server-side guard in `build_custom_data`: reject PA = 0 / IP = 0
    (divide-by-zero) with a clear error.
  - Light client-side range hints: BA 0–1, percentages 0–100, counts ≥ 0.
  - Nothing more.

## Transparency

Extend the existing "EST." badge convention (already used for estimated pitch
arsenals): on a custom card, visibly mark attributes that came from a
fallback vs. from entered stats, so a blank-EV card reads as an estimate, not
a measurement.

## Testing — success criteria

1. **Equivalence test (core guarantee):** feed `build_custom_data` the same
   field values `pull_all_data` produced for a known real player → assert
   `calculate_ratings` output is identical to the Converter's.
2. **Unit tests for `build_custom_data`:** full-stats hitter; minimal-stats
   hitter (advanced blank → fallback path); SP; RP; catcher block.
3. **Edge:** PA = 0 / IP = 0 → clean error, not a crash.
4. Reuse the existing `test_*.py` patterns in the repo.

## Files touched

- `generate_card.py` — add `build_custom_data` (new function only; existing
  functions untouched).
- `app.py` — add `/generate_custom` route.
- `templates/index.html` — add Custom Player tab + form; reuse render JS.
- `test_custom_card.py` (new) — equivalence + unit + edge tests.
