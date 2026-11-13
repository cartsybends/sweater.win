"""Fetch and reconcile official NHL schedules before publishing any forecast."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.cache/playoffs'
TEAMS = 'ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split()
FINAL = {'FINAL', 'OFF'}


def fetch(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Sweater Playoff Picture)'})
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def canonical(team):
    return 'UTA' if team == 'ARI' else team


def compact(raw):
    final = raw['gameState'] in FINAL
    result = {'id': raw['id'], 'season': raw['season'], 'date': raw['gameDate'],
              'home': canonical(raw['homeTeam']['abbrev']), 'away': canonical(raw['awayTeam']['abbrev']),
              'state': raw['gameState'], 'neutral': bool(raw.get('neutralSite')),
              'start': raw.get('startTimeUTC', raw['gameDate'] + 'T00:00:00Z')}
    if final:
        result.update(hg=raw['homeTeam']['score'], ag=raw['awayTeam']['score'],
                      end=raw.get('gameOutcome', {}).get('lastPeriodType', raw.get('periodDescriptor', {}).get('periodType')))
        if result['hg'] == result['ag'] or result['end'] not in {'REG', 'OT', 'SO'}:
            raise ValueError('Incomplete final NHL result')
    return result


def schedules(start, historical=False):
    path = CACHE / f'{start}.json'
    if historical and path.exists():
        return json.loads(path.read_text())
    season = start * 10000 + start + 1
    clubs = [t if t != 'UTA' or start >= 2024 else 'ARI' for t in TEAMS]
    def get(team):
        data = fetch(f'https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}')
        return [compact(g) for g in data['games'] if g['gameType'] == 2 and g['season'] == season]
    games = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for batch in pool.map(get, clubs):
            for g in batch:
                old = games.get(g['id'])
                if old and old['state'] in FINAL and g['state'] in FINAL and old != g:
                    raise ValueError('Conflicting NHL final results')
                if not old or g['state'] in FINAL:
                    games[g['id']] = g
    result = sorted(games.values(), key=lambda g: (g['date'], g['id']))
    counts = {t: sum(g['home'] == t or g['away'] == t for g in result) for t in TEAMS}
    expected = 84 if start >= 2026 else 82
    if set(counts.values()) != {expected} or len(result) != expected * 16:
        raise ValueError(f'Incomplete {season} NHL schedule: {counts}')
    if historical:
        if any(g['state'] not in FINAL for g in result):
            raise ValueError('Historical season is unfinished')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, separators=(',', ':')) + '\n')
    return result


def records(games):
    result = {t: dict(gp=0, points=0, wins=0, rw=0, row=0, gf=0, ga=0) for t in TEAMS}
    for g in games:
        if g['state'] not in FINAL:
            continue
        h, a = result[g['home']], result[g['away']]
        for r, gf, ga in [(h, g['hg'], g['ag']), (a, g['ag'], g['hg'])]:
            win = gf > ga
            r['gp'] += 1
            r['gf'] += gf
            r['ga'] += ga
            r['points'] += 2 if win else int(g['end'] != 'REG')
            r['wins'] += int(win)
            r['rw'] += int(win and g['end'] == 'REG')
            r['row'] += int(win and g['end'] != 'SO')
    return result


def validate_snapshot(games, standings):
    rows = standings['standings']
    if len(rows) != 32 or {r['teamAbbrev']['default'] for r in rows} != set(TEAMS):
        raise ValueError('Incomplete NHL standings')
    actual = records(games)
    fields = {'gp': 'gamesPlayed', 'points': 'points', 'wins': 'wins', 'rw': 'regulationWins',
              'row': 'regulationPlusOtWins', 'gf': 'goalFor', 'ga': 'goalAgainst'}
    for r in rows:
        t = r['teamAbbrev']['default']
        for key, source in fields.items():
            if actual[t][key] != r[source]:
                raise ValueError(f'NHL standings/schedule not reconciled: {t} {key} ({actual[t][key]} / {r[source]})')
    return actual


def collect(start):
    games = schedules(start)
    standings = fetch('https://api-web.nhle.com/v1/standings/now')
    season = start * 10000 + start + 1
    if any(r['seasonId'] != season for r in standings['standings']):
        raise ValueError('NHL standings are for a different season')
    actual = validate_snapshot(games, standings)
    teams = []
    for r in sorted(standings['standings'], key=lambda r: r['teamAbbrev']['default']):
        t = r['teamAbbrev']['default']
        teams.append({'abbr': t,
                      'name': r['teamName']['default'], 'conference': r['conferenceAbbrev'],
                      'division': r['divisionName'], 'division_code': r['divisionAbbrev'],
                      'official_rank': r['leagueSequence'], 'clinch': r.get('clinchIndicator', ''), **actual[t]})
    bracket = []
    if all(g['state'] in FINAL for g in games):
        raw = fetch(f'https://api-web.nhle.com/v1/playoff-bracket/{start + 1}')
        for s in raw.get('series', []):
            top, bottom = s.get('topSeedTeam'), s.get('bottomSeedTeam')
            if top and bottom:
                bracket.append({'round': s['playoffRound'], 'home': canonical(top['abbrev']),
                                'away': canonical(bottom['abbrev']), 'hw': s['topSeedWins'], 'aw': s['bottomSeedWins']})
        if len([s for s in bracket if s['round'] == 1]) != 8:
            raise ValueError('The postseason bracket is not yet complete; preserve the previous forecast')
    return {'version': 1, 'season': season, 'start': start, 'season_games': 84 if start >= 2026 else 82,
            'teams': teams, 'games': games, 'bracket': bracket}


def fingerprint(data):
    # A clock tick alone never changes the simulation or creates a history point.
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def model_signature(data, params, simulations, engine=None):
    # A game going from FUT to LIVE is not a new confirmed result.
    stable = {**data, 'games': [{**g, 'state': 'OFF' if g['state'] in FINAL else 'FUT'} for g in data['games']]}
    return fingerprint({'data': stable, 'model': engine.version if engine else 'sweater-goals-v1', 'parameters': params, 'simulations': simulations,**({'advanced':engine.signature} if engine else {})})


def main():
    from model import forecast, validate_forecast, MODEL_VERSION, parameters, PARAMETERS
    parser = argparse.ArgumentParser()
    parser.add_argument('--simulations', type=int, default=50000)
    parser.add_argument('--history-only', action='store_true')
    args = parser.parse_args()
    today = datetime.now(ZoneInfo('America/New_York')).date()
    start = today.year if today.month >= 7 else today.year - 1
    history = [g for year in range(start - 3, start) for g in schedules(year, historical=True)]
    if args.history_only:
        print('Cached', len(history), 'verified historical NHL games')
        return
    data = collect(start)
    path = ROOT / 'playoffs_cache.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    from advanced import load_inputs, availability, goalie_statistics
    from starters import collect as starter_reports
    from engine_v2 import Engine
    inputs=load_inputs(start)
    context=availability(data['teams'],fetch,now)
    context['goalie_stats']=goalie_statistics(data['season'],datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'))
    now=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    reports,starter_feed=starter_reports(data['games'],context['rosters'],old,now)
    engine=Engine(data,history,inputs,context,reports,now)
    params=engine.parameters
    signature=model_signature(data,params,args.simulations,engine)
    if old.get('source_sha256') == signature:
        output = {**old, 'checked_at': now}
    else:
        output = forecast(data, history, args.simulations, params, engine)
        output.update(source_sha256=signature, updated_at=now, checked_at=now,
                      parameters=params,
                      validation={'summary': f"Retrospective 2025–26 evaluation: Brier {engine.params['validation']['new']['brier']:.4f} versus {engine.params['validation']['baseline']['brier']:.4f} for the previous Sweater model. Advanced historical xG can be retrospectively revised; forward validation is ongoing. Playoff calibration is not established."},
                      sources=['https://api-web.nhle.com/v1/standings/now',
                               f'https://api-web.nhle.com/v1/club-schedule-season/{{team}}/{data["season"]}',
                               'https://moneypuck.com/data.htm',
                               'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries',
                               'https://www.nhl.com/info/standings-info/playoff-format',
                               'https://www.nhl.com/info/standings-info/tie-breaking-procedure'])
        previous = old if old.get('season') == data['season'] and old.get('model') == engine.version and old.get('parameters') == params else {}
        output['previous_at'] = previous.get('updated_at')
        prev = {t['abbr']: t for t in previous.get('teams', [])}
        for t in output['teams']:
            t['change'] = t['odds']['playoffs'] - prev[t['abbr']]['odds']['playoffs'] if t['abbr'] in prev else None
        history_points = previous.get('history', [])
        output['history'] = history_points + [{'at': now, 'completed': output['completed_games'],
          'teams': {t['abbr']: [t['odds']['playoffs'], t['odds']['cup']] for t in output['teams']}}]
    validate_forecast(output)
    from games import enrich
    output = enrich(output, data, history, old, fetch, now, engine,
                    clock=lambda:datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'))
    output['advanced']=engine.metadata()
    output['starter_feed']=starter_feed
    output['checked_at']=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    from evaluation import update as archive_update,scores as forward_scores
    archive_path=ROOT/'playoffs_predictions.json'
    archive=archive_update(json.loads(archive_path.read_text()) if archive_path.exists() else {},output,data['games'])
    output['forward_validation']=forward_scores(archive)
    archive_temp=archive_path.with_suffix('.tmp');archive_temp.write_text(json.dumps(archive,ensure_ascii=False,separators=(',',':'))+'\n');archive_temp.replace(archive_path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    temp.replace(path)
    print('Verified Playoff Picture:', output['completed_games'], 'final games;', output['simulations'], 'simulations;', now)


if __name__ == '__main__':
    main()
