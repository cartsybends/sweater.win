"""Last-game combinations inferred from verified NHL shift overlap.

No line assignments are fabricated from roster order. Missing combinations stay
unidentified; empty-net play never creates a special-teams unit.
"""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import urllib.parse
from player_data import get_json

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'playoffs_lines/observed'


def clock(value):
    try:
        m,s=str(value).split(':');m,s=int(m),int(s)
        return m*60+s if 0<=s<60 and 0<=m<=120 else None
    except (ValueError,TypeError):
        return None


def groups(ids,combinations,size,count,positions=None):
    ids=tuple(sorted(ids));index={p:i for i,p in enumerate(ids)}
    candidates=[]
    for players,seconds in combinations.items():
        if len(players)==size and seconds>=20 and set(players).issubset(index):
            candidates.append((sum(1<<index[p] for p in players),tuple(players),seconds))
    @lru_cache(None)
    def choose(remaining,slots):
        if not remaining or not slots:
            return 0,()
        first=remaining&-remaining;best=choose(remaining^first,slots)
        for mask,players,seconds in candidates:
            if mask&first and mask&remaining==mask:
                score,picked=choose(remaining^mask,slots-1)
                if score+seconds>best[0]:
                    best=(score+seconds,picked+((players,seconds),))
        return best
    _,picked=choose((1<<len(ids))-1,count)
    order={'L':0,'LW':0,'C':1,'R':2,'RW':2}
    return [{'players':sorted(players,key=lambda p:(order.get((positions or {}).get(p,''),9),p)),
             'seconds':round(seconds)} for players,seconds in sorted(picked,key=lambda g:(-g[1],g[0]))]


def special(combinations):
    ranked=sorted(combinations.items(),key=lambda r:(-r[1],r[0]));picked=[]
    for (players,opposition),seconds in ranked:
        if seconds<10 or picked and len(set(players)-set(picked[0]['players']))<2:
            continue
        picked.append({'players':list(players),'seconds':round(seconds),'strength':f'{len(players)}-on-{opposition}'})
        if len(picked)==2:
            break
    return picked


