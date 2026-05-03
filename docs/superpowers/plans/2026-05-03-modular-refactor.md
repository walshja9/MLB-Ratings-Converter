# MLB The Show Card Generator — Modular Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the 2,148-line monolithic `generate_card.py` into a modular package so formulas are independently testable, coefficients are versioned in a registry, and data models use typed dataclasses instead of raw dicts.

**Architecture:** The current `generate_card.py` gets replaced by a `ratings/` package. Each domain (hitting formulas, pitching formulas, fielding, baserunning, data pulling, constants) becomes its own module. A thin `engine.py` orchestrates them. The existing `app.py` and CLI entry point import from the package instead of the monolith. All existing tests continue to pass at every step.

**Tech Stack:** Python 3.12, Flask, numpy, pandas, pybaseball, cloudscraper, pytest

**Project root:** `C:/Users/Alex/Claude Context/MLB The Show 26 - Reverse Engineer Player Ratings/`

**Python interpreter:** `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe"`

**Alias used in this plan:** `PYTHON` = the interpreter path above. In all commands, substitute the full path.

---

## File Structure (final state)

```
ratings/
├── __init__.py            # public API re-exports
├── engine.py              # orchestration: pull -> calculate -> format
├── models.py              # dataclasses: BattingStats, PitchingStats, FieldingData, etc.
├── coefficients.py        # versioned formula coefficients registry
├── constants.py           # POSITION_DEFAULTS, baselines, thresholds
├── formulas/
│   ├── __init__.py
│   ├── shared.py          # clamp(), dampen(), trust_factor()
│   ├── hitting.py         # vision(), contact_r(), power_r(), etc.
│   ├── pitching.py        # velocity(), control(), k_per_9(), etc.
│   ├── fielding.py        # 7-tier chain, arm_strength(), arm_accuracy(), reactions()
│   └── baserunning.py     # speed(), stealing(), br_aggressiveness()
├── data/
│   ├── __init__.py
│   ├── bbref.py           # BBRef scraping (moved from bbref_scraper.py)
│   ├── statcast.py        # Statcast batter + pitcher pulls
│   ├── fangraphs.py       # FG fielding cache + Playwright
│   ├── lookup.py          # MLBAM ID lookup
│   └── pulling.py         # pull_all_data(), pull_all_pitcher_data() orchestration
└── display.py             # ASCII card + verbose output
tests/
├── test_formulas_hitting.py
├── test_formulas_pitching.py
├── test_formulas_fielding.py
├── test_formulas_baserunning.py
├── test_models.py
├── test_coefficients.py
├── test_integration_spotchecks.py      (existing, updated imports)
├── test_pre_oaa_fielding.py            (existing, updated imports)
├── test_bbref_position_normalization.py (existing, updated imports)
├── test_position_normalization_integration.py (existing, updated imports)
├── test_pre2015_speed_arm.py           (existing, updated imports)
```

---

### Task 1: Create the package skeleton and shared utilities

**Files:**
- Create: `ratings/__init__.py`
- Create: `ratings/formulas/__init__.py`
- Create: `ratings/formulas/shared.py`
- Create: `ratings/data/__init__.py`
- Create: `ratings/constants.py`
- Test: `tests/test_formulas_shared.py` (new)

- [ ] **Step 1: Write failing tests for clamp() and trust_factor()**

```python
# tests/test_formulas_shared.py
"""Unit tests for shared formula utilities."""
import pytest
from ratings.formulas.shared import clamp, trust_factor, dampen


class TestClamp:
    def test_clamp_normal(self):
        assert clamp(50.4) == 50

    def test_clamp_floor(self):
        assert clamp(-10) == 0

    def test_clamp_ceiling(self):
        assert clamp(120) == 99

    def test_clamp_rounds(self):
        assert clamp(50.6) == 51

    def test_clamp_zero(self):
        assert clamp(0) == 0

    def test_clamp_99(self):
        assert clamp(99) == 99


class TestTrustFactor:
    def test_full_trust(self):
        assert trust_factor(500, threshold=200) == 1.0

    def test_zero_trust(self):
        assert trust_factor(0, threshold=200) == 0.0

    def test_half_trust(self):
        assert trust_factor(100, threshold=200) == 0.5

    def test_caps_at_one(self):
        assert trust_factor(1000, threshold=200) == 1.0


class TestDampen:
    def test_full_trust_no_dampening(self):
        assert dampen(80, trust=1.0, league_avg=65) == 80

    def test_zero_trust_returns_avg(self):
        assert dampen(80, trust=0.0, league_avg=65) == 65

    def test_half_trust_blends(self):
        result = dampen(80, trust=0.5, league_avg=60)
        assert result == 70  # 0.5*80 + 0.5*60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_formulas_shared.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ratings'`

- [ ] **Step 3: Create package skeleton and implement shared.py**

```python
# ratings/__init__.py
"""MLB The Show 26 Rating Engine."""

# ratings/formulas/__init__.py
"""Formula modules for attribute calculation."""

# ratings/data/__init__.py
"""Data pulling and caching modules."""
```

```python
# ratings/formulas/shared.py
"""Shared utilities used by all formula modules."""


def clamp(val: float) -> int:
    """Clamp a value to 0-99 and round to nearest integer."""
    return max(0, min(99, round(val)))


def trust_factor(sample: float, threshold: float) -> float:
    """Compute a trust factor from 0.0 to 1.0 based on sample size.

    Returns min(sample / threshold, 1.0). At sample >= threshold,
    trust is 1.0 (full weight on observed data). Below threshold,
    trust scales linearly.
    """
    return min(sample / threshold, 1.0)


def dampen(raw_rating: float, trust: float, league_avg: float = 65) -> int:
    """Blend a raw rating toward league average based on trust.

    At trust=1.0, returns raw_rating clamped.
    At trust=0.0, returns league_avg clamped.
    """
    return clamp(trust * raw_rating + (1 - trust) * league_avg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_formulas_shared.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Extract constants to ratings/constants.py**

Move all constant dicts from `generate_card.py` lines 234-267 into `ratings/constants.py`:

```python
# ratings/constants.py
"""Position defaults, baselines, and threshold constants."""

FIELDING_YEAR_WEIGHTS = {0: 0.45, -1: 0.30, -2: 0.15, -3: 0.10}

POSITION_DEFAULTS = {
    "C":  {"arm_str": 80, "arm_acc": 65, "react_l": 0, "react_r": 0, "react_f": 0, "react_b": 0, "clutch": 65, "bunt": 35, "drag": 25},
    "1B": {"arm_str": 58, "arm_acc": 62, "react_l": 65, "react_r": 60, "react_f": 50, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 25},
    "2B": {"arm_str": 60, "arm_acc": 70, "react_l": 65, "react_r": 70, "react_f": 75, "react_b": 60, "clutch": 65, "bunt": 45, "drag": 35},
    "SS": {"arm_str": 68, "arm_acc": 75, "react_l": 55, "react_r": 80, "react_f": 80, "react_b": 70, "clutch": 65, "bunt": 35, "drag": 25},
    "3B": {"arm_str": 65, "arm_acc": 72, "react_l": 55, "react_r": 60, "react_f": 75, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 35},
    "LF": {"arm_str": 60, "arm_acc": 65, "react_l": 60, "react_r": 55, "react_f": 55, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 30},
    "CF": {"arm_str": 75, "arm_acc": 70, "react_l": 70, "react_r": 65, "react_f": 60, "react_b": 60, "clutch": 65, "bunt": 45, "drag": 40},
    "RF": {"arm_str": 75, "arm_acc": 70, "react_l": 60, "react_r": 60, "react_f": 55, "react_b": 60, "clutch": 65, "bunt": 35, "drag": 25},
    "DH": {"arm_str": 55, "arm_acc": 65, "react_l": 45, "react_r": 45, "react_f": 45, "react_b": 45, "clutch": 65, "bunt": 35, "drag": 25},
    "OF": {"arm_str": 68, "arm_acc": 68, "react_l": 63, "react_r": 60, "react_f": 57, "react_b": 60, "clutch": 65, "bunt": 38, "drag": 30},
}

