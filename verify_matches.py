"""Verify we're matching the right players in career data pulls."""
from pybaseball import batting_stats, fielding_stats
import warnings
warnings.filterwarnings("ignore")

suspect = ["Matt Shaw", "Pete Crow-Armstrong", "Hyeseong Kim", "Adley Rutschman",
           "Byron Buxton", "Yordan Alvarez"]

for year in [2022, 2023, 2024, 2025]:
    bat = batting_stats(year, qual=0)
    fld = fielding_stats(year, qual=0)
    print(f"\n=== {year} ===")
    for name in suspect:
        # Exact match first
        match = bat[bat["Name"] == name]
        if match.empty:
            for part in name.split():
                if len(part) > 3:
                    match = bat[bat["Name"].str.contains(part, case=False, na=False)]
                    if len(match) >= 1:
                        break
        if not match.empty:
            if len(match) > 1:
                match = match.sort_values("PA", ascending=False).head(1)
            row = match.iloc[0]
            actual_name = row["Name"]
            team = row.get("Team", "?")
            pa = row["PA"]
            hr = row["HR"]
            age = row.get("Age", "?")
            correct = "OK" if actual_name == name else f"WRONG -> {actual_name}"
            print(f"  {name:<25} {correct:<20} Team={team:<5} PA={pa:>4} HR={hr:>3} Age={age}")
        else:
            print(f"  {name:<25} NOT FOUND")

        # Check fielding match too
        fld_match = fld[fld["Name"] == name]
        if fld_match.empty:
            for part in name.split():
                if len(part) > 3:
                    fld_match = fld[fld["Name"].str.contains(part, case=False, na=False)]
                    if len(fld_match) >= 1:
                        break
        if not fld_match.empty:
            if len(fld_match) > 1:
                fld_match = fld_match.sort_values("G", ascending=False).head(1)
            frow = fld_match.iloc[0]
            fld_name = frow["Name"]
            if fld_name != name:
                print(f"    FIELDING MISMATCH: {fld_name}")
