"""Reproducible NHL shift / factual-shot inputs for adjusted skater impact.

Raw downloads remain outside Git. Shift membership, goalies, roster identity and
strength must reconcile before an observation can enter the model.
"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.parse
import zipfile
import numpy as np

from player_data import get_json
from data import canonical
from lineup_data import clock
from train_shots import features

ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'.cache/playoffs/impact'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as f:return json.load(f)


def save_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    with (gzip.open(temp,'wt') if str(path).endswith('.gz') else open(temp,'w')) as f:
        json.dump(value,f,separators=(',',':'),allow_nan=False)
    temp.replace(path)


def shifts(first,last):
    path=CACHE/'shifts'/f'{first}-{last}.json.gz'
    if path.exists():return load_json(path)
    expression=f'gameId>={first} and gameId<={last}'
    url='https://api.nhle.com/stats/rest/en/shiftcharts?'+urllib.parse.urlencode({'cayenneExp':expression,'limit':-1})
    raw=get_json(url);rows=raw.get('data')
    if not isinstance(rows,list) or raw.get('total')!=len(rows):
        if first==last:raise ValueError('Incomplete NHL shift report')
        middle=(first+last)//2
        return shifts(first,middle)+shifts(middle+1,last)
    output=[];seen=set()
    for r in rows:
        if r.get('eventDescription') not in (None,'') or r.get('typeCode')!=517:continue
        p,g,period=r.get('playerId'),r.get('gameId'),r.get('period')
        a,b=clock(r.get('startTime')),clock(r.get('endTime'))
        if not all(isinstance(v,int) for v in (p,g,period)) or not first<=g<=last or period not in (1,2,3):continue
        if a is None or b is None or not 0<=a<b<=1200:continue
        key=(g,p,period,a,b)
        if key not in seen:seen.add(key);output.append(list(key)+[r.get('teamId')])
    save_json(path,output)
    return output


def download(games):
    by_year=defaultdict(list)
    for g in games:by_year[g['season']//10000].append(g['id'])
    tasks=[]
    for year,ids in sorted(by_year.items()):
        for first in range(min(ids),max(ids)+1,8):tasks.append((first,min(first+7,max(ids))))
    result=[];misses=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(shifts,*pair):pair for pair in tasks}
        for i,task in enumerate(as_completed(futures),1):
            try:result.extend(task.result())
            except Exception as e:misses.append([futures[task],str(e)])
            if i%40==0 or i==len(tasks):print('Shift batches',i,'/',len(tasks),'rows',len(result),'misses',len(misses),flush=True)
    if misses:raise ValueError('NHL shift source misses: '+str(misses[:3]))
    output=defaultdict(list)
    for row in result:output[row[0]].append(row)
    return output


def official_goalies(year):
    day=datetime.now(timezone.utc).date().isoformat() if year>=2026 else 'complete'
    path=CACHE/f'goalies-{year}-{day}.json.gz'
    if path.exists():return load_json(path)
    url='https://api.nhle.com/stats/rest/en/goalie/summary?'+urllib.parse.urlencode({'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':f'seasonId={year}{year+1} and gameTypeId=2'})
    raw=get_json(url)
    if not isinstance(raw.get('data'),list) or raw.get('total')!=len(raw['data']):raise ValueError('Incomplete NHL goalie identities')
    rows=[{'g':r['gameId'],'p':r['playerId'],'t':canonical(r['teamAbbrev'])} for r in raw['data'] if r.get('timeOnIce',0)>0]
    save_json(path,rows);return rows


def shot_rows(path,year):
    """Use factual geometry/goals only; never read MoneyPuck predicted xGoal."""
    model=json.loads((ROOT/'backend/src/shot-model.mjs').read_text().split('export const SHOT_MODEL=',1)[1].strip().rstrip(';'))
    weights=np.array(model['weights']);intercept,slope=model['calibration'];by_game=defaultdict(list)
    with zipfile.ZipFile(path) as archive:
        members=[m for m in archive.namelist() if m.endswith('.csv')]
        if len(members)!=1:raise ValueError('Unexpected shot archive')
        with archive.open(members[0]) as stream:
            for r in csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig')):
                if int(float(r['isPlayoffGame'])) or int(r['period']) not in (1,2,3) or r['event'] not in ('SHOT','MISS','GOAL'):continue
                gid=year*1000000+int(r['game_id']);home=bool(int(float(r['isHomeTeam'])))
                x,y=float(r['xCordAdjusted']),float(r['yCordAdjusted']);attack,defend=(int(r['homeSkatersOnIce']),int(r['awaySkatersOnIce'])) if home else (int(r['awaySkatersOnIce']),int(r['homeSkatersOnIce']))
                empty=bool(int(r['homeEmptyNet']) or int(r['awayEmptyNet']));q=None
                if not empty and (attack,defend) in ((5,5),(5,4),(4,5)) and math.isfinite(x+y) and 0<=x<=100 and abs(y)<=43 and (x or y):
                    z=intercept+slope*float(np.array(features(x,y,r['shotType'],attack,defend,False,bool(int(r['shotRebound']))))@weights)
                    q=max(.0001,min(.995,1/(1+math.exp(-max(-35,min(35,z))))))
                by_game[gid].append({'t':int(r['time']),'period':int(r['period']),'home':home,'hc':int(r['homeSkatersOnIce']),'ac':int(r['awaySkatersOnIce']),
                  'shooter':int(float(r['shooterPlayerId'])),'goal':int(r['goal']),'hg':int(r['homeTeamGoals']),'ag':int(r['awayTeamGoals']),
                  'q':q,'empty':empty,'home_team':r['homeTeamCode'],'away_team':r['awayTeamCode']})
    return by_game


def intervals(game,rows,players,goalies):
    """Half-open shift intervals, with known goalie membership on both sides."""
    identity={p['p']:canonical(p['team']) for p in players};identity.update({p['p']:canonical(p['t']) for p in goalies})
    goalie_ids={p['p'] for p in goalies};events=defaultdict(lambda:defaultdict(list));seen=set();team_ids={}
    for gid,p,period,a,b,tid in rows:
        if gid!=game['id'] or p not in identity:continue
        team=identity[p]
        if team in team_ids and team_ids[team]!=tid:raise ValueError('NHL shift team/roster mismatch')
        team_ids[team]=tid;key=(p,period,a,b)
        if key in seen:continue
        seen.add(key);events[period][a].append((p,1));events[period][b].append((p,-1))
    result=[]
    for period,changes in sorted(events.items()):
        active=Counter();bounds=sorted(changes)
        for start,end in zip(bounds,bounds[1:]):
            for p,delta in changes[start]:active[p]+=delta
            home=tuple(sorted(p for p,n in active.items() if n>0 and p not in goalie_ids and identity[p]==game['home']))
            away=tuple(sorted(p for p,n in active.items() if n>0 and p not in goalie_ids and identity[p]==game['away']))
            nets=all(any(active[p]>0 and identity[p]==t for p in goalie_ids) for t in (game['home'],game['away']))
            if not nets or (len(home),len(away)) not in ((5,5),(5,4),(4,5)):continue
            result.append({'a':(period-1)*1200+start,'b':(period-1)*1200+end,'home':home,'away':away,'x':[0.,0.],'goals':[0,0],'shooters':[],'bad':False,'score':0})
    return result


def join(game,shift_rows,players,goalies,shots):
    audit=Counter();stints=intervals(game,shift_rows,players,goalies)
    home_goals=away_goals=0
    for s in shots:
        if canonical(s['home_team'])!=game['home'] or canonical(s['away_team'])!=game['away']:
            raise ValueError('Shot/schedule club mismatch')
        candidates=[i for i,r in enumerate(stints) if r['a']<=s['t']<=r['b']]
        valid=[i for i in candidates if len(stints[i]['home'])==s['hc'] and len(stints[i]['away'])==s['ac'] and s['shooter'] in stints[i]['home' if s['home'] else 'away']]
        # NHL event clocks at a stoppage belong to the shift ending there;
        # the next faceoff can start different shifts at the same clock second.
        ending=[i for i in valid if stints[i]['a']<s['t']<=stints[i]['b']]
        if ending:valid=ending
        memberships={(stints[i]['home'],stints[i]['away']) for i in valid}
        if s['q'] is not None and len(memberships)==1:
            i=valid[0];side=0 if s['home'] else 1
            stints[i]['x'][side]+=s['q'];stints[i]['goals'][side]+=s['goal'];audit['matched_shots']+=1
            role=0 if s['hc']==s['ac'] else 1 if (s['hc']>s['ac'])==s['home'] else 2
            stints[i]['shooters'].append([s['shooter'],role,s['goal'],s['q']])
        elif s['q'] is not None:
            audit['ambiguous_or_missing_shifts']+=1
            for i in candidates:stints[i]['bad']=True
        else:audit['outside_shot_domain']+=1
        if s['goal']:
            if s['home']:home_goals+=1
            else:away_goals+=1
    goals=sorted([s for s in shots if s['goal']],key=lambda s:s['t'])
    output=[];usage=defaultdict(lambda:[0.,0.,0.]);finishing=defaultdict(lambda:[0.,0.])
    for r in stints:
        if r['bad']:continue
        r['score']=sum((1 if s['home'] else -1) for s in goals if s['t']<=r['a'])
        role=0 if len(r['home'])==len(r['away']) else 1 if len(r['home'])>len(r['away']) else 2
        seconds=r['b']-r['a'];audit['verified_seconds']+=seconds
        for team,ids,k in [(game['home'],r['home'],role),(game['away'],r['away'],0 if role==0 else 3-role)]:
            for p in ids:usage[(team,p)][k]+=seconds
        for p,k,scored,xg in r['shooters']:
            finishing[(p,k)][0]+=scored;finishing[(p,k)][1]+=xg
        output.append([r['a'],r['b'],list(r['home']),list(r['away']),r['x'],r['goals'],r['score']])
    return {'version':2,'g':game['id'],'d':game['date'],'s':game['season']//10000,'h':game['home'],'a':game['away'],
      'stints':output,'usage':[[t,p,*v] for (t,p),v in sorted(usage.items())],
      'finishing':[[p,k,*v] for (p,k),v in sorted(finishing.items())],'audit':dict(audit),
      'facts':{'regulation_home_goals':home_goals,'regulation_away_goals':away_goals}}


def build(shots_folder,first=2023,last=2026):
    all_games=[];players=defaultdict(list);goalies=defaultdict(list)
    for year in range(first,last+1):
        if year<2026:games=load_json(ROOT/f'.cache/playoffs/{year}.json')
        else:games=load_json(ROOT/'.cache/playoffs/lines/matchups-2026.json')
        all_games.extend(g for g in games if g['state'] in ('OFF','FINAL') and (g.get('type',2)==2))
        for r in load_json(ROOT/f'.cache/playoffs/lines/games-{year}.json'):players[r['g']].append(r)
        for r in official_goalies(year):goalies[r['g']].append(r)
    raw=download(all_games);manifest=[]
    for year in range(first,last+1):
        path=Path(shots_folder)/f'shots_{year}.zip';shots=shot_rows(path,year);totals=Counter();count=0;included=[]
        for g in all_games:
            if g['season']//10000!=year or g['id'] not in shots:continue
            cache=CACHE/'games'/f'{g["id"]}.json.gz'
            result=join(g,raw.get(g['id'],[]),players[g['id']],goalies[g['id']],shots[g['id']])
            winner_home=g['hg']>g['ag'];bonus=int(g['end'] in ('OT','SO'))
            expected_h=g['hg']-int(winner_home)*bonus;expected_a=g['ag']-int(not winner_home)*bonus
            if result['facts']['regulation_home_goals']!=expected_h or result['facts']['regulation_away_goals']!=expected_a:
                totals['incomplete_goal_log_games']+=1;cache.unlink(missing_ok=True);continue
            if result['audit'].get('verified_seconds',0)<2400:
                totals['insufficient_shift_coverage_games']+=1;cache.unlink(missing_ok=True);continue
            save_json(cache,result)
            totals.update(result['audit']);count+=1;included.append(g['id'])
        manifest.append({'season':year,'games':count,'game_ids':included,'shots_sha256':sha(path),'audit':dict(totals)})
        print('Impact joined',year,count,dict(totals),flush=True)
    save_json(CACHE/'manifest.json',{'version':2,'at':datetime.now(timezone.utc).isoformat(),'sources':manifest,'shot_model_sha256':sha(ROOT/'backend/src/shot-model.mjs')})


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--shots',type=Path,required=True);p.add_argument('--first',type=int,default=2023);p.add_argument('--last',type=int,default=2026);args=p.parse_args();build(args.shots,args.first,args.last)
