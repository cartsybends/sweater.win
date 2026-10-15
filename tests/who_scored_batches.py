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
import corrections


class BatchGateTests(unittest.TestCase):
    def test_tracking_crop_keeps_small_scorer_pixels_in_full_scene(self):
        from PIL import Image
        edit={'tracking_crop_size':384,'anchors':[
            {'frame':0,'box':[0,10,60,90],'points':[[10,30],[800,400]],'labels':[1,0]},
            {'frame':2,'box':[880,400,960,540],'points':[[940,500]]}]}
        crops=pipeline.tracking_crops(edit,3)
        self.assertEqual(crops,[(-162,-142,384),(283,68,384),(728,278,384)])
        for frame,(px,py) in [(0,(10,30)),(1,(475,260)),(2,(940,500))]:
            x,y,size=crops[frame];mask=Image.new('L',(size,size))
            mask.putpixel((px-x,py-y),255)
            restored=pipeline.restore_tracking_mask(mask,crops[frame])
            self.assertEqual(restored.size,(960,540))
            self.assertEqual(restored.getbbox(),(px,py,px+1,py+1))
        prompt=pipeline.cropped_prompt(edit['anchors'][0],crops[0])
        self.assertEqual(prompt['points'],[[172,172]])
        self.assertEqual(prompt['labels'],[1])
        self.assertEqual(prompt['box'],[162,152,222,232])
        # Padding outside the source must not shift the visible part inward.
        padded=Image.new('L',(384,384),255)
        self.assertEqual(pipeline.restore_tracking_mask(padded,crops[0]).getbbox(),(0,0,222,242))

    def test_tracking_crop_cannot_silently_drop_scorer_prompts(self):
        with self.assertRaisesRegex(ValueError,'Positive scorer'):
            pipeline.cropped_prompt({'points':[[500,400]],'labels':[1]},(0,0,384))
        with self.assertRaisesRegex(ValueError,'room around'):
            pipeline.tracking_crops({'tracking_crop_size':384,'anchors':[
                {'frame':0,'box':[0,0,383,100]}]},1)
        with self.assertRaisesRegex(ValueError,'positive scorer'):
            pipeline.cropped_prompt({'points':[[20,20]],'labels':[0]},(0,0,384))
        self.assertNotEqual(pipeline.tracking_signature({'id':'goal-83'}),
                            pipeline.tracking_signature({'id':'goal-83','tracking_crop_size':384}))

    def test_export_cap_cannot_remove_the_reviewed_scoring_finish(self):
        edit={'duration':3.0,'scoring_play_end_frame':60}
        self.assertEqual(pipeline.frame_count(edit),72)
        with self.assertRaisesRegex(ValueError,'scoring finish'):
            pipeline.frame_count({**edit,'export_frames':40})
        self.assertEqual(pipeline.frame_count({**edit,'export_frames':66}),66)

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


class PublishedCorrectionTests(unittest.TestCase):
    def test_published_metadata_and_assets_match_completed_correction_reviews(self):
        media = TOOLS.parents[1] / 'static/who-scored'
        folder = TOOLS / 'progress/corrections-01'
        clips = json.loads((media / 'clips.json').read_text())
        baseline_ids = {clip['id'] for clip in json.loads((folder / 'clips-before.json').read_text())}
        corrected_clips = [clip for clip in clips if clip['id'] in baseline_ids]
        proposed, records = corrections.verify_corrections(folder, media, corrected_clips, inspect=False)
        self.assertEqual(corrected_clips, proposed)
        sources = {row['id']: row for row in json.loads((media / 'sources.json').read_text())}
        for record in records:
            with self.subTest(clip=record['id']):
                source = sources[record['id']]
                self.assertEqual(source, {**record['source'], 'exported_sha256': record['asset_sha256'],
                                         'review_record': str((folder / 'review.json').relative_to(TOOLS.parents[1]))})
                edit = json.loads((folder / f"{record['id']}-edit.json").read_text())
                if 'identity_verification' in edit:
                    self.assertEqual(source['identity_verification'], edit['identity_verification'])
                self.assertEqual(source['identity_verification'], record['reviews']['official_identity']['note'])

    def test_published_expansions_match_complete_reviewed_batches(self):
        media = TOOLS.parents[1] / 'static/who-scored'
        progress = TOOLS / 'progress'
        clips = json.loads((media / 'clips.json').read_text())
        registry = json.loads((progress / 'expansion-batches.json').read_text())
        by_id = {clip['id']: clip for clip in clips}
        self.assertEqual(len(by_id), len(clips))
        baseline_ids = {clip['id'] for clip in json.loads(
            (progress / 'corrections-01/clips-before.json').read_text())}
        additions = set(by_id) - baseline_ids
        verified = set()
        for row in registry['batches']:
            active = set(row['ids']) & additions
            if not active:
                continue
            self.assertEqual(active, set(row['ids']), 'Playable expansions must contain the entire batch')
            folder = progress / f"batch-{row['batch']:02d}"
            records = json.loads((folder / 'review.json').read_text())['reviewed_clips']
            previous = [clip for clip in clips if clip['id'] not in active]
            batch.verify_batch(row, records,
                               json.loads((progress / 'expansion-candidates.json').read_text()),
                               previous, media,
                               json.loads((progress / f"batch-{row['batch']:02d}-source-audit.json").read_text()),
                               folder)
            for record in records:
                source = next(source for source in json.loads(
                    (progress / f"batch-{row['batch']:02d}-source-audit.json").read_text())['sources']
                              if source['id'] == record['id'])
                self.assertEqual(by_id[record['id']], {
                    'id': record['id'], 'pid': record['pid'], **record['assets'],
                    'motion': record['motion'], 'source': source['source']})
            verified.update(active)
        self.assertEqual(verified, additions)

    def test_coleman_metadata_describes_the_replacement_colorado_goal(self):
        media = TOOLS.parents[1] / 'static/who-scored'
        clip = next(row for row in json.loads((media / 'clips.json').read_text()) if row['id'] == 'goal-79')
        source = next(row for row in json.loads((media / 'sources.json').read_text()) if row['id'] == 'goal-79')
        # Cached official game 2024021052, event 834: Coleman wrist shot, both goalies present (1551).
        self.assertEqual((source['game_id'], source['official_event_id'], source['source_video_id']),
                         (2024021052, 834, '6370064078112'))
        self.assertNotIn('empty-net', clip['motion'].lower())
        self.assertIn('wrist shot', clip['motion'].lower())
        self.assertIn('red Calgary jersey', source['identity_verification'])
        self.assertIn('Colorado', source['identity_verification'])
        self.assertNotIn('Jets', source['identity_verification'])


class CorrectionGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.baseline = [{'id': 'goal-17', 'pid': 42, 'masked': 'goal-17-masked-v1.mp4',
                          'reveal': 'goal-17-original-v1.mp4', 'poster': 'goal-17-v1.jpg',
                          'motion': 'Wrist shot', 'source': 'https://nhl.com/video/17'}]
        issue = {'id': 'goal-17', 'pid': 42, 'previous_assets': {
            kind: self.baseline[0][kind] for kind in ['masked', 'reveal', 'poster']}}
        source = {'id': 'goal-17', 'pid': 42, 'player': 'Test Scorer', 'jersey': 18,
                  'source': 'https://nhl.com/video/17', 'source_sha256': 'a' * 64}
        edit = {'id': 'goal-17', 'pid': 42, 'player': 'Test Scorer', 'version': 'v2',
                'source_sha256': source['source_sha256'], 'duration': 3 / 24,
                'scoring_play_end_frame': 1}
        edit_path = self.folder / 'goal-17-edit.json'
        edit_path.write_text(json.dumps(edit))
        assets = {'masked': 'goal-17-masked-v2.mp4', 'reveal': 'goal-17-original-v2.mp4',
                  'poster': 'goal-17-v2.jpg'}
        for name in assets.values():
            (self.folder / name).write_bytes(name.encode())
        self.record = {'id': 'goal-17', 'pid': 42, 'frames': 3, 'source': source,
                       'motion': 'Wrist shot', 'assets': assets,
                       'edit_sha256': batch.digest(edit_path),
                       'asset_sha256': {kind: batch.digest(self.folder / name) for kind, name in assets.items()},
                       'reviews': {
                           'official_identity': {'passed': True, 'jersey': 18, 'note': 'Verified 18.'},
                           'silhouette_coverage': {'passed': True, 'visually_reviewed_frames': [0, 1, 2], 'note': 'Full coverage.'},
                           'scoring_highlight': {'passed': True, 'finish_frame': 1, 'note': 'Goal and aftermath.'},
                           'encoded_video': {'passed': True, 'all_frames_decoded': True, 'matching_pair': True,
                                             'visually_sampled_frames': [0, 1, 2]}}}
        (self.folder / 'clips-before.json').write_text(json.dumps(self.baseline))
        (self.folder / 'issues.json').write_text(json.dumps({'clips': [issue]}))

    def verify(self, records=None, current=None):
        (self.folder / 'review.json').write_text(json.dumps({'reviewed_clips': records if records is not None else [self.record]}))
        return corrections.verify_corrections(self.folder, self.folder,
                                               self.baseline if current is None else current, inspect=False)

    def test_complete_correction_preserves_ids_and_scorers(self):
        proposed, _ = self.verify()
        self.assertEqual([(c['id'], c['pid']) for c in proposed], [('goal-17', 42)])
        self.assertEqual(proposed[0]['masked'], 'goal-17-masked-v2.mp4')
        self.verify(current=proposed)  # Rechecking staged assets is supported.

    def test_missing_review_or_wrong_scorer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Every reported clip'):
            self.verify(records=[])
        self.record['pid'] = 99
        with self.assertRaisesRegex(ValueError, 'retain the reported scorer'):
            self.verify()

    def test_changed_media_or_unrelated_library_changes_are_rejected(self):
        (self.folder / self.record['assets']['masked']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'matching the review'):
            self.verify()
        (self.folder / self.record['assets']['masked']).write_bytes(self.record['assets']['masked'].encode())
        with self.assertRaisesRegex(ValueError, 'outside the reported corrections'):
            self.verify(current=self.baseline + [{'id': 'unreviewed', 'pid': 99}])

    def test_incomplete_coverage_or_scoring_finish_is_rejected(self):
        self.record['reviews']['silhouette_coverage']['visually_reviewed_frames'] = [0, 2]
        with self.assertRaisesRegex(ValueError, 'every frame'):
            self.verify()
        self.record['reviews']['silhouette_coverage']['visually_reviewed_frames'] = [0, 1, 2]
        self.record['reviews']['scoring_highlight']['finish_frame'] = 0
        with self.assertRaisesRegex(ValueError, 'complete scoring finish'):
            self.verify()
        edit_path = self.folder / 'goal-17-edit.json'
        edit = json.loads(edit_path.read_text())
        edit.pop('scoring_play_end_frame')
        edit_path.write_text(json.dumps(edit))
        self.record['edit_sha256'] = batch.digest(edit_path)
        self.record['reviews']['scoring_highlight']['finish_frame'] = None
        with self.assertRaisesRegex(ValueError, 'complete scoring finish'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
