"""Runtime skater-availability adjustment; NumPy only, no online model fitting.

Team ratings already reflect historical availability. Corrections compare the
projected lineup with that embedded exposure, not with a second full-strength
team rating. Return-date windows are scenario assumptions, not medical models.
"""
from collections import defaultdict
from datetime import date,datetime,timedelta
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo
import base64
import hashlib
import json
import math
import numpy as np

from data import canonical

PARAMETERS=Path(__file__).with_name('impact_parameters.json')
ROLES=('ev','pp','pk')
KEYS=tuple('off_'+r for r in ROLES)+tuple('def_'+r for r in ROLES)
OUT={'out','injured reserve','ir','ir-lt','long-term injured reserve','suspended','suspension'}


def waterfill(weights,total,cap):
    weights=np.maximum(np.asarray(weights,dtype=float),.001);cap=np.broadcast_to(np.asarray(cap,dtype=float),weights.shape)
    result=np.zeros(len(weights));left=float(total);active=np.ones(len(weights),dtype=bool)
    for _ in range(len(weights)+1):
        if not active.any() or left<1e-9:break
        proposed=left*weights[active]/weights[active].sum();indices=np.flatnonzero(active);room=cap[active]-result[active]
        if np.all(proposed<=room+1e-9):result[active]+=proposed;left=0;break
        full=indices[proposed>=room];amount=cap[full]-result[full];result[full]=cap[full];left-=float(amount.sum());active[full]=False
    if left>.0001:raise ValueError('Insufficient replacement ice-time capacity')
    return result


def return_window(injury,today):
    current=date.fromisoformat(today)
    try:estimate=date.fromisoformat(injury.get('return_estimate','')[:10])
    except (TypeError,ValueError):estimate=None
    if estimate and estimate>current:
        return max(current+timedelta(days=1),estimate-timedelta(days=7)).toordinal(),(estimate+timedelta(days=7)).toordinal(),'reported estimate ±7 days'
    return (current+timedelta(days=1 if estimate else 7)).toordinal(),(current+timedelta(days=14 if estimate else 28)).toordinal(),'uncertain return window'


