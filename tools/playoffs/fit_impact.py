"""Offline regularized, teammate/opponent-adjusted skater chance impact.

Fits use only earlier seasons than evaluation. Runtime consumes the small JSON
artifact, never SciPy or historical shifts. Scores are conditional on observed
on-ice personnel, not a retrospective claim of known pregame injury reports.
"""
from collections import Counter, defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.optimize import minimize

from data import TEAMS,canonical
from impact_data import CACHE,ROOT,load_json,save_json,sha

ROLES=['ev','pp','pk']
BASE=70


def roster_index():
    players={}
    for year in range(2023,2027):
        for r in load_json(ROOT/f'.cache/playoffs/lines/games-{year}.json'):
            players[r['p']]={'id':r['p'],'name':r['name'],'position':r['pos']}
    return players


def design(year,pids):
    path=CACHE/f'design-v2-{year}.npz';meta=path.with_suffix('.json')
    manifest=load_json(CACHE/'manifest.json');source=next(s for s in manifest['sources'] if s['season']==year)
    signature=hashlib.sha256(json.dumps({'pids':pids,'source':source,'shot_model_sha256':manifest['shot_model_sha256'],'design_version':2},sort_keys=True).encode()).hexdigest()
    if path.exists() and meta.exists() and load_json(meta).get('signature')==signature:
        z=np.load(path);return {'x':sparse.csr_matrix((z['data'],z['indices'],z['indptr']),shape=tuple(z['shape'])),'y':z['y'],'hours':z['hours'],'role':z['role'],'games':z['games'],'meta':load_json(meta)}
    index={p:i for i,p in enumerate(pids)};clubs={t:i for i,t in enumerate(TEAMS)}
    rows=[];cols=[];values=[];ys=[];hours=[];roles=[];gids=[];usage=defaultdict(lambda:np.zeros(3));audit=Counter();count=0
    included=set(source['game_ids'])
    for path_game in sorted((CACHE/'games').glob(f'{year}*.json.gz')):
        g=load_json(path_game);audit.update(g['audit'])
        if g.get('version')!=2 or g['g'] not in included:continue
        if not g['stints'] or g['audit'].get('verified_seconds',0)<2400:continue
        for team,p,*seconds in g['usage']:
            usage[(team,p)]+=np.array(seconds)
        # Repeated membership within one game can be combined without losing
        # the exposure, score-state or teammate/opponent controls.
        groups=defaultdict(lambda:np.zeros(2))
        for start,end,home,away,xg,goals,score in g['stints']:
            for is_home,own,opp,y,t,other in [(True,home,away,xg[0],g['h'],g['a']),(False,away,home,xg[1],g['a'],g['h'])]:
                role=0 if len(own)==len(opp) else 1 if len(own)>len(opp) else 2
                key=(is_home,t,other,tuple(own),tuple(opp),max(-2,min(2,score if is_home else -score)),role)
                groups[key]+=np.array([end-start,y])
        for (home,t,other,own,opp,score,role),(seconds,y) in groups.items():
            feature={0:1.,1+clubs[t]:1.,33+clubs[other]:1.,65:1. if home else -1.}
            if score:feature[66+[-2,-1,1,2].index(score)]=1.
            for p in own:feature[BASE+index[p]]=1.
            for p in opp:feature[BASE+len(pids)+index[p]]=1.
            for j,v in feature.items():rows.append(count);cols.append(j);values.append(v)
            ys.append(y);hours.append(seconds/3600);roles.append(role);gids.append(g['g']);count+=1
    x=sparse.coo_matrix((np.array(values,dtype=np.float64),(rows,cols)),shape=(count,BASE+2*len(pids))).tocsr()
    output={'x':x,'y':np.array(ys),'hours':np.array(hours),'role':np.array(roles,dtype=np.int8),'games':np.array(gids,dtype=np.int64),
      'meta':{'year':year,'pids':pids,'signature':signature,'audit':dict(audit),'usage':[[t,p,*v.tolist()] for (t,p),v in usage.items()]}}
    np.savez_compressed(path,data=x.data,indices=x.indices,indptr=x.indptr,shape=x.shape,y=output['y'],hours=output['hours'],role=output['role'],games=output['games'])
    save_json(meta,output['meta']);print('Design',year,x.shape,'nonzero',x.nnz,flush=True)
    return output


def subset(data,role):
    mask=data['role']==role
    return {k:(v[mask] if k in ('x','y','hours','games') else v) for k,v in data.items() if k!='role'}


def combine(parts):
    return {'x':sparse.vstack([p['x'] for p in parts],format='csr'),**{k:np.concatenate([p[k] for p in parts]) for k in ('y','hours','games')}}


