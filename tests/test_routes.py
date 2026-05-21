import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("YACHT_AI_WARMUP", "0")

import database
import routes.leaderboard as leaderboard_routes
import server
from app_state import ai_metrics, lobby_clients, rooms


class RouteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server.app
        cls.client = cls.app.test_client()

    def setUp(self):
        rooms.clear()
        lobby_clients.clear()
        ai_metrics.recent_latencies.clear()
        ai_metrics.recent_stages.clear()
        ai_metrics.recent_slow_samples.clear()
        ai_metrics.request_count = 0
        ai_metrics.error_count = 0
        ai_metrics.max_latency_ms = 0.0

        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.original_data_file = database.DATA_FILE
        database.DATA_FILE = os.path.join(self.tempdir.name, "game_data.json")
        self.addCleanup(self._restore_database_file)

        self.original_admin_token = leaderboard_routes.RESET_ADMIN_TOKEN
        leaderboard_routes.RESET_ADMIN_TOKEN = "test-admin-token"
        self.addCleanup(self._restore_admin_token)

    def _restore_database_file(self):
        database.DATA_FILE = self.original_data_file

    def _restore_admin_token(self):
        leaderboard_routes.RESET_ADMIN_TOKEN = self.original_admin_token

    def test_recommend_and_health_endpoints(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")

        response = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["stage"], "roll")
        self.assertEqual(payload["strategy_mode"], "focused")
        self.assertEqual(payload["keep_indices"], [0, 1, 2, 3])
        self.assertEqual(len(payload["dice_recommendations"]), 5)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertIn("X-AI-Elapsed-Ms", response.headers)
        self.assertEqual(response.headers["X-AI-Request-Cache"], "miss")

        response_cached = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(response_cached.status_code, 200)
        self.assertEqual(response_cached.headers["X-AI-Request-Cache"], "hit")


    def test_recommend_validation_errors(self):
        bad_dice = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(bad_dice.status_code, 400)

        bad_scorecard = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 5],
                "rolls_left": 1,
                "scorecard": [None] * 11,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(bad_scorecard.status_code, 400)

        bad_mode = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 5],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "aggressive",
            },
        )
        self.assertEqual(bad_mode.status_code, 400)

        bad_rolls = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 5],
                "rolls_left": 3,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(bad_rolls.status_code, 400)

    def test_lobby_presence_endpoints(self):
        heartbeat = self.client.post(
            "/api/lobby-heartbeat",
            json={"client_id": "client-1", "username": "tester1"},
        )
        self.assertEqual(heartbeat.status_code, 200)
        self.assertEqual(heartbeat.get_json()["active_clients"], 1)

        lobby_users = self.client.get("/api/lobby-users")
        self.assertEqual(lobby_users.status_code, 200)
        self.assertEqual(lobby_users.get_json(), [{"client_id": "client-1", "username": "tester1"}])

        online_users = self.client.get("/api/online-users")
        self.assertEqual(online_users.status_code, 200)
        self.assertEqual(online_users.get_json(), [{"username": "tester1", "status": "대기중"}])

        fake_memory = SimpleNamespace(percent=42.5, used=3 * 1024 ** 3, total=8 * 1024 ** 3)
        with patch("routes.lobby.psutil.cpu_percent", return_value=12.5), patch(
            "routes.lobby.psutil.virtual_memory",
            return_value=fake_memory,
        ):
            system_status = self.client.get("/api/system-status")

        self.assertEqual(system_status.status_code, 200)
        payload = system_status.get_json()
        self.assertEqual(payload["online_count"], 1)
        self.assertEqual(payload["active_rooms"], 0)
        self.assertEqual(payload["cpu_percent"], 12.5)
        self.assertEqual(payload["memory_percent"], 42.5)
        self.assertIn("ai_policy_model_status", payload)

    def test_room_lifecycle_with_observer_and_forfeit(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        self.assertEqual(created.status_code, 200)
        created_payload = created.get_json()
        code = created_payload["code"]
        host_token = created_payload["player_token"]

        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)
        guest_token = joined.get_json()["player_token"]

        observed = self.client.post(f"/api/rooms/{code}/observe", json={"username": "watch1"})
        self.assertEqual(observed.status_code, 200)
        self.assertEqual(observed.get_json()["observers"], ["watch1"])

        room = self.client.get(f"/api/rooms/{code}", query_string={"u": "host1", "pt": host_token})
        self.assertEqual(room.status_code, 200)
        room_payload = room.get_json()
        self.assertEqual(room_payload["room_phase"], "playing")
        self.assertEqual(room_payload["player2"], "guest1")
        self.assertEqual(room_payload["observer_count"], 1)

        unchanged = self.client.get(f"/api/rooms/{code}", query_string={"sv": 1})
        self.assertEqual(unchanged.status_code, 200)
        self.assertTrue(unchanged.get_json()["unchanged"])

        observer_heartbeat = self.client.post(
            f"/api/rooms/{code}/heartbeat",
            json={"username": "watch1"},
        )
        self.assertEqual(observer_heartbeat.status_code, 200)
        self.assertEqual(observer_heartbeat.get_json()["observer_count"], 1)

        denied_roll = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": "wrong", "kept": [0, 0, 0, 0, 0]},
        )
        self.assertEqual(denied_roll.status_code, 403)

        rolled = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": host_token, "kept": [0, 0, 0, 0, 0]},
        )
        self.assertEqual(rolled.status_code, 200)
        rolled_payload = rolled.get_json()
        self.assertEqual(rolled_payload["rolls_left"], 2)
        self.assertEqual(rolled_payload["state"]["version"], 2)
        self.assertIn("fairness", rolled_payload)
        self.assertIn("revealed", rolled_payload["fairness"])
        self.assertIn("next_hash", rolled_payload["fairness"])

        fairness = self.client.get(f"/api/rooms/{code}/fairness")
        self.assertEqual(fairness.status_code, 200)
        fairness_payload = fairness.get_json()
        self.assertIn("current_hash", fairness_payload)
        self.assertIn("last_reveal", fairness_payload)

        wrong_turn_sync = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "guest1",
                "player_token": guest_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {"host1": [None] * 12, "guest1": [None] * 12},
            },
        )
        self.assertEqual(wrong_turn_sync.status_code, 403)

        synced = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {"host1": [5] + [None] * 11, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )
        self.assertEqual(synced.status_code, 200)
        self.assertEqual(synced.get_json()["state"]["turn"], "guest1")

        left = self.client.post(
            f"/api/rooms/{code}/leave",
            json={"username": "guest1", "player_token": guest_token},
        )
        self.assertEqual(left.status_code, 200)
        self.assertEqual(left.get_json()["players"], ["host1"])

        finished_room = self.client.get(f"/api/rooms/{code}")
        self.assertEqual(finished_room.status_code, 200)
        finished_payload = finished_room.get_json()
        self.assertEqual(finished_payload["room_phase"], "finished")
        self.assertEqual(finished_payload["state"]["winner"], "host1")
        self.assertEqual(finished_payload["state"]["loser"], "guest1")
        self.assertEqual(finished_payload["state"]["end_reason"], "leave")

        leaderboard = self.client.get("/api/leaderboard")
        leaderboard_payload = leaderboard.get_json()
        self.assertEqual(leaderboard.status_code, 200)
        self.assertEqual(leaderboard_payload[0]["username"], "host1")
        self.assertEqual(leaderboard_payload[0]["wins"], 1)


    def test_sync_validation_errors(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]
        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)

        bad_rolls = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 4,
                "scores": {"host1": [None] * 12, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )
        self.assertEqual(bad_rolls.status_code, 400)

        bad_scores = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {"host1": [None] * 11, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )
        self.assertEqual(bad_scores.status_code, 400)

    def test_rematch_requires_both_players_and_resets_room(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        self.assertEqual(created.status_code, 200)
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]

        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)
        guest_token = joined.get_json()["player_token"]

        finished = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [6, 6, 6, 6, 6],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {
                    "host1": [3, 6, 9, 12, 15, 18, 26, 24, 22, 15, 30, 50],
                    "guest1": [1, 4, 6, 8, 10, 12, 20, 18, 0, 0, 0, 0],
                },
                "turn": "host1",
                "game_over": True,
                "winner": "host1",
                "loser": "guest1",
                "end_reason": "score",
            },
        )
        self.assertEqual(finished.status_code, 200)
        self.assertTrue(finished.get_json()["state"]["game_over"])

        waiting = self.client.post(
            f"/api/rooms/{code}/rematch",
            json={"username": "host1", "player_token": host_token},
        )
        self.assertEqual(waiting.status_code, 200)
        waiting_payload = waiting.get_json()
        self.assertEqual(waiting_payload["status"], "waiting")
        self.assertEqual(waiting_payload["rematch_pending_players"], ["host1"])
        self.assertEqual(waiting_payload["rematch_waiting_for"], ["guest1"])

        room_waiting = self.client.get(f"/api/rooms/{code}", query_string={"u": "host1", "pt": host_token, "sv": 2})
        self.assertEqual(room_waiting.status_code, 200)
        room_waiting_payload = room_waiting.get_json()
        self.assertTrue(room_waiting_payload["unchanged"])
        self.assertEqual(room_waiting_payload["rematch_pending_players"], ["host1"])

        started = self.client.post(
            f"/api/rooms/{code}/rematch",
            json={"username": "guest1", "player_token": guest_token},
        )
        self.assertEqual(started.status_code, 200)
        started_payload = started.get_json()
        self.assertEqual(started_payload["status"], "started")
        self.assertFalse(started_payload["state"]["game_over"])
        self.assertEqual(started_payload["state"]["turn"], "guest1")
        self.assertEqual(started_payload["rematch_pending_players"], [])

        reset_room = self.client.get(f"/api/rooms/{code}", query_string={"u": "guest1", "pt": guest_token})
        self.assertEqual(reset_room.status_code, 200)
        reset_payload = reset_room.get_json()
        self.assertEqual(reset_payload["room_phase"], "playing")
        self.assertEqual(reset_payload["state"]["turn"], "guest1")
        self.assertFalse(reset_payload["state"]["game_over"])
        self.assertEqual(reset_payload["state"]["scores"]["host1"], [None] * 12)
        self.assertEqual(reset_payload["state"]["scores"]["guest1"], [None] * 12)
        self.assertEqual(reset_payload["rematch_pending_players"], [])

        guest_roll = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "guest1", "player_token": guest_token, "kept": [0, 0, 0, 0, 0]},
        )
        self.assertEqual(guest_roll.status_code, 200)
        self.assertEqual(guest_roll.get_json()["rolls_left"], 2)

    def test_leaderboard_endpoints_and_reset(self):
        single_saved = self.client.post(
            "/api/leaderboard/single",
            json={"username": "solo1", "score": 211},
        )
        self.assertEqual(single_saved.status_code, 200)
        self.assertTrue(single_saved.get_json()["success"])

        single_leaderboard = self.client.get("/api/leaderboard/single")
        self.assertEqual(single_leaderboard.status_code, 200)
        self.assertEqual(single_leaderboard.get_json()[0]["username"], "solo1")

        saved_game = self.client.post(
            "/api/save-game",
            json={"player1": "alpha1", "score1": 211, "player2": "beta12", "score2": 183},
        )
        self.assertEqual(saved_game.status_code, 200)
        self.assertEqual(saved_game.get_json()["status"], "success")

        second_game = self.client.post(
            "/api/save-game",
            json={"player1": "beta12", "score1": 198, "player2": "alpha1", "score2": 205},
        )
        self.assertEqual(second_game.status_code, 200)

        draw_game = self.client.post(
            "/api/save-game",
            json={"player1": "alpha1", "score1": 190, "player2": "gamma34", "score2": 190},
        )
        self.assertEqual(draw_game.status_code, 200)

        multi_leaderboard = self.client.get("/api/leaderboard/multi")
        self.assertEqual(multi_leaderboard.status_code, 200)
        multi_payload = multi_leaderboard.get_json()
        self.assertEqual([entry["username"] for entry in multi_payload[:3]], ["alpha1", "gamma34", "beta12"])

        recent_games = self.client.get("/api/leaderboard/recent", query_string={"limit": 2})
        self.assertEqual(recent_games.status_code, 200)
        recent_payload = recent_games.get_json()
        self.assertEqual(len(recent_payload), 2)
        self.assertEqual(recent_payload[0]["winner"], "DRAW")
        self.assertEqual(recent_payload[1]["winner"], "alpha1")

        alpha_recent = self.client.get(
            "/api/leaderboard/recent",
            query_string={"username": "alpha1", "limit": 2},
        )
        self.assertEqual(alpha_recent.status_code, 200)
        alpha_recent_payload = alpha_recent.get_json()
        self.assertEqual(alpha_recent_payload[0]["result"], "draw")
        self.assertEqual(alpha_recent_payload[0]["opponent"], "gamma34")
        self.assertEqual(alpha_recent_payload[1]["result"], "win")

        alpha_profile = self.client.get("/api/leaderboard/users/alpha1")
        self.assertEqual(alpha_profile.status_code, 200)
        alpha_profile_payload = alpha_profile.get_json()
        self.assertEqual(alpha_profile_payload["wins"], 2)
        self.assertEqual(alpha_profile_payload["draws"], 1)
        self.assertEqual(alpha_profile_payload["losses"], 0)
        self.assertEqual(alpha_profile_payload["games_played"], 3)
        self.assertEqual(alpha_profile_payload["rank"], 1)
        self.assertEqual(alpha_profile_payload["recent_form"], ["D", "W", "W"])
        self.assertEqual(alpha_profile_payload["current_streak"], {"type": "draw", "count": 1})
        self.assertAlmostEqual(alpha_profile_payload["avg_score"], 202.0)
        self.assertAlmostEqual(alpha_profile_payload["win_rate"], 66.7)

        denied_reset = self.client.post(
            "/api/leaderboard/reset",
            headers={"X-Admin-Token": "wrong-token"},
        )
        self.assertEqual(denied_reset.status_code, 403)

        reset = self.client.post(
            "/api/leaderboard/reset",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.get_json()["status"], "reset")

        after_reset = self.client.get("/api/leaderboard")
        self.assertEqual(after_reset.status_code, 200)
        self.assertEqual(after_reset.get_json(), [])


if __name__ == "__main__":
    unittest.main()
