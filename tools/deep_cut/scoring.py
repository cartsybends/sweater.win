"""Append immutable prompt releases and current-roster scoring editions."""
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


def load_expansion():
    path = Path(__file__).resolve().parents[2] / 'static/deep-cut/expansion.json'
    return json.loads(path.read_text()) if path.exists() else None


def expanded_templates(prompts):
    """Balance all families and cover every question in a stable 365-set bank."""
    families = {}
    for prompt in prompts:
        families.setdefault(prompt['family'], []).append(prompt['id'])
    usage = dict.fromkeys((p['id'] for p in prompts), 0)
    family_usage = dict.fromkeys(families, 0)
    selected = []
    for i in range(365):
        rng = random.Random(f'sweater-deepcut-expanded-v1-{i}')
        choices = list(families)
        rng.shuffle(choices)
        choices.sort(key=lambda family: family_usage[family])
        keys = []
        for family in choices[:7]:
            options = list(families[family])
            rng.shuffle(options)
            key = min(options, key=lambda key: usage[key])
            usage[key] += 1
            family_usage[family] += 1
            keys.append(key)
        rng.shuffle(keys)
        selected.append(keys)
    if not all(usage.values()) or len({tuple(keys) for keys in selected}) != 365:
        raise ValueError('Expanded practice rotation does not cover the question bank')
    return selected


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
    expansion = load_expansion()
    templates = list(base['prompts'])
    if expansion:
        templates += expansion['prompts']
        for player in expansion['players']:
            players.setdefault(player[0], player)
        for prompt in expansion['prompts']:
            if prompt['id'] in prompts and prompts[prompt['id']] != prompt:
                raise ValueError('A published expansion prompt changed; release a new content identity')
            prompts.setdefault(prompt['id'], deepcopy(prompt))
            team = prompt.get('rosterTeam')
            if not team:
                replacements[prompt['id']] = prompt['id']
                continue
            active = sorted(pid for pid, _ in prompt['answers'] if current.get(pid) == team)
            depth = sorted(set(active) & set(low_toi.get(team, [])))
            rows = [[pid, (15 if pid in depth else 10) if pid in active else points] for pid, points in prompt['answers']]
            if not any(score == 100 for _, score in rows):
                former = [row for row in rows if row[0] not in active and row[0] not in caps]
                if not former: raise ValueError('No former player remains for a team-era prompt')
                max(former, key=lambda row: (row[1], source_players.get(row[0], [0,0,0,0,0])[4], -row[0]))[1] = 100
            identity = f'dc{policy}-' + prompt['id'] + '-' + fingerprint({'answers':rows, 'current':active, 'depth':depth, 'policy':policy})
            replacements[prompt['id']] = identity
            prompts.setdefault(identity, {**deepcopy(prompt), 'id':identity, 'base':prompt['id'], 'version':2,
                                          'currentRoster':active, 'lowToiRoster':depth, 'answers':rows, 'rosterAsOf':today.isoformat()})
    latest = []
    sets = expanded_templates(templates) if expansion else [template['prompts'] for template in base['runs']]
    for i, template in enumerate(sets):
        keys = [replacements.get(key, key) for key in template]
        identity = (f'dc-x1-v{policy}-' if expansion else f'dc-v{policy}-') + f'{i:03}-' + fingerprint(keys)
        latest.append(identity)
        runs.setdefault(identity, {"id": identity, "prompts": keys, "scoringVersion": policy, **({'contentVersion':1} if expansion else {})})
    rollout = previous.get("rollout", {"daily_from": (today + timedelta(days=1)).isoformat()})
    result = {**base, "version": 2, "team_asof": source.get("grid_asof", source["asof"]), "roster_asof": today.isoformat(),
              "roster_snapshot": {str(pid): team for pid, team in sorted(current.items())},
              "toi_snapshot": toi_rows or [], "toi_season": toi_season, "low_toi_roster": low_toi, "active_policy": policy,
              "rollout": rollout, "practice_runs": latest, "current_prompts": replacements,
              "review_sha": fingerprint(review),
              **({'content_asof':expansion['asof'], 'active_prompt_ids':[replacements.get(p['id'],p['id']) for p in templates],
                  'content_version':1, 'content_prompts':len(templates), 'content_families':len({p['family'] for p in templates})} if expansion else {}),
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
