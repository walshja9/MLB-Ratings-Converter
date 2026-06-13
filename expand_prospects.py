from __future__ import annotations

import bisect
import copy
import json
import math
import os
import re
import shutil
import statistics
from datetime import date

from scrape_prospects import TEAMS, load_fg_rows, normalize_match_name, parse_fg_row


ROOT = os.path.dirname(os.path.abspath(__file__))
PROSPECT_DIR = os.path.join(ROOT, "prospect_data")
TEAMS_PATH = os.path.join(PROSPECT_DIR, "teams.json")
BACKUP_PATH = os.path.join(PROSPECT_DIR, "teams.backup.json")
AFFILIATE_ORG_MAP = os.path.join(PROSPECT_DIR, "affiliate_org_map.json")
VALUCAST_INPUTS = os.environ.get(
    "VALUCAST_INPUTS",
    "C:/Users/Alex/DDLensAdapter/data/valucast_prospect_model_inputs.json",
)
FIELDING_PATH = os.path.join(PROSPECT_DIR, "milb_fielding_2026.json")

MIN_PA = 100
MIN_IP = 30
MIN_FIELD_INN = 50

LEVEL_CAP_PRESENT = {"A": 55, "A+": 60, "AA": 68, "AAA": 75, "MLB": 80}
BASE_BUMP = {"A": 10, "A+": 8, "AA": 6, "AAA": 4, "MLB": 2}
LEVEL_FV_ADJ = {"A": -3, "A+": -1, "AA": 1, "AAA": 3, "MLB": 4}
# Percentile is computed WITHIN level, so an average A-ball tool and an average
# AAA tool both percentile ~0.5. This absolute (MLB-referenced) downshift pulls
# lower-level grades down so a median A-ball performer doesn't grade like a
# median AAA performer. Applied after the 20-80 map, before the level cap.
LEVEL_GRADE_SHIFT = {"A": -12, "A+": -8, "AA": -4, "AAA": 0, "MLB": 2}

HITTER_FUTURE_KEYS = ("hit", "power", "run", "arm", "field")
HITTER_PRESENT_KEYS = ("hit", "power", "run", "field")
PITCHER_REQUIRED_KEYS = ("fb", "control")
PITCHER_GRADE_KEYS = ("fb", "sl", "cb", "ch", "fc", "fs", "control")


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def grade(p):
    return int(round(20 + 60 * clamp(float(p), 0.0, 1.0)))


def pct(value, sorted_list, higher_is_better=True):
    values = [float(v) for v in sorted_list if _is_number(v)]
    if not values or not _is_number(value):
        return 0.5
    if len(values) == 1 or values[0] == values[-1]:
        result = 0.5
    else:
        rank = bisect.bisect_right(values, float(value)) - 1
        result = clamp(rank / (len(values) - 1), 0.0, 1.0)
    return result if higher_is_better else 1.0 - result


def _blend_toward_fv(tool_grade, fv, cap, w_tool=0.55):
    """Pull a tool grade toward the holistic FV. Preserves which tool is best
    while keeping the overall level consistent with FV."""
    return clamp(int(round(w_tool * tool_grade + (1.0 - w_tool) * fv)), 20, cap)


def age_factor(age):
    if not _is_number(age):
        return 0.0
    return clamp(((24.0 - float(age)) / 6.0) * 1.3, 0.0, 1.3)


def _hitter_stat_percentiles(player, level_pools):
    level = str(player.get("level") or "").strip()
    pool = _level_pool(level_pools, "hitters", level)
    pa = _num(player, "plate_appearances", "pa")
    iso = _num(player, "iso")
    avg = _num(player, "avg")
    k_pct = _num(player, "k_pct")
    bb_pct = _num(player, "bb_pct")
    sb = int(round(_num(player, "stolen_bases", "sb")))
    sb_rate = sb / max(pa / 600.0, 0.1)
    contact_pct = (
        0.5 * pct(avg, pool.get("avg", []), True)
        + 0.5 * pct(k_pct, pool.get("k_pct", []), False)
    )
    power_pct = pct(iso, pool.get("iso", []), True)
    eye_pct = pct(bb_pct, pool.get("bb_pct", []), True)
    speed_pct = pct(sb_rate, pool.get("sb_rate", []), True)
    if sb == 0:
        speed_pct = 0.30
    return contact_pct, power_pct, eye_pct, speed_pct


