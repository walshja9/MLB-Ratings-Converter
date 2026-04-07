"""
MLB The Show 26 - Reverse Engineer Player Ratings
Goal: Decode how individual attribute ratings roll up into overall/category ratings.
"""

# --- Data Structures ---

players = {}

# ============================================================
# POSITION PLAYERS
# ============================================================

players["Pete Crow-Armstrong"] = {
    "meta": {
        "team": "Chicago Cubs",
        "position": "CF",
        "bats": "Left",
        "throws": "Left",
        "height": "6'0\"",
        "weight": 184,
        "birthdate": "2002-03-25",
        "age": 23,
        "nationality": "USA",
        "birthplace": "Sherman Oaks, CA, USA",
        "jersey": 4,
        "draft_year": 2020,
        "nickname": "PCA",
        "potential": "A",
    },
    "overall": 87,
    "total_attributes": 1556,
    "fielding_overall": 99,
    "fielding": {
        "fielding": 99,
        "arm_strength": 97,
        "arm_accuracy": 90,
        "reaction_left": 99,
        "reaction_right": 92,
        "reaction_forward": 71,
        "reaction_back": 61,
    },
    "hitting_overall": 65,
    "hitting": {
        "contact_right": 73,
        "contact_left": 45,
        "power_right": 78,
        "power_left": 60,
        "vision": 59,
        "plate_discipline": 39,
        "batting_clutch": 69,
        "bunting": 82,
        "drag_bunt": 80,
    },
    "durability": 92,
    "baserunning_overall": 87,
    "baserunning": {
        "speed": 93,
        "stealing": 83,
        "baserunning_aggressiveness": 84,
    },
}

players["Yordan Alvarez"] = {
    "meta": {
        "team": "Houston Astros",
        "position": "LF",  # primary position - confirm with Alex
        "bats": "Left",
        "throws": "Right",
        "height": "6'4\"",
        "weight": 237,
        "birthdate": "1997-06-27",
        "age": 28,
        "nationality": "Cuba",
        "birthplace": "Las Tunas, Cuba",
        "jersey": 44,
        "draft_year": None,
        "nickname": "Yordan",
        "potential": "A",
    },
    "overall": 91,
    "total_attributes": 1220,
    "fielding_overall": 54,
    "fielding": {
        "fielding": 50,
        "arm_strength": 51,
        "arm_accuracy": 73,
        "reaction_left": 44,
        "reaction_right": 55,
        "reaction_forward": 49,
        "reaction_back": 55,
    },
    "hitting_overall": 76,
    "hitting": {
        "contact_right": 80,
        "contact_left": 99,
        "power_right": 93,
        "power_left": 80,
        "vision": 80,
        "plate_discipline": 86,
        "batting_clutch": 99,
        "bunting": 35,
        "drag_bunt": 30,
    },
    "durability": 80,
    "baserunning_overall": 24,
    "baserunning": {
        "speed": 37,
        "stealing": 18,
        "baserunning_aggressiveness": 16,
    },
}

players["Bobby Witt Jr."] = {
    "meta": {
        "team": "Kansas City Royals",
        "position": "SS",
        "bats": "Right",
        "throws": "Right",
        "height": "6'1\"",
        "weight": 200,
        "birthdate": "2000-06-14",
        "age": 25,
        "nationality": "USA",
        "birthplace": "Colleyville, TX, USA",
        "jersey": 7,
        "draft_year": 2019,
        "nickname": None,
        "potential": "A",
    },
    "overall": 83,
    "total_attributes": 1543,
    "fielding_overall": 83,
    "fielding": {
        "fielding": 99,
        "arm_strength": 75,
        "arm_accuracy": 82,
        "reaction_left": 53,
        "reaction_right": 99,
        "reaction_forward": 92,
        "reaction_back": 78,
    },
    "hitting_overall": 66,
    "hitting": {
        "contact_right": 88,
        "contact_left": 96,
        "power_right": 71,
        "power_left": 51,
        "vision": 78,
        "plate_discipline": 52,
        "batting_clutch": 99,
        "bunting": 35,
        "drag_bunt": 25,
    },
    "durability": 98,
    "baserunning_overall": 87,
    "baserunning": {
        "speed": 99,
        "stealing": 82,
        "baserunning_aggressiveness": 81,
    },
}

