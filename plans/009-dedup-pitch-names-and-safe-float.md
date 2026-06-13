# Plan 009: De-duplicate PITCH_NAMES (fix latent SP→Splitter bug) and consolidate safe_float

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 009 row in `plans/README.md`. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `git diff --stat bcfbd39..HEAD -- generate_card.py`
> Re-locate each excerpt by content if line numbers shifted; on a content
> mismatch, STOP.

## Status
- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: 001 (green baseline), 003 (runner)
- **Category**: tech-debt (contains a latent display bug fix)

## Why this matters

`generate_card.py` defines the pitch-code→name map twice, and the two copies have
diverged: the module-level `_PITCH_NAMES` includes `"SP": "Splitter"`, but the
local `PITCH_NAMES` inside `pull_pitcher_statcast` does NOT. So a pitch coded `SP`
displays as the raw code `"SP"` in the live Statcast path but as `"Splitter"` in
the custom-arsenal path — a real, if narrow, display inconsistency. Separately,
`safe_float` is defined four times across the file with subtly different defaults.
Collapsing these to one definition each removes the divergence and the drift risk.

## Current state

Module-level map (15 entries, has `SP`) — `generate_card.py:63-68`:
```python
_PITCH_NAMES = {
    "FF": "4-Seam FB", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
    "ST": "Sweeper", "CU": "Curveball", "CH": "Changeup", "FS": "Splitter",
    "SP": "Splitter", "KC": "Knuckle Curve", "SV": "Slurve", "KN": "Knuckleball",
    "SC": "Screwball", "EP": "Eephus", "CS": "Slow Curve",
}
```
Local map inside `pull_pitcher_statcast` (14 entries, MISSING `SP`) — `generate_card.py:1284-1289`:
```python
    PITCH_NAMES = {
        "FF": "4-Seam FB", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
        "ST": "Sweeper", "CU": "Curveball", "CH": "Changeup", "FS": "Splitter",
        "KC": "Knuckle Curve", "SV": "Slurve", "KN": "Knuckleball",
        "SC": "Screwball", "EP": "Eephus", "CS": "Slow Curve",
    }
```
`safe_float` definitions (different defaults): `generate_card.py:549` (`default=0.0`),
`:721` (`def safe_float(val)` — no default param), `:1141` (`default=0`). Plus
nested `sf`/`_sf` helpers at `:610, 982, 1040` (leave those — they're tiny
locals with their own defaults; only the three `safe_float`s are the target).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Find pitch-name maps | `grep -n "PITCH_NAMES" generate_card.py` | 2 definitions today |
| Find safe_float defs | `grep -n "def safe_float" generate_card.py` | 3 today |
| Syntax check | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -c "import py_compile; py_compile.compile('generate_card.py', doraise=True)"` | exit 0 |
| Suite | `"C:/.../python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: `generate_card.py`; a small `test_pitch_names.py`.
**Out of scope**: the nested `sf`/`_sf` locals; any rating formula; the
`int`/`safe_int` work (plan 007). If plan 007 already added a module-level
`safe_int`, place the consolidated `safe_float` beside it.

## Steps

### Step 1: Single source for pitch names

Use the module-level `_PITCH_NAMES` (the complete 15-entry map) everywhere.
- Decide one canonical name. Simplest: keep `_PITCH_NAMES` at module scope and, in
  `pull_pitcher_statcast`, delete the local `PITCH_NAMES = {...}` block and replace
  references to `PITCH_NAMES` in that function with `_PITCH_NAMES`.
- Confirm the local map had no entry that `_PITCH_NAMES` lacks (it does not — the
  module map is a strict superset; the only difference is the missing `SP`).

**Verify**: `grep -n "PITCH_NAMES" generate_card.py` shows ONE definition
(`_PITCH_NAMES`) plus reference sites; `py_compile` exit 0; `pytest -q` all pass.

### Step 2: Single safe_float

Promote one `safe_float` to module scope (NaN-guarded, `default=0.0`):
```python
def safe_float(val, default=0.0):
    if val is None or (isinstance(val, float) and _math.isnan(val)):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
```
Remove the three nested `def safe_float(...)` definitions (lines ~549, 721, 1141)
so all call sites use the module-level one. **Watch the `:721` variant** — it had
NO default param; check its call sites still pass what they need or rely on the
new `default=0.0` (if any caller depended on a different default, preserve that at
the call site, not by reintroducing a second definition).

**Verify**: `grep -n "def safe_float" generate_card.py` → exactly 1; `py_compile`
exit 0; `pytest -q` all pass.

### Step 3: Test the SP→Splitter fix

Create `test_pitch_names.py` asserting the canonical map resolves the previously
divergent code:
```python
from generate_card import _PITCH_NAMES

def test_sp_resolves_to_splitter():
    assert _PITCH_NAMES["SP"] == "Splitter"

def test_known_codes_present():
    for code in ("FF", "SL", "CU", "CH", "FS", "KC", "KN"):
        assert code in _PITCH_NAMES
```
If you renamed the canonical map, import that name instead.

**Verify**: `pytest test_pitch_names.py -q` → 2 passed.

### Step 4: Full run

**Verify**: `pytest -q` → all pass.

## Test plan

- New `test_pitch_names.py` (2 tests) locking the canonical pitch map.
- The existing suite guards the `safe_float` consolidation (any behavior change
  would surface there).
- Verification: `pytest -q` all pass.

## Done criteria

- [ ] `grep -n "PITCH_NAMES" generate_card.py` → one definition.
- [ ] `grep -n "def safe_float" generate_card.py` → one definition (module scope).
- [ ] `_PITCH_NAMES["SP"] == "Splitter"` and it's the map used by `pull_pitcher_statcast`.
- [ ] `py_compile` exit 0; `pytest -q` all pass; `test_pitch_names.py` exists.
- [ ] No rating formula changed.
- [ ] `plans/README.md` status row for 009 updated.

## STOP conditions

- A `safe_float` call site relied on a default you can't preserve cleanly via the
  single definition — report it rather than reintroducing a duplicate.
- The local `PITCH_NAMES` turns out to have an entry the module map lacks
  (contradicts the excerpt) — STOP, the maps drifted further than documented.
- Any existing test fails after consolidation.

## Maintenance notes

- This is the cheap first slice of the larger `generate_card.py` refactor in
  `docs/superpowers/plans/2026-05-03-modular-refactor.md` (extract shared
  constants/utilities). The full split is deliberately NOT in scope.
- Reviewer: confirm only constants/utilities were consolidated and no formula or
  control flow moved.