def stat_hitting_present(stat, level_pools):
    level = str(stat.get("level") or "").strip()
    cap = LEVEL_CAP_PRESENT.get(level, 60)
    shift = LEVEL_GRADE_SHIFT.get(level, 0)
    contact_pct, power_pct, eye_pct, speed_pct = _hitter_stat_percentiles(
        stat, level_pools
    )
    return {
        "hit": clamp(grade(contact_pct) + shift, 20, cap),
        "power": clamp(grade(power_pct) + shift, 20, cap),
        "eye": clamp(grade(eye_pct) + shift, 20, cap),
        "run": clamp(grade(speed_pct) + shift, 20, cap),
    }


def emit_stat_hitter(player, level_pools):
    level = str(player.get("level") or "").strip()
    pa = _num(player, "plate_appearances", "pa")
    avg = _num(player, "avg")
    obp = _num(player, "obp")
    slg = _num(player, "slg")
    ops = _num(player, "ops")
    iso = _num(player, "iso")
    k_pct = _num(player, "k_pct")
    bb_pct = _num(player, "bb_pct")
    hr = int(round(_num(player, "home_runs", "hr")))
    sb = int(round(_num(player, "stolen_bases", "sb")))
    cap = LEVEL_CAP_PRESENT.get(level, 60)
    raw = stat_hitting_present(player, level_pools)
    contact_pct, power_pct, eye_pct, _ = _hitter_stat_percentiles(player, level_pools)
    age_fv_adj = _age_fv_adjustment(player.get("age"))
    composite = _mean(contact_pct, power_pct, eye_pct)
    fv = clamp(
        round(28 + 20 * composite + LEVEL_FV_ADJ.get(level, 0) + age_fv_adj),
        25,
        55,
    )
    # Anchor each tool toward the holistic FV so a one-dimensional stat line
    # (big power, zero walks) cannot produce an elite OVR while FV says org
    # depth. Keeps tool SHAPE (best tool stays best); ties tool LEVEL to FV.
    present_core = {k: _blend_toward_fv(v, fv, cap) for k, v in raw.items()}
    dev_bump = max(0, round(BASE_BUMP.get(level, 4) * age_factor(player.get("age"))))
    cap_future = min(cap + 8, 80)
    future_core = {
        k: clamp(v + dev_bump, 20, cap_future)
        for k, v in present_core.items()
    }

    grades = {
        "hit": future_core["hit"],
        "power": future_core["power"],
        "eye": future_core["eye"],
        "run": future_core["run"],
        "arm": 50,
        "field": 50,
        "overall": fv,
    }
    grades_present = {
        "hit": present_core["hit"],
        "power": present_core["power"],
        "eye": present_core["eye"],
        "run": present_core["run"],
        "field": 50,
    }
    stat_line = {
        "avg": avg,
        "obp": obp,
        "slg": slg,
        "ops": ops,
        "iso": iso,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "pa": int(round(pa)),
        "hr": hr,
        "sb": sb,
    }

    return {
        "id": "stat_" + str(player.get("mlbam_id")),
        "rank": None,
        "name": str(player.get("name") or "").strip(),
        "pos": str(player.get("position") or "").strip() or None,
        "age": player.get("age"),
        "bats": _clean_side(player.get("bats")),
        "throws": _clean_side(player.get("throws")),
        "height": None,
        "weight": None,
        "eta": None,
        "level": level or None,
        "is_pitcher": False,
        "grades": grades,
        "grades_present": grades_present,
        "fv": fv,
        "fv_source": "stat-derived",
        "grades_incomplete": True,
        "source": "stat",
        "stat_line": stat_line,
    }


def _pitcher_stat_percentiles(player, level_pools):
    level = str(player.get("level") or "").strip()
    pool = _level_pool(level_pools, "pitchers", level)
    era = _num(player, "era")
    whip = _num(player, "whip")
    k_per_9 = _num(player, "k_per_9")
    bb_per_9 = _num(player, "bb_per_9")
    k_pct_pct = pct(k_per_9, pool.get("k_per_9", []), True)
    ctrl_pct = (
        0.5 * pct(bb_per_9, pool.get("bb_per_9", []), False)
        + 0.5 * pct(whip, pool.get("whip", []), False)
    )
    era_pct = pct(era, pool.get("era", []), False)
    return k_pct_pct, ctrl_pct, era_pct


