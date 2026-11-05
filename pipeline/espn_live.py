"""
Live rosters and depth charts from ESPN's public JSON (the same data behind espn.com).

nflverse's roster file only catches up to moves about once a week, and it can't see the
offseason at all once a season ends. ESPN shows trades, releases and signings much sooner.
pipeline/roster_moves.py combines the two.

This file only uses Python's built-in tools, so the quick "did anything change?" check in
the scheduled job can run in seconds without installing anything:

    python3 pipeline/espn_live.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
# Published with the site, so the check below can see what the live site actually has.
FINGERPRINT = Path(__file__).resolve().parent.parent / "public" / "data" / "roster_fingerprint.txt"

ESPN_TEAMS = ("ari atl bal buf car chi cin cle dal den det gb hou ind jax kc "
              "lv lac lar mia min ne no nyg nyj phi pit sf sea tb ten wsh").split()

# Teams with a smaller list than this mean a bad response, not a real roster.
MIN_ROSTER = 40


def app_team(team) -> str:
    """The team codes this app uses (nflverse's): ESPN says LAR and WSH, nflverse says LA and WAS."""
    code = str(team).upper()
    return {"LAR": "LA", "WSH": "WAS"}.get(code, code)


def _get(url: str, tries: int = 3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nfl-stats-app"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:  # network hiccup or bad response: wait a moment and try again
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def fetch_rosters() -> dict:
    """{espn id: {team, group, name, ...}} for every player on a team's list right now."""
    out = {}
    for t in ESPN_TEAMS:
        doc = _get(f"{BASE}/{t}/roster")
        items = [(g.get("position"), a) for g in doc.get("athletes", []) for a in g.get("items", [])]
        if len(items) < MIN_ROSTER:
            raise ValueError(f"{t} roster has only {len(items)} players")
        for group, a in items:
            out[str(a["id"])] = {
                "team": app_team(t), "group": group, "name": a.get("fullName"),
                "first": a.get("firstName"), "last": a.get("lastName"),
                "birth": (a.get("dateOfBirth") or "")[:10],
                "pos": (a.get("position") or {}).get("abbreviation"),
                "jersey": a.get("jersey"), "height": a.get("height"), "weight": a.get("weight"),
                "college": (a.get("college") or {}).get("name"),
                "years": (a.get("experience") or {}).get("years"),
                "headshot": (a.get("headshot") or {}).get("href"),
                "injuries": [i.get("status") for i in a.get("injuries", [])],
            }
    return out


def fetch_depth() -> dict:
    """{espn id: [teams whose depth chart lists him]}. Teams edit these right after a move."""
    out = {}
    for t in ESPN_TEAMS:
        doc = _get(f"{BASE}/{t}/depthcharts")
        for chart in doc.get("depthchart", []):
            for spot in (chart.get("positions") or {}).values():
                for a in spot.get("athletes", []):
                    teams = out.setdefault(str(a["id"]), [])
                    if app_team(t) not in teams:
                        teams.append(app_team(t))
    return out


def fetch_live() -> dict | None:
    """Everything live, or None if ESPN can't be reached (the build then uses nflverse alone)."""
    try:
        return {"rosters": fetch_rosters(), "depth": fetch_depth()}
    except Exception as e:
        print(f"  WARNING: couldn't load live ESPN rosters ({e}); using nflverse's rosters only")
        return None


def fingerprint(live: dict) -> str:
    """A short code that changes only when someone joins, leaves or changes a list."""
    rows = sorted(f"r|{pid}|{p['team']}|{p['group']}" for pid, p in live["rosters"].items())
    rows += sorted(f"d|{pid}|{','.join(sorted(teams))}" for pid, teams in live["depth"].items())
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def save_fingerprint(live: dict) -> None:
    FINGERPRINT.write_text(fingerprint(live) + "\n")


def published_fingerprint() -> str:
    """The code on the live site. Comparing with this (not the repo's copy) means a publish that
    failed gets retried on the next check. Empty if it can't be read, which triggers a rebuild."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    try:
        if not repo:
            return FINGERPRINT.read_text().strip()
        owner, name = repo.split("/")
        url = f"https://{owner}.github.io/{name}/data/roster_fingerprint.txt?t={int(time.time())}"
        req = urllib.request.Request(url, headers={"User-Agent": "nfl-stats-app"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode().strip()
    except Exception:
        return ""


def check() -> bool:
    """True if the live site's rosters are out of date. If ESPN is down, there's nothing to act on."""
    live = fetch_live()
    if live is None:
        return False
    return fingerprint(live) != published_fingerprint()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="say whether rosters changed since the last build")
    if ap.parse_args().check:
        changed = check()
        print("Roster moves found." if changed else "No roster moves.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"changed={'true' if changed else 'false'}\n")
    sys.exit(0)
