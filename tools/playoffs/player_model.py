"""Pregame allocation of Sweater's team goal forecast among dressed skaters.

This is a conditional player-scoring model, not an on-ice chemistry/xG model.
All features use earlier player games; lineup availability is a separate input.
"""
from collections import defaultdict, deque
import math
import numpy as np

FEATURES=['log_goal_rate','log_shot_rate','log_expected_ice_time','power_play_role',
          'recent_scoring_delta','opponent_scoring_delta','defense']
BASELINE=[1,0,1,0,0,0,0]
ZERO={'gp':0,'goals':0,'shots':0,'seconds':0,'pp':0,'pp_n':0,'blocks':0,'blocks_n':0,
      'fo_wins':0,'fo_total':0,'fo_n':0}


def canonical(team):
    return {'S.J':'SJS','L.A':'LAK','N.J':'NJD','T.B':'TBL'}.get(team,team)


def total_add(target,row):
    target['gp']+=1
    for key in ['goals','shots','seconds']:
        target[key]+=row[key]
    if row.get('pp') is not None:
        target['pp']+=row['pp'];target['pp_n']+=1
    if row.get('blocks') is not None:
        target['blocks']+=row['blocks'];target['blocks_n']+=1
    if row.get('fo_total') is not None and row.get('fo_wins') is not None:
        target['fo_wins']+=row['fo_wins'];target['fo_total']+=row['fo_total'];target['fo_n']+=1


class History:
    def __init__(self):
        self.years=defaultdict(lambda:defaultdict(lambda:dict(ZERO)))
        self.opponents=defaultdict(lambda:defaultdict(lambda:dict(ZERO)))
        self.recent=defaultdict(lambda:deque(maxlen=10))

    def add(self,row):
        total_add(self.years[row['p']][row['season']],row)
        total_add(self.opponents[row['p']][(row['season'],canonical(row['opp']))],row)
        self.recent[row['p']].append(row)

    def features(self,pid,season,opponent,position):
        defense=position=='D';prior_goal=.25 if defense else .8;prior_shot=5 if defense else 8.5
        default_seconds=1200 if defense else 840
        weights={season:1,season-1:.6,season-2:.3,season-3:.1}
        history=self.years.get(pid,{})
        values={k:sum(v.get(k,0)*weights.get(y,0) for y,v in history.items()) for k in ('gp','goals','shots','seconds','pp','pp_n')}
        prior_seconds=18000
        goal_rate=(values['goals']+prior_goal*prior_seconds/3600)/(values['seconds']+prior_seconds)*3600
        shot_rate=(values['shots']+prior_shot*prior_seconds/3600)/(values['seconds']+prior_seconds)*3600
        recent=list(self.recent.get(pid,[]))
        recent_seconds=sum(r['seconds'] for r in recent)
        recent_goals=sum(r['goals'] for r in recent)
        average=(values['seconds']+default_seconds*5)/(values['gp']+5)
        pp_average=values['pp']/max(1,values['pp_n'])
        last=recent[-5:]
        expected=.6*(sum(r['seconds'] for r in last)/len(last) if last else average)+.4*average
        pp_last=[r['pp'] for r in last if r.get('pp') is not None]
        pp=.6*(sum(pp_last)/len(pp_last) if pp_last else pp_average)+.4*pp_average
        expected=min(2100,max(60,expected))
        recent_rate=(recent_goals+goal_rate*18000/3600)/(recent_seconds+18000)*3600
        against=self.opponents.get(pid,{})
        opp_goals=sum(v['goals']*weights.get(y,0) for (y,o),v in against.items() if o==canonical(opponent))
        opp_seconds=sum(v['seconds']*weights.get(y,0) for (y,o),v in against.items() if o==canonical(opponent))
        # A 600-minute prior keeps a handful of opponent games from creating a
        # large matchup boost. Its coefficient is learned, not manually assigned.
        opponent_rate=(opp_goals+goal_rate*10)/(opp_seconds/3600+10)
        return np.array([math.log(goal_rate),math.log(shot_rate),math.log(expected/900),
          math.log1p(pp/60),math.log(recent_rate/goal_rate),math.log(opponent_rate/goal_rate),float(defense)])

    def season_stats(self,pid,season):
        s=self.years.get(pid,{}).get(season)
        if not s or not s['gp']:
            return {'gp':0,'sog':None,'blocks':None,'fo':None,'fo_attempts':0}
        return {'gp':s['gp'],'sog':round(s['shots']/s['gp'],3),
          'blocks':round(s['blocks']/s['gp'],3) if s['blocks_n']==s['gp'] else None,
          'fo':round(100*s['fo_wins']/s['fo_total'],3) if s['fo_n']==s['gp'] and s['fo_total'] else None,
          'fo_attempts':s['fo_total'] if s['fo_n']==s['gp'] else 0}


def shares(features,weights):
    z=np.asarray(features)@np.asarray(weights);prob=np.exp(z-z.max())
    return prob/prob.sum()


def goal_allocation(players,history,season,opponent,team_goals,weights):
    if not math.isfinite(team_goals) or team_goals<=0 or not players or len({p['id'] for p in players})!=len(players):
        raise ValueError('Invalid player projection inputs')
    features=[history.features(p['id'],season,opponent,p['position']) for p in players]
    return {p['id']:float(q*team_goals) for p,q in zip(players,shares(features,weights))}
