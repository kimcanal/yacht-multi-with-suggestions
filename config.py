import os
import re

# 클라이언트 타임아웃 (초)
CLIENT_TIMEOUT = 45
PLAYER_ROOM_TIMEOUT = 35
OBSERVER_ROOM_TIMEOUT = 90
TURN_TIME_LIMIT = 30
SSE_MAX_CONNECTIONS = max(1, int(os.getenv("YACHT_SSE_MAX_CONNECTIONS", "2")))

# 닉네임 유효성 검사
USERNAME_RE = re.compile(r"^[A-Za-z0-9가-힣_]{2,12}$")

# 관리자
RESET_ADMIN_TOKEN = os.getenv("YACHT_ADMIN_TOKEN", "").strip()

# AI 메트릭
AI_METRIC_WINDOW = 200
AI_SLOW_SAMPLE_WINDOW = 6
AI_SLOW_LOG_MS = float(os.getenv("YACHT_AI_SLOW_LOG_MS", "700"))

AI_WARMUP_ENABLED = os.getenv("YACHT_AI_WARMUP", "1") == "1"

# 멀티 판세 Monte Carlo는 요청 스레드를 막지 않고 백그라운드에서 계산한다.
WIN_PROBABILITY_WORKERS = max(1, int(os.getenv("YACHT_WIN_PROBABILITY_WORKERS", "1")))
WIN_PROBABILITY_DEFAULT_SAMPLES = max(5, int(os.getenv("YACHT_WIN_PROBABILITY_SAMPLES", "30")))
WIN_PROBABILITY_CACHE_MAX = max(8, int(os.getenv("YACHT_WIN_PROBABILITY_CACHE_MAX", "64")))
WIN_PROBABILITY_CACHE_TTL_SECONDS = max(30, int(os.getenv("YACHT_WIN_PROBABILITY_CACHE_TTL", "600")))
WIN_PROBABILITY_MAX_PENDING = max(1, int(os.getenv("YACHT_WIN_PROBABILITY_MAX_PENDING", "24")))

# Public, CPU-intensive endpoints are protected by a small in-process window.
# Redis-backed room state still works across workers; deployments that need a
# globally shared quota should enforce the same limit at their edge proxy.
AI_RECOMMEND_RATE_LIMIT = max(1, int(os.getenv("YACHT_AI_RECOMMEND_RATE_LIMIT", "40")))
AI_WIN_PROBABILITY_RATE_LIMIT = max(1, int(os.getenv("YACHT_AI_WIN_PROBABILITY_RATE_LIMIT", "24")))
AI_RATE_LIMIT_WINDOW_SECONDS = max(1, int(os.getenv("YACHT_AI_RATE_LIMIT_WINDOW_SECONDS", "60")))

# Sampling CPU metrics for every lobby request needlessly blocks a request.
SYSTEM_STATUS_CACHE_SECONDS = max(1.0, float(os.getenv("YACHT_SYSTEM_STATUS_CACHE_SECONDS", "2")))

# Set this only when the app sits behind a trusted reverse proxy.  It lets
# request.remote_addr remain useful for rate limiting without trusting a
# user-supplied X-Forwarded-For header on direct deployments.
TRUSTED_PROXY_HOPS = max(0, int(os.getenv("YACHT_TRUSTED_PROXY_HOPS", "0")))
