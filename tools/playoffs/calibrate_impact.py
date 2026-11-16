"""Chronological game-level calibration, conditional on dressed skater identities.

No historical injury-report archive is invented. Same-game minutes, shots and
goals never enter lineup features. This checks the translation to game outcomes;
it does not establish live injury-report or playoff-probability calibration.
"""
from collections import defaultdict
from copy import deepcopy
import json
import hashlib
import math
import numpy as np
from data import canonical
from impact_data import CACHE,ROOT,load_json,save_json
from impact_model import Team,KEYS,ROLES
from impact_artifact import finishing
from strength_v2 import design,expected,config,probability


def folded(model):
    result=deepcopy(model);coefs=load_json(CACHE/'coefficients-fold.json');pids=coefs['pids'];base=70
    facts=[defaultdict(lambda:[0.,0.]) for _ in ROLES];usage=defaultdict(lambda:np.zeros(3))
    for year in (2023,2024):
        source=next(s for s in model['inputs']['sources'] if s['season']==year)
        for gid in source['game_ids']:
            g=load_json(CACHE/'games'/f'{gid}.json.gz')
            for p,k,goals,xg in g['finishing']:facts[k][p][0]+=goals;facts[k][p][1]+=xg
            for _,p,*seconds in g['usage']:usage[p]+=seconds
    for k,role in enumerate(ROLES):
        beta=coefs['fold'][role];defending=0 if k==0 else 3-k;result['rates'][role]=math.exp(beta[0])
        prior=model['finishing_validation'][k]['prior_expected_goals'];ratings,league=finishing(facts[k],prior)
        for i,p in enumerate(pids):
            r=result['players'][str(p)];effect=(ratings.get(p,league)-league)*facts[k][p][1]*3600/max(usage[p][k],1)/result['rates'][role]
            r['off_'+role]=beta[base+i]+effect;r['def_'+ROLES[defending]]=beta[base+len(pids)+i]
            r['training_minutes'][role]=usage[p][k]/60
    result['usage_history']={y:v for y,v in model['usage_history'].items() if int(y)<2025}
    prior=defaultdict(lambda:np.zeros(4))
    for year,clubs in result['usage_history'].items():
        for c in clubs.values():
            for p,r in c['players'].items():prior[p]+=np.r_[r['gp'],r['minutes']]*{2023:.3,2024:.6}[int(year)]
    for p,r in result['players'].items():r['usage_prior']=(prior[p][1:]/max(prior[p][0],1)).tolist()
    for position in ('F','D'):
        selected=[p for p,r in result['players'].items() if (r['position']=='D')==(position=='D') and prior[p][0]>=15]
        cutoff=np.quantile([prior[p][1]/prior[p][0] for p in selected],.25)
        selected=[p for p in selected if prior[p][1]/prior[p][0]<=cutoff];weights=[prior[p][0] for p in selected]
        result['replacement'][position]={k:float(np.average([result['players'][p][k] for p in selected],weights=weights)) for k in KEYS}
        result['replacement'][position]['usage_prior']=np.average([result['players'][p]['usage_prior'] for p in selected],axis=0,weights=weights).tolist()
    return result


