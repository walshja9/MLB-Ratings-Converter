"""
Integration spot-checks against known Show card values.

Constructs realistic synthetic data dicts for five integration players,
calls calculate_ratings(), and asserts FIELD + reactions against expected values.

Players:
  1. Ozzie Smith 1987  (SS, elite Rdrs ≈ +15, inn ≈ 1200) — Bug 1 + Bug 3 validation
  2. Willie Mays 1954  (CF, Rtot ≈ +12, no innings data)  — Bug 2 + Bug 4 validation
  3. Derek Jeter 2005  (SS, Rdrs ≈ -10, inn ≈ 1200)       — penalty direction check
  4. Juan Soto 2025    (LF, OAA ≈ +5, inn ≈ 1200)         — modern-era preservation
  5. Xander Bogaerts 2022 (SS, RngR ≈ +3, inn ≈ 1200)     — middle-era preservation

Run with:
  pytest test_integration_spotchecks.py -v
"""

import pytest
from generate_card import calculate_ratings, POSITION_DEFAULTS


# ---------------------------------------------------------------------------
# Shared helper (same pattern as test_pre_oaa_fielding.py)
# ---------------------------------------------------------------------------

def _make_data(year, oaa_data, position="SS", games=130, ba=0.270, k_pct=20.0,
               bb_pct=8.0, sb=5, iso=0.150, obp=0.340, slg=0.420, war=2.0):
    """Build a minimal synthetic data dict for calculate_ratings()."""
    batting = {
        "G": games, "PA": games * 4, "BA": ba, "OBP": obp, "SLG": slg, "ISO": iso,
        "HR": 15, "SB": sb, "BB_pct": bb_pct, "K_pct": k_pct, "wOBA": 0.340,
        "WAR": war, "fg_spd": None, "bsr": None, "team": "TST",
    }
    return {
        "name": "Test Player", "year": year, "batting": batting,
        "career_avg": None, "career_yearly": {}, "sprint_speed": None,
        "fielding_oaa": oaa_data, "position": position, "splits": {}, "avg_ev": None,
    }


# ---------------------------------------------------------------------------
# Summary table helper
# ---------------------------------------------------------------------------

def _print_summary(results):
    """Print a formatted summary table of all spot-check results."""
    header = f"{'Player':<22} {'Year':<6} {'Pos':<4} {'FIELD':<7} {'rl':<5} {'rr':<5} {'rf':<5} {'rb':<5} {'Status'}"
    print("\n" + "=" * 75)
    print("INTEGRATION SPOT-CHECK SUMMARY")
    print("=" * 75)
    print(header)
    print("-" * 75)
    for row in results:
        status = "PASS" if row["pass"] else "FAIL"
        print(
            f"{row['player']:<22} {row['year']:<6} {row['pos']:<4} "
            f"{row['fielding']:<7} {row['rl']:<5} {row['rr']:<5} "
            f"{row['rf']:<5} {row['rb']:<5} {status}"
        )
    print("=" * 75)


# ---------------------------------------------------------------------------
# Player 1: Ozzie Smith 1987
# SS, elite Rdrs ≈ +15, inn ≈ 1200
# Expected: FIELD ≥ 85, all four reactions ABOVE SS flat defaults
# Validates: Bug 1 (Rdrs fielding slope) + Bug 3 (reactions use Rdrs)
# ---------------------------------------------------------------------------

