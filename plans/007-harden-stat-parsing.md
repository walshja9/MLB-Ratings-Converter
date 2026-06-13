# Plan 007: Harden stat parsing — NaN-safe ints, KeyError-safe sorts, no silent error-swallowing

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 007 row in `plans/README.md`. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `git diff --stat bcfbd39..HEAD -- generate_card.py`
> If `generate_card.py` changed since this plan was written, re-locate each
> excerpt below by content (line numbers may shift); on a content mismatch, STOP.

## Status
- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: 001 (green baseline), 003 (one-command runner)
- **Category**: bug

## Why this matters

The FanGraphs/BBRef data path has three classes of fragility that surface as
era-dependent 500s or silently-wrong cards:

1. **NaN → `int()` crash.** The pitcher pull casts count columns with bare
   `int(row.get(...))`; if FanGraphs returns `NaN` (common on partial rows),
   `int(nan)` raises `ValueError` and the whole pull fails.
2. **`KeyError` on missing sort columns.** Several lookups `sort_values("PA"/"IP")`
   without checking the column exists, so an old-era or oddly-shaped frame crashes.
3. **Silent `except: pass` on the career-walk path.** A transient network/parse
   failure is indistinguishable from "player didn't play that year," so cards get
   built on fewer years than intended with no log line.

These are real but lower-frequency than the rating bugs; the goal is to fail
loudly (or degrade explicitly) instead of crashing or silently truncating.

## Current state

**(1) Pitcher count columns — bare `int()`** — `generate_card.py:1141-1168`:
```python
    def safe_float(val, default=0):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return default
        return float(val)

    fbv = safe_float(row.get("FBv"), None)

    return {
        "W": int(row.get("W", 0)),
        "L": int(row.get("L", 0)),
        ...
        "G": int(row.get("G", 0)),
        "GS": int(row.get("GS", 0)),
        "SV": int(row.get("SV", 0)),
        ...
        "FB_velo": round(fbv, 1) if fbv else None,   # also: 0.0 velo -> None (minor)
        ...
    }
```
There is a `safe_float` right here but no `safe_int`. The batting pull elsewhere
already uses a NaN-guarded integer helper — match that style.

**(2) Sort-by-PA/IP without column guard** — examples:
`generate_card.py:446` `match.sort_values("PA", ...)`, the pitcher matcher
(`find_pitcher_fg`, ~line 1120/1127), career multi-match sorts (~lines 600, 1188),
and `detect_player_type` reads `iloc[0]["IP"]/["PA"]` (~lines 355, 364) inside a
`try/except: pass`.

**(3) Silent career-walk swallows** — broad `except Exception: pass`/`break` at
`generate_card.py:516-517, 527-528, 623-624, 862-863, 1203-1204` and the
`detect_player_type` blocks at `351-357, 359-366`. These hide network vs
not-found.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Syntax check | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -c "import py_compile; py_compile.compile('generate_card.py', doraise=True)"` | exit 0 |
| Suite | `"C:/.../python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: `generate_card.py` (the parsing/lookup helpers above); a new test
file `test_stat_parsing.py`.
**Out of scope**:
- Any rating *formula* (this plan is parsing robustness only).
- The duplicate-`safe_float` consolidation — that's plan 009; here just add a
  `safe_int` and use it. Do not refactor the existing `safe_float` definitions.
- Live network behavior / the scrapers themselves.

## Steps

### Step 1: Add a NaN-safe integer cast and use it in the pitcher pull

Next to the local `safe_float` at ~line 1141, add:
```python
    def safe_int(val, default=0):
        if val is None or (isinstance(val, float) and _math.isnan(val)):
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
```
Replace the bare `int(row.get("W", 0))`, `"L"`, `"G"`, `"GS"`, `"SV"` (and any
other bare `int(...)` in this return dict) with `safe_int(row.get(...))`.
Also change `"FB_velo": round(fbv, 1) if fbv else None` to
`round(fbv, 1) if fbv is not None else None` (so a legitimate 0.0 isn't dropped —
minor correctness).

