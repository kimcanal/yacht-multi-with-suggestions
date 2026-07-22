import unittest

from scripts.report_category_sacrifice_value import Profile, analyze_profile, render_markdown
from yacht_ai.value.endgame import EndgameValueTable
from yacht_core.constants import CATS


class CategorySacrificeValueReportTests(unittest.TestCase):
    def test_analyze_profile_reports_exact_difference_for_each_open_category(self):
        profile = Profile(
            slug="sample",
            title="sample",
            description="sample",
            scorecard=(None, None) + (0,) * 10,
        )
        table = EndgameValueTable.from_payload({
            "batch_open_count": 2,
            "values": {
                "4092:0:0": 25.0,
                str(4092 | (1 << CATS["Ones"])) + ":0:0": 17.0,
                str(4092 | (1 << CATS["Twos"])) + ":0:0": 21.5,
            },
        })

        report = analyze_profile(profile, table)

        self.assertEqual(report["baseline_remaining_ev"], 25.0)
        self.assertEqual([row["category"] for row in report["rows"]], ["Ones", "Twos"])
        self.assertEqual(report["rows"][0]["zero_close_cost"], 8.0)
        self.assertEqual(report["rows"][1]["zero_close_cost"], 3.5)

    def test_markdown_explains_exact_zero_close_formula(self):
        markdown = render_markdown([{
            "title": "sample",
            "description": "sample state",
            "upper_total": 0,
            "yacht_bonus_available": False,
            "baseline_remaining_ev": 25.0,
            "rows": [{
                "category": "Ones",
                "remaining_ev_after_zero": 17.0,
                "zero_close_cost": 8.0,
            }],
        }], "table.npz")

        self.assertIn("V(현재 점수판)", markdown)
        self.assertIn("8.000점", markdown)
