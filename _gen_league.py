"""Scratch: generate a 30-team x 90-man custom league through the live ratings
engine and write one transcribable roster sheet per team. Seeded = reproducible.
Run:  python _gen_league.py            (all 30)
      python _gen_league.py 1          (just team 1, for spot-checking)
Output: custom_league/Team_NN.md  + a summary to stdout.
"""
import os
import random
import sys
import statistics

from app import app

random.seed(2026)
client = app.test_client()
OUT = os.path.join(os.path.dirname(__file__), "custom_league")
os.makedirs(OUT, exist_ok=True)

# ---- name pools (combinatorial -> plenty of unique names for 2700) ----
FIRST = ("James John Mike Will Chris Tyler Jose Luis Carlos Diego Marcus Andre Devon Cole Brett "
         "Tariq Kenji Hideki Yusei Sang Min Dae Rafael Pedro Hector Ramon Eduardo Mateo Nico Gio "
         "Brock Chase Hunter Tanner Logan Cooper Mason Bryce Garrett Dalton Reid Wyatt Easton Knox "
         "Amir Omar Khalil Dominic Salvador Emilio Cruz Rico Javon Trey Quincy Darnell Malik Xavier "
         "Soren Lars Pieter Niko Dmitri Ivan Pavel Kwame Kofi Tunde Akira Ren Haruki Wei Jun Tao "
         "Bo Cade Rhett Boone Jett Ace Duke Roman Atlas Zane Finn Asher Ezra Silas Otto Cyrus").split()
LAST = ("Vance Reyes Tanaka Okafor Brennan Salas Cordero Whitfield Maddox Castellanos Nakamura Beckett "
        "Holloway Ferreira Delgado Ashby Kowalski Petrov Mbeki Dasilva Yamamoto Choi Nguyen Okonkwo "
        "Sutton Marsh Calloway Esposito Romano Bianchi Larsson Berg Haas Mueller Schmidt Novak Horvath "
        "Abara Sosa Bautista Guerra Medina Vargas Ibarra Fuentes Quintero Salinas Mercado Rios Acosta "
        "Pennington Cromwell Ashford Drummond Fairchild Lockwood Hammond Stockton Granger Hollis Pike "
        "Ozawa Sakamoto Fujimoto Watanabe Ishida Park Lim Jung Adeyemi Diallo Traore Sankara Bello "
        "Conway Doyle Flynn Mercer Boyd Reeves Tatum Hendricks Vasquez Cabrera Lugo Pena Tovar Bonilla").split()
_used = set()
def gen_name():
    while True:
        n = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if n not in _used:
            _used.add(n)
            return n

def U(a, b, nd=3):
    return round(random.uniform(a, b), nd)
def I(a, b):
    return random.randint(a, b)
def pick(seq):
    return random.choice(seq)

