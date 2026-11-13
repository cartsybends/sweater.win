"""Probability conservation, NHL seeding, overtime, tiebreaks and data integrity."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/playoffs'))
import data as D
import model as M
import games as A
from validate_history import input_at, DIVISIONS


def fixture():
    teams = []
    for i, t in enumerate(D.TEAMS):
        division = next(d for d, clubs in DIVISIONS.items() if t in clubs.split())
        teams.append({'abbr': t, 'name': t, 'conference': 'E' if division in ['Atlantic', 'Metropolitan'] else 'W',
          'division': division, 'division_code': division[0], 'gp': 82, 'points': 120-i, 'wins': 60-i//2,
          'rw': 50-i//2, 'row': 55-i//2, 'gf': 280-i, 'ga': 240+i})
    return {'start': 2025, 'season': 20252026, 'season_games': 82, 'teams': teams, 'games': [], 'bracket': []}


class Rules(unittest.TestCase):
    def test_published_feed(self):
        A.validate_analytics(M.validate_forecast(json.loads((ROOT / 'playoffs_cache.json').read_text())))

    def test_correct_regular_season_outcome_points(self):
        def game(end, hg, ag):
            return {'state': 'OFF', 'home': 'VAN', 'away': 'SEA', 'hg': hg, 'ag': ag, 'end': end}
        for end in ['REG', 'OT', 'SO']:
            r = D.records([game(end, 4, 3)])
            self.assertEqual(r['VAN']['points'], 2)
            self.assertEqual(r['SEA']['points'], int(end != 'REG'))
            self.assertEqual(r['VAN']['rw'], int(end == 'REG'))
            self.assertEqual(r['VAN']['row'], int(end != 'SO'))
            self.assertEqual(r['VAN']['gf'], 4)

    def test_inconsistent_official_standings_rejected(self):
        standings = {'standings': [{'teamAbbrev': {'default': t}, 'gamesPlayed': 0, 'points': 0, 'wins': 0,
          'regulationWins': 0, 'regulationPlusOtWins': 0, 'goalFor': 0, 'goalAgainst': 0} for t in D.TEAMS]}
        D.validate_snapshot([], standings)
        standings['standings'][0]['points'] = 2
        with self.assertRaisesRegex(ValueError, 'not reconciled'):
            D.validate_snapshot([], standings)

    def test_live_score_changes_do_not_recompute_postgame_model(self):
        data=fixture()
        data['games']=[{'id':2025020001,'date':'2025-10-01','state':'FUT'}]
        before=D.model_signature(data,M.DEFAULTS,50000)
        data['games'][0]['state']='LIVE'
        self.assertEqual(before,D.model_signature(data,M.DEFAULTS,50000))
        data['games'][0].update(state='OFF',hg=4,ag=3,end='OT')
        self.assertNotEqual(before,D.model_signature(data,M.DEFAULTS,50000))

    def test_no_future_data_in_priors_or_retrospective_inputs(self):
        data = fixture()
        future = {'season': 20262027, 'state': 'OFF', 'date': '2026-10-01', 'home': 'VAN', 'away': 'SEA', 'hg': 1000, 'ag': 0, 'end': 'REG'}
        a, league, _ = M.rates(data, [])
        b, league2, _ = M.rates(data, [future])
        self.assertEqual(league, league2)
        self.assertEqual([r['attack'] for r in a], [r['attack'] for r in b])
        historic = {**future, 'season': 20252026, 'date': '2025-12-01'}
        snapshot = input_at(2025, [historic], '2025-11-01')
        self.assertNotIn('hg', snapshot['games'][0])
        self.assertTrue(all(t['gp'] == 0 for t in snapshot['teams']))

    def test_odd_home_game_excluded_from_head_to_head(self):
        games = [{'id': i+1, 'date': f'2025-10-0{i+1}', 'home': h, 'away': a} for i, (h, a) in enumerate([('VAN','SEA'), ('SEA','VAN'), ('VAN','SEA')])]
        excluded, meetings = M.odd_games(games, {'VAN': 0, 'SEA': 1})
        self.assertEqual(excluded, {1})
        self.assertEqual(meetings[0,1], 2)

    def test_every_tiebreak_precedes_the_next(self):
        z = lambda: np.zeros((1, 2), dtype=np.int16)
        points, rw, row, wins, diff, gf = [z() for _ in range(6)]
        head = np.zeros((1,2,2), dtype=np.uint8);meetings=np.array([[0,2],[2,0]])
        lottery = np.array([[.9,.1]])
        for field in [points, rw, row, wins]:
            field[0,1] = 1
            rank = M.rank_teams(points,rw,row,wins,head,meetings,diff,gf,lottery)
            self.assertEqual(rank[0,0], 1)
            field[0,1] = 0
        head[0,1,0] = 3;head[0,0,1] = 1;diff[0,0] = 99
        self.assertEqual(M.rank_teams(points,rw,row,wins,head,meetings,diff,gf,lottery)[0,0],1)
        head.fill(0);diff[0,0]=0;diff[0,1]=1
        self.assertEqual(M.rank_teams(points,rw,row,wins,head,meetings,diff,gf,lottery)[0,0],1)
        diff.fill(0);gf[0,1]=1
        self.assertEqual(M.rank_teams(points,rw,row,wins,head,meetings,diff,gf,lottery)[0,0],1)

    def test_multi_team_head_to_head_uses_points_percentage(self):
        base = np.zeros((1,3),dtype=np.int16)
        head=np.array([[[0,2,2],[0,0,3],[2,3,0]]],dtype=np.uint8)
        meetings=np.array([[0,1,2],[1,0,3],[2,3,0]])
        # 4/6, 3/8, 5/10: team 0 wins despite team 2 earning more raw points.
        rank=M.rank_teams(base,base,base,base,head,meetings,base,base,np.zeros((1,3)))
        self.assertEqual(rank[0].tolist(),[0,2,1])

    def test_division_brackets_and_cross_division_wildcards(self):
        data=fixture();teams=data['teams'];idx={t['abbr']:i for i,t in enumerate(teams)}
        order='TOR TBL FLA BOS MTL BUF DET OTT CAR NJD NYR NYI PHI PIT CBJ WSH COL DAL MIN WPG STL NSH CHI UTA VGK EDM LAK VAN CGY SEA ANA SJS'.split()
        ranks=np.array([[idx[t] for t in order]])
        pairs,_=M.playoff_pairs(ranks,teams)
        named=[(teams[a[0]]['abbr'],teams[b[0]]['abbr']) for a,b in pairs]
        self.assertEqual(named[:4],[('TOR','MTL'),('TBL','FLA'),('CAR','BOS'),('NJD','NYR')])
        self.assertEqual(len({t for pair in named for t in pair}),16)

    def test_qualification_and_advancement_probability_conservation(self):
        data=fixture()
        a=M.forecast(data,[],1000);b=M.forecast(data,[],1000)
        self.assertEqual(a,b)
        for key,total in zip(M.STAGES,[1600,800,400,200,100]):
            self.assertAlmostEqual(sum(t['odds'][key] for t in a['teams']),total,places=3)
        self.assertTrue(all(t['odds']['playoffs'] in [0,100] for t in a['teams']))
        for t in a['teams']:
            self.assertEqual(t['projected_points'],next(r['points'] for r in data['teams'] if r['abbr']==t['abbr']))

    def test_confirmed_series_winner_cannot_be_eliminated_retroactively(self):
        data=fixture();teams=data['teams'];ranks=np.array([sorted(range(32),key=lambda i:-teams[i]['points'])]);pairs,_=M.playoff_pairs(ranks,teams)
        data['bracket']=[{'round':1,'home':teams[a[0]]['abbr'],'away':teams[b[0]]['abbr'],'hw':4,'aw':0} for a,b in pairs]
        result=M.forecast(data,[],1000)
        winners={s['home'] for s in data['bracket']}
        self.assertTrue(all(t['odds']['round2']==(100 if t['abbr'] in winners else 0) for t in result['teams']))

    def test_poisson_probability_symmetry_and_strength(self):
        self.assertAlmostEqual(M.game_probability(3,3),.5,places=10)
        self.assertGreater(M.game_probability(4,2),.7)
        self.assertAlmostEqual(M.game_probability(4,2)+M.game_probability(2,4),1,places=10)

    def test_training_and_holdout_report_present_and_separate(self):
        report=json.loads((ROOT/'tools/playoffs/parameters.json').read_text())
        self.assertEqual(report['training']['season'],'2024–25')
        self.assertEqual(report['holdout']['season'],'2025–26')
        self.assertEqual(len(report['playoff_snapshots']),3)
        self.assertEqual(report['holdout']['games'],1312)


class GameAnalytics(unittest.TestCase):
    def game(self, gid, day, hg=3, ag=2, end='REG', state='OFF'):
        return {'id':gid,'season':20262027,'date':day,'start':day+'T23:00:00Z','home':'VAN','away':'SEA','neutral':False,'state':state,**({'hg':hg,'ag':ag,'end':end} if state=='OFF' else {})}

    def output(self, games):
        d=fixture();d.update(start=2026,season=20262027,season_games=84,games=games)
        return d,{'model':M.MODEL_VERSION,'parameters':M.parameters(),'teams':copy.deepcopy(d['teams'])}

    def fetch(self,url):
        gid=int(url.split('/')[-2]);g=self.lookup[gid]
        return {'id':gid,'gameState':'OFF','homeTeam':{'abbrev':'VAN','score':g['hg'],'sog':31},'awayTeam':{'abbrev':'SEA','score':g['ag'],'sog':24}}

    def test_reconstructions_never_use_the_game_result_or_later_games(self):
        games=[self.game(1,'2026-11-10'),self.game(2,'2026-11-11')]
        self.lookup={g['id']:g for g in games};d,out=self.output(games)
        original=A.enrich(out,d,[],{},self.fetch,'2026-11-12T18:00:00Z')
        p=original['games'][0]['prediction']
        changed=copy.deepcopy(games);changed[0]['hg']=20;changed[1]['hg']=22
        self.lookup={g['id']:g for g in changed};d,out=self.output(changed)
        newer=A.enrich(out,d,[],{},self.fetch,'2026-11-12T18:00:00Z')
        self.assertEqual(p,newer['games'][0]['prediction'])
        self.assertNotEqual(original['games'][1]['prediction']['home_win'],newer['games'][1]['prediction']['home_win'])
        self.assertEqual(p['basis'],'reconstructed');self.assertIsNone(p['at'])

    def test_pregame_estimates_are_frozen_after_puck_drop(self):
        game=self.game(1,'2026-11-13',state='FUT');d,out=self.output([game])
        initial=A.enrich(out,d,[],{},lambda _: {},'2026-11-13T18:00:00Z')
        self.assertEqual(initial['games'][0]['prediction']['basis'],'pregame')
        saved=copy.deepcopy(initial['games'][0]['prediction'])
        # New results before the target date would change a fresh estimate, but
        # cannot replace the already-recorded pregame number once play begins.
        earlier=self.game(2,'2026-11-12',hg=10,ag=1);game.update(state='OFF',hg=3,ag=2,end='REG')
        self.lookup={1:game,2:earlier};d,out=self.output([earlier,game])
        later=A.enrich(out,d,[],initial,self.fetch,'2026-11-14T03:00:00Z')
        p=next(g for g in later['games'] if g['id']==1)['prediction']
        self.assertEqual(p,{**saved,'basis':'recorded'})

    def test_official_shots_reconcile_with_the_exact_final(self):
        g=self.game(1,'2026-11-12');self.lookup={1:g}
        self.assertEqual(A.boxscore_stats(g,self.fetch),{'home_shots':31,'away_shots':24})
        with self.assertRaises(ValueError):A.boxscore_stats(g,lambda _: {'id':1,'gameState':'OFF','homeTeam':{'abbrev':'VAN','score':4},'awayTeam':{'abbrev':'SEA','score':2}})

    def test_missing_shots_stay_missing_instead_of_becoming_zero(self):
        g=self.game(1,'2026-11-12');d,out=self.output([g])
        result=A.enrich(out,d,[],{},lambda _: {},'2026-11-13T18:00:00Z')
        self.assertNotIn('home_shots',result['games'][0]);self.assertNotIn('away_shots',result['games'][0])

    def test_form_uses_only_ten_completed_games(self):
        games=[self.game(i+1,f'2026-11-{i+1:02}',hg=3,ag=2,end='OT' if i%2 else 'REG') for i in range(12)]
        d,out=self.output(games);self.lookup={g['id']:g for g in games}
        result=A.enrich(out,d,[],{},self.fetch,'2026-11-13T18:00:00Z')
        van=next(t for t in result['teams'] if t['abbr']=='VAN');sea=next(t for t in result['teams'] if t['abbr']=='SEA')
        self.assertEqual(van['form']['gp'],10);self.assertEqual(van['form']['points'],20);self.assertEqual(sea['form']['points'],5)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--feed-only',action='store_true');args=parser.parse_args()
    if args.feed_only:
        A.validate_analytics(M.validate_forecast(json.loads((ROOT/'playoffs_cache.json').read_text())));print('Verified 32-team forecast, probability totals, game estimates, results and NHL analytics')
    else:
        unittest.main(argv=[sys.argv[0]])
