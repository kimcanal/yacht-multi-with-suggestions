import tempfile
import threading
import time
import unittest

from utils.presence_store import InMemoryPresenceStore
from utils.room_store import InMemoryRoomStore
from yacht_app.stores.results import SQLiteResultRepository
from yacht_app.stores.sessions import InMemorySingleSessionStore


class StoreContractTests(unittest.TestCase):
    def test_room_store_save_if_absent_rejects_collision(self):
        store = InMemoryRoomStore()
        first = {"players": ["host"]}
        second = {"players": ["guest"]}

        self.assertTrue(store.save_if_absent("ABC123", first))
        self.assertFalse(store.save_if_absent("ABC123", second))
        self.assertEqual(store.get("ABC123"), first)

    def test_room_store_lock_serializes_updates(self):
        store = InMemoryRoomStore()
        store.save("ABC123", {"count": 0})

        def increment():
            for _ in range(30):
                with store.lock("ABC123"):
                    room = store.get("ABC123")
                    current = room["count"]
                    time.sleep(0.001)
                    room["count"] = current + 1
                    store.save("ABC123", room)

        workers = [threading.Thread(target=increment) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertEqual(store.get("ABC123")["count"], 120)

    def test_presence_store_dict_contract(self):
        store = InMemoryPresenceStore()
        store["client-1"] = {"username": "tester1", "last_seen": 1.0}

        self.assertEqual(len(store), 1)
        self.assertEqual(list(store.items()), [("client-1", {"username": "tester1", "last_seen": 1.0})])
        self.assertEqual(store.pop("client-1")["username"], "tester1")
        self.assertEqual(len(store), 0)


    def test_single_session_store_mapping_and_lock_contract(self):
        store = InMemorySingleSessionStore()
        with store.lock():
            store["session-1"] = {"username": "tester1"}
        self.assertEqual(store.get("session-1")["username"], "tester1")
        self.assertEqual(list(store.items())[0][0], "session-1")
        self.assertEqual(store.pop("session-1")["username"], "tester1")

    def test_sqlite_result_repository_persists_and_serializes_writers(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = f"{tempdir}/results.sqlite3"
            store = SQLiteResultRepository(path)

            def record_games():
                for _ in range(5):
                    store.save_game_result("alpha1", 200, "beta12", 180)

            workers = [threading.Thread(target=record_games) for _ in range(4)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            reopened = SQLiteResultRepository(path)
            leaderboard = reopened.get_leaderboard()
            self.assertEqual(leaderboard[0]["username"], "alpha1")
            self.assertEqual(leaderboard[0]["games_played"], 20)
            self.assertEqual(len(reopened.get_recent_games(limit=50)), 20)

            reopened.save_single_leaderboard("alpha1", 222)
            self.assertEqual(reopened.get_single_leaderboard()[0]["score"], 222)
            self.assertEqual(reopened.get_user_profile("alpha1")["wins"], 20)

            first_bot_game = reopened.save_bot_game_result(
                "alpha1", 231, 202, "exact_memo", "sqlite-bot-match-01",
            )
            self.assertTrue(first_bot_game["saved"])
            self.assertFalse(first_bot_game["entry"]["verified"])
            self.assertTrue(
                SQLiteResultRepository(path).save_bot_game_result(
                    "alpha1", 231, 202, "exact_memo", "sqlite-bot-match-01",
                )["duplicate"]
            )
            self.assertEqual(SQLiteResultRepository(path).get_bot_leaderboard()[0]["wins"], 1)

if __name__ == "__main__":
    unittest.main()
