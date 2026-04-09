"""
Integration spot-checks for BBRef position normalization.

Constructs synthetic data dicts for four spot-check scenarios, calls
calculate_ratings(), and asserts position and position-dependent defaults.

Spot-checks:
  1. Nap Lajoie 1901  (*1B)  — arm_strength uses 1B defaults, not OF defaults
  2. Slash-composite player  (1B/OF) — infield position wins
  3. position_override wins  (*1B scraped, LF override) — override takes precedence
  4. Juan Soto 2025   (LF, OAA=5) — modern-era preservation, byte-for-byte identical

Run with:
  "C:/Users/Alex/Codex Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" \
      -m pytest test_position_normalization_integration.py -v
"""

import pytest
from generate_card import calculate_ratings, POSITION_DEFAULTS, normalize_position


# ---------------------------------------------------------------------------
# Shared helper (same _make_data pattern as other test files)
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
    header = (
        f"{'Spot-check':<35} {'Pos':<4} {'arm_str':<9} {'Status'}"
    )
    print("\n" + "=" * 65)
    print("POSITION NORMALIZATION INTEGRATION SPOT-CHECK SUMMARY")
    print("=" * 65)
    print(header)
    print("-" * 65)
    for row in results:
        status = "PASS" if row["pass"] else "FAIL"
        print(
            f"{row['label']:<35} {row['pos']:<4} {row['arm_str']:<9} {status}"
        )
    print("=" * 65)


# ---------------------------------------------------------------------------
# Spot-check 1: Nap Lajoie 1901 — *1B
#
# normalize_position("*1B") == "1B", so calculate_ratings() should use
# 1B position defaults, not OF defaults.
# ---------------------------------------------------------------------------

class TestNapLajoie1901:
    """Nap Lajoie 1901 — *1B must resolve to 1B, not OF."""

    YEAR = 1901
    RAW_POS = "*1B"

    @pytest.fixture
    def ratings(self):
        data = _make_data(self.YEAR, {}, position=normalize_position(self.RAW_POS))
        return calculate_ratings(data, mode="season")

    def test_position_is_1b(self, ratings):
        """ratings['position'] must be '1B', not 'OF'."""
        assert ratings["position"] == "1B", (
            f"Lajoie 1901: expected position='1B', got '{ratings['position']}'. "
            f"normalize_position('*1B') must strip the asterisk."
        )

    def test_arm_strength_matches_1b_default(self, ratings):
        """arm_strength must equal the 1B default (58), not the OF default (68)."""
        expected = POSITION_DEFAULTS["1B"]["arm_str"]
        assert ratings["arm_strength"] == expected, (
            f"Lajoie 1901: arm_strength={ratings['arm_strength']}, "
            f"expected 1B default={expected} (not OF default={POSITION_DEFAULTS['OF']['arm_str']}). "
            f"Position normalization must route to 1B defaults."
        )

    def test_arm_strength_not_of_default(self, ratings):
        """arm_strength must NOT equal the OF fallback default (68)."""
        of_arm = POSITION_DEFAULTS["OF"]["arm_str"]
        assert ratings["arm_strength"] != of_arm, (
            f"Lajoie 1901: arm_strength={ratings['arm_strength']} equals OF default {of_arm}. "
            f"Bug not fixed — *1B still falling through to OF."
        )


# ---------------------------------------------------------------------------
# Spot-check 2: Slash-composite player — 1B/OF
#
# normalize_position("1B/OF") == "1B" — infield position wins.
# ---------------------------------------------------------------------------

class TestSlashComposite:
    """Slash-composite player (1B/OF) — infield position must win."""

    YEAR = 2010
    RAW_POS = "1B/OF"

    @pytest.fixture
    def ratings(self):
        data = _make_data(self.YEAR, {}, position=normalize_position(self.RAW_POS))
        return calculate_ratings(data, mode="season")

    def test_position_is_1b(self, ratings):
        """ratings['position'] must be '1B' — first token before '/' wins."""
        assert ratings["position"] == "1B", (
            f"Slash-composite: expected position='1B', got '{ratings['position']}'. "
            f"normalize_position('1B/OF') must take the first token."
        )


# ---------------------------------------------------------------------------
# Spot-check 3: position_override wins over messy scraped position
#
# data["position"] = normalize_position("*1B") == "1B", but
# position_override="LF" must win — ratings["position"] == "LF".
# ---------------------------------------------------------------------------

