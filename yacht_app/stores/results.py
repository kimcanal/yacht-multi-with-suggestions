"""Game-result repositories with JSON compatibility and SQLite concurrency safety."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import database as legacy

MAX_BOT_GAME_HISTORY = 500


class ResultRepository:
    backend_name = "abstract"

    @contextmanager
    def _data(self, *, write=False):
        raise NotImplementedError

    def get_or_create_user(self, username):
        with self._data(write=True) as data:
            return dict(legacy._ensure_user(data, username))

    def save_game_result(self, player1_name, player1_score, player2_name, player2_score, result_override=None):
        with self._data(write=True) as data:
            player1_score = legacy._coerce_int(player1_score)
            player2_score = legacy._coerce_int(player2_score)
            legacy._ensure_user(data, player1_name)
            if player2_name:
                legacy._ensure_user(data, player2_name)

            if result_override == "player1_win":
                data["users"][player1_name]["wins"] += 1
                if player2_name:
                    data["users"][player2_name]["losses"] += 1
                winner_name = player1_name
            elif result_override == "player2_win":
                data["users"][player1_name]["losses"] += 1
                if player2_name:
                    data["users"][player2_name]["wins"] += 1
                winner_name = player2_name or "N/A"
            elif player2_name and player1_score == player2_score:
                data["users"][player1_name]["draws"] += 1
                data["users"][player2_name]["draws"] += 1
                winner_name = "DRAW"
            elif player1_score > player2_score or not player2_name:
                data["users"][player1_name]["wins"] += 1
                if player2_name:
                    data["users"][player2_name]["losses"] += 1
                winner_name = player1_name
            else:
                data["users"][player1_name]["losses"] += 1
                if player2_name:
                    data["users"][player2_name]["wins"] += 1
                winner_name = player2_name or "N/A"

            data["users"][player1_name]["total_score"] += player1_score
            data["users"][player1_name]["games_played"] += 1
            if player2_name:
                data["users"][player2_name]["total_score"] += player2_score
                data["users"][player2_name]["games_played"] += 1
            data["games"].append({
                "player1": player1_name,
                "score1": player1_score,
                "player2": player2_name,
                "score2": player2_score,
                "winner": winner_name,
                "timestamp": legacy._now_iso(),
            })
            return dict(data["users"][player1_name])

    def get_leaderboard(self):
        with self._data() as data:
            users = [dict(row) for row in data["users"].values()]
        for user in users:
            user.setdefault("draws", 0)
        return sorted(users, key=lambda row: (row["wins"], row["draws"], row["total_score"]), reverse=True)

    def get_recent_games(self, limit=10, username=None):
        with self._data() as data:
            games = list(data.get("games", []))
        result = []
        for game in legacy._sorted_games_desc(games):
            if username and username not in {game.get("player1"), game.get("player2")}:
                continue
            entry = legacy._serialize_game_entry(game, username=username)
            if entry is not None:
                result.append(entry)
            if len(result) >= legacy._clamp_limit(limit, default=10, maximum=50):
                break
        return result

    def save_single_leaderboard(self, username, score):
        with self._data(write=True) as data:
            data["single_leaderboard"].append({
                "username": username,
                "score": legacy._coerce_int(score),
                "timestamp": legacy._now_iso(),
            })
            data["single_leaderboard"] = sorted(
                data["single_leaderboard"], key=lambda row: row["score"], reverse=True
            )[:20]
        return True

    def get_single_leaderboard(self):
        with self._data() as data:
            rows = data.get("single_leaderboard", [])
            return [dict(row) for row in sorted(rows, key=lambda row: row["score"], reverse=True)]

    def save_bot_game_result(self, username, score, bot_score, policy_mode, match_id, *, verified=False):
        with self._data(write=True) as data:
            for key, default in (("bot_users", {}), ("bot_games", [])):
                data.setdefault(key, default)
            existing = next((row for row in data["bot_games"] if row.get("match_id") == match_id), None)
            if existing:
                return {"saved": False, "duplicate": True, "entry": dict(existing)}

            score = legacy._coerce_int(score)
            bot_score = legacy._coerce_int(bot_score)
            user = data["bot_users"].setdefault(username, legacy._normalize_user(username, {}))
            if score > bot_score:
                user["wins"] += 1
                winner = username
            elif score < bot_score:
                user["losses"] += 1
                winner = "Yacht Bot"
            else:
                user["draws"] += 1
                winner = "DRAW"
            user["total_score"] += score
            user["games_played"] += 1
            verification_key = "verified_games" if verified else "unverified_games"
            user[verification_key] = int(user.get(verification_key, 0) or 0) + 1
            entry = {
                "match_id": match_id,
                "player1": username,
                "score1": score,
                "player2": "Yacht Bot",
                "score2": bot_score,
                "winner": winner,
                "policy_mode": policy_mode,
                "timestamp": legacy._now_iso(),
                "verified": bool(verified),
            }
            data["bot_games"].append(entry)
            data["bot_games"] = legacy._sorted_games_desc(data["bot_games"])[:MAX_BOT_GAME_HISTORY]
            return {"saved": True, "duplicate": False, "entry": dict(entry), "user": dict(user)}

    def get_bot_leaderboard(self):
        with self._data() as data:
            users = [dict(row) for row in data.get("bot_users", {}).values()]
        for user in users:
            user.setdefault("draws", 0)
            games = user.get("games_played", 0) or 0
            user["avg_score"] = round((user.get("total_score", 0) or 0) / games, 1) if games else 0.0
            user["verified_games"] = int(user.get("verified_games", 0) or 0)
            user["unverified_games"] = int(user.get("unverified_games", 0) or 0)
            user["verified"] = bool(user["verified_games"]) and not user["unverified_games"]
        ranked = sorted(users, key=lambda row: (row["wins"], row["draws"], row["total_score"]), reverse=True)
        return ranked

    def get_recent_bot_games(self, limit=10):
        with self._data() as data:
            games = list(data.get("bot_games", []))
        return [
            {
                **legacy._serialize_game_entry(game),
                "game_type": "vs_ai",
                "policy_mode": game.get("policy_mode"),
                "verified": bool(game.get("verified", False)),
            }
            for game in legacy._sorted_games_desc(games)[: legacy._clamp_limit(limit, default=10, maximum=50)]
        ]

    def reset_leaderboard(self):
        with self._data(write=True) as data:
            data.clear()
            data.update(legacy._default_data())
        return True

    def get_user_stats(self, username):
        with self._data() as data:
            user = data["users"].get(username)
            return dict(user) if user else None

    def get_user_profile(self, username, recent_limit=5):
        with self._data() as data:
            user = data["users"].get(username)
            if not user:
                return None
            user = dict(user)
            users = [dict(row) for row in data["users"].values()]
            games = list(data.get("games", []))

        for row in users:
            row.setdefault("draws", 0)
        users.sort(key=lambda row: (row["wins"], row["draws"], row["total_score"]), reverse=True)
        rank = next((idx + 1 for idx, row in enumerate(users) if row.get("username") == username), None)
        recent_games = []
        for game in legacy._sorted_games_desc(games):
            if username not in {game.get("player1"), game.get("player2")}:
                continue
            entry = legacy._serialize_game_entry(game, username=username)
            if entry is not None:
                recent_games.append(entry)
            if len(recent_games) >= legacy._clamp_limit(recent_limit, default=5, maximum=10):
                break

        games_played = user.get("games_played", 0) or 0
        wins = user.get("wins", 0) or 0
        draws = user.get("draws", 0) or 0
        losses = user.get("losses", 0) or 0
        total_score = user.get("total_score", 0) or 0
        return {
            "username": username,
            "rank": rank,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "games_played": games_played,
            "total_score": total_score,
            "avg_score": round(total_score / games_played, 1) if games_played else 0.0,
            "win_rate": round((wins / games_played) * 100, 1) if games_played else 0.0,
            "created_at": user.get("created_at"),
            "last_played_at": recent_games[0].get("timestamp") if recent_games else None,
            "current_streak": legacy._current_streak(recent_games),
            "recent_form": [
                {"win": "W", "loss": "L", "draw": "D"}.get(game.get("result"), "?")
                for game in recent_games
            ],
            "recent_games": recent_games,
        }


class JsonResultRepository(ResultRepository):
    backend_name = "json"

    @contextmanager
    def _data(self, *, write=False):
        with legacy.DATA_LOCK:
            data = legacy._load_data_unlocked()
            yield data
            if write:
                legacy._save_data_unlocked(data)


class SQLiteResultRepository(ResultRepository):
    backend_name = "sqlite"

    def __init__(self, path):
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS yacht_state (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO yacht_state (id, payload) VALUES (1, ?)",
                (json.dumps(legacy._default_data(), ensure_ascii=False),),
            )

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def _data(self, *, write=False):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            row = connection.execute("SELECT payload FROM yacht_state WHERE id = 1").fetchone()
            data = legacy._normalize_data(json.loads(row[0])) if row else legacy._default_data()
            yield data
            if write:
                payload = json.dumps(legacy._normalize_data(data), ensure_ascii=False, separators=(",", ":"))
                connection.execute("UPDATE yacht_state SET payload = ? WHERE id = 1", (payload,))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def create_result_repository():
    backend = os.getenv("YACHT_RESULT_BACKEND", "json").strip().lower()
    if backend in ("", "json", "file"):
        return JsonResultRepository()
    if backend == "sqlite":
        return SQLiteResultRepository(os.getenv("YACHT_SQLITE_PATH", "game_data.sqlite3"))
    raise RuntimeError(f"Unsupported result backend: {backend}")
