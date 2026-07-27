import logging
import time
from copy import deepcopy

from flask import Blueprint, jsonify, request

import yacht_engine
from app_state import ai_metrics, get_services
from config import (
    AI_POLICY_MIN_CONFIDENCE,
    AI_SLOW_LOG_MS,
    WIN_PROBABILITY_DEFAULT_SAMPLES,
)
from utils.ai_utils import record_ai_slow_sample
from utils.validation import (
    normalize_dice,
    normalize_rolls_left,
    normalize_scorecard,
    normalize_strategy_mode,
    safe_int,
)
from yacht_ai.reporting.decision import build_decision_report
from yacht_app.infra.observability import log_json
from yacht_app.services.win_probability import request_win_probability
from yacht_core.constants import CATS
from yacht_core.scoring import calc_score

ai_bp = Blueprint("ai", __name__)


_RECOMMEND_CACHE_MAX = 512


def _rate_limit_response(limiter):
    allowed, retry_after = limiter.allow(request.remote_addr or "unknown")
    if allowed:
        return None
    response = jsonify({"error": "요청이 많습니다. 잠시 후 다시 시도해 주세요."})
    response.headers["Retry-After"] = str(retry_after)
    return response, 429


def _optional_turn_state(data, prefix):
    dice_raw = data.get(f"{prefix}_dice")
    rolls_raw = data.get(f"{prefix}_rolls_left")
    if dice_raw is None and rolls_raw is None:
        return None, None, None
    dice = normalize_dice(dice_raw)
    rolls_left = normalize_rolls_left(rolls_raw, 0, 2)
    if dice is None or rolls_left is None:
        return None, None, f"{prefix}_dice와 {prefix}_rolls_left가 올바르지 않습니다"
    return dice, rolls_left, None


@ai_bp.route("/api/win-probability", methods=["POST"])
def win_probability():
    limited = _rate_limit_response(get_services().ai_requests.win_probability_limiter)
    if limited:
        return limited
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON 객체 본문이 필요합니다"}), 400

    my_scorecard = normalize_scorecard(data.get("my_scorecard"))
    opp_scorecard = normalize_scorecard(data.get("opp_scorecard"))
    if my_scorecard is None or opp_scorecard is None:
        return jsonify({"error": "양쪽 scorecard는 길이 12의 점수/None 배열이어야 합니다"}), 400

    my_dice, my_rolls_left, my_error = _optional_turn_state(data, "my")
    opp_dice, opp_rolls_left, opp_error = _optional_turn_state(data, "opp")
    if my_error or opp_error:
        return jsonify({"error": my_error or opp_error}), 400

    requested_samples = safe_int(data.get("samples"), WIN_PROBABILITY_DEFAULT_SAMPLES)
    samples = max(5, min(requested_samples, 100))
    result = request_win_probability({
        "my_scorecard": my_scorecard,
        "opp_scorecard": opp_scorecard,
        "my_dice": my_dice,
        "my_rolls_left": my_rolls_left,
        "opp_dice": opp_dice,
        "opp_rolls_left": opp_rolls_left,
        "samples": samples,
    })
    if result["status"] == "busy":
        response = jsonify(result)
        response.headers["Retry-After"] = str(result.get("retry_after_seconds", 1))
        return response, 429
    return jsonify(result), 202 if result["status"] == "pending" else 200


def _recommend_cache_key(dice, rolls_left, strategy_mode, scorecard):
    return (tuple(dice), rolls_left, strategy_mode, tuple(scorecard))


def _get_cached_recommendation(cache_key):
    runtime = get_services().ai_requests
    with runtime.lock:
        cached = runtime.recommendation_cache.get(cache_key)
        if cached is None:
            return None
        runtime.recommendation_cache.move_to_end(cache_key)
        return deepcopy(cached)


def _set_cached_recommendation(cache_key, result):
    runtime = get_services().ai_requests
    with runtime.lock:
        runtime.recommendation_cache[cache_key] = deepcopy(result)
        runtime.recommendation_cache.move_to_end(cache_key)
        if len(runtime.recommendation_cache) > _RECOMMEND_CACHE_MAX:
            runtime.recommendation_cache.popitem(last=False)


def _solver_options_for_strategy(strategy_mode):
    if strategy_mode == "optimal":
        return "focused", "value_optimal", "exact_value_optimal"
    if strategy_mode == "focused":
        # roll 단계는 focused 휴리스틱 유지, score 단계만 exact V(next_state)로 대체.
        # regret 0.7554 -> 0, 200게임 +9.04점(95% CI [+3.43, +14.65], p=0.0016) 확인 후 기본값 승격.
        # docs/ai-quality-metrics.md, docs/decision-regret-100-value-score-only.md
        return "focused", "value_score_only", None
    return strategy_mode, None, None


def _mark_score_now_recommendation(
    result, dice, scorecard, open_categories, solver_strategy_mode, score_value_mode,
):
    """Turn an all-keep result into the unambiguous action it represents.

    Keeping every die is not an instruction to spend another roll.  It means
    that recording the best open category now beats every reroll candidate.
    Keeping this normalization at the route boundary also covers a guarded
    learned-policy response.
    """
    if result.get("stage") != "roll":
        return result
    recommendations = result.get("dice_recommendations")
    if not (
        isinstance(recommendations, list)
        and len(recommendations) == 5
        and all(isinstance(item, dict) and item.get("action") == "keep" for item in recommendations)
    ):
        return result

    target = result.get("primary_target")
    # Cover and optimal roll policies use a generic roll target (for example,
    # "hand one or more" or "EV optimal").  Resolve the concrete scorecard
    # category before asking the player to record it.
    if CATS.get(target) is None:
        score_result = yacht_engine.solve_best_move(
            dice,
            0,
            open_categories,
            solver_strategy_mode,
            scorecard,
            score_value_mode=score_value_mode,
        )
        target = score_result.get("primary_target")
    category_idx = CATS.get(target)
    if category_idx is None:
        return result

    score = calc_score(dice, category_idx)
    result = dict(result)
    result["stage"] = "score"
    result["recommended_action"] = "score_now"
    result["record_now"] = {
        "category": target,
        "score": score,
        "reroll_gap": result.get("alternative_gap"),
        "comparison": "expected_final_score" if result.get("policy_source") == "exact_value_optimal" else "utility",
    }
    result["message"] = f"지금 {target} {score}점 기록 추천"

    reroll_gap = result.get("alternative_gap")
    if isinstance(reroll_gap, (int, float)):
        if reroll_gap > 0.01:
            label = "기대 최종점수" if result["record_now"]["comparison"] == "expected_final_score" else "평가"
            comparison = f"다시 굴리기보다 {label} +{reroll_gap:.2f}"
        else:
            comparison = "다시 굴리는 선택과 거의 동률"
        result["summary"] = f"지금 {target} {score}점 기록 추천 · {comparison}"
    return result


@ai_bp.route("/api/recommend", methods=["POST"])
def recommend():
    try:
        limited = _rate_limit_response(get_services().ai_requests.recommend_limiter)
        if limited:
            return limited
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
                if forced_policy_source:
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
            if forced_policy_source:
                result["policy_source"] = forced_policy_source

        result = _mark_score_now_recommendation(
            result, dice, scorecard, open_categories, solver_strategy_mode, score_value_mode,
        )

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

    except yacht_engine.ExactValueTableUnavailableError:
        ai_metrics.error_count += 1
        return jsonify({
            "error": "exact_value_unavailable",
            "message": "최적 계산 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
        }), 503
    except Exception as e:
        ai_metrics.error_count += 1
        return jsonify({"error": str(e), "message": "AI 추천 오류"}), 500
