import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('sweater',Path(__file__).resolve().parents[1]/'build_sweater.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class GoalScheduleTests(unittest.TestCase):
    def test_every_clip_has_its_original_game_result(self):
        clips=builder.load_goal_clips()
        self.assertTrue(clips)
        sources={s['id']:s for s in json.loads((builder.HERE/'static/who-scored/sources.json').read_text())}
        for clip in clips:
            self.assertEqual(clip['game']['id'],sources[clip['id']]['game_id'])
            self.assertEqual(clip['game']['date'],sources[clip['id']]['date'])
        old_game=next(c['game'] for c in clips if c['id']=='goal-02')
        self.assertEqual(old_game['date'],'2019-09-18')
        self.assertEqual((old_game['away']['abbrev'],old_game['home']['abbrev']),('TOR','OTT'))
        overtime=next(c['game'] for c in clips if c['id']=='goal-10')
        self.assertEqual(overtime['finish'],'OT')
        self.assertEqual((overtime['away']['score'],overtime['home']['score']),(4,3))

    def test_missing_or_invalid_game_results_cannot_be_published(self):
        clip=builder.load_goal_clips()[0]
        game=clip.pop('game');gid=str(game['id'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'static/who-scored';root.mkdir(parents=True)
            (root/'clips.json').write_text(json.dumps([clip]))
            (root/'sources.json').write_text(json.dumps([{'id':clip['id'],'game_id':game['id'],'date':game['date']}]))
            for kind in ['masked','reveal','poster']:(root/clip[kind]).touch()
            with patch.object(builder,'HERE',Path(tmp)):
                (root/'games.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'game result'):builder.load_goal_clips()
                (root/'games.json').write_text(json.dumps({gid:{**game,'date':'2024-12-11'}}))
                with self.assertRaisesRegex(ValueError,'game result'):builder.load_goal_clips()
                for score in [-1,1,'2',True]:
                    invalid={**game,'home':{**game['home'],'score':score}}
                    (root/'games.json').write_text(json.dumps({gid:invalid}))
                    with self.subTest(score=score),self.assertRaisesRegex(ValueError,'final score'):builder.load_goal_clips()
                (root/'games.json').write_text(json.dumps({gid:game}))
                self.assertEqual(builder.load_goal_clips()[0]['game'],game)

    def test_footage_years_follow_active_clips(self):
        sources=[{'id':'old','clip_year':2019},{'id':'new','date':'2025-01-02'}, {'id':'unused','date':'2010-01-01'}]
        self.assertEqual(builder.goal_clip_year_range([{'id':'old'},{'id':'new'}],sources),'2019–2025')
        self.assertEqual(builder.goal_clip_year_range([{'id':'new'}],sources),'2025')
        with self.assertRaisesRegex(ValueError,'footage year'):
            builder.goal_clip_year_range([{'id':'missing'}],sources)

    def test_library_growth_and_stability(self):
        today=date(2026,10,12);old=list(range(1,10));expanded=list(range(1,40))
        days={(today+timedelta(days=i)).isoformat():old[(i+9)%9] for i in range(-1,builder.AHEAD+1)}
        saved={'whoscored_days':days,'whoscored_clip_ids':old}
        retained=builder.goal_days_for_library(saved,expanded,today)
        self.assertEqual(set(retained),{'2026-10-11','2026-10-12','2026-10-13'})
        for day,answer in retained.items():self.assertEqual(answer,days[day])
        planned=builder.plan_days(retained,{str(i):i for i in expanded},today,'sweater-goal',38)
        self.assertTrue(set(planned.values())-set(old))
        self.assertEqual(len(set(planned.values())),len(planned))
        self.assertEqual(saved['whoscored_days'],days)
        self.assertEqual(builder.goal_days_for_library({'whoscored_days':planned,'whoscored_clip_ids':expanded},expanded,today),planned)
    def test_signature_migration(self):
        today=date(2026,10,12);days={(today+timedelta(days=i)).isoformat():i%9+1 for i in range(31)}
        self.assertEqual(builder.goal_days_for_library({'whoscored_days':days},list(range(1,10)),today),days)
        self.assertEqual(len(builder.goal_days_for_library({'whoscored_days':days},list(range(1,40)),today)),2)
    def test_six_forty_player_releases_preserve_locked_days(self):
        today=date(2026,10,13);players=list(range(1,40))
        days={(today+timedelta(days=i)).isoformat():players[(i+1)%len(players)] for i in range(-1,builder.AHEAD+1)}
        locked={day:days[day] for day in ['2026-10-12','2026-10-13','2026-10-14']}
        for release in range(1,7):
            expanded=list(range(1,40+release*40))
            retained=builder.goal_days_for_library({'whoscored_days':days,'whoscored_clip_ids':players},expanded,today)
            self.assertEqual(retained,locked)
            days=builder.plan_days(retained,{str(i):i for i in expanded},today,'sweater-goal',len(expanded)-1)
            for day,answer in locked.items():self.assertEqual(days[day],answer)
            self.assertTrue(set(days.values())-set(players))
            players=expanded

if __name__=='__main__':unittest.main()
