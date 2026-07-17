import json
import os
import threading
from contextlib import contextmanager


class InMemoryRoomStore:
    backend_name = "memory"

    def __init__(self):
        self._rooms = {}
        self._global_lock = threading.RLock()
        self._locks = {}

    def __contains__(self, code):
        return code in self._rooms

    def __getitem__(self, code):
        return self._rooms[code]

    def __setitem__(self, code, room):
        self.save(code, room)

    def __len__(self):
        return len(self._rooms)

    def clear(self):
        with self._global_lock:
            self._rooms.clear()
            self._locks.clear()

    def get(self, code, default=None):
        with self._global_lock:
            return self._rooms.get(code, default)

    def items(self):
        with self._global_lock:
            return list(self._rooms.items())

    def keys(self):
        with self._global_lock:
            return list(self._rooms.keys())

    def pop(self, code, default=None):
        with self._global_lock:
            return self._rooms.pop(code, default)

    def save(self, code, room):
        with self._global_lock:
            self._rooms[code] = room

    def save_if_absent(self, code, room):
        with self._global_lock:
            if code in self._rooms:
                return False
            self._rooms[code] = room
            return True

    def delete(self, code):
        with self._global_lock:
            self._rooms.pop(code, None)

    @contextmanager
    def lock(self, code):
        with self._global_lock:
            lock = self._locks.setdefault(code, threading.RLock())
        with lock:
            yield


class RedisRoomStore:
    backend_name = "redis"

    def __init__(self, url, prefix="yacht:room:", ttl_seconds=21600):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis backend requires the 'redis' package") from exc

        if not url:
            raise RuntimeError("YACHT_REDIS_URL is required when YACHT_ROOM_BACKEND=redis")

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._lock_prefix = f"{prefix.rstrip(':')}-lock:"
        self._ttl_seconds = ttl_seconds
        self._client.ping()

    def _key(self, code):
        return f"{self._prefix}{code}"

    def _lock_key(self, code):
        return f"{self._lock_prefix}{code}"

    def _code_from_key(self, key):
        return key.removeprefix(self._prefix)

    def __contains__(self, code):
        return bool(self._client.exists(self._key(code)))

    def __getitem__(self, code):
        room = self.get(code)
        if room is None:
            raise KeyError(code)
        return room

    def __setitem__(self, code, room):
        self.save(code, room)

    def __len__(self):
        return sum(1 for _ in self._client.scan_iter(match=f"{self._prefix}*"))

    def clear(self):
        keys = list(self._client.scan_iter(match=f"{self._prefix}*"))
        if keys:
            self._client.delete(*keys)

    def get(self, code, default=None):
        raw = self._client.get(self._key(code))
        if raw is None:
            return default
        return json.loads(raw)

    def items(self):
        for key in self._client.scan_iter(match=f"{self._prefix}*"):
            raw = self._client.get(key)
            if raw is not None:
                yield self._code_from_key(key), json.loads(raw)

    def keys(self):
        for key in self._client.scan_iter(match=f"{self._prefix}*"):
            yield self._code_from_key(key)

    def pop(self, code, default=None):
        room = self.get(code, default)
        self.delete(code)
        return room

    def save(self, code, room):
        self._client.set(
            self._key(code),
            json.dumps(room, ensure_ascii=False, separators=(",", ":")),
            ex=self._ttl_seconds,
        )

    def save_if_absent(self, code, room):
        return bool(self._client.set(
            self._key(code),
            json.dumps(room, ensure_ascii=False, separators=(",", ":")),
            ex=self._ttl_seconds,
            nx=True,
        ))

    def delete(self, code):
        self._client.delete(self._key(code))

    @contextmanager
    def lock(self, code):
        lock = self._client.lock(
            self._lock_key(code),
            timeout=10,
            blocking_timeout=3,
        )
        with lock:
            yield


def create_room_store():
    backend = os.getenv("YACHT_ROOM_BACKEND", "memory").strip().lower()
    if backend in ("", "memory", "inmemory", "in-memory"):
        return InMemoryRoomStore()
    if backend == "redis":
        ttl_seconds = int(os.getenv("YACHT_ROOM_TTL_SECONDS", "21600"))
        return RedisRoomStore(
            os.getenv("YACHT_REDIS_URL", "").strip(),
            prefix=os.getenv("YACHT_REDIS_ROOM_PREFIX", "yacht:room:"),
            ttl_seconds=ttl_seconds,
        )
    raise RuntimeError(f"Unsupported room backend: {backend}")
