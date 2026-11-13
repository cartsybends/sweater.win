"""One trained strength model for game probabilities and playoff simulations."""
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import numpy as np

from data import TEAMS, FINAL
from strength_v2 import State,Goalies,config,expected,probability,FEATURES,OUT

MODEL_VERSION='sweater-xg-v2'


class Engine:
    version=MODEL_VERSION

    def __init__(self,data,history,inputs,availability,reports,now):
        self.data=data;self.history=history;self.inputs=inputs;self.availability=availability;self.reports=reports;self.now=now;self.day=now[:10]
        self.params=config();self.teams=[t['abbr'] for t in data['teams']];self.index={t:i for i,t in enumerate(self.teams)}
        self.goalies=Goalies(inputs['goalies'],inputs.get('births'));self.state=self.make_state()
        self.game_cache={};self.state_cache={};self.base_goalies={t:self.project(t,self.day) for t in self.teams}
        self.coefficients=np.array(self.params['coefficients']);self.mean=np.array(self.params['mean']);self.scale=np.array(self.params['scale'])
        self.rating_rows=[]
        for team in self.teams:
            off,defense=self.state.features(team,self.base_goalies[team]['gsax'])
            attack=math.exp(self.params['intercept']+float(((off-self.mean[:4])/self.scale[:4])@self.coefficients[:4]))
            defending=math.exp(float(((defense-self.mean[4:9])/self.scale[4:9])@self.coefficients[4:9]))
            effective=float(np.mean(self.state.weights[self.state.index[team]]))
            exposure=max(20,min(160,4*effective))
            self.rating_rows.append({'attack':attack,'defense':defending,'shape':np.array([attack,defending])*exposure,'exposure':exposure})
        self.parameters={k:self.params[k] for k in ['model','version','prior_games','half_life','alpha','temperature']}
        self.parameters.update(home_factor=1,prior_regression=.35,coefficients_sha256=hashlib.sha256(json.dumps(self.params,sort_keys=True).encode()).hexdigest())
        stable_availability={'rosters':availability['rosters'],'injuries':availability['injuries'],'status':availability['status']}
        self.signature={'inputs':inputs['sha256'],'availability':stable_availability,'reports':sorted(reports.values(),key=lambda r:(r['game_id'],r['team'])),'day':self.day}
        self.context_source={'advanced_data_through':max(r['d'] for r in inputs['teams']),'availability':availability['status'],'availability_reported_at':availability.get('reported_at')}
        last_day=max(g['date'] for g in data['games']);playoff_day=max(last_day,self.day)
        self.playoff_goalies={t:self.project(t,(date.fromisoformat(playoff_day)+timedelta(days=7)).isoformat()) for t in self.teams}

    def make_state(self,before=None):
        state=State(self.data['start'],self.inputs['teams'],self.params['prior_games'],self.params['half_life'])
        for g in sorted(self.data['games'],key=lambda g:(g['date'],g['id'])):
            known=datetime.fromisoformat(g.get('start',g['date']+'T00:00:00Z').replace('Z','+00:00'))<=datetime.fromisoformat(self.now.replace('Z','+00:00'))
            if g['state'] in FINAL and (g['date']<before if before is not None else known):
                state.update(g)
        return state

    def injuries(self,team,day):
        rows=self.availability['injuries'].get(team,[])
        if day<=self.day:
            return rows
        output=[]
        for r in rows:
            estimated=r.get('return_estimate')
            try:
                recovery=date.fromisoformat(estimated) if estimated else date.fromisoformat(self.day)+timedelta(days=14)
            except (TypeError,ValueError):
                recovery=date.fromisoformat(self.day)+timedelta(days=14)
            # An old/today return estimate never changes a currently-out player to healthy today.
            if recovery<=date.fromisoformat(self.day):
                recovery=date.fromisoformat(self.day)+timedelta(days=14)
            if date.fromisoformat(day)<recovery:
                output.append(r)
        return output

    def project(self,team,day,game=None,historical=False,state=None):
        state=state or self.state
        if historical:
            return self.goalies.project(team,day,home=bool(game and game['home']==team and not game['neutral']),importance=state.urgency(team))
        roster=self.availability['rosters'].get(team) or None
        result=self.goalies.project(team,day,roster=roster,injuries=self.injuries(team,day),
                                    report=self.reports.get((game['id'],team)) if game else None,
                                    home=bool(game and game['home']==team and not game['neutral']),importance=state.urgency(team))
        if roster is None:
            result={**result,'status':'unknown','roster_status':'unavailable'}
        totals=self.availability.get('goalie_stats',{})
        if totals.get('status') in {'reported','cached'} and totals.get('season')==self.data['season']:
            result={**result,'players':[{**p,'stats':{**totals['players'].get(str(p['id']),totals['players'].get(p['id'],{'gp':0,'gs':0,'sv':None,'gaa':None})),
                                                   'season':totals['season'],'as_of':totals['as_of'],'status':totals['status']}} for p in result['players']]}
        return result

    def rest(self,game,team):
        earlier=[g['date'] for g in self.data['games'] if team in (g['home'],g['away']) and g['date']<game['date']]
        return min(7,max(1,(date.fromisoformat(game['date'])-date.fromisoformat(max(earlier))).days)) if earlier else 4

    def context(self,game,force_historical=False):
        historical=force_historical or datetime.fromisoformat(game['start'].replace('Z','+00:00'))<=datetime.fromisoformat(self.now.replace('Z','+00:00'))
        key=(game['id'],historical)
        if key in self.game_cache:
            return self.game_cache[key]
        if historical:
            if game['date'] not in self.state_cache:
                self.state_cache[game['date']]=self.make_state(game['date'])
            state=self.state_cache[game['date']]
        else:
            state=self.state
        result={}
        for side in ['home','away']:
            team=game[side];goalie=self.project(team,game['date'],game,historical,state)
            result[side]={'rest_days':self.rest(game,team),'goalie':goalie,
                          'injuries':[] if historical else self.availability['injuries'].get(team,[]),
                          'injury_status':'not_reconstructed' if historical else self.availability['status'],
                          'injury_reported_at':None if historical else self.availability.get('reported_at')}
        self.game_cache[key]=result
        return result

    def event_features(self,game):
        h,a=self.rest(game,game['home']),self.rest(game,game['away'])
        return np.array([0 if game['neutral'] else 1,h==1,a==1,min(h,4)-2,min(a,4)-2],dtype=float)

    def adjust(self,game,home_rate,away_rate):
        context=self.context(game);h,a=game['home'],game['away']
        quality_coefficient=self.coefficients[8]/self.scale[8]
        home_rate=home_rate*np.exp(quality_coefficient*(context['away']['goalie']['gsax']-self.base_goalies[a]['gsax']))
        away_rate=away_rate*np.exp(quality_coefficient*(context['home']['goalie']['gsax']-self.base_goalies[h]['gsax']))
        event=self.event_features(game);reverse=event[[0,2,1,4,3]].copy();reverse[0]*=-1
        home_rate=home_rate*np.exp(((event-self.mean[9:])/self.scale[9:])@self.coefficients[9:])
        away_rate=away_rate*np.exp(((reverse-self.mean[9:])/self.scale[9:])@self.coefficients[9:])
        return self.temper(home_rate,away_rate)

    def temper(self,home,away):
        home=np.clip(home,.35,8);away=np.clip(away,.35,8)
        mid=np.sqrt(home*away);ratio=(home/away)**(.5/self.params['temperature'])
        return mid*ratio,mid/ratio

    def series_adjust(self,home_indices,away_indices,home_rate,away_rate):
        quality=self.coefficients[8]/self.scale[8]
        ratio=np.array([math.exp(quality*(self.playoff_goalies[t]['gsax']-self.base_goalies[t]['gsax'])) for t in self.teams])
        home_rate=home_rate*ratio[away_indices];away_rate=away_rate*ratio[home_indices]
        home=np.array([1,0,0,0,0]);away=np.array([-1,0,0,0,0])
        home_rate=home_rate*np.exp(((home-self.mean[9:])/self.scale[9:])@self.coefficients[9:])
        away_rate=away_rate*np.exp(((away-self.mean[9:])/self.scale[9:])@self.coefficients[9:])
        return self.temper(home_rate,away_rate)

    def predict(self,game,force_historical=False):
        context=self.context(game,force_historical)
        historical=force_historical or datetime.fromisoformat(game['start'].replace('Z','+00:00'))<=datetime.fromisoformat(self.now.replace('Z','+00:00'))
        state=self.state_cache[game['date']] if historical else self.state
        h,a=game['home'],game['away'];ho,hd=state.features(h,context['home']['goalie']['gsax']);ao,ad=state.features(a,context['away']['goalie']['gsax'])
        event=self.event_features(game);reverse=event[[0,2,1,4,3]].copy();reverse[0]*=-1
        raw=expected(np.array([np.r_[ho,ad,event],np.r_[ao,hd,reverse]]),self.params)
        probability_home,lh,la=probability(float(raw[0]),float(raw[1]),self.params['temperature'])
        return probability_home,lh,la,context

    def metadata(self):
        return {'version':2,'source':'MoneyPuck.com','source_url':'https://moneypuck.com/data.htm','revision':self.inputs['revision'],
                'data_through':self.context_source['advanced_data_through'],'injury_status':self.availability['status'],
                'injury_reported_at':self.availability.get('reported_at'),'starter_model':'trained workload/rest/performance model',
                'skater_injuries':'reported context only; no validated individual skater penalty',
                'validation':self.params['validation'],
                'summary':'Recency-weighted goals and expected goals, five-on-five and special teams, projected/confirmed goalies, and schedule rest. Injured goalies are removed from current starting options. Other skater absences are reported without an unvalidated numerical penalty.'}