def stat_pitching_present(stat, level_pools):
    level = str(stat.get("level") or "").strip()
    cap = LEVEL_CAP_PRESENT.get(level, 60)
    shift = LEVEL_GRADE_SHIFT.get(level, 0)
    k_pct_pct, ctrl_pct, _ = _pitcher_stat_percentiles(stat, level_pools)
    return {
        "fb": clamp(grade(k_pct_pct) + shift, 20, cap),
        "control": clamp(grade(ctrl_pct) + shift, 20, cap),
    }


def emit_stat_pitcher(player, level_pools):
    level = str(player.get("level") or "").strip()
    ip = _num(player, "innings_pitched", "ip")
    era = _num(player, "era")
    whip = _num(player, "whip")
    k_per_9 = _num(player, "k_per_9")
    bb_per_9 = _num(player, "bb_per_9")
    k_bb_pct = _num(player, "k_bb_pct")

    cap = LEVEL_CAP_PRESENT.get(level, 60)
    raw = stat_pitching_present(player, level_pools)
    k_pct_pct, ctrl_pct, era_pct = _pitcher_stat_percentiles(player, level_pools)
    composite = _mean(k_pct_pct, ctrl_pct, era_pct)
    fv = clamp(
        round(
            28
            + 20 * composite
            + LEVEL_FV_ADJ.get(level, 0)
            + _age_fv_adjustment(player.get("age"))
        ),
        25,
        55,
    )
    present = {k: _blend_toward_fv(v, fv, cap) for k, v in raw.items()}
    dev_bump = max(0, round(BASE_BUMP.get(level, 4) * age_factor(player.get("age"))))
    cap_future = min(cap + 8, 80)
    future = {
        k: clamp(v + dev_bump, 20, cap_future)
        for k, v in present.items()
    }
    future["overall"] = fv

    throws = _clean_side(player.get("throws")) or "R"
    role = "SP" if bool(player.get("is_starter")) else "RP"
    stat_line = {
        "era": era,
        "whip": whip,
        "k_per_9": k_per_9,
        "bb_per_9": bb_per_9,
        "ip": ip,
        "k_bb_pct": k_bb_pct,
    }

    return {
        "id": "stat_" + str(player.get("mlbam_id")),
        "rank": None,
        "name": str(player.get("name") or "").strip(),
        "pos": "LHP" if throws == "L" else "RHP",
        "age": player.get("age"),
        "bats": _clean_side(player.get("bats")),
        "throws": throws,
        "height": None,
        "weight": None,
        "eta": None,
        "level": level or None,
        "is_pitcher": True,
        "role": role,
        "grades": future,
        "grades_present": present,
        "fv": fv,
        "fv_source": "stat-derived",
        "grades_incomplete": True,
        "source": "stat",
        "stat_line": stat_line,
    }


def build_level_pools(hitters, pitchers):
    pools = {"hitters": {}, "pitchers": {}}
    for player in hitters:
        level = str(player.get("level") or "").strip()
        if not level:
            continue
        pool = pools["hitters"].setdefault(
            level,
            {"avg": [], "k_pct": [], "iso": [], "bb_pct": [], "sb_rate": []},
        )
        pa = _num(player, "plate_appearances", "pa")
        sb = _num(player, "stolen_bases", "sb")
        pool["avg"].append(_num(player, "avg"))
        pool["k_pct"].append(_num(player, "k_pct"))
        pool["iso"].append(_num(player, "iso"))
        pool["bb_pct"].append(_num(player, "bb_pct"))
        pool["sb_rate"].append(sb / max(pa / 600.0, 0.1))

    for player in pitchers:
        level = str(player.get("level") or "").strip()
        if not level:
            continue
        pool = pools["pitchers"].setdefault(
            level,
            {"k_per_9": [], "bb_per_9": [], "whip": [], "era": []},
        )
        pool["k_per_9"].append(_num(player, "k_per_9"))
        pool["bb_per_9"].append(_num(player, "bb_per_9"))
        pool["whip"].append(_num(player, "whip"))
        pool["era"].append(_num(player, "era"))

    for kind in pools.values():
        for pool in kind.values():
            for key, values in pool.items():
                pool[key] = sorted(v for v in values if _is_number(v))
    return pools


