"""Publish matchup-specific lineup context and conditional player goal forecasts."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from lineup_data import observed
from matchups import collect as collect_meetings, for_game as matchup_for_game
from player_data import CACHE, current_season, season_report, skater_games
from player_model import History, goal_allocation

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'playoffs_lines/matchups'


def stamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def stored(path,value):
    text=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
    if path.exists() and path.read_text()==text:
        return
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(text);temp.replace(path)


def player_rows(year):
    path=CACHE/f'games-{year}.json'
    if year<current_season() and path.exists():
        return json.loads(path.read_text())
    rows=skater_games(year,display_stats=year==current_season())
    stored(path,rows)
    return rows


def supplement(rows,observations,completed):
    """Use official final boxscores when season-stat publication is behind."""
    by_key={(r['g'],r['p']):r for r in rows if r['g'] in completed}
    for gid,data in observations.items():
        if gid not in completed:
            continue
        for club,team in data['teams'].items():
            opponent=data['away'] if club==data['home'] else data['home']
            for p in team['players']:
                key=(gid,p['id'])
                if key in by_key or not p['seconds']:
                    continue
                by_key[key]={'g':gid,'date':data['date'],'season':data['season']//10000,'p':p['id'],
                  'team':club,'opp':opponent,'pos':p['position'],'name':p['name'],
                  'goals':p['goals'],'shots':p['shots'],'seconds':p['seconds'],
                  'pp':p['pp'] if team['quality']=='available' else None,
                  'ev':p['ev'],'pk':p['pk'],'blocks':p['blocks'],
                  'fo_wins':p['fo_wins'],'fo_total':p['fo_total'],'source':'NHL final boxscore/shift feed'}
    return sorted(by_key.values(),key=lambda r:(r['date'],r['g'],r['team'],r['p']))


def team_special(year,completed):
    data={}
    for name in ['powerplay','penaltykill']:
        data[name]=[r for r in season_report('team',name,year) if r['gameId'] in completed]
    return data


def special_rates(club,source,cutoff,rows):
    # IDs come from the verified NHL boxscore; no name/abbreviation guessing.
    team_id=source['team_id']
    output={}
    for key,report,numerator,denominator in [('pp','powerplay','powerPlayGoalsFor','ppOpportunities'),('pk','penaltykill','ppGoalsAgainst','timesShorthanded')]:
        eligible=[r for r in rows[report] if r['teamId']==team_id and r['gameDate'][:10]<cutoff]
        if not eligible or any(not isinstance(r.get(numerator),int) or not isinstance(r.get(denominator),int) for r in eligible):
            output[key]=None;continue
        n=sum(r[numerator] for r in eligible);d=sum(r[denominator] for r in eligible)
        output[key]=round(100*((1-n/d) if key=='pk' else n/d),3) if d else None
    return output


def availability(game,side,pid,name):
    injuries=game.get('context',{}).get(side,{}).get('injuries',[])
    for injury in injuries:
        match=injury.get('nhl_id')==pid or injury.get('id')==pid or injury.get('name','').casefold()==name.casefold()
        if match:
            return injury.get('status','Unavailable')
    return None


def project_side(game,side,source,previous,history,parameters,specials,now):
    club=game[side];other=game['away' if side=='home' else 'home'];season=int(str(game['id'])[:4]);team=source['teams'][club]
    players=team['players'];mean=game['prediction'][side+'_goals']
    allocation=goal_allocation(players,history,season,other,mean,parameters['weights'])
    prior_units={}
    if previous and club in previous['teams']:
        for kind in ['f','d']:
            for index,unit in enumerate(previous['teams'][club][kind],1):
                for pid in unit['players']:
                    prior_units[(kind,pid)]=index
    projected=[]
    for p in players:
        row={k:p[k] for k in ['id','name','position','number']}
        row['stats']=history.season_stats(p['id'],season)
        row['expected_goals']=round(allocation[p['id']],6)
        row['availability']=availability(game,side,p['id'],p['name']) if stamp(game['start'])>stamp(now) else None
        projected.append(row)
    by_id={p['id']:p for p in projected};units={}
    for kind,count in [('f',4),('d',3),('pp',2),('pk',2)]:
        units[kind]=[]
        for index,unit in enumerate(team[kind][:count],1):
            ids=unit['players'];unavailable=any(str(by_id[p].get('availability') or '').upper() in ('OUT','IR','IR-LT','INJURED RESERVE','SUSPENSION','SUSPENDED') for p in ids)
            units[kind].append({**unit,'rank':index,
              'expected_goals':round(sum(allocation[p] for p in ids),4) if kind in ('f','d') and not unavailable else None,
              'movement':{str(p):{'previous':prior_units[(kind,p)],'current':index} for p in ids if kind in ('f','d') and (kind,p) in prior_units and prior_units[(kind,p)]!=index}})
    cutoff=game['date']
    return {'abbr':club,'status':team['quality'],'source_game':{'id':source['id'],'date':source['date'],
      'start':source['start'],'opponent':source['away'] if club==source['home'] else source['home'],
      'url':source['source_url']},'previous_game':previous['id'] if previous else None,
      'players':projected,'units':units,'other':team['other'],
      'forward_count':sum(p['position']!='D' for p in players),'defense_count':sum(p['position']=='D' for p in players),
      'special_teams':special_rates(club,team,cutoff,specials),'team_goals':mean,
      'stats_through':max((row['date'] for appearances in history.recent.values() for row in appearances),default=source['date'])}


def build(feed=None,now=None):
    feed=feed or json.loads((ROOT/'playoffs_cache.json').read_text())
    now=now or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    year=feed['start'];parameters=json.loads(Path(__file__).with_name('player_parameters.json').read_text())
    meetings=collect_meetings(last=year)
    season=[g for g in meetings if g['season']==feed['season'] and g['type']==2]
    completed={g['id']:g for g in season if g['state'] in ('OFF','FINAL') and stamp(g['start'])<stamp(now)}
    current=player_rows(year);known={r['g'] for r in current};needed={gid:g for gid,g in completed.items() if gid not in known}
    references={}
    for game in feed['games']:
        for side in ['home','away']:
            recent=sorted([g for g in completed.values() if game[side] in (g['home'],g['away']) and stamp(g['start'])<stamp(game['start'])],key=lambda g:g['start'],reverse=True)[:2]
            references[(game['id'],side)]=recent
            needed.update({g['id']:g for g in recent})
    observations={};errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(observed,g):gid for gid,g in needed.items()}
        for task in as_completed(tasks):
            gid=tasks[task]
            try:observations[gid]=task.result()
            except Exception as exc:errors.append((gid,str(exc)))
    current=supplement(current,observations,completed)
    # All feature/display updates are cut off at strictly earlier calendar dates;
    # today's partial appearances can never leak into a pregame projection.
    rows=[]
    for season_year in range(year-3,year):
        rows.extend(player_rows(season_year))
    rows.extend(current);rows.sort(key=lambda r:(r['date'],r['g'],r['p']))
    history=History();cursor=0;specials=team_special(year,completed);count=0
    for game in sorted(feed['games'],key=lambda g:(g['start'],g['id'])):
        cutoff=game['date']
        while cursor<len(rows) and rows[cursor]['date']<cutoff:
            history.add(rows[cursor]);cursor+=1
        path=FOLDER/f'{game["id"]}.json';old=json.loads(path.read_text()) if path.exists() else None
        freeze=old and old.get('basis')=='pregame' and old.get('start')==game['start'] and stamp(old['as_of'])<stamp(game['start'])<=stamp(now)
        if freeze:
            output={**old,'matchups':matchup_for_game(game,meetings,now)}
        else:
            output={'version':1,'id':game['id'],'start':game['start'],'home':game['home'],'away':game['away'],
              'as_of':now,'basis':'pregame' if stamp(now)<stamp(game['start']) else 'reconstructed',
              'model':parameters['version'],'model_validation':parameters['validation'],
              'method':'Last-game observed combinations; conditional player scoring projection',
              'matchups':matchup_for_game(game,meetings,now),'teams':{}}
            for side in ['home','away']:
                prior=references[(game['id'],side)];source=observations.get(prior[0]['id']) if prior else None
                previous=observations.get(prior[1]['id']) if len(prior)>1 else None
                if source:
                    output['teams'][game[side]]=project_side(game,side,source,previous,history,parameters,specials,now)
                else:
                    output['teams'][game[side]]={'abbr':game[side],'status':'unavailable','reason':'Previous-game shift data unavailable.'}
        stored(path,output);count+=1
    print('Game previews:',count,'matchups;',len(observations),'verified observed lineups;',len(errors),'source misses',flush=True)
    for gid,message in errors[:5]:print('Lineup source unavailable',gid,message,flush=True)
    return count


if __name__=='__main__':
    build()
