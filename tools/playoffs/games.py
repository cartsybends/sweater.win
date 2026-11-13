"""League form, pregame model estimates, and verified NHL final-game shots."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

from data import FINAL, TEAMS, records
from model import game_probability, rates, parameters


def boxscore_stats(game, fetch):
    raw = fetch(f'https://api-web.nhle.com/v1/gamecenter/{game["id"]}/boxscore')
    h, a = raw['homeTeam'], raw['awayTeam']
    if raw['gameState'] not in FINAL or raw['id'] != game['id'] or h['abbrev'] != game['home'] or a['abbrev'] != game['away'] or h['score'] != game['hg'] or a['score'] != game['ag']:
        raise ValueError('NHL boxscore does not match the verified final')
    hs, ats = h.get('sog'), a.get('sog')
    hg = game['hg'] - int(game['end'] == 'SO' and game['hg'] > game['ag'])
    ag = game['ag'] - int(game['end'] == 'SO' and game['ag'] > game['hg'])
    if type(hs) is not int or type(ats) is not int or not hg <= hs <= 200 or not ag <= ats <= 200:
        raise ValueError('Incomplete NHL shots')
    return {'home_shots': hs, 'away_shots': ats}


def enrich(output, data, history, old, fetch, now, engine=None, clock=None):
    now_dt = datetime.fromisoformat(now.replace('Z', '+00:00'))
    today = now_dt.astimezone(ZoneInfo('America/New_York')).date()
    first, last = today - timedelta(days=14), today + timedelta(days=7)
    games = sorted(data['games'], key=lambda g: (g['date'], g['start'], g['id']))
    included = [g for g in games if first.isoformat() <= g['date'] <= last.isoformat()]
    # The prior is computed once. Each day's reconstruction then adds only earlier
    # calendar dates, so overlapping or later games cannot leak their results.
    empty = {**data, 'teams': [{**t, 'gp': 0, 'gf': 0, 'ga': 0} for t in data['teams']]}
    prior, league, _ = rates(empty, history)
    home_factor = parameters()['home_factor']
    indexes = {t['abbr']: i for i, t in enumerate(data['teams'])}
    by_day = {}
    for day in {g['date'] for g in included}:
        by_day[day] = records([g for g in games if g['date'] < day])
    old_games = {g['id']: g for g in old.get('games', [])}
    rows = []
    for g in included:
        before = by_day[g['date']]
        def rate(team, field):
            r = prior[indexes[team]]
            return (r['shape'][0 if field == 'gf' else 1] + before[team][field]) / (r['exposure'] + before[team]['gp'])
        factor = 1 if g['neutral'] else home_factor
        lh = rate(g['home'], 'gf') * rate(g['away'], 'ga') / league * factor
        la = rate(g['away'], 'gf') * rate(g['home'], 'ga') / league / factor
        hp = round(game_probability(lh, la) * 100, 4)
        context=None
        if engine:
            probability,lh,la,context=engine.predict(g)
            hp=round(probability*100,4)
        captured_at=clock() if clock else now
        upcoming = datetime.fromisoformat(captured_at.replace('Z','+00:00')) < datetime.fromisoformat(g['start'].replace('Z', '+00:00'))
        if engine and not upcoming:
            probability,lh,la,context=engine.predict(g,force_historical=True)
            hp=round(probability*100,4)
        prediction = {'home_win': hp, 'away_win': round(100-hp, 4), 'home_goals': round(lh, 3), 'away_goals': round(la, 3),
                      'basis': 'pregame' if upcoming else 'reconstructed', 'at': captured_at if upcoming else None, 'model':output['model']}
        previous = old_games.get(g['id'])
        if not upcoming and previous and previous['start'] == g['start'] and previous['home'] == g['home'] and previous['away'] == g['away']:
            saved = previous.get('prediction', {})
            at = saved.get('at')
            if saved.get('basis') in {'pregame', 'recorded'} and at and datetime.fromisoformat(at.replace('Z', '+00:00')) < datetime.fromisoformat(g['start'].replace('Z', '+00:00')):
                prediction = {**saved, 'basis': 'recorded','model':saved.get('model',old.get('model'))}
        row = {k: g[k] for k in ['id', 'date', 'start', 'home', 'away', 'state', 'neutral']}
        row['prediction'] = prediction
        if context:
            if prediction['basis']=='recorded' and previous:
                if previous.get('context'):
                    row['context']=previous['context']
            else:
                row['context']=context
        if g['state'] in FINAL:
            row.update({k: g[k] for k in ['hg', 'ag', 'end']})
            if previous and g['date'] < (today-timedelta(days=1)).isoformat() and previous.get('hg') == g['hg'] and previous.get('ag') == g['ag'] and previous.get('end') == g['end'] and type(previous.get('home_shots')) is int and type(previous.get('away_shots')) is int:
                row.update(home_shots=previous['home_shots'], away_shots=previous['away_shots'])
        rows.append(row)
    def add_shots(row):
        if row['state'] in FINAL and 'home_shots' not in row:
            try:
                row.update(boxscore_stats(row, fetch))
            except Exception:
                # Missing shots do not hide a verified result or replace it with zeros.
                pass
        return row
    with ThreadPoolExecutor(max_workers=6) as pool:
        output['games'] = list(pool.map(add_shots, rows))
    for t in output['teams']:
        recent = [g for g in games if g['state'] in FINAL and t['abbr'] in (g['home'], g['away'])][-10:]
        t['form'] = records(recent)[t['abbr']]
    output.update(analytics_version=1, games_from=first.isoformat(), games_through=last.isoformat(), games_today=today.isoformat())
    from market import enrich_markets
    output = enrich_markets(output, old, fetch, now)
    return validate_analytics(output)


def validate_analytics(output):
    if 'analytics_version' not in output:
        return output
    assert output['analytics_version'] == 1 and len(output['games']) <= 400
    ids = set()
    for g in output['games']:
        assert g['id'] not in ids and g['home'] in TEAMS and g['away'] in TEAMS and g['home'] != g['away']
        ids.add(g['id'])
        p = g['prediction']
        assert all(math.isfinite(p[k]) for k in ['home_win', 'away_win', 'home_goals', 'away_goals'])
        assert 0 <= p['home_win'] <= 100 and abs(p['home_win'] + p['away_win'] - 100) < .001
        assert p['basis'] in ['pregame', 'recorded', 'reconstructed']
        assert p['home_goals'] > 0 and p['away_goals'] > 0
        if p['basis'] != 'reconstructed':
            assert datetime.fromisoformat(p['at'].replace('Z', '+00:00')) < datetime.fromisoformat(g['start'].replace('Z', '+00:00'))
        if g['state'] in FINAL:
            assert type(g['hg']) is int and type(g['ag']) is int and g['hg'] != g['ag']
            for field in ['home_shots', 'away_shots']:
                assert field not in g or type(g[field]) is int and 0 <= g[field] <= 200
        if 'market' in g:
            from market import valid_market
            assert valid_market(g['market'], g)
        if 'context' in g:
            validate_context(g)
    for t in output['teams']:
        f = t['form']
        assert 0 <= f['gp'] <= 10 and 0 <= f['points'] <= 2*f['gp'] and 0 <= f['wins'] <= f['gp']
    return output


def validate_context(game):
    from starters import valid_report
    for side in ['home','away']:
        context=game['context'][side];goalie=context['goalie'];players=goalie['players']
        assert type(context['rest_days']) is int and 1<=context['rest_days']<=7
        assert context['injury_status'] in {'reported','cached','stale','unavailable','not_reconstructed'}
        assert goalie['status'] in {'projected','confirmed','unknown'} and math.isfinite(goalie['gsax']) and abs(goalie['gsax'])<=2
        assert len(players)<=10 and all(type(p['id']) is int and p['id']>=0 and isinstance(p['name'],str) and 0<len(p['name'])<=100 and math.isfinite(p['probability']) and 0<=p['probability']<=100 for p in players)
        assert not players or abs(sum(p['probability'] for p in players)-100)<=.002
        assert len({p['id'] for p in players})==len(players)
        report=goalie.get('report')
        if report:
            roster={game[side]:[{'id':report['player_id'],'position':'goalies'}]}
            assert valid_report(report,game,roster,game['start'])
        if goalie['status']=='confirmed':
            assert report and report['status']=='confirmed' and sum(p['id']==report['player_id'] and p['probability']==100 for p in players)==1
        assert len(context['injuries'])<=100 and all(isinstance(i['name'],str) and len(i['name'])<=100 and isinstance(i['status'],str) and len(i['status'])<=50 for i in context['injuries'])
