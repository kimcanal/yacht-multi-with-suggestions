import os
import re

# 클라이언트 타임아웃 (초)
CLIENT_TIMEOUT = 45
PLAYER_ROOM_TIMEOUT = 35
OBSERVER_ROOM_TIMEOUT = 90
TURN_TIME_LIMIT = 30

# 닉네임 유효성 검사
USERNAME_RE = re.compile(r"^[A-Za-z0-9가-힣_]{2,12}$")

# 관리자
RESET_ADMIN_TOKEN = os.getenv("YACHT_ADMIN_TOKEN", "").strip()

# AI 메트릭
AI_METRIC_WINDOW = 200
AI_SLOW_SAMPLE_WINDOW = 6
AI_SLOW_LOG_MS = float(os.getenv("YACHT_AI_SLOW_LOG_MS", "700"))

# AI 정책 모델
AI_POLICY_MODEL_PATH = os.getenv("YACHT_AI_POLICY_MODEL", "").strip()
AI_POLICY_MIN_CONFIDENCE = float(os.getenv("YACHT_AI_POLICY_MIN_CONFIDENCE", "0.95"))
AI_WARMUP_ENABLED = os.getenv("YACHT_AI_WARMUP", "1") == "1"
