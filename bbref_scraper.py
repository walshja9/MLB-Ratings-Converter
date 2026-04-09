"""
Direct Baseball-Reference scraper. Replaces pybaseball's broken BBRef helpers
and the dead FanGraphs ingestion path.

- Uses cloudscraper to defeat BBRef's Cloudflare layer.
- Uses pandas.read_html to parse leaderboard tables.
- Returns DataFrames with column names matching what generate_card.py
  previously consumed from FanGraphs (e.g. AVG, K%, BB%, K/9, BB/9, FIP, WAR).
- FG-only metrics (Spd, BsR, wOBA, LOB%, FBv, RngR, ErrR, Def) are added as
  NaN columns so call sites that check for them gracefully fall back.
- Adds new BBRef-only fielding columns: Rtot, Rtot/yr, Rdrs, Rdrs/yr.
  These are surfaced as NEW era-specific inputs, not drop-in replacements.
- In-memory cache keyed by (kind, year). One fetch per process per year.
"""

import io
import math
import warnings
import numpy as np
import pandas as pd
import cloudscraper

warnings.filterwarnings("ignore")

_BBREF_BASE = "https://www.baseball-reference.com/leagues/majors"

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "desktop": True}
)

_cache: dict = {}  # {(kind, year): DataFrame}


def _fetch_tables(url: str) -> list:
    r = _scraper.get(url, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"BBRef fetch failed {r.status_code}: {url}")
    # BBRef wraps many tables in HTML comments to defeat naive scrapers.
    html = r.text.replace("<!--", "").replace("-->", "")
    return pd.read_html(io.StringIO(html))


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-index columns to single strings, dropping 'Unnamed: ...' prefixes."""
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    flat = []
    for top, sub in df.columns:
        if str(top).startswith("Unnamed"):
            flat.append(str(sub))
        else:
            flat.append(f"{top} {sub}")
    df = df.copy()
    df.columns = flat
    return df


def _drop_header_repeats(df: pd.DataFrame, key_col: str = "Player") -> pd.DataFrame:
    """BBRef tables periodically repeat the header row. Drop those."""
    if key_col not in df.columns:
        return df
    return df[df[key_col].astype(str) != key_col]


def _safe_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _dedupe_traded(df: pd.DataFrame, sort_col: str, group_cols=None) -> pd.DataFrame:
    """For multi-team players, BBRef shows individual stint rows AND a 'XTM'
    aggregate row (e.g. '2TM'). Collapse a group ONLY when an XTM row exists
    (i.e. the rows are provably the same player split across teams). Groups
    with multiple non-XTM rows are left intact, because they're almost always
    distinct players who happen to share a name in the same season — those
    must reach downstream disambiguation logic untouched.
    """
    if "Player" not in df.columns or "Team" not in df.columns:
        return df

    if group_cols is None:
        group_cols = ["Player"]

    xtm_re = r"^\d+TM$"
    out_rows = []

    for _, group in df.groupby(group_cols, as_index=False, sort=False):
        agg = group[group["Team"].astype(str).str.match(xtm_re, na=False)]
        if not agg.empty:
            # Traded player: keep only the XTM aggregate row(s).
            out_rows.append(agg.iloc[[0]])
        else:
            # No XTM row → either 1 row, or genuinely distinct same-name
            # players. Keep everything; let downstream disambiguate.
            out_rows.append(group)

    if not out_rows:
        return df.iloc[0:0]
    return pd.concat(out_rows, ignore_index=True)


# ----------------------------------------------------------------------
# BATTING
# ----------------------------------------------------------------------

def bbref_batting_df(year: int) -> pd.DataFrame:
    """Replacement for pybaseball.batting_stats(year, qual=0).
    Returns one row per player with FG-compatible column names."""
    key = ("bat", year)
    if key in _cache:
        return _cache[key]

    url = f"{_BBREF_BASE}/{year}-standard-batting.shtml"
    tables = _fetch_tables(url)
    # Player leaderboard is the largest table (not the team summary).
    df = max((t for t in tables if "Player" in [str(c) for c in t.columns]),
             key=lambda t: len(t), default=None)
    if df is None:
        raise RuntimeError(f"No player batting table at {url}")

    df = _drop_header_repeats(df)
    df = _safe_numeric(df, ["G","PA","AB","H","2B","3B","HR","SB","CS","BB","SO","HBP","SF","WAR"])
    df = _safe_numeric(df, ["BA","OBP","SLG"])
    df = _dedupe_traded(df, sort_col="PA")

    # Rename + derive FG-compatible columns
    df["Name"] = df["Player"].astype(str).str.replace(r"[*#]+$", "", regex=True).str.strip()
    df["AVG"]  = df["BA"]
    df["ISO"]  = (df["SLG"] - df["BA"]).round(3)

    # Walk and strikeout rates as decimals (FG convention — code multiplies by 100 later)
    pa = df["PA"].replace(0, np.nan)
    df["BB%"] = (df["BB"] / pa).round(4)
    df["K%"]  = (df["SO"] / pa).round(4)

    # FG-only metrics — explicit NaN, NOT silent zeros
    for c in ["Spd", "BsR", "wOBA"]:
        df[c] = np.nan

    _cache[key] = df
    return df


# ----------------------------------------------------------------------
# PITCHING
# ----------------------------------------------------------------------

def bbref_pitching_df(year: int) -> pd.DataFrame:
    """Replacement for pybaseball.pitching_stats(year, qual=0)."""
    key = ("pit", year)
    if key in _cache:
        return _cache[key]

    url = f"{_BBREF_BASE}/{year}-standard-pitching.shtml"
    tables = _fetch_tables(url)
    df = max((t for t in tables if "Player" in [str(c) for c in t.columns]),
             key=lambda t: len(t), default=None)
    if df is None:
        raise RuntimeError(f"No player pitching table at {url}")

    df = _drop_header_repeats(df)
    df = _safe_numeric(df, ["W","L","G","GS","SV","IP","H","ER","HR","BB","SO","BF","WAR"])
    df = _safe_numeric(df, ["ERA","FIP","WHIP","H9","HR9","BB9","SO9"])
    df = _dedupe_traded(df, sort_col="IP")

    df["Name"] = df["Player"].astype(str).str.replace(r"[*#]+$", "", regex=True).str.strip()

    # Map BBRef rate columns -> FG names
    df["K/9"]  = df["SO9"]
    df["BB/9"] = df["BB9"]
    df["HR/9"] = df["HR9"]
    df["H/9"]  = df["H9"]

    bf = df["BF"].replace(0, np.nan)
    df["K%"]  = (df["SO"] / bf).round(4)
    df["BB%"] = (df["BB"] / bf).round(4)

    # FG-only — set NaN. Velocity falls back gracefully when None.
    df["LOB%"] = np.nan
    df["FBv"]  = np.nan

    _cache[key] = df
    return df


# ----------------------------------------------------------------------
# FIELDING
# ----------------------------------------------------------------------

def bbref_fielding_df(year: int) -> pd.DataFrame:
    """Replacement for pybaseball.fielding_stats(year, qual=0).
    Notable additions vs FG: Rtot (Total Zone) and Rdrs (DRS) for the eras
    where BBRef provides them. These are NEW inputs — callers must opt in,
    not assume drop-in compatibility with RngR/Def."""
    key = ("fld", year)
    if key in _cache:
        return _cache[key]

    url = f"{_BBREF_BASE}/{year}-standard-fielding.shtml"
    tables = _fetch_tables(url)
    df = None
    # Find the largest player-level table (multi-index columns).
    candidates = []
    for t in tables:
        flat = _flatten_cols(t)
        if "Player" in flat.columns:
            candidates.append(flat)
    if not candidates:
        raise RuntimeError(f"No player fielding table at {url}")
    df = max(candidates, key=len)

    df = _drop_header_repeats(df)
    df = _safe_numeric(df, ["Standard G","Standard GS","Standard CG","Standard Inn",
                            "Standard Ch","Standard PO","Standard A","Standard E",
                            "Standard DP","Standard Fld%",
                            "Total Zone Rtot","Total Zone Rtot/yr",
                            "DRS Rdrs","DRS Rdrs/yr"])

    # Drop traded-player double counting: BBRef emits per-team-per-position
    # rows AND an XTM aggregate row for the same position. Collapse per
    # (Player, Pos) so multi-position players still sum across positions.
    if "Pos" in df.columns and "Team" in df.columns:
        df = _dedupe_traded(df, sort_col="Standard Inn", group_cols=["Player", "Pos"])

    df["Name"] = df["Player"].astype(str).str.replace(r"[*#]+$", "", regex=True).str.strip()

    # Map BBRef columns -> simpler names matching the rest of the code
    df["G"]      = df.get("Standard G")
    df["GS"]     = df.get("Standard GS")
    df["Inn"]    = df.get("Standard Inn")
    df["Ch"]     = df.get("Standard Ch")
    df["A"]      = df.get("Standard A")
    df["E"]      = df.get("Standard E")
    df["Fld_pct"]= df.get("Standard Fld%")
    df["Pos"]    = df.get("Pos")

    # New BBRef-specific defensive inputs (era-specific)
    df["Rtot"]    = df.get("Total Zone Rtot")
    df["Rtot_yr"] = df.get("Total Zone Rtot/yr")
    df["Rdrs"]    = df.get("DRS Rdrs")
    df["Rdrs_yr"] = df.get("DRS Rdrs/yr")

    # FG-only — explicit NaN so existing checks fall back to baseline.
    for c in ["OAA", "Def", "rARM", "RngR", "ErrR"]:
        df[c] = np.nan

    _cache[key] = df
    return df


if __name__ == "__main__":
    # Smoke test
    for year in (2024, 1995):
        bat = bbref_batting_df(year)
        pit = bbref_pitching_df(year)
        fld = bbref_fielding_df(year)
        print(f"{year}: bat {bat.shape}, pit {pit.shape}, fld {fld.shape}")
