"""Recency-aware shot-quality ratings and shared game/simulation adjustments.

Published coefficients are fitted chronologically. Runtime uses NumPy only.
Current injuries never enter retrospective features. Unconfirmed goalies remain
a distribution, including for future season simulations.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import numpy as np

from data import TEAMS
from model import game_probability

PARAMETERS = Path(__file__).with_name('parameters_v2.json')
STARTER_PARAMETERS = Path(__file__).with_name('starter_parameters.json')
FEATURES = ['attack_goals','attack_xg','attack_even_xg','attack_pp_xg',
            'defense_goals','defense_xg','defense_even_xg','defense_pk_xg','goalie_gsax',
            'home','own_back_to_back','opponent_back_to_back','own_rest','opponent_rest']
OUT = {'out','injured reserve','ir','long-term injured reserve','suspended'}
EAST = set('BOS BUF CAR CBJ DET FLA MTL NJD NYI NYR OTT PHI PIT TBL TOR WSH'.split())


def urgency(team, gp, points, season_games=82):
    """Standings-based playoff-race proxy, not a claim of exact game leverage."""
    index={t:i for i,t in enumerate(TEAMS)};i=index[team]
    if gp[i]<10:
        return .25
    clubs=[index[t] for t in TEAMS if (t in EAST)==(team in EAST)]
    percentages=[points[j]/max(2*gp[j],1) for j in clubs]
    cutoff=sorted(percentages,reverse=True)[7]
    closeness=math.exp(-((points[i]/(2*gp[i])-cutoff)/.1)**2)
    return .25+.75*closeness*min(1,gp[i]/season_games)


def config():
    return json.loads(PARAMETERS.read_text())


def day_number(day):
    return date.fromisoformat(day).toordinal()


class Goalies:
    def __init__(self, rows, births=None):
        self.rows = rows
        self.births = births or {}
        self.starter_parameters = json.loads(STARTER_PARAMETERS.read_text()) if STARTER_PARAMETERS.exists() else None
        self.by_team = defaultdict(list)
        self.by_player = defaultdict(list)
        self.cache = {}
        self.project_cache = {}
        for r in rows:
            self.by_team[r['t']].append(r)
            self.by_player[r['p']].append(r)

    def talent(self, player, day):
        key=(player,day)
        if key in self.cache:
            return self.cache[key]
        ordinal=day_number(day);minutes=xg=ga=0
        for r in self.by_player[player]:
            age=ordinal-day_number(r['d'])
            if not 0<age<=1095:
                continue
            w=2**(-age/365)
            minutes+=r['m']*w;xg+=r['x']*w;ga+=r['a']*w
        value=float(np.clip((xg-ga)*3600/(minutes+108000),-.8,.8))
        self.cache[key]=value
        return value

    def starter_features(self, player, team, day, home=False, importance=.5, candidate_count=2):
        ordinal=day_number(day);past=[r for r in self.by_player[player] if r['d']<day]
        recent=[r for r in self.by_team[team] if r['d']<day]
        last_games=sorted({r['g'] for r in recent},reverse=True)[:10]
        full=sum(r['p']==player and r['m']>=3300 for r in recent if r['g'] in last_games)/max(1,len(last_games))
        last=max(past,key=lambda r:(r['d'],r['g']),default=None)
        rest=min(7,ordinal-day_number(last['d'])) if last else 7
        time=sum(r['m'] for r in past if ordinal-day_number(r['d'])<=1095)/3600
        shots=sum(r.get('q',0) for r in past if ordinal-day_number(r['d'])<=730)
        ga=sum(r['a'] for r in past if ordinal-day_number(r['d'])<=730)
        save=(shots-ga+270)/(shots+300)-.9
        birth=self.births.get(str(player));age=(ordinal-day_number(birth))/365.25 if birth else 27
        talent=self.talent(player,day)
        return [rest,last.get('w',0) if last else 0,full,math.log1p(time),(age-27)/10,talent,save,
                float(home)*talent,(candidate_count-2)*full,importance*talent,float(player==0)]

    def project(self, team, day, roster=None, injuries=(), report=None, home=False, importance=.5, include_unknown=False):
        cache_key=(team,day,home,importance,include_unknown)
        historical=roster is None and not injuries and report is None
        if historical and cache_key in self.project_cache:
            return self.project_cache[cache_key]
        ordinal=day_number(day)
        recent=[r for r in self.by_team[team] if 0<ordinal-day_number(r['d'])<=365]
        recent.sort(key=lambda r:(r['d'],r['g']),reverse=True)
        if roster is not None:
            names={p['id']:p['name'] for p in roster if p['position']=='goalies'}
        else:
            names={}
            for r in recent:
                names.setdefault(r['p'],r['n'])
                if len(names)==3:
                    break
        excluded={i['player_id'] for i in injuries if i['status'].lower() in OUT and i.get('player_id')}
        if report and report.get('status')=='confirmed' and report.get('player_id') in excluded:
            def timestamp(value):
                try:
                    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
                except (TypeError,ValueError,AttributeError):
                    return datetime.min.replace(tzinfo=timezone.utc)
            prior=[timestamp(i.get('reported_at')) for i in injuries if i.get('player_id')==report['player_id']]
            if timestamp(report.get('reported_at'))>max(prior,default=timestamp(None)):
                excluded.discard(report['player_id'])
            else:
                report={**report,'status':'conflicting'}
        names={p:n for p,n in names.items() if p not in excluded}
        if include_unknown:
            names[0]='Other goalie'
        if not names:
            return {'status':'unknown','players':[],'gsax':0.0}
        recent_games=sorted({r['g'] for r in recent},reverse=True)[:20]
        order={g:i for i,g in enumerate(recent_games)}
        scores=[]
        for player,name in names.items():
            appearances=[r for r in recent if r['p']==player]
            workload=sum(r['m']*.90**order[r['g']] for r in appearances if r['g'] in order)
            last=max((day_number(r['d']) for r in self.by_player[player] if r['d']<day),default=ordinal-7)
            rest=min(7,ordinal-last)
            score=math.log(workload+1800)+.12*rest-1.8*(rest<=1)
            scores.append((player,name,score,self.talent(player,day),rest))
        if self.starter_parameters:
            p=self.starter_parameters
            features=np.array([self.starter_features(r[0],team,day,home,importance,len(names)) for r in scores])
            values=(features-np.array(p['mean']))/np.array(p['scale'])
            scores_array=values@np.array(p['coefficients'])
        else:
            scores_array=np.array([r[2] for r in scores])
        weights=np.exp(scores_array-scores_array.max());weights/=weights.sum()
        if report and report.get('status')=='not_starting':
            weights=np.array([w if r[0]!=report['player_id'] else 0 for w,r in zip(weights,scores)])
            if weights.sum()>0:
                weights/=weights.sum()
            else:
                return {'status':'unknown','players':[],'gsax':0.0,'report':report}
        status='projected'
        if report and report.get('status')=='confirmed' and report.get('player_id') in names:
            weights=np.array([float(r[0]==report['player_id']) for r in scores]);status='confirmed'
        players=[{'id':p,'name':name,'probability':round(float(w*100),4),'gsax_per60':round(talent,4),'rest_days':rest} for (p,name,_,talent,rest),w in zip(scores,weights)]
        players.sort(key=lambda r:-r['probability'])
        result={'status':status,'players':players,'gsax':float(sum(w*r[3] for w,r in zip(weights,scores))),**({'report':report} if report else {})}
        if historical:
            self.project_cache[cache_key]=result
        return result


class State:
    def __init__(self, start, rows, prior_games=15, half_life=30):
        self.start=start;self.half_life=half_life;self.prior_games=prior_games
        self.index={t:i for i,t in enumerate(TEAMS)}
        totals=np.zeros((32,11));counts=np.zeros(32)
        for r in rows:
            if not start-3<=r['s']<start:
                continue
            w={1:.6,2:.3,3:.1}[start-r['s']];i=self.index[r['t']]
            totals[i]+=np.array(r['v'])*w;counts[i]+=w
        if not counts.sum():
            raise ValueError('No past-season advanced inputs')
        league=totals.sum(axis=0)/counts.sum()
        means=np.divide(totals,counts[:,None],out=np.tile(league,(32,1)),where=counts[:,None]>0)
        self.sums=(means*.65+league*.35)*prior_games
        self.weights=np.full((32,11),float(prior_games))
        self.games=np.zeros(32);self.points=np.zeros(32);self.last={};self.rows={(r['g'],r['t']):r for r in rows if r['s']==start}

    def features(self, team, goalie_gsax=0):
        i=self.index[team];v=self.sums[i]/np.maximum(self.weights[i],1e-6)
        off=[v[0],v[2],v[4]*3600/max(v[6],60),v[7]*3600/max(v[8],60)]
        defense=[v[1],v[3],v[5]*3600/max(v[6],60),v[9]*3600/max(v[10],60)]
        return np.log(np.maximum(off,.05)),np.r_[np.log(np.maximum(defense,.05)),goalie_gsax]

    def rest(self, team, day):
        return min(7,max(1,day_number(day)-day_number(self.last[team]))) if team in self.last else 4

    def urgency(self,team):
        return urgency(team,self.games,self.points,84 if self.start>=2026 else 82)

    def pair_features(self, game, goalie_home, goalie_away):
        h,a=game['home'],game['away'];ho,hd=self.features(h,goalie_home);ao,ad=self.features(a,goalie_away)
        rh,ra=self.rest(h,game['date']),self.rest(a,game['date'])
        home=0 if game['neutral'] else 1
        return np.r_[ho,ad,home,rh==1,ra==1,min(rh,4)-2,min(ra,4)-2],np.r_[ao,hd,-home,ra==1,rh==1,min(ra,4)-2,min(rh,4)-2]

    def update(self, game):
        decay=2**(-1/self.half_life)
        for team,gf,ga in [(game['home'],game['hg'],game['ag']),(game['away'],game['ag'],game['hg'])]:
            i=self.index[team];r=self.rows.get((game['id'],team))
            if r:
                values=r['v'];mask=np.ones(11,dtype=bool)
                # Official results remain authoritative; shootout bonuses are not shots.
                bonus=int(game['end']=='SO' and gf>ga);opp_bonus=int(game['end']=='SO' and ga>gf)
                if abs(values[0]-(gf-bonus))>.001 or abs(values[1]-(ga-opp_bonus))>.001:
                    raise ValueError('Advanced data disagrees with NHL final')
            else:
                values=[gf-int(game['end']=='SO' and gf>ga),ga-int(game['end']=='SO' and ga>gf)]+[0]*9
                mask=np.array([True,True]+[False]*9)
            self.sums[i]*=decay;self.weights[i]*=decay
            self.sums[i,mask]+=np.array(values)[mask];self.weights[i,mask]+=1
            self.games[i]+=1;self.last[team]=game['date']
            self.points[i]+=2 if gf>ga else int(game['end']!='REG')


def design(start, games, inputs, prior_games, half_life, goalies=None):
    """Generate strictly prior-date features for fitting and retrospective scoring."""
    state=State(start,inputs['teams'],prior_games,half_life);goalies=goalies or Goalies(inputs['goalies'],inputs.get('births'))
    days=defaultdict(list)
    for g in games:
        days[g['date']].append(g)
    features=[];targets=[];ids=[];actual=[]
    for day,batch in sorted(days.items()):
        for g in batch:
            h=goalies.project(g['home'],day,home=not g['neutral'],importance=state.urgency(g['home']))['gsax'];a=goalies.project(g['away'],day,importance=state.urgency(g['away']))['gsax']
            x,y=state.pair_features(g,h,a);features.extend([x,y]);ids.append(g['id']);actual.append(g['hg']>g['ag'])
            targets.extend([g['hg']-int(g['end']=='SO' and g['hg']>g['ag']),g['ag']-int(g['end']=='SO' and g['ag']>g['hg'])])
        for g in batch:
            state.update(g)
    return np.array(features),np.array(targets),np.array(ids),np.array(actual)


def expected(features, params=None):
    params=params or config();x=(np.asarray(features)-np.array(params['mean']))/np.array(params['scale'])
    return np.clip(np.exp(params['intercept']+x@np.array(params['coefficients'])),.35,8)


def probability(home, away, temperature=1):
    midpoint=math.sqrt(home*away);ratio=(home/away)**(.5/temperature)
    home,away=midpoint*ratio,midpoint/ratio
    return game_probability(home,away),home,away