TRACKING_SPEED_BASELINES = {
    "C": 18, "1B": 28, "2B": 48, "SS": 50, "3B": 40,
    "LF": 38, "CF": 52, "RF": 40, "DH": 15, "OF": 44,
}

ARM_ASSIST_BASELINES = {
    "C": 1.0, "1B": 2.0, "2B": 4.5, "SS": 4.0, "3B": 2.5,
    "LF": 4.0, "CF": 6.0, "RF": 8.0, "OF": 5.5,
}

ARM_STRENGTH_SLOPES = {
    "C": 0.8, "1B": 0.8, "2B": 0.6, "SS": 0.7, "3B": 1.0,
    "LF": 2.2, "CF": 1.8, "RF": 1.9, "OF": 2.0,
}

ARM_ERROR_BASELINES = {
    "C": 0.020, "1B": 0.018, "2B": 0.040, "SS": 0.045, "3B": 0.040,
    "LF": 0.015, "CF": 0.012, "RF": 0.015, "OF": 0.015,
}

CANONICAL_POSITIONS = {"RF", "LF", "CF", "1B", "2B", "SS", "3B", "C", "DH"}

POS_FIELDING_BASELINES = {
    "C": 70, "1B": 50, "2B": 75, "SS": 85, "3B": 65,
    "LF": 50, "CF": 75, "RF": 60, "DH": 35, "OF": 55,
}

PITCHER_FIELDING_DEFAULTS = {
    "fielding": 50, "arm_str": 65, "arm_acc": 50,
    "react_l": 50, "react_r": 50, "react_f": 50, "react_b": 50,
}

REACTION_DIR_WEIGHTS = {
    "SS":  {"l": 0.85, "r": 1.15, "f": 1.05, "b": 0.90},
    "2B":  {"l": 0.95, "r": 1.05, "f": 1.10, "b": 0.85},
    "3B":  {"l": 0.90, "r": 0.95, "f": 1.15, "b": 0.90},
    "1B":  {"l": 1.05, "r": 0.95, "f": 0.85, "b": 0.95},
    "CF":  {"l": 1.00, "r": 1.00, "f": 0.95, "b": 0.95},
    "RF":  {"l": 0.95, "r": 0.95, "f": 0.85, "b": 0.95},
    "LF":  {"l": 0.95, "r": 0.90, "f": 0.85, "b": 0.95},
    "OF":  {"l": 0.95, "r": 0.93, "f": 0.87, "b": 0.93},
}

# Pre-OAA fielding formula constants
RDRS_FIELD_SLOPE = 2.5
RDRS_FIELD_INTERCEPT = 68
RTOT_FIELD_SLOPE = 2.0
RTOT_FIELD_INTERCEPT = 68
RDRS_REACT_SLOPE = 1.2
RTOT_REACT_SLOPE = 1.0
RTOT_PARTIAL_TRUST = 0.4

# League averages for dampening
LEAGUE_AVG_K = 25.0
LEAGUE_AVG_BB = 8.0
LEAGUE_AVG_BA = 0.248
LEAGUE_AVG_ISO = 0.155
LEAGUE_AVG_HR_RATE = 0.030
```

- [ ] **Step 6: Commit**

```bash
git add ratings/ tests/test_formulas_shared.py
git commit -m "feat: create ratings package skeleton with shared utils and constants"
```

---

### Task 2: Create the coefficient registry

**Files:**
- Create: `ratings/coefficients.py`
- Test: `tests/test_coefficients.py` (new)

- [ ] **Step 1: Write failing tests for the coefficient registry**

```python
# tests/test_coefficients.py
"""Tests for the coefficient registry."""
import pytest
from ratings.coefficients import HITTING, PITCHING, OVR


class TestHittingCoefficients:
    def test_vision_has_required_keys(self):
        v = HITTING["vision"]
        assert "slope" in v
        assert "intercept" in v
        assert "rmse" in v

    def test_vision_values_match_current(self):
        v = HITTING["vision"]
        assert v["slope"] == -3.07
        assert v["intercept"] == 126.9

    def test_all_hitter_formulas_present(self):
        expected = {
            "vision", "discipline", "contact_r_statcast", "contact_r_career",
            "contact_r_season", "contact_l", "power_r", "power_l",
            "speed_statcast", "speed_fg", "stealing_active", "stealing_inactive",
            "br_agg_active", "br_agg_inactive", "durability_season",
            "durability_career", "clutch_statcast", "clutch_pre_statcast",
        }
        assert expected.issubset(set(HITTING.keys()))


class TestPitchingCoefficients:
    def test_velocity_values(self):
        v = PITCHING["velocity"]
        assert v["slope"] == 3.1
        assert v["intercept"] == -214

    def test_all_pitcher_formulas_present(self):
        expected = {
            "velocity", "control", "hr_per_9", "h_per_9_left", "h_per_9_right",
            "k_per_9", "stamina_sp", "stamina_rp", "pitching_clutch", "break_",
        }
        assert expected.issubset(set(PITCHING.keys()))


class TestOVRCoefficients:
    def test_hitter_ovr(self):
        o = OVR["hitter"]
        assert o["core_hitting"] == pytest.approx(0.9082, abs=0.001)
        assert o["speed"] == pytest.approx(0.1058, abs=0.001)
        assert o["durability"] == pytest.approx(0.1924, abs=0.001)

    def test_pitcher_ovr(self):
        o = OVR["pitcher"]
        assert o["pitching"] == pytest.approx(1.0345, abs=0.001)
        assert o["durability"] == pytest.approx(0.1173, abs=0.001)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_coefficients.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the coefficient registry**