def game_factors(game,past,current,advanced,model,params):
    clubs={}
    for club in (game['home'],game['away']):
        dressed=[r for r in current if canonical(r['team'])==club]
        if sum(r['pos']=='D' for r in dressed)!=6 or len(dressed)!=18:return None
        previous=[r for r in past if canonical(r['team'])==club]
        recent_games=sorted({r['g'] for r in previous})[-10:];candidates={r['p']:r for r in previous if r['g'] in recent_games}
        candidates.update({r['p']:r for r in dressed});actual={r['p'] for r in dressed}
        by_player=defaultdict(list)
        for r in previous:by_player[r['p']].append((r.get('ev') or 0)/60)
        def value(pid):
            rows=by_player[pid];prior=model['players'].get(str(pid),{}).get('usage_prior',[0])[0]
            return .6*np.mean(rows[-5:])+.4*np.mean(rows) if rows else prior
        core=[]
        for position,count in [('F',12),('D',6)]:
            core.extend(sorted([r for r in candidates.values() if ('D' if r['pos']=='D' else 'F')==position],key=lambda r:-value(r['p']))[:count])
        roster={r['p']:r for r in core+dressed}
        injuries=[{'player_id':r['p'],'name':r['name'],'status':'Out'} for r in core if r['p'] not in actual]
        if len(injuries)>8:return None
        roster=[{'id':p,'name':r['name'],'position':'defensemen' if r['pos']=='D' else 'forwards'} for p,r in roster.items()]
        clubs[club]=Team(club,roster,injuries,past,[r for r in advanced if r['s']==game['season']//10000 and r['t']==club and r['d']<game['date']],model,game['date'],params['prior_games'],params['half_life'])
    home,away=clubs[game['home']],clubs[game['away']];rates=np.array([model['rates'][k] for k in ROLES]);share=model['modeled_regulation_goal_share']
    def side(own,opp):
        minutes=(own.role_minutes+opp.role_minutes[[0,2,1]])/2;weights=minutes*rates;weights/=weights.sum()
        values=own.mean(game['date'])[:3]*opp.mean(game['date'])[[3,5,4]]
        return math.log(1-share+share*float(values@weights))
    return side(home,away),side(away,home)


def dataset(year,model,inputs,params):
    path=CACHE/f'game-calibration-v1-{year}.json'
    rows=load_json(ROOT/f'.cache/playoffs/lines/games-{year}.json');by_date=defaultdict(list);by_game=defaultdict(list)
    for r in rows:by_date[r['date']].append(r);by_game[r['g']].append(r)
    games=load_json(ROOT/(f'.cache/playoffs/{year}.json' if year<2026 else '.cache/playoffs/lines/matchups-2026.json'))
    games=sorted([g for g in games if g['state'] in ('OFF','FINAL')],key=lambda g:(g['date'],g['id']))
    for g in games:g.setdefault('neutral',False)
    source={'players':model['players'],'replacement':model['replacement'],'history':model['usage_history'],'rates':model['rates'],
      'params':params,'rows':rows,'games':games,'runtime_sha256':hashlib.sha256((ROOT/'tools/playoffs/impact_model.py').read_bytes()).hexdigest(),
      'advanced':{k:[r for r in inputs[k] if r['s']<=year] for k in ('teams','goalies')}}
    signature=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    if path.exists():
        cached=load_json(path)
        if isinstance(cached,dict) and cached.get('signature')==signature:return cached['games']
    x,y,ids,actual=design(year,games,inputs,params['prior_games'],params['half_life']);means=expected(x,params).reshape(-1,2)
    past=[];days=sorted(by_date);included=[];known={(r['g'],r['t']) for r in inputs['teams']};joined=set(next(s['game_ids'] for s in model['inputs']['sources'] if s['season']==year))
    for i,g in enumerate(games):
        while days and days[0]<g['date']:past.extend(by_date[days.pop(0)])
        if g['id'] not in joined or any((g['id'],g[s]) not in known for s in ('home','away')):continue
        factors=game_factors(g,past,by_game[g['id']],inputs['teams'],model,params)
        if factors is None:continue
        included.append({'g':int(g['id']),'d':g['date'],'mu':means[i].tolist(),'log_factors':factors,'goals':y[i*2:i*2+2].tolist(),'home_win':bool(actual[i])})
        if len(included)%100==0:print('Game calibration',year,len(included),flush=True)
    save_json(path,{'signature':signature,'games':included});return included


def metrics(rows,scale,temperature):
    mu=np.clip(np.array([r['mu'] for r in rows])*np.exp(scale*np.array([r['log_factors'] for r in rows])),.35,8);y=np.array([r['goals'] for r in rows]);outcomes=np.array([r['home_win'] for r in rows],dtype=float)
    p=np.array([probability(h,a,temperature)[0] for h,a in mu]);p=np.clip(p,1e-9,1-1e-9)
    return {'games':len(rows),'poisson_loss_per_team_game':float(np.mean(mu-y*np.log(mu))),'brier':float(np.mean((p-outcomes)**2)),
      'log_loss':float(np.mean(-outcomes*np.log(p)-(1-outcomes)*np.log(1-p)))}


def main():
    model=load_json(ROOT/'tools/playoffs/impact_parameters.json');inputs=load_json(ROOT/'.cache/playoffs/advanced/compact.json');params=config()
    train=dataset(2025,folded(model),inputs,params);test=dataset(2026,model,inputs,params)
    candidates=[(metrics(train,s,params['temperature'])['poisson_loss_per_team_game'],s) for s in np.arange(0,1.51,.1)]
    _,scale=min(candidates);scale=round(float(scale),2)
    report={'calibration_season':2025,'evaluation_season':2026,'goal_scale':scale,'baseline_2025':metrics(train,0,params['temperature']),
      'adjusted_2025':metrics(train,scale,params['temperature']),'baseline_2026':metrics(test,0,params['temperature']),'adjusted_2026':metrics(test,scale,params['temperature']),
      'evaluation_through':max(r['d'] for r in test),'scope':'Conditional on retrospectively observed dressed player identities; projected minutes use only earlier games. Historical injury-report forecasting and playoff calibration are not established.',
      'upstream':'2025 game-strength and shot-quality inputs are retrospectively fitted. 2026 is later than all fitted skater, finishing and game-scale coefficients.'}
    report['dataset_sha256']={str(year):load_json(CACHE/f'game-calibration-v1-{year}.json')['signature'] for year in (2025,2026)}
    target=np.array([r['home_win'] for r in test]);base=[];adjusted=[]
    for r in test:
        base.append(probability(*r['mu'],params['temperature'])[0])
        mu=np.array(r['mu'])*np.exp(scale*np.array(r['log_factors']));adjusted.append(probability(*mu,params['temperature'])[0])
    delta=(np.array(adjusted)-target)**2-(np.array(base)-target)**2
    rng=np.random.default_rng(90421);bootstrap=np.mean(delta[rng.integers(0,len(delta),(5000,len(delta)))],axis=1)
    report['paired_brier_delta_95pct_interval']=np.quantile(bootstrap,[.025,.975]).tolist()
    model['goal_scale']=scale;model['game_validation']=report;save_json(ROOT/'tools/playoffs/impact_parameters.json',model);print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