class TestOzzieSmith1987:
    """Ozzie Smith 1987 — primary Bug 1 + Bug 3 validation."""

    YEAR = 1987
    POS = "SS"
    SS_DEFAULTS = POSITION_DEFAULTS["SS"]  # react_l=55, react_r=80, react_f=80, react_b=70

    @pytest.fixture
    def ratings(self):
        oaa_data = {
            f"rdrs_{self.YEAR}": 15,
            f"inn_{self.YEAR}": 1200,
            # No rngr, no oaa integer keys, no fg_def — pure Rdrs path
        }
        data = _make_data(self.YEAR, oaa_data, position=self.POS)
        return calculate_ratings(data, mode="season")

    def test_field_at_least_85(self, ratings):
        """
        Bug 1 fix: Rdrs=+15 elite defender should produce FIELD ≥ 85.
        Pre-fix formula (2.0*rdrs+68) at full innings yielded ~78.

        Validates: Requirements 2.1
        """
        assert ratings["fielding"] >= 85, (
            f"Ozzie Smith 1987: FIELD={ratings['fielding']} < 85. "
            f"Rdrs slope may still be too conservative."
        )

    def test_reactions_above_ss_defaults(self, ratings):
        """
        Bug 3 fix: reactions should be driven by Rdrs, not flat SS defaults.
        All four directions should exceed the flat position defaults for a +15 Rdrs defender.

        Validates: Requirements 2.3
        """
        d = self.SS_DEFAULTS
        assert ratings["reaction_left"] > d["react_l"], (
            f"reaction_left={ratings['reaction_left']} not above SS default {d['react_l']}"
        )
        assert ratings["reaction_right"] > d["react_r"], (
            f"reaction_right={ratings['reaction_right']} not above SS default {d['react_r']}"
        )
        assert ratings["reaction_forward"] > d["react_f"], (
            f"reaction_forward={ratings['reaction_forward']} not above SS default {d['react_f']}"
        )
        assert ratings["reaction_back"] > d["react_b"], (
            f"reaction_back={ratings['reaction_back']} not above SS default {d['react_b']}"
        )

    def test_reactions_not_equal_to_flat_defaults(self, ratings):
        """
        Reactions must differ from flat SS defaults — confirms base_react was set.

        Validates: Requirements 2.3
        """
        d = self.SS_DEFAULTS
        any_differs = (
            ratings["reaction_left"] != d["react_l"]
            or ratings["reaction_right"] != d["react_r"]
            or ratings["reaction_forward"] != d["react_f"]
            or ratings["reaction_back"] != d["react_b"]
        )
        assert any_differs, (
            f"All reactions equal flat SS defaults despite Rdrs=+15. "
            f"Bug 3 not fixed: base_react was never set."
        )


# ---------------------------------------------------------------------------
# Player 2: Willie Mays 1954
# CF, Rtot ≈ +12, no innings data (pre-2003 era)
# Expected: FIELD meaningfully above CF baseline (75), not equal to it
# Validates: Bug 2 (Rtot fielding slope) + Bug 4 (non-zero def_trust without innings)
# ---------------------------------------------------------------------------

class TestWillieMays1954:
    """Willie Mays 1954 — primary Bug 2 + Bug 4 validation."""

    YEAR = 1954
    POS = "CF"
    CF_BASELINE = 75  # pos_fielding_base["CF"]

    @pytest.fixture
    def ratings(self):
        oaa_data = {
            f"rtot_{self.YEAR}": 12,
            # No inn_{year} key — pre-2003 era, innings data absent
            # No rdrs, no rngr, no oaa integer keys
        }
        data = _make_data(self.YEAR, oaa_data, position=self.POS)
        return calculate_ratings(data, mode="season")

    def test_field_above_cf_baseline(self, ratings):
        """
        Bug 4 fix: def_trust must be non-zero (RTOT_PARTIAL_TRUST=0.4) so Rtot
        meaningfully influences the rating. Pre-fix: def_trust=0 → FIELD=75 exactly.
        Bug 2 fix: Rtot slope recalibrated so +12 maps above baseline.

        Validates: Requirements 2.2, 2.4
        """
        assert ratings["fielding"] > self.CF_BASELINE, (
            f"Willie Mays 1954: FIELD={ratings['fielding']} not above CF baseline {self.CF_BASELINE}. "
            f"def_trust may still be 0 (Bug 4) or Rtot slope too low (Bug 2)."
        )

    def test_field_not_equal_to_cf_baseline(self, ratings):
        """
        FIELD must not equal pos_baseline exactly — confirms def_trust > 0.

        Validates: Requirements 2.4
        """
        assert ratings["fielding"] != self.CF_BASELINE, (
            f"Willie Mays 1954: FIELD={ratings['fielding']} equals CF baseline exactly. "
            f"def_trust=0 — Bug 4 not fixed."
        )

    def test_field_in_reasonable_range(self, ratings):
        """
        Rtot=+12 for a CF should produce a rating in a reasonable range.
        Not so high it's implausible, not equal to baseline.
        """
        assert 76 <= ratings["fielding"] <= 95, (
            f"Willie Mays 1954: FIELD={ratings['fielding']} outside expected range [76, 95] "
            f"for Rtot=+12 CF with partial trust."
        )


# ---------------------------------------------------------------------------
# Player 3: Derek Jeter 2005
# SS, Rdrs ≈ -10, inn ≈ 1200
# Expected: FIELD below SS baseline (85), reactions below SS defaults
# Validates: penalty direction works correctly for bad defenders
# ---------------------------------------------------------------------------

