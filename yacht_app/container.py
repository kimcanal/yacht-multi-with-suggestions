"""Application-owned dependencies shared by Flask blueprints."""

from __future__ import annotations

import threading
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from config import (
    AI_METRIC_WINDOW,
    AI_RATE_LIMIT_WINDOW_SECONDS,
    AI_RECOMMEND_RATE_LIMIT,
    AI_SLOW_SAMPLE_WINDOW,
    AI_WIN_PROBABILITY_RATE_LIMIT,
    SSE_MAX_CONNECTIONS,
)
from yacht_app.infra.rate_limit import SlidingWindowRateLimiter
from yacht_app.stores import create_presence_store, create_room_store
from yacht_app.stores.results import create_result_repository
from yacht_app.stores.sessions import create_single_session_store


class AIMetrics:
    """Thread-safe mutable metrics for AI requests and model status."""

    def __init__(self):
        self.lock = threading.RLock()
        self.recent_latencies = deque(maxlen=AI_METRIC_WINDOW)
        self.recent_stages = deque(maxlen=AI_METRIC_WINDOW)
        self.recent_slow_samples = deque(maxlen=AI_SLOW_SAMPLE_WINDOW)
        self.request_count = 0
        self.error_count = 0
        self.max_latency_ms = 0.0
        self.policy_model = None
        self.policy_model_status = "disabled"


class AIRequestRuntime:
    """Per-application mutable state for public AI request handling."""

    def __init__(self):
        self.lock = threading.RLock()
        self.recommendation_cache = OrderedDict()
        self.recommend_limiter = SlidingWindowRateLimiter(
            AI_RECOMMEND_RATE_LIMIT, AI_RATE_LIMIT_WINDOW_SECONDS
        )
        self.win_probability_limiter = SlidingWindowRateLimiter(
            AI_WIN_PROBABILITY_RATE_LIMIT, AI_RATE_LIMIT_WINDOW_SECONDS
        )


@dataclass(slots=True)
class AppServices:
    rooms: Any
    presence: Any
    results: Any
    single_sessions: Any
    single_sessions_lock: Any
    ai_metrics: AIMetrics = field(default_factory=AIMetrics)
    ai_requests: AIRequestRuntime = field(default_factory=AIRequestRuntime)
    win_probability: Any = None
    sse_slots: Any = field(default_factory=lambda: threading.BoundedSemaphore(SSE_MAX_CONNECTIONS))
    system_status_cache: dict[str, Any] = field(default_factory=dict)
    system_status_lock: Any = field(default_factory=threading.RLock)

    @property
    def room_store(self):
        return self.rooms

    @property
    def presence_store(self):
        return self.presence


def create_services() -> AppServices:
    # The probability solver imports optional numerical dependencies.  Keep
    # plain room/lifecycle imports lightweight until an application container
    # is actually constructed.
    from yacht_app.services.win_probability import WinProbabilityRuntime

    single_sessions = create_single_session_store()
    return AppServices(
        rooms=create_room_store(),
        presence=create_presence_store(),
        results=create_result_repository(),
        single_sessions=single_sessions,
        single_sessions_lock=single_sessions.lock(),
        win_probability=WinProbabilityRuntime(),
    )
