"""Ranked single-session stores."""

from __future__ import annotations

import json
import os
import threading


class InMemorySingleSessionStore:
    backend_name = "memory"

    def __init__(self):
        self._sessions = {}
        self._lock = threading.RLock()

    def __setitem__(self, session_id, session):
        with self._lock:
            self._sessions[session_id] = session

    def __getitem__(self, session_id):
        with self._lock:
            return self._sessions[session_id]

    def get(self, session_id, default=None):
        with self._lock:
            return self._sessions.get(session_id, default)

    def items(self):
        with self._lock:
            return list(self._sessions.items())

    def pop(self, session_id, default=None):
        with self._lock:
            return self._sessions.pop(session_id, default)

    def clear(self):
        with self._lock:
            self._sessions.clear()

    def lock(self):
        return self._lock


class RedisSingleSessionStore:
    backend_name = "redis"

    def __init__(self, url, prefix="yacht:single:", ttl_seconds=14400):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis session backend requires the 'redis' package") from exc
        if not url:
            raise RuntimeError("YACHT_REDIS_URL is required when YACHT_SESSION_BACKEND=redis")
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._ttl_seconds = ttl_seconds
        self._client.ping()

    def _key(self, session_id):
        return f"{self._prefix}{session_id}"

    def __setitem__(self, session_id, session):
        self._client.set(
            self._key(session_id),
            json.dumps(session, ensure_ascii=False, separators=(",", ":")),
            ex=self._ttl_seconds,
        )

    def __getitem__(self, session_id):
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def get(self, session_id, default=None):
        raw = self._client.get(self._key(session_id))
        return json.loads(raw) if raw is not None else default

    def items(self):
        result = []
        for key in self._client.scan_iter(match=f"{self._prefix}*"):
            raw = self._client.get(key)
            if raw is not None:
                result.append((key.removeprefix(self._prefix), json.loads(raw)))
        return result

    def pop(self, session_id, default=None):
        value = self.get(session_id, default)
        self._client.delete(self._key(session_id))
        return value

    def clear(self):
        keys = list(self._client.scan_iter(match=f"{self._prefix}*"))
        if keys:
            self._client.delete(*keys)

    def lock(self):
        return self._client.lock(
            f"{self._prefix.rstrip(':')}:global-lock",
            timeout=15,
            blocking_timeout=5,
        )


def create_single_session_store():
    backend = os.getenv(
        "YACHT_SESSION_BACKEND",
        os.getenv("YACHT_ROOM_BACKEND", "memory"),
    ).strip().lower()
    if backend in ("", "memory", "inmemory", "in-memory"):
        return InMemorySingleSessionStore()
    if backend == "redis":
        return RedisSingleSessionStore(
            os.getenv("YACHT_REDIS_URL", "").strip(),
            prefix=os.getenv("YACHT_REDIS_SESSION_PREFIX", "yacht:single:"),
            ttl_seconds=int(os.getenv("YACHT_SESSION_TTL_SECONDS", "14400")),
        )
    raise RuntimeError(f"Unsupported session backend: {backend}")
