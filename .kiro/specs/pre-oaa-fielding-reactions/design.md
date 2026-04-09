# Pre-OAA Fielding & Reactions Bugfix Design

## Overview

Three related bugs cause the historical defensive card to feel artificially soft for pre-OAA
players. The Rdrs (DRS) and Rtot (Total Zone) fielding slopes are too conservative, reactions
ignore Rdrs/Rtot entirely and fall to flat position defaults, and the `def_trust` factor
collapses to zero for pre-2003 players when innings data is absent — zeroing out Rtot even
when it is available and meaningful.

The fix recalibrates the Rdrs and Rtot slopes independently, extends the reactions pipeline
to use Rdrs/Rtot as a range proxy when RngR/OAA are unavailable, and introduces a non-zero
minimum trust for Rtot when innings data is missing. All OAA/RngR/FG Def paths are left
completely unchanged.

All changes are confined to `calculate_ratings()` in `generate_card.py`.

---

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger one of the three defects — see
  `isBugCondition` pseudocode below.
- **Property (P)**: The desired output behavior for inputs in C — see `expectedBehavior`
  pseudocode below.
- **Preservation**: All inputs NOT in C must produce identical output before and after the fix.
- **Rdrs**: Baseball-Reference DRS (Defensive Runs Saved), available 2003+. Stored as
  `rdrs_{year}` in `oaa_data`. Range roughly −20 to +25.
- **Rtot**: Baseball-Reference Total Zone, available pre-2003 (and sometimes alongside Rdrs).
  Stored as `rtot_{year}` in `oaa_data`. Range roughly −15 to +15.
- **RngR**: FanGraphs UZR range component, available 2003–2019. Stored as `rngr_{year}`.
  Primary reactions driver in the modern era.
- **OAA**: Outs Above Average (Statcast), available 2020+. Primary fielding and reactions
  driver in the Statcast era.
- **FG Def**: FanGraphs total defense metric. Primary fielding driver for 2003–2019 when
  available.
- **def_trust**: Innings-based confidence scalar (0.0–1.0) that blends the metric-driven
  rating with the position baseline. Currently zero when `has_innings_data` is False.
- **pos_baseline**: Position-specific default fielding rating used when no metric is available
  or when trust is zero.
- **base_react**: Intermediate scalar (0–99) derived from the best available range metric,
  before directional weights are applied.
- **calculate_ratings()**: The function in `generate_card.py` that computes all hitter
  attribute ratings from pulled stats data.

---

## Bug Details

### Bug Condition

The three bugs share a common structural pattern: the historical fallback lane (Rdrs/Rtot)
is either under-weighted or completely bypassed.

**Formal Specification:**
```
FUNCTION isBugCondition(data, target_year)
  INPUT: data dict (fielding_oaa, batting, etc.), target_year int
  OUTPUT: boolean

  oaa_data   := data.fielding_oaa
  has_oaa    := any integer key in oaa_data
  rngr_val   := oaa_data.get("rngr_" + target_year)
  fg_def_val := oaa_data.get("def_"  + target_year)
  rdrs_val   := oaa_data.get("rdrs_" + target_year)
  rtot_val   := oaa_data.get("rtot_" + target_year)
  inn_key    := "inn_" + target_year
  has_inn    := inn_key in oaa_data

  -- Bug 1: Rdrs slope too conservative
  bug1 := rdrs_val IS NOT NULL
          AND rngr_val IS NULL
          AND fg_def_val IS NULL
          AND NOT has_oaa

  -- Bug 2: Rtot slope too conservative
  bug2 := rtot_val IS NOT NULL
          AND rdrs_val IS NULL
          AND rngr_val IS NULL
          AND fg_def_val IS NULL
          AND NOT has_oaa

  -- Bug 3: Reactions ignore Rdrs/Rtot
  bug3 := (rdrs_val IS NOT NULL OR rtot_val IS NOT NULL)
          AND rngr_val IS NULL
          AND NOT has_oaa

  -- Bug 4: def_trust collapses to 0 for pre-2003 players without innings
  bug4 := rtot_val IS NOT NULL
          AND NOT has_inn
          AND NOT has_oaa
          AND rngr_val IS NULL

  RETURN bug1 OR bug2 OR bug3 OR bug4
END FUNCTION
```

### Examples

- **Bug 1 — Rdrs slope**: Ozzie Smith 1987 (SS, Rdrs ≈ +15). Current output: FIELD ≈ 78
  (`2.0 * 15 + 68`). Expected: FIELD ≈ 85–88.
- **Bug 2 — Rtot slope**: Willie Mays 1954 (CF, Rtot ≈ +12). Current output: FIELD ≈ 87
  (`1.6 * 12 + 68`). Expected: FIELD ≈ 82–86 (slightly softer than Rdrs given coarser metric).
