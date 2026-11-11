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