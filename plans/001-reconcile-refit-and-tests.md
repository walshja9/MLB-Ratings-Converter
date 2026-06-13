# Plan 001: Reconcile the 6/4 recalibration — make the 24 stale preservation tests pass and update the docs

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If
> anything in "STOP conditions" occurs, stop and report — do not improvise.
> When done, update the status row for plan 001 in `plans/README.md`.
> Do NOT `git commit` or `git push` — this is a public repo; the owner commits.
>
> **Drift check (run first)**:
> `git diff --stat bcfbd39..HEAD -- generate_card.py test_pre_oaa_fielding.py test_integration_spotchecks.py test_position_normalization_integration.py test_pre2015_speed_arm.py CLAUDE.md AGENTS.md`
> If any of those changed since this plan was written, compare the "Current
> state" excerpts below against the live code before proceeding; on a mismatch,
> treat it as a STOP condition.

## Status
- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: tests / docs
- **Planned at**: commit `bcfbd39`, 2026-06-13

## Why this matters

`generate_card.py` contains a deliberate, validated 6/4 recalibration (contact
R/L, power R/L, fielding OAA→FLD, Statcast speed, pitcher OVR). The recalibration
is real and intended — but the test suite still asserts the OLD coefficients, so
`pytest` reports **24 failures**, and `CLAUDE.md` + `AGENTS.md` document the old
(and mutually contradictory) formulas. A permanently-red suite means "tests pass"
carries no signal: a real regression is indistinguishable from this background
noise, and every other plan in this batch relies on a green baseline to verify
against. This plan makes the suite green by updating the stale preservation tests
to the current formulas, and makes the docs match the code.

**This plan changes tests and docs only. It does NOT change any rating formula in
`generate_card.py`.** The formulas in the working tree are treated as the source
of truth; the tests are wrong, not the code.

## Current state

### The 24 failing tests (all hardcode pre-6/4 coefficients)

Run `pytest -q` and you will see exactly these 24 failures (names abbreviated):

- `test_pre_oaa_fielding.py`:
  - `test_oaa_path_preservation_ss` (2 params)
  - `test_oaa_path_preservation_multipos` (6 params: 2B/3B/CF × 2)
  - `test_rngr_path_preservation_multipos` (2 params: CF × 2)
  - `test_fg_def_path_preservation` (4 params)
  - `test_fg_def_path_preservation_def_trust` (6 params)
- `test_integration_spotchecks.py`:
  - `TestJuanSoto2025::test_fielding_unchanged`
  - `TestXanderBogaerts2022::test_fielding_unchanged`
- `test_position_normalization_integration.py`:
  - `TestJuanSoto2025Preservation::test_fielding_unchanged`
- `test_pre2015_speed_arm.py`:
  - `test_statcast_speed_path_unchanged`

All of these assert *specific numeric outputs* that were correct before the refit.
They are "preservation"/"unchanged" tests: their intent is "this path's output
didn't change." The output legitimately DID change (that's the recalibration), so
the baselines must be updated.

### What is NOT failing (do not touch)

`test_pre_oaa_fielding.py` also contains `TestBug1RdrsFieldingSlope` and other
"bug condition exploration" classes whose docstrings say *"Failure is the SUCCESS
condition"* and *"DO NOT fix the code or the test when it fails."* These currently
**pass** (the bug they explored was fixed). Leave every passing test alone.

### The recalibrated formulas (source of truth — read these, do not change them)

`generate_card.py` — fielding from OAA (the dominant cause of the failures):
```python
# generate_card.py ~2058-2068 (per-position OAA->FLD intercepts, refit 6/4)
_FLD_OAA_INT = {"1B": 64, "LF": 64, "RF": 64, "OF": 64, "DH": 64,
                "2B": 70, "3B": 70, "SS": 73, "CF": 73, "C": 71}
fld_int = _FLD_OAA_INT.get(pos, 70)
# ...
raw_fld = clamp(1.65 * weighted_oaa + fld_int)   # was 2.09 * weighted_oaa + 74.6
```

