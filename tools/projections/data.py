"""Official current-season skater totals and club GP for the projections tool."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import urllib.parse,urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'projections_cache.json'
TEAMS=set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split())

def season_start(today):return today.year if today.month>=7 else today.year-1

def validate(data):
    assert data['version']==1 and data['season']==data['start']*10000+data['start']+1
    assert set(data['team_games'])==TEAMS and all(type(gp)is int and 0<=gp<=100 for gp in data['team_games'].values())
    ids=set()
    for p in data['players']:
        assert type(p['id'])is int and p['id'] not in ids and p['name'] and p['pos'] in ['C','L','R','D']
        assert all(type(p[k])is int and 0<=p[k]<=1000 for k in ['gp','goals','assists','points']) and p['gp']<=100
        assert p['points']==p['goals']+p['assists'] and (p['gp']>0 or p['points']==0)
        assert p['team'] is None or p['team'] in TEAMS
        assert p['teamGP']==(data['team_games'].get(p['team']) if p['team'] else None)
        ids.add(p['id'])
    assert len(ids)>=500
    return data

def collect(fetch,roster,today):
    start=season_start(today);season=start*10000+start+1
    url='https://api.nhle.com/stats/rest/en/skater/summary?'+urllib.parse.urlencode({'isAggregate':'false','isGame':'false','start':0,'limit':-1,'cayenneExp':f'seasonId={season} and gameTypeId=2'})
    standings_url='https://api-web.nhle.com/v1/standings/now'
    with ThreadPoolExecutor(max_workers=2) as pool:summary,standings=list(pool.map(fetch,[url,standings_url]))
    if len(summary['data'])!=summary['total'] or len(summary['data'])>=10000:raise ValueError('Incomplete NHL skater summary')
    teams={r['teamAbbrev']['default']:r['gamesPlayed'] for r in standings['standings']}
    if set(teams)!=TEAMS or any(r.get('seasonId',season)!=season for r in standings['standings']):raise ValueError('Club games are not a complete current-season snapshot')
    current={p['id']:p for p in roster if p.get('pos')!='G'}
    records={}
    for r in summary['data']:
        pid=r['playerId']
        if pid in records or r['seasonId']!=season:raise ValueError('Duplicate or incorrect player-season')
        clubs=[t.strip() for t in r['teamAbbrevs'].split(',')]
        if not clubs or not set(clubs)<=TEAMS:raise ValueError('Unknown NHL club')
        bio=current.get(pid,{})
        team=bio.get('team') or (clubs[0] if len(clubs)==1 else None)
        records[pid]={'id':pid,'name':r['skaterFullName'],'pos':r['positionCode'],'team':team,'clubs':clubs,
          'gp':r['gamesPlayed'],'goals':r['goals'],'assists':r['assists'],'points':r['points'],'teamGP':teams.get(team),
          'headshot':bio.get('headshot') or f'https://assets.nhle.com/mugs/nhl/latest/{pid}.png'}
    for pid,p in current.items():
        if pid not in records:records[pid]={'id':pid,'name':p['name'],'pos':p['pos'],'team':p['team'],'clubs':[],
          'gp':0,'goals':0,'assists':0,'points':0,'teamGP':teams[p['team']],'headshot':p.get('headshot','')}
    return validate({'version':1,'start':start,'season':season,'season_games':84,'asof':today.isoformat(),
      'sources':[url,standings_url],'source_sha256':hashlib.sha256(json.dumps([summary,standings],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
      'team_games':teams,'players':sorted(records.values(),key=lambda p:p['id'])})

def load():
    start=season_start(datetime.now(ZoneInfo('America/New_York')).date())
    old=validate(json.loads(CACHE.read_text())) if CACHE.exists() else None
    return old if old and old['start']==start else {'version':1,'start':start,'season':start*10000+start+1,'season_games':84,'asof':None,'players':[],'team_games':{}}

def refresh(fetch,roster,today):
    try:
        data=collect(fetch,roster,today)
        CACHE.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');return data
    except Exception as error:
        old=load()
        if old['start']==season_start(today) and old['players']:
            print('Projections: using verified snapshot from',old['asof'],'after',type(error).__name__);return old
        print('Projections player data unavailable; manual calculator remains available.');return {**old,'players':[],'asof':None}

def main():
    def fetch(url):
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Sweater NHL points projections'}),timeout=45) as r:return json.load(r)
    def get_roster(team):
        data=fetch(f'https://api-web.nhle.com/v1/roster/{team}/current')
        return [{'id':p['id'],'name':p['firstName']['default']+' '+p['lastName']['default'],'team':team,'pos':p['positionCode'],'headshot':p.get('headshot','')} for group in ['forwards','defensemen'] for p in data.get(group,[])]
    with ThreadPoolExecutor(max_workers=6) as pool:roster=[p for batch in pool.map(get_roster,sorted(TEAMS)) for p in batch]
    data=collect(fetch,roster,datetime.now(ZoneInfo('America/New_York')).date())
    CACHE.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    print('Verified projections:',len(data['players']),'skaters;',len(data['team_games']),'clubs;',data['asof'])

if __name__=='__main__':main()
