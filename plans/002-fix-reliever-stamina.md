# Plan 002: Fix reliever stamina — openers/swingmen wrongly get starter-level stamina

> **Executor instructions**: Follow step by step. Run every verification command
> and confirm the expected result before moving on. Honor STOP conditions. Update
> the plan 002 status row in `plans/README.md` when done. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**:
> `git diff --stat bcfbd39..HEAD -- generate_card.py`
> If `generate_card.py` changed since this plan was written, compare the "Current
> state" excerpt below against the live code; on a mismatch, STOP.

## Status
- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: 001 (land on a green suite so the new test's pass is meaningful)
- **Category**: bug

## Why this matters

A pitcher is classified `RP` when fewer than 40% of his appearances are starts
(`generate_card.py:1358`). But the stamina formula only applies the reliever
branch when `GS == 0` (`generate_card.py:2500`). So an opener or swingman — say
5 starts in 50 games — is labeled `RP` yet falls through to the **starter**
stamina formula `0.273*GS + 76.8`, landing at ~78 stamina instead of the ~28 a
reliever should get. Stamina feeds the pitching-overall average, which feeds
pitcher OVR (`1.074*pitching_overall + 4.6`), so these arms get a materially
inflated card. The fix aligns the stamina branch with the role classification.

## Current state

`generate_card.py:1356-1358` — role classification:
```python
# Detect role: SP if >50% of games are starts
pit = data["pitching"]
data["role"] = "SP" if pit["GS"] > pit["G"] * 0.4 else "RP"
```
(Note the comment says 50% but the code uses 40% — leave that as-is; not this
plan's concern.)

`generate_card.py:2491-2507` — stamina assignment (the bug is the `and pit["GS"] == 0`):
```python
    # --- STAMINA ---
    # Show gives all SPs a high baseline (~75) with modest extra credit per
    # start. ...
    if role == "RP" and pit["GS"] == 0:
        ratings["stamina"] = clamp(-0.054 * pit["G"] + 28.7)
    elif use_career:
        career_gs = career.get("avg_GS_per_year", pit["GS"]) if isinstance(career, dict) else pit["GS"]
        gs_blend = 0.4 * pit["GS"] + 0.6 * career_gs
        ratings["stamina"] = clamp(0.273 * gs_blend + 76.8)
    else:
        ratings["stamina"] = clamp(0.273 * pit["GS"] + 76.8)
```
`role` is read from `data["role"]` earlier in `calculate_ratings` (the same value
set at line 1358). Confirm `role` is in scope at line 2500 before editing.

The existing custom-card test file `test_custom_card.py` builds synthetic pitcher
data dicts and calls through the engine — use it as the pattern for the new test.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Run suite | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q` | all pass |
| Run new test | `"C:/.../python.exe" -m pytest test_pitcher_stamina.py -q` | new tests pass |

## Scope

**In scope**:
- `generate_card.py` (the single stamina condition at ~line 2500)
- `test_pitcher_stamina.py` (create)

**Out of scope**:
- The 40%-vs-comment-50% role threshold at line 1358 — do not change it.
- Any other stamina/role/OVR coefficient.
- The RP baseline formula `-0.054*pit["G"] + 28.7` — keep it; only its *gate* changes.

## Steps

### Step 1: Make the reliever stamina branch fire for any reliever

Change the condition so role alone routes relievers to the RP stamina formula,
regardless of a few starts. Target shape:
```python
    if role == "RP":
        ratings["stamina"] = clamp(-0.054 * pit["G"] + 28.7)
    elif use_career:
        ...
    else:
        ...
```
That is: drop the `and pit["GS"] == 0` so every `RP` uses the reliever baseline.
(An opener with a handful of starts is still primarily a bullpen arm in Show
terms — low stamina is correct.)

**Verify**: `pytest -q` → still all pass (no existing test should regress; if one
does, read it — it may have depended on the buggy behavior; report it).

### Step 2: Add a regression test

Create `test_pitcher_stamina.py` modeled on the pitcher-data construction in
`test_custom_card.py`. Cover:
- **The bug**: a pitcher with `GS=5, G=50` (role → RP) gets RP-level stamina
  (assert `stamina < 40`, not the ~78 the SP formula would give).
- **Pure reliever**: `GS=0, G=65` → RP stamina (`stamina < 40`).
- **Starter unaffected**: `GS=30, G=32` (role → SP) → high stamina
  (assert `stamina > 70`).

If constructing a full data dict for the engine is heavy, build the minimal dict
the engine needs for the pitcher path (mirror what `test_custom_card.py` and
`test_pre_oaa_fielding.py::_make_data` do). If you cannot exercise `stamina`
through a stable public entry point, STOP and report rather than testing private
internals fragilely.

**Verify**: `pytest test_pitcher_stamina.py -q` → 3 passed.

### Step 3: Full run

**Verify**: `pytest -q` → all pass including the 3 new tests.

## Test plan

- New file `test_pitcher_stamina.py`, 3 tests (bug case, pure RP, SP control),
  structured after `test_custom_card.py`.
- Verification: `pytest -q` → all pass.

## Done criteria

- [ ] `generate_card.py` stamina condition no longer contains `and pit["GS"] == 0`.
- [ ] `pytest -q` exits 0; `test_pitcher_stamina.py` exists with 3 passing tests.
- [ ] `git diff --name-only` shows only `generate_card.py` + `test_pitcher_stamina.py`.
- [ ] `plans/README.md` status row for 002 updated.

## STOP conditions

- `generate_card.py` drifted from the excerpt (role/stamina code differs).
- An existing test regresses after Step 1 (report which and why before changing it).
- You cannot drive `stamina` through a stable entry point for the test.

## Maintenance notes

- If a future change reconciles the role threshold comment (50%) with the code
  (40%), this stamina branch still works — it keys off `role`, not the threshold.
- Reviewer: confirm the new test asserts on `role == "RP"` outcomes, and that the
  opener case (`GS>0`, role RP) is the one that would have failed before.