# ---- hitter archetypes: rate-stat ranges + power/speed per-600 + WAR band ----
# (BA, ISO, BB%, K%)  + hr/600, sb/600, war band
HIT = {
    "slugger":   dict(ba=(.230,.262), iso=(.250,.340), bb=(10,16), k=(26,36), hr=(34,48), sb=(0,5),  war=(2.0,5.5)),
    "masher":    dict(ba=(.265,.298), iso=(.200,.270), bb=(8,12),  k=(18,26), hr=(26,38), sb=(3,12), war=(2.5,5.5)),
    "five_tool": dict(ba=(.282,.312), iso=(.190,.255), bb=(9,13),  k=(15,22), hr=(22,34), sb=(15,32),war=(3.5,6.5)),
    "burner":    dict(ba=(.250,.292), iso=(.080,.140), bb=(6,10),  k=(11,18), hr=(2,10),  sb=(34,66),war=(1.5,4.0)),
    "contact":   dict(ba=(.292,.330), iso=(.110,.172), bb=(7,11),  k=(8,13),  hr=(8,18),  sb=(5,16), war=(2.0,4.5)),
    "solid":     dict(ba=(.255,.282), iso=(.140,.192), bb=(7,10),  k=(18,24), hr=(14,24), sb=(5,15), war=(1.5,3.0)),
    "average":   dict(ba=(.240,.266), iso=(.118,.170), bb=(6,9),   k=(20,27), hr=(10,20), sb=(3,12), war=(0.5,2.0)),
    "weak":      dict(ba=(.218,.246), iso=(.085,.138), bb=(5,8),   k=(23,31), hr=(5,14),  sb=(2,10), war=(-0.5,1.2)),
    "raw":       dict(ba=(.228,.276), iso=(.100,.215), bb=(6,12),  k=(19,31), hr=(6,26),  sb=(4,28), war=(0.0,2.2)),
}
# ---- pitcher archetypes: role + velo + k/9 + bb/9 + ERA + WHIP ----
PIT = {
    "ace":        dict(role="SP", velo=(94,98),  k9=(9.5,11.5), bb9=(1.8,2.8), era=(2.6,3.4), whip=(1.00,1.16), war=(3.5,6.5)),
    "power_sp":   dict(role="SP", velo=(96,99),  k9=(9.0,11.0), bb9=(2.8,3.8), era=(3.2,4.0), whip=(1.14,1.30), war=(1.5,3.5)),
    "soft_tosser":dict(role="SP", velo=(86,90),  k9=(6.0,7.6),  bb9=(1.3,2.2), era=(3.2,4.2), whip=(1.10,1.30), war=(1.5,3.5)),
    "mid_sp":     dict(role="SP", velo=(92,95),  k9=(7.5,9.0),  bb9=(2.5,3.2), era=(3.6,4.4), whip=(1.18,1.34), war=(1.0,3.0)),
    "backend_sp": dict(role="SP", velo=(90,94),  k9=(6.0,7.6),  bb9=(2.8,3.6), era=(4.3,5.3), whip=(1.30,1.48), war=(-0.3,1.5)),
    "closer":     dict(role="RP", velo=(99,103), k9=(12.0,15.0),bb9=(3.4,5.4), era=(2.2,3.4), whip=(1.00,1.24), war=(1.0,3.0)),
    "setup":      dict(role="RP", velo=(95,99),  k9=(10.0,13.0),bb9=(2.5,3.8), era=(2.8,3.8), whip=(1.05,1.28), war=(0.5,2.2)),
    "middle":     dict(role="RP", velo=(93,97),  k9=(8.0,10.5), bb9=(3.0,4.2), era=(3.8,4.8), whip=(1.25,1.45), war=(-0.3,1.2)),
    "submariner": dict(role="RP", velo=(86,90),  k9=(6.5,8.6),  bb9=(2.0,3.0), era=(3.2,4.2), whip=(1.16,1.36), war=(0.3,1.8)),
    "raw_arm":    dict(role="RP", velo=(96,101), k9=(9.0,12.0), bb9=(4.5,6.5), era=(4.0,5.6), whip=(1.34,1.60), war=(-0.5,1.5)),
}

CORNER = {"1B", "3B", "LF", "RF", "DH"}
MIDDLE = {"C", "2B", "SS", "CF"}

# Statcast sprint speed (ft/s) per archetype -> the engine's real speed formula
# (15.02*sprint + 0.10*SB/162 - 356.5). Without this it falls to the SB-attempt
# fallback, which pegs everyone at 99. ~27 ft/s = MLB average.
SPR = {"slugger": (25.0, 26.3), "masher": (26.3, 27.4), "five_tool": (28.3, 29.4),
       "burner": (29.3, 30.5), "contact": (27.0, 28.2), "solid": (26.6, 27.8),
       "average": (26.4, 27.6), "weak": (25.8, 27.2), "raw": (26.5, 29.0)}