- **Bug 3 — Reactions**: Ozzie Smith 1987 — FIELD is metric-driven but all four reactions
  land at flat SS defaults (react_l=55, react_r=80, react_f=80, react_b=70) because
  `base_react` is never set when RngR is absent.
- **Bug 4 — def_trust**: Any pre-2003 player with Rtot but no innings data. `def_trust = 0`,
  so `fielding = 0 * raw_fld + 1 * pos_baseline = pos_baseline`. Rtot is completely ignored.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- OAA-based fielding formula (`2.09 * OAA + 68.6`) must remain identical.
- OAA-based reactions (`1.5 * OAA + 65` → directional weights) must remain identical.
- RngR-based reactions (`2.0 * RngR + 65`) must remain the primary reactions driver when
  RngR is present, ahead of Rdrs/Rtot.
- FG Def fielding formula (`1.38 * FG_Def + 67.3`) must remain the primary fielding driver
  when FG Def is present, ahead of Rdrs/Rtot.
- `def_trust` blending logic for players WITH innings data must remain unchanged.
- DH-blend logic for low `field_pct` players must remain unchanged.
- Position baseline fallback for players with no defensive metrics at all must remain unchanged.

**Scope:**
All inputs where `isBugCondition` returns false must produce byte-for-byte identical output
from the fixed function. This covers:
- Any player with OAA data (2020+)
- Any player with RngR data (2003–2019 UZR era)
- Any player with FG Def data
- Any player with no defensive metrics at all (pure position baseline path)
- Any player with innings data present (def_trust path unchanged)

---

## Hypothesized Root Cause

1. **Rdrs slope calibrated against RngR, not Show FIELD values**: The `2.0 * Rdrs + 68`
   slope was likely chosen to mirror the RngR formula (`2.0 * RngR + 65`). But Rdrs (DRS)
   has a different distribution and relationship to Show FIELD than RngR does. A +15 DRS
   defender is elite and should map to ~85–88, not 78.

2. **Rtot slope further dampened without calibration data**: The `1.6 * Rtot + 68` slope
   applies an additional conservative haircut on top of the already-too-low Rdrs slope.
   Total Zone is noisier than DRS, but the intercept and slope still need independent
   calibration against known Show historical card values.

3. **Reactions pipeline has no Rdrs/Rtot branch**: The `base_react` assignment block only
   checks `rngr` and `oaa_data` integer keys. There is no `elif rdrs_val` or `elif rtot_val`
   branch. When both are absent, `base_react` stays `None` and the code falls through to
   flat position defaults unconditionally.

4. **def_trust hard-coded to 0 when `has_innings_data` is False**: The trust formula
   `max(0, min((innings - 50) / 450, 1.0))` requires `innings > 50`. When `has_innings_data`
   is False (pre-2003 BBRef data often lacks innings), `innings = 0` and `def_trust = 0`.
   This makes the Rtot branch in the fielding calculation a no-op: `0 * raw_fld + 1 * pos_baseline`.

---

## Correctness Properties

Property 1: Bug Condition — Rdrs Fielding Slope

_For any_ player where `isBugCondition` holds due to Bug 1 (Rdrs available, no RngR/OAA/FG Def),
the fixed `calculate_ratings()` SHALL produce a FIELD rating consistent with the recalibrated
slope such that a +15 Rdrs value maps to FIELD in [85, 88] and the output is strictly greater
than the pre-fix value (`2.0 * rdrs + 68`).

**Validates: Requirements 2.1**

Property 2: Bug Condition — Rtot Fielding Slope

_For any_ player where `isBugCondition` holds due to Bug 2 (Rtot available, no Rdrs/RngR/OAA/FG Def),
the fixed `calculate_ratings()` SHALL produce a FIELD rating consistent with the recalibrated
Rtot slope, with output strictly greater than the pre-fix value (`1.6 * rtot + 68`) for
positive Rtot values, and the slope SHALL be weaker than the Rdrs slope (reflecting lower
metric confidence).

**Validates: Requirements 2.2**

Property 3: Bug Condition — Reactions Use Rdrs/Rtot as Range Proxy

_For any_ player where `isBugCondition` holds due to Bug 3 (Rdrs or Rtot available, no RngR/OAA),
the fixed `calculate_ratings()` SHALL set `base_react` to a non-None value derived from
Rdrs or Rtot, and the four directional reaction ratings SHALL differ from the flat position
defaults whenever the metric value is non-zero.

**Validates: Requirements 2.3**

Property 4: Bug Condition — Non-Zero def_trust for Pre-2003 Players