def build_valucast_indexes(valucast_doc):
    current = valucast_doc.get("current", {}) if isinstance(valucast_doc, dict) else {}
    indexes = {
        "hitters_by_name": {},
        "pitchers_by_name": {},
        "hitters_by_mlbam": {},
        "pitchers_by_mlbam": {},
    }
    name_index = {"hitters": {}, "pitchers": {}, "all": {}}

    for player in current.get("hitters", []) or []:
        _index_valucast_player(
            player,
            indexes["hitters_by_name"],
            indexes["hitters_by_mlbam"],
            name_index["hitters"],
            name_index["all"],
        )
    for player in current.get("pitchers", []) or []:
        _index_valucast_player(
            player,
            indexes["pitchers_by_name"],
            indexes["pitchers_by_mlbam"],
            name_index["pitchers"],
            name_index["all"],
        )
    return indexes, name_index


def prospect_mlbam(prospect, name_index):
    mlbam = _mlbam_key(prospect.get("id"))
    if mlbam:
        return mlbam
    key = normalize_match_name(prospect.get("name"))
    if not key or not isinstance(name_index, dict):
        return None
    kind = "pitchers" if prospect.get("is_pitcher") else "hitters"
    return (
        name_index.get(kind, {}).get(key)
        or name_index.get("all", {}).get(key)
    )


def load_fielding(path=FIELDING_PATH):
    doc = _load_json_optional(path, {})
    players = doc.get("players", {}) if isinstance(doc, dict) else {}
    if not isinstance(players, dict):
        return {}
    return {str(k): v for k, v in players.items() if isinstance(v, list)}


def build_fielding_distributions(fielding):
    distributions = {}
    for stints in _fielding_players(fielding).values():
        if not isinstance(stints, list):
            continue
        for stint in stints:
            if not isinstance(stint, dict):
                continue
            inn = _num(stint, "inn")
            if inn < MIN_FIELD_INN:
                continue
            pos_group = _pos_group(stint.get("pos"))
            level = str(stint.get("level") or "").strip()
            if not pos_group or not level:
                continue
            bucket = distributions.setdefault(
                (pos_group, level),
                {"fld": [], "rf9": [], "arate": [], "erate": []},
            )
            chances = _num(stint, "chances")
            bucket["fld"].append(_num(stint, "fld"))
            bucket["rf9"].append(_num(stint, "rf9"))
            bucket["arate"].append(_num(stint, "A") * 9.0 / max(inn, 1.0))
            bucket["erate"].append(_num(stint, "E") / chances if chances else 0.0)

    for bucket in distributions.values():
        for key, values in bucket.items():
            bucket[key] = sorted(v for v in values if _is_number(v))
    return distributions


def fielding_stat_grades(stint, distributions):
    pos_group = _pos_group(stint.get("pos"))
    level = str(stint.get("level") or "").strip()
    if not pos_group or not level:
        return None, None
    dist = _fielding_distribution(distributions, pos_group, level)
    if not dist:
        return None, None

    cap = LEVEL_CAP_PRESENT.get(level, 60)
    shift = LEVEL_GRADE_SHIFT.get(level, 0)
    reliability_pct = pct(_num(stint, "fld"), dist.get("fld", []), True)
    range_pct = pct(_num(stint, "rf9"), dist.get("rf9", []), True)
    field_stat = clamp(grade(0.6 * reliability_pct + 0.4 * range_pct) + shift, 20, cap)

    arm_stat = None
    if pos_group != "1B":
        inn = _num(stint, "inn")
        chances = _num(stint, "chances")
        arate = _num(stint, "A") * 9.0 / max(inn, 1.0)
        erate = _num(stint, "E") / chances if chances else 0.0
        arm_pct = pct(arate, dist.get("arate", []), True)
        acc_pct = pct(erate, dist.get("erate", []), False)
        arm_stat = clamp(grade(0.6 * arm_pct + 0.4 * acc_pct) + shift, 20, cap)
    return field_stat, arm_stat


def apply_stat_blend(merged_teams, level_pools, valucast, fielding, name_index):
    if isinstance(valucast, dict) and "current" in valucast:
        valucast, built_name_index = build_valucast_indexes(valucast)
        if not name_index:
            name_index = built_name_index

    _apply_grade_stat_blend(merged_teams, level_pools, valucast or {}, name_index or {})
    _apply_fielding_stat_blend(merged_teams, fielding or {}, name_index or {})


