"""TOI selection uses average usage, verified club splits and active skaters."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('toi',ROOT/'tools/deep_cut/toi.py')
toi=importlib.util.module_from_spec(spec)
spec.loader.exec_module(toi)


class ToiTests(unittest.TestCase):
    def test_average_usage_not_total_minutes_selects_exactly_six_skaters(self):
        players={i:[i,'Player','G' if i==9 else 'D'] for i in range(1,11)}
        roster={i:'CGY' for i in players}
        rows=[[i,'CGY',20262027,20 if i!=8 else 1,400+i*60] for i in range(1,10)]
        selected,season=toi.lowest_six(players,roster,rows,True)
        self.assertEqual(selected['CGY'],[1,2,3,4,5,6]);self.assertEqual(season,20262027)
        self.assertNotIn(8,selected['CGY'],'One appearance must not make a high-usage player low TOI')
        self.assertNotIn(9,selected['CGY'],'Goalies are excluded')
        self.assertNotIn(10,selected['CGY'],'Missing usage is never treated as zero')

    def test_traded_players_use_each_clubs_actual_game_log_toi(self):
        summary={'total':1,'data':[{'playerId':8470001,'seasonId':20262027,'gamesPlayed':2,'teamAbbrevs':'BOS,CGY','timeOnIcePerGame':600}]}
        rows=toi.usage_rows(summary,lambda *args:{'gameLog':[{'gameId':1,'teamAbbrev':'BOS','toi':'08:00'},{'gameId':2,'teamAbbrev':'CGY','toi':'12:00'}]})
        self.assertEqual(rows,[[8470001,'BOS',20262027,1,480.0],[8470001,'CGY',20262027,1,720.0]])

    def test_partial_logs_or_inconsistent_averages_are_rejected(self):
        summary={'total':1,'data':[{'playerId':8470001,'seasonId':20262027,'gamesPlayed':2,'teamAbbrevs':'BOS,CGY','timeOnIcePerGame':600}]}
        for games in [[],[{'gameId':1,'teamAbbrev':'BOS','toi':'08:00'},{'gameId':1,'teamAbbrev':'CGY','toi':'12:00'}],[{'gameId':1,'teamAbbrev':'BOS','toi':'99:99'},{'gameId':2,'teamAbbrev':'CGY','toi':'12:00'}],[{'gameId':1,'teamAbbrev':'BOS','toi':'18:00'},{'gameId':2,'teamAbbrev':'CGY','toi':'12:00'}]]:
            with self.assertRaises(ValueError):toi.usage_rows(summary,lambda *args:{'gameLog':games})

    def test_zero_missing_and_old_season_usage_never_create_artificial_low_minutes(self):
        players={i:[i,'Player','C'] for i in range(1,9)};roster={i:'CGY' for i in players}
        rows=[[i,'CGY',20262027,10,500+i*60] for i in range(1,8)]+[[8,'CGY',20252026,50,1]]
        self.assertNotIn(8,toi.lowest_six(players,roster,rows,True)[0]['CGY'])
        with self.assertRaises(ValueError):toi.lowest_six(players,roster,rows[:5],True)


if __name__=='__main__':unittest.main()
