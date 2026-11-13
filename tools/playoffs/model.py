"""Sweater goals model v1: posterior goal rates, exact schedule, fixed playoff tree.

Only observed results enter team strength. Simulated future results determine
standings, never retrain the strength model inside a simulated season.
"""
import math
from pathlib import Path
import json
import numpy as np

MODEL_VERSION = 'sweater-goals-v1'
STAGES = ['playoffs', 'round2', 'conference', 'final', 'cup']
DEFAULTS = {'prior_games': 40, 'home_factor': 1.04, 'prior_regression': .35}
PARAMETERS = Path(__file__).with_name('parameters.json')


def parameters():
    return json.loads(PARAMETERS.read_text())['parameters'] if PARAMETERS.exists() else DEFAULTS


def rates(data, history, params=None):
    p = params or parameters()
    # A strict season boundary prevents retrospective validation from seeing the future.
    prior = [g for g in history if g['season'] < data['season'] and g['state'] in {'OFF', 'FINAL'}]
    weights = {data['start'] - 1: .6, data['start'] - 2: .3, data['start'] - 3: .1}
    totals = {t['abbr']: np.zeros(3) for t in data['teams']}
    so = ot = 0
    for g in prior:
        weight = weights.get(g['season'] // 10000, 0)
        if not weight:
            continue
        for team, gf, ga in [(g['home'], g['hg'], g['ag']), (g['away'], g['ag'], g['hg'])]:
            if team in totals:
                totals[team] += np.array([gf, ga, 1]) * weight
        so += g['end'] == 'SO'
        ot += g['end'] != 'REG'
    aggregate = sum(totals.values())
    league = float(aggregate[0] / aggregate[2]) if aggregate[2] else 3.0
    result = []
    for t in data['teams']:
        raw = totals[t['abbr']]
        historical = raw[:2] / raw[2] if raw[2] else np.array([league, league])
        shrunk = historical * (1 - p['prior_regression']) + league * p['prior_regression']
        shape = shrunk * p['prior_games'] + np.array([t['gf'], t['ga']])
        exposure = p['prior_games'] + t['gp']
        result.append({'shape': shape, 'exposure': exposure, 'attack': float(shape[0] / exposure), 'defense': float(shape[1] / exposure)})
    return result, league, so / ot if ot else .3


def game_probability(home_rate, away_rate):
    """Poisson scoring + goal-rate-weighted overtime; used by walk-forward tests."""
    hp = [math.exp(-home_rate)]
    ap = [math.exp(-away_rate)]
    for n in range(1, 40):
        hp.append(hp[-1] * home_rate / n)
        ap.append(ap[-1] * away_rate / n)
    win = sum(hp[h] * sum(ap[:h]) for h in range(40))
    tie = sum(h * a for h, a in zip(hp, ap))
    return win + tie * home_rate / (home_rate + away_rate)


def odd_games(games, indices):
    """NHL: discard the first game in the city hosting an extra head-to-head game."""
    pairs = {}
    for g in sorted(games, key=lambda g: (g['date'], g['id'])):
        h, a = indices[g['home']], indices[g['away']]
        pair = tuple(sorted((h, a)))
        pairs.setdefault(pair, []).append((g, h, a))
    excluded = set()
    counts = np.zeros((len(indices), len(indices)), dtype=np.int16)
    for (a, b), rows in pairs.items():
        ah = sum(h == a for _, h, _ in rows)
        bh = len(rows) - ah
        if ah != bh:
            host = a if ah > bh else b
            excluded.add(next(g['id'] for g, h, _ in rows if h == host))
        count = sum(g['id'] not in excluded for g, _, _ in rows)
        counts[a, b] = counts[b, a] = count
    return excluded, counts


def rank_teams(points, rw, row, wins, head, meetings, diff, gf, lottery):
    # Counts stay below 256; this encoding preserves all four primary criteria.
    primary = (((points.astype(np.int64) * 256 + rw) * 256 + row) * 256 + wins)
    h2h = np.zeros(points.shape)
    # Resolve only actual primary ties, rather than allocating an N x 32 x 32 mask.
    order = np.argsort(-primary, axis=1, kind='stable')
    ordered = np.take_along_axis(primary, order, axis=1)
    tied_rows = np.flatnonzero(np.any(ordered[:, 1:] == ordered[:, :-1], axis=1))
    for r in tied_rows:
        vals = ordered[r]
        start = 0
        while start < len(vals):
            end = start + 1
            while end < len(vals) and vals[end] == vals[start]:
                end += 1
            if end - start > 1:
                group = order[r, start:end]
                for t in group:
                    denominator = int(meetings[t, group].sum()) * 2
                    h2h[r, t] = float(head[r, t, group].sum()) / denominator if denominator else 0
            start = end
    return np.lexsort((-lottery, -gf, -diff, -h2h, -primary), axis=1)


def playoff_pairs(ranks, teams):
    count = len(ranks)
    inv = np.argsort(ranks, axis=1)
    all_pairs = []
    for conference in ['E', 'W']:
        divisions = sorted({t['division_code'] for t in teams if t['conference'] == conference})
        winners = []
        second_pairs = []
        selected = np.zeros((count, len(teams)), dtype=bool)
        rows = np.arange(count)
        for division in divisions:
            ids = np.array([i for i, t in enumerate(teams) if t['division_code'] == division and t['conference'] == conference])
            div = ids[np.argsort(inv[:, ids], axis=1)]
            winners.append(div[:, 0])
            second_pairs.append((div[:, 1], div[:, 2]))
            selected[rows[:, None], div[:, :3]] = True
        conf = np.array([i for i, t in enumerate(teams) if t['conference'] == conference])
        eligible = inv[:, conf] + selected[:, conf] * 100
        wild = conf[np.argsort(eligible, axis=1)[:, :2]]
        first_better = inv[rows, winners[0]] < inv[rows, winners[1]]
        for d in range(2):
            wildcard = np.where(first_better if d == 0 else ~first_better, wild[:, 1], wild[:, 0])
            all_pairs.extend([(winners[d], wildcard), second_pairs[d]])
    return all_pairs, inv


def simulate(data, history, simulations=50000, params=None, engine=None):
    if not 100 <= simulations <= 200000:
        raise ValueError('Simulation count outside supported range')
    params = params or parameters()
    teams = data['teams']
    indices = {t['abbr']: i for i, t in enumerate(teams)}
    if len(indices) != 32:
        raise ValueError('Expected 32 unique NHL clubs')
    n = simulations
    columns = len(teams)
    rows = np.arange(n)
    rng = np.random.default_rng(data['season'])
    if engine:
        rt,league=engine.rating_rows,1.0
        overtime=[g for g in history if g['state'] in {'OFF','FINAL'} and g.get('end') in {'OT','SO'}]
        so_share=sum(g['end']=='SO' for g in overtime)/len(overtime) if overtime else .3
    else:
        rt, league, so_share = rates(data, history, params)
    attack = np.column_stack([rng.gamma(r['shape'][0], 1 / r['exposure'], n) for r in rt])
    defense = np.column_stack([rng.gamma(r['shape'][1], 1 / r['exposure'], n) for r in rt])
    fields = {k: np.tile(np.array([t[k] for t in teams], dtype=np.int16), (n, 1)) for k in ['points', 'rw', 'row', 'wins', 'gf', 'ga']}
    excluded, meetings = odd_games(data['games'], indices)
    head = np.zeros((n, columns, columns), dtype=np.uint8)
    future = []
    for g in data['games']:
        h, a = indices[g['home']], indices[g['away']]
        if g['state'] not in {'OFF', 'FINAL'}:
            future.append(g)
            continue
        if g['id'] not in excluded:
            head[:, h, a] += 2 if g['hg'] > g['ag'] else int(g['end'] != 'REG')
            head[:, a, h] += 2 if g['ag'] > g['hg'] else int(g['end'] != 'REG')
    home_factor = params['home_factor']
    for g in future:
        # Per-game streams keep unchanged future draws stable across refreshes.
        grng = np.random.default_rng(g['id'])
        h, a = indices[g['home']], indices[g['away']]
        factor = 1 if g['neutral'] else home_factor
        lh = attack[:, h] * defense[:, a] / league * factor
        la = attack[:, a] * defense[:, h] / league / factor
        if engine:
            lh,la=engine.adjust(g,lh,la)
        hg, ag = grng.poisson(lh), grng.poisson(la)
        tied = hg == ag
        hw = (hg > ag) | (tied & (grng.random(n) < lh / (lh + la)))
        shootout = tied & (grng.random(n) < so_share)
        hg += tied & hw
        ag += tied & ~hw
        fields['points'][:, h] += np.where(hw, 2, tied.astype(np.int16))
        fields['points'][:, a] += np.where(~hw, 2, tied.astype(np.int16))
        fields['wins'][:, h] += hw
        fields['wins'][:, a] += ~hw
        fields['rw'][:, h] += hw & ~tied
        fields['rw'][:, a] += ~hw & ~tied
        fields['row'][:, h] += hw & ~shootout
        fields['row'][:, a] += ~hw & ~shootout
        fields['gf'][:, h] += hg
        fields['ga'][:, h] += ag
        fields['gf'][:, a] += ag
        fields['ga'][:, a] += hg
        if g['id'] not in excluded:
            head[:, h, a] += np.where(hw, 2, tied).astype(np.uint8)
            head[:, a, h] += np.where(~hw, 2, tied).astype(np.uint8)
    rank = rank_teams(fields['points'], fields['rw'], fields['row'], fields['wins'], head, meetings,
                      fields['gf'] - fields['ga'], fields['gf'], rng.random((n, columns)))
    pairs, inv = playoff_pairs(rank, teams)
    results = np.zeros((columns, 5), dtype=np.int64)
    opponents = np.zeros((columns, columns), dtype=np.int64)
    bracket = data.get('bracket', [])
    if bracket:
        # Actual postseason entrants and first-round pairings override simulated qualification.
        # Order by division bracket, then derive adjacent winners as in the official tree.
        actual = {(s['home'], s['away']) for s in bracket if s['round'] == 1}
        for pair in pairs:
            if (teams[pair[0][0]]['abbr'], teams[pair[1][0]]['abbr']) not in actual and (teams[pair[1][0]]['abbr'], teams[pair[0][0]]['abbr']) not in actual:
                raise ValueError('Final standings disagree with the official playoff bracket')
    def play_series(a, b, round_number):
        # The better regular-season record has home ice; no playoff reseeding occurs.
        better = inv[rows, a] < inv[rows, b]
        high, low = np.where(better, a, b), np.where(better, b, a)
        hw, aw = np.zeros(n, dtype=np.int8), np.zeros(n, dtype=np.int8)
        for s in bracket:
            if s['round'] != round_number:
                continue
            sh, sa = indices[s['home']], indices[s['away']]
            forward = (high == sh) & (low == sa)
            reverse = (high == sa) & (low == sh)
            hw[forward], aw[forward] = s['hw'], s['aw']
            hw[reverse], aw[reverse] = s['aw'], s['hw']
        # Games 1,2,5,7 at the higher seed; 3,4,6 at the lower seed.
        for _ in range(7):
            active = (hw < 4) & (aw < 4)
            if not np.any(active):
                break
            played = hw + aw
            high_home = np.isin(played, [0, 1, 4, 6])
            h = np.where(high_home, high, low)
            aa = np.where(high_home, low, high)
            lh = attack[rows, h] * defense[rows, aa] / league * home_factor
            la = attack[rows, aa] * defense[rows, h] / league / home_factor
            if engine:
                lh,la=engine.series_adjust(h,aa,lh,la)
            hg, ag = rng.poisson(lh), rng.poisson(la)
            home_win = (hg > ag) | ((hg == ag) & (rng.random(n) < lh / (lh + la)))
            high_win = home_win == high_home
            hw += active & high_win
            aw += active & ~high_win
        return np.where(hw >= 4, high, low)
    participants = []
    for a, b in pairs:
        results[:, 0] += np.bincount(a, minlength=columns) + np.bincount(b, minlength=columns)
        np.add.at(opponents, (a, b), 1)
        np.add.at(opponents, (b, a), 1)
        participants.append(play_series(a, b, 1))
    for stage in range(1, 5):
        for a in participants:
            results[:, stage] += np.bincount(a, minlength=columns)
        if stage < 4:
            participants = [play_series(participants[i], participants[i + 1], stage + 1) for i in range(0, len(participants), 2)]
    return {'counts': results, 'points': fields['points'], 'opponents': opponents, 'rates': rt, 'rank': rank}


def forecast(data, history, simulations=50000, params=None, engine=None):
    sim = simulate(data, history, simulations, params, engine)
    output = {'version': 1, 'model': engine.version if engine else MODEL_VERSION, 'season': data['season'], 'start': data['start'],
              'season_games': data['season_games'], 'simulations': simulations,
              'completed_games': sum(g['state'] in {'OFF', 'FINAL'} for g in data['games']),
              'total_games': len(data['games']), 'teams': [], 'history': []}
    finished = [g for g in data['games'] if g['state'] in {'OFF', 'FINAL'}]
    latest = max(finished, key=lambda g: (g['start'], g['id'])) if finished else None
    output['latest_game'] = {k: latest[k] for k in ['id', 'date', 'home', 'away', 'hg', 'ag', 'end']} if latest else None
    for i, team in enumerate(data['teams']):
        points = sim['points'][:, i]
        odds = {stage: round(float(sim['counts'][i, j] / simulations * 100), 4) for j, stage in enumerate(STAGES)}
        hist = np.bincount(points, minlength=data['season_games'] * 2 + 1)
        opponent = sim['opponents'][i]
        output['teams'].append({**team, 'odds': odds, 'projected_points': round(float(points.mean()), 1),
          'points_range': [int(v) for v in np.quantile(points, [.1, .9])],
          'distribution': [[p, round(float(c / simulations * 100), 4)] for p, c in enumerate(hist) if c],
          'opponents': [{'team': data['teams'][j]['abbr'], 'chance': round(float(opponent[j] / simulations * 100), 4)} for j in np.argsort(-opponent) if opponent[j]],
          'attack': round(sim['rates'][i]['attack'], 3), 'defense': round(sim['rates'][i]['defense'], 3)})
    output['teams'].sort(key=lambda t: (-t['odds']['playoffs'], -t['odds']['cup'], t['abbr']))
    if engine:
        output['advanced']=engine.metadata()
    return output


def validate_forecast(data):
    assert data['version'] == 1 and data['model'] in {MODEL_VERSION,'sweater-xg-v2'}
    if data['model']=='sweater-xg-v2':
        assert data.get('advanced',{}).get('version')==2
    assert len(data['teams']) == 32 and len({t['abbr'] for t in data['teams']}) == 32
    assert 100 <= data['simulations'] <= 200000
    assert 0 <= data['completed_games'] <= data['total_games'] == data['season_games'] * 16
    for t in data['teams']:
        values = [t['odds'][stage] for stage in STAGES]
        assert all(math.isfinite(v) and 0 <= v <= 100 for v in values)
        assert all(a >= b for a, b in zip(values, values[1:]))
        assert t['points'] <= t['projected_points'] <= t['points'] + 2 * (data['season_games'] - t['gp']) + .051
        assert abs(sum(prob for _, prob in t['distribution']) - 100) < .02
        assert abs(sum(o['chance'] for o in t['opponents']) - t['odds']['playoffs']) < .02
    for stage, total in zip(STAGES, [1600, 800, 400, 200, 100]):
        assert abs(sum(t['odds'][stage] for t in data['teams']) - total) < .02
    return data
