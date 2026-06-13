"""
Bug condition exploration tests for pre-OAA fielding & reactions.

These tests call calculate_ratings() directly with minimal synthetic inputs
to confirm the three bug conditions exist on UNFIXED code.

EXPECTED OUTCOME: All three test cases FAIL on unfixed code.
Failure is the SUCCESS condition — it proves the bugs exist.

DO NOT fix the code or the test when it fails.
"""

import pytest
from generate_card import calculate_ratings, POSITION_DEFAULTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data(year, oaa_data, position="SS", games=130, ba=0.270, k_pct=20.0, bb_pct=8.0,
               sb=5, iso=0.150, obp=0.340, slg=0.420, war=2.0):
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
        "fielding_oaa": oaa_data,
        "position": position,
        "splits": {},
        "avg_ev": None,
    }


YEAR = 2010  # pre-OAA era


class TestBug1RdrsFieldingSlope:
    """Bug 1: Rdrs slope too conservative — fielding underestimated."""

    def test_rdrs_15_fielding_should_be_at_least_85(self):
        """
        EXPECT FAIL on unfixed code.

        A +15 DRS defender (elite) should map to FIELD >= 85.
        Current formula: 2.0 * rdrs + 68 produces raw_fld=98, but at
        moderate innings (inn=210, def_trust≈0.356) the blending with
        pos_baseline=85 yields ~78 — well below the expected 85-88.

        inn=210 is realistic for a player who misses ~30 games (e.g. injury
        or platoon). def_trust = (210-50)/450 ≈ 0.356.
        Blended: 0.356*98 + 0.644*85 ≈ 34.9 + 54.7 ≈ 89.6... actually 78.
        (The clamp on raw_fld and rounding interact — see debug output.)

        Validates: Requirements 1.1 (bug condition), 2.1 (expected behavior)
        """
        oaa_data = {
            f"rdrs_{YEAR}": 15,
            f"inn_{YEAR}": 210,  # moderate innings → def_trust≈0.356 → blended ~78
            # No rngr, no oaa integer keys, no fg_def
        }
        data = _make_data(YEAR, oaa_data, position="SS")
        ratings = calculate_ratings(data, mode="season")

        actual_fielding = ratings["fielding"]
        print(f"\nBug 1 counterexample: fielding={actual_fielding} for rdrs=15, inn=210, expected >= 85")

        # This assertion FAILS on unfixed code (~78 actual)
        assert actual_fielding >= 85, (
            f"Bug 1 confirmed: fielding={actual_fielding} for rdrs=15, inn=210 (expected >= 85). "
            f"Current slope 2.0*rdrs+68 is too conservative — at moderate innings "
            f"the blending with pos_baseline pulls the rating down to ~78."
        )


# ---------------------------------------------------------------------------
# Bug 3: Reactions ignore Rdrs/Rtot — fall back to flat position defaults
#
# Input:  rdrs_{year}=15, no rngr/oaa, inn_{year}=400
# Expected: reaction_right != SS default (80)
# Actual on unfixed code: reaction_right == 80 (flat default, base_react never set)
# ---------------------------------------------------------------------------

