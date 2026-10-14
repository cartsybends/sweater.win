"""Curate immutable Sweater puzzles from official NHL history and bios.

The checked-in bank is stable for archives. Rebuilding is an explicit action;
normal site builds validate it and keep scheduled puzzles unchanged.
"""
import argparse
from collections import defaultdict, deque
from datetime import date
import hashlib
import itertools
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'static/community-games/data.json'
TOTALS = ROOT / 'tools/community_games/season_totals.json'
CUTOFF = 2025


def group(pos):
    return 'G' if pos == 'G' else 'D' if pos == 'D' else 'F'


def optimum(cards, players, budget):
    groups = {k: [c for c in cards if group(c[8]) == k] for k in ('F', 'D', 'G')}
    best, lineup = -1, None
    for forwards in itertools.combinations(groups['F'], 3):
        for defense in itertools.combinations(groups['D'], 2):
            for goalie in groups['G']:
                picks = (*forwards, *defense, goalie)
                if sum(c[1] for c in picks) <= budget:
                    score = sum(c[2] for c in picks)
                    if score > best:
                        best, lineup = score, [c[0] for c in picks]
    return best, lineup


def shortest(adj, start, end):
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        if path[-1] == end:
            return path
        for neighbor in sorted(adj[path[-1]]):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(path + [neighbor])


def qualifies(player, clue):
    kind, value = clue['kind'], clue['value']
    if kind == 'team':
        return player[8].get(value, 0) > 0
    if kind == 'country':
        return player[3] == value
    if kind == 'position':
        return group(player[2]) == value
    if kind == 'games':
        return player[4] >= value
    if kind == 'hall':
        return player[5]
    return False


