import unittest
import time

from utils.room_utils import score_total
from utils.win_probability_service import clear_win_probability_cache, request_win_probability
from yacht_ai.win_probability import estimate_win_probability


class WinProbabilityTests(unittest.TestCase):
    def setUp(self):
        clear_win_probability_cache()

    def test_result_shape_is_a_valid_probability_split(self):
        # both players have only "Ones" open so each rollout is a single turn -- fast.
        scorecard = [None, 6, 6, 12, 15, 18, 24, 22, 24, 15, 30, 50]
        result = estimate_win_probability(scorecard, scorecard, samples=3, seed=1)
        self.assertEqual(result["samples"], 3)
        total = result["win_rate"] + result["loss_rate"] + result["tie_rate"]
        self.assertAlmostEqual(total, 1.0, places=6)
        for key in ("win_rate", "loss_rate", "tie_rate"):
            self.assertGreaterEqual(result[key], 0.0)
            self.assertLessEqual(result[key], 1.0)

    def test_large_lead_wins_more_often_than_fresh_start(self):
        ahead_scorecard = [12, 16, 20, 24, 30, 0, 24, 22, 30, 15, 30, None]
        fresh_scorecard = [None, 6, 6, 12, 15, 18, 24, 22, 24, 15, 30, 50]

        result = estimate_win_probability(ahead_scorecard, fresh_scorecard, samples=6, seed=7)
        self.assertGreater(result["win_rate"], result["loss_rate"])

    def test_background_service_returns_exact_projection_and_cached_result(self):
        completed = [3, 6, 9, 12, 15, 18, 24, 22, 30, 15, 30, 50]
        payload = {
            "my_scorecard": completed,
            "opp_scorecard": completed,
            "my_dice": None,
            "my_rolls_left": None,
            "opp_dice": None,
            "opp_rolls_left": None,
            "samples": 5,
        }
        result = request_win_probability(payload)
        for _ in range(50):
            if result["status"] == "ready":
                break
            time.sleep(0.01)
            result = request_win_probability(payload)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["my_projected"], score_total(completed))
        self.assertEqual(result["opp_projected"], score_total(completed))
        self.assertEqual(result["effective_win_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
