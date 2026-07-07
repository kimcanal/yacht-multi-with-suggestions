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


if __name__ == "__main__":
    unittest.main()