players["Juan Soto"] = {
    "meta": {
        "team": "New York Mets",
        "position": "OF",
        "bats": "Left",
        "throws": "Left",
        "height": "6'1\"",
        "weight": 224,
        "birthdate": "1998-10-25",
        "age": 27,
        "nationality": "Dominican Republic",
        "birthplace": "Santo Domingo, Dominican Republic",
        "jersey": 22,
        "draft_year": None,
        "nickname": "Soto Pacheco",
        "potential": "A",
    },
    "overall": 98,
    "total_attributes": 1431,
    "fielding_overall": 62,
    "fielding": {
        "fielding": 53,
        "arm_strength": 71,
        "arm_accuracy": 70,
        "reaction_left": 62,
        "reaction_right": 60,
        "reaction_forward": 64,
        "reaction_back": 52,
    },
    "hitting_overall": 77,
    "hitting": {
        "contact_right": 85,
        "contact_left": 75,
        "power_right": 99,
        "power_left": 88,
        "vision": 72,
        "plate_discipline": 99,
        "batting_clutch": 83,
        "bunting": 38,
        "drag_bunt": 56,
    },
    "durability": 98,
    "baserunning_overall": 65,
    "baserunning": {
        "speed": 42,
        "stealing": 77,
        "baserunning_aggressiveness": 77,
    },
}

players["Matt Shaw"] = {
    "meta": {
        "team": "Chicago Cubs",
        "position": "3B",
        "bats": "Right",
        "throws": "Right",
        "height": "5'10\"",
        "weight": 185,
        "birthdate": "2001-11-06",
        "age": 24,
        "nationality": "USA",
        "birthplace": "Springfield, MA, USA",
        "jersey": 6,
        "draft_year": 2023,
        "nickname": None,
        "potential": "B",
    },
    "overall": 74,
    "total_attributes": 1217,
    "fielding_overall": 63,
    "fielding": {
        "fielding": 62,
        "arm_strength": 55,
        "arm_accuracy": 75,
        "reaction_left": 51,
        "reaction_right": 56,
        "reaction_forward": 83,
        "reaction_back": 56,
    },
    "hitting_overall": 52,
    "hitting": {
        "contact_right": 49,
        "contact_left": 65,
        "power_right": 49,
        "power_left": 73,
        "vision": 65,
        "plate_discipline": 63,
        "batting_clutch": 25,
        "bunting": 35,
        "drag_bunt": 44,
    },
    "durability": 91,
    "baserunning_overall": 70,
    "baserunning": {
        "speed": 83,
        "stealing": 56,
        "baserunning_aggressiveness": 71,
    },
}

players["Byron Buxton"] = {
    "meta": {
        "team": "Minnesota Twins",
        "position": "CF",
        "bats": "Right",
        "throws": "Right",
        "height": "6'1\"",
        "weight": 190,
        "birthdate": "1993-12-18",
        "age": 32,
        "nationality": "USA",
        "birthplace": "Baxley, GA, USA",
        "jersey": 25,
        "draft_year": 2012,
        "nickname": "Buck",
        "potential": "A",
    },
    "overall": 95,
    "total_attributes": 1408,
    "fielding_overall": 74,
    "fielding": {
        "fielding": 83,
        "arm_strength": 78,
        "arm_accuracy": 71,
        "reaction_left": 80,
        "reaction_right": 71,
        "reaction_forward": 67,
        "reaction_back": 65,
    },
    "hitting_overall": 63,
    "hitting": {
        "contact_right": 70,
        "contact_left": 87,
        "power_right": 85,
        "power_left": 84,
        "vision": 50,
        "plate_discipline": 50,
        "batting_clutch": 78,
        "bunting": 35,
        "drag_bunt": 25,
    },
    "durability": 84,
    "baserunning_overall": 78,
    "baserunning": {
        "speed": 99,
        "stealing": 75,
        "baserunning_aggressiveness": 61,
    },
}

