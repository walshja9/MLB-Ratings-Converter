# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Pre-OAA Fielding & Reactions Defects
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate all four bugs on unfixed `calculate_ratings()`
  - **Scoped PBT Approach**: Scope to concrete failing cases — use synthetic `data` dicts that isolate each bug condition
  - Write a test file (e.g. `test_pre_oaa_fielding.py`) that calls `calculate_ratings()` directly with minimal synthetic inputs
  - **Bug 1 case**: `rdrs_{year}=15`, no rngr/oaa/fg_def, `inn_{year}=400`. Assert `ratings["fielding"] >= 85`. Expect FAIL (~78 actual).
  - **Bug 3 case**: `rdrs_{year}=15`, no rngr/oaa, `inn_{year}=400`. Assert `ratings["reaction_right"] != pos_defaults["react_r"]`. Expect FAIL (flat default).
  - **Bug 4 case**: `rtot_{year}=10`, no innings key at all, no rngr/oaa. Assert `ratings["fielding"] != pos_baseline`. Expect FAIL (equals pos_baseline exactly).
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bugs exist)
  - Document the concrete counterexamples found (e.g. "Bug 1: fielding=78 for rdrs=15, expected ≥85")
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - OAA / RngR / FG Def Paths Unchanged
  - **IMPORTANT**: Follow observation-first methodology — run unfixed code first, record outputs, then encode as assertions
  - **Observe on UNFIXED code** (cases where `isBugCondition` returns false):
    - OAA path: random OAA values (−20 to +30), full innings → record fielding + all four reactions
    - RngR path: random RngR values (−15 to +20), full innings → record reactions
    - FG Def path: random FG Def values (−20 to +20) → record fielding
    - No-metrics path: empty `oaa_data` → record fielding = pos_baseline, reactions = flat defaults
    - Innings-present path: players with `inn_{year}` present → record def_trust calculation
  - Write property-based tests (use `hypothesis` or manual parametrize) asserting observed outputs hold for all non-buggy inputs
  - For each path: assert fixed output == original output (byte-for-byte identical)
  - Verify all preservation tests PASS on UNFIXED code before proceeding
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix pre-OAA fielding and reactions in `calculate_ratings()`

  - [x] 3.1 Define reaction slope constants at the top of the slopes block
    - Add a clearly-labelled constants section near the top of `calculate_ratings()` (or as module-level constants) so all four reaction slopes live in one place and are easy to retune after historical spot-checks
    - ```python
      # --- Pre-OAA reaction proxy slopes (tune here after spot-checks) ---
      RDRS_REACT_SLOPE = 1.2   # Rdrs as range proxy; weaker than RngR (2.0)
      RTOT_REACT_SLOPE = 1.0   # Rtot as range proxy; weakest signal
      ```
    - Similarly group the fielding slopes:
    - ```python
      # --- Pre-OAA fielding slopes (tune here after spot-checks) ---
      RDRS_FIELD_SLOPE     = 2.0   # recalibrated from current 2.0 — adjust after calibration
      RDRS_FIELD_INTERCEPT = 70    # intercept bump from 68
      RTOT_FIELD_SLOPE     = 1.8   # recalibrated from current 1.6; stays < RDRS slope
      RTOT_FIELD_INTERCEPT = 68
      RTOT_PARTIAL_TRUST   = 0.4   # fixed trust when innings data absent (Bug 4)
      ```
    - _Bug_Condition: isBugCondition(input) — bugs 1, 2, 3, 4_
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.2 Recalibrate Rdrs fielding slope (Bug 1)
    - Locate the `raw_fld = clamp(2.0 * rdrs_val + 68)` line in `calculate_ratings()`
    - Replace with `raw_fld = clamp(RDRS_FIELD_SLOPE * rdrs_val + RDRS_FIELD_INTERCEPT)`
    - Calibrate `RDRS_FIELD_SLOPE` / `RDRS_FIELD_INTERCEPT` so that rdrs=+15 with def_trust≈0.7 and SS pos_baseline≈65 yields FIELD in [85, 88]
    - _Bug_Condition: rdrs_val IS NOT NULL AND rngr_val IS NULL AND fg_def_val IS NULL AND NOT has_oaa_
    - _Expected_Behavior: ratings["fielding"] >= 85 for rdrs=+15_
    - _Requirements: 2.1_

  - [x] 3.3 Recalibrate Rtot fielding slope (Bug 2)
    - Locate the `raw_fld = clamp(1.6 * rtot_val + 68)` line
    - Replace with `raw_fld = clamp(RTOT_FIELD_SLOPE * rtot_val + RTOT_FIELD_INTERCEPT)`
    - Verify `RTOT_FIELD_SLOPE < RDRS_FIELD_SLOPE` (Rtot is coarser than DRS — guardrail)
    - _Bug_Condition: rtot_val IS NOT NULL AND rdrs_val IS NULL AND rngr_val IS NULL AND NOT has_oaa_
    - _Expected_Behavior: ratings["fielding"] > pre-fix value for positive Rtot; Rtot slope < Rdrs slope_
    - _Requirements: 2.2_

  - [x] 3.4 Add Rdrs/Rtot branch to reactions pipeline (Bug 3)
    - Find the `base_react` assignment block (after the `elif oaa_data:` OAA branch)
    - Add two new branches using the constants from 3.1:
    - ```python
      elif rdrs_val is not None:
          base_react = clamp(RDRS_REACT_SLOPE * rdrs_val + 65)
      elif rtot_val is not None:
          base_react = clamp(RTOT_REACT_SLOPE * rtot_val + 65)
      ```
    - Confirm these branches are ordered AFTER the RngR branch (RngR stays primary)
    - _Bug_Condition: (rdrs_val IS NOT NULL OR rtot_val IS NOT NULL) AND rngr_val IS NULL AND NOT has_oaa_
    - _Expected_Behavior: base_react is non-None; all four directional reactions differ from flat defaults when metric != 0_
    - _Preservation: RngR branch (`2.0 * RngR + 65`) must remain above these new branches in the elif chain_
    - _Requirements: 2.3, 3.2_

  - [x] 3.5 Apply non-zero def_trust when innings data is absent but Rtot is available (Bug 4)
    - Find the `def_trust = 0` (or `innings = 0`) path that fires when `has_innings_data` is False
    - Add a guard: when `has_innings_data` is False AND `rtot_val is not None`, set `def_trust = RTOT_PARTIAL_TRUST` instead of 0
    - The existing innings-based ramp (`max(0, min((innings - 50) / 450, 1.0))`) must remain unchanged for all players where innings data IS present
    - _Bug_Condition: rtot_val IS NOT NULL AND NOT has_inn AND NOT has_oaa AND rngr_val IS NULL_
    - _Expected_Behavior: def_trust = 0.4 (RTOT_PARTIAL_TRUST); ratings["fielding"] != pos_baseline when rtot != 0_
    - _Preservation: def_trust ramp for players with innings data is byte-for-byte unchanged_
    - _Requirements: 2.4, 3.4_

  - [x] 3.6 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Pre-OAA Fielding & Reactions Defects
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior; when it passes the fix is confirmed
    - Run all three bug-condition cases (Bug 1 fielding, Bug 3 reactions, Bug 4 def_trust)
    - **EXPECTED OUTCOME**: All assertions PASS
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - OAA / RngR / FG Def Paths Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run all preservation property tests (OAA, RngR, FG Def, no-metrics, innings-present paths)
    - **EXPECTED OUTCOME**: All tests PASS (no regressions on modern-era or FG Def paths)

- [x] 4. Integration spot-checks against known Show card values
  - Run `generate_card.py` for the integration players listed in the design and compare FIELD + reactions to known Show values
  - Ozzie Smith 1987 (SS): FIELD ≥ 85, reactions above SS flat defaults
  - Willie Mays 1954 (CF): FIELD meaningfully above CF baseline (75), not equal to it
  - Derek Jeter 2005 (SS, negative Rdrs): FIELD below SS baseline, reactions below SS defaults
  - Juan Soto 2025 (OAA era): FIELD and reactions byte-for-byte identical to pre-fix output
  - Xander Bogaerts 2022 (RngR era): FIELD and reactions byte-for-byte identical to pre-fix output
  - If any slope constant needs adjustment based on spot-check results, update the constant in the tuning block from task 3.1 only — do not scatter magic numbers elsewhere
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2_

- [x] 5. Checkpoint — Ensure all tests pass
  - Re-run the full test suite (exploration + preservation tests)
  - Confirm integration spot-checks are within acceptable range of known Show values
  - Ask the user if any slope constants need further tuning before closing the spec
