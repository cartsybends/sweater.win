"""Current NHL membership checks, including independently verified reserve players.

A parent-club label in an injury feed or player profile is not an active NHL
roster. Minor-league appearances require a separate current reserve listing.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unicodedata
import urllib.parse

from data import TEAMS,canonical

ESPN={'LAK':'LA','NJD':'NJ','SJS':'SJ','TBL':'TB','UTA':'UTAH'}
RESERVE={'ir','ir-lt','injured reserve','long-term injured reserve','suspended','suspension'}
NOT_NHL={'free-agent','retired','minors','minor-league','assigned-to-minors'}
CLUB_LEAGUES={'AHL','ECHL','OHL','WHL','QMJHL','LHJMQ','NCAA','USHL','SHL','Liiga','KHL','DEL','HockeyAllsvenskan'}


def norm(name):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKD',name) if c.isalnum())


def compatible_name(a,b):
    return norm(a)==norm(b) or bool(a.strip() and b.strip()) and norm(a.split()[-1])==norm(b.split()[-1]) and a[0].casefold()==b[0].casefold()


class Membership:
    def __init__(self,folder,fetch,now):
        self.folder=Path(folder)/'eligibility';self.folder.mkdir(parents=True,exist_ok=True)
        self.fetch=fetch;self.now=now;self.time=datetime.fromisoformat(now.replace('Z','+00:00'))
        self.season=(self.time.year-(self.time.month<7))*10000+self.time.year-(self.time.month<7)+1
        self.rosters={};self.status={}

    def observed(self,key,url,parse,ttl=900):
        path=self.folder/(key+'.json');saved=None
        try:
            saved=json.loads(path.read_text());age=(self.time-datetime.fromisoformat(saved['checked_at'].replace('Z','+00:00'))).total_seconds()
            if 0<=age<ttl:return parse(saved['data']),'reported'
        except (OSError,ValueError,TypeError,KeyError,AttributeError,IndexError):saved=None
        try:
            raw=self.fetch(url);value=parse(raw)
            with tempfile.NamedTemporaryFile('w',dir=self.folder,delete=False) as f:
                json.dump({'checked_at':self.now,'data':raw},f,separators=(',',':'));temp=Path(f.name)
            temp.replace(path);return value,'reported'
        except Exception:
            if saved:
                try:
                    age=(self.time-datetime.fromisoformat(saved['checked_at'].replace('Z','+00:00'))).total_seconds()
                    if 0<=age<=86400:return parse(saved['data']),'cached'
                except (ValueError,TypeError,KeyError,AttributeError,IndexError):pass
            return None,'unavailable'

    def roster(self,team):
        def parse(raw):
            players=[{'id':p['id'],'name':p['firstName']['default']+' '+p['lastName']['default'],'position':key}
              for key in ('forwards','defensemen','goalies') for p in raw[key]]
            if len(players)<15 or len({p['id'] for p in players})!=len(players) or not any(p['position']=='goalies' for p in players):raise ValueError('Incomplete NHL roster')
            if not all(type(p['id']) is int and p['id']>0 and p['name'].strip() for p in players):raise ValueError('Invalid NHL identities')
            return players
        players,status=self.observed('roster-'+team,f'https://api-web.nhle.com/v1/roster/{team}/current',parse)
        return team,players or [],status

    def collect(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            for team,players,status in pool.map(self.roster,TEAMS):self.rosters[team]=players;self.status[team]=status
        return self.rosters

    def identity(self,name):
        def parse(raw):
            if not isinstance(raw,list):raise ValueError('Invalid NHL search')
            matches={int(p['playerId']):p for p in raw if isinstance(p.get('name'),str) and compatible_name(p['name'],name)}
            exact={pid:p for pid,p in matches.items() if norm(p['name'])==norm(name)}
            choices=exact or matches
            return next(iter(choices.values())) if len(choices)==1 else None
        query=urllib.parse.urlencode({'culture':'en-us','limit':10,'q':name})
        key='identity-'+hashlib.sha256(norm(name).encode()).hexdigest()[:24]
        result,_=self.observed(key,'https://search.d3.nhle.com/api/v1/search/player?'+query,parse,86400)
        if result is None:
            surname=name.split()[-1];query=urllib.parse.urlencode({'culture':'en-us','limit':20,'q':surname})
            key='surname-'+hashlib.sha256(norm(surname).encode()).hexdigest()[:24]
            result,_=self.observed(key,'https://search.d3.nhle.com/api/v1/search/player?'+query,parse,86400)
        return result

    def espn_reserve(self,team,name):
        def parse(raw):
            if raw.get('team',{}).get('abbreviation')!=ESPN.get(team,team) or not isinstance(raw.get('athletes'),list):raise ValueError('Wrong ESPN roster')
            people=[p for g in raw['athletes'] for p in g['items']]
            if len(people)<15:raise ValueError('Incomplete ESPN roster')
            return {norm(p['displayName']) for p in people if p.get('status',{}).get('type') not in NOT_NHL and
              (p.get('status',{}).get('type') in {'injured-reserve','suspended'} or any(str(i.get('status','')).lower() in RESERVE for i in p.get('injuries',[])))}
        people,_=self.observed('reserve-'+team,f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{ESPN.get(team,team)}/roster',parse)
        return people is not None and norm(name) in people

    def check(self,item):
        team,injury=item;record=dict(injury);name=record['name'];players=self.rosters[team]
        # Preserve the dated source observation during an outage. The context
        # marks this roster unavailable; UI and player adjustments must not
        # present unverified membership as current.
        if self.status[team]=='unavailable':return team,record
        matched=[p for p in players if norm(p['name'])==norm(name)]
        if len(matched)==1:return team,{**record,'player_id':matched[0]['id'],'membership':'NHL roster'}
        if record.get('registration_status') in NOT_NHL:return team,None
        identity=self.identity(name)
        if identity:
            pid=int(identity['playerId'])
            if any(p['id']==pid for p in players):return team,{**record,'player_id':pid,'membership':'NHL roster'}
        if str(record.get('status','')).lower() not in RESERVE:return team,None
        if not identity:return team,({**record,'player_id':None,'membership':'verified reserve'} if self.espn_reserve(team,name) else None)
        pid=int(identity['playerId'])
        def parse(raw):
            if raw.get('playerId')!=pid or not compatible_name(raw['firstName']['default']+' '+raw['lastName']['default'],identity['name']):raise ValueError('Wrong NHL profile')
            return raw
        profile,_=self.observed('player-'+str(pid),f'https://api-web.nhle.com/v1/player/{pid}/landing',parse)
        if not profile:
            return team,({**record,'player_id':pid,'membership':'verified reserve'} if self.espn_reserve(team,name) else None)
        if canonical(profile.get('currentTeamAbbrev'))!=team:return team,None
        elsewhere=any(r.get('season')==self.season and r.get('leagueAbbrev') in CLUB_LEAGUES and r.get('gamesPlayed',0)>0 for r in profile.get('seasonTotals',[]))
        played_nhl=any(r.get('season')==self.season and r.get('leagueAbbrev')=='NHL' and r.get('gamesPlayed',0)>0 for r in profile.get('seasonTotals',[]))
        if (elsewhere or not played_nhl) and not self.espn_reserve(team,name):return team,None
        return team,{**record,'player_id':pid,'membership':'verified reserve'}

    def reconcile(self,injuries):
        result={t:[] for t in TEAMS};items=[(team,r) for team,rows in injuries.items() for r in rows]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for team,record in pool.map(self.check,items):
                if record:result[team].append(record)
        return result