`generate_card.py:402-405` — hitter OVR (now INCLUDES a fielding term):
```python
ovr = (0.8165 * core_hitting +
       0.1476 * overalls["fielding"] +
       0.0236 * ratings["speed"] +
       0.1957 * overalls["durability"])
ovr += _POS_OVR_ADJ.get(ratings.get("position", "OF"), 0)   # _POS_OVR_ADJ at line 414
```

`generate_card.py:434` — pitcher OVR:
```python
ovr = 1.074 * overalls["pitching"] + 4.6   # was 0.990 * pitching + 8.4
```

Contact/power refits (in `calculate_ratings`, ~lines 1947-2050): contact_right
`320.5*BA - 12.2` (was `268*BA + 4.8`); contact_left `251.9*BA + 5.8` (was
`212.7*BA + 18.7`); power_right `130.1*iso + 358.4*hr_rate_r + 30.4`; plus
platoon-aware `hr_rate_r`/`hr_rate_l` suppression. The Statcast speed formula in
`test_statcast_speed_path_unchanged` (`15.01*sprint - 353.5`) also changed — read
the live `speed` assignment in `calculate_ratings` to see the current form.

### Docs that are stale and contradictory

- `AGENTS.md:43` — `Fielding = 2.09 * OAA + 68.6` (old).
- `AGENTS.md:58-63` — hitter OVR `0.78*CoreHitting + 0.17*Fielding + 0.07*Speed + 0.16*Durability + 1.8` (old).
- `CLAUDE.md:47` (project-local `CLAUDE.md` in the repo root, NOT the global one) — hitter OVR `0.908*CoreHitting + 0.106*Speed + 0.192*Durability` (old AND missing the fielding term — contradicts AGENTS.md).
- `CLAUDE.md` pitcher OVR line — old `0.990*pitching + 8.4` style.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Run full suite | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest -q` | `167 passed` (0 failed) |
| Run one test file | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -m pytest test_pre_oaa_fielding.py -q` | all pass |
| Get one test's actual value | `"C:/Users/Alex/.../python.exe" -m pytest "test_pre_oaa_fielding.py::test_oaa_path_preservation_ss" -q` then read the assertion-error "actual" number | shows expected-vs-actual |

(All commands run from the project root. Substitute the full venv path everywhere
`python` is implied.)

## Scope

**In scope** (modify only these):
- `test_pre_oaa_fielding.py`
- `test_integration_spotchecks.py`
- `test_position_normalization_integration.py`
- `test_pre2015_speed_arm.py`
- `CLAUDE.md` (the repo-root one)
- `AGENTS.md`

**Out of scope** (do NOT touch):
- `generate_card.py` and every other `.py` that isn't a test listed above. The
  formulas are the source of truth — do not "fix" them to match the old tests.
- Any currently-passing test, especially the `TestBug1*` / "bug condition
  exploration" classes in `test_pre_oaa_fielding.py`.
- `app.py`, `expand_prospects.py`, prospect tests.

## Steps

### Step 1: Confirm the baseline

Run the full suite and confirm exactly 24 failures, all in the four test files
listed in Scope.

**Verify**: `pytest -q` → `24 failed, 143 passed`. If the count or the set of
failing files differs, STOP (the codebase has drifted).

### Step 2: Update each failing assertion to the value the current code produces

For each failing test, the safe mechanical procedure is:

1. Read the test to find what input it builds and what it asserts.
2. Run that single test; the assertion error prints the **actual** value the
   current (recalibrated) code produces.
3. Replace the hardcoded **expected** value (in the test or its `@pytest.mark.parametrize`
   tuple) with that actual value.
4. **Before accepting the new number, apply the ordinal sanity check in Step 3.**

