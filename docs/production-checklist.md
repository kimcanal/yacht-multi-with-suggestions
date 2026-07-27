# Production checklist

## Required state backends

For more than one Gunicorn worker, configure shared room/session state and a
transactional result repository. The application fails fast if this pairing is
incomplete.

```bash
export GUNICORN_WORKERS=2
export YACHT_ROOM_BACKEND=redis
export YACHT_PRESENCE_BACKEND=redis
export YACHT_SESSION_BACKEND=redis
export YACHT_REDIS_URL=redis://127.0.0.1:6379/0
export YACHT_RESULT_BACKEND=sqlite
export YACHT_SQLITE_PATH=/var/lib/yacht/game_data.sqlite3
# Set to the exact number of trusted proxy hops only when applicable.
export YACHT_TRUSTED_PROXY_HOPS=1
```

Keep Redis private to the application network and back up the SQLite volume.

## Capacity controls

- `YACHT_SSE_MAX_CONNECTIONS` caps blocking SSE streams. Clients over the cap
  automatically use the existing polling fallback.
- `YACHT_WIN_PROBABILITY_MAX_PENDING` bounds background Monte Carlo work.
- `YACHT_AI_RECOMMEND_RATE_LIMIT` and `YACHT_AI_WIN_PROBABILITY_RATE_LIMIT`
  set per-process, per-IP limits over `YACHT_AI_RATE_LIMIT_WINDOW_SECONDS`.
  Apply matching limits in the reverse proxy for a multi-worker deployment.

## Release smoke test

1. Run `ruff check .` and `pytest -q`.
2. With Redis enabled and two workers, create a room, join, roll, score,
   reconnect, observe, leave, and rematch.
3. Confirm an expired turn advances from a separate browser or via the room
   GET endpoint; the server, not the browser, must own the transition.
4. Verify `/health`, request IDs, slow-AI logs, and the Redis/SQLite backups.
