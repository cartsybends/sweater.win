import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("team_careers", ROOT / "tools/team_games/update_careers.py")
careers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(careers)


class CareerOrderTests(unittest.TestCase):
    def test_trade_order_comes_from_dates_not_the_season_totals_order(self):
        rows = [(2005, "SJS", 2), (2005, "BOS", 2), (2006, "SJS", 82)]
        games = [{"gameId": 4, "gameDate": "2006-01-01", "teamAbbrev": "SJS"},
                 {"gameId": 2, "gameDate": "2005-11-01", "teamAbbrev": "BOS"},
                 {"gameId": 3, "gameDate": "2005-12-01", "teamAbbrev": "SJS"},
                 {"gameId": 1, "gameDate": "2005-10-01", "teamAbbrev": "BOS"}]
        out = careers.verified_stints(rows, lambda _: games)
        self.assertEqual(out, [{"team": "BOS", "from": 2005, "to": 2005, "gp": 2},
                               {"team": "SJS", "from": 2005, "to": 2006, "gp": 84}])

    def test_return_to_the_same_club_within_one_season_is_a_separate_stop(self):
        rows = [(2022, "FLA", 2), (2022, "VAN", 1)]
        games = [{"gameId": i, "gameDate": f"2023-01-0{i}", "teamAbbrev": t}
                 for i, t in enumerate(["FLA", "VAN", "FLA"], 1)]
        self.assertEqual([s["team"] for s in careers.verified_stints(rows, lambda _: games)], ["FLA", "VAN", "FLA"])

    def test_incomplete_or_duplicate_game_logs_are_rejected(self):
        rows = [(2022, "BOS", 1), (2022, "TOR", 1)]
        game = {"gameId": 1, "gameDate": "2023-01-01", "teamAbbrev": "BOS"}
        for log in [[game], [game, {**game, "teamAbbrev": "TOR"}]]:
            with self.assertRaises(ValueError):
                careers.verified_stints(rows, lambda _: log)

    def test_only_actual_nhl_regular_season_appearances_count(self):
        base = {"season": 20222023, "leagueAbbrev": "NHL", "gameTypeId": 2,
                "teamName": {"default": "Boston Bruins"}, "gamesPlayed": 50}
        landing = {"seasonTotals": [base, {**base, "leagueAbbrev": "AHL"},
                   {**base, "gameTypeId": 3}, {**base, "gamesPlayed": 0}]}
        self.assertEqual(careers.season_rows(landing), [(2022, "BOS", 50)])

    def test_historic_jets_and_coyotes_are_not_confused_with_current_clubs(self):
        self.assertEqual(careers.canonical_team("WPG", 1995), "WIN")
        self.assertEqual(careers.canonical_team("WPG", 2011), "WPG")
        self.assertEqual(careers.canonical_team("PHX", 2010), "ARI")
        self.assertEqual(careers.canonical_team("UTA", 2024), "UTA")

    def test_partial_career_records_cannot_replace_verified_timelines(self):
        landing = {"playerId": 1, "careerTotals": {"regularSeason": {"gamesPlayed": 100}},
                   "seasonTotals": [{"season": 20222023, "leagueAbbrev": "NHL", "gameTypeId": 2,
                                     "teamName": {"default": "Boston Bruins"}, "gamesPlayed": 50}]}
        with patch.object(careers, "get_json", return_value=landing), self.assertRaises(ValueError):
            careers.fetch_career(1)

    def test_saved_careers_cover_every_club_and_known_return_visits(self):
        players = json.loads((ROOT / "team_careers.json").read_text())["players"]
        self.assertEqual(len(players), len({p["id"] for p in players}))
        for player in players:
            self.assertEqual(sum(s["gp"] for s in player["stints"]), player["career_gp"])
        for team in careers.TEAMS:
            pool = [p for p in players if 3 <= len(p["stints"]) <= 5 and
                    any(s["team"] == team and s["gp"] >= 20 for s in p["stints"])]
            self.assertGreaterEqual(len(pool), 5, team)
        by_name = {p["name"]: p for p in players}
        for name, path in {"Joe Thornton": ["BOS", "SJS", "TOR", "FLA"],
                           "Roberto Luongo": ["NYI", "FLA", "VAN", "FLA"],
                           "Patrick Marleau": ["SJS", "TOR", "SJS", "PIT", "SJS"],
                           "Wayne Gretzky": ["EDM", "LAK", "STL", "NYR"]}.items():
            self.assertEqual([s["team"] for s in by_name[name]["stints"]], path)


if __name__ == "__main__":
    unittest.main()