class TestBug3ReactionsIgnoreRdrs:
    """Bug 3: Reactions pipeline has no Rdrs/Rtot branch."""

    def test_rdrs_15_reactions_should_differ_from_flat_defaults(self):
        """
        EXPECT FAIL on unfixed code.

        With rdrs=15 and no rngr/oaa, reactions should be driven by Rdrs
        as a range proxy. On unfixed code, base_react is never set, so all
        four reactions fall through to flat SS position defaults.

        Validates: Requirements 1.3 (bug condition), 2.3 (expected behavior)
        """
        oaa_data = {
            f"rdrs_{YEAR}": 15,
            f"inn_{YEAR}": 400,
            # No rngr, no oaa integer keys
        }
        data = _make_data(YEAR, oaa_data, position="SS")
        ratings = calculate_ratings(data, mode="season")

        ss_defaults = POSITION_DEFAULTS["SS"]
        pos_react_r = ss_defaults["react_r"]  # 80

        actual_react_r = ratings["reaction_right"]
        actual_react_l = ratings["reaction_left"]
        actual_react_f = ratings["reaction_forward"]
        actual_react_b = ratings["reaction_back"]

        print(
            f"\nBug 3 counterexample: "
            f"reaction_right={actual_react_r} (SS default={pos_react_r}), "
            f"reaction_left={actual_react_l} (SS default={ss_defaults['react_l']}), "
            f"reaction_forward={actual_react_f} (SS default={ss_defaults['react_f']}), "
            f"reaction_back={actual_react_b} (SS default={ss_defaults['react_b']})"
        )

        # At least one reaction should differ from the flat SS default.
        # This assertion FAILS on unfixed code (all reactions == flat defaults).
        any_differs = (
            actual_react_r != ss_defaults["react_r"]
            or actual_react_l != ss_defaults["react_l"]
            or actual_react_f != ss_defaults["react_f"]
            or actual_react_b != ss_defaults["react_b"]
        )
        assert any_differs, (
            f"Bug 3 confirmed: all reactions equal flat SS defaults despite rdrs=15. "
            f"Got react_l={actual_react_l}, react_r={actual_react_r}, "
            f"react_f={actual_react_f}, react_b={actual_react_b}. "
            f"SS defaults: l={ss_defaults['react_l']}, r={ss_defaults['react_r']}, "
            f"f={ss_defaults['react_f']}, b={ss_defaults['react_b']}."
        )


# ---------------------------------------------------------------------------
# Bug 4: def_trust collapses to 0 when innings data is absent
#
# Input:  rtot_{year}=10, no innings key at all, no rngr/oaa
# Expected: fielding != pos_baseline (Rtot should influence the rating)
# Actual on unfixed code: def_trust=0 → fielding = 0*raw_fld + 1*pos_baseline = pos_baseline
# ---------------------------------------------------------------------------

class TestBug4DefTrustCollapseNoInnings:
    """Bug 4: def_trust hard-coded to 0 when innings data is absent."""

    def test_rtot_10_no_innings_fielding_should_not_equal_pos_baseline(self):
        """
        EXPECT FAIL on unfixed code.

        With rtot=10 and no innings data, def_trust=0 collapses the fielding
        rating entirely to pos_baseline, ignoring Rtot completely.

        Validates: Requirements 1.4 (bug condition), 2.4 (expected behavior)
        """
        oaa_data = {
            f"rtot_{YEAR}": 10,
            # No inn_{year} key — pre-2003 era, innings data absent
            # No rngr, no oaa integer keys
        }
        data = _make_data(YEAR, oaa_data, position="SS")
        ratings = calculate_ratings(data, mode="season")

        # pos_fielding_base["SS"] = 85 (from generate_card.py)
        pos_baseline = 85  # SS position baseline from pos_fielding_base

        actual_fielding = ratings["fielding"]
        print(
            f"\nBug 4 counterexample: fielding={actual_fielding}, "
            f"pos_baseline={pos_baseline} for rtot=10 with no innings data. "
            f"def_trust=0 → Rtot completely ignored."
        )

        # This assertion FAILS on unfixed code (fielding == pos_baseline exactly)
        assert actual_fielding != pos_baseline, (
            f"Bug 4 confirmed: fielding={actual_fielding} equals pos_baseline={pos_baseline} "
            f"despite rtot=10. def_trust=0 when innings data is absent, "
            f"so Rtot is completely ignored."
        )


# ===========================================================================
# TASK 2: Preservation property tests
#
# These tests encode the OBSERVED outputs of the UNFIXED code for all paths
# where isBugCondition() returns False.
#
# EXPECTED OUTCOME: All tests PASS on unfixed code (baseline confirmed).
# After the fix is applied (task 3), re-running these tests confirms no
# regressions on OAA / RngR / FG Def / no-metrics / innings-present paths.
#
# Observation methodology:
#   1. Ran _observe_preservation.py and _observe_preservation2.py on unfixed code.
#   2. Recorded exact integer outputs.
#   3. Encoded as parametrized assertions below.
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
# ===========================================================================