def hitter_form(pos, level_cfg, name, team_abbr, age):
    # bias archetype by position group, then by level weight
    if pos == "C":
        base = ["contact", "solid", "average", "weak", "masher"]  # catchers: no burner/speed bats
    elif pos in CORNER:
        base = ["slugger", "masher", "solid", "average", "weak"]
    else:
        base = ["five_tool", "burner", "contact", "solid", "average"]
    extra = [x for x in level_cfg["hit_extra"]
             if not (pos == "C" and x in ("burner", "five_tool", "slugger"))]
    a = pick(base + extra)
    h = HIT[a]
    ba = U(*h["ba"]); iso = U(*h["iso"]); bb = U(*h["bb"], 1); k = U(*h["k"], 1)
    g = I(*level_cfg["g"]); pa = int(g * level_cfg["pa_per_g"])
    scale = pa / 600.0
    hr = max(0, int(round(U(*h["hr"]) * scale)))
    sb = max(0, int(round(U(*h["sb"]) * scale)))
    war = round(U(*h["war"], 1) * level_cfg["war_mult"], 1)
    slg = round(ba + iso, 3); obp = round(ba + bb / 100.0 + 0.012, 3)
    sprint = round(U(25.0, 26.6, 1) if pos == "C" else U(*SPR[a], 1), 1)
    # tie steals to wheels — a slow player can't be a basestealer
    if sprint < 26.0:
        sb = min(sb, 3)
    elif sprint < 27.0:
        sb = min(sb, 9)
    elif sprint < 28.0:
        sb = min(sb, 22)
    f = {
        "name": name, "team": team_abbr, "year": "2025", "position": pos, "level": level_cfg["label"],
        "G": g, "PA": pa, "BA": ba, "OBP": obp, "SLG": slg, "ISO": iso,
        "HR": hr, "3B": I(0, 6) if a == "burner" else I(0, 3), "SB": sb, "CS": int(round(sb * 0.26)),
        "BB_pct": bb, "K_pct": k, "WAR": war, "sprint_speed": sprint,
    }
    return {kk: str(vv) for kk, vv in f.items()}, a, age

def pitcher_form(role_slot, level_cfg, name, team_abbr, age):
    if role_slot == "SP":
        pool = ["ace", "power_sp", "soft_tosser", "mid_sp", "backend_sp"] + level_cfg["sp_extra"]
    else:
        pool = ["closer", "setup", "middle", "submariner", "raw_arm"] + level_cfg["rp_extra"]
    # closer only as the team's first RP slot handled by caller; here keep pool varied
    a = pick(pool)
    p = PIT[a]
    velo = U(*p["velo"], 1); k9 = U(*p["k9"], 1); bb9 = U(*p["bb9"], 1)
    era = U(*p["era"], 2); whip = U(*p["whip"], 3)
    war = round(U(*p["war"], 1) * level_cfg["war_mult"], 1)
    if p["role"] == "SP":
        gs = I(*level_cfg["gs"]); g = gs; ip = round(gs * U(5.2, 6.2, 2), 1)
        sv = 0; w = I(6, 16); l = I(4, 12)
    else:
        g = I(*level_cfg["g_rp"]); gs = 0; ip = round(g * U(0.9, 1.2, 2), 1)
        sv = I(20, 40) if a == "closer" else I(0, 10); w = I(1, 7); l = I(1, 6)
    h9 = max(5.0, round(whip * 9 - bb9, 1))
    fip = round(era * U(0.92, 1.08), 2)
    f = {
        "name": name, "team": team_abbr, "year": "2025", "is_pitcher": "on", "level": level_cfg["label"],
        "role": p["role"], "throws": pick(["R", "R", "R", "L"]),
        "IP": ip, "G": g, "GS": gs, "SV": sv, "W": w, "L": l,
        "ERA": era, "FIP": fip, "WHIP": whip,
        "K_per_9": k9, "BB_per_9": bb9, "HR_per_9": round(U(0.6, 1.4, 2), 2), "H_per_9": h9,
        "K_pct": round(k9 * 2.63, 1), "BB_pct": round(bb9 * 2.63, 1), "WAR": war,
        "LOB_pct": round(U(70, 80, 1), 1), "FB_velo": velo,
    }
    return {kk: str(vv) for kk, vv in f.items()}, a, age

