import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sweater', ROOT / 'build_sweater.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class FaceSwapDataTests(unittest.TestCase):
    def test_full_library_has_200_unique_complete_pairings(self):
        bank = builder.load_face_swap_puzzles()
        self.assertEqual(len(bank), 200)
        self.assertEqual(len({tuple(sorted(p['players'])) for p in bank}), 200)
        self.assertEqual(len({pid for p in bank for pid in p['players']}), 60)
        self.assertEqual(bank[0]['players'], [8478402, 8479318])
        self.assertEqual(bank[9]['players'], [8477493, 8475167])
        hashes = set()
        for puzzle in bank:
            path = ROOT / 'static/face-swap' / puzzle['image']
            with Image.open(path) as image:
                self.assertGreaterEqual(image.width, 500)
                self.assertGreaterEqual(image.height, 600)
                self.assertAlmostEqual(image.width / image.height, .8, delta=.005)
                image.verify()
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(hashes), 200)

    def test_source_players_exist_and_have_local_reveal_headshots(self):
        bank = builder.load_face_swap_puzzles()
        schedule = json.loads((ROOT / 'schedule.json').read_text())
        for pid in {pid for p in bank for pid in p['players']}:
            player = schedule['players'][str(pid)]
            for field in ['name', 'birth', 'team', 'pos', 'nation']:
                self.assertTrue(player.get(field), (pid, field))
            with Image.open(ROOT / 'static/face-swap/players' / f'{pid}.webp') as image:
                self.assertEqual(image.size, (336, 336))
                image.verify()

    def test_daily_picks_do_not_repeat_and_published_days_never_move(self):
        bank = builder.load_face_swap_puzzles()
        today = date(2026, 10, 19)
        days = builder.plan_community_days({}, bank, today, 'faceswap')
        self.assertEqual(len(days), builder.AHEAD + 1)
        self.assertEqual(len({v['id'] for v in days.values()}), len(days))
        future = builder.plan_community_days(days, list(reversed(bank)), today + timedelta(days=10), 'faceswap')
        for day, puzzle in days.items():
            self.assertEqual(future[day], puzzle)
        self.assertEqual(builder.plan_community_days(days, bank, today, 'faceswap'), days)
        removed = [p for p in bank if p['id'] != days[today.isoformat()]['id']]
        with self.assertRaisesRegex(ValueError, 'immutable'):
            builder.plan_community_days(days, removed, today, 'faceswap')

    def test_every_required_media_file_is_copied_to_the_built_site(self):
        bank = builder.load_face_swap_puzzles()
        with tempfile.TemporaryDirectory() as tmp:
            builder.copy_face_swap_media(Path(tmp), bank)
            for p in bank:
                self.assertEqual((Path(tmp) / 'face-swap' / p['image']).read_bytes(),
                                 (ROOT / 'static/face-swap' / p['image']).read_bytes())
            self.assertEqual(len(list((Path(tmp) / 'face-swap/players').glob('*.webp'))), 60)

    def test_missing_or_changed_photos_and_duplicate_pairs_cannot_ship(self):
        bank = builder.load_face_swap_puzzles()[:2]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'static/face-swap'
            (folder / 'players').mkdir(parents=True)
            for p in bank:
                shutil.copy2(ROOT / 'static/face-swap' / p['image'], folder / p['image'])
                for pid in p['players']:
                    shutil.copy2(ROOT / 'static/face-swap/players' / f'{pid}.webp', folder / 'players' / f'{pid}.webp')
            manifest = folder / 'puzzles.json'
            manifest.write_text(json.dumps({'version': 1, 'puzzles': bank}))
            with patch.object(builder, 'HERE', Path(tmp)):
                self.assertEqual(len(builder.load_face_swap_puzzles()), 2)
                headshot = folder / 'players' / f"{bank[0]['players'][0]}.webp"
                original = headshot.read_bytes()
                headshot.unlink()
                with self.assertRaisesRegex(ValueError, 'photo'):
                    builder.load_face_swap_puzzles()
                headshot.write_bytes(original + b'changed')
                with self.assertRaisesRegex(ValueError, 'photo'):
                    builder.load_face_swap_puzzles()
                headshot.write_bytes(original)
                bank[1] = {**bank[1], 'players': bank[0]['players']}
                manifest.write_text(json.dumps({'version': 1, 'puzzles': bank}))
                with self.assertRaisesRegex(ValueError, 'pairing'):
                    builder.load_face_swap_puzzles()


if __name__ == '__main__':
    unittest.main()
