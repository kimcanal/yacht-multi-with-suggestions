import json
import os
import tempfile
import unittest

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.original_data_file = database.DATA_FILE
        database.DATA_FILE = os.path.join(self.tempdir.name, "game_data.json")
        self.addCleanup(self._restore_data_file)

    def _restore_data_file(self):
        database.DATA_FILE = self.original_data_file

    def test_save_data_uses_valid_normalized_json(self):
        database.save_data({
            "users": {
                "alpha1": {
                    "wins": "2",
                    "draws": True,
                    "losses": -5,
                    "total_score": "450",
                    "games_played": "2",
                }
            },
            "games": [
                {"player1": "alpha1", "score1": "220", "player2": "beta12", "score2": "180"},
                {"bad": "row"},
            ],
            "single_leaderboard": [
                {"username": "solo1", "score": "999"},
                {"username": "", "score": 10},
            ],
        })

        with open(database.DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.assertEqual(raw["users"]["alpha1"]["wins"], 2)
        self.assertEqual(raw["users"]["alpha1"]["draws"], 0)
        self.assertEqual(raw["users"]["alpha1"]["losses"], 0)
        self.assertEqual(raw["games"][0]["score1"], 220)
        self.assertEqual(len(raw["games"]), 1)
        self.assertEqual(raw["single_leaderboard"], [
            {
                "username": "solo1",
                "score": 999,
                "timestamp": raw["single_leaderboard"][0]["timestamp"],
            }
        ])

    def test_corrupt_file_loads_empty_data(self):
        with open(database.DATA_FILE, "w", encoding="utf-8") as f:
            f.write("{not-json")

        self.assertEqual(database.load_data(), database._default_data())

    def test_save_game_result_clamps_scores(self):
        database.save_game_result("alpha1", 1200, "beta12", -20)
        payload = database.load_data()

        game = payload["games"][0]
        self.assertEqual(game["score1"], 1000)
        self.assertEqual(game["score2"], 0)
        self.assertEqual(payload["users"]["alpha1"]["total_score"], 1000)
        self.assertEqual(payload["users"]["beta12"]["total_score"], 0)


if __name__ == "__main__":
    unittest.main()
