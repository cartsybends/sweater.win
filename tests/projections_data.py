import importlib.util,json,unittest
from datetime import date
from pathlib import Path
spec=importlib.util.spec_from_file_location('projection_data',Path(__file__).resolve().parents[1]/'tools/projections/data.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProjectionDataTests(unittest.TestCase):
 def setUp(self):
  self.roster=[{'id':1000000+i,'name':'Player '+str(i),'pos':'C','team':sorted(m.TEAMS)[i%32]} for i in range(640)]
  self.summary={'data':[{'playerId':1000000,'seasonId':20262027,'skaterFullName':'Test Player','positionCode':'C','teamAbbrevs':'ANA,BOS','gamesPlayed':10,'goals':4,'assists':8,'points':12}],'total':1}
  self.clubs={'standings':[{'teamAbbrev':{'default':t},'gamesPlayed':12,'seasonId':20262027} for t in sorted(m.TEAMS)]}
 def fetch(self,url):return self.clubs if '/standings/' in url else self.summary
 def test_complete_snapshot_combines_traded_totals_and_includes_zero_game_roster_players(self):
  d=m.collect(self.fetch,self.roster,date(2026,11,12));p=d['players'][0]
  self.assertEqual(len(d['players']),640);self.assertEqual(p['points'],12);self.assertEqual(p['gp'],10);self.assertEqual(p['team'],'ANA');self.assertEqual(p['teamGP'],12);self.assertEqual(d['players'][1]['gp'],0)
 def test_unconfirmed_traded_current_club_is_not_guessed_from_alphabetical_abbreviations(self):
  self.roster=self.roster[1:];d=m.collect(self.fetch,self.roster,date(2026,11,12));self.assertIsNone(d['players'][0]['team']);self.assertIsNone(d['players'][0]['teamGP'])
 def test_incomplete_duplicate_or_wrong_season_records_are_rejected(self):
  self.summary['total']=2
  with self.assertRaises(ValueError):m.collect(self.fetch,self.roster,date(2026,11,12))
  self.summary['data']*=2
  with self.assertRaises(ValueError):m.collect(self.fetch,self.roster,date(2026,11,12))
 def test_wrong_club_season_or_inconsistent_points_are_rejected(self):
  self.clubs['standings'][0]['seasonId']=20252026
  with self.assertRaises(ValueError):m.collect(self.fetch,self.roster,date(2026,11,12))
  self.clubs['standings'][0]['seasonId']=20262027;self.summary['data'][0]['points']=13
  with self.assertRaises(AssertionError):m.collect(self.fetch,self.roster,date(2026,11,12))
 def test_published_cache_covers_every_club_and_valid_stats(self):
  d=json.loads(m.CACHE.read_text());m.validate(d);self.assertEqual(len(d['team_games']),32);self.assertGreater(len(d['players']),700);self.assertEqual(d['season_games'],84)
if __name__=='__main__':unittest.main()