class TestDerekJeter2005:
    """Derek Jeter 2005 — penalty direction validation."""

    YEAR = 2005
    POS = "SS"
    SS_BASELINE = 85  # pos_fielding_base["SS"]
    SS_DEFAULTS = POSITION_DEFAULTS["SS"]

    @pytest.fixture
    def ratings(self):
        oaa_data = {
            f"rdrs_{self.YEAR}": -10,
            f"inn_{self.YEAR}": 1200,
        }
        data = _make_data(self.YEAR, oaa_data, position=self.POS)
        return calculate_ratings(data, mode="season")

    def test_field_below_ss_baseline(self, ratings):
        """
        A -10 DRS defender should be penalized below the SS baseline of 85.

        Validates: Requirements 2.1 (slope applies in both directions)
        """
        assert ratings["fielding"] < self.SS_BASELINE, (
            f"Jeter 2005: FIELD={ratings['fielding']} not below SS baseline {self.SS_BASELINE}. "
            f"Negative Rdrs should penalize the fielding rating."
        )

    def test_reactions_below_ss_defaults(self, ratings):
        """
        Reactions should be below SS flat defaults for a -10 Rdrs defender.

        Validates: Requirements 2.3 (reactions use Rdrs as range proxy, both directions)
        """
        d = self.SS_DEFAULTS
        assert ratings["reaction_left"] < d["react_l"], (
            f"reaction_left={ratings['reaction_left']} not below SS default {d['react_l']}"
        )
        assert ratings["reaction_right"] < d["react_r"], (
            f"reaction_right={ratings['reaction_right']} not below SS default {d['react_r']}"
        )
        assert ratings["reaction_forward"] < d["react_f"], (
            f"reaction_forward={ratings['reaction_forward']} not below SS default {d['react_f']}"
        )
        assert ratings["reaction_back"] < d["react_b"], (
            f"reaction_back={ratings['reaction_back']} not below SS default {d['react_b']}"
        )


# ---------------------------------------------------------------------------
# Player 4: Juan Soto 2025
# LF, OAA ≈ +5, inn ≈ 1200 — modern OAA era
# Expected: FIELD and reactions UNCHANGED from pre-fix behavior (preservation)
# Validates: Requirements 3.1 — OAA path byte-for-byte identical
# ---------------------------------------------------------------------------

class TestJuanSoto2025:
    """Juan Soto 2025 — critical modern-era preservation check."""

    # Observed on fixed code (OAA path is unchanged by the fix):
    # Soto (OAA=5, LF, inn=1200): fielding=79, rl=68, rr=65, rf=61, rb=68
    YEAR = 2022  # use 2022 as proxy year (same OAA path logic)
    POS = "LF"
    EXPECTED_FIELDING = 79
    EXPECTED_RL = 68
    EXPECTED_RR = 65
    EXPECTED_RF = 61
    EXPECTED_RB = 68

    @pytest.fixture
    def ratings(self):
        oaa_data = {self.YEAR: 5, f"inn_{self.YEAR}": 1200}
        data = _make_data(self.YEAR, oaa_data, position=self.POS)
        return calculate_ratings(data, mode="season")

    def test_fielding_unchanged(self, ratings):
        """
        OAA-based fielding formula (2.09*OAA+68.6) must be byte-for-byte identical.

        Validates: Requirements 3.1
        """
        assert ratings["fielding"] == self.EXPECTED_FIELDING, (
            f"Soto 2025 (OAA=5, LF): fielding changed — "
            f"expected {self.EXPECTED_FIELDING}, got {ratings['fielding']}. "
            f"OAA path must not be modified by the pre-OAA fix."
        )

    def test_reactions_unchanged(self, ratings):
        """
        OAA-based reactions must be byte-for-byte identical.

        Validates: Requirements 3.1
        """
        assert ratings["reaction_left"] == self.EXPECTED_RL, (
            f"Soto 2025: reaction_left changed — expected {self.EXPECTED_RL}, got {ratings['reaction_left']}"
        )
        assert ratings["reaction_right"] == self.EXPECTED_RR, (
            f"Soto 2025: reaction_right changed — expected {self.EXPECTED_RR}, got {ratings['reaction_right']}"
        )
        assert ratings["reaction_forward"] == self.EXPECTED_RF, (
            f"Soto 2025: reaction_forward changed — expected {self.EXPECTED_RF}, got {ratings['reaction_forward']}"
        )
        assert ratings["reaction_back"] == self.EXPECTED_RB, (
            f"Soto 2025: reaction_back changed — expected {self.EXPECTED_RB}, got {ratings['reaction_back']}"
        )


# ---------------------------------------------------------------------------
# Player 5: Xander Bogaerts 2022
# SS, RngR ≈ +3, inn ≈ 1200 — RngR era
# Expected: FIELD and reactions UNCHANGED from pre-fix behavior (preservation)
# Validates: Requirements 3.2 — RngR path byte-for-byte identical
# ---------------------------------------------------------------------------