```python
# ratings/coefficients.py
"""Versioned formula coefficients.

Each entry records the regression coefficients, RMSE, and refit date.
recalibrate_all.py can write updated values here after a refit cycle.
"""

HITTING = {
    "vision": {
        "slope": -3.07, "intercept": 126.9,
        "rmse": 7.6, "refit_date": "2026-04-20",
    },
    "discipline": {
        "slope": 4.86, "intercept": 17.2,
        "rmse": 10.7, "refit_date": "2026-04-20",
    },
    "contact_r_statcast": {
        "ba_coeff": 240, "ev_coeff": 2.09, "intercept": -168,
        "rmse": 8.8, "refit_date": "2026-04-20", "min_pa": 100,
    },
    "contact_r_career": {
        "ba_coeff": 372, "intercept": -29, "season_weight": 0.55, "career_weight": 0.45,
        "rmse": 10.1, "refit_date": "2026-04-20",
    },
    "contact_r_season": {
        "ba_coeff": 372, "intercept": -29,
        "rmse": 10.1, "refit_date": "2026-04-20",
    },
    "contact_l": {
        "ba_coeff": 281, "intercept": -3,
        "rmse": 12.0, "refit_date": "2026-04-20",
    },
    "power_r": {
        "iso_coeff": 91.6, "hr_rate_coeff": 502.4, "intercept": 31.8,
        "rmse": 17.5, "refit_date": "2026-04-21",
    },
    "power_l": {
        "iso_coeff": 18.6, "hr_rate_coeff": 764.6, "intercept": 31.2,
        "rmse": 13.3, "refit_date": "2026-04-21",
    },
    "speed_statcast": {
        "sprint_coeff": 7.36, "sb_coeff": 0.45, "intercept": -147.1,
        "rmse": 13.5, "refit_date": "2026-04-21",
    },
    "speed_fg": {
        "slope": 9.42, "intercept": 19.1,
        "rmse": None, "refit_date": "2026-04-20",
    },
    "stealing_active": {
        "slope": 2.0, "intercept": 9,
        "rmse": 8.6, "refit_date": "2026-04-20",
    },
    "stealing_inactive": {
        "base": 3, "speed_coeff": 0.04,
        "refit_date": "2026-04-20",
    },
    "br_agg_active": {
        "slope": 1.87, "intercept": 14,
        "rmse": 9.9, "refit_date": "2026-04-20",
    },
    "br_agg_inactive": {
        "base": 3, "speed_coeff": 0.03,
        "refit_date": "2026-04-20",
    },
    "durability_season": {
        "slope": 0.17, "intercept": 72, "baseline": 78,
        "rmse": 4.9, "refit_date": "2026-04-20",
    },
    "durability_career": {
        "slope": 0.16, "intercept": 72, "baseline": 78,
        "season_weight": 0.55, "career_weight": 0.45,
        "rmse": 4.9, "refit_date": "2026-04-20",
    },
    "clutch_statcast": {
        "ba_coeff": -161.7, "war_coeff": 2.2, "risp_coeff": 239.4, "intercept": 39.1,
        "rmse": 16.5, "refit_date": "2026-04-21",
    },
    "clutch_pre_statcast": {
        "ba_coeff": 93, "war_coeff": 2.6, "intercept": 34,
        "rmse": None, "refit_date": "2026-04-20",
    },
    "fielding_oaa": {
        "slope": 2.09, "intercept": 68.6,
        "rmse": 11.9, "refit_date": "2026-04-20",
    },
    "fielding_fg_def": {
        "slope": 1.38, "intercept": 67.3,
        "refit_date": "2026-04-20",
    },
    "fielding_rngr": {
        "slope": 1.46, "intercept": 72.2,
        "refit_date": "2026-04-20",
    },
}

PITCHING = {
    "velocity": {
        "slope": 3.1, "intercept": -214,
        "rmse": 9.4, "refit_date": "2026-04-20",
    },
    "control": {
        "bb9_coeff": -0.7, "whip_coeff": -71.2, "intercept": 149.9,
        "rmse": 9.5, "refit_date": "2026-04-22",
    },
    "hr_per_9": {
        "slope": -7.0, "intercept": 96.3,
        "rmse": 6.0, "refit_date": "2026-04-22",
    },
    "h_per_9_left": {
        "slope": -215.5, "intercept": 128.8,
        "rmse": 6.9, "refit_date": "2026-04-22",
    },
    "h_per_9_right": {
        "slope": -49.6, "intercept": 98.3,
        "rmse": 6.1, "refit_date": "2026-04-22",
    },
    "k_per_9": {
        "slope": 2.2, "intercept": 15,
        "rmse": 9.6, "refit_date": "2026-04-22",
    },
    "h_per_9_overall": {
        "slope": -7.86, "intercept": 131.1,
        "refit_date": "2026-04-22",
    },
    "k_per_9_overall": {
        "slope": 2.5, "intercept": 15,
        "refit_date": "2026-04-22",
    },
    "stamina_sp": {
        "slope": 0.62, "intercept": 75,
        "rmse": 7.6, "refit_date": "2026-04-22",
    },
    "stamina_rp": {
        "slope": 4.8, "intercept": -268,
        "rmse": None, "refit_date": "2026-04-22",
    },
    "stamina_sp_career": {
        "slope": 0.62, "intercept": 75,
        "season_weight": 0.4, "career_weight": 0.6,
        "refit_date": "2026-04-22",
    },
    "pitching_clutch": {
        "war_coeff": 2.7, "intercept": 59.3,
        "rmse": 4.1, "refit_date": "2026-04-22",
    },
    "break_": {
        "base": 75, "pitch_bonus": 3, "offspeed_coeff": 0.2,
        "rmse": 7.6, "refit_date": "2026-04-22",
    },
}

OVR = {
    "hitter": {
        "core_hitting": 0.9082, "fielding": 0.0, "speed": 0.1058, "durability": 0.1924,
        "rmse": 4.2, "refit_date": "2026-04-19", "n_players": 18,
    },
    "pitcher": {
        "pitching": 1.0345, "fielding": 0.0, "durability": 0.1173,
        "rmse": 3.6, "refit_date": "2026-04-19", "n_players": 10,
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_coefficients.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ratings/coefficients.py tests/test_coefficients.py
git commit -m "feat: add versioned coefficient registry with all current formula values"
```

---

### Task 3: Extract hitting formulas with unit tests

**Files:**
- Create: `ratings/formulas/hitting.py`
- Create: `tests/test_formulas_hitting.py`

This is the largest task — it extracts every hitter attribute formula from `generate_card.py` lines 1284-1683 into standalone, testable functions.

- [ ] **Step 1: Write failing tests for hitting formulas**

```python
# tests/test_formulas_hitting.py
"""Unit tests for hitter attribute formulas."""
import pytest
from ratings.formulas.hitting import (
    vision, discipline, contact_right, contact_left,
    power_right, power_left, durability, batting_clutch,
)


class TestVision:
    def test_low_k_high_vision(self):
        # 10% K rate, full trust -> -3.07*10 + 126.9 = 96.2 -> 96
        assert vision(k_pct=10.0, pa=500) == 96

    def test_high_k_low_vision(self):
        # 35% K rate, full trust -> -3.07*35 + 126.9 = 19.45 -> 19
        assert vision(k_pct=35.0, pa=500) == 19

    def test_low_pa_dampens_toward_avg(self):
        # 10% K, 50 PA -> trust=0.25 -> eff_k = 0.25*10 + 0.75*25 = 21.25
        # -3.07*21.25 + 126.9 = 61.7 -> 62
        assert vision(k_pct=10.0, pa=50) == 62

    def test_zero_pa(self):
        # 0 PA -> trust=0 -> effective_k = 25.0 -> -3.07*25 + 126.9 = 50.15 -> 50
        assert vision(k_pct=15.0, pa=0) == 50


class TestDiscipline:
    def test_high_walk_rate(self):
        # 15% BB, full trust -> 4.86*15 + 17.2 = 90.1 -> 90
        assert discipline(bb_pct=15.0, pa=500) == 90

    def test_low_pa_dampens(self):
        # 15% BB, 50 PA -> trust=0.25 -> eff_bb = 0.25*15 + 0.75*8 = 9.75
        # 4.86*9.75 + 17.2 = 64.6 -> 65
        assert discipline(bb_pct=15.0, pa=50) == 65


class TestContactRight:
    def test_statcast_path(self):
        # BA=0.300, EV=90, pa=500 -> 240*0.300 + 2.09*90 - 168 = 72+188.1-168 = 92.1 -> 92
        assert contact_right(ba_vs_r=0.300, pa=500, avg_ev=90.0) == 92

    def test_season_no_ev(self):
        # BA=0.270, no EV, not career -> 372*0.270 - 29 = 71.4 -> 71
        assert contact_right(ba_vs_r=0.270, pa=500, avg_ev=None) == 71

    def test_career_path(self):
        # BA=0.270, career_ba=0.290, career mode
        # blended = 0.55*0.270 + 0.45*0.290 = 0.279
        # 372*0.279 - 29 = 74.8 -> 75
        assert contact_right(ba_vs_r=0.270, pa=500, avg_ev=None,
                             use_career=True, career_ba=0.290) == 75


class TestContactLeft:
    def test_full_trust_split(self):
        # BA_vL=0.280, full trust -> 281*0.280 - 3 = 75.7 -> 76
        assert contact_left(ba_vs_l=0.280, pa_vs_l=200, fallback_ba=0.260) == 76

    def test_no_split_data(self):
        # pa_vs_l=0, trust=0 -> uses fallback_ba -> 281*0.260 - 3 = 70.1 -> 70
        assert contact_left(ba_vs_l=0.0, pa_vs_l=0, fallback_ba=0.260) == 70


class TestPowerRight:
    def test_basic(self):
        # iso=0.200, hr_rate=0.040 -> 91.6*0.200 + 502.4*0.040 + 31.8 = 18.32+20.1+31.8 = 70.2 -> 70
        assert power_right(iso_blend=0.200, hr_rate=0.040) == 70

    def test_high_hr_rate(self):
        # iso=0.250, hr_rate=0.060 -> 91.6*0.250 + 502.4*0.060 + 31.8 = 22.9+30.1+31.8 = 84.8 -> 85
        assert power_right(iso_blend=0.250, hr_rate=0.060) == 85


class TestPowerLeft:
    def test_basic(self):
        # iso=0.200, hr_rate=0.040 -> 18.6*0.200 + 764.6*0.040 + 31.2 = 3.72+30.58+31.2 = 65.5 -> 66
        assert power_left(iso_blend=0.200, hr_rate=0.040) == 66

    def test_hr_rate_dominates(self):
        # iso=0.100, hr_rate=0.060 -> 18.6*0.100 + 764.6*0.060 + 31.2 = 1.86+45.9+31.2 = 79.0 -> 79
        assert power_left(iso_blend=0.100, hr_rate=0.060) == 79


class TestDurability:
    def test_season_full_season(self):
        # G=155, PA=600 -> 0.17*155 + 72 = 98.35 -> 98, trust=1.0
        assert durability(games=155, pa=600, use_career=False) == 98

    def test_season_low_pa_dampens(self):
        # G=10, PA=30 -> raw=0.17*10+72=73.7->74, trust=0.15
        # 0.15*74 + 0.85*78 = 11.1+66.3 = 77.4 -> 77
        assert durability(games=10, pa=30, use_career=False) == 77

    def test_career_blends(self):
        # G=100, PA=400, career_avg_gp=140 -> gp=0.55*100+0.45*140=118
        # raw=0.16*118+72=90.88->91, trust=1.0 -> 91
        assert durability(games=100, pa=400, use_career=True, career_avg_gp=140) == 91


class TestBattingClutch:
    def test_statcast_with_risp(self):
        # ba=0.280, war=4.0, risp_ba=0.320, risp_pa=100, pa=500
        # risp_trust=1.0, eff_risp=0.320
        # raw = -161.7*0.280 + 2.2*4 + 239.4*0.320 + 39.1
        #     = -45.28 + 8.8 + 76.61 + 39.1 = 79.2
        # clutch_trust = 1.0 -> 79
        assert batting_clutch(ba=0.280, war=4.0, pa=500,
                              risp_ba=0.320, risp_pa=100) == 79

    def test_pre_statcast_fallback(self):
        # ba=0.280, war=3.0, no RISP, pa=500
        # raw = 93*0.280 + 2.6*3 + 34 = 26.04 + 7.8 + 34 = 67.8
        # clutch_trust = 1.0 -> 68
        assert batting_clutch(ba=0.280, war=3.0, pa=500) == 68

    def test_low_pa_dampens_to_50(self):
        # pa=50 -> clutch_trust=50/150=0.333
        # raw = 93*0.280 + 2.6*3 + 34 = 67.84
        # 0.333*67.84 + 0.667*50 = 22.6 + 33.4 = 55.9 -> 56
        assert batting_clutch(ba=0.280, war=3.0, pa=50) == 56
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_formulas_hitting.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement hitting formula functions**

```python
# ratings/formulas/hitting.py
"""Hitter attribute formulas.

Each function takes pre-processed stat inputs and returns a 0-99 rating.
Coefficients are imported from the registry so refit cycles auto-propagate.
"""
from ratings.formulas.shared import clamp, trust_factor
from ratings.coefficients import HITTING


