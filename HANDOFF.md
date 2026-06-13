# HANDOFF — Prospect Pool Expansion (2026-06-13)

## State: Part 2 DONE + LIVE. Part 1 OPEN.

Task: "create some actual prospects." Two parts. Alex's choices: expand pool beyond 900
using the **FG-Board + MiLB-stat-pool** option; build via BOTH scouting-grade and
real-stat methods; save to player pool.

## Part 2 (pool expansion) — COMPLETE, verified live at localhost:5000
`prospect_data/teams.json` went **900 -> 2494** (30 orgs, ~71-92 each):
900 original graded (untouched) + 166 extra FanGraphs-graded + 1428 stat-derived.
Zero changes to app.py / card engine / routes / templates — stat guys flow through the
unchanged `_scouting_card` path via SYNTHETIC grades in the existing schema.

New/changed files (project root):
- `expand_prospects.py` — idempotent builder. Backup-as-source (`prospect_data/teams.backup.json`)
  so re-runs never double-append. Knobs `MIN_PA=100`, `MIN_IP=30`. Reuses scrape_prospects helpers.
- `prospect_data/affiliate_org_map.json` — 120 affiliates -> org abbrev (MLB Stats API).
- `prospect_data/teams.backup.json` — canonical graded base (900) for rebuilds.
- `test_expand_prospects.py` — 7 tests. Full prospect suite 32/32 green.
- `prospect_data/teams.json` — REWRITTEN with the 2494.

Runtime inputs: `prospect_data/fg_board_cache.json` (1137 graded) +
`C:/Users/Alex/DDLensAdapter/data/valucast_prospect_model_inputs.json` (`["current"]["hitters"|"pitchers"]`,
~5633 MiLB lines; `team` field is AFFILIATE name, mapped via affiliate_org_map).

## Stat-derived card model (calibrated this session)
Per-stat percentile WITHIN level -> 20-80 grade, then:
1. `LEVEL_GRADE_SHIFT` (A -12 / A+ -8 / AA -4 / AAA 0) — absolute MLB-referenced downshift.
2. FV = `28 + 20*composite + LEVEL_FV_ADJ + age_fv_adj` clamp[25,55]; age penalty ramps hard
   after 23 (to -15 at 28+) so old AAA org guys don't anchor high.
3. `_blend_toward_fv(tool, fv, cap, 0.55)` — KEY coherence fix: ties lopsided stat lines
   (e.g. big power / no walks) to holistic FV. Keeps tool shape, ties tool level to FV.
Bug fixed: eye/discipline was misfiled into the fielding slot (mapper reads vision from
`present["eye"]`, fielding from `present["field"]`). Now eye keyed right; field/arm = 50.
Final OVR band: A med 62 / AAA med 64 / max 75. Stat guys flagged
`fv_source:"stat-derived"`, `grades_incomplete:true`, `source:"stat"`, carry `stat_line`.
Example: Jay Harry (TOR SS, AA) — was incoherent 73 OVR / 80 power vs 36 FV; now 69 / power 64.

## Part 1 — NOT STARTED (next action)
Build a SPECIFIC team's top prospects (scouting + real-stat) and SAVE TO POOL.
Alex said "I'll name the team" but never gave org+count. **Ask: which org + how many.**
Pool API: POST `/pool/save` with `source` in {scouting,real,custom} + `save_name`/`save_team`;
card builders `/generate_scouting`, `/generate_custom`, `/generate` (real).

## DONE 6/13 (later): stat-blend + fielding from PO/A/E
SHIPPED in expand_prospects.py (Codex built, Fable reviewed; 10 tests green; live).
- Graded prospects' PRESENT hit/power/eye/run (hitters) + fb/control (pitchers) now blended
  50/50 with continuous stat-derived grades -> de-clustered (TOR graded hitters 11 distinct
  contact values, was a handful). Gated MIN_PA=100/MIN_IP=30. Flag `stat_blended`.
- Fielding from real MiLB PO/A/E: `prospect_data/milb_fielding_2026.json` (4492 players,
  statsapi sport-level fielding sportId 11-14 gameType R). field grade from fld% + rangeFactor
  percentiles within (posgroup, level); arm from assist-rate + error-rate pctiles (1B arm
  skipped); gate MIN_FIELD_INN=50. Blended 50/50 for graded, REPLACES flat-50 for stat guys.
  Flag `fielding_stat` + `fielding_line`. Juan Sanchez (.824 fld%, 9E) -> FIELD 38; clean.
- KEY: MiLB people-stats only come from the SPORT-level /stats endpoint (per-player returns
  0 splits). Pattern: stats=season&group=fielding&sportId=<11-14>&season=2026&gameType=R&playerPool=all&limit=5000.
- Graded OVR median held 69, stat 63 (no re-inflation). PROSPECT_CARDS_TOR.txt regenerated.

## (superseded) earlier note: stat-blend graded prospects
Graded prospects (FanGraphs/Pipeline) use coarse 5-pt scouting buckets (45/50/55/60),
so several map to IDENTICAL in-game ratings and look samey. They are NOT defaulted-to-50
(grades_incomplete=0 for TOR) — the clustering is the bucketing. We HAVE continuous MiLB
stat lines for ~26/30 of them (valucast pool, join by normalized name / mlbam_id).
PLAN: extend expand_prospects.py with a stat-blend mode that runs the existing
percentile-within-level synthetic-grade model on EVERY prospect that has a stat line and
blends stat-derived tools with their FV/scouting grades, so cards are performance-driven
and stop clustering. Caveat to keep: MiLB stats lack Statcast (EV/sprint/OAA) + differ in
run environment -> percentile-rough, not the precise MLB engine. Trigger phrase next chat:
"stat-blend the graded prospects' ratings."

## Open / cautions
- Optional UI: badge stat-derived vs FG-graded in the prospect list (offered, no answer).
- NOT committed/pushed. Public repo w/ scraped MLB/FG data — ASK Alex before committing.
- After tuning knobs: re-run `expand_prospects.py`, then RESTART Flask (teams.json cached
  in memory by prospect_store). Restart ONLY the port-5000 PID
  (`netstat -ano | grep :5000` -> taskkill that PID), NOT all python.

## Run
`"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" app.py` -> http://localhost:5000
Rebuild pool: same python `expand_prospects.py`

`expand_prospects.py` reads ValuCast inputs from `$VALUCAST_INPUTS`
(defaults to the DDLensAdapter path). It warns to stderr if the file is missing.
