import sqlite3
import unittest
from switchboard.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)

    def test_account_lifecycle(self):
        self.store.add_user("alice", "key", True)
        self.assertTrue(self.store.user("alice")["admin"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_user("alice", "other-key")
        self.store.disable("alice")
        self.assertTrue(self.store.user("alice")["disabled"])
        self.store.set_key("alice", "new-key")
        self.assertEqual(self.store.user("alice")["public_key"], "new-key")
        self.store.disable("alice", False)
        self.assertFalse(self.store.user("alice")["disabled"])

    def test_history_order_and_retention(self):
        for index in range(1003):
            self.store.save_message("lobby", "alice", str(index))
        rows = self.store.history("lobby", 2000)
        self.assertEqual(len(rows), 1000)
        self.assertEqual(rows[0]["body"], "3")
        self.assertEqual(rows[-1]["body"], "1002")
        self.assertEqual(self.store.history("other"), [])

    def test_clear_history(self):
        self.store.save_message("lobby", "alice", "one")
        self.store.save_message("lobby", "alice", "two")
        self.store.save_message("code", "alice", "three")
        self.assertEqual(self.store.clear_history("lobby"), 2)
        self.assertEqual(self.store.history("lobby"), [])
        self.assertEqual(len(self.store.history("code")), 1)
        self.assertEqual(self.store.clear_history(), 1)
        self.assertEqual(self.store.history("code"), [])
        self.assertEqual(self.store.clear_history(), 0)
    
    def test_persistence_after_reopening(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "chat.sqlite3"
            first = Store(path)
            first.add_user("alice", "key")
            first.create_room("code")
            first.set_topic("code", "Python")
            first.save_message("code", "alice", "survives restart")
            first.close()
            second = Store(path)
            try:
                self.assertIsNotNone(second.user("alice"))
                self.assertEqual(second.room("code")["topic"], "Python")
                self.assertEqual(second.history("code")[0]["body"], "survives restart")
            finally:
                second.close()