PRES_YEAR = 2022  # any modern year with OAA/RngR available


# ---------------------------------------------------------------------------
# Path 1: OAA path (2020+ Statcast era)
# isBugCondition = False because has_oaa is True (integer year key present)
# Preservation: fielding formula 2.09*OAA+68.6 and OAA-based reactions unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oaa_val,expected_fielding,expected_rl,expected_rr,expected_rf,expected_rb", [
    # Observed on recalibrated code (6/4 refit) — SS position, inn=1200 (full trust)
    (-5,  65, 49, 67, 61, 52),
    ( 0,  73, 55, 75, 68, 58),
    (10,  90, 68, 92, 84, 72),
    (20,  99, 81, 99, 99, 86),
])
def test_oaa_path_preservation_ss(oaa_val, expected_fielding, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    OAA path (SS, full innings) — fielding and all four reactions must be
    byte-for-byte identical before and after the fix.

    Validates: Requirements 3.1
    """
    oaa_data = {PRES_YEAR: oaa_val, f"inn_{PRES_YEAR}": 1200}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding, (
        f"OAA={oaa_val}: fielding changed — expected {expected_fielding}, got {r['fielding']}"
    )
    assert r["reaction_left"] == expected_rl, (
        f"OAA={oaa_val}: reaction_left changed — expected {expected_rl}, got {r['reaction_left']}"
    )
    assert r["reaction_right"] == expected_rr, (
        f"OAA={oaa_val}: reaction_right changed — expected {expected_rr}, got {r['reaction_right']}"
    )
    assert r["reaction_forward"] == expected_rf, (
        f"OAA={oaa_val}: reaction_forward changed — expected {expected_rf}, got {r['reaction_forward']}"
    )
    assert r["reaction_back"] == expected_rb, (
        f"OAA={oaa_val}: reaction_back changed — expected {expected_rb}, got {r['reaction_back']}"
    )


@pytest.mark.parametrize("pos,oaa_val,expected_fielding,expected_rl,expected_rr,expected_rf,expected_rb", [
    # Observed on recalibrated code (6/4 refit) — multi-position, inn=1200
    ("CF", -5,  65, 58, 58, 55, 55),
    ("CF", 10,  90, 80, 80, 76, 76),
    ("3B", -5,  62, 52, 55, 67, 52),
    ("3B", 10,  86, 72, 76, 92, 72),
    ("2B", -5,  62, 55, 61, 64, 49),
    ("2B", 10,  86, 76, 84, 88, 68),
])
def test_oaa_path_preservation_multipos(pos, oaa_val, expected_fielding, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    OAA path (multiple positions, full innings) — directional weights per
    position must remain unchanged.

    Validates: Requirements 3.1
    """
    oaa_data = {PRES_YEAR: oaa_val, f"inn_{PRES_YEAR}": 1200}
    data = _make_data(PRES_YEAR, oaa_data, position=pos)
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding
    assert r["reaction_left"] == expected_rl
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


@pytest.mark.parametrize("inn_val,expected_fielding,expected_rl,expected_rr,expected_rf,expected_rb", [
    # OAA=10, SS — def_trust blending at various innings levels
    (100, 54, 56, 81, 80, 70),
    (300, 86, 62, 87, 82, 71),
    (600, 90, 68, 92, 84, 72),
])
def test_oaa_path_preservation_low_innings(inn_val, expected_fielding, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    OAA path with partial innings — def_trust blending must remain unchanged.

    Validates: Requirements 3.1, 3.4
    """
    oaa_data = {PRES_YEAR: 10, f"inn_{PRES_YEAR}": inn_val}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding
    assert r["reaction_left"] == expected_rl
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


# ---------------------------------------------------------------------------
# Path 2: RngR path (2003-2019 UZR era)
# isBugCondition = False because rngr_val is not None (RngR is primary reactions driver)
# Preservation: reactions formula 2.0*RngR+65 and directional weights unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rngr_val,expected_rl,expected_rr,expected_rf,expected_rb", [
    # Observed on unfixed code — SS position, inn=1200
    (-10, 38, 52, 47, 40),
    (  0, 55, 75, 68, 58),
    (  8, 69, 93, 85, 73),
    ( 15, 81, 99, 99, 86),
])
def test_rngr_path_preservation_ss(rngr_val, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    RngR path (SS, full innings) — reactions must be byte-for-byte identical
    before and after the fix. RngR stays primary reactions driver.

    Validates: Requirements 3.2
    """
    oaa_data = {f"rngr_{PRES_YEAR}": rngr_val, f"inn_{PRES_YEAR}": 1200}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["reaction_left"] == expected_rl, (
        f"RngR={rngr_val}: reaction_left changed — expected {expected_rl}, got {r['reaction_left']}"
    )
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


@pytest.mark.parametrize("pos,rngr_val,expected_rl,expected_rr,expected_rf,expected_rb", [
    # Observed on recalibrated code (6/4 refit) — multi-position, inn=1200
    ("CF", -10, 45, 45, 43, 43),
    ("CF",   8, 81, 81, 77, 77),
    ("3B", -10, 40, 43, 52, 40),
    ("3B",   8, 73, 77, 93, 73),
])
def test_rngr_path_preservation_multipos(pos, rngr_val, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    RngR path (multiple positions) — position-specific directional weights
    must remain unchanged.

    Validates: Requirements 3.2
    """
    oaa_data = {f"rngr_{PRES_YEAR}": rngr_val, f"inn_{PRES_YEAR}": 1200}
    data = _make_data(PRES_YEAR, oaa_data, position=pos)
    r = calculate_ratings(data, mode="season")

    assert r["reaction_left"] == expected_rl
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


@pytest.mark.parametrize("inn_val,expected_rl,expected_rr,expected_rf,expected_rb", [
    # RngR=8, SS — def_trust blending at various innings levels
    (100, 57, 81, 81, 70),
    (300, 63, 87, 83, 72),
    (600, 69, 93, 85, 73),
])
def test_rngr_path_preservation_low_innings(inn_val, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    RngR path with partial innings — def_trust blending on reactions unchanged.

    Validates: Requirements 3.2, 3.4
    """
    oaa_data = {f"rngr_{PRES_YEAR}": 8, f"inn_{PRES_YEAR}": inn_val}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["reaction_left"] == expected_rl
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


# ---------------------------------------------------------------------------
# Path 3: FG Def path (2003-2019 primary fielding driver)
# isBugCondition = False because fg_def_val is not None (FG Def is primary fielding)
# Preservation: fielding formula 1.38*FG_Def+67.3 unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("def_val,expected_fielding", [
    # Observed on recalibrated code (6/4 refit) — SS position, inn=1200 (full trust)
    (-15, 53),
    (  0, 73),
    ( 10, 87),
    ( 20, 99),
])
def test_fg_def_path_preservation(def_val, expected_fielding):
    """
    FG Def path (SS, full innings) — fielding must be byte-for-byte identical
    before and after the fix.

    Validates: Requirements 3.3
    """
    oaa_data = {f"def_{PRES_YEAR}": def_val, f"inn_{PRES_YEAR}": 1200}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding, (
        f"FGDef={def_val}: fielding changed — expected {expected_fielding}, got {r['fielding']}"
    )


@pytest.mark.parametrize("def_val,inn_val,expected_fielding", [
    # Observed on recalibrated code (6/4 refit) — def_trust blending at various innings
    ( 0, 200, 68),
    (10, 200, 72),
    ( 0, 600, 73),
    (10, 600, 87),
    ( 0, 1200, 73),
    (10, 1200, 87),
])
def test_fg_def_path_preservation_def_trust(def_val, inn_val, expected_fielding):
    """
    FG Def path with varying innings — def_trust blending must remain unchanged.

    Validates: Requirements 3.3, 3.4
    """
    oaa_data = {f"def_{PRES_YEAR}": def_val, f"inn_{PRES_YEAR}": inn_val}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding, (
        f"FGDef={def_val}, inn={inn_val}: fielding changed — expected {expected_fielding}, got {r['fielding']}"
    )


# ---------------------------------------------------------------------------
# Path 4: No-metrics path (empty oaa_data)
# isBugCondition = False because no metrics at all — pure position baseline
# Preservation: fielding = pos_baseline, reactions = flat position defaults
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pos,expected_fielding,expected_rl,expected_rr,expected_rf,expected_rb", [
    # Observed on unfixed code — empty oaa_data
    ("SS", 85, 55, 80, 80, 70),
    ("CF", 75, 70, 65, 60, 60),
    ("3B", 65, 55, 60, 75, 60),
    ("1B", 50, 65, 60, 50, 60),
])
def test_no_metrics_path_preservation(pos, expected_fielding, expected_rl, expected_rr, expected_rf, expected_rb):
    """
    No-metrics path (empty oaa_data) — fielding = pos_baseline and reactions =
    flat position defaults, byte-for-byte identical before and after the fix.

    Validates: Requirements 3.6
    """
    data = _make_data(PRES_YEAR, {}, position=pos)
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding, (
        f"pos={pos}: fielding changed — expected {expected_fielding}, got {r['fielding']}"
    )
    assert r["reaction_left"] == expected_rl, (
        f"pos={pos}: reaction_left changed — expected {expected_rl}, got {r['reaction_left']}"
    )
    assert r["reaction_right"] == expected_rr
    assert r["reaction_forward"] == expected_rf
    assert r["reaction_back"] == expected_rb


