"""Listed MoneyPuck downloads, NHL rosters and dated availability observations.

Sweater is non-commercial. MoneyPuck.com must be credited in displayed outputs.
No MoneyPuck predictions, rankings or unlisted endpoints are scraped.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import subprocess
import tempfile
import unicodedata
import urllib.parse
import zipfile

from data import CACHE, TEAMS, canonical as nhl_canonical

TEAM_URL = 'https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv'
UPDATE_URL = 'https://moneypuck.com/moneypuck/playerData/seasonSummary/update_date.txt'
GOALIE_URL = 'https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary/goalies/{year}.zip'
INJURY_URL = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries'
BIO_URL = 'https://moneypuck.com/moneypuck/playerData/playerBios/allPlayersLookup.csv'
VECTOR = ['gf','ga','xf','xa','even_xf','even_xa','even_seconds','pp_xf','pp_seconds','pk_xa','pk_seconds']
NAMES = {'New York Rangers':'NYR','New York Islanders':'NYI','New Jersey Devils':'NJD','Los Angeles Kings':'LAK',
         'San Jose Sharks':'SJS','Tampa Bay Lightning':'TBL','Utah Mammoth':'UTA','Utah Hockey Club':'UTA',
         'Washington Capitals':'WSH','Montréal Canadiens':'MTL','Montreal Canadiens':'MTL'}


def canonical(team):
    return nhl_canonical({'S.J':'SJS','L.A':'LAK','N.J':'NJD','T.B':'TBL','PHX':'ARI'}.get(team,team))


def normalized(name):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKD', name) if c.isalnum())


def number(row, key):
    value = float(row[key])
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid MoneyPuck '+key)
    return value


def parse_teams(stream, first):
    rows = {}
    for r in csv.DictReader(stream):
        year = int(r['season']);gid = int(r['gameId']);team = canonical(r['playerTeam'])
        if year < first or str(gid)[4:6] != '02' or team not in TEAMS:
            continue
        key = (gid, team)
        if key not in rows:
            day = datetime.strptime(r['gameDate'], '%Y%m%d').date().isoformat()
            rows[key] = {'g':gid,'s':year,'d':day,'t':team,'o':canonical(r['opposingTeam']), 'v':[None]*len(VECTOR)}
        vector = rows[key]['v']
        state = r['situation']
        if state == 'all':
            vector[:4] = [number(r,k) for k in ['goalsFor','goalsAgainst','flurryScoreVenueAdjustedxGoalsFor','flurryScoreVenueAdjustedxGoalsAgainst']]
        elif state == '5on5':
            vector[4:7] = [number(r,k) for k in ['flurryScoreVenueAdjustedxGoalsFor','flurryScoreVenueAdjustedxGoalsAgainst','iceTime']]
        elif state == '5on4':
            vector[7:9] = [number(r,k) for k in ['flurryScoreVenueAdjustedxGoalsFor','iceTime']]
        elif state == '4on5':
            vector[9:11] = [number(r,k) for k in ['flurryScoreVenueAdjustedxGoalsAgainst','iceTime']]
    output = sorted(rows.values(), key=lambda r:(r['d'],r['g'],r['t']))
    if not output or any(None in r['v'] for r in output):
        raise ValueError('Incomplete MoneyPuck team situations')
    pairs = {}
    for r in output:
        pairs.setdefault(r['g'],[]).append(r)
    for pair in pairs.values():
        if len(pair)!=2 or pair[0]['t']!=pair[1]['o'] or pair[0]['o']!=pair[1]['t'] or pair[0]['d']!=pair[1]['d'] or abs(pair[0]['v'][0]-pair[1]['v'][1])>.003:
            raise ValueError('MoneyPuck team rows do not reconcile')
    return output


def parse_goalies(stream, year):
    rows = []
    for r in csv.DictReader(stream):
        if r['situation']!='all' or str(r['gameId'])[4:6]!='02':
            continue
        seconds=number(r,'icetime')
        if seconds<=0:
            continue
        rows.append({'g':int(r['gameId']),'s':int(r['season']),'d':datetime.strptime(r['gameDate'],'%Y%m%d').date().isoformat(),
                     't':canonical(r['playerTeam']),'p':int(r['playerId']),'n':r['name'],'m':seconds,
                     'x':number(r,'flurryAdjustedxGoals'),'a':number(r,'goals')})
    if not rows or any(r['s']!=year for r in rows):
        raise ValueError('Invalid MoneyPuck goalie season')
    return sorted(rows,key=lambda r:(r['d'],r['g'],r['p']))


def download(url, path):
    # curl is a standard client supported by the explicitly listed download hosts.
    subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time','45','--max-filesize','350000000',url,'--output',str(path)],check=True,timeout=50)


def load_inputs(start):
    directory=CACHE/'advanced';directory.mkdir(parents=True,exist_ok=True)
    target=directory/'compact.json';prior=json.loads(target.read_text()) if target.exists() else None
    try:
        with tempfile.TemporaryDirectory(prefix='sweater-mp-') as folder:
            tmp=Path(folder);download(UPDATE_URL,tmp/'revision.txt');revision=(tmp/'revision.txt').read_text().strip()
            datetime.fromisoformat(revision)
            if prior and prior.get('version')==2 and prior.get('start')==start and prior.get('revision')==revision:
                return prior
            download(TEAM_URL,tmp/'teams.csv')
            with (tmp/'teams.csv').open(newline='',encoding='utf-8-sig') as f:
                teams=parse_teams(f,start-3)
            def goalies(year):
                cache=directory/f'goalies-{year}.json'
                if year<start and cache.exists():
                    cached=json.loads(cache.read_text())
                    if cached and 'st' in cached[0]:
                        return cached
                path=tmp/f'{year}.zip';download(GOALIE_URL.format(year=year),path)
                with zipfile.ZipFile(path) as archive:
                    members=[r for r in archive.infolist() if r.filename.endswith('.csv')]
                    if len(members)!=1 or members[0].file_size>40000000:
                        raise ValueError('Unexpected goalie archive')
                    with archive.open(members[0]) as f:
                        rows=parse_goalies(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''),year)
                official=tmp/f'official-{year}.json'
                query=urllib.parse.urlencode({'isAggregate':'false','isGame':'true','start':0,'limit':-1,'cayenneExp':f'gameTypeId=2 and seasonId={year}{year+1}'})
                download('https://api.nhle.com/stats/rest/en/goalie/summary?'+query,official)
                raw=json.loads(official.read_text())
                if len(raw['data'])!=raw['total']:
                    raise ValueError('Incomplete official goalie statistics')
                index={(r['gameId'],r['playerId']):r for r in raw['data']}
                for r in rows:
                    o=index.get((r['g'],r['p']))
                    if not o or canonical(o['teamAbbrev'])!=r['t']:
                        raise ValueError('Goalie history does not reconcile with NHL')
                    r.update(st=int(o['gamesStarted']),w=int(o['wins']),q=int(o['shotsAgainst']))
                cache.write_text(json.dumps(rows,separators=(',',':'))+'\n')
                return rows
            goalie_rows=[]
            with ThreadPoolExecutor(max_workers=3) as pool:
                for batch in pool.map(goalies,range(start-3,start+1)):
                    goalie_rows.extend(batch)
            download(BIO_URL,tmp/'bios.csv')
            with (tmp/'bios.csv').open(newline='',encoding='utf-8-sig') as f:
                births={r['playerId']:r['birthDate'] for r in csv.DictReader(f) if r.get('birthDate')}
            result={'version':2,'start':start,'revision':revision,'teams':teams,'goalies':goalie_rows,'births':births,'source':TEAM_URL}
            result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(result,separators=(',',':'))+'\n');temporary.replace(target)
            return result
    except Exception:
        if prior and prior.get('version')==2 and prior.get('start')==start:
            return prior
        raise


def goalie_statistics(season, now, fetch=None):
    """Official season totals; unavailable values never become invented statistics."""
    query=urllib.parse.urlencode({'isAggregate':'false','isGame':'false','start':0,'limit':-1,
                                 'cayenneExp':f'gameTypeId=2 and seasonId={season}'})
    url='https://api.nhle.com/stats/rest/en/goalie/summary?'+query
    directory=CACHE/'advanced';directory.mkdir(parents=True,exist_ok=True)
    target=directory/f'goalie-totals-{season}.json'
    try:
        if fetch:
            raw=fetch(url)
        else:
            with tempfile.TemporaryDirectory(prefix='sweater-goalies-') as folder:
                path=Path(folder)/'totals.json';download(url,path);raw=json.loads(path.read_text())
        if not raw['data'] or len(raw['data'])!=raw['total']:
            raise ValueError('Incomplete official goalie totals')
        players={}
        for r in raw['data']:
            pid=r['playerId'];gp=r['gamesPlayed'];gs=r['gamesStarted'];sv=r.get('savePct');gaa=r.get('goalsAgainstAverage')
            if (r['seasonId']!=season or type(pid) is not int or pid in players or type(gp) is not int or type(gs) is not int or not 0<=gs<=gp<=100
                or sv is not None and (not math.isfinite(sv) or not 0<=sv<=1)
                or gaa is not None and (not math.isfinite(gaa) or not 0<=gaa<=3600)):
                raise ValueError('Invalid official goalie totals')
            players[pid]={'gp':gp,'gs':gs,'sv':sv,'gaa':gaa}
        result={'season':season,'as_of':now,'status':'reported','players':players}
        temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(result));temporary.replace(target)
        return result
    except Exception:
        if target.exists():
            saved=json.loads(target.read_text());saved['status']='cached'
            return saved
        return {'season':season,'as_of':None,'status':'unavailable','players':{}}


def availability(teams, fetch, now):
    """Report source observations and only resolve unambiguous NHL player identities."""
    directory=CACHE/'advanced';directory.mkdir(parents=True,exist_ok=True)
    rosters={}
    def roster(team):
        path=directory/f'roster-{team}.json'
        cached=json.loads(path.read_text()) if path.exists() else None
        if cached and cached.get('day')==now[:10]:
            return team,cached['players']
        try:
            raw=fetch(f'https://api-web.nhle.com/v1/roster/{team}/current')
            players=[{'id':p['id'],'name':p['firstName']['default']+' '+p['lastName']['default'],'position':key} for key in ['forwards','defensemen','goalies'] for p in raw[key]]
            if not any(p['position']=='goalies' for p in players):
                raise ValueError('No rostered goalie')
            path.write_text(json.dumps({'day':now[:10],'players':players}))
            return team,players
        except Exception:
            return team,cached['players'] if cached else []
    with ThreadPoolExecutor(max_workers=6) as pool:
        rosters=dict(pool.map(roster,TEAMS))
    names={t['name']:t['abbr'] for t in teams};names.update(NAMES)
    known={team:{normalized(p['name']):p for p in players} for team,players in rosters.items()}
    injuries={team:[] for team in TEAMS};status='unavailable';reported=None
    try:
        raw=fetch(INJURY_URL);reported=raw.get('timestamp')
        observed=datetime.fromisoformat(reported.replace('Z','+00:00'))
        age=(datetime.fromisoformat(now.replace('Z','+00:00'))-observed).total_seconds()
        if age>86400 or age< -300:
            raise ValueError('Injury report is stale')
        for group in raw['injuries']:
            team=names.get(group.get('displayName'))
            if not team:
                continue
            for injury in group.get('injuries',[]):
                athlete=injury.get('athlete',{});name=athlete.get('displayName','')
                if not isinstance(name,str) or not name or len(name)>100:
                    continue
                player=known[team].get(normalized(name));injury_status=injury.get('status','Unknown')
                if not isinstance(injury_status,str) or len(injury_status)>50:
                    injury_status='Unknown'
                injuries[team].append({'player_id':player['id'] if player else None,'name':name,'position':athlete.get('position',{}).get('abbreviation',''),
                   'status':injury_status,'reported_at':injury.get('date'),'return_estimate':injury.get('details',{}).get('returnDate')})
        status='reported'
        (directory/'injuries.json').write_text(json.dumps({'reported_at':reported,'injuries':injuries},separators=(',',':')))
    except Exception:
        cached=directory/'injuries.json'
        if cached.exists():
            try:
                saved=json.loads(cached.read_text());reported=saved['reported_at'];injuries=saved['injuries']
                age=(datetime.fromisoformat(now.replace('Z','+00:00'))-datetime.fromisoformat(reported.replace('Z','+00:00'))).total_seconds()
                status='cached' if 0<=age<=86400 else 'stale'
            except (KeyError,ValueError,TypeError):
                status='unavailable'
    return {'rosters':rosters,'injuries':injuries,'status':status,'reported_at':reported,'source':'ESPN','observed_at':now}