For the parametrized fielding tests, the parametrize tuples encode expected
outputs (e.g. `test_oaa_path_preservation_ss[-5-58-49-67-61-52]` — the bracketed
values are the params/expectations). Update the expected fields in each tuple to
the current outputs. Where a test asserts a hard threshold (e.g.
`test_statcast_speed_path_unchanged` asserts `speed == clamp(max(15.01*30.0-353.5,15))`),
replace the inlined formula with the current formula from `generate_card.py`'s
`speed` assignment (read it; do not guess the coefficients).

### Step 3: Ordinal sanity check (this is the regression guard)

Updating a baseline to "whatever the code now outputs" can silently bake in a
real regression. For each test you touch, confirm the *relationships* still make
baseball sense:

- A more elite defender must still grade ≥ an average one ≥ a poor one
  (e.g. in `test_oaa_path_preservation_*`, the higher-OAA param must yield the
  higher FLD).
- A premium position (SS/CF) must not grade a clean glove *below* a corner
  (1B/LF) with the same OAA.
- The Statcast speed test: a 30.0 ft/s sprint must still produce an elite speed
  (≥ ~95 after clamp), not a mid value.

**If any ordinal relationship inverts or a value is obviously wrong (e.g. an
elite defender drops below 50), STOP and report** — that means the refit itself
has a bug, which is out of scope for this plan.

### Step 4: Update the docs to match the live formulas

Edit `AGENTS.md` and the repo-root `CLAUDE.md` so the formula tables match
`generate_card.py` exactly:

- Fielding (OAA path): `1.65 * OAA + per-position intercept` with the
  `_FLD_OAA_INT` table.
- Hitter OVR: `0.8165*CoreHitting + 0.1476*FieldingOVR + 0.0236*Speed + 0.1957*Durability + _POS_OVR_ADJ`.
- Pitcher OVR: `1.074 * PitchingOVR + 4.6`.
- Contact R/L and Power R/L: the current coefficients from `calculate_ratings`.

Make `AGENTS.md` and `CLAUDE.md` agree with each other (today they disagree on
the hitter OVR formula). Add a one-line note: "Coefficients last refit 6/4/2026;
keep this table in sync with `generate_card.py`."

### Step 5: Full green run

**Verify**: `pytest -q` → `167 passed` (0 failed, 0 error).

## Test plan

- No NEW test files. This plan repairs existing tests.
- After the change, the four edited test files must pass in full, and every
  previously-passing test must still pass (no net loss).
- Verification: `pytest -q` → `167 passed`.

## Done criteria

ALL must hold:
- [ ] `pytest -q` exits 0 with `167 passed`, 0 failed.
- [ ] `git diff --name-only` shows ONLY the 6 in-scope files changed (4 tests + 2 docs).
- [ ] `grep -n "2.09" AGENTS.md CLAUDE.md` returns nothing (old fielding coeff gone from docs).
- [ ] No formula constant in `generate_card.py` was changed (`git diff generate_card.py` is empty).
- [ ] Ordinal sanity check (Step 3) passed for every edited test.
- [ ] `plans/README.md` status row for 001 updated.

## STOP conditions

Stop and report (do not improvise) if:
- The baseline is not exactly 24 failures in the 4 named files (drift).
- Any ordinal relationship inverts when you plug in the current code's outputs
  (Step 3) — signals a real formula regression, out of scope here.
- Making a test pass appears to require editing `generate_card.py`.
- After updating baselines, the suite is still not fully green (some failure you
  can't trace to a stale coefficient) — report the residual failures.

## Maintenance notes

- These preservation tests are brittle by design (hardcoded magic numbers). A
  good follow-up (NOT in this plan) is converting them to ordinal/property
  assertions (elite > avg > poor, within tolerance) so the next recalibration
  doesn't re-break them. Left out here to keep risk low.
- After this lands and the owner commits, the uncommitted 6/4 refit in
  `generate_card.py` should be committed in the same logical change so code,
  tests, and docs move together. Flag this to the owner.
- A reviewer should scrutinize Step 3: confirm the new baselines preserve
  ordering, not just that the suite is green.
