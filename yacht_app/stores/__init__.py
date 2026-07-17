"""State-store implementations used by the application layer."""

from .presence import InMemoryPresenceStore, RedisPresenceStore, create_presence_store
from .results import JsonResultRepository, SQLiteResultRepository, create_result_repository
from .room import InMemoryRoomStore, RedisRoomStore, create_room_store
from .sessions import (
    InMemorySingleSessionStore,
    RedisSingleSessionStore,
    create_single_session_store,
)

__all__ = [
    "InMemoryPresenceStore",
    "RedisPresenceStore",
    "create_presence_store",
    "InMemoryRoomStore",
    "RedisRoomStore",
    "create_room_store",
    "JsonResultRepository",
    "SQLiteResultRepository",
    "create_result_repository",
    "InMemorySingleSessionStore",
    "RedisSingleSessionStore",
    "create_single_session_store",
]
