# Plan 006: Move dead one-off analysis scripts into archive/

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 006 row in `plans/README.md`. Uses `git mv`
> (index-only move, files preserved) — permitted. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `ls *.py | wc -l` and confirm the candidate files
> below still exist. If many are already gone, reconcile against the live listing.

## Status
- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt

## Why this matters

The repo root holds ~21 historical, single-use scripts (early data pulls, formula
exploration, one-time data fixes) mixed in with the ~8 live modules. A new
contributor or agent can't tell live tooling from archaeology — e.g.
`recalibrate.py` vs `recalibrate_all.py`, or five `pull_*.py` scripts superseded
by inline pulls in `generate_card.py`. Moving the dead ones into `archive/`
preserves history while making the live surface obvious.

## Current state

Live modules imported by the app/engine (DO NOT move): `app.py`,
`generate_card.py`, `bbref_scraper.py`, `prospect_mapper.py`, `prospect_store.py`,
`player_pool.py`, `sim_engine.py`, `scrape_prospects.py`, `expand_prospects.py`,
and the calibration entry point `recalibrate_all.py` (with its import
`scrape_truth.py`).

**Candidate dead scripts** (verify each is imported by nothing before moving):
```
pull_stats.py            pull_stats_v2.py
pull_batted_ball.py      pull_fielding_career.py
pull_pitcher_stats.py    pull_simpson.py        pull_splits.py
build_mappings.py        build_mappings_v2.py
final_mappings.py        final_pass.py
pitcher_analysis.py      pitcher_analysis_v2.py
blended_analysis.py      player_data.py         deep_dive.py
explore_break.py         explore_enhancements.py  explore_finetune.py
_refit_hitter_ovr.py     _refit_pitcher_ovr.py
fix_career_data.py       verify_matches.py
recalibrate.py
```

**Known nuances to check, not assume:**
- `explore_break.py` imports from `generate_card` — it's exploration, still
  movable, but confirm nothing imports *it*.
- `recalibrate.py` is the OVR-only predecessor of `recalibrate_all.py`. Movable,
  but if the owner uses it as a quick OVR-only path, keep it. Flag, don't force.
- `scrape_teams.py` uses `scrape_truth` — it documents the data pipeline; the
  audit recommends KEEPING it. Do not move it.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Is a script imported anywhere? | `grep -rn "import <modname>\|from <modname> import" --include=*.py . :^archive` | no matches = safe to move |
| Move preserving history | `git mv <file> archive/<file>` | moved |
| Suite | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: create `archive/`; `git mv` the verified-dead scripts into it; add a
short `archive/README.md`.
**Out of scope**: deleting any file; moving any live module or any test; changing
script contents.

## Steps

### Step 1: Verify each candidate is import-free

For every file in the candidate list, run the import grep (module name = filename
without `.py`). Build the **confirmed-dead** set = candidates with zero import
hits anywhere outside themselves. Any candidate that IS imported drops off the
list (report it).

**Verify**: produce the confirmed-dead list; it should be a subset of the
candidates above.

### Step 2: Create archive/ and move

```
mkdir -p archive
git mv <each confirmed-dead file> archive/
```
Do them one at a time or in a batch. For `recalibrate.py`, only move it if the
owner hasn't flagged it as a kept quick-path (default: move it; it's superseded).

**Verify**: `ls archive/` lists the moved files; `ls *.py` no longer shows them.

### Step 3: Add archive/README.md

Create `archive/README.md`:
```markdown
# Archived scripts

One-off data pulls, formula-fitting experiments, and one-time data fixes from the
project's history. Not imported by the app or engine. Kept for reference only.
Live calibration is done by `../recalibrate_all.py`.
```

### Step 4: Confirm nothing broke

**Verify**: `pytest -q` → all pass. `"C:/.../python.exe" -c "import app"` → no
ImportError (the app must still import after the move).

## Test plan

- No new tests. The safety net is: (a) the import-grep in Step 1, (b) the full
  suite passing, (c) `import app` succeeding.

## Done criteria

- [ ] `archive/` exists with the confirmed-dead scripts and a README.
- [ ] `grep`-verified: no moved file is imported by any remaining `.py`.
- [ ] `pytest -q` exits 0; `import app` succeeds.
- [ ] `scrape_teams.py`, `recalibrate_all.py`, `scrape_truth.py`, and all live
      modules remain in the repo root.
- [ ] `plans/README.md` status row for 006 updated (note if `recalibrate.py` was kept).

## STOP conditions

- A candidate turns out to be imported by a live module or test — do not move it;
  report it.
- The suite or `import app` fails after a move — `git mv` it back and report.

## Maintenance notes

- If any archived script is later needed, `git mv archive/<f> .` restores it.
- Reviewer: spot-check that no live import path was broken and that the kept set
  is correct.