**Verify**: `py_compile` exit 0; `pytest -q` all pass.

### Step 2: Guard the PA/IP sorts

For each `sort_values("PA"/"IP", ...)` in the listed locations, guard with a
column check, falling back to the first row when the column is absent. Pattern:
```python
sort_col = "PA"  # or "IP"
if sort_col in match.columns:
    chosen = match.sort_values(sort_col, ascending=False).iloc[0]
else:
    chosen = match.iloc[0]
```
Apply the same guard inside `detect_player_type` before `iloc[0]["IP"]/["PA"]`.

**Verify**: `pytest -q` all pass.

### Step 3: Make the career-walk swallows explicit

For the broad `except Exception` blocks on the career-walk and detect paths, do
NOT remove the resilience, but distinguish "no data for this year" (an empty
match — keep walking/stop normally) from a real exception (log it). Minimal,
low-risk change: replace `except Exception: pass`/`break` with
```python
except Exception as e:
    import sys
    print(f"[career-walk] {year}: {type(e).__name__}: {e}", file=sys.stderr)
    break   # or `continue`/`pass` — preserve the original control flow
```
Preserve each block's original control flow (whatever it did after the except —
`break`, `continue`, or fall-through). Only add the log line; do not change the
flow. If a block's original behavior is load-bearing and unclear, leave it and
note it.

**Verify**: `pytest -q` all pass; no test asserts on stderr.

### Step 4: Add targeted unit tests

Create `test_stat_parsing.py` exercising the parse helpers with hostile inputs
(model construction after `test_custom_card.py` / the `_make_data` helpers):
- `safe_int(float('nan'))` → 0; `safe_int(None)` → 0; `safe_int("12")` → 12;
  `safe_int(5.0)` → 5.
- A pitcher row dict with `NaN` in `W`/`G`/`GS` parses without raising and yields
  integer 0s.
- A match frame **without** a `PA` column does not raise in the guarded
  selection path (test the smallest reachable function that contains the guard;
  if the sort is buried in a network function, test `safe_int`/`safe_float` plus
  the guard logic via a tiny extracted check rather than mocking the network).

If a helper is a nested function not importable at module scope, STOP and report
— do not promote it to module scope here (that overlaps plan 009); instead test
behavior through the nearest importable caller, or note the coverage gap.

**Verify**: `pytest test_stat_parsing.py -q` → all new tests pass.

### Step 5: Full run

**Verify**: `pytest -q` → all pass including new tests.

## Test plan

- New `test_stat_parsing.py`: NaN/None/str/float cases for `safe_int`; a
  NaN-bearing pitcher row parses cleanly; the missing-column selection doesn't
  raise. Pattern after `test_custom_card.py`.
- Verification: `pytest -q` all pass.

## Done criteria

- [ ] No bare `int(row.get(...))` remains in the pitcher pull return dict (`grep -n "int(row.get" generate_card.py` shows only `safe_int` usages or none).
- [ ] `py_compile generate_card.py` exit 0; `pytest -q` all pass.
- [ ] `test_stat_parsing.py` exists with passing NaN/missing-column tests.
- [ ] No rating formula constant changed (`git diff generate_card.py` shows only parsing/guard/log edits).
- [ ] `plans/README.md` status row for 007 updated.

## STOP conditions

- `generate_card.py` content drifted from the excerpts.
- Changing a guard or except block makes an existing test fail (the test may
  encode the old behavior — report it, don't silently update).
- A helper you need to test is nested and not reachable — report the coverage gap
  rather than restructuring (that's plan 009's job).

## Maintenance notes

- Plan 009 consolidates the three duplicate `safe_float` definitions and could
  fold `safe_int` into the same shared helper — coordinate so they don't conflict.
- Reviewer: confirm no formula changed and that the except blocks kept their
  original control flow (only gained a log line).
