"""Chronological model fitting; SciPy is needed only to regenerate coefficients.

Example: python tools/playoffs/fit_advanced.py --inputs compact.json
The 2025-26 season is scored after selection on 2024-25. Historical MoneyPuck
shot-model vintages are retrospective, so the report does not claim a fully
untouched end-to-end holdout or superiority to sportsbooks.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

from scipy.optimize import minimize
from scipy.special import logsumexp
from data import schedules, TEAMS
from model import parameters
from validate_history import metrics,walk_forward
from strength_v2 import Goalies,design,PARAMETERS,STARTER_PARAMETERS,FEATURES,urgency


def game_probabilities(rates,temperature=1):
    home,away=rates[::2],rates[1::2]
    middle=np.sqrt(home*away);ratio=(home/away)**(.5/temperature);home,away=middle*ratio,middle/ratio
    hp=np.empty((len(home),40));ap=np.empty_like(hp);hp[:,0]=np.exp(-home);ap[:,0]=np.exp(-away)
    for n in range(1,40):
        hp[:,n]=hp[:,n-1]*home/n;ap[:,n]=ap[:,n-1]*away/n
    return (hp*(np.cumsum(ap,axis=1)-ap)).sum(axis=1)+(hp*ap).sum(axis=1)*home/(home+away)


def fit_goals(x,y,alpha):
    mean=x.mean(axis=0);scale=np.maximum(x.std(axis=0),.05);z=(x-mean)/scale
    def objective(v):
        eta=np.clip(v[0]+z@v[1:],-8,4);mu=np.exp(eta)
        loss=np.mean(mu-y*eta)+alpha*np.sum(v[1:]**2)/2
        residual=mu-y
        gradient=np.r_[residual.mean(),z.T@residual/len(y)+alpha*v[1:]]
        return loss,gradient
    bounds=[(None,None)]+[(0,None)]*8+[(None,0),(0,None),(None,0),(0,None),(0,None),(None,0)]
    result=minimize(objective,np.r_[np.log(y.mean()),np.zeros(x.shape[1])],jac=True,bounds=bounds,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-11})
    if not result.success:
        raise ValueError('Goal fit failed: '+result.message)
    return {'intercept':float(result.x[0]),'coefficients':result.x[1:].tolist(),'mean':mean.tolist(),'scale':scale.tolist()}


def predict(x,p):
    return np.clip(np.exp(p['intercept']+((x-p['mean'])/p['scale'])@p['coefficients']),.35,8)


def starter_dataset(goalies,games):
    starts={(r['g'],r['t']):r['p'] for r in goalies.rows if r.get('st')==1}
    x=[];labels=[];offsets=[];actuals=[];candidates=[]
    gp=np.zeros(32);points=np.zeros(32);pending=[];last_day=None;indices={t:i for i,t in enumerate(TEAMS)}
    for g in games:
        if g['date']!=last_day:
            for previous in pending:
                for team,win in [(previous['home'],previous['hg']>previous['ag']),(previous['away'],previous['ag']>previous['hg'])]:
                    i=indices[team];gp[i]+=1;points[i]+=2 if win else int(previous['end']!='REG')
            pending=[];last_day=g['date']
        for side in ['home','away']:
            team=g[side];actual=starts.get((g['id'],team))
            if not actual:
                continue
            importance=urgency(team,gp,points)
            result=goalies.project(team,g['date'],home=side=='home' and not g['neutral'],importance=importance,include_unknown=True)
            ids=[r['id'] for r in result['players']]
            offsets.append(len(x));actuals.append(actual)
            for player in ids:
                x.append(goalies.starter_features(player,team,g['date'],side=='home' and not g['neutral'],importance,len(ids)))
                labels.append(int(player==(actual if actual in ids else 0)));candidates.append(player)
        pending.append(g)
    return {'x':np.array(x),'y':np.array(labels),'offsets':np.array(offsets),'actual':np.array(actuals),'players':np.array(candidates)}


def fit_starter(d,alpha):
    x=d['x'];mean=x.mean(axis=0);scale=np.maximum(x.std(axis=0),.05);z=(x-mean)/scale
    starts=d['offsets'];counts=np.diff(np.r_[starts,len(x)]);groups=np.repeat(np.arange(len(starts)),counts)
    def objective(w):
        scores=z@w;maximum=np.maximum.reduceat(scores,starts);e=np.exp(scores-maximum[groups]);total=np.add.reduceat(e,starts);prob=e/total[groups]
        loss=float((np.log(total)+maximum).sum()-(scores*d['y']).sum())/len(starts)+alpha*float(w@w)/2
        return loss,z.T@(prob-d['y'])/len(starts)+alpha*w
    bounds=[(0,None),(None,None),(0,None),(0,None),(None,None),(0,None),(0,None),(None,None),(None,None),(None,None),(None,None)]
    result=minimize(objective,np.zeros(x.shape[1]),jac=True,bounds=bounds,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-10})
    if not result.success:
        raise ValueError('Starter fit failed')
    return {'coefficients':result.x.tolist(),'mean':mean.tolist(),'scale':scale.tolist()}


def starter_metrics(d,p):
    scores=((d['x']-p['mean'])/p['scale'])@p['coefficients'];loss=0;correct=0;covered=0
    for i,start in enumerate(d['offsets']):
        end=d['offsets'][i+1] if i+1<len(d['offsets']) else len(scores)
        s=scores[start:end];y=d['y'][start:end];loss+=float(logsumexp(s)-s[y.astype(bool)][0])
        picked=d['players'][start+int(np.argmax(s))];correct+=picked==d['actual'][i]
        covered+=d['actual'][i] in d['players'][start:end]
    return {'team_games':len(d['offsets']),'log_loss':loss/len(d['offsets']),'named_starter_accuracy':correct/len(d['offsets']),'candidate_coverage':covered/len(d['offsets'])}


def join_starter(datasets):
    x=[];y=[];offsets=[];players=[];actual=[];size=0
    for d in datasets:
        x.append(d['x']);y.append(d['y']);offsets.extend((d['offsets']+size).tolist());players.append(d['players']);actual.append(d['actual']);size+=len(d['x'])
    return {'x':np.concatenate(x),'y':np.concatenate(y),'offsets':np.array(offsets),'players':np.concatenate(players),'actual':np.concatenate(actual)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True);args=parser.parse_args()
    inputs=json.loads(args.inputs.read_text());games={year:schedules(year,True) for year in range(2021,2026)}
    goalies=Goalies(inputs['goalies'],inputs.get('births'));goalies.starter_parameters=None
    starters={year:starter_dataset(goalies,games[year]) for year in range(2021,2026)}
    training=join_starter([starters[2022],starters[2023]])
    choices=[]
    for alpha in [.005,.02,.1]:
        p=fit_starter(training,alpha);score=starter_metrics(starters[2024],p);choices.append((score['log_loss'],alpha))
    _,starter_alpha=min(choices);before=fit_starter(join_starter([starters[y] for y in [2021,2022,2023,2024]]),starter_alpha)
    report=starter_metrics(starters[2025],before)
    final=fit_starter(join_starter([starters[y] for y in [2021,2022,2023,2024,2025]]),starter_alpha)
    final.update(version=1,alpha=starter_alpha,training_seasons=[2021,2022,2023,2024,2025],retrospective_evaluation={'season':2025,**report})
    STARTER_PARAMETERS.write_text(json.dumps(final,indent=2)+'\n');print('Starter evaluation:',json.dumps(report),flush=True)
    # Cross-fit the upstream starter predictor: every game season gets a model
    # trained on earlier seasons only, including during downstream model fitting.
    goalie_folds={}
    for year in range(2022,2026):
        fold=Goalies(inputs['goalies'],inputs.get('births'))
        fold.starter_parameters=fit_starter(join_starter([starters[y] for y in range(2021,year)]),starter_alpha)
        goalie_folds[year]=fold
    candidates=[];all_design={}
    for prior in [5,15,30]:
        for half in [15,30,60]:
            datasets={year:design(year,games[year],inputs,prior,half,goalie_folds[year]) for year in [2022,2023,2024]}
            all_design[(prior,half)]=datasets
            train_x=np.concatenate([datasets[y][0] for y in [2022,2023]]);train_y=np.concatenate([datasets[y][1] for y in [2022,2023]])
            for alpha in [.01,.05,.2]:
                p=fit_goals(train_x,train_y,alpha)
                for temperature in [1,1.2,1.5]:
                    probabilities=game_probabilities(predict(datasets[2024][0],p),temperature)
                    score=float(np.mean((probabilities-datasets[2024][3])**2))
                    candidates.append((score,prior,half,alpha,temperature))
            print('Selected-grid stage',prior,half,flush=True)
    val,prior,half,alpha,temperature=min(candidates)
    datasets=all_design[(prior,half)];x=np.concatenate([datasets[y][0] for y in [2022,2023,2024]]);y=np.concatenate([datasets[y][1] for y in [2022,2023,2024]])
    fitted=fit_goals(x,y,alpha);test=design(2025,games[2025],inputs,prior,half,goalie_folds[2025])
    probs=game_probabilities(predict(test[0],fitted),temperature);scores=metrics(np.column_stack([probs,test[3]]))
    baseline=metrics(walk_forward(2025,games[2025],games[2023]+games[2024],parameters()))
    production=fit_goals(np.concatenate([x,test[0]]),np.concatenate([y,test[1]]),alpha)
    production.update(version=2,model='sweater-xg-v2',prior_games=prior,half_life=half,alpha=alpha,temperature=temperature,features=FEATURES,
                      training_seasons=[2022,2023,2024,2025],validation={'selection_season':2024,'selection_brier':val,'evaluation_season':2025,'new':scores,'baseline':baseline,
                       'limitations':['Retrospectively rebuilt expected-goal values; not an untouched end-to-end holdout.','No independently validated skater injury-impact coefficient.','Game-win validation does not establish playoff-probability calibration.']})
    PARAMETERS.write_text(json.dumps(production,indent=2)+'\n')
    print('Game model:',json.dumps({'prior':prior,'half_life':half,'alpha':alpha,'temperature':temperature,'validation':val,'new':{k:v for k,v in scores.items() if k!='reliability'},'baseline':{k:v for k,v in baseline.items() if k!='reliability'}}),flush=True)


if __name__=='__main__':
    main()
