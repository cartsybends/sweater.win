"""Archive integrity, daily cutoffs, version preservation and failure behaviour."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/playoffs'))
from archive import capture, snapshot, timestamp, ZONE


class Archive(unittest.TestCase):
    def setUp(self):
        self.feed = json.loads((ROOT / 'playoffs_cache.json').read_text())

    def test_published_daily_snapshots_have_exact_content_hashes_and_original_team_data(self):
        index = json.loads((ROOT / 'playoffs_archive/index.json').read_text())
        self.assertEqual(index['time_zone'], ZONE)
        previous = ''
        for entry in index['days']:
            self.assertGreater(entry['date'], previous)
            content = (ROOT / 'playoffs_archive' / (entry['date'] + '.json')).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry['sha256'])
            data = json.loads(content)
            self.assertEqual(data['checked_at'], entry['checked_at'])
            self.assertEqual(data['archive']['date'], entry['date'])
            self.assertEqual(data['archive']['kind'], 'recorded')
            self.assertEqual(len(data['teams']), 32)
            self.assertFalse(data['games'])
            self.assertFalse(data['history'])
            previous = entry['date']

    def test_compact_snapshot_keeps_all_five_stages_records_and_full_team_breakdowns(self):
        saved = snapshot(self.feed)
        self.assertEqual(saved['teams'], self.feed['teams'])
        self.assertEqual(saved['model'], self.feed['model'])
        self.assertEqual(saved['updated_at'], self.feed['updated_at'])
        self.assertNotIn('starter_feed', saved)
        self.assertNotIn('analytics_version', saved)
        saved['teams'][0]['points'] = -1
        self.assertGreaterEqual(self.feed['teams'][0]['points'], 0)

    def test_newer_check_replaces_only_its_day_older_checks_cannot_move_archive_backwards(self):
        with tempfile.TemporaryDirectory() as folder:
            original = copy.deepcopy(self.feed)
            original.update(updated_at='2026-11-14T23:00:00Z', checked_at='2026-11-14T23:01:00Z')
            self.assertTrue(capture(original, folder))
            path = Path(folder) / '2026-11-14.json'
            first = path.read_bytes()
            newer = {**original, 'checked_at': '2026-11-15T04:59:00Z'}
            self.assertTrue(capture(newer, folder))
            second = path.read_bytes()
            self.assertNotEqual(first, second)
            self.assertFalse(capture(original, folder))
            self.assertEqual(path.read_bytes(), second)
            self.assertFalse(capture(newer, folder))

    def test_midnight_uses_nhl_eastern_dates_including_daylight_saving_changes(self):
        for checked, day in [('2026-11-15T04:59:59Z', '2026-11-14'),
                             ('2026-11-15T05:00:00Z', '2026-11-15'),
                             ('2026-07-02T03:59:59Z', '2026-07-01'),
                             ('2026-07-02T04:00:00Z', '2026-07-02')]:
            feed = {**self.feed, 'checked_at': checked, 'updated_at': checked}
            self.assertEqual(snapshot(feed)['archive']['date'], day)

    def test_bad_timestamp_or_invalid_forecast_does_not_replace_an_existing_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            capture(self.feed, folder)
            before = {p.name: p.read_bytes() for p in Path(folder).glob('*.json')}
            for mutate in [lambda d: d.update(updated_at='2099-01-01T00:00:00Z'),
                           lambda d: d['teams'][0]['odds'].update(cup=101)]:
                bad = copy.deepcopy(self.feed)
                mutate(bad)
                with self.assertRaises((ValueError, AssertionError)):
                    capture(bad, folder)
                self.assertEqual(before, {p.name: p.read_bytes() for p in Path(folder).glob('*.json')})
            with self.assertRaises(ValueError):
                timestamp('2026-11-15T12:00:00')


if __name__ == '__main__':
    unittest.main()
