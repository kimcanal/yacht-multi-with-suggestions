import time

import yacht_engine
from flask import Blueprint, jsonify, request

from app_state import ai_metrics
from config import AI_SLOW_LOG_MS, AI_POLICY_MIN_CONFIDENCE
from utils.ai_utils import record_ai_slow_sample
from utils.validation import safe_int

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/recommend", methods=["POST"])
def recommend():
    try:
        started = time.perf_counter()
        data = request.json or {}
        dice = data.get("dice", [])
        normalized_rolls_left = safe_int(data.get("rolls_left", 0), 0)
        scorecard = data.get("scorecard", [])
        strategy_mode = data.get("strategy_mode", "focused")
        open_categories = [i for i, score in enumerate(scorecard) if score is None]

        if not open_categories or normalized_rolls_left < 0:
            return jsonify({"message": "추천 불가", "keep_indices": [], "dice_recommendations": []})

        result = None
        if ai_metrics.policy_model and normalized_rolls_left > 0:
            result = ai_metrics.policy_model.recommend_roll(
                dice, normalized_rolls_left, strategy_mode, scorecard,
                min_confidence=AI_POLICY_MIN_CONFIDENCE,
            )

        if result is None:
            result = yacht_engine.solve_best_move(
                dice, normalized_rolls_left, open_categories, strategy_mode, scorecard
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        ai_metrics.request_count += 1
        ai_metrics.recent_latencies.append(elapsed_ms)
        ai_metrics.recent_stages.append(result.get("stage", "unknown"))
        ai_metrics.max_latency_ms = max(ai_metrics.max_latency_ms, elapsed_ms)

        cache_info = yacht_engine.get_solver_cache_info()
        if elapsed_ms >= AI_SLOW_LOG_MS:
            record_ai_slow_sample(
                elapsed_ms, result.get("stage"), strategy_mode,
                normalized_rolls_left, dice, open_categories, result,
            )
            print(
                f"[AI] slow recommend elapsed_ms={elapsed_ms:.2f} "
                f"stage={result.get('stage')} mode={strategy_mode} "
                f"rolls_left={normalized_rolls_left} dice={dice} "
                f"open_categories={open_categories} "
                f"cache_hits={cache_info.hits} cache_misses={cache_info.misses}"
            )

        response = jsonify(result)
        response.headers["X-AI-Elapsed-Ms"] = f"{elapsed_ms:.2f}"
        response.headers["X-AI-Cache-Hits"] = str(cache_info.hits)
        response.headers["X-AI-Cache-Misses"] = str(cache_info.misses)
        response.headers["X-AI-Policy-Source"] = result.get("policy_source", "exact")
        return response

    except Exception as e:
        ai_metrics.error_count += 1
        return jsonify({"error": str(e), "message": "AI 추천 오류"}), 500
