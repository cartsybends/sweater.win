"""Official NHL skater game reports, compacted for chronological line forecasts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import calendar
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.cache/playoffs/lines'
API = 'https://api.nhle.com/stats/rest/en/'
KEEP = {
    'summary': ['gameId','gameDate','playerId','teamAbbrev','opponentTeamAbbrev',
                'positionCode','skaterFullName','goals','shots','timeOnIcePerGame'],
    'timeonice': ['gameId','playerId','timeOnIce','evTimeOnIce','ppTimeOnIce','shTimeOnIce'],
    'realtime': ['gameId','playerId','blockedShots'],
    'faceoffwins': ['gameId','playerId','totalFaceoffWins','totalFaceoffs'],
    'powerplay': ['gameId','gameDate','teamId','teamFullName','powerPlayGoalsFor','ppOpportunities'],
    'penaltykill': ['gameId','gameDate','teamId','teamFullName','ppGoalsAgainst','timesShorthanded'],
}


def get_json(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Sweater NHL analytics)', 'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def report_page(url):
    raw = get_json(url)
    rows, total = raw.get('data'), raw.get('total')
    if not isinstance(rows, list) or not isinstance(total, int) or total < len(rows):
        raise ValueError('Invalid NHL game report')
    return rows, total


def report(kind, report_name, season, first, last):
    path = CACHE / f'{kind}-{report_name}-{season}-{first}-{last}.json'
    fresh = season < current_season() or path.exists() and time.time()-path.stat().st_mtime < 900
    if path.exists() and fresh:
        data = json.loads(path.read_text())
        if data.get('version') == 1:
            return data['rows']
    expression = f'seasonId={season*10000+season+1} and gameTypeId=2 and gameDate>="{first}" and gameDate<="{last}"'
    endpoint = API + kind + '/' + report_name + '?'
    query = {'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':expression}
    url = endpoint + urllib.parse.urlencode(query)
    rows, total = report_page(url)
    if total >= 10000:
        a,b = date.fromisoformat(first),date.fromisoformat(last)
        if a >= b:
            raise ValueError(f'NHL {kind}/{report_name} report exceeds query limit on {first}')
        middle = a + (b-a)//2
        return report(kind,report_name,season,first,middle.isoformat()) + report(kind,report_name,season,(middle+timedelta(days=1)).isoformat(),last)
    if len(rows) < total:
        # Some reports return a short bulk response, even for a single date.
        # Restart with a stable order before advancing by the returned row count.
        identity = 'playerId' if kind == 'skater' else 'teamId'
        sort = json.dumps([{'property': key, 'direction': 'ASC'} for key in ('gameId', identity)])
        query.update(limit=1000, sort=sort)
        rows = []
        seen = set()
        while len(rows) < total:
            offset = len(rows)
            page_url = endpoint + urllib.parse.urlencode({**query, 'start': offset})
            page, count = report_page(page_url)
            keys = {(row.get('gameId'), row.get(identity)) for row in page}
            if count != total or not page or len(page) > total - offset or len(keys) != len(page) or keys & seen:
                raise ValueError(f'Incomplete NHL {kind}/{report_name} report for {first} to {last} at offset {offset} of {total}')
            rows.extend(page)
            seen.update(keys)
    rows = [{key:r.get(key) for key in KEEP[report_name]} for r in rows]
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'version':1,'source':url,'rows':rows},ensure_ascii=False,separators=(',',':')))
    temp.replace(path)
    return rows


def current_season():
    today = datetime.now(timezone.utc)
    return today.year if today.month >= 7 else today.year-1


def season_report(kind, name, season):
    today = datetime.now(timezone.utc).date()
    spans=[]
    # Filter by seasonId/gameType, not an assumed October opening night. The
    # longer 2026–27 regular season begins in September.
    for year,month in [(season,m) for m in range(7,13)]+[(season+1,m) for m in range(1,7)]:
        first=date(year,month,1)
        if first > today:
            continue
        last=min(date(year,month,calendar.monthrange(year,month)[1]),today)
        spans.append((kind,name,season,first.isoformat(),last.isoformat()))
    with ThreadPoolExecutor(max_workers=4) as pool:
        chunks=list(pool.map(lambda args:report(*args),spans))
    rows=[r for chunk in chunks for r in chunk]
    identities=[(r['gameId'],r.get('playerId',r.get('teamId'))) for r in rows]
    if len(identities)!=len(set(identities)):
        raise ValueError('Duplicate NHL game report rows')
    return rows


def skater_games(season, display_stats=False):
    summaries=season_report('skater','summary',season)
    usage={(r['gameId'],r['playerId']):r for r in season_report('skater','timeonice',season)}
    extra={name:{(r['gameId'],r['playerId']):r for r in season_report('skater',name,season)}
           for name in ('realtime','faceoffwins')} if display_stats else {}
    output=[]
    for s in summaries:
        key=(s['gameId'],s['playerId']);u=usage.get(key)
        if not u:
            raise ValueError('NHL scoring/ice-time report mismatch')
        if abs(s['timeOnIcePerGame']-u['timeOnIce'])>1:
            raise ValueError('NHL playing time does not reconcile')
        b=extra.get('realtime',{}).get(key,{});f=extra.get('faceoffwins',{}).get(key,{})
        output.append({'g':s['gameId'],'date':s['gameDate'][:10],'season':season,'p':s['playerId'],
          'team':s['teamAbbrev'],'opp':s['opponentTeamAbbrev'],'pos':s['positionCode'],
          'name':s['skaterFullName'],'goals':s['goals'],'shots':s['shots'],
          'seconds':u['timeOnIce'],'pp':u['ppTimeOnIce'],'ev':u['evTimeOnIce'],'pk':u['shTimeOnIce'],
          'blocks':b.get('blockedShots'),'fo_wins':f.get('totalFaceoffWins'),'fo_total':f.get('totalFaceoffs')})
    return sorted(output,key=lambda r:(r['date'],r['g'],r['team'],r['p']))


def audit(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first',type=int,default=2023)
    parser.add_argument('--last',type=int,default=current_season())
    args=parser.parse_args()
    for season in range(args.first,args.last+1):
        rows=skater_games(season,display_stats=season==args.last)
        path=CACHE/f'games-{season}.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
        print(season,len(rows),'player-games',audit(rows),flush=True)
