# Plan 005: Stop tracking bloated and personal data artifacts

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 005 row in `plans/README.md`.
> This plan runs `git rm --cached` (index-only, does NOT delete working files) —
> that is permitted. Do NOT run `git commit` or `git push`; leave staged changes
> for the owner to review and commit.
>
> **Drift check (run first)**: `git ls-files | grep -E "_recal_cache.json|show_truth.json|player_pool.json"`
> Confirm these are still tracked; if already untracked, mark the corresponding
> step done and skip it.

## Status
- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt

## Why this matters

Several large or personal files are committed to a public repo: `_recal_cache.json`
(~647 KB, a regenerable calibration cache), `show_truth.json` (~459 KB, regenerable
by `scrape_truth.py`), and `player_pool.json` (~28 KB, the user's *personal* saved
cards — different per user, not project data). They bloat clones, make calibration
diffs noisy, and publish personal state. This plan stops tracking them (keeping the
files on disk) and ignores them going forward.

**One judgment call to surface, not decide:** `show_truth.json` is the hand-collected
ground-truth Show ratings that the whole reverse-engineering effort calibrates
against. Untracking it removes it from the public repo. If the owner considers it
the project's differentiating asset, untracking is *desirable*; if they want others
to reproduce the calibration, it should stay. **Do Step 3 only after confirming
with the owner** (see STOP conditions).

## Current state

- `.gitignore` currently ignores (relevant excerpt):
  ```
  # Project-local caches
  .cache/
  *.parquet
  fg_fielding_cache/
  ...
  prospect_data/progress.json
  prospect_data/fg_unmatched.json
  prospect_data/fg_board_cache.json
  prospect_data/fangraphs_board.csv
  recal_run.log
  ```
  It does NOT ignore `_recal_cache.json`, `show_truth.json`, or `player_pool.json`.
- `git ls-files` shows all three are tracked.
- `player_pool.json` is written at runtime by `player_pool.py` (`_save_all`); it
  is user state, not source data.
- `_recal_cache.json` is the `--skip-pull` cache for `recalibrate_all.py`.
- `show_truth.json` is produced by `scrape_truth.py`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| List tracked targets | `git ls-files \| grep -E "_recal_cache\|show_truth\|player_pool.json"` | shows tracked files |
| Untrack (index only) | `git rm --cached <file>` | "rm '<file>'", file stays on disk |
| Confirm still on disk | `ls -la <file>` | file present |
| Suite | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q` | all pass |

## Scope

**In scope**:
- `.gitignore` (add entries)
- Untracking (git index only): `_recal_cache.json`, `player_pool.json`, and —
  pending owner confirmation — `show_truth.json`.

**Out of scope**:
- Deleting any file from disk (only `--cached` untracking).
- `prospect_data/teams.json` — intentionally committed per the `.gitignore`
  comment (line 27); leave it tracked.
- `career_data.json` / `career_data_fixed.json` / `player_2025_*.json` — these
  are small and may be referenced; do NOT untrack them in this plan (see
  Maintenance notes; verify usage first in a separate change).

## Steps

### Step 1: Add ignore entries

Append to `.gitignore`:
```
# Regenerable calibration artifacts
_recal_cache.json
show_truth.json

# Personal runtime state (per-user saved cards)
player_pool.json
```

### Step 2: Untrack the safe two

```
git rm --cached _recal_cache.json player_pool.json
```
**Verify**: both files still exist on disk (`ls -la`); `git status` shows them as
deleted-from-index + now-untracked/ignored.

### Step 3: Untrack show_truth.json — ONLY after owner confirmation

If (and only if) the owner confirms `show_truth.json` should leave the public repo:
```
git rm --cached show_truth.json
```
If the owner wants it to stay public, REMOVE the `show_truth.json` line you added
to `.gitignore` in Step 1 and skip this step. Record which choice was made in the
plan 005 status row.

### Step 4: Verify nothing breaks

`recalibrate_all.py` regenerates `_recal_cache.json`; `scrape_truth.py`
regenerates `show_truth.json`; the app recreates `player_pool.json` on first save.
Untracking does not remove the working files, so runtime is unaffected.

**Verify**: `pytest -q` → all pass (the suite must not depend on these being
*tracked*; it reads the on-disk files which still exist).

## Done criteria

- [ ] `.gitignore` contains entries for `_recal_cache.json` and `player_pool.json` (and `show_truth.json` iff owner chose to untrack it).
- [ ] `git ls-files | grep -E "_recal_cache|player_pool.json"` returns nothing.
- [ ] `_recal_cache.json`, `player_pool.json`, `show_truth.json` still exist on disk.
- [ ] `pytest -q` exits 0.
- [ ] `show_truth.json` decision recorded in `plans/README.md` status row.

## STOP conditions

- The owner has not weighed in on `show_truth.json` — do Steps 1–2 and 4, leave
  Step 3 pending, and report that it's awaiting the owner's call.
- Any test fails after untracking (means a test depended on git-tracked state —
  investigate; do not re-add to git blindly).
- `git rm --cached` reports a file is not tracked — skip it (already done).

## Maintenance notes

- A separate, larger cleanup could untrack `career_data.json`,
  `career_data_fixed.json`, and `player_2025_*.json` after confirming nothing
  imports them — left out here because they need a usage audit first.
- Reviewer: confirm `git rm --cached` (not `git rm`) was used — the working files
  must remain.
