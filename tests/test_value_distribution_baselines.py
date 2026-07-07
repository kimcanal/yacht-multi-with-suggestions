import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval_value_distribution_baselines import build_report, load_model, load_predictions
from scripts.train_value_distribution_baselines import (
    DEFAULT_TARGETS,
    fit_ridge_multi,
    load_rows,
    predict,
    quantile_order_report,
)
from yacht_ai.value_model import VALUE_FEATURE_NAMES


class ValueDistributionBaselineTests(unittest.TestCase):
    def test_distribution_model_round_trips_through_eval_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            data_path = tmp_path / "distribution.jsonl"
            model_path = tmp_path / "model.json"

            rows = []
            for index, remaining_mean in enumerate([180.0, 160.0, 145.0, 130.0]):
                features = [0.0] * len(VALUE_FEATURE_NAMES)
                features[0] = 1.0
                if len(features) > 1:
                    features[1] = float(index)
                rows.append({
                    "source": f"case:{index}",
                    "turns_completed": index,
                    "current_total": index * 10,
                    "upper_score": index * 5,
                    "upper_gap": 63 - index * 5,
                    "yacht_bonus_active": False,
                    "open_category_names": ["Choice"],
                    "scorecard": [None] * 12,
                    "feature_values": features,
                    "target_remaining_mean": remaining_mean,
                    "target_remaining_stdev": 10.0 + index,
                    "target_remaining_p10": remaining_mean - 20.0,
                    "target_remaining_p50": remaining_mean,
                    "target_remaining_p90": remaining_mean + 20.0,
                    "target_upper_bonus_rate": index / 4.0,
                })
            data_path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            x, y = load_rows(data_path, DEFAULT_TARGETS)
            weights = fit_ridge_multi(x, y, ridge=1.0)
            predictions = predict(weights, x)
            order_report = quantile_order_report(DEFAULT_TARGETS, predictions)
            self.assertEqual(order_report["any_violation"], 0)

            model_path.write_text(
                json.dumps({
                    "model_id": "test-distribution-baseline",
                    "model_type": "scorecard_value_distribution_linear_v1",
                    "targets": list(DEFAULT_TARGETS),
                    "feature_names": list(VALUE_FEATURE_NAMES),
                    "bias": [float(value) for value in weights[0, :]],
                    "weights": [[float(value) for value in row] for row in weights[1:, :]],
                }),
                encoding="utf-8",
            )

            model = load_model(model_path)
            prediction_rows = load_predictions(data_path, model)
            report = build_report(data_path, model_path, model, prediction_rows, limit=2)

            self.assertEqual(report["examples"], 4)
            self.assertIn("target_remaining_p50", report["metrics"])
            self.assertEqual(report["quantile_order"]["violations"], 0)
            json.dumps(report)


if __name__ == "__main__":
    unittest.main()
