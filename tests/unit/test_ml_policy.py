import unittest

from yacht_ai.constants import CATS
from yacht_ai.decision_confidence import classify_alternative_gap, recommendation_strength
from yacht_ai.ml_policy import _made_hand_safety_action, _should_apply_safety_action


class RollPolicySafetyTests(unittest.TestCase):
    def test_action_margin_bands_capture_ties_and_clear_edges(self):
        self.assertEqual(classify_alternative_gap(0.1)["key"], "near_tie")
        self.assertEqual(classify_alternative_gap(0.7)["key"], "slight_edge")
        self.assertEqual(classify_alternative_gap(1.2)["key"], "clear_edge")
        self.assertEqual(classify_alternative_gap(-0.4)["key"], "strategy_tradeoff")
        self.assertEqual(recommendation_strength(0.1)["points"], 5)
        self.assertEqual(recommendation_strength(0.7)["points"], 7)
        self.assertEqual(recommendation_strength(1.2)["points"], 9)

    def test_safety_keeps_made_yacht(self):
        action = _made_hand_safety_action([5, 5, 5, 5, 5], 1, [None] * 12)

        self.assertEqual(action["keep_indices"], [0, 1, 2, 3, 4])
        self.assertEqual(action["safety_override"], "made_yacht")

    def test_safety_keeps_four_kind_core(self):
        action = _made_hand_safety_action([4, 4, 4, 4, 6], 1, [None] * 12)

        self.assertEqual(action["keep_indices"], [0, 1, 2, 3])
        self.assertEqual(action["safety_override"], "made_four_kind")

    def test_safety_ignores_closed_target(self):
        scorecard = [None] * 12
        scorecard[CATS["4 of a Kind"]] = 0

        action = _made_hand_safety_action([4, 4, 4, 4, 6], 1, scorecard)

        self.assertIsNone(action)

    def test_safety_applies_when_model_drops_core_dice(self):
        model_action = {"keep_counts": (0, 0, 0, 3, 0, 0)}
        safety_action = {"keep_counts": (0, 0, 0, 4, 0, 0)}

        self.assertTrue(_should_apply_safety_action(model_action, safety_action))


if __name__ == "__main__":
    unittest.main()