class Team:
    def __init__(self,club,roster,injuries,rows,advanced,model,today,prior_games,half_life):
        self.club=club;self.model=model;self.today=today;self.rows=rows;self.draws={};self.forecasts={};self.windows=[]
        self.season=int(today[:4])-(int(today[5:7])<7)
        by_player=defaultdict(list)
        for row in sorted(rows,key=lambda r:(r['date'],r['g'])):by_player[row['p']].append(row)
        self.by_player=by_player;self.pool={};self.missing=[]
        self.role_minutes=np.mean([[r['v'][6]/60,r['v'][8]/60,r['v'][10]/60] for r in sorted(advanced,key=lambda r:(r['d'],r['g']))[-10:]],axis=0) if advanced else np.array(model.get('role_minutes',[48,5,5]),dtype=float)
        self.role_minutes=np.maximum(self.role_minutes,.1)
        for p in roster:
            if p.get('position')=='goalies':continue
            self.pool[p['id']]=self.player(p['id'],p['name'],'D' if p.get('position')=='defensemen' else 'F')
        for injury in injuries:
            if str(injury.get('status','')).lower() not in OUT:continue
            pid=injury.get('player_id')
            if not isinstance(pid,int):continue
            if pid not in self.pool:
                previous=by_player.get(pid,[])
                if not previous or canonical(previous[-1]['team'])!=club:continue
                self.pool[pid]=self.player(pid,injury['name'],'D' if previous[-1]['pos']=='D' else 'F')
            self.missing.append({**injury,'id':pid})
        self.missing=sorted({r['id']:r for r in self.missing}.values(),key=lambda r:-float(self.pool[r['id']]['usage'].sum()))
        self.fixed={r['id'] for r in self.missing[8:]};self.missing=self.missing[:8]
        self.k=len(self.missing);self.bits=np.array(list(product((0,1),repeat=self.k)),dtype=np.int8) if self.k else np.zeros((1,0),dtype=np.int8)
        self.masks=self.bits@(1<<np.arange(self.k,dtype=np.int64))
        # Lexicographic product order is not integer-mask order; use direct mask
        # indexing consistently for simulation lookups and exact mixtures.
        self.bits=self.bits[np.argsort(self.masks)];self.masks=np.arange(1<<self.k)
        self.profiles=[];self.assignments=[]
        for mask in self.masks:
            missing=self.fixed|{r['id'] for i,r in enumerate(self.missing) if mask&(1<<i)}
            profile,assignments=self.profile(missing);self.profiles.append(profile);self.assignments.append(assignments)
        self.profiles=np.array(self.profiles);self.factors=np.exp(self.profiles-self.profiles[0]);self.embedded=np.ones(6)
        if self.k:self.embedded=self.reference(prior_games,half_life)
        for r in self.missing:self.windows.append(return_window(r,today))

    def player(self,pid,name,position):
        r=self.model['players'].get(str(pid));replacement=self.model['replacement'][position]
        known=r and r['training_minutes']['ev']>=150
        coefficients=np.array([r[key] if known else replacement[key] for key in KEYS])
        prior=np.array(r.get('usage_prior',replacement['usage_prior']) if r else replacement['usage_prior'],dtype=float)
        history=self.by_player.get(pid,[]);observed=[row for row in history if row['seconds']>0]
        if observed:
            values=np.array([[row.get(key) or 0 for key in ('ev','pp','pk')] for row in observed])/60
            value=.6*values[-5:].mean(axis=0)+.4*values.mean(axis=0);weight=min(1,len(values)/10);prior=weight*value+(1-weight)*prior
        return {'id':pid,'name':name,'position':position,'coefficients':coefficients,'usage':np.maximum(prior,.001),'known':bool(known)}

    def profile(self,missing):
        available=[p for pid,p in self.pool.items() if pid not in missing];selected=[]
        for position,count in [('F',12),('D',6)]:
            group=sorted([p for p in available if p['position']==position],key=lambda p:(-p['usage'][0],p['id']))[:count]
            for i in range(count-len(group)):
                r=self.model['replacement'][position];group.append({'id':-(i+1)-(0 if position=='F' else 20),'name':'Replacement-level '+('forward' if position=='F' else 'defenseman'),
                  'position':position,'usage':np.array(r['usage_prior']),'coefficients':np.array([r[k] for k in KEYS]),'known':False})
            selected.extend(group)
        minutes=np.zeros((18,3));values=np.array([p['coefficients'] for p in selected])
        for pos,n in [('F',3),('D',2)]:
            indices=[i for i,p in enumerate(selected) if p['position']==pos]
            minutes[indices,0]=waterfill([selected[i]['usage'][0] for i in indices],n*self.role_minutes[0],min(self.role_minutes[0],24 if pos=='F' else 32))
        for k,n in [(1,5),(2,4)]:minutes[:,k]=waterfill([p['usage'][k] for p in selected],n*self.role_minutes[k],self.role_minutes[k])
        profile=np.r_[np.sum(values[:,:3]*minutes,axis=0)/self.role_minutes,np.sum(values[:,3:]*minutes,axis=0)/self.role_minutes]
        return profile,{p['id']:minutes[i] for i,p in enumerate(selected)}

    def mixture(self,probabilities):
        if not self.k:return np.ones(1)
        p=np.asarray(probabilities);return np.prod(np.where(self.bits,p,1-p),axis=1)

    def reference(self,prior_games,half_life):
        before=[]
        affiliation={}
        for r in self.missing:
            pid=r['id'];earliest=min((x['date'] for x in self.by_player.get(pid,[]) if canonical(x['team'])==self.club),default='9999')
            prior_clubs=self.model['usage_history'].get(str(self.season-1),{});last=None
            for club,c in prior_clubs.items():
                player=c['players'].get(str(pid))
                if not player:continue
                mask=int(player['mask'],16)
                if mask:
                    seen=(c['games'][mask.bit_length()-1][1],club)
                    if last is None or seen>last:last=seen
            # A returning skater who finished last year at this club may have
            # missed every current game. No appearance is not evidence of health.
            if last and last[1]==self.club:earliest=f'{self.season}-07-01'
            affiliation[pid]=earliest
        for year,clubs in self.model['usage_history'].items():
            c=clubs.get(self.club);weight={1:.6,2:.3,3:.1}.get(self.season-int(year),0)
            if not c or not weight:continue
            exposures=[]
            for i,_ in enumerate(c['games']):
                unavailable=[]
                for r in self.missing:
                    p=c['players'].get(str(r['id']));expected=self.assignments[0].get(r['id'],np.zeros(3))[0]
                    if not p or expected<1:unavailable.append(0.);continue
                    actual=base64.b64decode(p['ev'])[i]/2
                    unavailable.append(1-min(1,actual/expected))
                exposures.append(self.mixture(unavailable)@self.factors)
            before.append((weight,np.mean(exposures,axis=0)))
        prior=(.65*sum(w*v for w,v in before)/sum(w for w,_ in before)+.35) if before else np.ones(6)
        numerator=prior*prior_games;denominator=float(prior_games);decay=2**(-1/half_life)
        groups=defaultdict(dict)
        for r in self.rows:
            if canonical(r['team'])==self.club:groups[(r['date'],r['g'])][r['p']]=r
        for game_key,players in sorted(groups.items()):
            probabilities=[]
            for r in self.missing:
                expected=self.assignments[0].get(r['id'],np.zeros(3))[0];actual=(players.get(r['id'],{}).get('ev') or 0)/60
                # No past affiliation is not proof of a past injury. Returning
                # current-roster players are compared only after joining this club.
                earliest=affiliation[r['id']]
                probabilities.append(1-min(1,actual/expected) if expected>=1 and game_key[0]>=earliest else 0.)
            value=self.mixture(probabilities)@self.factors;numerator=numerator*decay+value;denominator=denominator*decay+1
        return numerator/denominator

    def out_probabilities(self,day):
        ordinal=date.fromisoformat(day).toordinal();today=date.fromisoformat(self.today).toordinal()
        return [1. if ordinal<=today else min(1,max(0,(high-ordinal)/(high-low+1))) for low,high,_ in self.windows]

    def mean(self,day):
        if day not in self.forecasts:self.forecasts[day]=(self.mixture(self.out_probabilities(day))@self.factors)/self.embedded
        return self.forecasts[day]

    def simulation(self,day,n):
        ordinal=date.fromisoformat(day).toordinal()
        masks=np.zeros(n,dtype=np.int64)
        for i,(r,(low,high,_)) in enumerate(zip(self.missing,self.windows)):
            seed=int(hashlib.sha256((self.today+str(r['id'])+self.model['version']).encode()).hexdigest()[:16],16)
            key=(r['id'],n)
            if key not in self.draws:self.draws[key]=np.random.default_rng(seed).integers(low,high+1,n,dtype=np.int32)
            dates=self.draws[key]
            if day<=self.today:masks|=1<<i
            else:masks|=(dates>ordinal).astype(np.int64)<<i
        # A return date denotes the first available date; probability mixtures
        # and simulation therefore use the same strict comparison.
        return self.factors[masks]/self.embedded

    def summary(self,day):
        probabilities=self.out_probabilities(day);players=[]
        all_out=(1<<self.k)-1
        for i,r in enumerate(self.missing):
            p=self.pool[r['id']];restored=all_out&~(1<<i);healthy=self.assignments[restored].get(r['id'],np.zeros(3))
            marginal=self.profiles[all_out]-self.profiles[restored]
            players.append({'id':r['id'],'name':r['name'],'status':r['status'],'return_estimate':r.get('return_estimate'),
              'out_probability':round(probabilities[i]*100,3),'expected_minutes':{k:round(float(v),2) for k,v in zip(ROLES,healthy)},
              'absence_role_log_change':{key:round(float(value),6) for key,value in zip(KEYS,marginal)},
              'sample':'trained' if p['known'] else 'replacement prior','return_window':{'earliest':date.fromordinal(self.windows[i][0]).isoformat(),'latest':date.fromordinal(self.windows[i][1]).isoformat()}})
        return {'status':'partial' if self.fixed else 'available','version':self.model['version'],'players':players,
          'baseline':'availability already embedded in recency-weighted team performance','return_dates':'scenario windows, not confirmed recovery dates'}