def build(history, bios, league):
    rng = random.Random(20261014)
    raw, seasons, team_games = {}, defaultdict(list), {}
    for team, data in history.items():
        for kind in ('s', 'g'):
            for r in data[kind]:
                pid, name = r[:2]
                pos, year, gp = (r[2], r[3], r[4]) if kind == 's' else ('G', r[2], r[3])
                if year > CUTOFF or not gp:
                    continue
                p = raw.setdefault(pid, {'name': name, 'pos': pos, 'first': year, 'last': year, 'teams': defaultdict(int)})
                p['first'], p['last'] = min(p['first'], year), max(p['last'], year)
                # A skater's emergency-goalie appearance is already in his
                # skater GP. Multiple role summaries must not count it twice.
                key = (pid, team, year)
                team_games[key] = max(team_games.get(key, 0), gp)
                if 1967 <= year <= CUTOFF and 0 < gp <= 84:
                    seasons[(team, year)].append((pid, gp))
    for (pid, team, year), gp in team_games.items():
        raw[pid]['teams'][team] += gp
    players = {}
    for pid, p in sorted(raw.items()):
        bio = bios[pid]
        players[pid] = [pid, p['name'], bio.get('positionCode', p['pos']), bio['birthCountryCode'],
                        int(bio['gamesPlayed']), bio.get('isInHallOfFameYn') == 'Y', p['first'], p['last'], dict(p['teams']), int(bio['birthDate'][:4])]

    # Each square has at least nine candidates. Consequently, any valid eight
    # distinct answers leave an unused candidate for the final square.
    teams = sorted(history)
    country_clues = [{'kind': 'country', 'value': c} for c in ('CAN', 'USA', 'SWE', 'FIN')]
    other_clues = country_clues + [{'kind': 'position', 'value': p} for p in ('F', 'D', 'G')] + [
        {'kind': 'games', 'value': 1000}, {'kind': 'hall', 'value': True}]
    grids, seen = [], set()
    for attempt in range(20000):
        rows = rng.sample(teams, 3)
        remaining = [t for t in teams if t not in rows]
        mixed = len(grids) % 2 == 1
        columns = ([{'kind': 'team', 'value': t} for t in rng.sample(remaining, 1)] + rng.sample(other_clues, 2)) if mixed else [
            {'kind': 'team', 'value': t} for t in rng.sample(remaining, 3)]
        key = json.dumps([rows, columns], sort_keys=True)
        if key in seen:
            continue
        if any(sum(p[8].get(team, 0) > 0 and qualifies(p, col) for p in players.values()) < 9 for team in rows for col in columns):
            continue
        seen.add(key)
        grids.append({'id': f'grid-{len(grids):03}', 'rows': rows, 'cols': columns})
        if len(grids) == 120:
            break
    assert len(grids) == 120

    # A conservative pigeonhole proof of real shared appearances: NHL seasons
    # in this era have at most 84 games. Combined GP >= 89 guarantees at least
    # five games in which both players appeared, even in trade seasons.
    eligible = {pid for pid, p in players.items() if p[4] >= 500 and p[7] >= 1990}
    edges = {}
    for (team, year), entries in seasons.items():
        entries = [(pid, gp) for pid, gp in entries if pid in eligible]
        for (a, ga), (b, gb) in itertools.combinations(entries, 2):
            if ga + gb < 89 or a == b:
                continue
            if a > b:
                a, b, ga, gb = b, a, gb, ga
            old = edges.get((a, b))
            proof = [a, b, team, year, ga, gb]
            if old is None or (ga + gb, year) > (old[4] + old[5], old[3]):
                edges[(a, b)] = proof
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b); adj[b].add(a)
    stars = sorted([pid for pid in adj if players[pid][4] >= 800 and players[pid][7] >= 2000])
    pairs, used = {2: [], 3: []}, set()
    for attempt in range(30000):
        start, end = rng.sample(stars, 2)
        key = tuple(sorted((start, end)))
        if key in used or end in adj[start]:
            continue
        path = shortest(adj, start, end)
        if path and len(path) - 1 in pairs:
            used.add(key); pairs[len(path) - 1].append({'start': start, 'end': end, 'solution': path})
        if len(pairs[2]) >= 240 and len(pairs[3]) >= 120:
            break
    assert len(pairs[2]) >= 240 and len(pairs[3]) >= 120
    trails = [{'id': f'trail-{i:03}', 'rounds': [pairs[2][i * 2], pairs[2][i * 2 + 1], pairs[3][i]]} for i in range(120)]

    # Fixed, completed seasons keep scoring and archives stable. Each market
    # has 9 forwards, 6 defensemen, and 3 goalies, with an exact legal optimum.
    clubs = {}
    for team, data in history.items():
        for kind in ('s', 'g'):
            for r in data[kind]:
                pid = r[0]
                year, gp = (r[3], r[4]) if kind == 's' else (r[2], r[3])
                if not 2005 <= year <= 2024 or pid not in players:
                    continue
                key = (year, pid)
                if key not in clubs or gp > clubs[key][1]:
                    clubs[key] = (team, gp)
    # League-wide summaries include games at retired franchises (ARI, ATL,
    # etc.). Adding only current-club histories would omit part of a traded
    # player's season. The badge is his largest current-club stint; totals
    # always come from the complete official league summary.
    by_year = defaultdict(dict)
    for year, rows in league['seasons'].items():
        year = int(year)
        for pid, pos, gp, goals, assists, wins in rows:
            if pid not in players or (year, pid) not in clubs:
                continue
            by_year[year][pid] = [pid, 0, 0, goals, assists, wins, clubs[(year, pid)][0], gp, pos]
    bosses, used_markets = [], set()
    for attempt in range(10000):
        year = rng.choice(sorted(by_year))
        groups = {k: [] for k in ('F', 'D', 'G')}
        for row in by_year[year].values():
            k = group(row[8])
            if row[7] >= (25 if k == 'G' else 40):
                row[2] = row[5] * 3 if k == 'G' else row[3] * 2 + row[4]
                groups[k].append(row)
        market = []
        for k, size in (('F', 9), ('D', 6), ('G', 3)):
            ordered = sorted(groups[k], key=lambda c: c[2], reverse=True)
            pool = ordered[:90 if k != 'G' else 30]
            selected = rng.sample(pool, size)
            if not any(c[0] in {r[0] for r in ordered[:8]} for c in selected):
                selected[0] = ordered[0]
            for row in selected:
                card = row[:9]
                card[1] = max(8, min(33, round(card[2] / 7) + 11 + rng.randint(-5, 5)))
                market.append(card)
        key = (year, tuple(sorted(c[0] for c in market)))
        par, best = optimum(market, players, 100)
        if key in used_markets or par <= 0 or not best:
            continue
        # At least two legal, meaningfully different lineups make this a game.
        if sum(c[1] for c in sorted(market, key=lambda c: c[2], reverse=True)[:6]) <= 100:
            continue
        used_markets.add(key)
        bosses.append({'id': f'boss-{len(bosses):03}', 'year': year, 'budget': 100, 'cards': market, 'par': par, 'optimal': best})
        if len(bosses) == 120:
            break
    assert len(bosses) == 120
    return {'version': 1, 'asof': date.today().isoformat(), 'team_cutoff': CUTOFF,
            'sources': ['https://api.nhle.com/stats/rest/en/skater/summary', 'https://api.nhle.com/stats/rest/en/goalie/summary',
                        'https://api.nhle.com/stats/rest/en/skater/bios', 'https://api.nhle.com/stats/rest/en/goalie/bios'],
            'players': list(players.values()), 'grid': grids, 'benchboss': bosses, 'teammatetrail': trails,
            'links': [edges[k] for k in sorted(edges)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bios-dir', type=Path)
    parser.add_argument('--league-dir', type=Path, help='Unmodified league-wide skater/goalie summary responses for 2005–2024')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--replace-bank', action='store_true', help='Explicitly replace a bank before its puzzle IDs have been published')
    args = parser.parse_args()
    if not args.bios_dir:
        parser.error('--bios-dir must contain the unmodified official skater-bios.json and goalie-bios.json responses')
    if args.out.exists() and not args.replace_bank:
        parser.error('This bank already exists. Published puzzle IDs must remain immutable; use a new output path.')
    history = json.loads((ROOT / 'team_history_cache.json').read_text())['teams']
    bios = {}
    for kind in ('skater', 'goalie'):
        for row in json.loads((args.bios_dir / (kind + '-bios.json')).read_text())['data']:
            record = {**row, 'positionCode': 'G'} if kind == 'goalie' else row
            old = bios.get(row['playerId'])
            if old is None or record['gamesPlayed'] > old['gamesPlayed']:
                bios[row['playerId']] = record
    if args.league_dir:
        league = {'source': 'https://api.nhle.com/stats/rest/en/{skater|goalie}/summary?isAggregate=true&isGame=false&start=0&limit=-1&cayenneExp=seasonId%3D{year}{year+1}%20and%20gameTypeId%3D2',
                  'seasons': {}, 'response_sha256': {}}
        for year in range(2005, 2025):
            rows = {}
            for kind in ('skater', 'goalie'):
                source = args.league_dir / f'{kind}-{year}.json'
                raw = json.loads(source.read_text())
                assert len(raw['data']) == raw['total']
                assert len({r['playerId'] for r in raw['data']}) == len(raw['data'])
                league['response_sha256'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
                for r in raw['data']:
                    pid, gp = r['playerId'], int(r['gamesPlayed'])
                    row = [pid, r.get('positionCode', 'G'), gp, int(r['goals']), int(r['assists']), int(r.get('wins', 0))]
                    # Keep a dual-role player's primary season summary.
                    if pid not in rows or gp > rows[pid][2]:
                        rows[pid] = row
            league['seasons'][str(year)] = [rows[pid] for pid in sorted(rows)]
        TOTALS.write_text(json.dumps(league, separators=(',', ':')) + '\n')
    league = json.loads(TOTALS.read_text())
    data = build(history, bios, league)
    data['league_sha256'] = hashlib.sha256(TOTALS.read_bytes()).hexdigest()
    data['history_sha256'] = hashlib.sha256((ROOT / 'team_history_cache.json').read_bytes()).hexdigest()
    data['bios_sha256'] = {kind: hashlib.sha256((args.bios_dir / (kind + '-bios.json')).read_bytes()).hexdigest() for kind in ('skater', 'goalie')}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print('Curated:', len(data['players']), 'players,', len(data['links']), 'verified teammate links, and 120 puzzles per mode.')


if __name__ == '__main__':
    main()
