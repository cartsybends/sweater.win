#!/usr/bin/env python3
"""Refresh current-team fields for every player embedded by Sweater.

The main builder gets its active pool from NHL team roster endpoints, but archived
players from schedule.json are also embedded so older daily puzzles keep working.
Around a trade, a player can temporarily disappear from the roster feed while the
NHL player index already has the new currentTeamId. This pass updates both the
archive and the generated HTML from that independent current-team source.

This script is deliberately fail-open: if the NHL current-player index is
temporarily unavailable or incomplete, it leaves the build unchanged instead of
blocking the entire GitHub Pages deploy.
"""
import argparse
import json
import urllib.request
from pathlib import Path

PLAYER_INDEX_ACTIVE = (
    "https://api.nhle.com/stats/rest/en/players"
    "?limit=-1&cayenneExp=currentTeamId%3E0"
)
PLAYER_INDEX_TEAM = (
    "https://api.nhle.com/stats/rest/en/players"
    "?limit=-1&cayenneExp=currentTeamId%3D{team_id}"
)

TEAM_ID_TO_ABBR = {
    1: "NJD", 2: "NYI", 3: "NYR", 4: "PHI", 5: "PIT", 6: "BOS", 7: "BUF", 8: "MTL",
    9: "OTT", 10: "TOR", 12: "CAR", 13: "FLA", 14: "TBL", 15: "WSH", 16: "CHI", 17: "DET",
    18: "NSH", 19: "STL", 20: "CGY", 21: "COL", 22: "EDM", 23: "VAN", 24: "ANA", 25: "DAL",
    26: "LAK", 28: "SJS", 29: "CBJ", 30: "MIN", 52: "WPG", 54: "VGK", 55: "SEA", 59: "UTA",
}


def get_json(url, timeout=35):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Sweater current-team refresh)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def add_rows(out, rows):
    for row in rows or []:
        try:
            pid = int(row.get("id"))
            team_id = int(row.get("currentTeamId"))
        except (TypeError, ValueError):
            continue
        team = TEAM_ID_TO_ABBR.get(team_id)
        if not team:
            continue
        out[pid] = {
            "team": team,
            "number": row.get("sweaterNumber"),
            "pos": row.get("positionCode"),
        }


def current_index():
    out = {}

    # Preferred path: ask the NHL API only for players that have a current team.
    try:
        add_rows(out, get_json(PLAYER_INDEX_ACTIVE).get("data", []))
    except Exception as exc:
        print(f"  Active-player index request failed: {exc}")

    if len(out) >= 500:
        return out

    # Defensive fallback. The unfiltered /players endpoint can return a small
    # sample of historical/free-agent records, so query each current team
    # individually and merge the results.
    print(
        f"  Active-player index looked incomplete ({len(out)} players); "
        "falling back to team-by-team NHL player lookups."
    )
    out = {}
    failed = 0
    for team_id in TEAM_ID_TO_ABBR:
        try:
            rows = get_json(PLAYER_INDEX_TEAM.format(team_id=team_id), timeout=20).get("data", [])
            add_rows(out, rows)
        except Exception as exc:
            failed += 1
            print(f"  Team {TEAM_ID_TO_ABBR[team_id]} current-player lookup failed: {exc}")

    if len(out) < 500:
        print(
            f"  WARNING: NHL current-player data still looked incomplete "
            f"({len(out)} players; {failed} team requests failed). "
            "Skipping current-team refresh so the Pages deploy can continue."
        )
        return {}

    return out


def apply(players, live, label):
    changed = 0
    for player in players:
        if not isinstance(player, dict):
            continue
        try:
            pid = int(player.get("id"))
        except (TypeError, ValueError):
            continue
        now = live.get(pid)
        if not now:
            continue
        old = player.get("team")
        if old != now["team"]:
            print(
                f"  Current-team correction ({label}): "
                f"{player.get('name', pid)}: {old} -> {now['team']}"
            )
            player["team"] = now["team"]
            changed += 1
        if now["number"] is not None:
            player["number"] = now["number"]
        if now["pos"]:
            player["pos"] = now["pos"]
    return changed


def patch_schedule(path, live):
    data = json.loads(path.read_text(encoding="utf-8"))
    archive = data.get("players") or {}
    players = [p for p in archive.values() if isinstance(p, dict)]
    changed = apply(players, live, "schedule archive")
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return changed


def patch_html(path, live):
    html = path.read_text(encoding="utf-8")
    start_token = "const PLAYERS = "
    end_token = ".sort((a, b) => a.id - b.id);"
    start = html.find(start_token)
    if start < 0:
        raise RuntimeError("Couldn't find embedded PLAYERS data in generated HTML")
    start += len(start_token)
    end = html.find(end_token, start)
    if end < 0:
        raise RuntimeError("Couldn't find the end of embedded PLAYERS data")

    players = json.loads(html[start:end])
    changed = apply(players, live, "generated site")
    if changed:
        payload = json.dumps(players, ensure_ascii=False).replace("</", "<\\/")
        html = html[:start] + payload + html[end:]
        path.write_text(html, encoding="utf-8")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="site/index.html")
    ap.add_argument("--schedule", default="schedule.json")
    args = ap.parse_args()

    html_path = Path(args.html)
    schedule_path = Path(args.schedule)

    live = current_index()
    if not live:
        print("Current-team refresh skipped; generated site left unchanged.")
        return

    print(f"Loaded {len(live)} NHL players with a current team.")
    schedule_changes = patch_schedule(schedule_path, live) if schedule_path.exists() else 0
    html_changes = patch_html(html_path, live)
    print(
        f"Current-team refresh complete: {schedule_changes} archive correction(s), "
        f"{html_changes} site correction(s)."
    )


if __name__ == "__main__":
    main()