def load_base_document():
    if os.path.exists(BACKUP_PATH):
        with open(BACKUP_PATH, "r", encoding="utf-8") as f:
            return json.load(f), False
    with open(TEAMS_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
    shutil.copyfile(TEAMS_PATH, BACKUP_PATH)
    return doc, True


def main():
    base_doc, backup_created = load_base_document()
    base_teams = base_doc.get("teams", {})
    present_by_org = _present_by_org(base_teams)

    fg_by_org = {abbr: [] for abbr in TEAMS}
    stat_by_org = {abbr: [] for abbr in TEAMS}
    counts = {
        "fg_extra_added": 0,
        "stat_added": 0,
        "unmapped_skipped": 0,
        "dedup_skipped": 0,
    }

    for raw_row in load_fg_rows():
        row = parse_fg_row(raw_row)
        if not row or not row.get("org") or row.get("org") not in TEAMS:
            continue
        org = row["org"]
        name_key = normalize_match_name(row.get("name"))
        if name_key in present_by_org[org]:
            counts["dedup_skipped"] += 1
            continue
        if row.get("fv") is None:
            continue
        prospect = emit_fg_extra(raw_row, row)
        fg_by_org[org].append(prospect)
        present_by_org[org].add(name_key)
        counts["fg_extra_added"] += 1

    affiliate_map = _load_affiliate_map()
    if not os.path.exists(VALUCAST_INPUTS):
        import sys
        print(
            f"WARNING: ValuCast inputs not found at {VALUCAST_INPUTS}; "
            f"stat-derived prospects will be empty. "
            f"Set the VALUCAST_INPUTS env var to override.",
            file=sys.stderr,
        )
    valucast_doc = _load_json_optional(VALUCAST_INPUTS, {})
    valucast, name_index = build_valucast_indexes(valucast_doc)
    current = valucast_doc.get("current", {}) if isinstance(valucast_doc, dict) else {}
    qualified_hitters = [
        p for p in current.get("hitters", [])
        if _num(p, "plate_appearances", "pa") >= MIN_PA
    ]
    qualified_pitchers = [
        p for p in current.get("pitchers", [])
        if _num(p, "innings_pitched", "ip") >= MIN_IP
    ]
    level_pools = build_level_pools(qualified_hitters, qualified_pitchers)

    for player in qualified_hitters:
        org = affiliate_map.get(str(player.get("team") or "").strip())
        if org not in TEAMS:
            counts["unmapped_skipped"] += 1
            continue
        name_key = normalize_match_name(player.get("name"))
        if name_key in present_by_org[org]:
            counts["dedup_skipped"] += 1
            continue
        prospect = emit_stat_hitter(player, level_pools)
        stat_by_org[org].append(prospect)
        present_by_org[org].add(name_key)
        counts["stat_added"] += 1

    for player in qualified_pitchers:
        org = affiliate_map.get(str(player.get("team") or "").strip())
        if org not in TEAMS:
            counts["unmapped_skipped"] += 1
            continue
        name_key = normalize_match_name(player.get("name"))
        if name_key in present_by_org[org]:
            counts["dedup_skipped"] += 1
            continue
        prospect = emit_stat_pitcher(player, level_pools)
        stat_by_org[org].append(prospect)
        present_by_org[org].add(name_key)
        counts["stat_added"] += 1

    merged_teams = {}
    for abbr, (_, display_name) in TEAMS.items():
        team = copy.deepcopy(base_teams.get(abbr, {"name": display_name, "prospects": []}))
        existing = team.get("prospects", [])
        max_rank = max([_int_or_zero(p.get("rank")) for p in existing] or [0])
        fg_extra = sorted(
            fg_by_org[abbr],
            key=lambda p: (-_int_or_zero(p.get("fv")), str(p.get("name") or "")),
        )
        stat_extra = sorted(
            stat_by_org[abbr],
            key=lambda p: (
                -_int_or_zero(p.get("fv")),
                -_stat_composite(p),
                str(p.get("name") or ""),
            ),
        )
        rank = max_rank + 1
        for prospect in fg_extra + stat_extra:
            prospect["rank"] = rank
            rank += 1
        merged_teams[abbr] = {
            "name": team.get("name") or display_name,
            "prospects": existing + fg_extra + stat_extra,
        }

    fielding = load_fielding()
    apply_stat_blend(merged_teams, level_pools, valucast, fielding, name_index)

    out = {"season": 2026, "scraped": date.today().isoformat(), "teams": merged_teams}
    with open(TEAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    if backup_created:
        backup_note = "created"
    else:
        backup_note = "existing"
    _print_summary(base_teams, merged_teams, counts, backup_note)


def emit_fg_extra(raw_row, row):
    is_pitcher = bool(row.get("is_pitcher"))
    name = str(row.get("name") or "").strip()
    fv = int(row["fv"])
    future_in = row.get("future") or {}
    present_in = row.get("present") or {}
    grades_incomplete = False

    if is_pitcher:
        grades = {}
        for key in PITCHER_GRADE_KEYS:
            if key in future_in and future_in[key] is not None:
                grades[key] = int(future_in[key])
            elif key in PITCHER_REQUIRED_KEYS:
                grades[key] = 50
                grades_incomplete = True
        grades["overall"] = fv
        for key in PITCHER_REQUIRED_KEYS:
            if key not in future_in:
                grades_incomplete = True
        grades_present = {
            key: int(present_in[key])
            for key in present_in
            if key in PITCHER_GRADE_KEYS and present_in[key] is not None
        }
    else:
        grades = {}
        for key in HITTER_FUTURE_KEYS:
            if key in future_in and future_in[key] is not None:
                grades[key] = int(future_in[key])
            else:
                grades[key] = 50
                grades_incomplete = True
        grades["overall"] = fv
        grades_present = {
            key: int(present_in[key])
            for key in HITTER_PRESENT_KEYS
            if key in present_in and present_in[key] is not None
        }

    bats = _clean_side(_raw_get(raw_row, "Bats"))
    throws = _clean_side(_raw_get(raw_row, "Throws"))
    raw_pos = str(
        _raw_get(raw_row, "Position", "positionDB", "Pos", "pos") or ""
    ).strip().upper()
    if is_pitcher:
        role = row.get("role") or ("RP" if raw_pos in {"RP", "SIRP", "MIRP"} else "SP")
        pos = raw_pos if raw_pos in {"LHP", "RHP"} else ("LHP" if throws == "L" else "RHP")
    else:
        role = None
        pos = raw_pos or None

    prospect = {
        "id": "fg_" + re.sub(r"\s+", "_", normalize_match_name(name)),
        "rank": None,
        "name": name,
        "pos": pos,
        "age": row.get("age"),
        "bats": bats,
        "throws": throws,
        "height": _height_value(raw_row),
        "weight": _int_or_none(_raw_get(raw_row, "cWeight", "Weight")),
        "eta": _int_or_none(_raw_get(raw_row, "cETA", "ETA_Current")),
        "level": row.get("level"),
        "is_pitcher": is_pitcher,
        "grades": grades,
        "grades_present": grades_present,
        "fv": fv,
        "fv_source": "fangraphs",
        "grades_incomplete": grades_incomplete,
        "source": "fg-extra",
    }
    if is_pitcher:
        prospect["role"] = role if role in {"SP", "RP"} else "SP"
    return prospect


def _index_valucast_player(player, by_name, by_mlbam, name_index, all_name_index):
    mlbam = _mlbam_key(player.get("mlbam_id"))
    if mlbam:
        by_mlbam[mlbam] = player
    for key in _valucast_name_keys(player):
        by_name.setdefault(key, player)
        if mlbam:
            name_index.setdefault(key, mlbam)
            all_name_index.setdefault(key, mlbam)


def _valucast_name_keys(player):
    keys = []
    for value in (player.get("normalized_name"), player.get("name")):
        key = normalize_match_name(value)
        if key and key not in keys:
            keys.append(key)
    return keys


def _mlbam_key(value):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.startswith("stat_"):
        text = text[5:]
    if text.isdigit():
        return text
    if _is_number(text):
        return str(int(round(float(text))))
    return None


def _iter_prospects(teams):
    for team in teams.values():
        for prospect in team.get("prospects", []):
            yield prospect


def _is_grade_blend_source(prospect):
    return prospect.get("source") in (None, "fg-extra")


def _apply_grade_stat_blend(merged_teams, level_pools, valucast, name_index):
    for prospect in _iter_prospects(merged_teams):
        if not _is_grade_blend_source(prospect):
            continue
        stat = _resolve_valucast_stat(prospect, valucast, name_index)
        if not stat:
            continue

        grades = prospect.setdefault("grades", {})
        grades_present = prospect.setdefault("grades_present", {})
        if prospect.get("is_pitcher"):
            if _num(stat, "innings_pitched", "ip") < MIN_IP:
                continue
            stat_present = stat_pitching_present(stat, level_pools)
            for key in ("fb", "control"):
                base = grades_present.get(key, grades.get(key, 50))
                grades_present[key] = clamp(
                    round(0.5 * base + 0.5 * stat_present[key]), 20, 80
                )
            prospect["stat_blended"] = True
        else:
            if _num(stat, "plate_appearances", "pa") < MIN_PA:
                continue
            stat_present = stat_hitting_present(stat, level_pools)
            for key in ("hit", "power", "eye", "run"):
                base = grades_present.get(key, grades.get(key, 50))
                grades_present[key] = clamp(
                    round(0.5 * base + 0.5 * stat_present[key]), 20, 80
                )
            grades.setdefault("eye", grades_present["eye"])
            prospect["stat_blended"] = True


def _resolve_valucast_stat(prospect, valucast, name_index):
    if prospect.get("is_pitcher"):
        by_mlbam = valucast.get("pitchers_by_mlbam", {})
        by_name = valucast.get("pitchers_by_name", {})
    else:
        by_mlbam = valucast.get("hitters_by_mlbam", {})
        by_name = valucast.get("hitters_by_name", {})

    mlbam = prospect_mlbam(prospect, name_index)
    if mlbam and mlbam in by_mlbam:
        return by_mlbam[mlbam]
    return by_name.get(normalize_match_name(prospect.get("name")))


def _apply_fielding_stat_blend(merged_teams, fielding, name_index):
    players = _fielding_players(fielding)
    if not players:
        return
    distributions = build_fielding_distributions(players)
    if not distributions:
        return

    for prospect in _iter_prospects(merged_teams):
        if prospect.get("is_pitcher"):
            continue
        mlbam = prospect_mlbam(prospect, name_index)
        if not mlbam:
            continue
        primary = _primary_fielding_stint(players.get(mlbam, []))
        if not primary or _num(primary, "inn") < MIN_FIELD_INN:
            continue
        field_stat, arm_stat = fielding_stat_grades(primary, distributions)
        if field_stat is None:
            continue

        grades = prospect.setdefault("grades", {})
        grades_present = prospect.setdefault("grades_present", {})
        if prospect.get("source") == "stat":
            grades_present["field"] = field_stat
            grades["field"] = field_stat
            if arm_stat is not None:
                grades_present["arm"] = arm_stat
                grades["arm"] = arm_stat
        else:
            for key, stat_value in (("field", field_stat), ("arm", arm_stat)):
                if stat_value is None:
                    continue
                present_base = grades_present.get(key, grades.get(key, 50))
                grades_present[key] = clamp(
                    round(0.5 * present_base + 0.5 * stat_value), 20, 80
                )
                grades[key] = clamp(
                    round(0.5 * grades.get(key, 50) + 0.5 * stat_value), 20, 80
                )
        prospect["fielding_stat"] = True
        prospect["fielding_line"] = _fielding_line(primary)


def _fielding_players(fielding):
    if not isinstance(fielding, dict):
        return {}
    if isinstance(fielding.get("players"), dict):
        fielding = fielding["players"]
    return {str(k): v for k, v in fielding.items() if isinstance(v, list)}


def _primary_fielding_stint(stints):
    eligible = [
        stint for stint in stints
        if isinstance(stint, dict) and _pos_group(stint.get("pos"))
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda stint: _num(stint, "inn"))


def _pos_group(pos):
    pos = str(pos or "").strip().upper()
    if pos in {"C", "1B", "2B", "3B", "SS"}:
        return pos
    if pos in {"LF", "CF", "RF", "OF"}:
        return "OF"
    return None


def _fielding_distribution(distributions, pos_group, level):
    exact = distributions.get((pos_group, level))
    if exact and any(exact.get(key) for key in ("fld", "rf9", "arate", "erate")):
        return exact

    combined = {"fld": [], "rf9": [], "arate": [], "erate": []}
    for (group, _level), bucket in distributions.items():
        if group != pos_group:
            continue
        for key in combined:
            combined[key].extend(bucket.get(key, []))
    for key, values in combined.items():
        combined[key] = sorted(v for v in values if _is_number(v))
    if any(combined.values()):
        return combined
    return None


def _fielding_line(stint):
    return {
        "pos": str(stint.get("pos") or "").strip().upper(),
        "level": str(stint.get("level") or "").strip(),
        "inn": _num(stint, "inn"),
        "PO": int(round(_num(stint, "PO"))),
        "A": int(round(_num(stint, "A"))),
        "E": int(round(_num(stint, "E"))),
        "fld": _num(stint, "fld"),
        "rf9": _num(stint, "rf9"),
    }


def _print_summary(base_teams, merged_teams, counts, backup_note):
    graded_kept = sum(len(t.get("prospects", [])) for t in base_teams.values())
    totals = [len(t.get("prospects", [])) for t in merged_teams.values()]
    new_total = sum(totals)
    median_total = statistics.median(totals) if totals else 0
    print("summary")
    print(f"graded_kept: {graded_kept}")
    print(f"fg_extra_added: {counts['fg_extra_added']}")
    print(f"stat_added: {counts['stat_added']}")
    print(f"unmapped_skipped: {counts['unmapped_skipped']}")
    print(f"dedup_skipped: {counts['dedup_skipped']}")
    print(f"new_total: {new_total}")
    print(f"per-org min/median/max: {min(totals)}/{median_total}/{max(totals)}")
    print(f"backup: {BACKUP_PATH} ({backup_note})")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_json_optional(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        return _load_json(path)
    except OSError:
        return default


def _load_affiliate_map():
    doc = _load_json(AFFILIATE_ORG_MAP)
    return doc.get("affiliates", {})


def _present_by_org(teams):
    present = {abbr: set() for abbr in TEAMS}
    for abbr, team in teams.items():
        if abbr not in present:
            continue
        for prospect in team.get("prospects", []):
            key = normalize_match_name(prospect.get("name"))
            if key:
                present[abbr].add(key)
    return present


def _level_pool(level_pools, kind, level):
    if kind in level_pools:
        return level_pools.get(kind, {}).get(level, {})
    return level_pools.get(level, {})


def _mean(*values):
    nums = [float(v) for v in values if _is_number(v)]
    if not nums:
        return 0.5
    return sum(nums) / len(nums)


def _age_fv_adjustment(age):
    # Minor leaguers who are old for their level are org depth, not prospects,
    # regardless of stat line. Ramp the penalty hard after ~23 so a 30-year-old
    # AAA masher does not anchor to a high FV.
    if not _is_number(age):
        return 0
    age = float(age)
    if age <= 19:
        return 3
    if age <= 20:
        return 1
    if age <= 21:
        return 0
    if age <= 22:
        return -2
    if age <= 23:
        return -4
    if age <= 24:
        return -6
    if age <= 25:
        return -8
    if age <= 26:
        return -10
    if age <= 27:
        return -12
    return -15


def _stat_composite(prospect):
    present = prospect.get("grades_present") or {}
    if prospect.get("is_pitcher"):
        values = [present.get("fb"), present.get("control")]
    else:
        values = [present.get("hit"), present.get("power"), present.get("run")]
    return _mean(*values)


def _num(mapping, *keys, default=0.0):
    for key in keys:
        value = mapping.get(key)
        if _is_number(value):
            return float(value)
    return float(default)


def _is_number(value):
    if value is None or value == "":
        return False
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x)


def _int_or_zero(value):
    if not _is_number(value):
        return 0
    return int(round(float(value)))


def _int_or_none(value):
    if not _is_number(value):
        return None
    return int(round(float(value)))


def _clean_side(value):
    if value is None:
        return None
    value = str(value).strip().upper()
    return value if value in {"L", "R", "S"} else None


def _raw_get(row, *names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = lower.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _height_value(row):
    text = _raw_get(row, "cHeight")
    if text:
        return str(text)
    inches = _raw_get(row, "Height")
    if not _is_number(inches):
        return None
    inches = int(round(float(inches)))
    return f"{inches // 12}' {inches % 12}\""


if __name__ == "__main__":
    main()
