import logging
import time
from collections import OrderedDict
from copy import deepcopy

import yacht_engine
from flask import Blueprint, jsonify, request

from app_state import ai_metrics
from config import AI_SLOW_LOG_MS, AI_POLICY_MIN_CONFIDENCE
from utils.ai_utils import record_ai_slow_sample
from utils.observability import log_json
from utils.validation import (
    normalize_dice,
    normalize_rolls_left,
    normalize_scorecard,
    normalize_strategy_mode,
)
from yacht_ai.report import build_decision_report

ai_bp = Blueprint("ai", __name__)


_RECOMMEND_CACHE_MAX = 512
_RECOMMEND_RESULT_CACHE = OrderedDict()


def _recommend_cache_key(dice, rolls_left, strategy_mode, scorecard):
    return (tuple(dice), rolls_left, strategy_mode, tuple(scorecard))


def _get_cached_recommendation(cache_key):
    cached = _RECOMMEND_RESULT_CACHE.get(cache_key)
    if cached is None:
        return None
    _RECOMMEND_RESULT_CACHE.move_to_end(cache_key)
    return deepcopy(cached)


def _set_cached_recommendation(cache_key, result):
    _RECOMMEND_RESULT_CACHE[cache_key] = deepcopy(result)
    _RECOMMEND_RESULT_CACHE.move_to_end(cache_key)
    if len(_RECOMMEND_RESULT_CACHE) > _RECOMMEND_CACHE_MAX:
        _RECOMMEND_RESULT_CACHE.popitem(last=False)


def _solver_options_for_strategy(strategy_mode):
    if strategy_mode == "optimal":
        return "focused", "value_optimal", "exact_value_optimal"
    return strategy_mode, None, None


@ai_bp.route("/api/recommend", methods=["POST"])
def recommend():
    try:
        started = time.perf_counter()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "JSON 객체 본문이 필요합니다"}), 400

        dice = normalize_dice(data.get("dice", []))
        normalized_rolls_left = normalize_rolls_left(data.get("rolls_left", 0), 0, 2)
        scorecard = normalize_scorecard(data.get("scorecard", []))
        strategy_mode = normalize_strategy_mode(data.get("strategy_mode", "focused"))

        if dice is None:
            return jsonify({"error": "dice는 길이 5의 1~6 정수 배열이어야 합니다"}), 400
        if scorecard is None:
            return jsonify({"error": "scorecard는 길이 12의 점수/None 배열이어야 합니다"}), 400
        if strategy_mode is None:
            return jsonify({"error": "strategy_mode는 focused, cover, optimal만 허용됩니다"}), 400
        if normalized_rolls_left is None or normalized_rolls_left < 0 or normalized_rolls_left > 2:
            return jsonify({"error": "rolls_left는 0~2 정수여야 합니다"}), 400

        solver_strategy_mode, score_value_mode, forced_policy_source = _solver_options_for_strategy(strategy_mode)

        open_categories = [i for i, score in enumerate(scorecard) if score is None]
        if not open_categories:
            result = {
                "message": "추천 불가",
                "keep_indices": [],
                "dice_recommendations": [],
                "stage": "done",
                "strategy_mode": strategy_mode,
                "breakdown": [],
                "primary_target": None,
                "summary": "남은 열린 칸이 없어 추천할 수 없습니다.",
                "policy_source": "exact",
            }
            if score_value_mode:
                result["score_value_mode"] = score_value_mode
                result["policy_source"] = forced_policy_source
            result["decision_report"] = build_decision_report(
                result, dice, normalized_rolls_left, strategy_mode, scorecard, open_categories
            )
            return jsonify(result)

        cache_key = _recommend_cache_key(dice, normalized_rolls_left, strategy_mode, scorecard)
        result = _get_cached_recommendation(cache_key)
        request_cache_hit = result is not None

        if result is None and not score_value_mode and ai_metrics.policy_model and normalized_rolls_left > 0:
            result = ai_metrics.policy_model.recommend_roll(
                dice, normalized_rolls_left, strategy_mode, scorecard,
                min_confidence=AI_POLICY_MIN_CONFIDENCE,
            )

        if result is None:
            result = yacht_engine.solve_best_move(
                dice,
                normalized_rolls_left,
                open_categories,
                solver_strategy_mode,
                scorecard,
                score_value_mode=score_value_mode,
            )
            result.setdefault("policy_source", "exact")

        if score_value_mode:
            result["strategy_mode"] = strategy_mode
            result["score_value_mode"] = score_value_mode
            result["policy_source"] = forced_policy_source

        result["decision_report"] = build_decision_report(
            result, dice, normalized_rolls_left, strategy_mode, scorecard, open_categories
        )

        if not request_cache_hit:
            _set_cached_recommendation(cache_key, result)

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
            log_json(
                logging.WARNING,
                "ai_slow_recommend",
                elapsed_ms=round(elapsed_ms, 2),
                stage=result.get("stage", "unknown"),
                mode=strategy_mode,
                rolls_left=normalized_rolls_left,
                dice=dice,
                open_categories=open_categories,
                cache_hits=cache_info.hits,
                cache_misses=cache_info.misses,
                policy_source=result.get("policy_source", "exact"),
            )

        response = jsonify(result)
        response.headers["X-AI-Elapsed-Ms"] = f"{elapsed_ms:.2f}"
        response.headers["X-AI-Cache-Hits"] = str(cache_info.hits)
        response.headers["X-AI-Cache-Misses"] = str(cache_info.misses)
        response.headers["X-AI-Policy-Source"] = result.get("policy_source", "exact")
        response.headers["X-AI-Request-Cache"] = "hit" if request_cache_hit else "miss"
        return response

    except Exception as e:
        ai_metrics.error_count += 1
        return jsonify({"error": str(e), "message": "AI 추천 오류"}), 500
