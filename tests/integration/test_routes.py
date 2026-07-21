import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("YACHT_AI_WARMUP", "0")
os.environ.setdefault("YACHT_ROOM_BACKEND", "memory")
os.environ.setdefault("YACHT_OTEL_ENABLED", "0")

import database
import routes.ai as ai_routes
import routes.leaderboard as leaderboard_routes
import server
from app_state import ai_metrics, lobby_clients, rooms, single_sessions, single_sessions_lock
from yacht_ai.ml_policy import RollPolicyModel
from yacht_engine import CATS, calc_score


class RouteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server.app
        cls.client = cls.app.test_client()

    def setUp(self):
        rooms.clear()
        lobby_clients.clear()
        with single_sessions_lock:
            single_sessions.clear()
        ai_metrics.recent_latencies.clear()
        ai_metrics.recent_stages.clear()
        ai_metrics.recent_slow_samples.clear()
        ai_metrics.request_count = 0
        ai_metrics.error_count = 0
        ai_metrics.max_latency_ms = 0.0
        ai_routes._RECOMMEND_RESULT_CACHE.clear()

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
        self.assertEqual(health.get_json()["room_backend"], "memory")
        self.assertEqual(health.get_json()["presence_backend"], "memory")

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
        self.assertIn("decision_report", payload)
        report = payload["decision_report"]
        self.assertEqual(report["title"], "AI 결론 리포트")
        self.assertTrue(report["conclusion"])
        self.assertIn(report["method"]["source"], {"exact", "learned_roll_policy"})
        self.assertTrue(report["method"]["label"])
        self.assertIn("decision_margin_text", report["method"])
        self.assertIn("decision_margin_key", report["method"])
        self.assertTrue(report["learning_note"])
        self.assertGreaterEqual(len(report["why"]), 1)
        comparison = payload["action_comparison"]
        self.assertEqual(comparison["recommended"], "reroll")
        self.assertTrue(comparison["record_target"])
        self.assertIsInstance(comparison["record_score"], int)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertIn("X-AI-Elapsed-Ms", response.headers)
        self.assertIn("X-Request-ID", response.headers)
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
        self.assertIn("decision_report", response_cached.get_json())

    def test_alternate_multiplayer_table_page_is_available(self):
        response = self.client.get("/game/multi/table?room=ABC123")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"table-game-shell", response.data)
        self.assertIn(b"multi-game-table.css", response.data)

    def test_alternate_single_table_page_is_available(self):
        response = self.client.get("/game/single/table?mode=solo&coach=on")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"single-table-game-shell", response.data)
        self.assertIn(b"single-game-table.css", response.data)

    @patch("routes.ai.request_win_probability")
    def test_win_probability_endpoint_validates_and_returns_pending_projection(self, request_probability):
        request_probability.return_value = {
            "status": "pending",
            "request_id": "test-request",
            "retry_after_ms": 900,
            "my_projected": 198.3582,
            "opp_projected": 198.3582,
            "projection_method": "full_game_exact_value",
        }
        response = self.client.post(
            "/api/win-probability",
            json={"my_scorecard": [None] * 12, "opp_scorecard": [None] * 12, "samples": 30},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["status"], "pending")
        request_probability.assert_called_once()
        self.assertEqual(request_probability.call_args.args[0]["samples"], 30)

        request_probability.reset_mock()
        refined = self.client.post(
            "/api/win-probability",
            json={"my_scorecard": [None] * 12, "opp_scorecard": [None] * 12, "samples": 100},
        )
        self.assertEqual(refined.status_code, 202)
        self.assertEqual(request_probability.call_args.args[0]["samples"], 100)

        invalid = self.client.post(
            "/api/win-probability",
            json={"my_scorecard": [None] * 11, "opp_scorecard": [None] * 12},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_recommend_focused_score_stage_uses_exact_value_by_default(self):
        # scorecard: Threes/Twos/Sixes 등 상단 여러 칸이 열려 있어 순수 휴리스틱이면
        # 상단 보너스 페이스를 우선해 Sixes에 적곤 했던 상태. Full House가 완성됐으므로
        # exact V 기준 정답은 Full House.
        scorecard = [None, None, 3, None, 15, None, 24, None, None, 15, 30, None]
        response = self.client.post(
            "/api/recommend",
            json={
                "dice": [6, 6, 5, 5, 6],
                "rolls_left": 0,
                "scorecard": scorecard,
                "strategy_mode": "focused",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["stage"], "score")
        self.assertEqual(payload["strategy_mode"], "focused")
        self.assertEqual(payload["score_value_mode"], "value_score_only")
        self.assertEqual(payload["policy_source"], "exact")
        self.assertEqual(payload["primary_target"], "Full House")

        # roll-stage keep 판단은 여전히 focused 휴리스틱 그대로다.
        roll_response = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        roll_payload = roll_response.get_json()
        self.assertEqual(roll_payload["keep_indices"], [0, 1, 2, 3])

    def test_all_keep_roll_recommendation_is_presented_as_record_now(self):
        response = self.client.post(
            "/api/recommend",
            json={
                "dice": [6, 6, 6, 6, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "optimal",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["stage"], "score")
        self.assertEqual(payload["recommended_action"], "score_now")
        self.assertEqual(payload["record_now"]["category"], "Yacht")
        self.assertEqual(payload["record_now"]["score"], 50)
        self.assertIn("지금 Yacht 50점 기록 추천", payload["message"])

    def test_loaded_roll_policy_is_used_for_cover_but_not_focused_value_mode(self):
        model_path = Path("artifacts/runtime/models/model-20260717-roll-policy-v3.json")
        self.assertTrue(model_path.exists())
        original_model = ai_metrics.policy_model
        original_status = ai_metrics.policy_model_status
        ai_metrics.policy_model = RollPolicyModel.load(model_path)
        ai_metrics.policy_model_status = "loaded"
        self.addCleanup(setattr, ai_metrics, "policy_model", original_model)
        self.addCleanup(setattr, ai_metrics, "policy_model_status", original_status)

        focused = self.client.post(
            "/api/recommend",
            json={
                "dice": [3, 3, 5, 6, 6],
                "rolls_left": 2,
                "scorecard": [None, None, None, None, None, None, 13, None, None, None, None, None],
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(focused.status_code, 200)
        focused_payload = focused.get_json()
        self.assertEqual(focused_payload["policy_source"], "exact")
        self.assertEqual(focused_payload["score_value_mode"], "value_score_only")

        ai_routes._RECOMMEND_RESULT_CACHE.clear()
        cover = self.client.post(
            "/api/recommend",
            json={
                "dice": [3, 4, 4, 6, 6],
                "rolls_left": 1,
                "scorecard": [3, 4, 9, 8, 10, 12, 19, 0, None, 15, None, 0],
                "strategy_mode": "cover",
            },
        )
        self.assertEqual(cover.status_code, 200)
        cover_payload = cover.get_json()
        self.assertEqual(cover_payload["policy_source"], "learned_roll_policy")
        self.assertEqual(cover.headers["X-AI-Policy-Source"], "learned_roll_policy")

    def test_recommend_optimal_strategy_uses_exact_value_mode(self):
        response = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "optimal",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["stage"], "roll")
        self.assertEqual(payload["strategy_mode"], "optimal")
        self.assertEqual(payload["score_value_mode"], "value_optimal")
        self.assertEqual(payload["policy_source"], "exact_value_optimal")
        self.assertEqual(response.headers["X-AI-Policy-Source"], "exact_value_optimal")
        self.assertIn("예상 최종 점수", payload["summary"])
        self.assertEqual(
            payload["expected_final_score"],
            round(payload["banked_score"] + payload["remaining_game_ev"], 2),
        )
        self.assertEqual(payload["decision_report"]["method"]["source"], "exact_value_optimal")
        self.assertEqual(payload["decision_report"]["method"]["label"], "Full-game exact V")
        self.assertEqual(
            payload["decision_report"]["decision"]["expected_value"],
            payload["expected_final_score"],
        )

    @patch(
        "routes.ai.yacht_engine.solve_best_move",
        side_effect=ai_routes.yacht_engine.ExactValueTableUnavailableError("missing"),
    )
    def test_recommend_optimal_returns_503_when_exact_table_is_unavailable(self, solve):
        response = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 6],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "optimal",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "exact_value_unavailable")
        self.assertIn("최적 계산 데이터", response.get_json()["message"])
        solve.assert_called_once()

    def test_request_id_header_is_propagated(self):
        response = self.client.get("/health", headers={"X-Request-ID": "route-test-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "route-test-123")

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

        non_numeric_rolls = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 5],
                "rolls_left": "soon",
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(non_numeric_rolls.status_code, 400)

        impossible_score = self.client.post(
            "/api/recommend",
            json={
                "dice": [1, 2, 3, 4, 5],
                "rolls_left": 1,
                "scorecard": [6] + [None] * 11,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(impossible_score.status_code, 400)

        boolean_dice = self.client.post(
            "/api/recommend",
            json={
                "dice": [True, 2, 3, 4, 5],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(boolean_dice.status_code, 400)

        fractional_dice = self.client.post(
            "/api/recommend",
            json={
                "dice": [1.5, 2, 3, 4, 5],
                "rolls_left": 1,
                "scorecard": [None] * 12,
                "strategy_mode": "focused",
            },
        )
        self.assertEqual(fractional_dice.status_code, 400)

        non_json = self.client.post(
            "/api/recommend",
            data="dice=1,2,3,4,5",
            content_type="text/plain",
        )
        self.assertEqual(non_json.status_code, 400)
        self.assertEqual(ai_metrics.error_count, 0)

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

        leaked_query_token = self.client.get(
            f"/api/rooms/{code}",
            query_string={"u": "host1", "pt": host_token},
        )
        self.assertEqual(leaked_query_token.status_code, 403)

        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)
        guest_token = joined.get_json()["player_token"]

        observed = self.client.post(f"/api/rooms/{code}/observe", json={"username": "watch1"})
        self.assertEqual(observed.status_code, 200)
        self.assertEqual(observed.get_json()["observers"], ["watch1"])

        room = self.client.get(
            f"/api/rooms/{code}",
            query_string={"u": "host1"},
            headers={"X-Player-Token": host_token},
        )
        self.assertEqual(room.status_code, 200)
        room_payload = room.get_json()
        self.assertEqual(room_payload["room_phase"], "playing")
        self.assertEqual(room_payload["player2"], "guest1")
        self.assertEqual(room_payload["observer_count"], 1)

        event_stream = self.client.get(f"/api/rooms/{code}/events", query_string={"once": 1})
        self.assertEqual(event_stream.status_code, 200)
        self.assertEqual(event_stream.mimetype, "text/event-stream")
        self.assertEqual(event_stream.headers["Cache-Control"], "no-cache")
        event_text = event_stream.get_data(as_text=True)
        self.assertIn("event: room_state", event_text)
        self.assertIn(f'"code":"{code}"', event_text)

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
        host_score = calc_score(rolled_payload["dice"], CATS["Ones"])

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
                "rolls_left": 3,
                "scores": {"host1": [host_score] + [None] * 11, "guest1": [None] * 12},
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


    def test_room_reaction_send_rate_limit_and_sse(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]
        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        guest_token = joined.get_json()["player_token"]
        game_version_before_reaction = joined.get_json()["state"]["version"]

        forged = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "host1", "player_token": "wrong", "reaction": "nice"},
        )
        self.assertEqual(forged.status_code, 403)

        invalid = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "host1", "player_token": host_token, "reaction": "custom"},
        )
        self.assertEqual(invalid.status_code, 400)

        sent = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "guest1", "player_token": guest_token, "reaction": "fire"},
        )
        self.assertEqual(sent.status_code, 200)
        sent_payload = sent.get_json()
        self.assertEqual(sent_payload["reaction"]["user"], "guest1")
        self.assertEqual(sent_payload["reaction"]["code"], "fire")
        self.assertEqual(sent_payload["reaction"]["emoji"], "🔥")
        self.assertEqual(sent_payload["reaction"]["asset"], "/static/assets/openmoji/1F525.svg")
        first_reaction_id = sent_payload["reaction"]["id"]

        room = self.client.get(
            f"/api/rooms/{code}",
            query_string={"u": "host1"},
            headers={"X-Player-Token": host_token},
        )
        reactions = room.get_json()["reactions"]
        self.assertEqual(len(reactions), 1)
        self.assertEqual(reactions[0]["code"], "fire")
        self.assertEqual(room.get_json()["state"]["version"], game_version_before_reaction)

        rate_limited = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "guest1", "player_token": guest_token, "reaction": "laugh"},
        )
        self.assertEqual(rate_limited.status_code, 429)
        self.assertGreater(rate_limited.get_json()["retry_after_ms"], 0)

        second = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "host1", "player_token": host_token, "reaction": "gg"},
        )
        self.assertEqual(second.status_code, 200)

        reaction_events = self.client.get(
            f"/api/rooms/{code}/events",
            query_string={"once": 1, "reaction_id": first_reaction_id},
        )
        reaction_event_text = reaction_events.get_data(as_text=True)
        self.assertIn("event: reaction", reaction_event_text)
        self.assertIn('"code":"gg"', reaction_event_text)
        self.assertNotIn('"code":"fire"', reaction_event_text)

        outsider = self.client.post(
            f"/api/rooms/{code}/reaction",
            json={"username": "stranger", "reaction": "nice"},
        )
        self.assertEqual(outsider.status_code, 404)

        removed_chat = self.client.post(
            f"/api/rooms/{code}/chat",
            json={"username": "host1", "player_token": host_token, "text": "hi"},
        )
        self.assertEqual(removed_chat.status_code, 404)

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

    def test_sync_rejects_forged_score(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]
        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)

        rolled = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": host_token, "kept": [0, 0, 0, 0, 0]},
        )
        self.assertEqual(rolled.status_code, 200)

        forged = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [0, 0, 0, 0, 0],
                "rolls_left": 3,
                "scores": {"host1": [5] + [None] * 11, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )
        expected = calc_score(rolled.get_json()["dice"], CATS["Ones"])
        if expected == 5:
            self.skipTest("deterministic roll happened to match the forged score")
        self.assertEqual(forged.status_code, 400)

    def test_sync_cannot_overwrite_server_dice_before_scoring(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]
        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)

        rolled = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": host_token, "kept": [0, 0, 0, 0, 0]},
        )
        self.assertEqual(rolled.status_code, 200)
        server_dice = rolled.get_json()["dice"]
        self.assertNotEqual(rolled.get_json()["rolls_left"], 0)

        forged_sync = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [6, 6, 6, 6, 6],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {"host1": [None] * 12, "guest1": [None] * 12},
                "turn": "host1",
                "game_over": False,
            },
        )
        self.assertEqual(forged_sync.status_code, 200)
        forged_state = forged_sync.get_json()["state"]
        self.assertEqual(forged_state["dice"], server_dice)
        self.assertEqual(forged_state["rolls_left"], rolled.get_json()["rolls_left"])

        forged_card = [None] * 12
        forged_card[CATS["Yacht"]] = 50
        forged_score = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [6, 6, 6, 6, 6],
                "kept": [1, 1, 1, 1, 1],
                "rolls_left": 0,
                "scores": {"host1": forged_card, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )
        if calc_score(server_dice, CATS["Yacht"]) == 50:
            self.skipTest("deterministic roll happened to be Yacht")
        self.assertEqual(forged_score.status_code, 400)

    def test_multiplayer_keep_is_persisted_and_preserved_by_the_next_roll(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]
        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)

        first_roll = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": host_token, "kept": [0, 0, 0, 0, 0]},
        ).get_json()
        keep_mask = [1, 0, 0, 0, 0]
        synced = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "kept": keep_mask,
                "scores": {"host1": [None] * 12, "guest1": [None] * 12},
                "turn": "host1",
                "game_over": False,
            },
        )
        self.assertEqual(synced.status_code, 200)
        self.assertEqual(synced.get_json()["state"]["kept"], keep_mask)
        self.assertEqual(synced.get_json()["state"]["player_kept"]["host1"], keep_mask)

        second_roll = self.client.post(
            f"/api/rooms/{code}/roll",
            json={"username": "host1", "player_token": host_token, "kept": keep_mask},
        )
        self.assertEqual(second_roll.status_code, 200)
        self.assertEqual(second_roll.get_json()["dice"][0], first_roll["dice"][0])

    def test_multiplayer_zero_score_sacrifice_resets_next_turn_state(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        self.assertEqual(created.status_code, 200)
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]

        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)

        room = rooms.get(code)
        room["state"].update({
            "dice": [1, 2, 3, 4, 6],
            "kept": [0, 0, 0, 0, 0],
            "rolls_left": 0,
            "scores": {"host1": [None] * 12, "guest1": [None] * 12},
            "player_dice": {"host1": [1, 2, 3, 4, 6], "guest1": [6, 6, 6, 6, 6]},
            "player_kept": {"host1": [0, 0, 0, 0, 0], "guest1": [1, 1, 1, 1, 1]},
            "player_rolls_left": {"host1": 0, "guest1": 0},
            "turn": "host1",
            "version": 4,
        })
        rooms.save(code, room)

        host_card = [None] * 12
        host_card[CATS["Full House"]] = 0
        sacrificed = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "host1",
                "player_token": host_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [0, 0, 0, 0, 0],
                "rolls_left": 3,
                "scores": {"host1": host_card, "guest1": [None] * 12},
                "turn": "guest1",
                "game_over": False,
            },
        )

        self.assertEqual(sacrificed.status_code, 200)
        state = sacrificed.get_json()["state"]
        self.assertEqual(state["scores"]["host1"][CATS["Full House"]], 0)
        self.assertEqual(state["turn"], "guest1")
        self.assertEqual(state["rolls_left"], 3)
        self.assertEqual(state["kept"], [0, 0, 0, 0, 0])
        self.assertEqual(state["player_dice"]["guest1"], [1, 1, 1, 1, 1])
        self.assertEqual(state["player_kept"]["guest1"], [0, 0, 0, 0, 0])
        self.assertEqual(state["player_rolls_left"]["guest1"], 3)

    def test_rematch_requires_both_players_and_resets_room(self):
        created = self.client.post("/api/rooms", json={"username": "host1"})
        self.assertEqual(created.status_code, 200)
        code = created.get_json()["code"]
        host_token = created.get_json()["player_token"]

        joined = self.client.post(f"/api/rooms/{code}/join", json={"username": "guest1"})
        self.assertEqual(joined.status_code, 200)
        guest_token = joined.get_json()["player_token"]

        room = rooms.get(code)
        room["state"].update({
            "dice": [6, 6, 6, 6, 6],
            "kept": [1, 1, 1, 1, 1],
            "rolls_left": 0,
            "scores": {
                "host1": [3, 6, 9, 12, 15, 18, 26, 24, 22, 15, 30, 50],
                "guest1": [1, 4, 6, 8, 10, 12, 20, 18, 0, 0, 0, None],
            },
            "player_dice": {"host1": [1, 1, 1, 1, 1], "guest1": [6, 6, 6, 6, 6]},
            "player_kept": {"host1": [0, 0, 0, 0, 0], "guest1": [1, 1, 1, 1, 1]},
            "player_rolls_left": {"host1": 3, "guest1": 0},
            "turn": "guest1",
            "turn_start_time": None,
            "version": 2,
        })
        rooms.save(code, room)

        finished = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "guest1",
                "player_token": guest_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [0, 0, 0, 0, 0],
                "rolls_left": 3,
                "scores": {
                    "host1": [3, 6, 9, 12, 15, 18, 26, 24, 22, 15, 30, 50],
                    "guest1": [1, 4, 6, 8, 10, 12, 20, 18, 0, 0, 0, 50],
                },
                "turn": "guest1",
                "game_over": True,
            },
        )
        self.assertEqual(finished.status_code, 200)
        finished_payload = finished.get_json()
        self.assertTrue(finished_payload["state"]["game_over"])
        self.assertEqual(finished_payload["state"]["winner"], "host1")

        leaderboard = self.client.get("/api/leaderboard")
        self.assertEqual(leaderboard.status_code, 200)
        self.assertEqual(len(leaderboard.get_json()), 2)

        duplicate_finish = self.client.post(
            f"/api/rooms/{code}/sync",
            json={
                "username": "guest1",
                "player_token": guest_token,
                "dice": [1, 1, 1, 1, 1],
                "kept": [0, 0, 0, 0, 0],
                "rolls_left": 3,
                "scores": {
                    "host1": [3, 6, 9, 12, 15, 18, 26, 24, 22, 15, 30, 50],
                    "guest1": [1, 4, 6, 8, 10, 12, 20, 18, 0, 0, 0, 50],
                },
                "turn": "guest1",
                "game_over": True,
            },
        )
        self.assertEqual(duplicate_finish.status_code, 200)
        duplicate_payload = duplicate_finish.get_json()
        self.assertEqual(len(self.client.get("/api/leaderboard").get_json()), 2)

        waiting = self.client.post(
            f"/api/rooms/{code}/rematch",
            json={"username": "host1", "player_token": host_token},
        )
        self.assertEqual(waiting.status_code, 200)
        waiting_payload = waiting.get_json()
        self.assertEqual(waiting_payload["status"], "waiting")
        self.assertEqual(waiting_payload["rematch_pending_players"], ["host1"])
        self.assertEqual(waiting_payload["rematch_waiting_for"], ["guest1"])

        room_waiting = self.client.get(
            f"/api/rooms/{code}",
            query_string={"u": "host1", "sv": duplicate_payload["state"]["version"]},
            headers={"X-Player-Token": host_token},
        )
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

        reset_room = self.client.get(
            f"/api/rooms/{code}",
            query_string={"u": "guest1"},
            headers={"X-Player-Token": guest_token},
        )
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

    def test_ranked_single_session_rolls_and_scores_on_server(self):
        started = self.client.post(
            "/api/single/start",
            json={"username": "solo1", "mode": "solo", "coach_enabled": False},
        )
        self.assertEqual(started.status_code, 200)
        start_payload = started.get_json()
        session_id = start_payload["session_id"]
        session_token = start_payload["session_token"]

        rolled = self.client.post(
            "/api/single/roll",
            json={
                "session_id": session_id,
                "session_token": session_token,
                "kept": [0, 0, 0, 0, 0],
            },
        )
        self.assertEqual(rolled.status_code, 200)
        rolled_state = rolled.get_json()["state"]
        self.assertEqual(rolled_state["rolls_left"], 2)
        expected_score = calc_score(rolled_state["dice"], CATS["Ones"])

        scored = self.client.post(
            "/api/single/score",
            json={
                "session_id": session_id,
                "session_token": session_token,
                "category_idx": CATS["Ones"],
            },
        )
        self.assertEqual(scored.status_code, 200)
        scored_payload = scored.get_json()
        self.assertEqual(scored_payload["score"], expected_score)
        self.assertEqual(scored_payload["state"]["scorecard"][CATS["Ones"]], expected_score)
        self.assertEqual(scored_payload["state"]["rolls_left"], 3)

    def test_leaderboard_endpoints_and_reset(self):
        started_single = self.client.post(
            "/api/single/start",
            json={"username": "solo1", "mode": "solo", "coach_enabled": False},
        )
        self.assertEqual(started_single.status_code, 200)
        single_session = started_single.get_json()
        with single_sessions_lock:
            session = single_sessions[single_session["session_id"]]
            session["finished"] = True
            session["final_score"] = 211

        single_saved = self.client.post(
            "/api/leaderboard/single",
            json={
                "username": "solo1",
                "score": 211,
                "mode": "solo",
                "coach_enabled": False,
                "session_id": single_session["session_id"],
                "session_token": single_session["session_token"],
            },
        )
        self.assertEqual(single_saved.status_code, 200)
        self.assertTrue(single_saved.get_json()["success"])

        duplicate_single = self.client.post(
            "/api/leaderboard/single",
            json={
                "username": "solo1",
                "score": 211,
                "mode": "solo",
                "coach_enabled": False,
                "session_id": single_session["session_id"],
                "session_token": single_session["session_token"],
            },
        )
        self.assertEqual(duplicate_single.status_code, 403)

        single_leaderboard = self.client.get("/api/leaderboard/single")
        self.assertEqual(single_leaderboard.status_code, 200)
        self.assertEqual(single_leaderboard.get_json()[0]["username"], "solo1")

        saved_game = self.client.post(
            "/api/save-game",
            json={"player1": "alpha1", "score1": 211, "player2": "beta12", "score2": 183},
        )
        self.assertEqual(saved_game.status_code, 410)

        database.save_game_result("alpha1", 211, "beta12", 183)
        database.save_game_result("beta12", 198, "alpha1", 205)
        database.save_game_result("alpha1", 190, "gamma34", 190)

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

        bad_score = self.client.post(
            "/api/save-game",
            json={"player1": "alpha1", "score1": 1001, "player2": "beta12", "score2": 183},
        )
        self.assertEqual(bad_score.status_code, 410)

        fractional_single_score = self.client.post(
            "/api/leaderboard/single",
            json={"username": "solo1", "score": 211.5, "mode": "solo", "coach_enabled": False},
        )
        self.assertEqual(fractional_single_score.status_code, 400)

        coach_score = self.client.post(
            "/api/leaderboard/single",
            json={"username": "solo1", "score": 211, "mode": "solo", "coach_enabled": True},
        )
        self.assertEqual(coach_score.status_code, 403)

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