# ---- per-level config ----
LEVELS = {
    "MLB": dict(label="MLB", g=(120, 155), pa_per_g=4.2, war_mult=1.0, age=(23, 35),
                gs=(26, 32), g_rp=(55, 68), hit_extra=["five_tool", "slugger", "burner"],
                sp_extra=["ace", "mid_sp"], rp_extra=["setup", "closer"]),
    "AAA": dict(label="AAA", g=(95, 130), pa_per_g=4.1, war_mult=0.7, age=(22, 28),
                gs=(20, 27), g_rp=(40, 55), hit_extra=["solid", "average", "raw"],
                sp_extra=["mid_sp", "backend_sp"], rp_extra=["middle", "raw_arm"]),
    "AA": dict(label="AA", g=(85, 120), pa_per_g=4.0, war_mult=0.55, age=(20, 25),
               gs=(18, 25), g_rp=(34, 50), hit_extra=["average", "weak", "raw", "raw"],
               sp_extra=["backend_sp", "mid_sp"], rp_extra=["middle", "raw_arm"]),
    "A+": dict(label="A+", g=(70, 110), pa_per_g=3.9, war_mult=0.45, age=(19, 23),
               gs=(15, 23), g_rp=(28, 44), hit_extra=["weak", "raw", "raw", "average"],
               sp_extra=["backend_sp", "raw_arm" if False else "mid_sp"], rp_extra=["raw_arm", "middle"]),
    "A": dict(label="A", g=(55, 100), pa_per_g=3.8, war_mult=0.4, age=(18, 22),
              hit_extra=["raw", "raw", "weak"], gs=(13, 21), g_rp=(24, 40),
              sp_extra=["backend_sp", "raw_arm" if False else "mid_sp"], rp_extra=["raw_arm", "raw_arm"]),
}

def norm_pos(slot):
    if slot == "OF":
        return pick(["LF", "CF", "RF"])
    if slot == "UT":
        return pick(["2B", "3B", "LF"])
    if slot == "IF":
        return pick(["SS", "3B", "2B"])
    return slot

