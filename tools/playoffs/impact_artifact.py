"""Finish the offline impact release: shooting skill and compact usage priors."""
from collections import defaultdict
import base64
import math
import numpy as np
from impact_data import CACHE,ROOT,load_json,save_json
from data import canonical,TEAMS

ROLES=['ev','pp','pk']


def finishing(rows,prior,base=None):
    league=(sum(v[0] for v in rows.values())+prior)/(sum(v[1] for v in rows.values())+prior) if base is None else base
    return {p:(v[0]+prior*league)/(v[1]+prior) for p,v in rows.items()},league


def finisher_score(training,test,prior):
    ratings,league=finishing(training,prior)
    y=np.array([r[0] for r in test.values()]);mu=np.array([r[1]*ratings.get(p,league) for p,r in test.items()]);baseline=np.array([r[1]*league for r in test.values()])
    loss=lambda value:float(np.sum(value-y*np.log(np.maximum(value,1e-15))))/max(1,float(y.sum()))
    return {'goals':int(y.sum()),'players':len(test),'poisson_loss_per_goal':loss(mu),'baseline_loss_per_goal':loss(baseline)}


def main():
    model=load_json(ROOT/'tools/playoffs/impact_parameters.json');manifest=load_json(CACHE/'manifest.json')
    facts={};minutes={};supported=actual=0
    schedules={year:{g['id']:g for g in load_json(ROOT/f'.cache/playoffs/{year}.json')} for year in (2023,2024,2025)}
    for source in manifest['sources']:
        year=source['season'];facts[year]=[defaultdict(lambda:[0.,0.]) for _ in ROLES];minutes[year]=defaultdict(lambda:np.zeros(3))
        for gid in source['game_ids']:
            g=load_json(CACHE/'games'/f'{gid}.json.gz')
            for p,k,goals,xg in g['finishing']:
                facts[year][k][p][0]+=goals;facts[year][k][p][1]+=xg
            for t,p,*seconds in g['usage']:minutes[year][p]+=seconds
            if year<=2025:
                supported+=sum(sum(row[5]) for row in g['stints']);official=schedules[year][gid]
                actual+=official['hg']+official['ag']-int(official['end']=='SO')
    reports=[]
    for k,role in enumerate(ROLES):
        candidates=[]
        for prior in (16,64,256):
            score=finisher_score(facts[2023][k],facts[2024][k],prior);candidates.append((score['poisson_loss_per_goal'],prior))
        _,prior=min(candidates);train=defaultdict(lambda:[0.,0.])
        for year in (2023,2024):
            for p,v in facts[year][k].items():train[p][0]+=v[0];train[p][1]+=v[1]
        report={'role':role,'prior_expected_goals':prior,'evaluation_2025':finisher_score(train,facts[2025][k],prior)}
        for p,v in facts[2025][k].items():train[p][0]+=v[0];train[p][1]+=v[1]
        ratings,league=finishing(train,prior);report['evaluation_2026']=finisher_score(train,facts[2026][k],prior);reports.append(report)
        for p,record in model['players'].items():
            pid=int(p);xg=train.get(pid,[0,0])[1];seconds=sum(minutes[y][pid][k] for y in (2023,2024,2025));rate=xg*3600/max(seconds,1)
            effect=(ratings.get(pid,league)-league)*rate/model['rates'][role]
            record['chance_off_'+role]=record.get('chance_off_'+role,record['off_'+role]);record['finishing_'+role]=round(effect,7)
            record['off_'+role]=round(record['chance_off_'+role]+effect,7)
        print('Finishing',report,flush=True)
    history={};prior_usage=defaultdict(lambda:np.zeros(4))
    for year in (2023,2024,2025):
        rows=load_json(ROOT/f'.cache/playoffs/lines/games-{year}.json');games=defaultdict(set)
        for r in rows:games[canonical(r['team'])].add((r['g'],r['date']))
        clubs={t:{'games':sorted(games[t]),'players':{}} for t in TEAMS};lookups={t:{g:i for i,(g,d) in enumerate(c['games'])} for t,c in clubs.items()}
        for r in rows:
            team=canonical(r['team']);p=str(r['p']);c=clubs[team]['players'].setdefault(p,{'mask':0,'minutes':[0.,0.,0.],'gp':0,'ev':bytearray(len(clubs[team]['games']))})
            c['mask']|=1<<lookups[team][r['g']];c['gp']+=1
            c['ev'][lookups[team][r['g']]]=min(255,round((r.get('ev') or 0)/30))
            values=np.array([r.get('ev') or 0,r.get('pp') or 0,r.get('pk') or 0])/60
            c['minutes']=(np.array(c['minutes'])+values).tolist()
            prior_usage[p]+=np.r_[1,values]*{2023:.1,2024:.3,2025:.6}[year]
        for c in clubs.values():
            for record in c['players'].values():record['mask']=hex(record['mask']);record['minutes']=[round(v,3) for v in record['minutes']];record['ev']=base64.b64encode(record['ev']).decode()
        history[str(year)]=clubs
    replacement={}
    for pos in ('F','D'):
        eligible=[p for p,r in model['players'].items() if (r['position']=='D')==(pos=='D') and prior_usage[p][0]>=15]
        threshold=np.quantile([prior_usage[p][1]/prior_usage[p][0] for p in eligible],.25)
        selected=[p for p in eligible if prior_usage[p][1]/prior_usage[p][0]<=threshold]
        replacement[pos]={key:round(float(np.average([model['players'][p][key] for p in selected],weights=[prior_usage[p][0] for p in selected])),7) for key in ['off_'+k for k in ROLES]+['def_'+k for k in ROLES]}
        replacement[pos]['sample_players']=len(selected)
        replacement[pos]['usage_prior']=np.average([model['players'][p].get('usage_prior',prior_usage[p][1:]/prior_usage[p][0]) for p in selected],axis=0,weights=[prior_usage[p][0] for p in selected]).round(4).tolist()
    for p,r in model['players'].items():
        prior=prior_usage[p];r['usage_prior']=[round(v/max(prior[0],1),4) for v in prior[1:]];r['prior_gp']=round(float(prior[0]),3)
    model['finishing_validation']=reports;model['replacement']=replacement;model['modeled_regulation_goal_share']=round(supported/max(actual,1),6)
    model['usage_history']=history
    save_json(ROOT/'tools/playoffs/impact_parameters.json',model)
    print('Impact release enriched; modeled regulation goal share',model['modeled_regulation_goal_share'],flush=True)


if __name__=='__main__':main()
