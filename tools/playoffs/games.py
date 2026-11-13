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


def enrich(output, data, history, old, fetch, now):
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
    old_games = {g['id']: g for g in old.get('games', [])} if old.get('model') == output['model'] and old.get('parameters') == output.get('parameters') else {}
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
        upcoming = now_dt < datetime.fromisoformat(g['start'].replace('Z', '+00:00'))
        prediction = {'home_win': hp, 'away_win': round(100-hp, 4), 'home_goals': round(lh, 3), 'away_goals': round(la, 3),
                      'basis': 'pregame' if upcoming else 'reconstructed', 'at': now if upcoming else None}
        previous = old_games.get(g['id'])
        if not upcoming and previous and previous['home'] == g['home'] and previous['away'] == g['away']:
            saved = previous.get('prediction', {})
            at = saved.get('at')
            if saved.get('basis') in {'pregame', 'recorded'} and at and datetime.fromisoformat(at.replace('Z', '+00:00')) < datetime.fromisoformat(g['start'].replace('Z', '+00:00')):
                prediction = {**saved, 'basis': 'recorded'}
        row = {k: g[k] for k in ['id', 'date', 'start', 'home', 'away', 'state', 'neutral']}
        row['prediction'] = prediction
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
    for t in output['teams']:
        f = t['form']
        assert 0 <= f['gp'] <= 10 and 0 <= f['points'] <= 2*f['gp'] and 0 <= f['wins'] <= f['gp']
    return output
