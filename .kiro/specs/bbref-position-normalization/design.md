# BBRef Position Normalization Bugfix Design

## Overview

Baseball-Reference returns non-canonical position strings — leading asterisks (`*1B`),
slash-separated composites (`1B/OF`), hyphen-separated composites (`1B-2B`), and generic
outfield aliases (`OF`, `LF-RF`) — that `generate_card.py`'s `pos_map` dict does not
recognize. Any unrecognized string falls through to `"OF"`, corrupting arm defaults,
directional reactions, bunt/drag defaults, and the overall feel of the card for infield
players like Nap Lajoie.

The fix is a single `normalize_position()` function inserted in `pull_career_fielding()`
at the point where `best_pos` is stored, before it ever reaches `calculate_ratings()`.
The `pos_map` lookup in `calculate_ratings()` is left untouched.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — `best_pos` contains a
  non-canonical BBRef position string that `pos_map` cannot match.
- **Property (P)**: The desired behavior — `normalize_position()` returns a member of the
  canonical set `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH, OF}` for every possible input.
- **Preservation**: The existing behavior that must not change — canonical inputs pass
  through unchanged, and `position_override` continues to win over any scraped value.
- **normalize_position(raw)**: The new function in `generate_card.py` that maps a raw
  BBRef position string to a canonical token before `pos_map` sees it.
- **best_pos**: The variable in `pull_career_fielding()` that tracks the position with
  the most innings played; the value ultimately stored in `data["position"]`.
- **pos_map**: The dict in `calculate_ratings()` that maps canonical strings to
  themselves and falls back to `"OF"` for anything unrecognized.
- **CANONICAL_SET**: `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH}` — the nine values `pos_map`
  recognizes. `"OF"` is the fallback, not a member of the input set.

## Bug Details

### Bug Condition

The bug manifests when `pull_career_fielding()` stores a `best_pos` value that contains
a leading asterisk, a slash separator, a hyphen separator, or a generic outfield alias.
`calculate_ratings()` receives that raw string, `pos_map.get(raw, "OF")` returns `"OF"`,
and all position-dependent defaults are set to generic outfield values.

**Formal Specification:**
```
FUNCTION isBugCondition(raw)
  INPUT: raw — the string value of best_pos from pull_career_fielding()
  OUTPUT: boolean

  IF raw STARTS WITH "*"                          THEN RETURN true   -- e.g. *1B
  IF raw CONTAINS "/"                             THEN RETURN true   -- e.g. 1B/OF
  IF raw CONTAINS "-"                             THEN RETURN true   -- e.g. 1B-2B, LF-RF
  IF raw IN {"OF", "LF/CF", "CF-RF", "LF-RF"}    THEN RETURN true   -- outfield aliases
  RETURN false
END FUNCTION
```

### Examples

| Raw BBRef string | Current (buggy) result | Expected result |
|-----------------|----------------------|-----------------|
| `*1B`           | `OF`                 | `1B`            |
| `1B/OF`         | `OF`                 | `1B`            |
| `1B-2B`         | `OF`                 | `1B`            |
| `OF`            | `OF` (correct label, wrong player — infielder gets OF defaults) | `CF` (outfield default) |
| `LF-RF`         | `OF`                 | `LF`            |
| `CF-RF`         | `OF`                 | `CF`            |
| `LF/CF`         | `OF`                 | `LF`            |
| `*SS`           | `OF`                 | `SS`            |
| `RF`            | `RF` ✓               | `RF` (unchanged)|

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Already-canonical position strings (`RF`, `LF`, `CF`, `1B`, `2B`, `SS`, `3B`, `C`,
  `DH`) must pass through `normalize_position()` and produce the identical string.
- When `position_override` is supplied (via `--position` CLI flag or the
  `position_override` parameter to `calculate_ratings()`), it must continue to win over
  `data["position"]` regardless of how messy the scraped BBRef string is. The line
  `pos = position_override or data.get("position") or "OF"` must remain semantically
  unchanged.
- Strings that cannot be resolved to any canonical position after all normalization steps
  must continue to fall back to `"OF"`.

**Scope:**
All inputs that do NOT match the bug condition (i.e., already-canonical strings and the
`position_override` path) must be completely unaffected by this fix.

## Hypothesized Root Cause

