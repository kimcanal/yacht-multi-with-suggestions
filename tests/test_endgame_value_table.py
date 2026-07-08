import json
import tempfile
import unittest
from pathlib import Path

from yacht_ai.advice import build_score_stage_advice
from yacht_ai.constants import CATS
from yacht_ai.endgame_value import EndgameValueTable, state_key_from_scorecard
from yacht_ai.learned_value import LinearScorecardValueModel
from yacht_ai.solver import solve_best_move
from yacht_ai.value_model import VALUE_FEATURE_NAMES
from scripts.build_value_table import (
    build_exact_endgame_batch_table,
    build_value_table_from_state,
    mask_from_open_arg,
)


class EndgameValueTableTests(unittest.TestCase):
    def test_batch_value_matches_recursive_single_state(self):
        mask = mask_from_open_arg("Yacht")

        _recursive_values, recursive_value = build_value_table_from_state(
            mask,
            start_upper_total=40,
            start_yacht_bonus=False,
            max_exact_open=1,
            max_states=3000,
        )
        batch_values = build_exact_endgame_batch_table(
            max_open_count=1,
            max_states=3000,
        )

        self.assertAlmostEqual(batch_values[(mask, 40, False)], recursive_value, places=6)

    def test_score_stage_value_mode_uses_next_state_table(self):
        dice = [6, 6, 6, 6, 6]
        scorecard = [None, 6, 9, 12, 15, 18, None, 20, 25, 15, 30, 50]
        score_ones = list(scorecard)
        score_ones[CATS["Ones"]] = 0
        score_choice = list(scorecard)
        score_choice[CATS["Choice"]] = 30
        table = EndgameValueTable.from_payload({
            "batch_open_count": 1,
            "values": {
                state_key_from_scorecard(score_ones): 160.0,
                state_key_from_scorecard(score_choice): 0.0,
            },
        })

        heuristic = build_score_stage_advice(
            dice,
            scorecard,
            [CATS["Ones"], CATS["Choice"]],
            "focused",
        )
        value_mode = build_score_stage_advice(
            dice,
            scorecard,
            [CATS["Ones"], CATS["Choice"]],
            "focused",
            score_value_mode="value",
            endgame_value_table=table,
        )

        self.assertEqual(heuristic["primary_target"], "Choice")
        self.assertEqual(value_mode["primary_target"], "Ones")
        self.assertEqual(value_mode["expected_value"], 160.0)
        self.assertTrue(any(row["name"] == "Endgame V" for row in value_mode["breakdown"]))

    def test_solver_value_mode_can_load_table_by_path(self):
        dice = [6, 6, 6, 6, 6]
        scorecard = [None, 6, 9, 12, 15, 18, None, 20, 25, 15, 30, 50]
        score_ones = list(scorecard)
        score_ones[CATS["Ones"]] = 0
        score_choice = list(scorecard)
        score_choice[CATS["Choice"]] = 30

        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = Path(tmpdir) / "value-table.json"
            table_path.write_text(
                json.dumps({
                    "batch_open_count": 1,
                    "values": {
                        state_key_from_scorecard(score_ones): 160.0,
                        state_key_from_scorecard(score_choice): 0.0,
                    },
                }),
                encoding="utf-8",
            )

            result = solve_best_move(
                dice,
                0,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
                score_value_mode="value",
                endgame_value_table_path=str(table_path),
            )

        self.assertEqual(result["primary_target"], "Ones")
        self.assertEqual(result["expected_value"], 160.0)

    def test_solver_value_score_only_keeps_roll_policy_heuristic(self):
        dice = [6, 6, 6, 6, 6]
        scorecard = [None, 6, 9, 12, 15, 18, None, 20, 25, 15, 30, 50]
        score_ones = list(scorecard)
        score_ones[CATS["Ones"]] = 0
        score_choice = list(scorecard)
        score_choice[CATS["Choice"]] = 30

        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = Path(tmpdir) / "value-table.json"
            table_path.write_text(
                json.dumps({
                    "batch_open_count": 1,
                    "values": {
                        state_key_from_scorecard(score_ones): 160.0,
                        state_key_from_scorecard(score_choice): 0.0,
                    },
                }),
                encoding="utf-8",
            )

            score_stage = solve_best_move(
                dice,
                0,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
                score_value_mode="value_score_only",
                endgame_value_table_path=str(table_path),
            )
            heuristic_roll = solve_best_move(
                dice,
                1,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
            )
            score_only_roll = solve_best_move(
                dice,
                1,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
                score_value_mode="value_score_only",
                endgame_value_table_path=str(table_path),
            )

        self.assertEqual(score_stage["primary_target"], "Ones")
        self.assertEqual(score_stage["expected_value"], 160.0)
        self.assertEqual(score_only_roll["keep_indices"], heuristic_roll["keep_indices"])
        self.assertEqual(score_only_roll["expected_value"], heuristic_roll["expected_value"])

    def test_hybrid_mode_uses_guarded_learned_value_fallback(self):
        dice = [1, 2, 3, 4, 6]
        scorecard = [None] * 12
        empty_table = EndgameValueTable.from_payload({"batch_open_count": 0, "values": {}})
        model = LinearScorecardValueModel.from_payload({
            "model_id": "test-linear-value",
            "target": "target_remaining_score",
            "feature_names": list(VALUE_FEATURE_NAMES),
            "validation_metrics": {"mae": 10.0},
            "bias": 42.0,
            "weights": [0.0] * len(VALUE_FEATURE_NAMES),
        })

        guarded = build_score_stage_advice(
            dice,
            scorecard,
            [CATS["Choice"], CATS["Large Straight"]],
            "focused",
            score_value_mode="hybrid",
            endgame_value_table=empty_table,
            learned_value_model=model,
            learned_value_max_mae=25.0,
            learned_value_min_turns=0,
        )
        blocked = build_score_stage_advice(
            dice,
            scorecard,
            [CATS["Choice"], CATS["Large Straight"]],
            "focused",
            score_value_mode="hybrid",
            endgame_value_table=empty_table,
            learned_value_model=model,
            learned_value_max_mae=5.0,
            learned_value_min_turns=0,
        )

        self.assertTrue(any(row["name"] == "Learned V" for row in guarded["breakdown"]))
        self.assertFalse(any(row["name"] == "Learned V" for row in blocked["breakdown"]))


if __name__ == "__main__":
    unittest.main()
