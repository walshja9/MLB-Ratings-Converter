"""Tests for the Custom Card Generator.

The core guarantee: feeding build_custom_data the same field values that
pull_all_data would produce yields IDENTICAL ratings from the engine. The
custom path and the Converter path are the same engine, two producers.
"""

from generate_card import (
    build_custom_data,
    calculate_ratings,
    calculate_pitcher_ratings,
)
from app import app


HITTER_FORM = {
    "name": "Test Masher", "team": "TST", "year": "2024", "position": "RF",
    "G": "150", "PA": "600", "BA": "0.300", "OBP": "0.400", "SLG": "0.550",
    "ISO": "0.250", "HR": "35", "3B": "2", "SB": "10", "CS": "3",
    "BB_pct": "12.0", "K_pct": "18.0", "WAR": "5.5",
}

PITCHER_FORM = {
    "name": "Test Ace", "team": "TST", "year": "2024", "role": "SP", "throws": "R",
    "IP": "190.0", "G": "31", "GS": "31", "SV": "0", "W": "15", "L": "6",
    "ERA": "2.90", "FIP": "3.10", "WHIP": "1.020",
    "K_per_9": "10.5", "BB_per_9": "2.1", "HR_per_9": "0.85", "H_per_9": "7.0",
    "K_pct": "29.0", "BB_pct": "6.0", "WAR": "5.0", "LOB_pct": "78.0", "FB_velo": "96.0",
}


def canonical_hitter_data():
    """A data dict shaped exactly as pull_all_data would, with no advanced fields."""
    return {
        "name": "Test Masher", "year": 2024,
        "batting": {
            "G": 150, "PA": 600, "BA": 0.3, "OBP": 0.4, "SLG": 0.55,
            "ISO": 0.25, "HR": 35, "3B": 2, "SB": 10, "CS": 3,
            "BB_pct": 12.0, "K_pct": 18.0, "wOBA": 0.0, "WAR": 5.5,
            "fg_spd": None, "bsr": None, "team": "TST",
        },
        "career_avg": None, "career_yearly": {},
        "sprint_speed": None, "position": "RF",
        "avg_ev": None, "barrel_stats": None, "catcher_stats": None,
        "splits": None, "fielding_oaa": {},
    }


def canonical_pitcher_data():
    return {
        "name": "Test Ace", "year": 2024, "is_pitcher": True,
        "pitching": {
            "W": 15, "L": 6, "ERA": 2.9, "FIP": 3.1, "IP": 190.0,
            "G": 31, "GS": 31, "SV": 0,
            "K_per_9": 10.5, "BB_per_9": 2.1, "HR_per_9": 0.85, "H_per_9": 7.0,
            "K_pct": 29.0, "BB_pct": 6.0, "WHIP": 1.02, "WAR": 5.0,
            "LOB_pct": 78.0, "FB_velo": 96.0, "team": "TST",
        },
        "career_avg": None, "career_yearly": {},
        "statcast": {"throws": "R"},
        "role": "SP", "sprint_speed": None,
    }


# ---- Core guarantee: equivalence ----

def test_hitter_equivalence():
    custom = build_custom_data(HITTER_FORM, is_pitcher=False, position="RF")
    canon = canonical_hitter_data()
    assert calculate_ratings(custom, "RF", "season") == calculate_ratings(canon, "RF", "season")


def test_pitcher_equivalence():
    custom = build_custom_data(PITCHER_FORM, is_pitcher=True)
    canon = canonical_pitcher_data()
    assert calculate_pitcher_ratings(custom, "season") == calculate_pitcher_ratings(canon, "season")


# ---- Builder unit tests ----

def test_hitter_builder_shape():
    d = build_custom_data(HITTER_FORM, is_pitcher=False, position="RF")
    assert d["batting"]["PA"] == 600
    assert d["batting"]["BA"] == 0.3
    assert d["position"] == "RF"
    # advanced blank -> fallback inputs
    assert d["splits"] is None
    assert d["barrel_stats"] is None
    assert d["fielding_oaa"] == {}


def test_iso_derived_from_slg_when_blank():
    form = {**HITTER_FORM}
    del form["ISO"]
    d = build_custom_data(form, is_pitcher=False, position="RF")
    assert d["batting"]["ISO"] == round(0.55 - 0.30, 3)


def test_hitter_advanced_fields_populate():
    form = {**HITTER_FORM, "sprint_speed": "29.5", "avg_ev": "92.0",
            "brl_percent": "14.0", "ba_vr": "0.310", "iso_vr": "0.270",
            "risp_ba": "0.330", "oaa": "8"}
    d = build_custom_data(form, is_pitcher=False, position="RF")
    assert d["sprint_speed"] == 29.5
    assert d["barrel_stats"]["brl_percent"] == 14.0
    assert d["splits"]["vs_RHP"]["BA"] == 0.31
    assert d["splits"]["vs_RHP"]["PA"] == round(600 * 0.7)
    assert d["splits"]["risp_ba"] == 0.33
    assert d["fielding_oaa"][2024] == 8.0  # int year key triggers OAA branch


