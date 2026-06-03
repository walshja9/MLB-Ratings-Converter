"""Merge-scrape team rosters into show_truth.json.

The /lists/pitchers grid only surfaces the top ~100 arms; team roster pages
(/teams/<slug>) list full rosters including the low-rated middle relievers we
need to anchor the pitcher OVR low end. This fetches every team's roster,
scrapes only players not already in the truth set, and merges them in.
"""

import json
import re
import scrape_truth as st


def main():
    data = json.load(open(st.OUTPUT_FILE, encoding="utf-8"))
    hit, pit = data["hitters"], data["pitchers"]
    existing = set(hit) | set(pit)
    print(f"existing: {len(hit)} hitters, {len(pit)} pitchers")

    lp = st.fetch_page(st.BASE_URL + "/lists/pitchers")
    teams = sorted(set(re.findall(r"(/teams/[a-z0-9-]+)", lp or "")))
    print(f"teams found: {len(teams)}")

    roster = {}
    for t in teams:
        h = st.fetch_page(st.BASE_URL + t)
        if not h:
            print(f"  WARN: no html for {t}")
            continue
        for p in st.parse_player_list(h):
            roster.setdefault(p["name"], p["slug"])
    print(f"total roster names: {len(roster)}")

    new_names = [n for n in roster if n not in existing]
    print(f"NEW players to scrape: {len(new_names)}")

    added_p = added_h = 0
    for i, name in enumerate(new_names):
        res, is_p = st.scrape_player(roster[name], name)
        if res is None:
            continue
        if is_p:
            pit[res["name"]] = res["attrs"]
            added_p += 1
        else:
            hit[res["name"]] = res["attrs"]
            added_h += 1
        if (i + 1) % 50 == 0:
            st.save_truth(hit, pit)
            print(f"  ...{i + 1}/{len(new_names)} (added {added_p}P {added_h}H)")

    st.save_truth(hit, pit)
    povr = sorted(v.get("ovr", 0) for v in pit.values() if v.get("ovr", 0) > 0)
    print(f"DONE: added {added_p} pitchers, {added_h} hitters")
    print(f"pitcher OVR now: min={min(povr)} max={max(povr)} n={len(povr)}")


if __name__ == "__main__":
    main()
