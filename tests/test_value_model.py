import unittest

from yacht_ai.self_play import play_self_play_game
from yacht_ai.value_model import VALUE_FEATURE_NAMES, encode_value_state, scorecard_totals


class ValueModelFeatureTests(unittest.TestCase):
    def test_scorecard_totals_include_upper_bonus(self):
        scorecard = [3, 6, 9, 12, 15, 18, 20, 0, 0, 15, 30, 50]

        totals = scorecard_totals(scorecard)

        self.assertEqual(totals["upper_score"], 63)
        self.assertEqual(totals["upper_bonus"], 35)
        self.assertEqual(totals["total_score"], 213)

    def test_value_feature_shape_is_stable(self):
        features = encode_value_state([None] * 12, "cover")

        self.assertEqual(len(features), len(VALUE_FEATURE_NAMES))
        self.assertEqual(features[0], 1.0)

    def test_self_play_one_turn_sample_targets_remaining_score(self):
        scorecard = [3, 6, 9, 12, 15, 18, 20, 0, 0, 15, 30, None]

        game = play_self_play_game(20260708, "focused", initial_scorecard=scorecard)

        self.assertEqual(len(game["samples"]), 1)
        sample = game["samples"][0]
        self.assertEqual(sample["target_final_score"], game["final_score"])
        self.assertEqual(
            sample["target_remaining_score"],
            game["final_score"] - sample["state"]["current_total"],
        )
        self.assertIsNotNone(game["final_scorecard"][-1])


if __name__ == "__main__":
    unittest.main()