def test_catcher_block():
    form = {**HITTER_FORM, "position": "C", "pop_2b": "1.95", "arm_mph": "82.0"}
    d = build_custom_data(form, is_pitcher=False, position="C")
    assert d["catcher_stats"] == {"pop_2b": 1.95, "arm_mph": 82.0}


def test_pitcher_role_rp():
    form = {**PITCHER_FORM, "role": "RP", "GS": "0", "G": "65", "SV": "30"}
    d = build_custom_data(form, is_pitcher=True)
    assert d["role"] == "RP"
    assert d["pitching"]["SV"] == 30


# ---- Fielding inputs ----

def test_traditional_fielding_maps_to_engine_keys():
    form = {**HITTER_FORM, "po": "300", "a": "420", "e": "8", "dp": "95"}
    d = build_custom_data(form, is_pitcher=False, position="SS")
    fo = d["fielding_oaa"]
    assert fo["ass_2024"] == 420.0
    assert fo["err_2024"] == 8.0
    assert fo["ch_2024"] == 300 + 420 + 8     # CH auto = PO + A + E
    assert fo["inn_2024"] == 150 * 8.5        # innings derived from G (=150)
    assert "rtot_2024" in fo                  # Total-Zone-style estimate present


def test_oaa_overrides_traditional():
    form = {**HITTER_FORM, "po": "300", "a": "420", "e": "8", "oaa": "14"}
    d = build_custom_data(form, is_pitcher=False, position="SS")
    assert d["fielding_oaa"][2024] == 14.0    # int year key -> OAA branch wins


def test_good_vs_bad_fielder_traditional():
    """A rangy, sure-handed SS line should beat an error-prone, low-range one."""
    good = build_custom_data({**HITTER_FORM, "po": "260", "a": "470", "e": "6"}, False, "SS")
    bad = build_custom_data({**HITTER_FORM, "po": "180", "a": "300", "e": "30"}, False, "SS")
    assert (calculate_ratings(good, "SS", "season")["fielding"]
            > calculate_ratings(bad, "SS", "season")["fielding"])


def test_fielding_oaa_raises_fielding_rating():
    """A strong OAA (full-season G -> full trust) beats the bare baseline."""
    base = build_custom_data(HITTER_FORM, is_pitcher=False, position="CF")
    fielded = build_custom_data({**HITTER_FORM, "oaa": "15"}, is_pitcher=False, position="CF")
    r_base = calculate_ratings(base, "CF", "season")
    r_fld = calculate_ratings(fielded, "CF", "season")
    assert r_fld["fielding"] > r_base["fielding"]


# ---- Derivation math (mirrors the client-side JS so the formulas stay honest) ----

def test_hitter_rate_derivation_math():
    ab, h, _2b, _3b, hr, bb, k, pa = 550, 165, 30, 3, 35, 60, 120, 615
    avg = h / ab
    slg = (h + _2b + 2 * _3b + 3 * hr) / ab
    assert round(avg, 3) == 0.3
    assert round(slg - avg, 3) == round((_2b + 2 * _3b + 3 * hr) / ab, 3)  # ISO
    assert round(100 * bb / pa, 1) == 9.8
    assert round(100 * k / pa, 1) == 19.5


def test_pitcher_rate_derivation_math():
    ip, k, bb, h, hr = 186.2, 281, 58, 142, 22
    k9 = 9 * k / ip
    bb9 = 9 * bb / ip
    fip = (13 * hr + 3 * bb - 2 * k) / ip + 3.10
    tbf = 3 * ip + h + bb
    kpct = 100 * k / tbf
    assert round(k9, 1) == 13.6
    assert round(bb9, 1) == 2.8
    assert 2.0 < round(fip, 2) < 3.5          # Strider-like, sane FIP
    assert 33.0 < round(kpct, 1) < 40.0       # elite K% band


def test_era_and_fldpct_derivation_math():
    assert round(9 * 60 / 190.0, 2) == 2.84               # ERA = 9*ER/IP
    po, a, e = 300, 420, 8
    assert round((po + a) / (po + a + e), 3) == 0.989      # FLD% = (PO+A)/CH


# ---- Pitch arsenal ----

def test_custom_arsenal_builds_entries():
    import json
    ars = json.dumps([{"code": "FF", "velo": 97.0, "usage": 55},
                      {"code": "SL", "velo": 88.0}])          # usage omitted -> even split
    d = build_custom_data({**PITCHER_FORM, "arsenal": ars}, is_pitcher=True)
    sc = d["statcast"]
    assert sc["arsenal_estimated"] is True
    ff, sl = sc["arsenal"][0], sc["arsenal"][1]
    assert ff["code"] == "FF" and ff["name"] == "4-Seam FB" and ff["velo"] == 97.0
    assert ff["break_rating"] == 42 and sl["break_rating"] == 70   # pitch-type heuristic
    assert sl["usage"] == 50.0                                     # even split (2 pitches)


