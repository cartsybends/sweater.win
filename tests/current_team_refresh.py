"""Persist landing-page corrections even when an archived player's team matches."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "refresh", Path(__file__).resolve().parents[1] / "refresh_current_teams.py"
)
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class CurrentPlayerRefreshTests(unittest.TestCase):
    player = {"id": 42, "name": "Fixture Player", "team": "TOR", "number": 88,
              "pos": "R", "headshot": "old.png"}

    def run_refresh(self, live):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            html, schedule, rosters = [folder / name for name in
                                       ["index.html", "schedule.json", "rosters.json"]]
            html.write_text("const PLAYERS = " + json.dumps([self.player]) +
                            ".sort((a, b) => a.id - b.id);")
            schedule.write_text(json.dumps({"players": {"42": self.player}}))
            rosters.write_text("{}")
            before = (html.read_bytes(), schedule.read_bytes())
            args = ["refresh", "--html", str(html), "--schedule", str(schedule),
                    "--rosters", str(rosters)]
            with patch.object(sys, "argv", args), patch.object(
                refresh, "current_for_archived_players", return_value={42: live}
            ) as fetch:
                refresh.main()
                fetch.assert_called_once_with({42})
            after = (html.read_bytes(), schedule.read_bytes())
            return (refresh.embedded_players_from_html(html)[3][0],
                    json.loads(schedule.read_text())["players"]["42"], before, after)

    def test_each_same_team_metadata_change_is_persisted_in_both_files(self):
        for field, value in [("number", 16), ("pos", "C"), ("headshot", "new.png")]:
            with self.subTest(field=field):
                html, archive, before, after = self.run_refresh({"team": "TOR", field: value})
                expected = {**self.player, field: value}
                self.assertEqual(html, expected)
                self.assertEqual(archive, expected)
                self.assertNotEqual(before, after)

    def test_multiple_changes_count_the_player_once_and_unchanged_is_zero(self):
        player = copy.deepcopy(self.player)
        live = {42: {"team": "VAN", "number": 16, "pos": "C", "headshot": "new.png"}}
        self.assertEqual(refresh.apply([player], live, "fixture"), 1)
        self.assertEqual(refresh.apply([player], live, "fixture"), 0)
        self.assertEqual(player, {**self.player, **live[42]})

    def test_missing_metadata_preserves_existing_values_and_files(self):
        html, archive, before, after = self.run_refresh(
            {"team": "TOR", "number": None, "pos": "", "headshot": None}
        )
        self.assertEqual(html, self.player)
        self.assertEqual(archive, self.player)
        self.assertEqual(before, after)

    def test_zero_number_is_a_valid_change(self):
        html, archive, _, _ = self.run_refresh({"team": "TOR", "number": 0})
        self.assertEqual(html["number"], 0)
        self.assertEqual(archive["number"], 0)


if __name__ == "__main__":
    unittest.main()
