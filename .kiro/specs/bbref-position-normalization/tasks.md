# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Non-Canonical BBRef Position String Bug
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate `pos_map` silently falls through to `"OF"` for all non-canonical inputs
  - **Scoped PBT Approach**: Scope to the concrete failing cases — call `pos_map.get(raw, "OF")` directly (simulating the unfixed path) for each buggy input
  - Write a test file `test_bbref_position_normalization.py` that imports `pos_map` from `generate_card.py` and asserts the expected canonical result for each buggy input
  - **Bug case — asterisk**: `pos_map.get("*1B", "OF")` → assert `== "1B"`. Expect FAIL (`"OF"` actual).
  - **Bug case — slash composite**: `pos_map.get("1B/OF", "OF")` → assert `== "1B"`. Expect FAIL.
  - **Bug case — hyphen composite**: `pos_map.get("1B-2B", "OF")` → assert `== "1B"`. Expect FAIL.
  - **Bug case — outfield alias**: `pos_map.get("LF-RF", "OF")` → assert `== "LF"`. Expect FAIL.
  - **Bug case — asterisk SS**: `pos_map.get("*SS", "OF")` → assert `== "SS"`. Expect FAIL.
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bug exists)
  - Document counterexamples found (e.g. `"*1B" → "OF"` instead of `"1B"`)
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Canonical Pass-Through and position_override Wins
  - **IMPORTANT**: Follow observation-first methodology — run unfixed code first, record outputs, then encode as assertions
  - **Observe on UNFIXED code** (cases where `isBugCondition` returns false):
    - Canonical pass-through: for each of `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH}`, call `pos_map.get(x, "OF")` and record that it returns `x` unchanged
    - position_override path: call `calculate_ratings(data, position_override="SS")` with `data["position"] = "*1B"` and record that `ratings["position"] == "SS"`
    - Unresolvable fallback: call `pos_map.get("XYZ", "OF")` and record that it returns `"OF"`
  - Write property-based tests asserting all nine canonical strings pass through unchanged
  - Write a test asserting `position_override` wins even when `data["position"]` is a messy scraped BBRef string (e.g. `"*1B"`)
  - Write a test asserting unresolvable strings still fall back to `"OF"`
  - Verify all preservation tests PASS on UNFIXED code before proceeding
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix BBRef position normalization in `generate_card.py`

  - [x] 3.1 Implement `normalize_position()` function
    - Add the function near the top of `generate_card.py`, just before `pull_career_fielding()`
    - ```python
      CANONICAL_POSITIONS = {"RF", "LF", "CF", "1B", "2B", "SS", "3B", "C", "DH"}

      def normalize_position(raw):
          """Map a raw BBRef Pos string to a canonical position token."""
          if not raw:
              return "OF"
          s = raw.strip()
          if s.startswith("*"):
              s = s[1:]
          if "/" in s:
              s = s.split("/")[0]
          if "-" in s:
              s = s.split("-")[0]
          s = s.strip()
          if s in CANONICAL_POSITIONS:
              return s
          if s == "OF":
              return "CF"
          return "OF"
      ```
    - _Bug_Condition: isBugCondition(raw) — raw starts with `*`, contains `/` or `-`, or is a generic outfield alias_
    - _Expected_Behavior: normalize_position(raw) returns a member of CANONICAL_POSITIONS ∪ {"OF"}, never "OF" for a recognizable infield position_
    - _Preservation: canonical inputs pass through unchanged; position_override path in calculate_ratings() is untouched_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.2 Apply `normalize_position()` at the `best_pos` assignment in `pull_career_fielding()`
    - Locate the line `best_pos = pos_val` inside the `if inn > best_inn and pos_val not in ("DH", ""):` block
    - Replace with `best_pos = normalize_position(pos_val)`
    - No changes to `pos_map` or `calculate_ratings()`
    - _Bug_Condition: pos_val contains a non-canonical BBRef string_
    - _Expected_Behavior: data["position"] is already canonical when calculate_ratings() receives it_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Non-Canonical BBRef Position String Bug
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 now calls `normalize_position()` instead of `pos_map.get()` directly
    - Update the test to call `normalize_position(raw)` and assert the canonical result
    - **EXPECTED OUTCOME**: All assertions PASS (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Canonical Pass-Through and position_override Wins
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run all preservation tests: canonical pass-through, position_override wins, unresolvable fallback
    - **EXPECTED OUTCOME**: All tests PASS (no regressions)

- [x] 4. Integration spot-checks against known players
  - Run `generate_card.py` for the integration players listed in the design and verify position and position-dependent defaults
  - **Nap Lajoie 1901** (`*1B`): assert `ratings["position"] == "1B"` and arm/reaction defaults match `1B` baselines, not `OF` baselines
  - **Slash-composite player** (e.g. a player with `1B/OF`): assert the infield position wins (`"1B"`)
  - **position_override wins over messy scraped position**: run with `--position LF` for a player whose scraped position is `*1B`; assert `ratings["position"] == "LF"`
  - **Modern-era player (OAA era)**: run Juan Soto 2025 and confirm output is byte-for-byte identical to pre-fix output (no regression)
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

- [x] 5. Checkpoint — Ensure all tests pass
  - Re-run the full test suite (exploration + preservation tests)
  - Confirm integration spot-checks match expected position and defaults
  - Ask the user if any edge cases need further coverage before closing the spec