def test_arsenal_autofills_fb_velo_when_blank():
    import json
    form = {k: v for k, v in PITCHER_FORM.items() if k != "FB_velo"}
    form["arsenal"] = json.dumps([{"code": "FF", "velo": 98.5, "usage": 60}])
    d = build_custom_data(form, is_pitcher=True)
    assert d["pitching"]["FB_velo"] == 98.5


def test_route_pitcher_with_arsenal():
    import json
    client = app.test_client()
    ars = json.dumps([{"code": "FF", "velo": 96, "usage": 55}, {"code": "CH", "velo": 87, "usage": 45}])
    r = client.post("/generate_custom", data={**PITCHER_FORM, "is_pitcher": "on", "arsenal": ars})
    assert r.status_code == 200
    j = r.get_json()
    assert len(j["arsenal"]) == 2
    assert j["arsenal_estimated"] is True


def test_arsenal_spin_parsed():
    import json
    ars = json.dumps([{"code": "FF", "velo": 96, "usage": 60, "spin": 2400}])
    d = build_custom_data({**PITCHER_FORM, "arsenal": ars}, is_pitcher=True)
    assert d["statcast"]["arsenal"][0]["spin"] == 2400


# ---- Full-confidence toggle ----

SMALL_HITTER = {
    "name": "Cup", "team": "X", "year": "2026", "position": "CF",
    "PA": "50", "G": "14", "BA": "0.350", "OBP": "0.430", "SLG": "0.650",
    "ISO": "0.300", "HR": "5", "3B": "1", "SB": "3", "CS": "0",
    "BB_pct": "12", "K_pct": "10", "WAR": "2",
}
SMALL_PITCHER = {
    "name": "Cup", "team": "X", "year": "2026", "role": "SP", "throws": "R",
    "IP": "20", "G": "4", "GS": "4", "K_per_9": "14", "BB_per_9": "1.5",
    "HR_per_9": "0.4", "H_per_9": "5", "K_pct": "40", "BB_pct": "4",
    "WHIP": "0.8", "WAR": "1.5",
}


def test_full_confidence_flag_set():
    assert build_custom_data(SMALL_HITTER, False, "CF")["full_confidence"] is False
    assert build_custom_data({**SMALL_HITTER, "full_confidence": "on"}, False, "CF")["full_confidence"] is True


def test_full_confidence_hitter_trusts_elite_rates():
    reg = calculate_ratings(build_custom_data(SMALL_HITTER, False, "CF"), "CF", "season")
    fc = calculate_ratings(build_custom_data({**SMALL_HITTER, "full_confidence": "on"}, False, "CF"), "CF", "season")
    # Without FC a 50-PA line regresses toward league average; FC trusts it.
    assert fc["contact_right"] > reg["contact_right"]
    assert fc["vision"] > reg["vision"]
    assert fc["power_right"] > reg["power_right"]


def test_full_confidence_pitcher_trusts_elite_rates():
    reg = calculate_pitcher_ratings(build_custom_data(SMALL_PITCHER, True), "season")
    fc = calculate_pitcher_ratings(build_custom_data({**SMALL_PITCHER, "full_confidence": "on"}, True), "season")
    assert fc["k_per_9_right"] > reg["k_per_9_right"]
    assert fc["control"] > reg["control"]


# ---- Route tests (edge + smoke) ----

def test_route_rejects_zero_pa():
    client = app.test_client()
    r = client.post("/generate_custom", data={**HITTER_FORM, "PA": "0"})
    assert r.status_code == 400
    assert "PA" in r.get_json()["error"]


def test_route_rejects_zero_ip():
    client = app.test_client()
    r = client.post("/generate_custom", data={**PITCHER_FORM, "is_pitcher": "on", "IP": "0"})
    assert r.status_code == 400
    assert "IP" in r.get_json()["error"]


def test_route_hitter_smoke():
    client = app.test_client()
    r = client.post("/generate_custom", data=HITTER_FORM)
    assert r.status_code == 200
    j = r.get_json()
    assert j["type"] == "hitter"
    assert j["custom"] is True
    assert 0 < j["ovr"] <= 99
    assert j["name"] == "Test Masher"
    assert "ratings" in j and "overalls" in j


def test_route_pitcher_smoke():
    client = app.test_client()
    r = client.post("/generate_custom", data={**PITCHER_FORM, "is_pitcher": "on"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["type"] == "pitcher"
    assert 0 < j["ovr"] <= 99
    assert j["position"] == "SP"
