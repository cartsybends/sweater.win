"""Preserve actual pregame predictions for ongoing, outcome-blind evaluation."""
from datetime import datetime
import math


def update(old, output, schedule):
    games={r['id']:r for r in old.get('games',[])}
    for g in output.get('games',[]):
        p=g['prediction'];at=p.get('at')
        if p.get('basis') not in {'pregame','recorded'} or not at or datetime.fromisoformat(at.replace('Z','+00:00'))>=datetime.fromisoformat(g['start'].replace('Z','+00:00')):
            continue
        prior=games.get(g['id'])
        if prior and prior['start']==g['start'] and prior['home']==g['home'] and prior['away']==g['away'] and prior['prediction']['at']>=at:
            continue
        row={k:g[k] for k in ['id','start','home','away']}
        row['prediction']={**p,'model':p.get('model',output['model'])}
        if g.get('market'):
            row['market']=g['market']
        if g.get('context'):
            row['goalies']={side:{k:g['context'][side]['goalie'].get(k) for k in ['status','players','report']} for side in ['home','away']}
        games[g['id']]=row
    for g in schedule:
        row=games.get(g['id'])
        if row and g['state'] in {'OFF','FINAL'} and row['home']==g['home'] and row['away']==g['away']:
            row['result']={'home_goals':g['hg'],'away_goals':g['ag'],'home_win':int(g['hg']>g['ag'])}
    return {'version':1,'note':'Only forecasts captured before puck drop are evaluated; reconstructed forecasts are excluded.',
            'games':sorted(games.values(),key=lambda r:r['start'])[-5000:]}


def scores(archive):
    groups={}
    for g in archive['games']:
        if 'result' not in g:
            continue
        p=g['prediction']['home_win']/100;y=g['result']['home_win'];key=g['prediction']['model']
        if not 0<p<1:
            p=min(1-1e-9,max(1e-9,p))
        groups.setdefault(key,[]).append((p,y))
    return {key:{'games':len(rows),'brier':sum((p-y)**2 for p,y in rows)/len(rows),
                 'log_loss':-sum(y*math.log(p)+(1-y)*math.log1p(-p) for p,y in rows)/len(rows),
                 'accuracy':sum((p>=.5)==bool(y) for p,y in rows)/len(rows)} for key,rows in groups.items()}
