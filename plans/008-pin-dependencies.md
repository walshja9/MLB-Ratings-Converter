# Plan 008: Pin dependencies and add a reproducible lockfile

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 008 row in `plans/README.md`. Do NOT `git commit`/`push`.
> Do NOT run `pip install` of new/upgraded packages — only read what's installed.
>
> **Drift check (run first)**: `cat requirements.txt`
> Confirm it still uses `>=` floors as in "Current state"; if already pinned, this
> plan may be partly done — reconcile.

## Status
- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dependencies

## Why this matters

`requirements.txt` pins only floors (`flask>=3.0`, `pandas>=2.1`, `pybaseball>=2.2`,
`lxml>=5.0`, ...). A fresh install resolves to whatever is newest, so builds are
non-reproducible and a breaking major (pandas 3.x changing `read_html`, a numpy
ABI bump, a `pybaseball`/`cloudscraper` change) can silently break the app or the
scrapers — and those last two are the most fragile, highest-churn deps and sit on
the only data path. A lockfile capturing the currently-working versions makes the
environment reproducible.

## Current state

`requirements.txt`:
```
flask>=3.0
numpy>=1.26
pandas>=2.1
lxml>=5.0
pybaseball>=2.2
cloudscraper>=1.2
scipy>=1.11
```
No lockfile, no upper bounds, no dev requirements. The working interpreter is the
shared venv at
`C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Capture installed versions | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pip freeze` | full resolved list |
| Show one package version | `"C:/.../python.exe" -m pip show <pkg>` | version line |
| Suite | `"C:/.../python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: `requirements.txt` (add upper bounds), create `requirements.lock`.
**Out of scope**: upgrading/downgrading any package; creating a new venv; CI
changes (plan 003 owns CI — but if 003 already landed, you MAY add a `pip-audit`
step as noted in Maintenance, optional).

## Steps

### Step 1: Capture the known-good resolved set

Run `pip freeze` in the shared venv and save the FULL output to
`requirements.lock` (verbatim, with `==` pins). Add a header comment:
```
# Locked resolved environment captured 2026-06-13 from the working venv.
# Reproduce with: pip install -r requirements.lock
# Regenerate with: pip freeze > requirements.lock
```
**Verify**: `requirements.lock` exists and contains `==`-pinned `flask`, `pandas`,
`numpy`, `lxml`, `pybaseball`, `cloudscraper`, `scipy` lines.

### Step 2: Add tested upper bounds to requirements.txt

For each direct dependency, read its installed version (`pip show`) and add an
upper bound at the next major above the installed one, keeping the existing floor.
Example shape (use the ACTUAL installed majors, do not copy these blindly):
```
flask>=3.0,<4
numpy>=1.26,<3
pandas>=2.1,<3
lxml>=5.0,<6
pybaseball>=2.2,<3
cloudscraper>=1.2,<2
scipy>=1.11,<2
```
The intent: a fresh install can still patch/minor-upgrade but won't silently jump
a major you haven't tested.

**Verify**: `requirements.txt` parses — `"C:/.../python.exe" -m pip install --dry-run -r requirements.txt`
should resolve without error (dry-run does not install; if `--dry-run` is
unsupported in this pip, skip this check and rely on Step 3).

### Step 3: Confirm the suite still passes (no install performed)

Because you did NOT change the installed environment, the suite must still pass.
**Verify**: `pytest -q` → all pass.

## Test plan

- No application tests. Verification is: lockfile exists with `==` pins, the
  capped `requirements.txt` parses, and the suite still passes on the unchanged
  environment.

## Done criteria

- [ ] `requirements.lock` exists with `==` pins for all 7 direct deps (plus transitives from freeze).
- [ ] `requirements.txt` has `<major` upper bounds on every direct dep, floors preserved.
- [ ] `pytest -q` exits 0.
- [ ] `plans/README.md` status row for 008 updated.

## STOP conditions

- `pip freeze` output is empty or missing the core packages (wrong interpreter) —
  STOP and confirm the venv path.
- The capped `requirements.txt` fails to resolve in `--dry-run` — relax the bound
  that conflicts and report.

## Maintenance notes

- If plan 003's CI is in place, add `pip install pip-audit && pip-audit` as a
  non-blocking CI step to surface advisories on the locked set (optional, note as
  follow-up if not done here).
- `pybaseball` and `cloudscraper` break when upstream sites change; the durable
  mitigation is the local-cache work in `AGENTS.md` "Next Steps" — out of scope.
- Reviewer: confirm no package was actually upgraded/downgraded (the lock reflects
  what was already installed).
