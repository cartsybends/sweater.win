"""Lineup inference, chronological player features and published preview integrity."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/playoffs'))
import player_data
from lineup_data import groups, special, infer
from lineups import special_rates, supplement
from matchups import compact, for_game
from player_model import History, FEATURES, goal_allocation


class Previews(unittest.TestCase):
    def test_short_nhl_game_reports_page_without_accepting_duplicates(self):
        day = '2026-11-19'
        rows = [{'gameId': 2026020001, 'playerId': pid} for pid in range(1, 8)]
        starts = []

        def fetch(url):
            query = parse_qs(urlparse(url).query)
            self.assertEqual(query['limit'], ['1000'])
            self.assertEqual([item['property'] for item in json.loads(query['sort'][0])], ['gameId', 'playerId'])
            start = int(query['start'][0])
            starts.append(start)
            return {'data': rows[start:start+3], 'total': len(rows)}

        with TemporaryDirectory() as cache, patch.object(player_data, 'CACHE', Path(cache)), patch.object(player_data.time, 'sleep'):
            with patch.object(player_data, 'get_json', side_effect=lambda url: {'data': rows[:3], 'total': len(rows)}):
                with self.assertRaisesRegex(ValueError, 'offset 3 of 7'):
                    player_data.report('skater', 'summary', 2026, day, day)
            self.assertFalse(list(Path(cache).iterdir()))
            with patch.object(player_data, 'get_json', side_effect=fetch):
                result = player_data.report('skater', 'summary', 2026, day, day)
            self.assertEqual([row['playerId'] for row in result], list(range(1, 8)))
            self.assertEqual(starts, [0, 3, 6])

    def test_report_restarts_when_the_nhl_posts_more_rows_between_pages(self):
        day = '2026-11-19'
        rows = [{'gameId': 2026020001, 'playerId': pid, 'totalFaceoffs': 2} for pid in range(1, 9)]
        starts = []

        def fetch(url):
            start = int(parse_qs(urlparse(url).query)['start'][0])
            starts.append(start)
            if len(starts) == 1:
                return {'data': [{**row, 'totalFaceoffs': 1} for row in rows[:3]], 'total': 7}
            return {'data': rows[start:start+3], 'total': len(rows)}

        with TemporaryDirectory() as cache, patch.object(player_data, 'CACHE', Path(cache)):
            with patch.object(player_data, 'get_json', side_effect=fetch), patch.object(player_data.time, 'sleep') as wait:
                result = player_data.report('skater', 'faceoffwins', 2026, day, day)
            wait.assert_called_once_with(1)
            self.assertEqual(starts, [0, 3, 0, 3, 6])
            self.assertEqual([row['playerId'] for row in result], list(range(1, 9)))
            self.assertTrue(all(row['totalFaceoffs'] == 2 for row in result))

    def test_disjoint_units_optimize_total_overlap_without_inventing_players(self):
        units=groups(range(1,7),{(1,2,3):100,(1,4,5):90,(2,3,6):90},3,2)
        self.assertEqual(sum(g['seconds'] for g in units),180)
        self.assertEqual(len({p for g in units for p in g['players']}),6)
        self.assertEqual(groups(range(1,13),{(1,2,3):10},3,4),[])
        self.assertEqual(len(groups(range(1,12),{(1,2,3):80,(4,5,6):90,(7,8,9):100},3,4)),3)

    def test_special_units_require_distinct_personnel_and_observed_time(self):
        rows={((1,2,3,4,5),4):80,((1,2,3,4,6),4):70,((6,7,8,9,10),4):60}
        units=special(rows)
        self.assertEqual([u['seconds'] for u in units],[80,60])
        self.assertEqual(special({((1,2,3,4),3):9}),[])

    def test_shift_inference_excludes_empty_net_units_and_rejects_source_disagreement(self):
        game={'id':2026020316,'home':'TBL','away':'DET','start':'2026-11-15T00:00:00Z'}
        box={'id':game['id'],'season':20262027,'gameDate':'2026-11-14','startTimeUTC':game['start'],'gameType':2,'gameState':'OFF',
             'homeTeam':{'id':14,'abbrev':'TBL','score':2},'awayTeam':{'id':17,'abbrev':'DET','score':1},'playerByGameStats':{}}
        for side,offset in [('home',0),('away',100)]:
            box['playerByGameStats'][side+'Team']={
              'forwards':[{'playerId':offset+p,'position':'C' if p==2 else 'L','toi':'20:00','name':{'default':f'Player {offset+p}'}} for p in range(1,13)],
              'defense':[{'playerId':offset+p,'position':'D','toi':'20:00','name':{'default':f'Player {offset+p}'}} for p in range(13,19)],
              'goalies':[{'playerId':offset+90}]}
        pbp={k:v for k,v in box.items() if k!='playerByGameStats'};pbp['plays']=[];pbp['rosterSpots']=[]
        rows=[]
        def shift(pid,start,end):rows.append({'playerId':pid,'period':1,'startTime':start,'endTime':end})
        # A real 5-on-4, followed by a pulled-goalie 5-on-4, then five-on-five.
        for pid in [1,2,3,13,14,90]:shift(pid,'00:00','20:00')
        for pid in [101,102,113,114]:shift(pid,'00:00','20:00')
        shift(190,'00:00','05:00');shift(190,'10:00','20:00');shift(103,'10:00','20:00')
        result=infer(game,box,{'data':rows,'total':len(rows)},pbp)
        self.assertEqual(result['teams']['TBL']['pp'][0]['seconds'],300)
        self.assertEqual(result['teams']['TBL']['five_on_five_seconds'],600)
        bad=copy.deepcopy(pbp);bad['homeTeam']['score']=3
        with self.assertRaisesRegex(ValueError,'disagree'):infer(game,box,{'data':rows,'total':len(rows)},bad)

    def test_weighted_faceoffs_and_unknown_blocks_are_preserved(self):
        h=History()
        base={'p':1,'season':2026,'opp':'NYR','goals':1,'shots':2,'seconds':900,'pp':None,'blocks':2}
        h.add({**base,'fo_wins':1,'fo_total':2})
        h.add({**base,'fo_wins':9,'fo_total':10})
        self.assertEqual(h.season_stats(1,2026)['fo'],83.333)
        self.assertEqual(h.season_stats(1,2026)['sog'],2)
        h.add({**base,'blocks':None,'fo_wins':None,'fo_total':None})
        self.assertIsNone(h.season_stats(1,2026)['blocks'])
        self.assertIsNone(h.season_stats(1,2026)['fo'])
        self.assertIsNone(h.season_stats(99,2026)['sog'])
        self.assertTrue(all(math.isfinite(v) for v in h.features(1,2026,'NYR','C')))

    def test_player_allocation_conserves_team_forecast_including_new_players(self):
        players=[{'id':p,'position':'D' if p<7 else 'C'} for p in range(1,19)]
        parameters=json.loads((ROOT/'tools/playoffs/player_parameters.json').read_text())
        self.assertEqual(parameters['features'],FEATURES)
        allocation=goal_allocation(players,History(),2026,'MTL',3.27,parameters['weights'])
        self.assertAlmostEqual(sum(allocation.values()),3.27)
        self.assertTrue(all(v>0 for v in allocation.values()))
        with self.assertRaises(ValueError):goal_allocation(players*2,History(),2026,'MTL',3,parameters['weights'])

    def test_pp_pk_use_total_opportunities_and_strictly_earlier_nhl_dates(self):
        rows={'powerplay':[],'penaltykill':[]}
        for date,goals,opportunities in [('2026-11-14',1,1),('2026-11-15',0,9),('2026-11-16',5,5)]:
            rows['powerplay'].append({'teamId':10,'gameDate':date,'powerPlayGoalsFor':goals,'ppOpportunities':opportunities})
            rows['penaltykill'].append({'teamId':10,'gameDate':date,'ppGoalsAgainst':goals,'timesShorthanded':opportunities})
        rates=special_rates('TOR',{'team_id':10},'2026-11-16',rows)
        self.assertEqual(rates,{'pp':10,'pk':90})

    def test_schedule_history_keeps_finals_future_dates_and_franchise_identity(self):
        g={'id':2026020331,'home':'UTA','away':'SEA'}
        rows=[{'id':2026020000+i,'season':20262027,'type':2,'date':f'2026-11-{i:02d}',
               'start':f'2026-11-{i:02d}T23:00:00Z','home':'UTA','away':'SEA','state':'OFF','hg':2,'ag':1,'end':'OT'} for i in range(1,13)]
        rows += [{**rows[0],'id':2023020001,'home':'ARI','season':20232024},
                 {**rows[0],'id':2026020400,'date':'2026-12-01','start':'2026-12-01T23:00:00Z','state':'FUT'}]
        data=for_game(g,rows,'2026-11-16T12:00:00Z')
        self.assertEqual(len(data['recent']),10)
        self.assertEqual(data['wins'],{'UTA':10,'SEA':0})
        self.assertEqual(len(data['season']),13)
        self.assertEqual(data['season'][-1]['state'],'FUT')
        self.assertIsNone(compact({'id':2026010001,'gameType':1},2026))

    def test_schedule_holds_a_game_marked_over_until_the_final_is_official(self):
        raw = {'id': 2026020347, 'gameType': 2, 'gameDate': '2026-11-19', 'startTimeUTC': '2026-11-20T00:00:00Z',
               'homeTeam': {'abbrev': 'TOR', 'score': 3}, 'awayTeam': {'abbrev': 'LAK', 'score': 4},
               'gameState': 'OVER', 'gameOutcome': {'lastPeriodType': 'SO'}}
        pending = compact(raw, 2026)
        self.assertEqual(pending['state'], 'CRIT')
        self.assertEqual((pending['hg'], pending['ag']), (3, 4))
        check = '2026-11-20T03:00:00Z'
        report = for_game(pending, [pending], check)
        self.assertEqual(report['season'], [pending])
        self.assertEqual(report['recent'], [])
        final = compact({**raw, 'gameState': 'FINAL'}, 2026)
        self.assertEqual(for_game(final, [final], check)['wins'], {'TOR': 0, 'LAK': 1})

    def test_league_special_team_ranks_require_all_clubs_and_share_tied_ranks(self):
        rows={'powerplay':[],'penaltykill':[]}
        for club in range(32):
            rows['powerplay'].append({'teamId':club,'gameDate':'2026-11-15','powerPlayGoalsFor':club+1,'ppOpportunities':100})
            rows['penaltykill'].append({'teamId':club,'gameDate':'2026-11-15','ppGoalsAgainst':club+1,'timesShorthanded':100})
        rates=special_rates('TOR',{'team_id':2},'2026-11-16',rows)
        self.assertEqual(rates['ranks'],{'pp':30,'pk':3})
        rows['powerplay'][1].update(powerPlayGoalsFor=3,ppOpportunities=100)
        self.assertEqual(special_rates('TOR',{'team_id':1},'2026-11-16',rows)['ranks']['pp'],30)
        # Adding future results cannot change this game's historical medal.
        rows['powerplay'].append({'teamId':2,'gameDate':'2026-11-16','powerPlayGoalsFor':100,'ppOpportunities':100})
        self.assertEqual(special_rates('TOR',{'team_id':2},'2026-11-16',rows)['ranks']['pp'],30)
        rows['powerplay']=rows['powerplay'][1:]
        self.assertNotIn('pp',special_rates('TOR',{'team_id':2},'2026-11-16',rows)['ranks'])

    def test_published_units_stats_chronology_and_goal_totals(self):
        paths=list((ROOT/'playoffs_lines/matchups').glob('*.json'))
        self.assertGreater(len(paths),0)
        for path in paths:
            d=json.loads(path.read_text())
            for t in d['teams'].values():
                if t['status']=='unavailable':continue
                self.assertLess(t['source_game']['start'],d['start'])
                self.assertLess(t['stats_through'],d['start'][:10])
                self.assertAlmostEqual(sum(p['expected_goals'] for p in t['players']),t['team_goals'],places=4)
                assigned=[p for key in ('f','d') for u in t['units'][key] for p in u['players']]
                self.assertEqual(len(assigned),len(set(assigned)))
                self.assertEqual(set(assigned+t['other']),{p['id'] for p in t['players']})
                for p in t['players']:
                    self.assertGreaterEqual(p['stats']['gp'],0)
                    if not p['stats']['fo_attempts']:self.assertIsNone(p['stats']['fo'])

    def test_observed_reports_do_not_duplicate_players_between_regular_units(self):
        for path in (ROOT/'playoffs_lines/observed').glob('*.json'):
            d=json.loads(path.read_text())
            for t in d['teams'].values():
                assigned=[p for key in ('f','d') for u in t[key] for p in u['players']]
                self.assertEqual(len(assigned),len(set(assigned)))
                self.assertEqual(set(assigned+t['other']),{p['id'] for p in t['players']})
                self.assertTrue(all(u['seconds']>=20 for key in ('f','d') for u in t[key]))


if __name__=='__main__':unittest.main()
