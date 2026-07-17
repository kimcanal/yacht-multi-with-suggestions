from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from config import (
    WIN_PROBABILITY_CACHE_MAX,
    WIN_PROBABILITY_CACHE_TTL_SECONDS,
    WIN_PROBABILITY_WORKERS,
)
from yacht_ai.value.endgame import DEFAULT_ENDGAME_VALUE_TABLE_PATH, load_endgame_value_table
from yacht_ai.win_probability import estimate_win_probability
from yacht_app.services.room_lifecycle import score_total

_executor = ThreadPoolExecutor(
    max_workers=WIN_PROBABILITY_WORKERS,
    thread_name_prefix="yacht-win-probability",
)
_lock = threading.RLock()
_pending = {}
_completed = OrderedDict()


def _exact_projected_final(scorecard):
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


def _prune_completed(now):
    expired = [
        key for key, item in _completed.items()
        if now - item["created_at"] > WIN_PROBABILITY_CACHE_TTL_SECONDS
    ]
    for key in expired:
        _completed.pop(key, None)
    while len(_completed) > WIN_PROBABILITY_CACHE_MAX:
        _completed.popitem(last=False)


def request_win_probability(payload):
    request_key = _request_key(payload)
    seed = int(request_key[:8], 16)
    projections = {
        "my_projected": _exact_projected_final(payload["my_scorecard"]),
        "opp_projected": _exact_projected_final(payload["opp_scorecard"]),
        "projection_method": "full_game_exact_value",
    }
    now = time.time()

    with _lock:
        _prune_completed(now)
        cached = _completed.get(request_key)
        if cached:
            _completed.move_to_end(request_key)
            return {"status": "ready", "request_id": request_key[:16], **projections, **cached["result"]}

        future = _pending.get(request_key)
        if future and future.done():
            _pending.pop(request_key, None)
            try:
                result = future.result()
            except Exception as exc:
                return {
                    "status": "error",
                    "request_id": request_key[:16],
                    "error": str(exc),
                    **projections,
                }
            _completed[request_key] = {"created_at": now, "result": result}
            _prune_completed(now)
            return {"status": "ready", "request_id": request_key[:16], **projections, **result}

        if future is None:
            _pending[request_key] = _executor.submit(_run_estimate, payload, seed)

    return {
        "status": "pending",
        "request_id": request_key[:16],
        "retry_after_ms": 900,
        **projections,
    }


def clear_win_probability_cache():
    with _lock:
        _completed.clear()
        _pending.clear()
