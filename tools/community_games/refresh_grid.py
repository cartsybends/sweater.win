"""Refresh Grid eligibility from played NHL games without rebuilding puzzle banks."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'grid_current_cache.json'


def appearance_rows(summaries, get_log, cutoff, through):
    """Split traded seasons using actual game logs; never assign combined GP to each club."""
    appearances = {}
    for kind, summary in summaries.items():
        if len(summary['data']) != summary['total']:
            raise ValueError('Incomplete NHL summary response')
        seen = set()
        for row in summary['data']:
            pid, season, gp = row['playerId'], row['seasonId'], row['gamesPlayed']
            year = season // 10000
            if not cutoff < year <= through or season != year * 10000 + year + 1:
                raise ValueError('Unexpected NHL season')
            if (pid, season) in seen or type(gp) is not int or not 0 < gp <= 84:
                raise ValueError('Duplicate or invalid NHL appearance summary')
            seen.add((pid, season))
            teams = row['teamAbbrevs'].split(',')
            if not teams or len(set(teams)) != len(teams) or any(not re.fullmatch('[A-Z]{3}', t) for t in teams):
                raise ValueError('Invalid NHL club abbreviations')
            if len(teams) == 1:
                counts = {teams[0]: gp}
            else:
                log = get_log(pid, season)
                games = log['gameLog']
                if log.get('playerId', pid) != pid or len(games) != gp or len({g['gameId'] for g in games}) != gp:
                    raise ValueError('Incomplete or mismatched NHL trade-season game log')
                counts = Counter(g['teamAbbrev'] for g in games)
                if set(counts) != set(teams):
                    raise ValueError('NHL game log disagrees with trade-season clubs')
            for team, games in counts.items():
                key = (pid, team, year)
                # Emergency goalie appearances must not duplicate skater GP.
                appearances[key] = max(appearances.get(key, 0), games)
    return [[pid, team, year, gp] for (pid, team, year), gp in sorted(appearances.items())]


def updated_players(bank, appearances, bios):
    base = {p[0]: p for p in bank['players']}
    teams = {team for p in base.values() for team in p[8]}
    extra = defaultdict(dict)
    years = defaultdict(list)
    for pid, team, year, gp in appearances:
        if team in teams:
            extra[pid][team] = extra[pid].get(team, 0) + gp
            years[pid].append(year)
    result = []
    for pid, played in sorted(extra.items()):
        bio = bios[pid]
        previous = base.get(pid)
        clubs = dict(previous[8]) if previous else {}
        for team, gp in played.items():
            clubs[team] = clubs.get(team, 0) + gp
        career_gp = bio['gamesPlayed']
        if type(career_gp) is not int or career_gp < sum(clubs.values()):
            raise ValueError(f'Career GP does not cover verified NHL appearances for {pid}')
        row = [pid, bio.get('skaterFullName') or bio.get('goalieFullName'),
               bio['positionCode'], bio['birthCountryCode'], career_gp,
               bio.get('isInHallOfFameYn') == 'Y',
               previous[6] if previous else min(years[pid]), max(years[pid]), clubs,
               int(bio['birthDate'][:4])]
        if not row[1] or row[2] not in ('C', 'L', 'R', 'D', 'G') or not re.fullmatch('[A-Z]{3}', row[3]):
            raise ValueError('Invalid NHL player bio')
        result.append(row)
    return result


def attach_updates(bank, snapshot):
    """Validate persisted facts before embedding the identical browser/server catalog."""
    raw = json.dumps(bank, ensure_ascii=False, separators=(',', ':')).encode()
    if (snapshot.get('version') != 1 or snapshot['base_team_cutoff'] != bank['team_cutoff']
            or snapshot['bank_sha256'] != hashlib.sha256(raw).hexdigest()):
        raise ValueError('Grid update snapshot does not match the immutable bank')
    cutoff, through = bank['team_cutoff'], snapshot['season_through']
    seen = set()
    for pid, team, year, gp in snapshot['appearances']:
        if (pid, team, year) in seen or not cutoff < year <= through or type(gp) is not int or not 0 < gp <= 84:
            raise ValueError('Invalid persisted NHL appearance')
        seen.add((pid, team, year))
    bios = {p[0]: {'skaterFullName': p[1], 'positionCode': p[2], 'birthCountryCode': p[3],
                  'gamesPlayed': p[4], 'isInHallOfFameYn': 'Y' if p[5] else 'N',
                  'birthDate': str(p[9]) + '-01-01'} for p in snapshot['players']}
    if len(bios) != len(snapshot['players']) or updated_players(bank, snapshot['appearances'], bios) != snapshot['players']:
        raise ValueError('Grid player updates disagree with verified appearance totals')
    date.fromisoformat(snapshot['asof'])
    players = {p[0]: p for p in bank['players']}
    players.update({p[0]: p for p in snapshot['players']})
    # Preserve the existing catalog schema so already deployed scoring workers
    # accept the same fresh facts as the browser without a coordinated rollout.
    return {**bank, 'players': list(players.values()), 'grid_asof': snapshot['asof']}


def refresh(bank, today, fetch):
    cutoff = bank['team_cutoff']
    through = today.year if today.month >= 7 else today.year - 1
    sources = []

    def request(kind, report):
        params = {'isAggregate': 'false' if report == 'summary' else 'true',
                  'isGame': 'false', 'start': 0, 'limit': -1, 'cayenneExp': 'gameTypeId=2'}
        if report == 'summary':
            params['cayenneExp'] += f' and seasonId>={cutoff + 1}{cutoff + 2} and seasonId<={through}{through + 1}'
        url = f'https://api.nhle.com/stats/rest/en/{kind}/{report}?' + urllib.parse.urlencode(params)
        document, audit = fetch(f'{kind}-{report}.json', url)
        if len(document['data']) != document['total']:
            raise ValueError('Incomplete NHL response')
        return kind, report, document, audit

    jobs = [(kind, report) for kind in ('skater', 'goalie') for report in ('summary', 'bios')]
    bios, summaries = {}, {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda pair: request(*pair), jobs))
    for kind, report, document, audit in results:
        sources.append(audit)
        if report == 'summary':
            summaries[kind] = document
        else:
            for row in document['data']:
                row = {**row, 'positionCode': 'G'} if kind == 'goalie' else row
                if row['playerId'] not in bios or row['gamesPlayed'] > bios[row['playerId']]['gamesPlayed']:
                    bios[row['playerId']] = row

    def get_log(pid, season):
        document, audit = fetch(f'log-{pid}-{season}.json',
            f'https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2')
        sources.append(audit)
        return document

    appearances = appearance_rows(summaries, get_log, cutoff, through)
    snapshot = {'version': 1, 'asof': today.isoformat(), 'base_team_cutoff': cutoff,
                'season_through': through,
                'bank_sha256': hashlib.sha256(json.dumps(bank, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
                'sources': sources, 'appearances': appearances,
                'players': updated_players(bank, appearances, bios)}
    attach_updates(bank, snapshot)
    return snapshot


def preserve_verified_connections(previous, current):
    known = {(pid, team, year) for pid, team, year, gp in previous['appearances']
             if year > current['base_team_cutoff']}
    incoming = {(pid, team, year) for pid, team, year, gp in current['appearances']}
    if not known <= incoming:
        raise ValueError('NHL response would remove previously verified club appearances; preserving the last good snapshot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--responses', type=Path, help='Explicit response directory for reproducible offline review')
    parser.add_argument('--out', type=Path, default=OUTPUT)
    args = parser.parse_args()

    def fetch(name, url):
        path = args.responses / name if args.responses else None
        if path and path.exists():
            raw = path.read_bytes()
        else:
            request = urllib.request.Request(url, headers={'User-Agent': 'Sweater Grid official NHL appearance verification'})
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        return json.loads(raw), {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}

    bank = json.loads((ROOT / 'static/community-games/data.json').read_text())
    snapshot = refresh(bank, datetime.now(ZoneInfo('America/New_York')).date(), fetch)
    if args.out.exists():
        preserve_verified_connections(json.loads(args.out.read_text()), snapshot)
    temporary = args.out.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(args.out)
    print(f"Grid refreshed through {snapshot['asof']}: {len(snapshot['players'])} players, {len(snapshot['appearances'])} verified club-season records.")


if __name__ == '__main__':
    main()
