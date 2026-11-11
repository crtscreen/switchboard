import sqlite3

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                name TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                admin INTEGER NOT NULL DEFAULT 0,
                disabled INTEGER NOT NULL DEFAULT 0
            );
        """)

    def user(self, username):
        return self.db.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()

    def add_user(self, username, public_key, admin=False):
        with self.db:
            self.db.execute("INSERT INTO users(name,public_key,admin) VALUES(?,?,?)",
                            (username, public_key, int(admin)))
    def users(self):
        return self.db.execute("SELECT * FROM users ORDER BY name").fetchall()

    def set_key(self, username, public_key):
        if not self.user(username):
            raise ValueError("unknown user.")
        with self.db:
            self.db.execute("UPDATE users SET public_key=? WHERE name=?",
                            (public_key, username))

    def disable(self, username, disabled=True):
        if not self.user(username):
            raise ValueError("unknown user.")
        with self.db:
            self.db.execute("UPDATE users SET disabled=? WHERE name=?",
                            (int(disabled), username))

    def close(self):
        self.db.close()