# (level, [hitter position slots], [pitcher role slots])
COMP = [
    ("MLB", ["C", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH", "UT", "OF", "IF"],
            ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP", "RP", "RP"]),
    ("AAA", ["C", "1B", "3B", "SS", "OF", "OF", "UT"], ["SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP"]),
    ("AA",  ["C", "2B", "SS", "OF", "OF", "3B", "1B"], ["SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP"]),
    ("A+",  ["C", "1B", "2B", "SS", "3B", "OF", "OF", "DH"], ["SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP"]),
    ("A",   ["C", "1B", "2B", "SS", "3B", "OF", "OF", "OF"], ["SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP"]),
]

def card_for(form):
    r = client.post("/generate_custom", data=form)
    j = r.get_json()
    if not j or "error" in j:
        raise RuntimeError(f"engine error: {j} for {form.get('name')}")
    return j

def fmt_hitter(name, age, bats, throws, c):
    r = c["ratings"]
    head = (f"{name} — {c['position']} | Age {age} | B/T {bats}/{throws} | OVR {c['ovr']}\n"
            f"    CON L{r['contact_left']}/R{r['contact_right']}  POW L{r['power_left']}/R{r['power_right']}  "
            f"VIS {r['vision']}  DIS {r['discipline']}  CLU {r['batting_clutch']}\n"
            f"    SPD {r['speed']}  STE {r['stealing']}  BR-AGG {r['br_aggressiveness']}  DUR {r['durability']}  "
            f"FLD {r['fielding']}  ARM {r['arm_strength']}/ACC {r['arm_accuracy']}\n")
    if c["position"] == "C":
        # Custom path can't model catcher blocking/pop-time/directional reactions.
        tail = "    Blocking / Pop / Reactions = set to Show position default (not stat-modeled)  " \
               f"BNT {r['bunting']}  DRG {r['drag_bunt']}\n"
    else:
        tail = (f"    REA F{r['reaction_forward']}/B{r['reaction_back']}/L{r['reaction_left']}/R{r['reaction_right']}  "
                f"BNT {r['bunting']}  DRG {r['drag_bunt']}\n")
    return head + tail

def fmt_pitcher(name, age, throws, velo_mph, c):
    r = c["ratings"]
    return (f"{name} — {r.get('role','RP')} | Age {age} | T {throws} | OVR {c['ovr']} | {velo_mph} mph\n"
            f"    K/9 L{r['k_per_9_left']}/R{r['k_per_9_right']}  H/9 L{r['h_per_9_left']}/R{r['h_per_9_right']}  "
            f"CTL {r['control']}  VEL {r['velocity']}  STA {r['stamina']}  BRK {r['break_']}  "
            f"HR/9 {r['hr_per_9']}  CLU {r['pitching_clutch']}\n")

def build_team(num):
    abbr = f"T{num:02d}"
    lines = [f"# Team {num:02d}  ({abbr})", "", "*Custom 90-man org. OVR + attributes from the Ratings Converter engine.*", ""]
    ovrs = []
    closer_used = False
    for level, hit_slots, pit_slots in COMP:
        cfg = LEVELS[level]
        lines.append(f"## {level}")
        lines.append("")
        lines.append("### Position players")
        for slot in hit_slots:
            pos = norm_pos(slot)
            age = I(*cfg["age"])
            bats = pick(["R", "R", "L", "S"])
            form, arch, _ = hitter_form(pos, cfg, gen_name(), abbr, age)
            c = card_for(form)
            ovrs.append((level, c["ovr"]))
            lines.append(fmt_hitter(form["name"], age, bats, form_throws(pos), c).rstrip())
        lines.append("")
        lines.append("### Pitchers")
        for slot in pit_slots:
            age = I(*cfg["age"])
            form, arch, _ = pitcher_form(slot, cfg, gen_name(), abbr, age)
            # guarantee exactly one closer at MLB (first RP)
            if level == "MLB" and slot == "RP" and not closer_used:
                form2, _, _ = pitcher_form("RP", cfg, form["name"], abbr, age)
                form = force_closer(form, age)
                closer_used = True
            c = card_for(form)
            ovrs.append((level, c["ovr"]))
            lines.append(fmt_pitcher(form["name"], age, form["throws"], form["FB_velo"], c).rstrip())
        lines.append("")
    return "\n".join(lines), ovrs

def form_throws(pos):
    return "R" if pos in ("C", "2B", "SS", "3B", "CF") else pick(["R", "R", "L"])

def force_closer(form, age):
    p = PIT["closer"]
    velo = U(*p["velo"], 1); k9 = U(*p["k9"], 1); bb9 = U(*p["bb9"], 1)
    era = U(*p["era"], 2); whip = U(*p["whip"], 3)
    g = I(58, 68); ip = round(g * U(0.9, 1.1, 2), 1)
    h9 = max(5.0, round(whip * 9 - bb9, 1))
    f = dict(form)
    f.update({"role": "RP", "G": str(g), "GS": "0", "IP": str(ip), "SV": str(I(28, 45)),
              "ERA": str(era), "WHIP": str(whip), "K_per_9": str(k9), "BB_per_9": str(bb9),
              "H_per_9": str(h9), "K_pct": str(round(k9 * 2.63, 1)), "BB_pct": str(round(bb9 * 2.63, 1)),
              "FB_velo": str(velo), "FIP": str(round(era * U(0.92, 1.08), 2))})
    return f

def main():
    teams = range(1, 31)
    if len(sys.argv) > 1:
        teams = [int(sys.argv[1])]
    all_ovrs = []
    for n in teams:
        txt, ovrs = build_team(n)
        with open(os.path.join(OUT, f"Team_{n:02d}.md"), "w", encoding="utf-8") as fh:
            fh.write(txt)
        all_ovrs.extend(ovrs)
    # summary
    by_level = {}
    for lvl, o in all_ovrs:
        by_level.setdefault(lvl, []).append(o)
    print(f"Generated {len(list(teams))} team(s), {len(all_ovrs)} players -> {OUT}")
    for lvl in ["MLB", "AAA", "AA", "A+", "A"]:
        v = by_level.get(lvl, [])
        if v:
            print(f"  {lvl:>3}: n={len(v):>4}  OVR min {min(v):>2}  med {int(statistics.median(v)):>2}  max {max(v):>2}")

if __name__ == "__main__":
    main()
