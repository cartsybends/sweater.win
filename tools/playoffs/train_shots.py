"""Train Sweater's compact shot model from listed MoneyPuck factual shot files.

No MoneyPuck predicted probabilities are features or targets. Fit 2023/2024,
calibrate 2025, and evaluate the untouched 2026 snapshot. Training stays offline;
Cloudflare receives only the small coefficients and validation report.
"""
import argparse,csv,hashlib,io,json,math,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import numpy as np

TYPES=['BACK','SNAP','SLAP','TIP','DEFL','WRAP','UNKNOWN']
NAMES=['intercept','distance','log_distance','angle','angle_squared','distance_angle','empty_net','empty_net_distance','rebound','rebound_distance','skater_advantage','attacking_three','defending_three']+['type_'+x.lower() for x in TYPES]

def features(x,y,kind,attack,defend,empty,rebound):
    distance=math.hypot(89-x,y);angle=abs(math.atan2(y,89-x))/math.pi*2;d=distance/60
    return [1,d,math.log1p(distance)/4,angle,angle*angle,d*angle,int(empty),int(empty)*d,int(rebound),int(rebound)*d,(attack-defend)/2,int(attack==3),int(defend==3)]+[int(kind==t) for t in TYPES]

def load(path):
    xs=[];ys=[];groups=[];excluded=Counter()
    with zipfile.ZipFile(path) as archive:
        members=[n for n in archive.namelist() if n.endswith('.csv')]
        if len(members)!=1:raise ValueError('Unexpected shot archive')
        with archive.open(members[0]) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig')):
                try:
                    if int(float(row['isPlayoffGame'])) or int(row['period'])>4 or row['event'] not in {'SHOT','MISS','GOAL'}:
                        excluded['outside_regular_game_shots']+=1;continue
                    x=float(row['xCordAdjusted']);y=float(row['yCordAdjusted'])
                    if not math.isfinite(x+y) or abs(x)>100 or abs(y)>43 or x==y==0:
                        excluded['unlocated']+=1;continue
                    home=int(float(row['isHomeTeam']));home_count=int(row['homeSkatersOnIce']);away_count=int(row['awaySkatersOnIce'])
                    attack,defend=(home_count,away_count) if home else (away_count,home_count)
                    if not 3<=attack<=6 or not 3<=defend<=6:
                        excluded['unsupported_strength']+=1;continue
                    kind=row['shotType'] if row['shotType'] in TYPES+['WRIST'] else 'UNKNOWN'
                    empty=int(row['shotOnEmptyNet']);rebound=int(row['shotRebound']);goal=int(row['goal'])
                    if any(n not in (0,1) for n in [home,empty,rebound,goal]):raise ValueError()
                    xs.append(features(x,y,kind,attack,defend,empty,rebound));ys.append(goal);groups.append(empty)
                except (KeyError,ValueError,TypeError):excluded['invalid_row']+=1
    return np.asarray(xs,dtype=float),np.asarray(ys,dtype=float),np.asarray(groups),dict(excluded)

def sigmoid(value):return 1/(1+np.exp(-np.clip(value,-35,35)))

def fit(x,y,ridge=.0001):
    w=np.zeros(x.shape[1]);w[0]=math.log(y.mean()/(1-y.mean()));penalty=np.ones(x.shape[1])*ridge;penalty[0]=0
    for _ in range(40):
        p=sigmoid(x@w);loss=np.mean(np.logaddexp(0,x@w)-y*(x@w))+np.dot(penalty,w*w)/2
        gradient=x.T@(p-y)/len(y)+penalty*w;hessian=(x.T*(p*(1-p)))@x/len(y)+np.diag(penalty)+np.eye(x.shape[1])*1e-10
        delta=np.linalg.solve(hessian,gradient);step=1
        while step>1/1024:
            candidate=w-step*delta;z=x@candidate;next_loss=np.mean(np.logaddexp(0,z)-y*z)+np.dot(penalty,candidate*candidate)/2
            if next_loss<=loss:break
            step/=2
        w=candidate
        if np.max(np.abs(step*delta))<1e-7:break
    return w

