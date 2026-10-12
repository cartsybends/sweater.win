import importlib.util
import unittest
from datetime import date, timedelta
from pathlib import Path

spec=importlib.util.spec_from_file_location('sweater',Path(__file__).resolve().parents[1]/'build_sweater.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class GoalScheduleTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
