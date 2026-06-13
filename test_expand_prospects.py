import pytest

from expand_prospects import (
    apply_stat_blend,
    build_fielding_distributions,
    build_level_pools,
    clamp,
    emit_stat_hitter,
    emit_stat_pitcher,
    fielding_stat_grades,
    grade,
    normalize_match_name,
    pct,
    age_factor,
    stat_hitting_present,
    stat_pitching_present,
)


def test_pct_monotonic_and_inversion():
    values = [10, 20, 30]
    assert pct(10, values, True) == pytest.approx(0.0)
    assert pct(20, values, True) == pytest.approx(0.5)
    assert pct(30, values, True) == pytest.approx(1.0)
    assert pct(10, values, False) == pytest.approx(1.0)
    assert pct(30, values, False) == pytest.approx(0.0)


def test_grade_and_clamp():
    assert grade(0.0) == 20
    assert grade(0.5) == 50
    assert grade(1.0) == 80
    assert clamp(10, 20, 80) == 20
    assert clamp(90, 20, 80) == 80
    assert clamp(55, 20, 80) == 55


def test_age_factor_caps_young_players():
    assert age_factor(18) == pytest.approx(1.3)
    assert age_factor(24) == pytest.approx(0.0)
    assert age_factor(30) == pytest.approx(0.0)


def test_emit_stat_hitter_schema_and_ranges():
    hitters = [
        _hitter("Test Hitter", 101, "AA", 20, 220, .330, .420, .550, .220, 12.0, 14.0, 12, 20),
        _hitter("Pool Two", 102, "AA", 21, 210, .280, .350, .450, .170, 22.0, 9.0, 7, 6),
        _hitter("Pool Three", 103, "AA", 22, 205, .240, .310, .370, .130, 27.0, 7.0, 3, 2),
        _hitter("Pool Four", 104, "AA", 23, 200, .210, .280, .320, .090, 34.0, 5.0, 1, 0),
    ]
    pools = build_level_pools(hitters, [])

    prospect = emit_stat_hitter(hitters[0], pools)

    expected = {
        "id",
        "rank",
        "name",
        "pos",
        "age",
        "bats",
        "throws",
        "height",
        "weight",
        "eta",
        "level",
        "is_pitcher",
        "grades",
        "grades_present",
        "fv",
        "fv_source",
        "grades_incomplete",
        "source",
        "stat_line",
    }
    assert expected <= set(prospect)
    assert prospect["id"].startswith("stat_")
    assert prospect["is_pitcher"] is False
    assert 30 <= prospect["fv"] <= 60
    assert all(20 <= value <= 80 for value in prospect["grades"].values())


def test_emit_stat_pitcher_schema_and_role():
    pitchers = [
        _pitcher("Test Pitcher", 201, "AA", 21, 45.0, 2.50, 1.05, 12.0, 2.5, 20.0, True, "L"),
        _pitcher("Pool Two", 202, "AA", 22, 40.0, 3.30, 1.20, 10.0, 3.0, 15.0, True, "R"),
        _pitcher("Pool Three", 203, "AA", 23, 38.0, 4.20, 1.35, 8.0, 4.0, 9.0, False, "R"),
        _pitcher("Pool Four", 204, "AA", 24, 35.0, 5.10, 1.50, 6.0, 5.0, 4.0, False, "L"),
    ]
    pools = build_level_pools([], pitchers)

    prospect = emit_stat_pitcher(pitchers[0], pools)

    assert prospect["id"].startswith("stat_")
    assert prospect["is_pitcher"] is True
    assert prospect["role"] == "SP"
    assert prospect["pos"] == "LHP"
    assert 30 <= prospect["fv"] <= 60
    assert all(20 <= value <= 80 for value in prospect["grades"].values())


def test_stat_present_helpers_schema_and_ranges():
    hitters = [
        _hitter("Test Hitter", 101, "AA", 20, 220, .330, .420, .550, .220, 12.0, 14.0, 12, 20),
        _hitter("Pool Two", 102, "AA", 21, 210, .280, .350, .450, .170, 22.0, 9.0, 7, 6),
        _hitter("Pool Three", 103, "AA", 22, 205, .240, .310, .370, .130, 27.0, 7.0, 3, 2),
    ]
    pitchers = [
        _pitcher("Test Pitcher", 201, "AA", 21, 45.0, 2.50, 1.05, 12.0, 2.5, 20.0, True, "L"),
        _pitcher("Pool Two", 202, "AA", 22, 40.0, 3.30, 1.20, 10.0, 3.0, 15.0, True, "R"),
        _pitcher("Pool Three", 203, "AA", 23, 38.0, 4.20, 1.35, 8.0, 4.0, 9.0, False, "R"),
    ]
    pools = build_level_pools(hitters, pitchers)

    hitting = stat_hitting_present(hitters[0], pools)
    pitching = stat_pitching_present(pitchers[0], pools)

    assert set(hitting) == {"hit", "power", "eye", "run"}
    assert set(pitching) == {"fb", "control"}
    assert all(20 <= value <= 80 for value in hitting.values())
    assert all(20 <= value <= 80 for value in pitching.values())