players["Chandler Simpson"] = {
    "meta": {
        "team": "Tampa Bay Rays",
        "position": "OF",
        "bats": "Left",
        "throws": "Right",
        "height": "5'11\"",
        "weight": 170,
        "birthdate": "2000-11-18",
        "age": 25,
        "nationality": "USA",
        "birthplace": "Atlanta, GA, USA",
        "jersey": 14,
        "draft_year": 2022,
        "nickname": None,
        "potential": "B",
    },
    "overall": 72,
    "total_attributes": 1371,
    "fielding_overall": 59,
    "fielding": {
        "fielding": 47,
        "arm_strength": 69,
        "arm_accuracy": 57,
        "reaction_left": 60,
        "reaction_right": 49,
        "reaction_forward": 54,
        "reaction_back": 76,
    },
    "hitting_overall": 63,
    "hitting": {
        "contact_right": 81,
        "contact_left": 84,
        "power_right": 25,
        "power_left": 25,
        "vision": 93,
        "plate_discipline": 37,
        "batting_clutch": 80,
        "bunting": 70,
        "drag_bunt": 70,
    },
    "durability": 87,
    "baserunning_overall": 99,
    "baserunning": {
        "speed": 99,
        "stealing": 99,
        "baserunning_aggressiveness": 99,
    },
}

players["Adley Rutschman"] = {
    "meta": {
        "team": "Baltimore Orioles",
        "position": "C",
        "bats": "Switch",
        "throws": "Right",
        "height": "6'1\"",
        "weight": 230,
        "birthdate": "1998-02-06",
        "age": 28,
        "nationality": "USA",
        "birthplace": "Portland, OR, USA",
        "jersey": 35,
        "draft_year": 2019,
        "nickname": None,
        "potential": "B",
    },
    "overall": 84,
    "total_attributes": 1059,
    "catching_overall": 70,
    "catching": {
        "blocking": 81,
        "pop_time": 58,
    },
    "fielding_overall": 33,
    "fielding": {
        "fielding": 74,
        "arm_strength": 94,
        "arm_accuracy": 64,
        "reaction_left": 0,
        "reaction_right": 0,
        "reaction_forward": 0,
        "reaction_back": 0,
    },
    "hitting_overall": 60,
    "hitting": {
        "contact_right": 60,
        "contact_left": 91,
        "power_right": 58,
        "power_left": 59,
        "vision": 81,
        "plate_discipline": 70,
        "batting_clutch": 63,
        "bunting": 35,
        "drag_bunt": 25,
    },
    "durability": 86,
    "baserunning_overall": 17,
    "baserunning": {
        "speed": 45,
        "stealing": 3,
        "baserunning_aggressiveness": 2,
    },
}

players["Xander Bogaerts"] = {
    "meta": {
        "team": "San Diego Padres",
        "position": "SS",
        "bats": "Right",
        "throws": "Right",
        "height": "6'2\"",
        "weight": 218,
        "birthdate": "1992-10-01",
        "age": 33,
        "nationality": "Aruba",
        "birthplace": "Oranjestad, Aruba",
        "jersey": 2,
        "draft_year": None,
        "nickname": "X-Man",
        "potential": "B",
    },
    "overall": 80,
    "total_attributes": 1290,
    "fielding_overall": 72,
    "fielding": {
        "fielding": 85,
        "arm_strength": 55,
        "arm_accuracy": 73,
        "reaction_left": 58,
        "reaction_right": 84,
        "reaction_forward": 81,
        "reaction_back": 70,
    },
    "hitting_overall": 56,
    "hitting": {
        "contact_right": 75,
        "contact_left": 82,
        "power_right": 53,
        "power_left": 47,
        "vision": 78,
        "plate_discipline": 58,
        "batting_clutch": 44,
        "bunting": 38,
        "drag_bunt": 25,
    },
    "durability": 87,
    "baserunning_overall": 62,
    "baserunning": {
        "speed": 59,
        "stealing": 65,
        "baserunning_aggressiveness": 63,
    },
}

