import json
import os
import threading


class InMemoryPresenceStore:
    backend_name = "memory"

    def __init__(self):
        self._clients = {}
        self._lock = threading.RLock()

    def __setitem__(self, client_id, info):
        with self._lock:
            self._clients[client_id] = info

    def __delitem__(self, client_id):
        with self._lock:
            del self._clients[client_id]

    def __len__(self):
        with self._lock:
            return len(self._clients)

    def clear(self):
        with self._lock:
            self._clients.clear()

    def items(self):
        with self._lock:
            return list(self._clients.items())

    def pop(self, client_id, default=None):
        with self._lock:
            return self._clients.pop(client_id, default)


class RedisPresenceStore:
    backend_name = "redis"

    def __init__(self, url, prefix="yacht:presence:", ttl_seconds=45):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis presence backend requires the 'redis' package") from exc

        if not url:
            raise RuntimeError("YACHT_REDIS_URL is required when YACHT_PRESENCE_BACKEND=redis")

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._ttl_seconds = ttl_seconds
        self._client.ping()

    def _key(self, client_id):
        return f"{self._prefix}{client_id}"

    def _client_id_from_key(self, key):
        return key.removeprefix(self._prefix)

    def __setitem__(self, client_id, info):
        self._client.set(
            self._key(client_id),
            json.dumps(info, ensure_ascii=False, separators=(",", ":")),
            ex=self._ttl_seconds,
        )

    def __delitem__(self, client_id):
        deleted = self._client.delete(self._key(client_id))
        if not deleted:
            raise KeyError(client_id)

    def __len__(self):
        return sum(1 for _ in self._client.scan_iter(match=f"{self._prefix}*"))

    def clear(self):
        keys = list(self._client.scan_iter(match=f"{self._prefix}*"))
        if keys:
            self._client.delete(*keys)

    def items(self):
        for key in self._client.scan_iter(match=f"{self._prefix}*"):
            raw = self._client.get(key)
            if raw is not None:
                yield self._client_id_from_key(key), json.loads(raw)

    def pop(self, client_id, default=None):
        key = self._key(client_id)
        raw = self._client.get(key)
        self._client.delete(key)
        if raw is None:
            return default
        return json.loads(raw)


def create_presence_store():
    backend = os.getenv("YACHT_PRESENCE_BACKEND", os.getenv("YACHT_ROOM_BACKEND", "memory")).strip().lower()
    if backend in ("", "memory", "inmemory", "in-memory"):
        return InMemoryPresenceStore()
    if backend == "redis":
        ttl_seconds = int(os.getenv("YACHT_PRESENCE_TTL_SECONDS", "45"))
        return RedisPresenceStore(
            os.getenv("YACHT_REDIS_URL", "").strip(),
            prefix=os.getenv("YACHT_REDIS_PRESENCE_PREFIX", "yacht:presence:"),
            ttl_seconds=ttl_seconds,
        )
    raise RuntimeError(f"Unsupported presence backend: {backend}")
