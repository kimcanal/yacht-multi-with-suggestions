"""Application-owned dependencies shared by Flask blueprints."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from config import AI_METRIC_WINDOW, AI_SLOW_SAMPLE_WINDOW
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


@dataclass(slots=True)
class AppServices:
    rooms: Any
    presence: Any
    results: Any
    single_sessions: Any
    single_sessions_lock: Any
    ai_metrics: AIMetrics = field(default_factory=AIMetrics)

    @property
    def room_store(self):
        return self.rooms

    @property
    def presence_store(self):
        return self.presence


def create_services() -> AppServices:
    single_sessions = create_single_session_store()
    return AppServices(
        rooms=create_room_store(),
        presence=create_presence_store(),
        results=create_result_repository(),
        single_sessions=single_sessions,
        single_sessions_lock=single_sessions.lock(),
    )