players["Hyeseong Kim"] = {
    "meta": {
        "team": "Los Angeles Dodgers",
        "position": "2B",
        "bats": "Left",
        "throws": "Right",
        "height": "5'10\"",
        "weight": 175,
        "birthdate": "1999-01-27",
        "age": 27,
        "nationality": "Republic of Korea",
        "birthplace": "Goyang, Republic of Korea",
        "jersey": 6,
        "draft_year": None,
        "nickname": None,
        "potential": "B",
    },
    "overall": 74,
    "total_attributes": 1271,
    "fielding_overall": 71,
    "fielding": {
        "fielding": 79,
        "arm_strength": 64,
        "arm_accuracy": 66,
        "reaction_left": 72,
        "reaction_right": 72,
        "reaction_forward": 78,
        "reaction_back": 65,
    },
    "hitting_overall": 51,
    "hitting": {
        "contact_right": 72,
        "contact_left": 68,
        "power_right": 39,
        "power_left": 40,
        "vision": 45,
        "plate_discipline": 35,
        "batting_clutch": 76,
        "bunting": 56,
        "drag_bunt": 25,
    },
    "durability": 88,
    "baserunning_overall": 74,
    "baserunning": {
        "speed": 78,
        "stealing": 70,
        "baserunning_aggressiveness": 73,
    },
}

players["Vladimir Guerrero Jr."] = {
    "meta": {
        "team": "Toronto Blue Jays",
        "position": "1B",
        "bats": "Right",
        "throws": "Right",
        "height": "6'0\"",
        "weight": 245,
        "birthdate": "1999-03-16",
        "age": 27,
        "nationality": "Canada",
        "birthplace": "Montreal, QC, Canada",
        "jersey": 27,
        "draft_year": None,
        "nickname": "El K",
        "potential": "A",
    },
    "overall": 94,
    "total_attributes": 1274,
    "fielding_overall": 60,
    "fielding": {
        "fielding": 55,
        "arm_strength": 59,
        "arm_accuracy": 62,
        "reaction_left": 71,
        "reaction_right": 59,
        "reaction_forward": 49,
        "reaction_back": 65,
    },
    "hitting_overall": 73,
    "hitting": {
        "contact_right": 93,
        "contact_left": 99,
        "power_right": 73,
        "power_left": 73,
        "vision": 85,
        "plate_discipline": 84,
        "batting_clutch": 92,
        "bunting": 35,
        "drag_bunt": 25,
    },
    "durability": 98,
    "baserunning_overall": 29,
    "baserunning": {
        "speed": 45,
        "stealing": 16,
        "baserunning_aggressiveness": 26,
    },
}

# ============================================================
# PITCHERS
# ============================================================

players["Garrett Crochet"] = {
    "meta": {
        "team": "Boston Red Sox",
        "position": "SP",
        "bats": "Left",
        "throws": "Left",
        "height": "6'6\"",
        "weight": 245,
        "birthdate": "1999-06-21",
        "age": 26,
        "nationality": "USA",
        "birthplace": "Ocean Springs, MS, USA",
        "jersey": 35,
        "draft_year": 2020,
        "nickname": None,
        "potential": "A",
    },
    "overall": 87,
    "total_attributes": 1373,
    "pitching_overall": 87,
    "pitching": {
        "h_per_9_left": 90,
        "h_per_9_right": 74,
        "k_per_9_left": 92,
        "k_per_9_right": 99,
        "hr_per_9": 65,
        "pitching_clutch": 80,
        "control": 89,
        "velocity": 99,
        "break": 90,
        "stamina": 87,
    },
    "fielding_overall": 49,
    "fielding": {
        "fielding": 46,
        "arm_strength": 77,
        "arm_accuracy": 48,
        "reaction_left": 43,
        "reaction_right": 43,
        "reaction_forward": 43,
        "reaction_back": 43,
    },
    "hitting_overall": 5,
    "hitting": {
        "contact_right": 0,
        "contact_left": 0,
        "power_right": 0,
        "power_left": 0,
        "vision": 2,
        "plate_discipline": 0,
        "batting_clutch": 0,
        "bunting": 35,
        "drag_bunt": 8,
    },
    "durability": 67,
    "baserunning_overall": 18,
    "baserunning": {
        "speed": 38,
        "stealing": 8,
        "baserunning_aggressiveness": 7,
    },
}


# --- Analysis Functions ---

