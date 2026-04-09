# Bugfix Requirements Document

## Introduction

Historical players like Nap Lajoie (1B) are assigned the wrong primary position because
Baseball-Reference returns non-canonical position strings (e.g. `*1B`, `1B/OF`, `1B-2B`)
that `generate_card.py`'s `pos_map` does not recognize. Any unrecognized string falls
through to `"OF"`, which corrupts fielding baseline, arm defaults, directional reactions,
bunt/drag defaults, and the overall feel of the card.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN BBRef returns a position string with a leading asterisk (e.g. `*1B`) THEN the
    system falls through to `"OF"` instead of recognizing the infield position.

1.2 WHEN BBRef returns a slash-separated multi-position string (e.g. `1B/OF`) THEN the
    system falls through to `"OF"` instead of using the primary (first) position token.

1.3 WHEN BBRef returns a hyphen-separated multi-position string (e.g. `1B-2B`) THEN the
    system falls through to `"OF"` instead of using the primary (first) position token.

1.4 WHEN the raw `best_pos` value from `pull_career_fielding()` contains any non-canonical
    variant THEN `calculate_ratings()` receives a string that `pos_map` cannot match,
    causing all position-dependent defaults (arm strength, arm accuracy, reactions, bunt,
    drag bunt) to be set to generic outfield values.

### Expected Behavior (Correct)

2.1 WHEN BBRef returns a position string with a leading asterisk (e.g. `*1B`) THEN the
    system SHALL strip the asterisk and resolve the position to the canonical token (`1B`).

2.2 WHEN BBRef returns a slash-separated multi-position string (e.g. `1B/OF`) THEN the
    system SHALL use the first token as the primary position and resolve it to its
    canonical form (`1B`).

2.3 WHEN BBRef returns a hyphen-separated multi-position string (e.g. `1B-2B`) THEN the
    system SHALL use the first token as the primary position and resolve it to its
    canonical form (`1B`).

2.4 WHEN any BBRef position string is normalized THEN the system SHALL produce a value
    that is a member of the canonical set `{RF, LF, CF, 1B, 2B, SS, 3B, C, DH}` before
    the `pos_map` lookup in `calculate_ratings()` is executed.

2.5 WHEN BBRef returns a generic outfield alias or composite outfield string (e.g. `OF`,
    `LF-RF`, `CF-RF`, `LF/CF`) THEN the system SHALL normalize it to the most specific
    canonical outfield token available (e.g. `LF`, `CF`, `RF`) using the first recognizable
    outfield token, or `CF` as the outfield default when no specific token is present.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN BBRef returns an already-canonical position string (e.g. `RF`, `SS`, `C`) THEN
    the system SHALL CONTINUE TO resolve it to the same canonical position without change.

3.2 WHEN a player genuinely plays outfield and BBRef returns `LF`, `CF`, or `RF` THEN the
    system SHALL CONTINUE TO assign the correct outfield position and its associated defaults.

3.3 WHEN a player's position is explicitly overridden via the `--position` CLI flag or
    `position_override` parameter THEN the system SHALL CONTINUE TO use the override and
    bypass auto-detection entirely, even if the scraped BBRef position string is malformed
    or non-canonical.

3.4 WHEN a position string cannot be resolved to any canonical position after normalization
    THEN the system SHALL CONTINUE TO fall back to `"OF"` as the default.