The root cause is a missing normalization step between data ingestion and the `pos_map`
lookup. Specifically:

1. **No asterisk stripping**: BBRef uses a leading `*` to denote a player's primary
   position when they played multiple positions. `pos_map` has no `"*1B"` key, so it
   falls through to `"OF"`.

2. **No composite splitting**: BBRef uses `/` and `-` to express multi-position seasons
   (e.g., `1B/OF`, `1B-2B`). `pos_map` has no composite keys, so all composites fall
   through to `"OF"`.

3. **No outfield alias table**: Generic `"OF"` and composite outfield strings like
   `"LF-RF"` are not mapped to specific outfield positions. The fallback `"OF"` happens
   to produce the right label but assigns generic outfield defaults rather than the most
   specific canonical outfield position.

4. **Fix location**: The normalization must happen in `pull_career_fielding()` at the
   `best_pos` assignment, not inside `pos_map`, so that `data["position"]` is already
   clean when `calculate_ratings()` receives it.

## Correctness Properties

Property 1: Bug Condition — Normalized Position Is Canonical

_For any_ raw BBRef position string where `isBugCondition(raw)` returns true, calling
`normalize_position(raw)` SHALL return a value that is a member of the canonical set
`{RF, LF, CF, 1B, 2B, SS, 3B, C, DH, OF}`, and SHALL NOT return `"OF"` when the raw
string encodes a recognizable infield or specific outfield position.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation — Canonical Inputs Pass Through Unchanged

_For any_ raw position string where `isBugCondition(raw)` returns false (i.e., the string
is already a member of `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH}`), calling
`normalize_position(raw)` SHALL return the identical string, preserving all existing
position-dependent defaults for players whose BBRef data is already clean.

**Validates: Requirements 3.1, 3.2**

Property 3: Preservation — position_override Wins Over Messy Scraped Position

_For any_ call to `calculate_ratings(data, position_override=X)` where `X` is a
canonical position string and `data["position"]` is any string (including malformed BBRef
values), the resulting `ratings["position"]` SHALL equal `X`, proving that the override
path is unaffected by the normalization change.

**Validates: Requirement 3.3**

## Fix Implementation

### Changes Required

**File**: `generate_card.py`

**New Function** (insert near the top of the data-pulling section, before
`pull_career_fielding`):

```
FUNCTION normalize_position(raw)
  INPUT: raw — string from BBRef Pos column
  OUTPUT: canonical position string

  IF raw IS None OR raw IS empty  THEN RETURN "OF"

  s = raw.strip()

  -- Step 1: strip leading asterisk
  IF s STARTS WITH "*"  THEN s = s[1:]

  -- Step 2: split on "/" or "-", take first token
  IF s CONTAINS "/"  THEN s = s.split("/")[0]
  IF s CONTAINS "-"  THEN s = s.split("-")[0]

  s = s.strip()

  -- Step 3: check canonical set (fast path)
  CANONICAL = {RF, LF, CF, 1B, 2B, SS, 3B, C, DH}
  IF s IN CANONICAL  THEN RETURN s

  -- Step 4: outfield alias table
  OF_ALIASES = {OF -> CF, LF -> LF, CF -> CF, RF -> RF}
  -- (LF, CF, RF already caught by CANONICAL above)
  -- Generic "OF" with no specific token defaults to CF
  IF s == "OF"  THEN RETURN "CF"

  -- Step 5: unresolvable — preserve existing fallback
  RETURN "OF"
END FUNCTION
```

**Modification in `pull_career_fielding()`**:

```
-- Existing code (around line where best_pos is assigned):
IF inn > best_inn AND pos_val NOT IN ("DH", "")
  best_inn = inn
  best_pos = pos_val          -- BEFORE: raw BBRef string stored here

-- After fix:
IF inn > best_inn AND pos_val NOT IN ("DH", "")
  best_inn = inn
  best_pos = normalize_position(pos_val)   -- normalize at storage point
```

No changes to `calculate_ratings()` or `pos_map`.

### Outfield Alias Resolution Detail

When the first token after splitting is an outfield indicator, use the most specific
canonical token available:

| First token | Result |
|-------------|--------|
| `LF`        | `LF`   |
| `CF`        | `CF`   |
| `RF`        | `RF`   |
| `OF`        | `CF`   (generic outfield defaults to CF) |