def test_fielding_stat_grades_rank_fielding_and_skip_1b_arm():
    high_ss = _stint("AA", "SS", 100.0, 30, 70, 0, 100, 1.000, 9.00)
    low_ss = _stint("AA", "SS", 100.0, 20, 25, 10, 55, .818, 4.05)
    one_b = _stint("AA", "1B", 100.0, 90, 5, 0, 95, 1.000, 8.55)
    distributions = build_fielding_distributions({
        "1": [high_ss],
        "2": [low_ss],
        "3": [one_b],
    })

    high_field, high_arm = fielding_stat_grades(high_ss, distributions)
    low_field, _ = fielding_stat_grades(low_ss, distributions)
    _, one_b_arm = fielding_stat_grades(one_b, distributions)

    assert high_field > low_field
    assert high_arm is not None
    assert one_b_arm is None


def test_stat_blend_averages_graded_hitter_present_tool():
    stat = {
        "name": "Blend Guy",
        "mlbam_id": 999001,
        "level": "MLB",
        "plate_appearances": 200,
        "avg": .500,
        "k_pct": 20.0,
        "iso": .100,
        "bb_pct": 8.0,
        "stolen_bases": 0,
    }
    pools = {
        "hitters": {
            "MLB": {
                "avg": [.100, .200, .300, .400, .500, .600],
                "k_pct": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
                "iso": [.050, .080, .100, .120, .150, .200],
                "bb_pct": [4.0, 6.0, 8.0, 10.0, 12.0, 14.0],
                "sb_rate": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            }
        },
        "pitchers": {},
    }
    key = normalize_match_name("Blend Guy")
    merged = {
        "TOR": {
            "prospects": [
                {
                    "id": "999001",
                    "name": "Blend Guy",
                    "is_pitcher": False,
                    "grades": {"hit": 55, "overall": 50},
                    "grades_present": {"hit": 50},
                }
            ]
        }
    }
    valucast = {
        "hitters_by_name": {key: stat},
        "pitchers_by_name": {},
        "hitters_by_mlbam": {"999001": stat},
        "pitchers_by_mlbam": {},
    }
    name_index = {"hitters": {key: "999001"}, "pitchers": {}, "all": {key: "999001"}}

    assert stat_hitting_present(stat, pools)["hit"] == 70

    apply_stat_blend(merged, pools, valucast, {}, name_index)
    prospect = merged["TOR"]["prospects"][0]

    assert prospect["grades_present"]["hit"] == 60
    assert prospect["stat_blended"] is True


def test_a_ball_present_cap_for_top_hitter():
    hitters = [
        _hitter("Elite A", 301, "A", 18, 250, .400, .500, .720, .320, 5.0, 18.0, 20, 45),
        _hitter("A Two", 302, "A", 20, 240, .260, .330, .420, .160, 24.0, 8.0, 5, 5),
        _hitter("A Three", 303, "A", 21, 230, .220, .280, .350, .090, 31.0, 5.0, 2, 1),
    ]
    pools = build_level_pools(hitters, [])

    prospect = emit_stat_hitter(hitters[0], pools)

    assert all(value <= 55 for value in prospect["grades_present"].values())


def test_normalized_dedup_check():
    present_by_org = {"NYY": {normalize_match_name("Sample Guy")}}
    candidate = normalize_match_name("Sample Guy Jr.")

    assert candidate in present_by_org["NYY"]


def _hitter(name, mlbam_id, level, age, pa, avg, obp, slg, iso, k_pct, bb_pct, hr, sb):
    return {
        "name": name,
        "mlbam_id": mlbam_id,
        "level": level,
        "age": age,
        "plate_appearances": pa,
        "avg": avg,
        "obp": obp,
        "slg": slg,
        "ops": obp + slg,
        "iso": iso,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "home_runs": hr,
        "stolen_bases": sb,
        "position": "SS",
    }


def _pitcher(
    name,
    mlbam_id,
    level,
    age,
    ip,
    era,
    whip,
    k_per_9,
    bb_per_9,
    k_bb_pct,
    is_starter,
    throws,
):
    return {
        "name": name,
        "mlbam_id": mlbam_id,
        "level": level,
        "age": age,
        "innings_pitched": ip,
        "era": era,
        "whip": whip,
        "k_per_9": k_per_9,
        "bb_per_9": bb_per_9,
        "k_bb_pct": k_bb_pct,
        "is_starter": is_starter,
        "throws": throws,
        "bats": "R",
    }


def _stint(level, pos, inn, po, assists, errors, chances, fld, rf9):
    return {
        "level": level,
        "pos": pos,
        "inn": inn,
        "PO": po,
        "A": assists,
        "E": errors,
        "chances": chances,
        "fld": fld,
        "rf9": rf9,
    }
