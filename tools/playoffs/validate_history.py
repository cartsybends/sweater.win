"""Walk-forward evaluation; training and holdout seasons stay separate."""
from datetime import date
import argparse
import json
from pathlib import Path
import numpy as np
from data import schedules, records, fetch, TEAMS
from model import rates, game_probability, simulate, STAGES

ROOT = Path(__file__).resolve().parents[2]
DIVISIONS = {'Atlantic': 'BOS BUF DET FLA MTL OTT TBL TOR', 'Metropolitan': 'CAR CBJ NJD NYI NYR PHI PIT WSH',
             'Central': 'CHI COL DAL MIN NSH STL UTA WPG', 'Pacific': 'ANA CGY EDM LAK SEA SJS VAN VGK'}


def input_at(start, games, cutoff):
    before = [g if g['date'] < cutoff else {k: v for k, v in {**g, 'state': 'FUT'}.items() if k not in {'hg', 'ag', 'end'}} for g in games]
    rec = records(before)
    teams = []
    for t in TEAMS:
        division = next(d for d, clubs in DIVISIONS.items() if t in clubs.split())
        teams.append({'abbr': t, 'name': t, 'conference': 'E' if division in ['Atlantic', 'Metropolitan'] else 'W',
                      'division': division, 'division_code': division[0], **rec[t]})
    return {'start': start, 'season': start * 10000 + start + 1, 'season_games': 82, 'teams': teams, 'games': before, 'bracket': []}


def walk_forward(start, games, history, params):
    data = input_at(start, games, f'{start}-07-01')
    rt, league, _ = rates(data, history, params)
    clubs = {t: i for i, t in enumerate(TEAMS)}
    gf = np.zeros(32)
    ga = np.zeros(32)
    gp = np.zeros(32)
    predictions = []
    for g in games:
        h, a = clubs[g['home']], clubs[g['away']]
        # Priors were built exclusively from earlier seasons. Current-season totals
        # are incremented only AFTER this game's prediction has been recorded.
        attack = [(rt[i]['shape'][0] + gf[i]) / (rt[i]['exposure'] + gp[i]) for i in [h, a]]
        defense = [(rt[i]['shape'][1] + ga[i]) / (rt[i]['exposure'] + gp[i]) for i in [h, a]]
        factor = 1 if g['neutral'] else params['home_factor']
        p = game_probability(attack[0] * defense[1] / league * factor, attack[1] * defense[0] / league / factor)
        predictions.append((p, int(g['hg'] > g['ag'])))
        gf[h] += g['hg']; ga[h] += g['ag']; gf[a] += g['ag']; ga[a] += g['hg']; gp[h] += 1; gp[a] += 1
    return np.array(predictions)


def metrics(p):
    probability, actual = p[:, 0], p[:, 1]
    bins = []
    for lo in np.arange(0, 1, .1):
        mask = (probability >= lo) & (probability < lo + .1)
        if mask.any():
            bins.append({'range': [round(float(lo), 1), round(float(lo + .1), 1)], 'games': int(mask.sum()),
                         'mean_probability': round(float(probability[mask].mean()), 4), 'actual_win_rate': round(float(actual[mask].mean()), 4)})
    return {'games': len(p), 'brier': round(float(((probability - actual) ** 2).mean()), 5),
            'log_loss': round(float(-(actual * np.log(probability) + (1 - actual) * np.log(1 - probability)).mean()), 5),
            'accuracy': round(float(((probability >= .5) == actual).mean()), 4), 'reliability': bins}


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--playoffs', action='store_true');args = parser.parse_args()
    historical = {s: schedules(s, True) for s in [2023, 2024, 2025]}
    candidates = []
    for prior in [20, 40, 60]:
        for home in [1.02, 1.04, 1.06]:
            for regression in [.25, .5]:
                params = {'prior_games': prior, 'home_factor': home, 'prior_regression': regression}
                result = metrics(walk_forward(2024, historical[2024], historical[2023], params))
                candidates.append((result['brier'], params, result))
    _, params, training = min(candidates, key=lambda item: item[0])
    holdout_predictions = walk_forward(2025, historical[2025], historical[2023] + historical[2024], params)
    holdout = metrics(holdout_predictions)
    training_home_rate = sum(g['hg'] > g['ag'] for g in historical[2024]) / len(historical[2024])
    baseline = metrics(np.column_stack([np.repeat(training_home_rate, len(holdout_predictions)), holdout_predictions[:, 1]]))
    summary = f"Walk-forward game validation: {holdout['games']:,} games in 2025–26; Brier score {holdout['brier']:.4f} versus {baseline['brier']:.4f} for a fixed home-team baseline (lower is better). Holdout performance is close to that baseline. This is a beta model; game tests do not establish playoff-probability calibration."
    report = {'version': 1, 'model': 'sweater-goals-v1', 'parameters': params, 'training': {'season': '2024–25', **training},
              'holdout': {'season': '2025–26', **holdout}, 'baseline': {'method': '2024–25 home win rate', **baseline}, 'summary': summary,
              'limitations': ['Goal totals include empty-net and shootout-awarded goals.', 'No injuries, lineups, starting goalies, or expected-goal inputs.',
                              'Game-probability evaluation does not establish playoff-probability calibration.',
                              'Retrospective playoff snapshots use the final published schedule; original postponement publication times are unavailable.']}
    if args.playoffs:
        bracket = fetch('https://api-web.nhle.com/v1/playoff-bracket/2026')
        qualified = {t['abbrev'] for s in bracket['series'] if s['playoffRound'] == 1 for t in [s['topSeedTeam'], s['bottomSeedTeam']]}
        report['playoff_snapshots'] = []
        for cutoff in ['2025-11-15', '2026-01-01', '2026-03-01']:
            data = input_at(2025, historical[2025], cutoff)
            result = simulate(data, historical[2023] + historical[2024], 10000, params)
            predictions = result['counts'][:, 0] / 10000
            actual = np.array([t['abbr'] in qualified for t in data['teams']])
            report['playoff_snapshots'].append({'asof': cutoff, 'simulations': 10000, 'brier': round(float(((predictions-actual)**2).mean()), 5),
              'teams': {t['abbr']: {'probability': round(float(predictions[i]), 4), 'qualified': bool(actual[i])} for i, t in enumerate(data['teams'])}})
            print('Evaluated playoff snapshot', cutoff, flush=True)
    path = Path(__file__).with_name('parameters.json');path.write_text(json.dumps(report, indent=2) + '\n')
    print(summary)


if __name__ == '__main__':
    main()
