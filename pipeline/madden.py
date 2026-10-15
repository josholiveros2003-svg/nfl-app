"""
Madden ratings: the starting point (baseline) for every player and team rating.

Source: a spreadsheet of EA's official Madden NFL 27 *launch* ratings (August 2026),
posted for free by the fan site MaddenRatings.net. You download it once by hand and save
it in data/madden/ (any .xlsx name works). The pipeline never downloads it, and it
doesn't need to update during the season.

Each Madden player is matched to his NFL id (the one nflverse uses) by:
  1. name + team, then
  2. name + birthdate (catches players who changed teams since August), then
  3. last name + birthdate (catches nickname spellings like "Mike"/"Michael"), then
  4. name alone, when exactly one player has it (a few spreadsheet birthdates are off).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MADDEN_DIR = Path(__file__).resolve().parent.parent / "data" / "madden"

# Madden position -> our position groups (used only as a fallback; nflverse position wins).
MADDEN_GROUP = {
    "QB": "QB", "HB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    "LT": "OL", "LG": "OL", "C": "OL", "RG": "OL", "RT": "OL",
    "LEDG": "DL", "REDG": "DL", "DT": "DL", "SAM": "LB", "MIKE": "LB", "WILL": "LB",
    "CB": "DB", "FS": "DB", "SS": "DB", "K": "K", "P": "P", "LS": "LS",
}


def norm_name(name) -> str:
    s = str(name).lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def last_name(name) -> str:
    parts = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(name).lower()).split()
    return re.sub(r"[^a-z]", "", parts[-1]) if parts else ""


# Small file kept in the repo: NFL id + Madden overall only. The full spreadsheet stays on
# your computer (it's EA's data), and the online job reads this instead.
SAVED = MADDEN_DIR / "madden_overall.csv"


def find_file() -> Path | None:
    files = sorted(MADDEN_DIR.glob("*.xlsx")) if MADDEN_DIR.exists() else []
    return files[0] if files else None


def load_madden(roster: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Madden ratings with NFL ids attached: columns gsis_id, madden, madden_pos, name.
    Returns an empty table if no Madden file has been added."""
    path = find_file()
    if path is None:
        if SAVED.exists():
            print(f"  reading Madden ratings from {SAVED.name}")
            return pd.read_csv(SAVED)
        print("  no Madden file in data/madden/ - ratings will use estimated baselines")
        return pd.DataFrame(columns=["gsis_id", "madden", "madden_pos", "name", "grp"])
    print(f"  reading Madden ratings from {path.name}")
    m = pd.read_excel(path)
    # Only today's 32 teams (the team list also has old ones like STL/SD/OAK with the same nicknames).
    current = teams[~teams.team_abbr.isin(["STL", "SD", "OAK", "LAR"])]
    nick_to_abbr = dict(zip(current.team_nick, current.team_abbr))
    m["team"] = m.Team.map(nick_to_abbr)
    m["k_name"] = m.Name.map(norm_name)
    m["k_last"] = m.Name.map(last_name)
    m["bday"] = pd.to_datetime(m.PLYR_BIRTHDATE, errors="coerce").dt.strftime("%Y-%m-%d")
    m["grp"] = m.Position.map(MADDEN_GROUP)

    r = roster.dropna(subset=["gsis_id"]).sort_values("week").drop_duplicates("gsis_id", keep="last").copy()
    r["k_name"] = r.full_name.map(norm_name)
    r["k_last"] = r.full_name.map(last_name)
    r["bday"] = pd.to_datetime(r.birth_date, errors="coerce").dt.strftime("%Y-%m-%d")

    def lookup(keys):
        table = r.dropna(subset=[k for k in keys if k != "team"]).drop_duplicates(keys, keep=False)
        return table.set_index(keys).gsis_id

    by_team = lookup(["k_name", "team"])
    by_bday = lookup(["k_name", "bday"])
    by_last = lookup(["k_last", "bday"])
    unique_names = r.drop_duplicates("k_name", keep=False).set_index("k_name").gsis_id

    ids = []
    for row in m.itertuples():
        pid = by_team.get((row.k_name, row.team))
        if pid is None and isinstance(row.bday, str):
            pid = by_bday.get((row.k_name, row.bday))
        if pid is None and isinstance(row.bday, str):
            pid = by_last.get((row.k_last, row.bday))
        if pid is None:  # some spreadsheet birthdates are slightly off; a unique name is safe
            pid = unique_names.get(row.k_name)
        ids.append(pid)
    m["gsis_id"] = ids
    matched = m.dropna(subset=["gsis_id"]).drop_duplicates("gsis_id")
    print(f"  matched {len(matched)} of {len(m)} Madden players to NFL ids")
    out = matched.rename(columns={"OverallRating": "madden", "Position": "madden_pos", "Name": "name"})[
        ["gsis_id", "madden", "madden_pos", "name", "grp"]].sort_values("gsis_id")
    out.to_csv(SAVED, index=False)
    return out
