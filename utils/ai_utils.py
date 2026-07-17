import platform
import time

import yacht_engine
from app_state import ai_metrics
from config import AI_POLICY_MIN_CONFIDENCE, AI_POLICY_MODEL_PATH

try:
    from yacht_ai.policies.ml_policy import RollPolicyModel
except Exception:
    RollPolicyModel = None


def detect_cpu_model():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    processor = platform.processor().strip()
    if processor:
        return processor
    return platform.machine() or "Unknown CPU"


CPU_MODEL = detect_cpu_model()


def load_ai_policy_model():
    if not AI_POLICY_MODEL_PATH:
        return
    if RollPolicyModel is None:
        ai_metrics.policy_model_status = "import_failed"
        print("[AI] learned roll policy unavailable: missing numpy or import failure")
        return
    try:
        ai_metrics.policy_model = RollPolicyModel.load(AI_POLICY_MODEL_PATH)
        ai_metrics.policy_model_status = "loaded"
        print(f"[AI] learned roll policy loaded from {AI_POLICY_MODEL_PATH}")
    except Exception as exc:
        ai_metrics.policy_model_status = f"load_failed:{exc}"
        print(f"[AI] learned roll policy load failed: {exc}")


def percentile(values, ratio):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * ratio)))
    return ordered[index]


def ai_metrics_snapshot():
    recent = list(ai_metrics.recent_latencies)
    recent_stages = list(ai_metrics.recent_stages)
    cache_info = yacht_engine.get_solver_cache_info()
    total = cache_info.hits + cache_info.misses
    hit_rate = (cache_info.hits / total) if total else 0.0
    return {
        "ai_requests_total": ai_metrics.request_count,
        "ai_errors_total": ai_metrics.error_count,
        "ai_recent_samples": len(recent),
        "ai_recent_avg_ms": round(sum(recent) / len(recent), 2) if recent else 0.0,
        "ai_recent_p95_ms": round(percentile(recent, 0.95), 2) if recent else 0.0,
        "ai_recent_max_ms": round(max(recent), 2) if recent else 0.0,
        "ai_max_latency_ms": round(ai_metrics.max_latency_ms, 2),
        "ai_recent_roll_count": sum(1 for s in recent_stages if s == "roll"),
        "ai_recent_score_count": sum(1 for s in recent_stages if s == "score"),
        "ai_cache_hits": cache_info.hits,
        "ai_cache_misses": cache_info.misses,
        "ai_cache_hit_rate": round(hit_rate * 100, 1),
        "ai_recent_slow_samples": list(ai_metrics.recent_slow_samples),
        "ai_policy_model_status": ai_metrics.policy_model_status,
        "ai_policy_model_enabled": bool(ai_metrics.policy_model),
    }


def record_ai_slow_sample(elapsed_ms, stage, mode, rolls_left, dice, open_categories, result):
    ai_metrics.recent_slow_samples.appendleft({
        "elapsed_ms": round(elapsed_ms, 2),
        "stage": stage or "unknown",
        "mode": mode or "focused",
        "rolls_left": int(rolls_left) if isinstance(rolls_left, (int, float)) else rolls_left,
        "dice": list(dice)[:5] if isinstance(dice, list) else [],
        "open_slots": len(open_categories) if isinstance(open_categories, list) else 0,
        "target": result.get("primary_target"),
        "summary": result.get("summary"),
        "recorded_at": int(time.time()),
    })


def warm_ai_runtime():
    warm_cases = [
        ([1, 2, 3, 4, 6], 1, [None] * 12, "focused"),
        ([6, 6, 5, 1, 5], 2, [None] * 12, "focused"),
        ([6, 6, 5, 1, 5], 2, [None] * 12, "cover"),
        ([6, 6, 6, 1, 2], 2, [None] * 12, "focused"),
        ([6, 6, 6, 1, 2], 0, [3, 6, 9, 12, 15, None, None, None, None, None, None, None], "focused"),
    ]
    started = time.perf_counter()
    try:
        for dice, rolls_left, scorecard, mode in warm_cases:
            open_cats = [i for i, v in enumerate(scorecard) if v is None]
            yacht_engine.solve_best_move(dice, rolls_left, open_cats, mode, scorecard)
            if ai_metrics.policy_model and rolls_left > 0:
                ai_metrics.policy_model.recommend_roll(
                    dice, rolls_left, mode, scorecard,
                    min_confidence=AI_POLICY_MIN_CONFIDENCE,
                )
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"[AI] runtime warm-up complete in {elapsed_ms:.1f}ms")
    except Exception as exc:
        print(f"[AI] runtime warm-up failed: {exc}")
