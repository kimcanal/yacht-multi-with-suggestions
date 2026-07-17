import unittest

from yacht_ai.self_play import play_self_play_game, simulate_state_distribution
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
        self.assertIn("upper_bonus_live", VALUE_FEATURE_NAMES)
        self.assertIn("yacht_bonus_cash_slots", VALUE_FEATURE_NAMES)
        self.assertIn("zero_category_count", VALUE_FEATURE_NAMES)

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

    def test_state_distribution_reports_quantiles(self):
        scorecard = [3, 6, 9, 12, 15, 18, 20, 0, 0, 15, 30, None]

        report = simulate_state_distribution(scorecard, trials=3, seed=20260708)

        self.assertEqual(report["trials"], 3)
        self.assertEqual(report["remaining_score"]["count"], 3)
        self.assertIn("p10", report["remaining_score"])
        self.assertLessEqual(report["remaining_score"]["min"], report["remaining_score"]["max"])


if __name__ == "__main__":
    unittest.main()