def metrics(y,p):
    p=np.clip(p,.0001,.995);order=np.argsort(p,kind='stable');sorted_p=p[order];ranks=np.empty(len(p),dtype=float)
    start=0
    while start<len(p):
        end=start+1
        while end<len(p) and sorted_p[end]==sorted_p[start]:end+=1
        ranks[order[start:end]]=(start+1+end)/2;start=end
    positives=y.sum();auc=(ranks[y==1].sum()-positives*(positives+1)/2)/(positives*(len(y)-positives))
    bins=[];ece=0
    for i in range(10):
        mask=(p>=i/10)&(p<(i+1)/10)
        if not mask.any():continue
        predicted=float(p[mask].mean());observed=float(y[mask].mean());count=int(mask.sum());ece+=count/len(y)*abs(predicted-observed)
        bins.append({'from':i/10,'through':(i+1)/10,'n':count,'predicted':round(predicted,5),'observed':round(observed,5)})
    return {'n':len(y),'goals':int(y.sum()),'brier':round(float(np.mean((p-y)**2)),6),'log_loss':round(float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),6),'auc':round(float(auc),6),'mean_prediction':round(float(p.mean()),6),'goal_rate':round(float(y.mean()),6),'ece':round(float(ece),6),'calibration':bins}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);parser.add_argument('--out',type=Path,default=Path('backend/src/shot-model.mjs'));args=parser.parse_args()
    inputs={};audits=[]
    for year in [2023,2024,2025,2026]:
        path=args.data/f'shots_{year}.zip';inputs[year]=load(path);audits.append({'season':year,'url':f'https://peter-tanner.com/moneypuck/downloads/shots_{year}.zip','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'included':len(inputs[year][1]),'excluded':inputs[year][3]})
        print('Loaded',year,len(inputs[year][1]),flush=True)
    train_x=np.concatenate([inputs[y][0] for y in [2023,2024]]);train_y=np.concatenate([inputs[y][1] for y in [2023,2024]])
    weights=fit(train_x,train_y);cal_x,cal_y,_,_=inputs[2025];cal_z=cal_x@weights;calibration=fit(np.column_stack([np.ones(len(cal_z)),cal_z]),cal_y,ridge=.00001)
    if not 0<calibration[1]<3:raise ValueError('Invalid probability calibration')
    test_x,test_y,empty,_=inputs[2026];predicted=np.clip(sigmoid(calibration[0]+calibration[1]*(test_x@weights)),.0001,.995)
    result=metrics(test_y,predicted);baseline=metrics(test_y,np.full(len(test_y),train_y.mean()));subgroups={}
    for key,mask in [('goalie_in_net',empty==0),('empty_net',empty==1)]:
        if mask.sum()>100:subgroups[key]=metrics(test_y[mask],predicted[mask])
    if result['n']<10000 or result['auc']<.7 or result['brier']>=baseline['brier'] or result['log_loss']>=baseline['log_loss'] or abs(result['mean_prediction']-result['goal_rate'])>.015 or result['ece']>.025:
        raise ValueError('Shot model failed held-out release gates: '+json.dumps(result))
    model={'version':'sweater-shot-v1','built_at':datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),'features':NAMES,'weights':[round(float(w),10) for w in weights],'calibration':[round(float(w),10) for w in calibration],'probability_bounds':[.0001,.995],
           'training_seasons':[2023,2024],'calibration_season':2025,'evaluation_season':2026,'validation':result,'baseline':baseline,'subgroups':subgroups,'inputs':audits,'source':'MoneyPuck.com factual shot data','source_url':'https://moneypuck.com/data.htm','limitations':['Average-goalie shot estimate; no individual shooter or goalie adjustment.','Released domain: located offensive-half unblocked attempts with a goalie in net; no empty-net, own-half, blocked-shot or shootout estimates.','Current-season validation is a snapshot and does not establish future accuracy.']}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text('// Generated by tools/playoffs/train_shots.py; raw data remains outside the repository.\nexport const SHOT_MODEL='+json.dumps(model,separators=(',',':'))+';\n')
    (args.data/'shot-validation.json').write_text(json.dumps(model,indent=2));print('Held-out validation',json.dumps(result),flush=True);print('Baseline',json.dumps(baseline),flush=True)

if __name__=='__main__':main()
