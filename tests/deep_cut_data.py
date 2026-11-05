"""Independent membership checks against the frozen, NHL-backed source catalog."""
import importlib.util
import json
from pathlib import Path
import unittest
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sweater", ROOT / "build_sweater.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
DATA = builder.load_deep_cut_data()
SOURCE = json.loads((ROOT / "static/community-games/data.json").read_text())
BASE = json.loads((ROOT / "static/deep-cut/data.json").read_text())
UPDATED = builder.load_community_data()


class DeepCutDataTests(unittest.TestCase):
    def test_every_answer_set_matches_all_qualifying_source_records(self):
        for prompt in DATA["prompts"]:
            if prompt.get('contentVersion'): continue  # Independently verified in deep_cut_expansion.py.
            kind, _, value = prompt["rule"].partition("-")
            records = UPDATED if prompt.get("version") == 2 and kind in ("team", "goalie") else SOURCE
            def matches(p):
                if kind == "team": return p[8].get(value, 0) > 0
                if kind == "goalie": return p[2] == "G" and p[8].get(value, 0) > 0
                if kind == "country": return p[3] == value
                if kind == "award": return any(t.split()[0].lower() == value for t in SOURCE["awards"].get(str(p[0]), []))
                if kind == "goals": return SOURCE["season_goals"].get(str(p[0]), 0) >= int(value)
                if kind == "games": return p[4] >= int(value)
                if kind == "cup": return p[0] in SOURCE["cup_winners"]
                if kind == "hall": return p[5]
                if kind == "debut": return int(value) <= p[6] < int(value) + 10
                if kind == "both":
                    a, b = value.split("-")
                    return p[8].get(a, 0) > 0 and p[8].get(b, 0) > 0
                self.fail(prompt["rule"])
            with self.subTest(prompt=prompt["id"]):
                actual = {pid for pid, _ in prompt["answers"]}
                expected = {p[0] for p in records["players"] if matches(p)}
                if prompt.get("version") == 2 and kind in ("team", "goalie") and prompt["id"] not in DATA["current_prompts"].values():
                    self.assertTrue(actual <= expected)
                else:
                    self.assertEqual(actual, expected)

    def test_published_daily_assignments_are_stable(self):
        today = date(2026, 11, 4)
        days = builder.plan_deep_cut_days({}, DATA, today)
        self.assertEqual(len(days), builder.AHEAD + 1)
        self.assertEqual(len(set(v["id"] for v in days.values())), len(days))
        extended = builder.plan_deep_cut_days(days, DATA, today + timedelta(days=10))
        for day, ref in days.items(): self.assertEqual(extended[day], ref)

    def test_canonical_names_and_font_are_included(self):
        self.assertEqual(len(BASE["players"]), 8280)
        self.assertEqual(len(BASE["prompts"]), 119)
        builder.deep_cut_scoring().validate(BASE, DATA)
        self.assertTrue((ROOT / "static/deep-cut/pixel.ttf").read_bytes().startswith(b"\0\1\0\0"))
        self.assertIn("SIL OPEN FONT LICENSE", (ROOT / "static/deep-cut/FONT-LICENSE.txt").read_text())


if __name__ == "__main__": unittest.main()
