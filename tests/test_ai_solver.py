import unittest

from yacht_engine import CATS, solve_best_move


class AiSolverRecommendationTests(unittest.TestCase):
    def test_focused_mode_guards_against_large_evaluation_loss(self):
        scorecard = [6, 12, 9, 12, None, None, None, None, None, None, 30, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [6, 6, 6, 4, 3],
            1,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["keep_indices"], [0, 1, 2])
        self.assertIn("4 of a Kind", result["message"])
        self.assertIn("집중 공략 보정", [row.get("name") for row in result["breakdown"][:4]])
        self.assertFalse(
            any("EV" in str(row.get("val_str", "")) for row in result["breakdown"])
        )

    def test_score_stage_keeps_completed_yacht_over_upper_bonus_push(self):
        scorecard = [None, 6, None, 16, None, 18, 16, None, 28, 15, 30, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [5, 5, 5, 5, 5],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["primary_target"], "Yacht")
        self.assertEqual(result["message"], "Yacht")
        self.assertIn("Yacht 50점", result["summary"])

    def test_score_stage_allows_low_positive_score_sacrifice(self):
        scorecard = [1, 6, None, 12, 15, 24, 23, 27, None, 15, None, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [2, 3, 4, 4, 6],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["primary_target"], "Yacht")
        self.assertEqual(result["message"], "Yacht")
        self.assertIn("0점", result["summary"])

    def test_score_stage_sacrifice_preserves_upper_bonus_survival(self):
        scorecard = [2, 6, None, 16, 15, 18, 22, None, 24, 15, None, 0]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [6, 6, 5, 5, 6],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["breakdown"][0]["name"], "4 of a Kind")
        self.assertNotEqual(result["breakdown"][0]["name"], "Threes")

    def test_score_stage_dumps_ones_instead_of_low_sixes_early(self):
        scorecard = [None, None, None, None, None, None, 24, None, None, None, None, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [1, 4, 5, 1, 6],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["primary_target"], "Ones")
        self.assertEqual(result["breakdown"][0]["name"], "Ones")

    def test_score_stage_dumps_ones_instead_of_two_sixes(self):
        scorecard = [None, None, None, 16, 15, None, 21, None, None, None, None, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [6, 5, 3, 6, 1],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["primary_target"], "Ones")
        self.assertEqual(result["breakdown"][0]["name"], "Ones")

    def test_score_stage_sacrifices_yacht_instead_of_low_fives(self):
        scorecard = [None, None, 12, 12, None, 18, 20, 10, None, 15, None, None]
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            [1, 5, 5, 6, 3],
            0,
            open_categories,
            "focused",
            scorecard,
        )

        self.assertEqual(result["primary_target"], "Yacht")
        self.assertEqual(result["breakdown"][0]["name"], "Yacht")


if __name__ == "__main__":
    unittest.main()
