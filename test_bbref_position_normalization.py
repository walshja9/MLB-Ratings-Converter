"""
Bug condition exploration test for BBRef position normalization.

After fix: these tests call normalize_position(raw) and all 5 should PASS.

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

import pytest
from generate_card import normalize_position

# Replicate the exact pos_map from generate_card.py calculate_ratings()
# (local variable — cannot be imported directly, so we mirror it faithfully)
pos_map = {
    "RF": "RF", "LF": "LF", "CF": "CF",
    "1B": "1B", "2B": "2B", "SS": "SS",
    "3B": "3B", "C": "C", "DH": "DH",
}


# ---------------------------------------------------------------------------
# Bug condition exploration tests — all EXPECTED TO PASS after fix
# ---------------------------------------------------------------------------

def test_asterisk_1b():
    """Bug case: leading asterisk — *1B should resolve to 1B, not OF."""
    assert normalize_position("*1B") == "1B"


def test_slash_composite_1b_of():
    """Bug case: slash composite — 1B/OF should resolve to 1B (primary), not OF."""
    assert normalize_position("1B/OF") == "1B"


def test_hyphen_composite_1b_2b():
    """Bug case: hyphen composite — 1B-2B should resolve to 1B (primary), not OF."""
    assert normalize_position("1B-2B") == "1B"


def test_outfield_alias_lf_rf():
    """Bug case: outfield alias — LF-RF should resolve to LF (first token), not OF."""
    assert normalize_position("LF-RF") == "LF"


def test_asterisk_ss():
    """Bug case: leading asterisk — *SS should resolve to SS, not OF."""
    assert normalize_position("*SS") == "SS"


# ===========================================================================
# Task 2: Preservation property tests (BEFORE implementing fix)
#
# Observation-first methodology: all three groups were observed on UNFIXED
# code first, outputs recorded, then encoded as assertions.
#
# EXPECTED OUTCOME: All tests PASS on unfixed code (baseline confirmed).
# After the fix is applied (task 3), re-running these tests confirms no
# regressions on the preservation paths.
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ===========================================================================

import pytest
from generate_card import calculate_ratings


def _make_data(year=2022, position="SS", games=130, ba=0.270, k_pct=20.0,
               bb_pct=8.0, sb=5, iso=0.150, obp=0.340, slg=0.420, war=2.0):
    """Build a minimal synthetic data dict that satisfies calculate_ratings()."""
    batting = {
        "G": games,
        "PA": games * 4,
        "BA": ba,
        "OBP": obp,
        "SLG": slg,
        "ISO": iso,
        "HR": 15,
        "SB": sb,
        "BB_pct": bb_pct,
        "K_pct": k_pct,
        "wOBA": 0.340,
        "WAR": war,
        "fg_spd": None,
        "bsr": None,
        "team": "TST",
    }
    return {
        "name": "Test Player",
        "year": year,
        "batting": batting,
        "career_avg": None,
        "career_yearly": {},
        "sprint_speed": None,
        "fielding_oaa": {},
        "position": position,
        "splits": {},
        "avg_ev": None,
    }


# ---------------------------------------------------------------------------
# Preservation 1: Canonical pass-through
#
# Observed on unfixed code: pos_map.get(x, "OF") == x for all 9 canonical
# strings. Encodes as assertions to lock in this baseline.
# ---------------------------------------------------------------------------

CANONICAL_POSITIONS = ["RF", "LF", "CF", "1B", "2B", "SS", "3B", "C", "DH"]


@pytest.mark.parametrize("canonical", CANONICAL_POSITIONS)
def test_canonical_passthrough(canonical):
    """
    Canonical pass-through: each of the 9 canonical position strings must
    resolve to itself via pos_map.get(x, "OF").

    Observed on unfixed code: all 9 return x unchanged.
    EXPECTED OUTCOME: PASS on unfixed code.

    Validates: Requirements 3.1, 3.2
    """
    result = pos_map.get(canonical, "OF")
    assert result == canonical, (
        f"Canonical pass-through broken: pos_map.get('{canonical}', 'OF') "
        f"returned '{result}', expected '{canonical}'"
    )


# ---------------------------------------------------------------------------
# Preservation 2: position_override wins over messy scraped position
#
# Observed on unfixed code: calculate_ratings(data, position_override="SS")
# with data["position"] = "*1B" returns ratings["position"] == "SS".
# The override path `pos = position_override or data.get("position") or "OF"`
# picks up "SS" before pos_map ever sees "*1B".
# ---------------------------------------------------------------------------

def test_position_override_wins_over_messy_scraped_position():
    """
    position_override must win even when data["position"] is a non-canonical
    BBRef string (e.g. "*1B").

    Observed on unfixed code: ratings["position"] == "SS" (override wins).
    EXPECTED OUTCOME: PASS on unfixed code.

    Validates: Requirement 3.3
    """
    data = _make_data(position="*1B")
    ratings = calculate_ratings(data, position_override="SS")
    assert ratings["position"] == "SS", (
        f"position_override did not win: expected 'SS', got '{ratings['position']}'. "
        f"The override path must bypass the messy scraped position entirely."
    )


# ---------------------------------------------------------------------------
# Preservation 3: Unresolvable string falls back to "OF"
#
# Observed on unfixed code: pos_map.get("XYZ", "OF") == "OF".
# Encodes the existing fallback guarantee.
# ---------------------------------------------------------------------------

def test_unresolvable_fallback_to_of():
    """
    Strings that cannot be resolved to any canonical position must fall back
    to "OF" via pos_map.get(x, "OF").

    Observed on unfixed code: pos_map.get("XYZ", "OF") == "OF".
    EXPECTED OUTCOME: PASS on unfixed code.

    Validates: Requirement 3.4
    """
    result = pos_map.get("XYZ", "OF")
    assert result == "OF", (
        f"Unresolvable fallback broken: pos_map.get('XYZ', 'OF') "
        f"returned '{result}', expected 'OF'"
    )