def fit(d,alpha,baseline=False,start=None):
    x=d['x'][:,:BASE] if baseline else d['x'];y=d['y'];hours=d['hours'];penalty=np.full(x.shape[1],alpha);penalty[:BASE]=20;penalty[65:BASE]=2;penalty[0]=0
    if start is None:start=np.zeros(x.shape[1]);start[0]=np.log(y.sum()/hours.sum())
    scale=max(1,float(y.sum()))
    def objective(beta):
        eta=np.asarray(x@beta);mu=np.exp(np.clip(eta,-8,6))*hours
        loss=float((mu-y*eta).sum()+.5*np.dot(penalty,beta*beta))/scale
        grad=(np.asarray(x.T@(mu-y)).ravel()+penalty*beta)/scale
        return loss,grad
    result=minimize(objective,start,jac=True,method='L-BFGS-B',options={'maxiter':350,'ftol':1e-10,'gtol':1e-7,'maxcor':20})
    if not result.success:raise ValueError('Impact fit failed: '+result.message)
    print('Fit',len(y),'alpha',alpha,'baseline',baseline,'iterations',result.nit,flush=True)
    return result.x


def score(d,beta):
    x=d['x'][:,:len(beta)];mu=np.exp(np.clip(np.asarray(x@beta),-8,6))*d['hours'];y=d['y'];n=max(float(y.sum()),1)
    deviance=2*float(np.sum(mu-y+np.where(y>0,y*np.log(np.maximum(y,1e-20)/np.maximum(mu,1e-20)),0)))
    return {'rows':len(y),'games':len(set(d['games'].tolist())),'xg':round(float(y.sum()),6),'hours':round(float(d['hours'].sum()),3),
      'poisson_deviance_per_xg':deviance/n,'poisson_loss_per_hour':float(np.sum(mu-y*np.log(np.maximum(mu,1e-20))))/d['hours'].sum()}


def main():
    players=roster_index();pids=sorted(players);datasets={year:design(year,pids) for year in range(2023,2027)}
    release={};reports=[];early={};fold={};penalties={}
    for role,name in enumerate(ROLES):
        d={year:subset(data,role) for year,data in datasets.items()};candidates=[]
        for alpha in (32,128,512):
            beta=fit(d[2023],alpha);s=score(d[2024],beta);candidates.append((s['poisson_deviance_per_xg'],alpha,beta));print('Tune',name,alpha,s,flush=True)
        _,alpha,early[name]=min(candidates,key=lambda row:row[0]);penalties[name]=alpha
        train=combine([d[2023],d[2024]]);beta=fit(train,alpha);baseline=fit(train,alpha,True)
        reports.append({'role':name,'penalty':alpha,'evaluation_2025':score(d[2025],beta),'baseline_2025':score(d[2025],baseline)})
        fold[name]=beta.tolist();production=fit(combine([train,d[2025]]),alpha,start=beta);release[name]=production.tolist()
        baseline_current=fit(combine([train,d[2025]]),alpha,True)
        reports[-1].update(evaluation_2026=score(d[2026],production),baseline_2026=score(d[2026],baseline_current))
        print('Impact role evaluation',name,json.dumps(reports[-1]),flush=True)
    usage=defaultdict(lambda:np.zeros(3));count=defaultdict(lambda:np.zeros(3))
    for year in (2023,2024,2025):
        for team,p,*seconds in datasets[year]['meta']['usage']:
            usage[p]+=np.array(seconds);count[p]+=np.array(seconds)>0
    roster={}
    for i,p in enumerate(pids):
        effects={}
        for role,name in enumerate(ROLES):
            beta=release[name];defending=0 if role==0 else 3-role
            effects['off_'+name]=round(beta[BASE+i],7);effects['def_'+ROLES[defending]]=round(beta[BASE+len(pids)+i],7)
        roster[str(p)]={**players[p],**effects,'training_minutes':dict(zip(ROLES,(usage[p]/60).round(1).tolist()))}
    output={'version':'sweater-skater-impact-v1','built_at':datetime.now(timezone.utc).isoformat(),'trained_through':'2026-06-30',
      'training_seasons':[2023,2024,2025],'tuning_season':2024,'evaluation_season':2026,
      'roles':ROLES,'players':roster,'rates':{name:float(np.exp(release[name][0])) for name in ROLES},'validation':reports,
      'penalties':penalties,'inputs':load_json(CACHE/'manifest.json'),
      'method':'Ridge Poisson adjusted on-ice shot-quality impact, separate EV/PP/PK offense and defense; club, opponent, home and score controls',
      'limitations':['Conditional on verified observed personnel and NHL shifts.','Source shot-quality model is retrospective; current-season evaluation uses only prior-season coefficients.','Historical injury-report timestamps are not reconstructed.','Individual effects are regularized estimates, not isolated causal guarantees.']}
    save_json(CACHE/'coefficients-fold.json',{'pids':pids,'early':{k:v.tolist() for k,v in early.items()},'fold':fold,'release':release})
    save_json(ROOT/'tools/playoffs/impact_parameters.json',output)
    print('Published impact coefficients',len(roster),flush=True)


if __name__=='__main__':main()
