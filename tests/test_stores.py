import threading
import time
import unittest

from utils.presence_store import InMemoryPresenceStore
from utils.room_store import InMemoryRoomStore


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


if __name__ == "__main__":
    unittest.main()
