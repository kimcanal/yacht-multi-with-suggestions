import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.build_value_table import (
    build_exact_endgame_batch_table,
    build_value_table_from_state,
    dense_values_from_cache,
    mask_from_open_arg,
)
from yacht_ai.advice import build_score_stage_advice
from yacht_ai.constants import CATS
from yacht_ai.endgame_value import (
    EndgameValueTable,
    load_endgame_value_table,
    state_key_from_scorecard,
)
from yacht_ai.learned_value import LinearScorecardValueModel
from yacht_ai.solver import ExactValueTableUnavailableError, solve_best_move
from yacht_ai.value_model import VALUE_FEATURE_NAMES


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

    def test_npz_value_table_lookup_matches_dense_state(self):
        mask = mask_from_open_arg("Yacht")
        batch_values = build_exact_endgame_batch_table(
            max_open_count=1,
            max_states=3000,
        )
        dense_values = dense_values_from_cache(batch_values)

        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = Path(tmpdir) / "value-table-open1.npz"
            np.savez_compressed(
                table_path,
                values=dense_values,
                max_open_count=np.asarray(1, dtype=np.int16),
            )
            table = load_endgame_value_table(str(table_path))

        self.assertAlmostEqual(
            table.lookup_state(mask, 40, False),
            batch_values[(mask, 40, False)],
            places=5,
        )

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

    def test_solver_value_optimal_bypasses_focused_hand_override(self):
        table_path = Path("artifacts/runtime/value/endgame-value-table-open12.npz")
        if not table_path.exists():
            self.skipTest("full value table artifact is not available")

        dice = [1, 1, 2, 2, 3]
        scorecard = [None] * 12
        open_categories = list(range(12))

        focused_value = solve_best_move(
            dice,
            2,
            open_categories,
            "focused",
            scorecard,
            score_value_mode="value",
            endgame_value_table_path=str(table_path),
        )
        optimal_value = solve_best_move(
            dice,
            2,
            open_categories,
            "focused",
            scorecard,
            score_value_mode="value_optimal",
            endgame_value_table_path=str(table_path),
        )

        self.assertEqual(focused_value["keep_indices"], [0, 1, 2, 3])
        self.assertEqual(optimal_value["keep_indices"], [2, 3])
        self.assertGreater(optimal_value["expected_value"], focused_value["expected_value"])

    def test_solver_value_optimal_explains_banked_and_remaining_scores(self):
        table_path = Path("artifacts/runtime/value/endgame-value-table-open12.npz")
        if not table_path.exists():
            self.skipTest("full value table artifact is not available")

        dice = [3, 3, 6, 1, 2]
        scorecard = [4] + [None] * 11
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]

        result = solve_best_move(
            dice,
            1,
            open_categories,
            "focused",
            scorecard,
            score_value_mode="value_optimal",
            endgame_value_table_path=str(table_path),
        )

        self.assertEqual(result["keep_indices"], [0, 1])
        self.assertEqual(result["banked_score"], 4)
        self.assertEqual(result["remaining_game_ev"], 180.68)
        self.assertEqual(result["expected_final_score"], 184.68)
        self.assertEqual(result["alternative_gap"], 1.31)
        self.assertEqual(
            result["expected_final_score"],
            round(result["banked_score"] + result["remaining_game_ev"], 2),
        )
        reason = result["breakdown"][0]["reason"]
        self.assertIn("현재 점수판에 기록된 4점", reason)
        self.assertIn("이번 턴의 재굴림과 기록 점수", reason)
        self.assertNotIn("즉시 기록 점수", reason)

    def test_solver_value_optimal_fails_when_exact_table_is_unavailable(self):
        with self.assertRaises(ExactValueTableUnavailableError):
            solve_best_move(
                [1, 2, 3, 4, 6],
                1,
                list(range(12)),
                "focused",
                [None] * 12,
                score_value_mode="value_optimal",
                endgame_value_table_path="missing-exact-value-table.npz",
            )

    def test_solver_value_optimal_fails_when_required_state_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = Path(tmpdir) / "incomplete-value-table.json"
            table_path.write_text(
                json.dumps({"batch_open_count": 0, "values": {}}),
                encoding="utf-8",
            )

            with self.assertRaises(ExactValueTableUnavailableError):
                solve_best_move(
                    [1, 2, 3, 4, 6],
                    0,
                    list(range(12)),
                    "focused",
                    [None] * 12,
                    score_value_mode="value_optimal",
                    endgame_value_table_path=str(table_path),
                )

    def test_solver_value_optimal_fast_score_path_matches_explained_result(self):
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

            explained = solve_best_move(
                dice,
                0,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
                score_value_mode="value_optimal",
                endgame_value_table_path=str(table_path),
            )
            fast = solve_best_move(
                dice,
                0,
                [CATS["Ones"], CATS["Choice"]],
                "focused",
                scorecard,
                score_value_mode="value_optimal",
                endgame_value_table_path=str(table_path),
                explain=False,
            )

        self.assertEqual(fast["primary_target"], explained["primary_target"])
        self.assertEqual(fast["expected_value"], explained["expected_value"])
        self.assertEqual(fast["expected_final_score"], explained["expected_final_score"])
        self.assertEqual(fast["remaining_game_ev"], explained["remaining_game_ev"])
        self.assertEqual(fast["policy_source"], "exact_value_optimal")
        self.assertEqual(fast["breakdown"], [])

    def test_solver_value_optimal_fast_roll_path_matches_explained_result(self):
        table_path = Path("artifacts/runtime/value/endgame-value-table-open12.npz")
        if not table_path.exists():
            self.skipTest("full value table artifact is not available")

        dice = [1, 1, 2, 2, 3]
        scorecard = [None] * 12
        open_categories = list(range(12))

        explained = solve_best_move(
            dice,
            2,
            open_categories,
            "focused",
            scorecard,
            score_value_mode="value_optimal",
            endgame_value_table_path=str(table_path),
        )
        fast = solve_best_move(
            dice,
            2,
            open_categories,
            "focused",
            scorecard,
            score_value_mode="value_optimal",
            endgame_value_table_path=str(table_path),
            explain=False,
        )

        self.assertEqual(fast["keep_indices"], explained["keep_indices"])
        self.assertEqual(fast["expected_value"], explained["expected_value"])
        self.assertEqual(fast["expected_final_score"], explained["expected_final_score"])
        self.assertEqual(fast["alternative_gap"], explained["alternative_gap"])
        self.assertEqual(fast["policy_source"], "exact_value_optimal")
        self.assertEqual(fast["breakdown"], [])

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