def vision(k_pct: float, pa: int) -> int:
    """Vision rating from strikeout rate. RMSE=7.6."""
    c = HITTING["vision"]
    trust = trust_factor(pa, 200)
    effective_k = trust * k_pct + (1 - trust) * 25.0  # league avg K%
    return clamp(c["slope"] * effective_k + c["intercept"])


def discipline(bb_pct: float, pa: int) -> int:
    """Discipline rating from walk rate. RMSE=10.7."""
    c = HITTING["discipline"]
    trust = trust_factor(pa, 200)
    effective_bb = trust * bb_pct + (1 - trust) * 8.0  # league avg BB%
    return clamp(c["slope"] * effective_bb + c["intercept"])


def contact_right(ba_vs_r: float, pa: int, avg_ev: float | None = None,
                  use_career: bool = False, career_ba: float | None = None) -> int:
    """Contact vs RHP. Uses BA + exit velo (Statcast) or BA only."""
    if avg_ev is not None and pa >= HITTING["contact_r_statcast"]["min_pa"]:
        c = HITTING["contact_r_statcast"]
        return clamp(c["ba_coeff"] * ba_vs_r + c["ev_coeff"] * avg_ev + c["intercept"])
    elif use_career and career_ba is not None:
        c = HITTING["contact_r_career"]
        blended = c["season_weight"] * ba_vs_r + c["career_weight"] * career_ba
        return clamp(c["ba_coeff"] * blended + c["intercept"])
    else:
        c = HITTING["contact_r_season"]
        return clamp(c["ba_coeff"] * ba_vs_r + c["intercept"])


def contact_left(ba_vs_l: float, pa_vs_l: int, fallback_ba: float) -> int:
    """Contact vs LHP. Trust-blends split BA toward fallback."""
    c = HITTING["contact_l"]
    trust = trust_factor(pa_vs_l, 120)
    effective_ba = trust * ba_vs_l + (1 - trust) * fallback_ba
    return clamp(c["ba_coeff"] * effective_ba + c["intercept"])


def power_right(iso_blend: float, hr_rate: float) -> int:
    """Power vs RHP. ISO + HR rate."""
    c = HITTING["power_r"]
    return clamp(c["iso_coeff"] * iso_blend + c["hr_rate_coeff"] * hr_rate + c["intercept"])


def power_left(iso_blend: float, hr_rate: float) -> int:
    """Power vs LHP. HR rate dominates."""
    c = HITTING["power_l"]
    return clamp(c["iso_coeff"] * iso_blend + c["hr_rate_coeff"] * hr_rate + c["intercept"])


def durability(games: int, pa: int, use_career: bool = False,
               career_avg_gp: float | None = None) -> int:
    """Durability (health) rating. High floor for healthy young players."""
    dur_trust = trust_factor(pa, 200)
    if use_career and career_avg_gp is not None:
        c = HITTING["durability_career"]
        gp = c["season_weight"] * games + c["career_weight"] * career_avg_gp
        raw = clamp(c["slope"] * gp + c["intercept"])
    else:
        c = HITTING["durability_season"]
        raw = clamp(c["slope"] * games + c["intercept"])
    baseline = HITTING["durability_season"]["baseline"]
    return clamp(dur_trust * raw + (1 - dur_trust) * baseline)


def batting_clutch(ba: float, war: float, pa: int,
                   risp_ba: float | None = None, risp_pa: int = 0) -> int:
    """Batting clutch from BA + WAR + RISP BA (Statcast era)."""
    clutch_trust = trust_factor(pa, 150)

    if risp_ba is not None and risp_pa > 30:
        c = HITTING["clutch_statcast"]
        risp_trust = trust_factor(risp_pa, 100)
        eff_risp = risp_trust * risp_ba + (1 - risp_trust) * ba
        raw = c["ba_coeff"] * ba + c["war_coeff"] * war + c["risp_coeff"] * eff_risp + c["intercept"]
    else:
        c = HITTING["clutch_pre_statcast"]
        raw = c["ba_coeff"] * ba + c["war_coeff"] * war + c["intercept"]

    return clamp(clutch_trust * raw + (1 - clutch_trust) * 50)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_formulas_hitting.py -v`
Expected: All 18 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ratings/formulas/hitting.py tests/test_formulas_hitting.py
git commit -m "feat: extract hitting formulas with 18 unit tests"
```

---

### Task 4: Extract baserunning formulas with unit tests

**Files:**
- Create: `ratings/formulas/baserunning.py`
- Create: `tests/test_formulas_baserunning.py`

- [ ] **Step 1: Write failing tests for baserunning**

