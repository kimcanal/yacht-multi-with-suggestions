from collections import deque
from config import AI_METRIC_WINDOW, AI_SLOW_SAMPLE_WINDOW

# 방 목록과 로비 클라이언트 — dict이므로 임포트한 참조로 in-place 수정 가능
rooms = {}
lobby_clients = {}


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
