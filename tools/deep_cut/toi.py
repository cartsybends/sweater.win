"""Verified, club-specific average skater TOI from NHL summaries/game logs."""
from collections import defaultdict
import math
import re


def usage_rows(summary, get_log):
    if len(summary["data"]) != summary["total"]:
        raise ValueError("Incomplete NHL time-on-ice response")
    rows = []
    for player in summary["data"]:
        if "timeOnIcePerGame" not in player:
            continue  # Older offline Grid fixtures predate TOI; production requires it.
        pid, season, gp = player["playerId"], player["seasonId"], player["gamesPlayed"]
        average = player["timeOnIcePerGame"]
        if average is None or average == 0:
            continue
        if not isinstance(average, (float, int)) or not math.isfinite(average) or not 0 < average < 3900 or type(gp) is not int or gp <= 0:
            raise ValueError("Invalid NHL average time on ice")
        teams = player["teamAbbrevs"].split(",")
        if len(teams) == 1:
            rows.append([pid, teams[0], season, gp, round(average, 3)])
            continue
        games = get_log(pid, season)["gameLog"]
        if len(games) != gp or len({game["gameId"] for game in games}) != gp:
            raise ValueError("Incomplete trade-season TOI game log")
        totals = defaultdict(lambda: [0, 0])
        for game in games:
            value = game.get("toi", "")
            if not re.fullmatch(r"\d{1,2}:[0-5]\d", value):
                raise ValueError("Missing NHL game-log time on ice")
            minutes, seconds = map(int, value.split(":"))
            totals[game["teamAbbrev"]][0] += 1
            totals[game["teamAbbrev"]][1] += minutes*60+seconds
        if set(totals) != set(teams):
            raise ValueError("TOI game logs disagree with the player's clubs")
        if abs(sum(seconds for _, seconds in totals.values())/gp-average) > 1:
            raise ValueError("TOI game logs disagree with the season average")
        for team, (played, seconds) in sorted(totals.items()):
            rows.append([pid, team, season, played, round(seconds/played, 3)])
    if len({(pid, team, season) for pid, team, season, _, _ in rows}) != len(rows):
        raise ValueError("Duplicate club TOI records")
    return sorted(rows)


def lowest_six(source_players, roster, rows, required=False):
    season = max((row[2] for row in rows), default=None)
    usage = {(pid, team): seconds for pid, team, year, gp, seconds in rows if year == season and gp > 0 and seconds > 0}
    result = {}
    for team in sorted(set(roster.values())):
        candidates = [(usage[(pid, team)], pid) for pid, club in roster.items() if club == team and pid in source_players and source_players[pid][2] != "G" and (pid, team) in usage]
        if required and len(candidates) < 6:
            raise ValueError(f"Fewer than six verified current skater TOI records for {team}")
        result[team] = sorted(pid for _, pid in sorted(candidates)[:6])
    return result, season