class Impact:
    def __init__(self,data,inputs,availability,rows,now,model=None,params=None):
        self.model=model or json.loads(PARAMETERS.read_text());self.teams={};self.date=datetime.fromisoformat(now.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        self.rows=rows;self.source='NHL shifts, NHL skater usage and Sweater shot-quality model';self.version=self.model['version'];self.scale=float(self.model.get('goal_scale',1.))
        self.healthy_teams=set();self.series_cache={}
        self.rates=np.array([self.model['rates'][k] for k in ROLES]);self.share=self.model['modeled_regulation_goal_share']
        self.as_of=max((r['date'] for r in rows),default=None)
        self.signature={'version':self.version,'coefficients_sha256':hashlib.sha256(json.dumps(self.model,sort_keys=True).encode()).hexdigest(),'usage_through':self.as_of,'usage_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
        params=params or {'prior_games':30,'half_life':15}
        for t in data['teams']:
            club=t['abbr'];roster=availability['rosters'].get(club,[])
            if len([p for p in roster if p.get('position')!='goalies'])<12:continue
            self.teams[club]=Team(club,roster,availability['injuries'].get(club,[]),rows,[r for r in inputs['teams'] if r['s']==data['start'] and r['t']==club],self.model,self.date,params['prior_games'],params['half_life'])

    def weights(self,home,away):
        a=self.teams[home].role_minutes;b=self.teams[away].role_minutes
        minutes=np.array([(a[0]+b[0])/2,(a[1]+b[2])/2,(a[2]+b[1])/2]);raw=minutes*self.rates
        return raw/raw.sum()

    def multipliers(self,home,away,day,n=None):
        if home not in self.teams or away not in self.teams:return 1.,1.
        h=self.factors(home,day,n);a=self.factors(away,day,n)
        def attack(own,opp,w):
            values=own[...,:3]*opp[...,[3,5,4]]
            return np.power(1-self.share+self.share*np.sum(values*w,axis=-1),self.scale)
        return attack(h,a,self.weights(home,away)),attack(a,h,self.weights(away,home))

    def factors(self,club,day,n=None):
        team=self.teams.get(club)
        if team is None:return np.ones(6)
        if club in self.healthy_teams:return 1/team.embedded
        return team.simulation(day,n) if n is not None else team.mean(day)

    def series_multipliers(self,clubs,h,a,day):
        n=len(h);key=(day,n,tuple(sorted(self.healthy_teams)))
        if key not in self.series_cache:
            self.series_cache.clear() # One postseason date, rather than every date × every simulation.
            self.series_cache[key]=np.stack([np.broadcast_to(self.factors(t,day,n),(n,6)) for t in clubs])
        matrix=self.series_cache[key];rows=np.arange(n);hf=matrix[h,rows];af=matrix[a,rows]
        weights=np.array([[self.weights(x,y) if x in self.teams and y in self.teams else np.ones(3)/3 for y in clubs] for x in clubs])
        def attack(own,opp,w):return np.power(1-self.share+self.share*np.sum(own[:,:3]*opp[:,[3,5,4]]*w,axis=1),self.scale)
        return attack(hf,af,weights[h,a]),attack(af,hf,weights[a,h])

    def summary(self,team,day):
        if team not in self.teams:return {'status':'unavailable','version':self.version}
        result=self.teams[team].summary(day)
        # Marginal changes refer to this player absent versus restored while the
        # other currently-out players remain absent. Replacement minutes count.
        weights=self.weights(team,team)
        for p in result['players']:
            values=p['absence_role_log_change']
            p['attack_change_pct']=round(100*((1-self.share+self.share*float(np.exp([values['off_'+r] for r in ROLES])@weights))**self.scale-1),2)
            p['opponent_attack_change_pct']=round(100*((1-self.share+self.share*float(np.exp([values['def_'+r] for r in ROLES])@weights[[0,2,1]]))**self.scale-1),2)
        return {**result,'usage_through':self.as_of,'trained_through':self.model['trained_through'],
          'goal_scale':self.scale,'estimated':True,'scope':'Model estimates relative to projected replacements; not isolated causal effects.'}

    def metadata(self):
        return {'version':self.version,'status':'beta','trained_through':self.model['trained_through'],'usage_through':self.as_of,
          'coefficients_sha256':self.signature['coefficients_sha256'],'players':len(self.model['players']),
          'training_games':sum(s['games'] for s in self.model['inputs']['sources'] if s['season']<=2025),
          'goal_scale':self.scale,'game_validation':self.model.get('game_validation'),
          'return_dates':'Uniform scenario windows around reported estimates; uncertain defaults when no future estimate exists. Not a trained medical forecast.',
          'limitations':self.model['limitations']}


def load_impact(data,inputs,availability,now,params=None):
    if not PARAMETERS.exists() or availability.get('status') not in ('reported','cached'):return None
    from player_data import skater_games,ROOT
    path=ROOT/f'.cache/playoffs/impact/usage-{data["start"]}.json'
    try:
        rows=skater_games(data['start'],False)
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(rows,separators=(',',':')));temp.replace(path)
    except Exception:
        if not path.exists():return None
        try:rows=json.loads(path.read_text())
        except (OSError,ValueError):return None
    completed={g['id'] for g in data['games'] if g['state'] in ('OFF','FINAL')}
    rows=[r for r in rows if r['g'] in completed]
    if not rows:return None
    today=datetime.fromisoformat(now.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date()
    if (today-date.fromisoformat(max(r['date'] for r in rows))).days>7:return None
    return Impact(data,inputs,availability,rows,now,params=params)