_For any_ player where `isBugCondition` holds due to Bug 4 (Rtot available, no innings data),
the fixed `calculate_ratings()` SHALL apply a non-zero `def_trust` (capped below 1.0) so
that the FIELD rating is a blend of `raw_fld` and `pos_baseline`, and SHALL NOT equal
`pos_baseline` when `rtot_val != 0`.

**Validates: Requirements 2.4**

Property 5: Preservation — OAA/RngR/FG Def Paths Unchanged

_For any_ player where `isBugCondition` returns false (OAA, RngR, or FG Def is present, or
no metrics at all), the fixed `calculate_ratings()` SHALL produce exactly the same FIELD,
reaction_left, reaction_right, reaction_forward, and reaction_back values as the original
function.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Changes Required

**File**: `generate_card.py`

**Function**: `calculate_ratings()`

**Specific Changes:**

1. **Recalibrate Rdrs slope (Bug 1)**
   - Current: `raw_fld = clamp(2.0 * rdrs_val + 68)`
   - Fixed: `raw_fld = clamp(2.5 * rdrs_val + 68)`
   - Rationale: `2.5 * 15 + 68 = 105.5 → clamped 99` is too high; target is 85–88 for +15.
     Solve: `slope * 15 + 68 = 86.5` → `slope ≈ 1.23`. But def_trust < 1.0 for most
     historical players (limited innings data), so the effective output is
     `def_trust * raw_fld + (1 - def_trust) * pos_baseline`. The slope must be set
     accounting for typical def_trust values. With def_trust ≈ 0.7 and pos_baseline ≈ 65
     (SS), target 86: `0.7 * raw_fld + 0.3 * 65 = 86` → `raw_fld ≈ 95`.
     `slope * 15 + 68 = 95` → `slope ≈ 1.8`. Use **`2.0 * rdrs_val + 70`** as the
     recalibrated formula (intercept bump + modest slope increase). Exact slope TBD from
     calibration against known Show historical card values during implementation.

2. **Recalibrate Rtot slope (Bug 2)**
   - Current: `raw_fld = clamp(1.6 * rtot_val + 68)`
   - Fixed: Use a slope weaker than Rdrs but stronger than current, e.g.
     `raw_fld = clamp(1.8 * rtot_val + 68)`. Rtot is coarser than DRS so the slope
     stays below the Rdrs slope per the guardrail. Exact value TBD from calibration.

3. **Add Rdrs/Rtot branch to reactions pipeline (Bug 3)**
   - After the existing `elif oaa_data:` block that sets `base_react` from OAA, add:
   ```python
   elif rdrs_val is not None:
       # Rdrs as range proxy — weaker signal than RngR, so use a dampened slope
       base_react = clamp(1.2 * rdrs_val + 65)
   elif rtot_val is not None:
       # Rtot as range proxy — weakest signal, most conservative slope
       base_react = clamp(1.0 * rtot_val + 65)
   ```
   - The slopes are intentionally weaker than the RngR slope (`2.0 * RngR + 65`) per the
     guardrail that historical reaction influence stays weaker than true OAA/RngR-based reactions.

4. **Non-zero def_trust when innings data is absent but Rtot is available (Bug 4)**
   - Current: when `has_innings_data` is False, `innings = 0` → `def_trust = 0`.
   - Fixed: when `has_innings_data` is False AND `rtot_val is not None`, apply a fixed
     partial trust, e.g. `def_trust = 0.4`. This is capped well below 1.0 so Rtot helps
     without pretending it is as strong as measured modern data.
   - The existing trust ramp (`max(0, min((innings - 50) / 450, 1.0))`) is unchanged for
     all players where innings data IS present.

5. **Guard: Rdrs/Rtot reactions only when def_trust > 0**
   - The existing `if base_react is not None and def_trust > 0:` guard already handles this.
     With Bug 4 fixed, pre-2003 players will have `def_trust = 0.4`, so reactions will
     also benefit from the Rdrs/Rtot branch automatically.

---

## Testing Strategy

### Validation Approach

Two-phase: first run exploratory tests on the unfixed code to confirm the root cause and
surface concrete counterexamples, then run fix-checking and preservation tests on the fixed code.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug on unfixed code. Confirm or
refute the root cause analysis.

**Test Plan**: Construct minimal synthetic `data` dicts that isolate each bug condition and
call `calculate_ratings()` directly. Assert the expected (correct) output — these assertions
will FAIL on unfixed code, confirming the bug.

**Test Cases:**
1. **Rdrs slope test**: `rdrs_{year}=15`, no rngr/oaa/fg_def, innings=400. Assert
   `ratings["fielding"] >= 85`. Will fail on unfixed code (produces ~78).
2. **Rtot slope test**: `rtot_{year}=12`, no rdrs/rngr/oaa/fg_def, innings=400. Assert
   `ratings["fielding"] >= 82`. Will fail on unfixed code (produces ~87 — actually may
   pass; confirms Rtot slope is less broken than Rdrs for moderate values).
