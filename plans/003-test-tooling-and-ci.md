# Plan 003: Add pytest config, a shared conftest, a one-command runner, and CI

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 003 row in `plans/README.md`. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `git diff --stat bcfbd39..HEAD -- . :^plans`
> Confirm the test files still start with manual `sys.path.insert` blocks (see
> "Current state"); if the layout changed materially, STOP.

## Status
- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: 001 (a CI gate is only meaningful once the suite is green)
- **Category**: dx

## Why this matters

Today there is no `pytest.ini`, no `conftest.py`, no CI, and no documented
one-command test invocation — running the suite requires knowing the sibling
project's venv path from `CLAUDE.md`. Six of twelve test files hand-roll
`sys.path.insert(0, ...)` to import the project. A contributor or agent cannot
answer "is this working?" without tribal knowledge, and nothing prevents a red
suite from being pushed. This plan makes the suite runnable and gated with one
command.

## Current state

- No `pytest.ini`, `setup.cfg`, `pyproject.toml`, `conftest.py`, or `.github/`
  directory exists (confirm with `ls`).
- Test files that manually insert the project root onto `sys.path` include
  `test_prospect_routes.py:5-6`, `test_prospect_store.py:5-6`,
  `test_scrape_prospects.py:5-7` (and three others). Pattern:
  ```python
  import sys, os
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  ```
- Tests are named `test_*.py` and live in the repo root (flat layout).
- The interpreter is the shared venv:
  `C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe`.
- `requirements.txt` exists but has no test-only deps (`pytest` is installed in
  the shared venv but not declared anywhere).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Run suite (current) | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q` | all pass |
| Confirm config picked up | `"C:/.../python.exe" -m pytest --co -q` | collects all `test_*.py` |

## Scope

**In scope** (create):
- `pytest.ini`
- `conftest.py`
- `requirements-dev.txt`
- `.github/workflows/tests.yml`
- A short "Running tests" section appended to `README.md`

**Optionally in scope** (only if trivial and safe): removing the now-redundant
`sys.path.insert` blocks from the test files once `conftest.py` makes them
unnecessary. If removing them risks breaking import in any runner, leave them —
they're harmless with conftest present.

**Out of scope**:
- Any source `.py` change, any test logic change.
- Switching off the shared venv / creating a new venv (that's a bigger DX call;
  document it as a follow-up, don't do it here).

## Steps

### Step 1: pytest.ini

Create `pytest.ini` so config is centralized:
```ini
[pytest]
testpaths = .
python_files = test_*.py
addopts = -q
# Exclude isolated worktrees from collection
norecursedirs = .git .claude __pycache__ *.egg-info venv env
```
**Verify**: `pytest --co -q` collects the same test set as before (no tests from
`.claude/worktrees/*`). Compare the collected count to a plain run.

### Step 2: conftest.py

Create a root `conftest.py` that puts the project root on `sys.path` once:
```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```
**Verify**: `pytest -q` → all pass.

### Step 3: requirements-dev.txt

Create `requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
```
**Verify**: file exists; `pytest --version` reports a 8.x interpreter in the
shared venv (informational).

### Step 4: CI workflow

Create `.github/workflows/tests.yml` that installs deps and runs the suite on
push/PR. Because the data path depends on fragile scrapers (`pybaseball`,
`cloudscraper`) and live network, the suite must run **offline** — the existing
tests use synthetic fixtures, so this should work, but if any test reaches the
network in CI, mark it to skip there rather than weakening it.
```yaml
name: tests
on:
  push:
  pull_request:
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: pytest -q
```
**Verify**: YAML parses (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/tests.yml'))"`
→ no error). Actual CI run happens after the owner pushes.

### Step 5: README "Running tests" section

Append to `README.md` a short section with the exact one-command invocation
(the full venv path) and `pip install -r requirements-dev.txt`.

**Verify**: `grep -n "Running tests" README.md` → match.

## Test plan

- No new application tests; this plan is harness/config only.
- Verification is that the existing suite collects and passes identically through
  the new config: `pytest -q` → all pass, and `pytest --co -q` count unchanged.

## Done criteria

- [ ] `pytest.ini`, `conftest.py`, `requirements-dev.txt`, `.github/workflows/tests.yml` exist.
- [ ] `pytest -q` exits 0 with the same number of tests as before this plan.
- [ ] `pytest --co -q` does NOT collect anything under `.claude/worktrees/`.
- [ ] No source/test logic file was modified (only optional `sys.path.insert` removals).
- [ ] `README.md` documents the one-command test invocation.
- [ ] `plans/README.md` status row for 003 updated.

## STOP conditions

- The new `pytest.ini` changes which tests are collected (count differs) — adjust
  `norecursedirs`/`testpaths`, and if it still differs, STOP and report.
- Any test reaches the live network under the CI config and can't be cleanly
  skipped — report rather than disabling tests.

## Maintenance notes

- Follow-up (deferred): give this project its own venv instead of borrowing the
  Robert Stock one, and pin exact versions (see plan 008). Documented, not done.
- If tests are later moved into a `tests/` dir, update `testpaths`.
- Reviewer: confirm CI runs offline and the collected test count matches local.