```python
# tests/test_formulas_baserunning.py
"""Unit tests for baserunning formulas."""
import pytest
from ratings.formulas.baserunning import (
    speed_statcast, speed_fg, speed_no_tracking,
    stealing, br_aggressiveness,
)


class TestSpeedStatcast:
    def test_fast_runner(self):
        # sprint=30.0, sb/162=30 -> 7.36*30 + 0.45*30 - 147.1 = 220.8+13.5-147.1 = 87.2 -> 87
        assert speed_statcast(sprint=30.0, sb_per_162=30.0, games=100) == 87

    def test_slow_runner(self):
        # sprint=26.0, sb/162=0 -> 7.36*26 - 147.1 = 44.3 -> 44
        assert speed_statcast(sprint=26.0, sb_per_162=0.0, games=100) == 44

    def test_tiny_sample_regresses(self):
        # sprint=30.0, sb/162=30, games=15 -> trust=0.5
        # raw = max(87.2, 15) = 87.2
        # pos baseline for SS (50) -> default = clamp(max(7.36*27+0.45*30-147.1, 50)) = max(65.6, 50) = 66
        # 0.5*87.2 + 0.5*66 = 76.6 -> 77
        assert speed_statcast(sprint=30.0, sb_per_162=30.0, games=15, pos="SS") == 77


class TestSpeedFG:
    def test_basic(self):
        # spd=5.0 -> 9.42*5 + 19.1 = 66.2 -> 66
        assert speed_fg(fg_spd=5.0) == 66


class TestStealing:
    def test_active_stealer(self):
        # sb/162=25 -> 2.0*25 + 9 = 59
        assert stealing(sb_per_162=25.0, speed=80) == 59

    def test_inactive_stealer(self):
        # sb/162=1 -> 3 + 0.04*50 = 5
        assert stealing(sb_per_162=1.0, speed=50) == 5

    def test_zero_steals(self):
        assert stealing(sb_per_162=0.0, speed=30) == 4  # 3 + 0.04*30 = 4.2 -> 4


class TestBrAggressiveness:
    def test_active(self):
        # sb/162=25 -> 1.87*25 + 14 = 60.75 -> 61
        assert br_aggressiveness(sb_per_162=25.0, speed=80) == 61

    def test_inactive(self):
        # sb/162=1 -> 3 + 0.03*50 = 4.5 -> 4
        assert br_aggressiveness(sb_per_162=1.0, speed=50) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_formulas_baserunning.py -v`
Expected: FAIL

- [ ] **Step 3: Implement baserunning formulas**

```python
# ratings/formulas/baserunning.py
"""Baserunning attribute formulas: speed, stealing, BR aggressiveness."""
from ratings.formulas.shared import clamp, trust_factor
from ratings.coefficients import HITTING
from ratings.constants import TRACKING_SPEED_BASELINES


def speed_statcast(sprint: float, sb_per_162: float, games: int,
                   pos: str = "OF") -> int:
    """Speed from Statcast sprint speed + SB rate. RMSE~13.5."""
    c = HITTING["speed_statcast"]
    raw = max(c["sprint_coeff"] * sprint + c["sb_coeff"] * sb_per_162 + c["intercept"], 15)

    if games < 30:
        baseline = TRACKING_SPEED_BASELINES.get(pos, 44)
        default = clamp(max(c["sprint_coeff"] * 27.0 + c["sb_coeff"] * sb_per_162 + c["intercept"], baseline))
        speed_trust = games / 30.0
        return clamp(speed_trust * raw + (1 - speed_trust) * default)
    return clamp(raw)


def speed_fg(fg_spd: float) -> int:
    """Speed from FanGraphs Spd metric (pre-2015)."""
    c = HITTING["speed_fg"]
    return clamp(c["slope"] * fg_spd + c["intercept"])


def speed_no_tracking(sb: int, cs: int, pa: int, triples: int,
                      games: int, pos: str) -> int:
    """Fallback speed for eras without sprint speed or FG Spd.
    Uses steal attempts, efficiency, triples, and position archetype."""
    attempts = sb + cs
    baseline = TRACKING_SPEED_BASELINES.get(pos, TRACKING_SPEED_BASELINES["OF"])
    triples_per_600 = 600.0 * triples / max(pa, 1)

    speed = baseline
    speed += 1.2 * attempts
    speed += 1.5 * min(triples_per_600, 8.0)
    if attempts >= 5:
        speed += 10.0 * ((sb / attempts) - 0.67)
    return clamp(speed)


def stealing(sb_per_162: float, speed: int) -> int:
    """Stealing rating. SB rate dominates; non-stealers get floor."""
    if sb_per_162 < 2:
        c = HITTING["stealing_inactive"]
        return clamp(c["base"] + c["speed_coeff"] * speed)
    c = HITTING["stealing_active"]
    return clamp(c["slope"] * sb_per_162 + c["intercept"])


def br_aggressiveness(sb_per_162: float, speed: int) -> int:
    """Baserunning aggressiveness. Similar to stealing but slightly different weights."""
    if sb_per_162 < 2:
        c = HITTING["br_agg_inactive"]
        return clamp(c["base"] + c["speed_coeff"] * speed)
    c = HITTING["br_agg_active"]
    return clamp(c["slope"] * sb_per_162 + c["intercept"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_formulas_baserunning.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ratings/formulas/baserunning.py tests/test_formulas_baserunning.py
git commit -m "feat: extract baserunning formulas with 9 unit tests"
```

---

### Task 5: Extract pitching formulas with unit tests

**Files:**
- Create: `ratings/formulas/pitching.py`
- Create: `tests/test_formulas_pitching.py`

- [ ] **Step 1: Write failing tests for pitching formulas**

```python
# tests/test_formulas_pitching.py
"""Unit tests for pitcher attribute formulas."""
import pytest
from ratings.formulas.pitching import (
    velocity, control, hr_per_9, h_per_9_split, k_per_9_split,
    stamina, pitching_break, pitching_clutch,
)


class TestVelocity:
    def test_hard_thrower(self):
        # 97.5 mph -> 3.1*97.5 - 214 = 88.3 -> 88
        assert velocity(fb_velo=97.5) == 88

    def test_soft_tosser(self):
        # 89.0 -> 3.1*89 - 214 = 61.9 -> 62
        assert velocity(fb_velo=89.0) == 62


class TestControl:
    def test_good_control(self):
        # bb9=2.0, whip=1.0, trust=1.0
        # -0.7*2 - 71.2*1.0 + 149.9 = -1.4 - 71.2 + 149.9 = 77.3 -> 77
        assert control(bb9=2.0, whip=1.0, trust=1.0) == 77

    def test_dampened(self):
        # same values, trust=0.5 -> dampen(77.3, 0.5, 65) = 0.5*77.3 + 0.5*65 = 71.2 -> 71
        assert control(bb9=2.0, whip=1.0, trust=0.5) == 71


class TestHRPer9:
    def test_low_hr_rate(self):
        # hr9=0.5, trust=1.0 -> -7.0*0.5 + 96.3 = 92.8 -> 93
        assert hr_per_9(hr9=0.5, trust=1.0) == 93

    def test_high_hr_rate(self):
        # hr9=2.0, trust=1.0 -> -7.0*2 + 96.3 = 82.3 -> 82
        assert hr_per_9(hr9=2.0, trust=1.0) == 82


class TestH9Split:
    def test_vs_lhb(self):
        # ba=0.220, trust=1.0 -> -215.5*0.220 + 128.8 = -47.4 + 128.8 = 81.4 -> 81
        assert h_per_9_split(ba_against=0.220, side="left", trust=1.0) == 81

    def test_vs_rhb(self):
        # ba=0.250, trust=1.0 -> -49.6*0.250 + 98.3 = -12.4 + 98.3 = 85.9 -> 86
        assert h_per_9_split(ba_against=0.250, side="right", trust=1.0) == 86


class TestK9Split:
    def test_high_k_rate(self):
        # k_pct=30, trust=1.0 -> 2.2*30 + 15 = 81
        assert k_per_9_split(k_pct=30.0, trust=1.0) == 81

    def test_dampened(self):
        # k_pct=30, trust=0.5 -> raw=81, dampen(81, 0.5, 65) = 73
        assert k_per_9_split(k_pct=30.0, trust=0.5) == 73


class TestStamina:
    def test_sp_full_season(self):
        # GS=32, role=SP -> 0.62*32 + 75 = 94.84 -> 95
        assert stamina(games=32, gs=32, role="SP") == 95

    def test_rp(self):
        # G=65, GS=0, role=RP -> 4.8*65 - 268 = 44
        assert stamina(games=65, gs=0, role="RP") == 44


class TestBreak:
    def test_diverse_arsenal(self):
        # 4 pitches >5%, offspeed_usage=65%
        # 75 + (4-2)*3 + 65*0.2 = 75+6+13 = 94, trust=1.0 -> 94
        arsenal = [
            {"code": "FF", "usage": 35}, {"code": "SL", "usage": 25},
            {"code": "CH", "usage": 22}, {"code": "CU", "usage": 18},
        ]
        assert pitching_break(arsenal=arsenal, trust=1.0) == 94

    def test_no_arsenal(self):
        assert pitching_break(arsenal=[], trust=1.0) == 80


class TestPitchingClutch:
    def test_ace(self):
        # war=5.0, ip=200 -> 2.7*5 + 59.3 = 72.8 -> 73
        assert pitching_clutch(war=5.0, career_ip=200) == 73

    def test_low_ip_dampens(self):
        # war=5.0, ip=50 -> trust=0.25 -> 0.25*72.8 + 0.75*65 = 18.2+48.75 = 67.0 -> 67
        assert pitching_clutch(war=5.0, career_ip=50) == 67
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_formulas_pitching.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pitching formula functions**

```python
# ratings/formulas/pitching.py
"""Pitcher attribute formulas."""
from ratings.formulas.shared import clamp, trust_factor, dampen
from ratings.coefficients import PITCHING