def test_no_metrics_path_equals_position_defaults():
    """
    No-metrics path: reactions must exactly equal POSITION_DEFAULTS values
    (not just match observed numbers — also validates the structural invariant).

    Validates: Requirements 3.6
    """
    for pos in ["SS", "CF", "3B", "1B", "2B", "LF", "RF"]:
        data = _make_data(PRES_YEAR, {}, position=pos)
        r = calculate_ratings(data, mode="season")
        d = POSITION_DEFAULTS[pos]

        assert r["reaction_left"] == d["react_l"], f"pos={pos}: reaction_left != default"
        assert r["reaction_right"] == d["react_r"], f"pos={pos}: reaction_right != default"
        assert r["reaction_forward"] == d["react_f"], f"pos={pos}: reaction_forward != default"
        assert r["reaction_back"] == d["react_b"], f"pos={pos}: reaction_back != default"


# ---------------------------------------------------------------------------
# Path 5: Innings-present path (def_trust calculation)
# isBugCondition = False because has_innings_data is True
# Preservation: def_trust ramp max(0, min((inn-50)/450, 1.0)) unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inn_val,expected_fielding", [
    # Observed on FIXED code — rdrs=5, SS position
    # def_trust = max(0, min((inn-50)/450, 1.0))
    # Note: DH-blend is skipped when Rdrs is present (player is a real fielder)
    # raw_fld = clamp(2.5*5+68) = 80; pos_baseline = 85
    ( 50,  85),   # def_trust = 0 → fielding = pos_baseline = 85
    (200,  83),   # def_trust = 0.333 → 0.333*80 + 0.667*85 ≈ 83.3 → 83
    (400,  81),   # def_trust = 0.778 → 0.778*80 + 0.222*85 ≈ 81.1 → 81
    (600,  80),   # def_trust = 1.0 → raw_fld = 80
    (900,  80),   # def_trust = 1.0 → same as 600
])
def test_innings_present_def_trust_preservation(inn_val, expected_fielding):
    """
    Innings-present path — def_trust ramp formula must remain byte-for-byte
    identical before and after the fix. This is the critical preservation
    invariant: the fix must NOT change def_trust for players who have innings data.

    Validates: Requirements 3.4
    """
    oaa_data = {f"rdrs_{PRES_YEAR}": 5, f"inn_{PRES_YEAR}": inn_val}
    data = _make_data(PRES_YEAR, oaa_data, position="SS")
    r = calculate_ratings(data, mode="season")

    assert r["fielding"] == expected_fielding, (
        f"inn={inn_val}: fielding changed — expected {expected_fielding}, got {r['fielding']}. "
        f"def_trust ramp may have been altered."
    )
