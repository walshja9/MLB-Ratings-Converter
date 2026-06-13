"""Pitch-name map dedup tests (plan 009).

Locks the single canonical pitch-code -> display-name map. Before the fix the
local map inside pull_pitcher_statcast was missing "SP", so a pitch coded SP
showed as the raw code in the live Statcast path but as "Splitter" in the custom
arsenal path. Now both use the module-level _PITCH_NAMES.
"""

from generate_card import _PITCH_NAMES


def test_sp_resolves_to_splitter():
    assert _PITCH_NAMES["SP"] == "Splitter"


def test_known_codes_present():
    for code in ("FF", "SL", "CU", "CH", "FS", "KC", "KN"):
        assert code in _PITCH_NAMES
