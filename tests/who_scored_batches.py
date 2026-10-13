"""Release boundary tests: unfinished or stale clips must not become playable."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools/who_scored'
sys.path.insert(0, str(TOOLS))
import batch
import discover
import pipeline


class BatchGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records, candidates, sources = [], [], []
        for index in range(40):
            ident = f'goal-{40 + index}'
            pid = 1000 + index
            source_hash = hashlib.sha256(f'original-{ident}'.encode()).hexdigest()
            source = {'id': ident, 'pid': pid, 'source': f'https://nhl.com/video/{ident}',
                      'source_sha256': source_hash, 'jersey': 7, 'official_event_id': index}
            sources.append(source)
            candidates.append({'id': ident, 'pid': pid, 'candidates': [{'source': source['source']}]})
            edit_path = self.root / f'{ident}-edit.json'
            edit_path.write_text(json.dumps({'id': ident, 'pid': pid, 'duration': 2 / 24, 'source_sha256': source_hash}))
            assets = {'masked': f'{ident}-masked-v1.mp4', 'reveal': f'{ident}-original-v1.mp4', 'poster': f'{ident}-v1.jpg'}
            for name in assets.values():
                (self.root / name).write_bytes(name.encode())
            self.records.append({'id': ident, 'pid': pid, 'frames': 2, 'source_sha256': source_hash,
                                 'edit_sha256': batch.digest(edit_path), 'assets': assets,
                                 'asset_sha256': {kind: batch.digest(self.root / name) for kind, name in assets.items()},
                                 'motion': 'Wrist shot', 'reviews': {
                                     'official_identity': {'passed': True, 'jersey': 7, 'event_id': index},
                                     'silhouette_coverage': {'passed': True, 'visually_reviewed_frames': [0, 1], 'note': 'Fixture review.'},
                                     'encoded_video': {'passed': True, 'all_frames_decoded': True, 'matching_pair': True,
                                                       'visually_sampled_frames': [0, 1]}}})
        ids = [record['id'] for record in self.records]
        self.batch = {'ids': ids, 'approved_clips': ids.copy()}
        self.queue = {'candidates': candidates}
        self.audit = {'sources': sources}

    def verify(self, records=None, existing=None):
        return batch.verify_batch(self.batch, self.records if records is None else records,
                                  self.queue, existing or [], self.root, self.audit, self.root)

    def test_complete_forty_passes_without_changing_library(self):
        existing = [{'id': 'goal-01', 'pid': 1}]
        saved = copy.deepcopy(existing)
        with patch.object(batch, 'inspect_media', return_value='0.083333') as inspect, patch.object(batch, 'inspect_poster'):
            self.assertEqual(len(self.verify(existing=existing)), 40)
            self.assertEqual(inspect.call_count, 80)
        self.assertEqual(existing, saved)

    def test_partial_batch_is_rejected_before_media_work(self):
        with patch.object(batch, 'inspect_media') as inspect:
            with self.assertRaisesRegex(ValueError, '3/40'):
                self.verify(self.records[:3])
            inspect.assert_not_called()

    def test_duplicate_or_existing_scorer_is_rejected(self):
        self.records[-1]['pid'] = self.records[0]['pid']
        with self.assertRaisesRegex(ValueError, 'distinct new scorer'):
            self.verify()
        self.records[-1]['pid'] = 1039
        with self.assertRaisesRegex(ValueError, 'distinct new scorer'):
            self.verify(existing=[{'id': 'goal-01', 'pid': 1000}])

    def test_frame_coverage_and_three_review_passes_are_required(self):
        coverage = self.records[0]['reviews']['silhouette_coverage']
        coverage['visually_reviewed_frames'] = [0]
        with self.assertRaisesRegex(ValueError, 'every frame'):
            self.verify()
        coverage['visually_reviewed_frames'] = [0, 1]
        self.records[0]['reviews']['encoded_video']['passed'] = False
        with self.assertRaisesRegex(ValueError, 'All three'):
            self.verify()

    def test_changed_edit_or_media_invalidates_review(self):
        edit = self.root / 'goal-40-edit.json'
        original = edit.read_bytes()
        edit.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'Edit changed'):
            self.verify()
        edit.write_bytes(original)
        (self.root / 'goal-40-masked-v1.mp4').write_bytes(b'rerendered')
        with self.assertRaisesRegex(ValueError, 'Export changed'):
            self.verify()

    def test_official_scorer_mismatch_is_rejected(self):
        self.audit['sources'][0]['pid'] += 1
        with self.assertRaisesRegex(ValueError, 'Scorer identity'):
            self.verify()

    def test_encoded_timing_must_match(self):
        with patch.object(batch, 'inspect_media', side_effect=['0.08', '0.12']):
            with self.assertRaisesRegex(ValueError, 'different timing'):
                self.verify()


class SourceQueueTests(unittest.TestCase):
    def test_export_cap_preserves_the_full_tracking_window(self):
        edit={'duration':2,'export_frames':45}
        self.assertEqual(pipeline.frame_count(edit),45)
        self.assertEqual(pipeline.frame_count(edit,full_window=True),48)
        for cap in [0,49,True,1.5]:
            with self.assertRaises(ValueError):pipeline.frame_count(dict(edit,export_frames=cap))

    def test_only_new_completed_regular_season_scorers_with_official_sources(self):
        goal = {'playerId': 42, 'highlightClip': 99, 'highlightClipSharingUrl': 'https://nhl.com/video/official-99',
                'firstName': {'default': 'Test'}, 'lastName': {'default': 'Scorer'},
                'period': 1, 'timeInPeriod': '03:00', 'teamAbbrev': 'SEA'}
        game = {'id': 1, 'gameType': 2, 'gameState': 'OFF', 'gameDate': '2025-01-01', 'goals': [goal]}
        document = {'games': [game]}
        self.assertEqual(list(discover.goal_sources(document, {42}, {42})), [])
        self.assertEqual(list(discover.goal_sources(document, {7}, set())), [])
        self.assertEqual(list(discover.goal_sources(document, {42}, set()))[0][0], 42)
        for mutation in [{'gameType': 3}, {'gameState': 'LIVE'}]:
            altered = copy.deepcopy(document)
            altered['games'][0].update(mutation)
            self.assertEqual(list(discover.goal_sources(altered, {42}, set())), [])
        goal['highlightClipSharingUrl'] = 'https://example.com/clip'
        self.assertEqual(list(discover.goal_sources(document, {42}, set())), [])

    def test_registry_has_six_batches_and_240_distinct_new_players(self):
        progress = TOOLS / 'progress'
        registry = json.loads((progress / 'expansion-batches.json').read_text())
        queue = json.loads((progress / 'expansion-candidates.json').read_text())
        by_id = {row['id']: row for row in queue['candidates']}
        ids = [ident for row in registry['batches'] for ident in row['ids']]
        self.assertEqual(len(registry['batches']), 6)
        self.assertTrue(all(len(row['ids']) == 40 for row in registry['batches']))
        self.assertEqual(len(ids), 240)
        self.assertEqual(len(set(ids)), 240)
        self.assertEqual(len({by_id[ident]['pid'] for ident in ids}), 240)
        baseline = json.loads((TOOLS.parents[1] / 'static/who-scored/clips.json').read_text())
        new_ids = set(ids) - {clip['id'] for clip in baseline}
        self.assertFalse({by_id[ident]['pid'] for ident in new_ids} & {clip['pid'] for clip in baseline})


if __name__ == '__main__':
    unittest.main()
