from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from flask import current_app, has_app_context

from config import (
    WIN_PROBABILITY_CACHE_MAX,
    WIN_PROBABILITY_CACHE_TTL_SECONDS,
    WIN_PROBABILITY_MAX_PENDING,
    WIN_PROBABILITY_WORKERS,
)
from yacht_ai.solvers import solve_best_move
from yacht_ai.value.endgame import DEFAULT_ENDGAME_VALUE_TABLE_PATH, load_endgame_value_table
from yacht_ai.win_probability import estimate_win_probability
from yacht_core.simulation import total_score as score_total


class WinProbabilityRuntime:
    """App-owned queue and cache for asynchronous win-probability work."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=WIN_PROBABILITY_WORKERS,
            thread_name_prefix="yacht-win-probability",
        )
        self.lock = threading.RLock()
        self.pending = {}
        self.completed = OrderedDict()


# Standalone scripts and legacy callers can use the service without Flask. The
# web application itself always resolves a dedicated runtime from AppServices.
_default_runtime = WinProbabilityRuntime()
_executor = _default_runtime.executor
_lock = _default_runtime.lock
_pending = _default_runtime.pending
_completed = _default_runtime.completed


def _runtime() -> WinProbabilityRuntime:
    if has_app_context():
        services = current_app.extensions.get("yacht_services")
        if services is not None:
            return services.win_probability
    return _default_runtime


def _exact_projected_final(scorecard, dice=None, rolls_left=None):
    """Return the expected final score from the scorecard and active turn."""
    if dice is not None and rolls_left is not None and any(value is None for value in scorecard):
        result = solve_best_move(
            dice,
            rolls_left,
            [idx for idx, value in enumerate(scorecard) if value is None],
            "focused",
            scorecard,
            score_value_mode="value_optimal",
            endgame_value_table_path=DEFAULT_ENDGAME_VALUE_TABLE_PATH,
            explain=False,
        )
        return round(float(result["expected_final_score"]), 4)

    table = load_endgame_value_table(DEFAULT_ENDGAME_VALUE_TABLE_PATH)
    remaining_value, _ = table.lookup_scorecard(scorecard)
    return round(score_total(scorecard) + float(remaining_value or 0.0), 4)


def _request_key(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_estimate(payload, seed):
    result = estimate_win_probability(
        payload["my_scorecard"],
        payload["opp_scorecard"],
        my_dice=payload.get("my_dice"),
        my_rolls_left=payload.get("my_rolls_left"),
        opp_dice=payload.get("opp_dice"),
        opp_rolls_left=payload.get("opp_rolls_left"),
        samples=payload["samples"],
        seed=seed,
    )
    result["effective_win_rate"] = round(result["win_rate"] + result["tie_rate"] * 0.5, 6)
    result["confidence_95"] = round(result["win_rate_stderr"] * 1.96, 6)
    result["method"] = "monte_carlo_value_optimal"
    return result


def _prune_completed(runtime, now):
    expired = [
        key for key, item in runtime.completed.items()
        if now - item["created_at"] > WIN_PROBABILITY_CACHE_TTL_SECONDS
    ]
    for key in expired:
        runtime.completed.pop(key, None)
    while len(runtime.completed) > WIN_PROBABILITY_CACHE_MAX:
        runtime.completed.popitem(last=False)


def _collect_finished_requests(runtime, now):
    """Move completed work out of the pending map even when clients disappear."""
    for key, future in list(runtime.pending.items()):
        if not future.done():
            continue
        runtime.pending.pop(key, None)
        try:
            runtime.completed[key] = {"created_at": now, "result": future.result()}
        except Exception:
            # A later retry can submit a fresh estimate; failed tasks should
            # never occupy the bounded pending queue indefinitely.
            continue
    _prune_completed(runtime, now)


def request_win_probability(payload):
    request_key = _request_key(payload)
    seed = int(request_key[:8], 16)
    now = time.time()
    cached_result = None
    runtime = _runtime()

    with runtime.lock:
        _collect_finished_requests(runtime, now)
        cached = runtime.completed.get(request_key)
        if cached:
            runtime.completed.move_to_end(request_key)
            cached_result = cached["result"]
        elif request_key not in runtime.pending:
            if len(runtime.pending) >= WIN_PROBABILITY_MAX_PENDING:
                return {
                    "status": "busy",
                    "request_id": request_key[:16],
                    "retry_after_seconds": 2,
                    "error": "승률 계산 대기열이 가득 찼습니다",
                }
            runtime.pending[request_key] = runtime.executor.submit(_run_estimate, payload, seed)

    projections = {
        "my_projected": _exact_projected_final(
            payload["my_scorecard"], payload.get("my_dice"), payload.get("my_rolls_left")
        ),
        "opp_projected": _exact_projected_final(
            payload["opp_scorecard"], payload.get("opp_dice"), payload.get("opp_rolls_left")
        ),
        "projection_method": "full_game_exact_value_current_turn",
    }
    if cached_result is not None:
        return {"status": "ready", "request_id": request_key[:16], **projections, **cached_result}

    return {
        "status": "pending",
        "request_id": request_key[:16],
        "retry_after_ms": 900,
        **projections,
    }


def clear_win_probability_cache(runtime=None):
    runtime = runtime or _runtime()
    with runtime.lock:
        runtime.completed.clear()
        runtime.pending.clear()
