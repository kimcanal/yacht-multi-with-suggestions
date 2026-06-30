from collections import deque
import threading

from config import AI_METRIC_WINDOW, AI_SLOW_SAMPLE_WINDOW
from utils.presence_store import create_presence_store
from utils.room_store import create_room_store

# 방 상태 저장소. 기본은 in-memory, 환경변수로 Redis backend를 선택할 수 있음.
room_store = create_room_store()
rooms = room_store
presence_store = create_presence_store()
lobby_clients = presence_store
single_sessions = {}
single_sessions_lock = threading.RLock()


class AIMetrics:
    """AI 요청 카운터, 레이턴시 기록, 정책 모델 상태를 한 곳에서 관리."""

    def __init__(self):
        self.recent_latencies = deque(maxlen=AI_METRIC_WINDOW)
        self.recent_stages = deque(maxlen=AI_METRIC_WINDOW)
        self.recent_slow_samples = deque(maxlen=AI_SLOW_SAMPLE_WINDOW)
        self.request_count = 0
        self.error_count = 0
        self.max_latency_ms = 0.0
        self.policy_model = None
        self.policy_model_status = "disabled"


ai_metrics = AIMetrics()
