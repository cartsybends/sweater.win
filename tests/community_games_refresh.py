"""Regressions for stale Grid connections and official trade-season evidence."""
from copy import deepcopy
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grid_refresh', ROOT / 'tools/community_games/refresh_grid.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class GridRefresh(unittest.TestCase):
    def summary(self, teams='CGY', gp=6):
        return {'skater': {'total': 1, 'data': [{'playerId': 8483495,
            'seasonId': 20262027, 'gamesPlayed': gp, 'teamAbbrevs': teams}]}}

    def test_traded_season_counts_actual_games_for_each_club(self):
        games = [{'gameId': i, 'teamAbbrev': team} for i, team in enumerate(['NJD', 'NJD', 'CGY', 'CGY', 'CGY'])]
        rows = refresh.appearance_rows(self.summary('NJD,CGY', 5),
            lambda pid, season: {'playerId': pid, 'gameLog': games}, 2025, 2026)
        self.assertEqual(rows, [[8483495, 'CGY', 2026, 3], [8483495, 'NJD', 2026, 2]])

    def test_trade_logs_must_be_complete_unique_and_match_the_summary(self):
        for games in [[], [{'gameId': 1, 'teamAbbrev': 'NJD'}] * 5,
                      [{'gameId': i, 'teamAbbrev': 'NYR'} for i in range(5)]]:
            with self.assertRaises(ValueError):
                refresh.appearance_rows(self.summary('NJD,CGY', 5),
                    lambda pid, season: {'gameLog': games}, 2025, 2026)

    def test_roster_assignment_zero_games_wrong_seasons_and_partial_responses_do_not_qualify(self):
        summary = self.summary()
        variants = [self.summary(gp=0), deepcopy(summary), deepcopy(summary), deepcopy(summary)]
        variants[1]['skater']['data'][0]['seasonId'] = 20252026
        variants[2]['skater']['total'] = 2
        variants[3]['skater']['data'] *= 2
        variants[3]['skater']['total'] = 2
        for invalid in variants:
            with self.assertRaises(ValueError):
                refresh.appearance_rows(invalid, lambda *args: self.fail('No trade log expected'), 2025, 2026)
        self.assertEqual(refresh.appearance_rows({'skater': {'total': 0, 'data': []}}, None, 2025, 2026), [])
        self.assertEqual(refresh.appearance_rows(self.summary(gp=1), None, 2025, 2026), [[8483495, 'CGY', 2026, 1]])

    def test_emergency_goalie_and_skater_summaries_never_double_count_appearances(self):
        summaries = self.summary(gp=6)
        summaries['goalie'] = self.summary(gp=1)['skater']
        self.assertEqual(refresh.appearance_rows(summaries, None, 2025, 2026), [[8483495, 'CGY', 2026, 6]])

    def test_committed_refresh_extends_nemec_and_all_other_verified_connections_without_mutating_history(self):
        bank = json.loads((ROOT / 'static/community-games/data.json').read_text())
        snapshot = json.loads((ROOT / 'grid_current_cache.json').read_text())
        original = deepcopy(bank)
        attached = refresh.attach_updates(bank, snapshot)
        self.assertEqual(bank, original)
        nemec = next(p for p in attached['players'] if p[0] == 8483495)
        self.assertGreaterEqual(nemec[8]['NJD'], 155)
        self.assertGreaterEqual(nemec[8]['CGY'], 6)
        unplayed = next(team for p in bank['players'] for team in p[8] if team not in nemec[8])
        self.assertNotIn('CGY', next(p for p in bank['players'] if p[0] == 8483495)[8])
        for field in ('grid', 'benchboss', 'teammatetrail', 'links'):
            self.assertEqual(attached[field], original[field])
        corrupted = deepcopy(snapshot)
        next(p for p in corrupted['players'] if p[0] == 8483495)[8][unplayed] = 1
        with self.assertRaises(ValueError):
            refresh.attach_updates(bank, corrupted)

    def test_refresh_requests_only_regular_seasons_after_the_immutable_cutoff(self):
        bank = {'players': [], 'team_cutoff': 2025}
        urls = []
        def fetch(name, url):
            urls.append(url)
            return {'total': 0, 'data': []}, {'url': url, 'sha256': '0' * 64}
        snapshot = refresh.refresh(bank, date(2026, 10, 15), fetch)
        self.assertEqual(snapshot['players'], [])
        self.assertEqual(len(urls), 4)
        self.assertTrue(all('gameTypeId%3D2' in url for url in urls))
        self.assertTrue(all('seasonId%3E%3D20262027' in url for url in urls if '/summary?' in url))

    def test_empty_or_incomplete_refresh_cannot_erase_a_verified_team_connection(self):
        previous = {'appearances': [[8483495, 'CGY', 2026, 6]]}
        current = {'base_team_cutoff': 2025, 'appearances': []}
        with self.assertRaisesRegex(ValueError, 'preserving the last good snapshot'):
            refresh.preserve_verified_connections(previous, current)
        current['appearances'] = [[8483495, 'CGY', 2026, 7]]
        refresh.preserve_verified_connections(previous, current)
        current['base_team_cutoff'] = 2026
        current['appearances'] = []
        refresh.preserve_verified_connections(previous, current)


if __name__ == '__main__':
    unittest.main()
