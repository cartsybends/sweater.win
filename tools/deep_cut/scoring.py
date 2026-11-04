"""Append immutable team-prompt editions with a current-roster 10-point rule."""
from copy import deepcopy
from datetime import timedelta, date
import hashlib
import json
import math
import random
import importlib.util
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def validate(base, data):
    """Every published identity, prompt and run remains available unchanged."""
    for key, identity in [("players", lambda p: p[0]), ("prompts", lambda p: p["id"]), ("runs", lambda p: p["id"])]:
        incoming = {identity(row): row for row in data[key]}
        if len(incoming) != len(data[key]) or any(incoming.get(identity(row)) != row for row in base[key]):
            raise ValueError(f"Deep Cut changed or removed published {key}")
    return data


def publish(base, previous, source, roster, today, review=None, toi_rows=None, require_toi=False):
    """Keep historical tiers; current players get 10 in their own team's prompts.

    Current appearances are verified by Grid's NHL game-log refresh. Merely
    joining a roster does not invent a regular-season appearance for that club.
    """
    previous = validate(base, previous or base)
    if len(roster) < 500 or len({p["team"] for p in roster.values()}) != 32:
        raise ValueError("A complete current NHL roster snapshot is required")
    source_players = {p[0]: p for p in source["players"]}
    review = review or {}
    caps = {row["id"]: row["points"] for row in review.get("global_caps", [])}
    connections = {(row["team"], row["id"]): row["points"] for row in review.get("team_connections", [])}
    for row in [*review.get("global_caps", []), *review.get("team_connections", [])]:
        if row["points"] not in (10, 15, 30, 60, 85, 100) or source_players.get(row["id"], [None, None])[1] != row["name"]:
            raise ValueError("Invalid editorial familiarity adjustment")
        if "team" in row and not source_players[row["id"]][8].get(row["team"], 0):
            raise ValueError("Editorial adjustment requires a verified club appearance")
    current = {int(pid): p["team"] for pid, p in roster.items()}
    spec = importlib.util.spec_from_file_location('deep_cut_toi', Path(__file__).with_name('toi.py'))
    toi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toi)
    low_toi, toi_season = toi.lowest_six(source_players, current, toi_rows or [], require_toi)
    policy = 3 if toi_season else 2
    players = {p[0]: p for p in previous["players"]}
    prompts = {p["id"]: p for p in previous["prompts"]}
    runs = {p["id"]: p for p in previous["runs"]}
    replacements = {}
    for prompt in base["prompts"]:
        kind, _, team = prompt["rule"].partition("-")
        if kind not in ("team", "goalie"):
            rows = [[pid, min(points, caps.get(pid, points))] for pid, points in prompt["answers"]]
            if rows != prompt["answers"]:
                identity = "dc2-" + prompt["id"] + "-" + fingerprint(rows)
                replacements[prompt["id"]] = identity
                prompts.setdefault(identity, {**deepcopy(prompt), "id": identity, "version": 2, "base": prompt["id"], "answers": rows})
            continue
        eligible = [p for p in source_players.values() if p[8].get(team, 0) > 0 and (kind != "goalie" or p[2] == "G")]
        original = dict(prompt["answers"])
        def fame(p):
            value = math.log1p(p[4]) + 1.4 * bool(p[5]) + .8 * len(source["awards"].get(str(p[0]), [])) + max(0, p[7] - 1980) / 100
            return .65 * value + .35 * math.log1p(p[8][team])
        ordered = sorted(eligible, key=lambda p: (-fame(p), p[0]))
        answers = {}
        for i, player in enumerate(ordered):
            pid = player[0]
            fraction = i / max(1, len(ordered) - 1)
            estimate = 10 if fraction < .15 else 15 if fraction < .35 else 30 if fraction < .60 else 60 if fraction < .85 else 85
            editorial = connections.get((team, pid), min(original.get(pid, estimate), caps.get(pid, 100)))
            answers[pid] = (15 if kind == 'team' and pid in low_toi.get(team, []) else 10) if current.get(pid) == team else editorial
            players.setdefault(pid, [pid, player[1], player[9], []])
        active = sorted(pid for pid in answers if current.get(pid) == team)
        if not any(points == 100 for points in answers.values()):
            former = [p for p in ordered if current.get(p[0]) != team]
            gems = [p for p in former if p[4] >= 100 and p[8][team] >= 5] or former
            if not gems:
                raise ValueError(f"No former-player deep cut remains for {prompt['id']}")
            gem = max(gems, key=lambda p: (answers[p[0]], p[4], -p[0]))
            answers[gem[0]] = 100
        rows = sorted([pid, score] for pid, score in answers.items())
        depth = sorted(pid for pid in active if kind == 'team' and pid in low_toi.get(team, []))
        identity = f"dc{policy}-" + prompt["id"] + "-" + fingerprint({"answers": rows, "current": active, "depth": depth, "policy": policy})
        replacements[prompt["id"]] = identity
        if identity not in prompts:
            prompts[identity] = {**deepcopy(prompt), "id": identity, "version": 2, "base": prompt["id"],
                                 "asof": today.isoformat(), "currentRoster": active, "lowToiRoster": depth, "answers": rows,
                                 "note": f"Verified appearances through {source.get('grid_asof', source['asof'])}. Current roster: 10 points" + ("; six lowest average-TOI skaters: 15" if policy == 3 and kind == 'team' else '') + f". Snapshot {today.isoformat()}; former players count."}
    latest = []
    for template in base["runs"]:
        keys = [replacements.get(key, key) for key in template["prompts"]]
        identity = f"dc-v{policy}-" + template["id"].rsplit("-", 1)[1] + "-" + fingerprint(keys)
        latest.append(identity)
        runs.setdefault(identity, {"id": identity, "prompts": keys, "scoringVersion": policy})
    rollout = previous.get("rollout", {"daily_from": (today + timedelta(days=1)).isoformat()})
    result = {**base, "version": 2, "team_asof": source.get("grid_asof", source["asof"]), "roster_asof": today.isoformat(),
              "roster_snapshot": {str(pid): team for pid, team in sorted(current.items())},
              "toi_snapshot": toi_rows or [], "toi_season": toi_season, "low_toi_roster": low_toi, "active_policy": policy,
              "rollout": rollout, "practice_runs": latest, "current_prompts": replacements,
              "review_sha": fingerprint(review),
              "scoring": "Fixed editorial tiers with reviewed name-recognition and club-connection adjustments. Current-club players score 10, except the six lowest average-TOI current skaters for that club score 15. Goalies stay at 10. Historical shifts retain their original scores; this is not live answer popularity.",
              "players": list(players.values()), "prompts": list(prompts.values()), "runs": list(runs.values())}
    return validate(previous, result)


def plan_days(saved, data, today, ahead):
    """Keep today's/past runs fixed; use the latest roster edition for future days."""
    known = {run["id"] for run in data["runs"]}
    latest = set(data.get("practice_runs", known))
    if any(not isinstance(ref, dict) or ref.get("id") not in known for ref in saved.values()):
        raise ValueError("A published Deep Cut run is missing")
    days = {day: ref for day, ref in saved.items() if day <= today.isoformat() or ref["id"] in latest}
    for offset in range(ahead + 1):
        day = (today + timedelta(days=offset)).isoformat()
        if day in days:
            continue
        used = {ref["id"] for key, ref in days.items() if abs((date.fromisoformat(key) - date.fromisoformat(day)).days) < len(latest)}
        choices = sorted(latest - used) or sorted(latest)
        days[day] = {"id": random.Random("sweater-deepcut-" + day).choice(choices)}
    return dict(sorted(days.items()))
