# Plan 010: Make the ValuCast input path configurable and warn loudly when it's missing

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 010 row in `plans/README.md`. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `git diff --stat bcfbd39..HEAD -- expand_prospects.py`
> Confirm the excerpts below match the live code; on a mismatch, STOP.

## Status
- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt

## Why this matters

`expand_prospects.py` hardcodes an absolute, machine-specific path to its main
data input (`C:/Users/Alex/DDLensAdapter/data/valucast_prospect_model_inputs.json`),
and loads it through a wrapper that **silently** returns an empty default when the
file is missing. On any other machine — or if that sibling project moves — the
prospect builder produces empty stat-derived data with no error, and debugging
means tracing through the silent loader. Making the path configurable via env var
and emitting a clear warning when the file is absent removes a silent-failure trap.

## Current state

`expand_prospects.py:21`:
```python
VALUCAST_INPUTS = "C:/Users/Alex/DDLensAdapter/data/valucast_prospect_model_inputs.json"
```
Usage — `expand_prospects.py:489`:
```python
    valucast_doc = _load_json_optional(VALUCAST_INPUTS, {})
```
The silent loader — `expand_prospects.py:855-866`:
```python
def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_json_optional(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        return _load_json(path)
    except OSError:
        return default
```
`os` and `json` are already imported (the loader uses `os.path.exists`).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Syntax check | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -c "import py_compile; py_compile.compile('expand_prospects.py', doraise=True)"` | exit 0 |
| Suite (prospect tests) | `"C:/.../python.exe" -m pytest test_expand_prospects.py -q` | all pass |
| Full suite | `"C:/.../python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: `expand_prospects.py` (the constant + a one-line warning at the load
site); a short note in `HANDOFF.md`'s "Run" section.
**Out of scope**: the loader's general behavior for other optional files (keep
`_load_json_optional` silent for genuinely-optional inputs); the `MIN_*`
calibration knobs; any grading logic.

## Steps

### Step 1: Env-var override with the current path as default

Change line 21 to:
```python
VALUCAST_INPUTS = os.environ.get(
    "VALUCAST_INPUTS",
    "C:/Users/Alex/DDLensAdapter/data/valucast_prospect_model_inputs.json",
)
```
(Confirm `os` is imported at the top of the file — it is, since the loader uses
`os.path.exists`. If for some reason the import is below line 21, move the import
up or compute the constant after the import.)

**Verify**: `py_compile` exit 0.

### Step 2: Warn when the input is missing

At the load site (line ~489), make the absence explicit instead of silent.
Target shape:
```python
    if not os.path.exists(VALUCAST_INPUTS):
        import sys
        print(
            f"WARNING: ValuCast inputs not found at {VALUCAST_INPUTS}; "
            f"stat-derived prospects will be empty. "
            f"Set the VALUCAST_INPUTS env var to override.",
            file=sys.stderr,
        )
    valucast_doc = _load_json_optional(VALUCAST_INPUTS, {})
```
Keep `_load_json_optional` itself unchanged (other callers may rely on its silent
behavior).

**Verify**: `pytest test_expand_prospects.py -q` → all pass.

### Step 3: Document it

Add to `HANDOFF.md` "Run" section (or create a one-line note near the rebuild
command): "`expand_prospects.py` reads ValuCast inputs from `$VALUCAST_INPUTS`
(defaults to the DDLensAdapter path). It warns to stderr if the file is missing."

**Verify**: `grep -n "VALUCAST_INPUTS" HANDOFF.md` → match.

### Step 4: Full run

**Verify**: `pytest -q` → all pass.

## Test plan

- The existing `test_expand_prospects.py` already exercises the builder functions
  with in-memory data (not the file), so it must remain green.
- Optional (only if quick and stable): a test that sets `VALUCAST_INPUTS` to a
  nonexistent path and asserts `_load_json_optional(path, {}) == {}` — but since
  `VALUCAST_INPUTS` is read at import time, prefer testing `_load_json_optional`
  directly with a bogus path rather than re-importing the module. If clean, add
  it; if it requires import gymnastics, skip and note it.

## Done criteria

- [ ] `VALUCAST_INPUTS` reads from the env var with the old path as default.
- [ ] A missing input file prints a stderr WARNING (not silent).
- [ ] `py_compile expand_prospects.py` exit 0; `pytest -q` all pass.
- [ ] `HANDOFF.md` documents the env var.
- [ ] `git diff --name-only` shows only `expand_prospects.py` + `HANDOFF.md`.
- [ ] `plans/README.md` status row for 010 updated.

## STOP conditions

- `os` is not imported before line 21 and cannot be cleanly moved — report.
- `expand_prospects.py` drifted from the excerpts.
- Any prospect test fails after the change.

## Maintenance notes

- This is a single-input fix. If more sibling-project paths get hardcoded later,
  generalize to a small config block at the top of the file.
- Reviewer: confirm `_load_json_optional` was left untouched (still silent for
  other optional inputs) and only the ValuCast site gained the warning.