def velocity(fb_velo: float) -> int:
    """Velocity rating from fastball speed. Not dampened. RMSE=9.4."""
    c = PITCHING["velocity"]
    return clamp(c["slope"] * fb_velo + c["intercept"])


def control(bb9: float, whip: float, trust: float) -> int:
    """Control from BB/9 + WHIP. RMSE=9.5."""
    c = PITCHING["control"]
    raw = c["bb9_coeff"] * bb9 + c["whip_coeff"] * whip + c["intercept"]
    return dampen(raw, trust)


def hr_per_9(hr9: float, trust: float) -> int:
    """HR/9 rating. RMSE=6.0."""
    c = PITCHING["hr_per_9"]
    raw = c["slope"] * hr9 + c["intercept"]
    return dampen(raw, trust)


def h_per_9_split(ba_against: float, side: str, trust: float) -> int:
    """H/9 per split (left or right). Uses BA against that side."""
    key = f"h_per_9_{side}"
    c = PITCHING[key]
    raw = c["slope"] * ba_against + c["intercept"]
    return dampen(raw, trust)


def k_per_9_split(k_pct: float, trust: float) -> int:
    """K/9 per split. Same formula both sides."""
    c = PITCHING["k_per_9"]
    raw = c["slope"] * k_pct + c["intercept"]
    return dampen(raw, trust)


def stamina(games: int, gs: int, role: str,
            use_career: bool = False, career_avg_gs: float | None = None) -> int:
    """Stamina from games started (SP) or games (RP)."""
    if role == "RP" and gs == 0:
        c = PITCHING["stamina_rp"]
        return clamp(c["slope"] * games + c["intercept"])
    elif use_career and career_avg_gs is not None:
        c = PITCHING["stamina_sp_career"]
        gs_blend = c["season_weight"] * gs + c["career_weight"] * career_avg_gs
        return clamp(c["slope"] * gs_blend + c["intercept"])
    else:
        c = PITCHING["stamina_sp"]
        return clamp(c["slope"] * gs + c["intercept"])


def pitching_break(arsenal: list, trust: float) -> int:
    """Break rating from pitch diversity heuristic. Not stat-derivable."""
    if not arsenal:
        return 80
    c = PITCHING["break_"]
    pitch_types = [p for p in arsenal if p["usage"] > 5]
    num_pitches = len(pitch_types)
    offspeed_usage = sum(p["usage"] for p in arsenal if p["code"] != "FF")
    raw = c["base"] + max(0, (num_pitches - 2)) * c["pitch_bonus"] + offspeed_usage * c["offspeed_coeff"]
    return dampen(clamp(raw), trust)


def pitching_clutch(war: float, career_ip: float) -> int:
    """Pitching clutch from WAR. RMSE=4.1."""
    c = PITCHING["pitching_clutch"]
    trust = trust_factor(career_ip, 200)
    raw = c["war_coeff"] * war + c["intercept"]
    if career_ip > 100:
        return clamp(raw)
    return dampen(raw, trust)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_formulas_pitching.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ratings/formulas/pitching.py tests/test_formulas_pitching.py
git commit -m "feat: extract pitching formulas with 14 unit tests"
```

---

### Task 6: Extract fielding formulas with unit tests

**Files:**
- Create: `ratings/formulas/fielding.py`
- Create: `tests/test_formulas_fielding.py`

- [ ] **Step 1: Write failing tests for fielding formulas**

```python
# tests/test_formulas_fielding.py
"""Unit tests for fielding attribute formulas."""
import pytest
from ratings.formulas.fielding import (
    fielding_from_oaa, fielding_from_fg_def, fielding_from_rngr,
    fielding_from_rdrs, fielding_from_rtot, fielding_from_blend,
    arm_strength_from_rarm, arm_strength_from_bbref,
    arm_accuracy_from_errr, arm_accuracy_from_bbref,
    normalize_position,
)


class TestFieldingOAA:
    def test_positive_oaa(self):
        # oaa=10, trust=1.0 -> 2.09*10 + 68.6 = 89.5 -> 90
        assert fielding_from_oaa(oaa=10, def_trust=1.0, pos_baseline=55) == 90

    def test_negative_oaa(self):
        # oaa=-5, trust=1.0 -> 2.09*-5 + 68.6 = 58.2 -> 58
        assert fielding_from_oaa(oaa=-5, def_trust=1.0, pos_baseline=55) == 58

    def test_partial_trust(self):
        # oaa=10, trust=0.5, baseline=55
        # raw=90, 0.5*90 + 0.5*55 = 72.5 -> 72
        assert fielding_from_oaa(oaa=10, def_trust=0.5, pos_baseline=55) == 72


class TestFieldingPreOAA:
    def test_fg_def(self):
        # def=5, trust=1.0 -> 1.38*5 + 67.3 = 74.2 -> 74
        assert fielding_from_fg_def(fg_def=5, def_trust=1.0, pos_baseline=55) == 74

    def test_rngr(self):
        # rngr=8, trust=1.0 -> 1.46*8 + 72.2 = 83.9 -> 84
        assert fielding_from_rngr(rngr=8, def_trust=1.0, pos_baseline=55) == 84

    def test_rdrs(self):
        # rdrs=10, trust=1.0 -> 2.5*10 + 68 = 93
        assert fielding_from_rdrs(rdrs=10, def_trust=1.0, pos_baseline=55) == 93

    def test_rtot(self):
        # rtot=12, trust=1.0 -> 2.0*12 + 68 = 92
        assert fielding_from_rtot(rtot=12, def_trust=1.0, pos_baseline=55) == 92

    def test_blend(self):
        # rdrs=10 (93), rtot=12 (92), trust=1.0 -> 0.5*93 + 0.5*92 = 92.5 -> 92
        assert fielding_from_blend(rdrs=10, rtot=12, def_trust=1.0, pos_baseline=55) == 92


class TestArmStrength:
    def test_rarm_positive(self):
        # rarm=5, OF defaults arm_str=68 -> 3.9*5 + 68 = 87.5 -> 88
        assert arm_strength_from_rarm(rarm=5.0, default_arm=68) == 88

    def test_bbref_of(self):
        # assists=12, innings=1200, pos=RF -> rate=12, baseline=8
        # raw = 75 + 1.9*(12-8) = 75+7.6 = 82.6
        # trust = min(1200/900, 1) = 1.0 -> 83
        assert arm_strength_from_bbref(pos="RF", default_arm=75,
                                       assists=12, innings=1200) == 83

    def test_bbref_non_of_returns_default(self):
        assert arm_strength_from_bbref(pos="SS", default_arm=68,
                                       assists=300, innings=1200) == 68


class TestNormalizePosition:
    def test_clean(self):
        assert normalize_position("SS") == "SS"

    def test_asterisk(self):
        assert normalize_position("*1B") == "1B"

    def test_slash_composite(self):
        assert normalize_position("1B/OF") == "1B"

    def test_of_to_cf(self):
        assert normalize_position("OF") == "CF"

    def test_empty(self):
        assert normalize_position("") == "OF"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHON -m pytest tests/test_formulas_fielding.py -v`
Expected: FAIL

- [ ] **Step 3: Implement fielding formulas**

```python
# ratings/formulas/fielding.py
"""Fielding attribute formulas: fielding rating, arm, reactions, position normalization."""
from ratings.formulas.shared import clamp
from ratings.coefficients import HITTING
from ratings.constants import (
    CANONICAL_POSITIONS, ARM_ASSIST_BASELINES, ARM_STRENGTH_SLOPES,
    ARM_ERROR_BASELINES, RDRS_FIELD_SLOPE, RDRS_FIELD_INTERCEPT,
    RTOT_FIELD_SLOPE, RTOT_FIELD_INTERCEPT,
)