def calc_category_averages(player):
    """Calculate simple averages for each category to compare against displayed ratings."""
    results = {}
    categories = ["pitching", "fielding", "hitting", "baserunning"] if "pitching" in player else ["fielding", "hitting", "baserunning"]
    for category in categories:
        attrs = player[category]
        avg = sum(attrs.values()) / len(attrs)
        displayed = player[f"{category}_overall"]
        results[category] = {
            "simple_avg": round(avg, 2),
            "displayed": displayed,
            "delta": round(displayed - avg, 2),
            "max": max(attrs.values()),
            "min": min(attrs.values()),
            "count": len(attrs),
        }
    return results


def verify_total_attributes(player):
    """Sum all individual attributes and compare to the stated total."""
    total = 0
    categories = ["pitching", "fielding", "hitting", "baserunning"] if "pitching" in player else ["fielding", "hitting", "baserunning"]
    for category in categories:
        total += sum(player[category].values())
    total += player["durability"]
    return {
        "calculated": total,
        "stated": player["total_attributes"],
        "diff": player["total_attributes"] - total,
    }


def print_analysis(name):
    player = players[name]
    pos = player["meta"]["position"]
    print(f"\n{'='*60}")
    print(f"  {name} ({pos}) - OVR {player['overall']}")
    print(f"{'='*60}")

    # Verify total
    totals = verify_total_attributes(player)
    print(f"\nTotal Attributes: {totals['calculated']} (stated: {totals['stated']}) [diff: {totals['diff']:+d}]")

    # Category breakdowns
    avgs = calc_category_averages(player)
    print(f"\n{'Category':<15} {'Displayed':>10} {'Avg':>8} {'Delta':>8} {'Min':>6} {'Max':>6} {'#Attrs':>7}")
    print("-" * 62)
    for cat, data in avgs.items():
        print(f"{cat:<15} {data['displayed']:>10} {data['simple_avg']:>8} {data['delta']:>+8.2f} {data['min']:>6} {data['max']:>6} {data['count']:>7}")

    print(f"\n  DURABILITY: {player['durability']}")


def print_comparison_table():
    """Side-by-side comparison of all players."""
    print(f"\n{'='*70}")
    print("  COMPARISON TABLE")
    print(f"{'='*70}")

    # Header
    print(f"\n{'':30}", end="")
    for name in players:
        short = name.split()[-1][:8]
        print(f"{short:>10}", end="")
    print()
    print("-" * (30 + 10 * len(players)))

    # Overall
    print(f"{'Overall':30}", end="")
    for p in players.values():
        print(f"{p['overall']:>10}", end="")
    print()

    # Position
    print(f"{'Position':30}", end="")
    for p in players.values():
        print(f"{p['meta']['position']:>10}", end="")
    print()

    # Total attrs
    print(f"{'Total Attrs (stated)':30}", end="")
    for p in players.values():
        print(f"{p['total_attributes']:>10}", end="")
    print()

    diff_row = f"{'Total Attrs (diff)':30}"
    for p in players.values():
        t = verify_total_attributes(p)
        diff_row += f"{t['diff']:>+10d}"
    print(diff_row)

    print()

    # Category overalls
    all_cats = ["pitching_overall", "fielding_overall", "hitting_overall", "baserunning_overall", "durability"]
    labels = ["Pitching OVR", "Fielding OVR", "Hitting OVR", "Baserunning OVR", "Durability"]
    for label, cat in zip(labels, all_cats):
        print(f"{label:30}", end="")
        for p in players.values():
            val = p.get(cat, "--")
            print(f"{val:>10}" if val != "--" else f"{'--':>10}", end="")
        print()

    # Category avg vs displayed delta
    print(f"\n{'--- Avg vs Displayed Delta ---':30}")
    for cat in ["pitching", "fielding", "hitting", "baserunning"]:
        print(f"  {cat + ' delta':28}", end="")
        for p in players.values():
            if cat in p:
                attrs = p[cat]
                avg = sum(attrs.values()) / len(attrs)
                displayed = p[f"{cat}_overall"]
                delta = displayed - avg
                print(f"{delta:>+10.1f}", end="")
            else:
                print(f"{'--':>10}", end="")
        print()


if __name__ == "__main__":
    for name in players:
        print_analysis(name)
    print_comparison_table()
