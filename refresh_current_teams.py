#!/usr/bin/env python3
"""Refresh current-team fields for archived players embedded by Sweater.

Sweater's main active pool comes from NHL /roster/{team}/current endpoints.
Around a trade, a player can temporarily disappear from those roster feeds while
his NHL player landing page already has the new currentTeamAbbrev. Older daily
puzzles can then re-embed an archived copy with the player's former team.

This pass targets exactly those players: anyone embedded in schedule.json or the
generated site who is NOT present in the fresh current_rosters.json snapshot.
It checks their NHL player landing record and updates active players to the
landing page's currentTeamAbbrev.

The script is fail-open. NHL/API problems never block the Pages deploy.
"""
import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PLAYER_LANDING = "https://api-web.nhle.com/v1/player/{player_id}/landing"
CURRENT_TEAMS = {
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH",
    "NJD", "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WSH", "WPG",
}


def get_json(url, timeout=20):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Sweater current-team refresh)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  Could not read {path}: {exc}")
        return default


def embedded_players_from_html(path):
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
    return html, start, end, json.loads(html[start:end])


def landing_current(player_id):
    try:
        data = get_json(PLAYER_LANDING.format(player_id=player_id))
    except Exception as exc:
        return player_id, None, str(exc)

    team = data.get("currentTeamAbbrev")
    if isinstance(team, dict):
        team = team.get("default")
    if not data.get("isActive") or team not in CURRENT_TEAMS:
        return player_id, None, None

    return player_id, {
        "team": team,
        "number": data.get("sweaterNumber"),
        "pos": data.get("position"),
        "headshot": data.get("headshot"),
    }, None


def current_for_archived_players(candidate_ids):
    ids = sorted(set(candidate_ids))
    if not ids:
        return {}

    print(f"Checking {len(ids)} archived/missing-roster player(s) against NHL player landing data...")
    live = {}
    failures = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(landing_current, pid) for pid in ids]
        for future in as_completed(futures):
            pid, info, error = future.result()
            if error:
                failures += 1
            elif info:
                live[pid] = info

    print(
        f"  Landing checks finished in {time.time() - started:.1f}s: "
        f"{len(live)} active player(s), {failures} request failure(s)."
    )
    return live


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

        if now.get("number") is not None:
            player["number"] = now["number"]
        if now.get("pos"):
            player["pos"] = now["pos"]
        if now.get("headshot"):
            player["headshot"] = now["headshot"]

    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="site/index.html")
    ap.add_argument("--schedule", default="schedule.json")
    ap.add_argument("--rosters", default="current_rosters.json")
    args = ap.parse_args()

    html_path = Path(args.html)
    schedule_path = Path(args.schedule)
    roster_path = Path(args.rosters)

    try:
        html, html_start, html_end, embedded = embedded_players_from_html(html_path)
    except Exception as exc:
        print(f"WARNING: current-team refresh skipped: {exc}")
        return

    schedule = load_json(schedule_path, {})
    archive = schedule.get("players") or {}
    rosters = load_json(roster_path, {})

    fresh_ids = {int(pid) for pid in rosters if str(pid).isdigit()}

    archive_players = [p for p in archive.values() if isinstance(p, dict)]
    all_players = embedded + archive_players

    candidate_ids = set()
    for player in all_players:
        try:
            pid = int(player.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        if pid not in fresh_ids:
            candidate_ids.add(pid)

    live = current_for_archived_players(candidate_ids)
    if not live:
        print("No active archived players needed a current-team landing check.")
        return

    schedule_changes = apply(archive_players, live, "schedule archive")
    html_changes = apply(embedded, live, "generated site")

    if schedule_changes:
        schedule_path.write_text(
            json.dumps(schedule, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    if html_changes:
        payload = json.dumps(embedded, ensure_ascii=False).replace("</", "<\\/")
        html = html[:html_start] + payload + html[html_end:]
        html_path.write_text(html, encoding="utf-8")

    print(
        f"Current-team refresh complete: {schedule_changes} archive correction(s), "
        f"{html_changes} site correction(s)."
    )


if __name__ == "__main__":
    main()