_BBREF_POS_CODE = {
    "1": "P", "2": "C", "3": "1B", "4": "2B", "5": "3B",
    "6": "SS", "7": "LF", "8": "CF", "9": "RF",
    "O": "CF", "D": "DH", "H": "DH",
}


def normalize_position(raw: str) -> str:
    """Map a raw BBRef Pos string to a canonical position token."""
    if not raw:
        return "OF"
    s = str(raw).strip()
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
    if s and s[0] in _BBREF_POS_CODE:
        return _BBREF_POS_CODE[s[0]]
    return "OF"


def _apply_trust(raw: int, def_trust: float, pos_baseline: int) -> int:
    """Blend raw fielding toward position baseline by defensive trust."""
    return clamp(def_trust * raw + (1 - def_trust) * pos_baseline)


def fielding_from_oaa(oaa: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from OAA (Statcast era, 2015+). RMSE=11.9."""
    c = HITTING["fielding_oaa"]
    raw = clamp(c["slope"] * oaa + c["intercept"])
    return _apply_trust(raw, def_trust, pos_baseline)


def fielding_from_fg_def(fg_def: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from FanGraphs Def metric."""
    c = HITTING["fielding_fg_def"]
    raw = clamp(c["slope"] * fg_def + c["intercept"])
    return _apply_trust(raw, def_trust, pos_baseline)


def fielding_from_rngr(rngr: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from FanGraphs RngR (range runs)."""
    c = HITTING["fielding_rngr"]
    raw = clamp(c["slope"] * rngr + c["intercept"])
    return _apply_trust(raw, def_trust, pos_baseline)


def fielding_from_rdrs(rdrs: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from BBRef DRS (Rdrs)."""
    raw = clamp(RDRS_FIELD_SLOPE * rdrs + RDRS_FIELD_INTERCEPT)
    return _apply_trust(raw, def_trust, pos_baseline)


def fielding_from_rtot(rtot: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from BBRef Total Zone (Rtot)."""
    raw = clamp(RTOT_FIELD_SLOPE * rtot + RTOT_FIELD_INTERCEPT)
    return _apply_trust(raw, def_trust, pos_baseline)


def fielding_from_blend(rdrs: float, rtot: float, def_trust: float, pos_baseline: int) -> int:
    """Fielding from blended DRS + Total Zone (when both available)."""
    raw_rdrs = RDRS_FIELD_SLOPE * rdrs + RDRS_FIELD_INTERCEPT
    raw_rtot = RTOT_FIELD_SLOPE * rtot + RTOT_FIELD_INTERCEPT
    raw = clamp(0.5 * raw_rdrs + 0.5 * raw_rtot)
    return _apply_trust(raw, def_trust, pos_baseline)


def arm_strength_from_rarm(rarm: float, default_arm: int) -> int:
    """Arm strength for outfielders from FG rARM metric."""
    return clamp(3.9 * rarm + default_arm)


def arm_strength_from_bbref(pos: str, default_arm: int,
                             assists: float | None, innings: float | None) -> int:
    """Fallback arm strength from BBRef assist rate (OF only)."""
    if pos not in ("LF", "CF", "RF", "OF"):
        return default_arm
    if assists is None or innings is None or innings <= 0:
        return default_arm
    assist_rate = 1200.0 * assists / innings
    baseline = ARM_ASSIST_BASELINES.get(pos, ARM_ASSIST_BASELINES["OF"])
    slope = ARM_STRENGTH_SLOPES.get(pos, ARM_STRENGTH_SLOPES["OF"])
    raw = default_arm + slope * (assist_rate - baseline)
    trust = min(innings / 900.0, 1.0)
    return clamp(default_arm * (1 - trust) + raw * trust)


def arm_accuracy_from_errr(errr: float, default_acc: int) -> int:
    """Arm accuracy from FG ErrR metric."""
    return clamp(3.0 * errr + default_acc)


def arm_accuracy_from_bbref(pos: str, default_acc: int,
                             errors: float | None, chances: float | None) -> int:
    """Fallback arm accuracy from BBRef error rate (OF only)."""
    if pos not in ("LF", "CF", "RF", "OF"):
        return default_acc
    if errors is None or chances is None or chances <= 0:
        return default_acc
    err_rate = errors / chances
    baseline = ARM_ERROR_BASELINES.get(pos, ARM_ERROR_BASELINES["OF"])
    raw = default_acc + (baseline - err_rate) * 350.0
    trust = min(chances / 250.0, 1.0)
    return clamp(default_acc * (1 - trust) + raw * trust)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHON -m pytest tests/test_formulas_fielding.py -v`
Expected: All 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ratings/formulas/fielding.py tests/test_formulas_fielding.py
git commit -m "feat: extract fielding formulas with 16 unit tests"
```

---

### Task 7: Wire generate_card.py to use the new formula modules

This is the integration task. `generate_card.py` keeps working as before, but its `calculate_ratings()` and `calculate_pitcher_ratings()` now call the extracted formula functions instead of inline math.

**Files:**
- Modify: `generate_card.py` (replace inline formulas with imports from `ratings/`)

- [ ] **Step 1: Run existing tests to confirm baseline**

Run: `PYTHON -m pytest test_integration_spotchecks.py test_pre_oaa_fielding.py test_bbref_position_normalization.py test_pre2015_speed_arm.py -v`
Expected: All existing tests PASS (baseline)

- [ ] **Step 2: Add imports and replace constants in generate_card.py**

At the top of `generate_card.py`, add:

```python
from ratings.constants import (
    POSITION_DEFAULTS, TRACKING_SPEED_BASELINES,
    ARM_ASSIST_BASELINES, ARM_STRENGTH_SLOPES, ARM_ERROR_BASELINES,
    FIELDING_YEAR_WEIGHTS, POS_FIELDING_BASELINES, CANONICAL_POSITIONS,
    PITCHER_FIELDING_DEFAULTS, REACTION_DIR_WEIGHTS,
    RDRS_FIELD_SLOPE, RDRS_FIELD_INTERCEPT, RTOT_FIELD_SLOPE, RTOT_FIELD_INTERCEPT,
    RDRS_REACT_SLOPE, RTOT_REACT_SLOPE, RTOT_PARTIAL_TRUST,
    LEAGUE_AVG_K, LEAGUE_AVG_BB, LEAGUE_AVG_BA, LEAGUE_AVG_ISO, LEAGUE_AVG_HR_RATE,
)
from ratings.coefficients import HITTING, PITCHING, OVR
from ratings.formulas.shared import clamp, trust_factor, dampen
from ratings.formulas.hitting import (
    vision, discipline, contact_right, contact_left,
    power_right, power_left, durability, batting_clutch,
)
from ratings.formulas.baserunning import (
    speed_statcast, speed_fg, speed_no_tracking, stealing, br_aggressiveness,
)
from ratings.formulas.pitching import (
    velocity as pitch_velocity, control as pitch_control,
    hr_per_9 as pitch_hr9, h_per_9_split, k_per_9_split,
    stamina as pitch_stamina, pitching_break, pitching_clutch as pitch_clutch,
)
from ratings.formulas.fielding import (
    normalize_position,
    fielding_from_oaa, fielding_from_fg_def, fielding_from_rngr,
    fielding_from_rdrs, fielding_from_rtot, fielding_from_blend,
    arm_strength_from_rarm, arm_strength_from_bbref,
    arm_accuracy_from_errr, arm_accuracy_from_bbref,
)
```

Remove the duplicate constant definitions from `generate_card.py` (lines 234-267) since they now come from `ratings.constants`.

Remove the duplicate `clamp()`, `estimate_speed_no_tracking()`, `estimate_arm_strength_from_bbref()`, `estimate_arm_accuracy_from_bbref()`, `normalize_position()` functions since they now come from the `ratings/` package.

- [ ] **Step 3: Replace inline formulas in calculate_ratings()**

Replace each formula block in `calculate_ratings()` with calls to the new functions. For example, the vision block (lines 1284-1292) becomes:

```python
ratings["vision"] = vision(k_pct=bat["K_pct"], pa=pa)
```

The speed block (lines 1299-1322) becomes:

```python
games_played = bat.get("G", 0) or 0
games = max(bat["G"], 1)
sb_per_162 = min(bat["SB"] / games * 162.0, 60.0)
sprint = data.get("sprint_speed")
if sprint:
    ratings["speed"] = speed_statcast(sprint, sb_per_162, games_played, pos)
elif bat.get("fg_spd"):
    ratings["speed"] = speed_fg(bat["fg_spd"])
    sprint = None
else:
    ratings["speed"] = speed_no_tracking(
        bat["SB"], bat.get("CS", 0) or 0, bat.get("PA", 0) or 0,
        bat.get("3B", 0) or 0, games_played, pos
    )
    sprint = None
```

Continue this pattern for discipline, contact_r/l, power_r/l, stealing, br_aggressiveness, durability, batting_clutch. The data preparation (split blending, trust calculations, ISO blending) stays in `calculate_ratings()` — only the final formula call delegates to the new module.

Similarly for the fielding section — replace inline slope math with calls to `fielding_from_oaa()`, `fielding_from_fg_def()`, etc.

Similarly for `calculate_pitcher_ratings()` — replace inline math with `pitch_velocity()`, `pitch_control()`, etc.

**Important:** The `estimate_ovr_hitter()` and `estimate_ovr_pitcher()` functions should now read from `OVR`:

```python
def estimate_ovr_hitter(ratings, overalls):
    o = OVR["hitter"]
    core_hitting = np.mean([
        ratings["contact_right"], ratings["contact_left"],
        ratings["power_right"], ratings["power_left"],
        ratings["vision"], ratings["discipline"],
        ratings["batting_clutch"],
    ])
    ovr = (o["core_hitting"] * core_hitting +
           o["fielding"] * overalls["fielding"] +
           o["speed"] * ratings["speed"] +
           o["durability"] * overalls["durability"])
    return clamp(ovr)
```

- [ ] **Step 4: Run all existing tests to verify nothing broke**

Run: `PYTHON -m pytest test_integration_spotchecks.py test_pre_oaa_fielding.py test_bbref_position_normalization.py test_position_normalization_integration.py test_pre2015_speed_arm.py -v`
Expected: All existing tests PASS (identical behavior)

- [ ] **Step 5: Run all new unit tests too**

Run: `PYTHON -m pytest tests/ -v`
Expected: All 67 tests PASS (shared + coefficients + hitting + pitching + fielding + baserunning)

- [ ] **Step 6: Commit**

```bash
git add generate_card.py
git commit -m "refactor: wire generate_card.py to use ratings/ formula modules"
```

---

### Task 8: Update app.py imports and verify web app works

**Files:**
- Modify: `app.py` (ensure it imports from the new structure correctly)

- [ ] **Step 1: Verify app.py still works with no changes**

`app.py` imports from `generate_card`, which itself now imports from `ratings/`. So `app.py` should work without changes. Verify:

Run: `PYTHON -c "from app import generate_card_data; print('OK')"`
Expected: `OK`

- [ ] **Step 2: Run the web app briefly to confirm**

Run: `PYTHON app.py &` then `curl http://localhost:5000/` and kill the process.
Expected: HTML response from the index page.

- [ ] **Step 3: Commit (if any changes were needed)**

```bash
git add app.py
git commit -m "chore: verify web app works with refactored ratings package"
```

---

### Task 9: Move existing tests into tests/ directory and update imports

**Files:**
- Move: `test_*.py` -> `tests/test_*.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create tests directory and move files**

```bash
mkdir -p tests
touch tests/__init__.py
mv test_integration_spotchecks.py tests/
mv test_pre_oaa_fielding.py tests/
mv test_bbref_position_normalization.py tests/
mv test_position_normalization_integration.py tests/
mv test_pre2015_speed_arm.py tests/
```

- [ ] **Step 2: Update imports in moved test files**

Each test file imports from `generate_card`. Since we've moved them into `tests/`, we need to ensure they can still find the module. Add to each test file's top:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

Or use a `conftest.py`:

```python
# tests/conftest.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

- [ ] **Step 3: Run all tests from the project root**

Run: `PYTHON -m pytest tests/ -v`
Expected: All tests PASS (old integration + new unit tests)

- [ ] **Step 4: Commit**

```bash
git add tests/ -A
git commit -m "chore: consolidate all tests into tests/ directory"
```

---

### Task 10: Wire recalibrate_all.py to write to coefficients.py

**Files:**
- Modify: `recalibrate_all.py`

Currently `recalibrate_all.py` prints new coefficients to stdout and you manually copy them into `generate_card.py`. After this task, it writes directly to `ratings/coefficients.py`.

- [ ] **Step 1: Add a write function to recalibrate_all.py**

After the existing refit logic, add:

```python
def update_coefficients_file(updates: dict, player_type: str):
    """Write updated coefficients back to ratings/coefficients.py.

    updates: dict of {formula_name: {key: value, ...}} to merge.
    player_type: 'HITTING', 'PITCHING', or 'OVR'.
    """
    import ast
    coeff_path = os.path.join(os.path.dirname(__file__), "ratings", "coefficients.py")
    with open(coeff_path, "r") as f:
        content = f.read()

    # Parse the current module to get existing dicts
    tree = ast.parse(content)
    # For each assignment, find the target dict and update it
    # This is a simple approach: re-serialize the entire dict

    from ratings import coefficients
    target = getattr(coefficients, player_type)
    for formula_name, new_values in updates.items():
        if formula_name in target:
            target[formula_name].update(new_values)
            target[formula_name]["refit_date"] = datetime.date.today().isoformat()
        else:
            new_values["refit_date"] = datetime.date.today().isoformat()
            target[formula_name] = new_values

    # Write back
    import pprint
    lines = ['"""Versioned formula coefficients.\n\nEach entry records the regression coefficients, RMSE, and refit date.\nrecalibrate_all.py can write updated values here after a refit cycle.\n"""\n']
    for name in ["HITTING", "PITCHING", "OVR"]:
        d = getattr(coefficients, name)
        lines.append(f"\n{name} = " + pprint.pformat(d, indent=4, width=100) + "\n")

    with open(coeff_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\n  Updated {len(updates)} formulas in {coeff_path}")
```

- [ ] **Step 2: Add --write flag to argparse**

```python
parser.add_argument("--write", action="store_true",
                    help="Write updated coefficients to ratings/coefficients.py")
```

- [ ] **Step 3: After refit, conditionally write**

At the end of the refit section:

```python
if args.write:
    update_coefficients_file(hitter_updates, "HITTING")
    update_coefficients_file(pitcher_updates, "PITCHING")
    update_coefficients_file(ovr_updates, "OVR")
    print("\n  Coefficients written. Run tests to verify.")
```

- [ ] **Step 4: Test the write path**

Run: `PYTHON recalibrate_all.py --skip-pull --write`
Then: `PYTHON -m pytest tests/ -v`
Expected: All tests still pass (coefficients unchanged if formulas haven't changed)

- [ ] **Step 5: Commit**

```bash
git add recalibrate_all.py
git commit -m "feat: recalibrate_all can write directly to coefficients.py with --write"
```

---

## Summary

| Task | What | Tests Added |
|------|------|-------------|
| 1 | Package skeleton + shared utils + constants | 10 |
| 2 | Coefficient registry | 6 |
| 3 | Hitting formulas | 18 |
| 4 | Baserunning formulas | 9 |
| 5 | Pitching formulas | 14 |
| 6 | Fielding formulas | 16 |
| 7 | Wire generate_card.py to new modules | 0 (existing pass) |
| 8 | Verify web app | 0 |
| 9 | Consolidate test directory | 0 (move existing) |
| 10 | Wire recalibrate to write coefficients | 0 |
| **Total** | | **73 new + existing** |

Each task produces a working commit. The monolith shrinks from 2,148 lines to ~800 (data pulling + orchestration logic that stays in `generate_card.py`). Every formula is independently testable. The coefficient registry enables automated refit-and-commit cycles.
