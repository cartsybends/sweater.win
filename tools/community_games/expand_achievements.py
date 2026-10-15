"""Append verified Cup/season-goal grids, preserving every published puzzle.

Inputs are unmodified NHL award-details and skater/summary responses. Fetch
URLs are recorded in grid_achievements.json alongside their response hashes.
"""
import argparse
import hashlib
import json
import random
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

from build_data import qualifies

ROOT = Path(__file__).resolve().parents[2]


def source_snapshot(input_dir, cutoff):
    cup_path = input_dir / 'cup-awards.json'
    goals_path = input_dir / 'goals-seasons.json'
    cups = json.loads(cup_path.read_text())
    goals = json.loads(goals_path.read_text())
    assert len(cups['data']) == cups['total']
    assert len(goals['data']) == goals['total']
    end = int(f'{cutoff}{cutoff+1}')
    winners = {}
    for row in cups['data']:
        if row['status'] != 'WINNER' or row['seasonId'] > end:
            continue
        season = row['seasonId']
        if row['playerId']:
            winners[season, row['playerId']] = row['fullName']
        elif season >= 20232024:
            # Recent individual award rows are incomplete. The NHL's winner
            # summaries explicitly list engraved players, including exceptions.
            # Restrict links to the names section: never infer wins from team
            # membership or include opposition players mentioned in the recap.
            summary = row.get('summary') or ''
            marker = summary.find('Names on the Stanley Cup')
            assert marker >= 0, season
            for href, name in re.findall(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', summary[marker:], re.S):
                match = re.search(r'https?://www\.nhl\.com/(?:[^/]+/)?player/(?:[^/]*-)?(\d{7})$', unescape(href))
                if match:
                    winners[season, int(match[1])] = unescape(re.sub('<[^>]*>', '', name))
    expected = {int(f'{y}{y+1}') for y in range(1917, cutoff+1) if y not in (1918, 2004)}
    assert {season for season, pid in winners} == expected
    goal_rows = sorted([r['playerId'], r['seasonId'], r['goals'], r['teamAbbrevs']] for r in goals['data'] if r['seasonId'] <= end)
    assert len({(r[0], r[1]) for r in goal_rows}) == len(goal_rows)
    assert all(r[2] >= 30 for r in goal_rows)
    crosschecks = []
    for path in sorted((input_dir / 'landing').glob('*.json')):
        raw = path.read_bytes()
        player = json.loads(raw)
        seasons = sorted(s['seasonId'] for a in player.get('awards', []) if a['trophy']['default'] == 'Stanley Cup' for s in a['seasons'] if s['seasonId'] <= end)
        actual = sorted(season for season, pid in winners if pid == player['playerId'])
        assert actual == seasons, (player['playerId'], actual, seasons)
        crosschecks.append({'id': player['playerId'], 'seasons': seasons, 'sha256': hashlib.sha256(raw).hexdigest()})
    return {
        'through': cutoff,
        'sources': {
            'cup': {'url': 'https://records.nhl.com/site/api/award-details?' + urlencode({'cayenneExp': f'trophyId=1 and seasonId<={end}', 'limit': -1, 'sort': 'seasonId', 'dir': 'ASC'}), 'sha256': hashlib.sha256(cup_path.read_bytes()).hexdigest()},
            'season_goals': {'url': 'https://api.nhle.com/stats/rest/en/skater/summary?' + urlencode({'isAggregate': 'false', 'isGame': 'false', 'start': 0, 'limit': -1, 'cayenneExp': f'goals>=30 and gameTypeId=2 and seasonId<={end}', 'sort': '[{"property":"playerId","direction":"ASC"},{"property":"seasonId","direction":"ASC"}]'}), 'sha256': hashlib.sha256(goals_path.read_bytes()).hexdigest()},
        },
        'cup_rows': [[season, pid, name] for (season, pid), name in sorted(winners.items())],
        'cup_crosschecks': crosschecks,
        'season_goal_rows': goal_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--count', type=int, default=48)
    args = parser.parse_args()
    path = ROOT / 'static/community-games/data.json'
    data = json.loads(path.read_text())
    assert args.count >= 2
    source = ROOT / 'tools/community_games/grid_achievements.json'
    snapshot = source_snapshot(args.input_dir, data['team_cutoff'])
    source.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')) + '\n')
    players = data['players']
    player_ids = {p[0] for p in players}
    cup_ids = {r[1] for r in snapshot['cup_rows']} & player_ids
    peak = {}
    for pid, season, goals, teams in snapshot['season_goal_rows']:
        if pid in player_ids:
            peak[str(pid)] = max(peak.get(str(pid), 0), goals)
    data['cup_winners'] = sorted(cup_ids)
    data['season_goals'] = peak
    data['achievements_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    data['sources'] += [s['url'] for s in snapshot['sources'].values() if s['url'] not in data['sources']]
    existing = list(data['grid'])
    seen = {json.dumps([t['rows'], t['cols']], sort_keys=True) for t in existing}
    teams = sorted({t for p in players for t in p[8]})
    new_clues = [{'kind': 'trophy', 'value': 'Stanley Cup'}, {'kind': 'season_goals', 'value': 30}]

    def match(p, c):
        if c['kind'] == 'trophy':
            return p[0] in cup_ids if c['value'] == 'Stanley Cup' else c['value'] in data['awards'].get(str(p[0]), [])
        if c['kind'] == 'season_goals':
            return peak.get(str(p[0]), 0) >= c['value']
        return qualifies(p, c)

    eligible = [[t for t in teams if sum(t in p[8] and match(p, c) for p in players) >= 9] for c in new_clues]
    rng = random.Random('sweater-grid-cup-goals-2026')
    for added in range(args.count):
        feature = added % 2
        for _ in range(30000):
            rows = rng.sample(eligible[feature], 3)
            other = [{'kind': 'team', 'value': t} for t in teams if t not in rows] + [{'kind': 'country', 'value': c} for c in ['CAN', 'USA', 'SWE', 'FIN']] + [{'kind': 'position', 'value': v} for v in ['F', 'D', 'G']] + [{'kind': 'games', 'value': 1000}, new_clues[1-feature]]
            cols = [new_clues[feature], *rng.sample(other, 2)]
            rng.shuffle(cols)
            key = json.dumps([rows, cols], sort_keys=True)
            if key in seen or any(sum(team in p[8] and match(p, c) for p in players) < 9 for team in rows for c in cols):
                continue
            seen.add(key)
            data['grid'].append({'id': f'grid-{len(data["grid"]):03}', 'rows': rows, 'cols': cols})
            break
        else:
            raise ValueError('Not enough verified boards')
    assert data['grid'][:len(existing)] == existing
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Appended {args.count} grids; {len(cup_ids)} Cup winners and {len(peak)} 30-goal scorers in the catalog')


if __name__ == '__main__':
    main()