class TestPositionOverrideWins:
    """position_override must win even when scraped position is messy."""

    YEAR = 2005
    RAW_POS = "*1B"
    OVERRIDE = "LF"

    @pytest.fixture
    def ratings(self):
        data = _make_data(self.YEAR, {}, position=normalize_position(self.RAW_POS))
        return calculate_ratings(data, position_override=self.OVERRIDE, mode="season")

    def test_position_is_override(self, ratings):
        """ratings['position'] must equal the override ('LF'), not the scraped value."""
        assert ratings["position"] == self.OVERRIDE, (
            f"Override test: expected position='{self.OVERRIDE}', got '{ratings['position']}'. "
            f"position_override must win over any scraped position value."
        )


# ---------------------------------------------------------------------------
# Spot-check 4: Juan Soto 2025 — modern-era preservation
#
# LF, OAA=5, inn=1200 — OAA path must be byte-for-byte identical.
# Expected values observed from the fixed code (same as test_integration_spotchecks.py).
# ---------------------------------------------------------------------------

class TestJuanSoto2025Preservation:
    """Juan Soto 2025 — modern-era OAA path must be byte-for-byte identical."""

    # Use 2022 as proxy year (same OAA path logic; Statcast era)
    YEAR = 2022
    POS = "LF"
    # Values observed on fixed code (same as test_integration_spotchecks.py TestJuanSoto2025)
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

    def test_position_is_lf(self, ratings):
        """Already-canonical 'LF' must pass through unchanged."""
        assert ratings["position"] == "LF", (
            f"Soto 2025: expected position='LF', got '{ratings['position']}'."
        )

    def test_fielding_unchanged(self, ratings):
        """OAA-based fielding (2.09*OAA+68.6) must be byte-for-byte identical."""
        assert ratings["fielding"] == self.EXPECTED_FIELDING, (
            f"Soto 2025 (OAA=5, LF): fielding changed — "
            f"expected {self.EXPECTED_FIELDING}, got {ratings['fielding']}."
        )

    def test_reactions_unchanged(self, ratings):
        """All four OAA-based reactions must be byte-for-byte identical."""
        assert ratings["reaction_left"] == self.EXPECTED_RL, (
            f"Soto 2025: reaction_left — expected {self.EXPECTED_RL}, got {ratings['reaction_left']}"
        )
        assert ratings["reaction_right"] == self.EXPECTED_RR, (
            f"Soto 2025: reaction_right — expected {self.EXPECTED_RR}, got {ratings['reaction_right']}"
        )
        assert ratings["reaction_forward"] == self.EXPECTED_RF, (
            f"Soto 2025: reaction_forward — expected {self.EXPECTED_RF}, got {ratings['reaction_forward']}"
        )
        assert ratings["reaction_back"] == self.EXPECTED_RB, (
            f"Soto 2025: reaction_back — expected {self.EXPECTED_RB}, got {ratings['reaction_back']}"
        )


# ---------------------------------------------------------------------------
# Summary fixture — prints the table after all tests run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def print_summary(request):
    """Print a summary table after all spot-check tests complete."""
    yield
    results = []

    def _run(label, year, oaa_data, position, override, checks):
        data = _make_data(year, oaa_data, position=position)
        r = calculate_ratings(data, position_override=override, mode="season")
        passed = all(check(r) for check in checks)
        results.append({
            "label": label,
            "pos": r["position"],
            "arm_str": r["arm_strength"],
            "pass": passed,
        })

    # Spot-check 1: Nap Lajoie 1901
    _run(
        "Lajoie 1901 (*1B)", 1901, {}, normalize_position("*1B"), None,
        [lambda r: r["position"] == "1B",
         lambda r: r["arm_strength"] == POSITION_DEFAULTS["1B"]["arm_str"]],
    )

    # Spot-check 2: Slash-composite 1B/OF
    _run(
        "Slash-composite (1B/OF)", 2010, {}, normalize_position("1B/OF"), None,
        [lambda r: r["position"] == "1B"],
    )

    # Spot-check 3: position_override wins
    _run(
        "Override wins (*1B -> LF)", 2005, {}, normalize_position("*1B"), "LF",
        [lambda r: r["position"] == "LF"],
    )

    # Spot-check 4: Juan Soto 2025 preservation
    _run(
        "Soto 2025 (OAA=5, LF)", 2022, {2022: 5, "inn_2022": 1200}, "LF", None,
        [lambda r: r["fielding"] == 79,
         lambda r: r["reaction_left"] == 68,
         lambda r: r["reaction_right"] == 65],
    )

    _print_summary(results)
