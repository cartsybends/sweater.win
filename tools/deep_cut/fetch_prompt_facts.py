"""Fetch official NHL facts for an explicit, frozen Deep Cut content release."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo


def collect(fetch, today):
    year = today.year if today.month >= 7 else today.year - 1
    season = year * 10000 + year + 1
    jobs = [(kind, report) for kind in ('skater', 'goalie') for report in ('summary', 'bios')]
    def request(job):
        kind, report = job
        params = {'isAggregate': 'true' if report == 'bios' else 'false', 'isGame': 'false', 'start': 0, 'limit': -1,
                  'cayenneExp': f'gameTypeId=2 and seasonId<={season}'}
        url = f'https://api.nhle.com/stats/rest/en/{kind}/{report}?' + urllib.parse.urlencode(params)
        document, audit = fetch(kind + '-' + report + '.json', url)
        if len(document['data']) != document['total']:
            raise ValueError('Incomplete official NHL facts response')
        return kind, report, document['data'], audit
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, jobs))
    bios, seasons, sources = {}, {}, []
    for kind, report, records, audit in results:
        sources.append(audit)
        seen = set()
        for record in records:
            pid = record['playerId']
            if report == 'bios':
                if pid not in bios or kind == 'skater': bios[pid] = record
                continue
            season_id, gp = record['seasonId'], record['gamesPlayed']
            if (pid, season_id) in seen or type(gp) is not int or not 0 < gp < 100 or season_id > season:
                raise ValueError('Invalid or duplicate NHL player-season fact')
            seen.add((pid, season_id))
            clubs = [club.strip() for club in record['teamAbbrevs'].split(',')]
            key = (pid, season_id)
            row = seasons.setdefault(key, [pid, season_id, [], 0, 0, 0, 0, 0, 0, 0])
            row[2] = sorted(set(row[2]) | set(clubs));row[3] = max(row[3], gp)
            if kind == 'skater': row[4:8] = [record.get(k, 0) or 0 for k in ('goals', 'assists', 'points', 'penaltyMinutes')]
            else: row[8:10] = [record.get(k, 0) or 0 for k in ('wins', 'shutouts')]
    played = {key[0] for key in seasons}
    if not played <= bios.keys(): raise ValueError('An NHL player is missing biographical evidence')
    teams_url = 'https://api.nhle.com/stats/rest/en/team'
    teams, audit = fetch('teams.json', teams_url);sources.append(audit)
    return {'version': 1, 'asof': today.isoformat(), 'through_season': season,
            'sources': sources, 'bio': {str(pid): bios[pid] for pid in sorted(played)},
            'seasons': [seasons[key] for key in sorted(seasons)], 'teams': teams['data'],
            'season_columns': ['id', 'season', 'clubs', 'gp', 'goals', 'assists', 'points', 'pim', 'wins', 'shutouts']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--responses', type=Path)
    args = parser.parse_args()
    def fetch(name, url):
        path = args.responses / name if args.responses else None
        if path and path.exists(): raw = path.read_bytes()
        else:
            request = urllib.request.Request(url, headers={'User-Agent': 'Sweater NHL prompt fact verification'})
            with urllib.request.urlopen(request, timeout=120) as response: raw = response.read()
            if path: path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(raw)
        return json.loads(raw), {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
    data = collect(fetch, datetime.now(ZoneInfo('America/New_York')).date())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print('Verified NHL facts:', len(data['bio']), 'players,', len(data['seasons']), 'player-seasons.')
    print('Available bio fields:', ', '.join(sorted(set().union(*(record.keys() for record in data['bio'].values())))))


if __name__ == '__main__': main()
