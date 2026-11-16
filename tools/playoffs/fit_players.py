"""Fit and chronologically evaluate conditional skater goal shares from NHL facts."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from player_data import CACHE, audit
from player_model import History, FEATURES, BASELINE

ROOT=Path(__file__).resolve().parents[2]


def samples(rows):
    games=defaultdict(list)
    for row in rows:
        games[(row['date'],row['g'])].append(row)
    state=History();output=[]
    for (day,gid),players in sorted(games.items()):
        teams=defaultdict(list)
        for p in players:
            teams[p['team']].append(p)
        if len(teams)!=2:
            raise ValueError('Incomplete skater game sides')
        for team,side in teams.items():
            season=side[0]['season']
            if season>=2024:
                output.append({'g':gid,'date':day,'season':season,'team':team,
                  'x':np.array([state.features(p['p'],season,p['opp'],p['pos']) for p in side]),
                  'y':np.array([p['goals'] for p in side],dtype=float)})
        for row in players:
            state.add(row)
    return output


def matrix(samples):
    x=np.vstack([s['x'] for s in samples]);y=np.concatenate([s['y'] for s in samples])
    counts=np.array([len(s['y']) for s in samples]);starts=np.r_[0,np.cumsum(counts)[:-1]]
    groups=np.repeat(np.arange(len(counts)),counts);totals=np.add.reduceat(y,starts)
    return x,y,starts,groups,totals


def objective(beta,bundle,penalty=0,gradient=False):
    x,y,starts,groups,totals=bundle;z=x@beta;maximum=np.maximum.reduceat(z,starts)
    exp=np.exp(z-maximum[groups]);denom=np.add.reduceat(exp,starts);logsum=np.log(denom)+maximum
    loss=(totals@logsum-y@z)/y.sum()+penalty*np.sum((beta-np.array(BASELINE))**2)
    if not gradient:
        return float(loss)
    grad=x.T@(exp/denom[groups]*totals[groups]-y)/y.sum()+2*penalty*(beta-np.array(BASELINE))
    return float(loss),grad


def fit(data,penalty):
    result=minimize(lambda b:objective(b,data,penalty,True),np.array(BASELINE,dtype=float),jac=True,method='L-BFGS-B',bounds=[(-3,3)]*len(BASELINE))
    if not result.success:
        raise ValueError(result.message)
    return result.x


if __name__=='__main__':
    rows=[];inputs=[]
    for season in range(2023,2027):
        path=CACHE/f'games-{season}.json';part=json.loads(path.read_text())
        # Current-season snapshot excludes the current NHL calendar day, where
        # official stat reports can still contain live, incomplete appearances.
        if season==2026:
            from zoneinfo import ZoneInfo
            today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
            part=[r for r in part if r['date']<today]
        inputs.append({'season':season,'rows':len(part),'sha256':audit(part)})
        rows.extend(part)
    all_samples=samples(rows)
    train=[s for s in all_samples if s['season']==2024 and s['date']<'2025-01-15']
    tune=[s for s in all_samples if s['season']==2024 and s['date']>='2025-01-15']
    hold=[s for s in all_samples if s['season']==2025]
    live=[s for s in all_samples if s['season']==2026]
    a,b=matrix(train),matrix(tune);candidates=[]
    for penalty in [.0001,.001,.01,.1]:
        coef=fit(a,penalty);score=objective(coef,b);candidates.append((score,penalty));print('Tune',penalty,score,flush=True)
    _,penalty=min(candidates)
    initial=fit(matrix([s for s in all_samples if s['season']==2024]),penalty)
    test=matrix(hold);baseline=objective(np.array(BASELINE),test);value=objective(initial,test)
    if value>baseline+.003:
        raise ValueError('Player allocation failed its later-season baseline gate')
    release=fit(matrix([s for s in all_samples if s['season'] in (2024,2025)]),penalty)
    current=matrix(live)
    output={'version':'sweater-player-shares-v1','built_at':datetime.now(timezone.utc).isoformat(),
      'features':FEATURES,'weights':release.tolist(),'penalty':penalty,'inputs':inputs,
      'validation':{'season':2025,'team_games':len(hold),'goals':int(test[1].sum()),'goal_allocation_log_loss':value,'baseline_log_loss':baseline},
      'current_snapshot':{'season':2026,'data_through':max(s['date'] for s in live),'team_games':len(live),'goals':int(current[1].sum()),'goal_allocation_log_loss':objective(release,current),'baseline_log_loss':objective(np.array(BASELINE),current)},
      'limitations':['Conditional on dressed skaters; not a lineup or injury forecast.',
        'Allocates the existing team goal forecast; does not establish calibration of team or line totals.',
        'Opponent history is strongly regressed; no fitted line chemistry effect.',
        'Historical evaluation knows the dressed roster, but all performance and usage features use strictly earlier games.',
        'Release coefficients are refitted through 2025–26 after evaluating the earlier fit on that season.'],
      'sources':['https://api.nhle.com/stats/rest/en/skater/summary','https://api.nhle.com/stats/rest/en/skater/timeonice']}
    path=Path(__file__).with_name('player_parameters.json');path.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output['validation']),json.dumps(output['current_snapshot']),flush=True)
