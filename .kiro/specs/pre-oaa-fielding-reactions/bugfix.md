# Bugfix Requirements Document

## Introduction

For players in the pre-OAA era (pre-2020) and especially pre-2003, the defensive card feels
artificially soft compared to real MLB The Show ratings. The root cause is two-fold:

1. The Rdrs/Rtot slopes used for fielding are too conservative, producing muted FIELD numbers
   for historical defenders even when the underlying metric is strong.
2. Reactions (L/R/F/B) are only driven by RngR or OAA. When neither is available — which is
   the case for all pre-2003 players and many 2003-2014 players who lack RngR — reactions fall
   back to flat position defaults. A great pre-OAA defender therefore gets a decent FIELD number
   but dead, baseline reactions, making the whole defensive section feel weaker than Show.

The fix has two parts: recalibrate the Rdrs/Rtot fielding slopes, and let Rdrs/Rtot also
drive reactions as a proxy when RngR/OAA are unavailable.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a player has only Rdrs (DRS, 2003-2019) and no RngR or OAA THEN the system uses
    a conservative slope (`2.0 * Rdrs + 68`) that underestimates the FIELD rating relative
    to known Show values for strong defenders.

1.2 WHEN a player has only Rtot (Total Zone, pre-2003) and no RngR or OAA THEN the system
    uses an even more conservative slope (`1.6 * Rtot + 68`) that further underestimates
    the FIELD rating for historical defenders.

1.3 WHEN a player has Rdrs or Rtot but no RngR and no OAA THEN the system assigns flat
    position-default reactions (react_l/r/f/b), ignoring the available range information
    entirely, making the defensive card feel dead regardless of how good the fielding metric is.

1.4 WHEN a player is in the pre-2003 era and has Rtot but no innings data THEN the system
    applies `def_trust = 0` (because `innings = 0`), collapsing the fielding rating entirely
    to the position baseline even when Rtot is available and meaningful.

### Expected Behavior (Correct)

2.1 WHEN a player has only Rdrs and no RngR or OAA THEN the system SHALL use a recalibrated
    slope that maps Rdrs to FIELD ratings consistent with known Show values for the same
    defensive tier (e.g. a +15 DRS defender should land near 85-88 FIELD, not 78).

2.2 WHEN a player has only Rtot and no RngR or OAA THEN the system SHALL use a recalibrated
    slope that maps Rtot to FIELD ratings consistent with known Show values, with a slightly
    wider confidence interval than Rdrs given the coarser metric.

2.3 WHEN a player has Rdrs or Rtot but no RngR and no OAA THEN the system SHALL derive a
    base reaction value from Rdrs or Rtot (as a range proxy) and apply it through the
    existing directional-weight system, so reactions reflect the player's actual range quality
    rather than a flat default.

2.4 WHEN a player has Rtot but no innings data (pre-2003 era) THEN the system SHALL apply
    a non-zero trust factor derived from the metric itself (e.g. games played or a fixed
    partial trust) so that Rtot meaningfully influences the fielding rating rather than
    being overridden entirely by the position baseline.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a player has OAA data (2020+) THEN the system SHALL CONTINUE TO use the OAA-based
    fielding formula (`2.09 * OAA + 68.6`) and OAA-based reactions unchanged.

3.2 WHEN a player has RngR data (2003-2019 UZR era) THEN the system SHALL CONTINUE TO use
    RngR as the primary reactions driver (`2.0 * RngR + 65`) ahead of Rdrs/Rtot.

3.3 WHEN a player has FG Def data THEN the system SHALL CONTINUE TO use FG Def as the
    primary fielding input (`1.38 * FG_Def + 67.3`) ahead of Rdrs/Rtot.

3.4 WHEN a player has sufficient innings data THEN the system SHALL CONTINUE TO apply the
    def_trust blending between the metric-driven rating and the position baseline.

3.5 WHEN a player is a DH or has very low field_pct THEN the system SHALL CONTINUE TO
    blend the position baseline toward DH level as before.

3.6 WHEN a player has no defensive metrics at all THEN the system SHALL CONTINUE TO return
    the position baseline for both fielding and reactions.
