"""Roster policy, reviewed familiarity and immutable score-release regression cases."""
import importlib.util
import json
from pathlib import Path
from datetime import date, timedelta
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "build_sweater.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
BASE = json.loads((ROOT / "static/deep-cut/data.json").read_text())
DATA = b.load_deep_cut_data()
SOURCE = b.load_community_data()
ROSTER = {pid: {"team": team} for pid, team in DATA["roster_snapshot"].items()}
REVIEW = json.loads((ROOT / "static/deep-cut/familiarity.json").read_text())
RULES = b.deep_cut_scoring()


class ScoringTests(unittest.TestCase):
    def test_current_roster_answers_follow_ten_fifteen_usage_tiers(self):
        prompts = {p["id"]: p for p in DATA["prompts"]}
        checked = 0
        for original, identity in DATA["current_prompts"].items():
            prompt = prompts[identity]
            if not original.startswith(("team-", "goalie-")): continue
            team = original.split("-", 1)[1]
            answers = dict(prompt["answers"])
            expected = {int(pid) for pid, row in ROSTER.items() if row["team"] == team and int(pid) in answers}
            self.assertEqual(set(prompt["currentRoster"]), expected)
            for pid in expected: self.assertEqual(answers[pid], 15 if pid in prompt.get("lowToiRoster", []) else 10)
            if DATA.get("active_policy") == 3 and original.startswith('team-'): self.assertEqual(len(prompt['lowToiRoster']), 6)
            checked += len(expected)
        self.assertGreater(checked, 500)

    def test_famous_names_can_have_rare_connections_but_current_rule_takes_precedence(self):
        prompts = {p["id"]: p for p in DATA["prompts"]}
        for row in REVIEW["team_connections"]:
            key = "team-" + row["team"]
            actual = dict(prompts[DATA["current_prompts"][key]]["answers"])[row["id"]]
            self.assertEqual(actual, 10 if ROSTER.get(str(row["id"]), {}).get("team") == row["team"] else row["points"])
        changed = {key: dict(value) for key, value in ROSTER.items()}
        changed["8448208"] = {"team": "CGY"}
        fresh = RULES.publish(BASE, DATA, SOURCE, changed, date(2026, 11, 5), REVIEW, DATA.get('toi_snapshot', []))
        prompt = next(p for p in fresh["prompts"] if p["id"] == fresh["current_prompts"]["team-CGY"])
        self.assertEqual(dict(prompt["answers"])[8448208], 10)

    def test_a_roster_change_appends_an_edition_without_changing_old_answers(self):
        changed = {key: dict(value) for key, value in ROSTER.items()}
        source_players = {p[0]: p for p in SOURCE["players"]}
        pid, team = next((pid, row["team"]) for pid, row in ROSTER.items() if int(pid) in source_players and source_players[int(pid)][8].get(row["team"]))
        target = next(row["team"] for row in ROSTER.values() if not source_players[int(pid)][8].get(row["team"]))
        changed[pid] = {"team": target}
        fresh = RULES.publish(BASE, DATA, SOURCE, changed, date(2026, 11, 5), REVIEW, DATA.get('toi_snapshot', []))
        RULES.validate(DATA, fresh)
        self.assertNotEqual(DATA["current_prompts"]["team-"+team], fresh["current_prompts"]["team-"+team])
        new_club = next(p for p in fresh["prompts"] if p["id"] == fresh["current_prompts"]["team-"+target])
        self.assertNotIn(int(pid), dict(new_club["answers"]))

    def test_archives_and_today_stay_fixed_and_new_days_use_latest_editions(self):
        today = date(2026, 11, 4)
        old = {today.isoformat(): {"id": BASE["runs"][0]["id"]}, (today-timedelta(days=1)).isoformat(): {"id": BASE["runs"][1]["id"]}, (today+timedelta(days=1)).isoformat(): {"id": BASE["runs"][2]["id"]}}
        days = b.plan_deep_cut_days(old, DATA, today)
        for key in old:
            if key <= today.isoformat(): self.assertEqual(days[key], old[key])
        self.assertIn(days[(today+timedelta(days=1)).isoformat()]["id"], DATA["practice_runs"])

    def test_repeated_publication_is_stable_and_incomplete_rosters_are_rejected(self):
        again = RULES.publish(BASE, DATA, SOURCE, ROSTER, date.fromisoformat(DATA["roster_asof"]), REVIEW, DATA.get('toi_snapshot', []))
        self.assertEqual(again, DATA)
        with self.assertRaises(ValueError): RULES.publish(BASE, DATA, SOURCE, {}, date(2026,11,5), REVIEW)


if __name__ == "__main__": unittest.main()