3. **Reactions fallback test**: `rdrs_{year}=15`, no rngr/oaa, innings=400. Assert
   `ratings["reaction_right"] != defaults["react_r"]`. Will fail on unfixed code.
4. **def_trust collapse test**: `rtot_{year}=10`, no innings data. Assert
   `ratings["fielding"] != pos_baseline`. Will fail on unfixed code.

**Expected Counterexamples:**
- Bug 1: FIELD ≈ 78 for +15 Rdrs (expected 85–88).
- Bug 3: All four reactions equal flat position defaults despite Rdrs=+15.
- Bug 4: FIELD equals pos_baseline exactly despite Rtot=+10.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function
produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := calculate_ratings_fixed(input)
  ASSERT expectedBehavior(result)
END FOR

FUNCTION expectedBehavior(result)
  -- Property 1
  IF bug1(input): ASSERT result.fielding > (2.0 * rdrs + 68) clamped
                  ASSERT result.fielding IN [85, 88] FOR rdrs=15
  -- Property 2
  IF bug2(input): ASSERT result.fielding > (1.6 * rtot + 68) clamped FOR rtot > 0
                  ASSERT Rtot_slope < Rdrs_slope
  -- Property 3
  IF bug3(input): ASSERT result.reaction_right != pos_defaults.react_r FOR metric != 0
  -- Property 4
  IF bug4(input): ASSERT result.fielding != pos_baseline FOR rtot != 0
END FUNCTION
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed
function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT calculate_ratings_original(input) == calculate_ratings_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended because:
- It generates many random OAA/RngR/FG Def values automatically.
- It catches edge cases (zero values, negative values, boundary innings) that manual tests miss.
- It provides strong guarantees that the modern-era paths are completely unaffected.

**Test Cases:**
1. **OAA preservation**: Random OAA values (−20 to +30), full innings. Assert FIELD and all
   four reactions are identical before and after fix.
2. **RngR preservation**: Random RngR values (−15 to +20), full innings. Assert reactions
   are identical. Assert FIELD uses FG Def or pos_baseline path (not reactions path).
3. **FG Def preservation**: Random FG Def values (−20 to +20). Assert FIELD is identical.
4. **No-metrics preservation**: Empty `oaa_data`. Assert FIELD = pos_baseline and reactions
   = flat defaults, identical before and after fix.
5. **def_trust with innings preservation**: Players with innings data present. Assert
   def_trust calculation is unchanged.

### Unit Tests

- `test_rdrs_slope_recalibrated`: rdrs=+15 → FIELD in [85, 88] after fix.
- `test_rtot_slope_recalibrated`: rtot=+12 → FIELD > pre-fix value, slope < Rdrs slope.
- `test_reactions_use_rdrs`: rdrs=+15, no rngr/oaa → reactions differ from flat defaults.
- `test_reactions_use_rtot`: rtot=+10, no rdrs/rngr/oaa → reactions differ from flat defaults.
- `test_def_trust_nonzero_no_innings`: rtot=+10, no innings → FIELD != pos_baseline.
- `test_def_trust_capped`: no innings → def_trust <= 0.5 (not pretending full confidence).
- `test_rdrs_negative`: rdrs=−10 → FIELD < pos_baseline (bad defender penalized).
- `test_rtot_zero`: rtot=0 → FIELD ≈ pos_baseline (average defender gets baseline).

### Property-Based Tests

- Generate random Rdrs values in [−20, +25]: fixed FIELD is always > pre-fix FIELD for
  positive values, and the slope is consistent (linear relationship holds).
- Generate random Rtot values in [−15, +15]: Rtot slope is always weaker than Rdrs slope
  for the same input magnitude.
- Generate random OAA values: output is byte-for-byte identical before and after fix
  (preservation property).
- Generate random RngR values: reactions output is byte-for-byte identical before and after
  fix (preservation property).
- Generate random (rdrs, rtot) pairs with no rngr/oaa: reactions are always non-default
  when the metric is non-zero and def_trust > 0.

### Integration Tests

- **Ozzie Smith 1987** (SS, elite Rdrs): FIELD ≥ 85, reactions above SS defaults.
- **Willie Mays 1954** (CF, strong Rtot, no innings data): FIELD meaningfully above CF
  baseline (75), not equal to it.
- **Derek Jeter 2005** (SS, Rdrs negative): FIELD below SS baseline, reactions below SS
  defaults — penalty applies correctly.
- **Juan Soto 2025** (OAA era): FIELD and reactions unchanged from pre-fix output.
- **Xander Bogaerts 2022** (RngR era): FIELD and reactions unchanged from pre-fix output.
