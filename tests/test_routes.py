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

        multi_leaderboard = self.client.get("/api/leaderboard/multi")
        self.assertEqual(multi_leaderboard.status_code, 200)
        multi_payload = multi_leaderboard.get_json()
        self.assertEqual([entry["username"] for entry in multi_payload[:2]], ["alpha1", "beta12"])

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
