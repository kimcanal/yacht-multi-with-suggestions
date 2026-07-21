import unittest

from yacht_ai.policies.advice import build_recommendation_context_row
from yacht_ai.reporting.decision import build_decision_report


class DecisionReportTests(unittest.TestCase):
    def test_roll_report_explains_the_target_probability_from_the_selected_keep(self):
        report = build_decision_report(
            {
                "stage": "roll",
                "primary_target": "Full House",
                "keep_indices": [0, 1, 2],
                "target_probabilities": [
                    {"name": "Full House", "probability": 0.333333, "kind": "hand"},
                    {"name": "4 of a Kind", "probability": 0.185185, "kind": "hand"},
                ],
            },
            dice=[6, 6, 6, 2, 4],
            rolls_left=1,
            strategy_mode="focused",
            scorecard=[None] * 12,
            open_categories=[7, 8],
        )

        context = report["probability_context"]
        self.assertEqual(context["label"], "주목표")
        self.assertEqual(context["name"], "Full House")
        self.assertAlmostEqual(context["probability"], 0.333333)
        self.assertEqual(context["supporting"][0]["name"], "4 of a Kind")

    def test_tradeoffs_exclude_the_primary_recommendation(self):
        report = build_decision_report(
            {
                "breakdown": [
                    {
                        "name": "Sixes",
                        "val_str": "18점",
                        "reason": "가장 높은 기대값",
                        "type": "decision",
                    },
                    {
                        "name": "Choice",
                        "val_str": "20점",
                        "reason": "안정적인 대안",
                        "type": "risk",
                    },
                ],
                "message": "Sixes를 기록하세요.",
            },
            dice=[6, 6, 6, 1, 1],
            rolls_left=0,
            strategy_mode="focused",
            scorecard=[None] * 12,
            open_categories=["Sixes", "Choice"],
        )

        self.assertIn("Sixes · 18점", report["why"][0])
        self.assertEqual(report["tradeoffs"], ["Choice 20점: 안정적인 대안"])

    def test_recommendation_value_is_labeled_as_a_comparison_not_a_game_score(self):
        row = build_recommendation_context_row(
            "focused",
            42.52,
            0.7,
            {"name": "Full House", "type": "hand"},
            False,
            [0, 1, 2],
            None,
            None,
        )

        self.assertEqual(row["name"], "추천 정도")
        self.assertEqual(row["val_str"], "7/10")
        self.assertIn("차선책과의 차이", row["keep_str"])
        self.assertIn("실제 점수나 성공 확률이 아니라", row["reason"])


if __name__ == "__main__":
    unittest.main()