def infer(game,box,shifts,pbp):
    if box.get('id')!=game['id'] or pbp.get('id')!=game['id'] or box.get('gameState') not in ('OFF','FINAL') or box.get('gameType')!=2:
        raise ValueError('Lineup source must be a completed regular-season NHL game')
    if box['homeTeam']['abbrev']!=game['home'] or box['awayTeam']['abbrev']!=game['away'] or box['startTimeUTC']!=game['start']:
        raise ValueError('Lineup game identity mismatch')
    if (pbp.get('gameState') not in ('OFF','FINAL') or pbp.get('gameType')!=2
        or pbp.get('startTimeUTC')!=game['start'] or pbp.get('gameDate')!=box.get('gameDate')
        or pbp.get('season')!=box.get('season')
        or any(pbp.get(side+'Team',{}).get(key)!=box[side+'Team'].get(key)
               for side in ('home','away') for key in ('id','abbrev','score'))):
        raise ValueError('NHL lineup boxscore and play-by-play disagree')
    names={p['playerId']:' '.join(filter(None,[p.get('firstName',{}).get('default'),p.get('lastName',{}).get('default')])) for p in pbp.get('rosterSpots',[])}
    teams={};identity={};goalies=set();positions={};per_player=defaultdict(lambda:{'ev':0,'pp':0,'pk':0})
    for side in ['home','away']:
        club=box[side+'Team'];stats=box.get('playerByGameStats',{}).get(side+'Team',{})
        players=[]
        for category in ['forwards','defense']:
            for r in stats.get(category,[]):
                pid=r['playerId'];pos='D' if category=='defense' else r.get('position','F')
                seconds=clock(r.get('toi'))
                if not isinstance(pid,int) or seconds is None or pid in identity:
                    raise ValueError('Invalid NHL skater')
                identity[pid]=club['abbrev'];positions[pid]=pos
                players.append({'id':pid,'name':names.get(pid) or r.get('name',{}).get('default','Player unavailable'),
                  'position':pos,'number':r.get('sweaterNumber'),'seconds':seconds,
                  'goals':r.get('goals',0),'shots':r.get('sog',0),'blocks':r.get('blockedShots'),
                  'fo_reported':r.get('faceoffWinningPctg')})
        if not 15<=len(players)<=21:
            raise ValueError('Incomplete dressed lineup')
        for r in stats.get('goalies',[]):
            pid=r['playerId'];identity[pid]=club['abbrev'];goalies.add(pid)
        teams[club['abbrev']]={'abbr':club['abbrev'],'team_id':club['id'],'players':players,'f':defaultdict(float),'d':defaultdict(float),
          'pp':defaultdict(float),'pk':defaultdict(float),'five_on_five_seconds':0}
    by_period=defaultdict(lambda:defaultdict(list));seen=set()
    rows=shifts.get('data',[])
    if not isinstance(rows,list) or len(rows)>5000 or shifts.get('total')!=len(rows):
        raise ValueError('Incomplete NHL shift feed')
    for r in rows:
        pid=r.get('playerId');period=r.get('period');start,end=clock(r.get('startTime')),clock(r.get('endTime'))
        if r.get('eventDescription') not in (None,'') or pid not in identity or not isinstance(period,int) or period not in (1,2,3,4):
            continue
        length=1200 if period<=3 else 300
        if start is None or end is None or not 0<=start<end<=length:
            continue
        key=(pid,period,start,end)
        if key in seen:
            continue
        seen.add(key);by_period[period][start].append((pid,1));by_period[period][end].append((pid,-1))
    for period,events in by_period.items():
        active=defaultdict(int);bounds=sorted(events)
        for start,end in zip(bounds,bounds[1:]):
            for pid,delta in events[start]:
                active[pid]+=delta
            skaters={t:{p for p,n in active.items() if n>0 and p not in goalies and identity[p]==t} for t in teams}
            both_goalies=all(any(active[g]>0 and identity[g]==t for g in goalies) for t in teams)
            if not both_goalies:
                continue
            for team,target in teams.items():
                ids=skaters[team];opponent=next(t for t in teams if t!=team);other=skaters[opponent];seconds=end-start
                if not 3<=len(ids)<=5 or not 3<=len(other)<=5:
                    continue
                strength='ev' if len(ids)==len(other) else 'pp' if len(ids)>len(other) else 'pk'
                for pid in ids:
                    per_player[pid][strength]+=seconds
                if strength=='ev' and len(ids)==5 and period<=3:
                    target['five_on_five_seconds']+=seconds
                    forwards=tuple(sorted(p for p in ids if positions[p]!='D'));defense=tuple(sorted(p for p in ids if positions[p]=='D'))
                    if len(forwards)==3 and len(defense)==2:
                        target['f'][forwards]+=seconds;target['d'][defense]+=seconds
                elif strength in ('pp','pk'):
                    target[strength][(tuple(sorted(ids)),len(other))]+=seconds
    faces=defaultdict(lambda:[0,0])
    for p in pbp.get('plays',[]):
        if p.get('typeDescKey')=='faceoff' and p.get('periodDescriptor',{}).get('periodType') in ('REG','OT'):
            d=p.get('details',{});winner,loser=d.get('winningPlayerId'),d.get('losingPlayerId')
            if winner in identity and loser in identity:
                faces[winner][0]+=1;faces[winner][1]+=1;faces[loser][1]+=1
    for team,target in teams.items():
        forwards=[p['id'] for p in target['players'] if p['position']!='D'];defense=[p['id'] for p in target['players'] if p['position']=='D']
        valid=target['five_on_five_seconds']>=300
        for key,ids,size,count in [('f',forwards,3,4),('d',defense,2,3)]:
            target[key]=groups(ids,target[key],size,count,positions) if valid else []
        for key in ('pp','pk'):
            target[key]=special(target[key])
        assigned={pid for group in target['f']+target['d'] for pid in group['players']}
        target['other']=[p['id'] for p in target['players'] if p['id'] not in assigned]
        for p in target['players']:
            pid=p['id'];p.update(per_player[pid]);wins,attempts=faces[pid]
            reported=p.pop('fo_reported')
            # Do not average faceoff percentages or infer attempts from rounding.
            agrees=attempts>0 and (reported is None or abs(wins/attempts-reported)<.00001)
            p['fo_wins']=wins if agrees or attempts==0 else None;p['fo_total']=attempts if agrees or attempts==0 else None
        target['quality']='available' if valid else 'partial'
    return {'version':1,'id':game['id'],'season':box['season'],'date':box['gameDate'],'start':game['start'],
      'home':game['home'],'away':game['away'],'teams':teams,
      'source_url':f'https://www.nhl.com/gamecenter/{game["id"]}','method':'observed NHL shift overlap'}


def observed(game,folder=FOLDER):
    path=Path(folder)/f'{game["id"]}.json'
    if path.exists():
        saved=json.loads(path.read_text())
        if saved.get('version')==1 and saved.get('id')==game['id'] and saved.get('start')==game['start'] and all(t.get('team_id') for t in saved.get('teams',{}).values()):
            return saved
    gid=game['id']
    box=get_json(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore')
    shifts=get_json('https://api.nhle.com/stats/rest/en/shiftcharts?'+urllib.parse.urlencode({'cayenneExp':f'gameId={gid}','limit':-1}))
    pbp=get_json(f'https://api-web.nhle.com/v1/gamecenter/{gid}/play-by-play')
    result=infer(game,box,shifts,pbp)
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n');temp.replace(path)
    return result