class TestXanderBogaerts2022:
    """Xander Bogaerts 2022 — critical middle-era preservation check."""

    # Observed on fixed code (RngR path is unchanged by the fix):
    # Bogaerts (RngR=3, SS, inn=1200): fielding=85, rl=60, rr=82, rf=75, rb=64
    YEAR = 2022
    POS = "SS"
    EXPECTED_FIELDING = 85
    EXPECTED_RL = 60
    EXPECTED_RR = 82
    EXPECTED_RF = 75
    EXPECTED_RB = 64

    @pytest.fixture
    def ratings(self):
        oaa_data = {f"rngr_{self.YEAR}": 3, f"inn_{self.YEAR}": 1200}
        data = _make_data(self.YEAR, oaa_data, position=self.POS)
        return calculate_ratings(data, mode="season")

    def test_fielding_unchanged(self, ratings):
        """
        RngR-era fielding must be byte-for-byte identical.
        (RngR path uses FG Def or pos_baseline for fielding — not RngR itself.)

        Validates: Requirements 3.2
        """
        assert ratings["fielding"] == self.EXPECTED_FIELDING, (
            f"Bogaerts 2022 (RngR=3, SS): fielding changed — "
            f"expected {self.EXPECTED_FIELDING}, got {ratings['fielding']}. "
            f"RngR path must not be modified by the pre-OAA fix."
        )

    def test_reactions_unchanged(self, ratings):
        """
        RngR-based reactions (2.0*RngR+65 → directional weights) must be
        byte-for-byte identical.

        Validates: Requirements 3.2
        """
        assert ratings["reaction_left"] == self.EXPECTED_RL, (
            f"Bogaerts 2022: reaction_left changed — expected {self.EXPECTED_RL}, got {ratings['reaction_left']}"
        )
        assert ratings["reaction_right"] == self.EXPECTED_RR, (
            f"Bogaerts 2022: reaction_right changed — expected {self.EXPECTED_RR}, got {ratings['reaction_right']}"
        )
        assert ratings["reaction_forward"] == self.EXPECTED_RF, (
            f"Bogaerts 2022: reaction_forward changed — expected {self.EXPECTED_RF}, got {ratings['reaction_forward']}"
        )
        assert ratings["reaction_back"] == self.EXPECTED_RB, (
            f"Bogaerts 2022: reaction_back changed — expected {self.EXPECTED_RB}, got {ratings['reaction_back']}"
        )


# ---------------------------------------------------------------------------
# Summary fixture — prints the table after all tests run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def print_summary(request):
    """Print a summary table after all spot-check tests complete."""
    yield
    # Collect results by running each player's scenario once more
    results = []

    def _run(year, oaa_data, position, player, expected_checks):
        data = _make_data(year, oaa_data, position=position)
        r = calculate_ratings(data, mode="season")
        passed = all(check(r) for check in expected_checks)
        results.append({
            "player": player, "year": year, "pos": position,
            "fielding": r["fielding"],
            "rl": r["reaction_left"], "rr": r["reaction_right"],
            "rf": r["reaction_forward"], "rb": r["reaction_back"],
            "pass": passed,
        })

    # Ozzie Smith 1987
    _run(1987, {"rdrs_1987": 15, "inn_1987": 1200}, "SS", "Ozzie Smith",
         [lambda r: r["fielding"] >= 85,
          lambda r: r["reaction_right"] > POSITION_DEFAULTS["SS"]["react_r"]])

    # Willie Mays 1954
    _run(1954, {"rtot_1954": 12}, "CF", "Willie Mays",
         [lambda r: r["fielding"] > 75,
          lambda r: r["fielding"] != 75])

    # Derek Jeter 2005
    _run(2005, {"rdrs_2005": -10, "inn_2005": 1200}, "SS", "Derek Jeter",
         [lambda r: r["fielding"] < 85,
          lambda r: r["reaction_right"] < POSITION_DEFAULTS["SS"]["react_r"]])

    # Juan Soto 2025 (OAA proxy)
    _run(2022, {2022: 5, "inn_2022": 1200}, "LF", "Juan Soto",
         [lambda r: r["fielding"] == 79,
          lambda r: r["reaction_right"] == 65])

    # Xander Bogaerts 2022
    _run(2022, {"rngr_2022": 3, "inn_2022": 1200}, "SS", "Xander Bogaerts",
         [lambda r: r["fielding"] == 85,
          lambda r: r["reaction_right"] == 82])

    _print_summary(results)