This means `LF-RF` → split on `-` → first token `LF` → canonical → `LF`. The outfield
alias table is only needed for the bare `OF` case after splitting.

## Testing Strategy

### Validation Approach

Two-phase: first run exploratory tests on the unfixed code to confirm the bug and root
cause, then verify the fix with unit, property-based, and integration tests.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples on unfixed code to confirm the root cause before
implementing the fix.

**Test Plan**: Call `pos_map.get(raw, "OF")` directly (simulating the unfixed path) for
each buggy input and assert the result is NOT `"OF"`. These assertions will fail on
unfixed code, confirming the bug.

**Test Cases**:
1. `pos_map.get("*1B", "OF")` → expect `"1B"`, observe `"OF"` (will fail on unfixed code)
2. `pos_map.get("1B/OF", "OF")` → expect `"1B"`, observe `"OF"` (will fail)
3. `pos_map.get("1B-2B", "OF")` → expect `"1B"`, observe `"OF"` (will fail)
4. `pos_map.get("OF", "OF")` → observe `"OF"` — ambiguous; confirms alias table needed
5. `pos_map.get("LF-RF", "OF")` → expect `"LF"`, observe `"OF"` (will fail)

**Expected Counterexamples**:
- All non-canonical strings return `"OF"` regardless of their actual encoded position.
- Confirms root cause: no normalization step exists before `pos_map`.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, `normalize_position()`
produces the expected canonical result.

**Pseudocode:**
```
FOR ALL raw WHERE isBugCondition(raw) DO
  result = normalize_position(raw)
  ASSERT result IN CANONICAL_SET
  ASSERT result != "OF" OR raw encodes a genuine outfield position
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold,
`normalize_position()` returns the identical string.

**Pseudocode:**
```
FOR ALL raw WHERE NOT isBugCondition(raw) DO
  ASSERT normalize_position(raw) == raw
END FOR
```

**Testing Approach**: Property-based testing is well-suited here because the canonical
set is small (9 values) and exhaustive enumeration is trivial. A PBT generator can also
produce random strings to verify the fallback-to-`"OF"` guarantee.

**Test Cases**:
1. **Canonical pass-through**: for each of `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH}`,
   assert `normalize_position(x) == x`.
2. **position_override preservation**: given `data["position"] = "*1B"` and
   `position_override = "SS"`, assert `ratings["position"] == "SS"` after
   `calculate_ratings()`.
3. **Fallback preservation**: assert `normalize_position("XYZ") == "OF"`.

### Unit Tests

- `normalize_position("*1B")` == `"1B"`
- `normalize_position("1B/OF")` == `"1B"`
- `normalize_position("1B-2B")` == `"1B"`
- `normalize_position("OF")` == `"CF"`
- `normalize_position("LF-RF")` == `"LF"`
- `normalize_position("CF-RF")` == `"CF"`
- `normalize_position("LF/CF")` == `"LF"`
- `normalize_position("*SS")` == `"SS"`
- `normalize_position("RF")` == `"RF"` (canonical pass-through)
- `normalize_position("XYZ")` == `"OF"` (unresolvable fallback)
- `normalize_position(None)` == `"OF"` (null safety)

### Property-Based Tests

- **Property 1 (fix checking)**: for all strings in the bug-condition set, output is in
  `CANONICAL_SET ∪ {"OF"}` and encodes the correct position.
- **Property 2 (preservation)**: for all 9 canonical strings, `normalize_position(x) == x`.
- **Property 3 (output closure)**: for any arbitrary string input, output is always in
  `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH, OF}` — the function never produces garbage.
- **Property 4 (override preservation)**: for any `data["position"]` value and any
  canonical `position_override`, `ratings["position"] == position_override`.

### Integration Tests

- Generate a card for Nap Lajoie (1901) — a historical player whose BBRef position is
  `*1B` — and assert `ratings["position"] == "1B"` and arm/reaction defaults match `1B`
  baselines, not `OF` baselines.
- Generate a card for a player with a slash-composite position (e.g., `1B/OF`) and assert
  the infield position wins.
- Generate a card with `--position LF` for a player whose scraped position is `*1B` and
  assert `ratings["position"] == "LF"` (override wins).
