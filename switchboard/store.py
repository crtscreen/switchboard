import sqlite3

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                room TEXT NOT NULL,
                sender TEXT NOT NULL,
                body TEXT NOT NULL,
                action INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
            );
            CREATE INDEX IF NOT EXISTS messages_room_id ON messages(room,id);
            CREATE TABLE IF NOT EXISTS rooms (
                name TEXT PRIMARY KEY,
                topic TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO rooms(name) VALUES ('lobby');
            CREATE TABLE IF NOT EXISTS users (
                name TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                admin INTEGER NOT NULL DEFAULT 0,
                disabled INTEGER NOT NULL DEFAULT 0
            );
        """)

        # older database accs w no password
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(users)")}
        if "password_hash" not in columns:
            with self.db:
                self.db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    def user(self, username):
        return self.db.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()

    def add_user(self, username, public_key, admin=False, password_hash=None):
        if admin and password_hash:
            raise ValueError("Admin accounts use SSH keys only.")
        with self.db:
            self.db.execute(
                "INSERT INTO users(name,public_key,admin,password_hash) VALUES(?,?,?,?)",
                (username, public_key, int(admin), password_hash))

    def credential(self, user):
        return f"{user['public_key']}|{user['password_hash'] or ''}"

    def set_password(self, username, password_hash):
        user = self.user(username)
        if not user:
            raise ValueError("Unknown user.")
        if user["admin"]:
            raise ValueError("Admin accounts use SSH keys only.")
        with self.db:
            self.db.execute("UPDATE users SET password_hash=? WHERE name=?",
                            (password_hash, username))

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

    def rooms(self):
        return self.db.execute("SELECT * FROM rooms ORDER BY name").fetchall()

    def room(self, room):
        return self.db.execute("SELECT * FROM rooms WHERE name=?", (room,)).fetchone()

    def create_room(self, room):
        if self.room(room):
            return
        if len(self.rooms()) >= 32:
            raise ValueError("This server already has 32 rooms.")
        with self.db:
            self.db.execute("INSERT INTO rooms(name) VALUES(?)", (room,))

    def set_topic(self, room, topic):
        with self.db:
            self.db.execute("UPDATE rooms SET topic=? WHERE name=?", (topic, room))

    def save_message(self, room, sender, body, action=False):
        with self.db:
            self.db.execute(
                "INSERT INTO messages(room,sender,body,action) VALUES(?,?,?,?)",
                (room, sender, body, int(action)),
            )
            self.db.execute("""
                DELETE FROM messages WHERE room=? AND id NOT IN
                (SELECT id FROM messages WHERE room=? ORDER BY id DESC LIMIT 1000)
            """, (room, room))
        return self.history(room, 1)[0]

    def history(self, room, count=20):
        rows = self.db.execute(
            "SELECT * FROM messages WHERE room=? ORDER BY id DESC LIMIT ?",
            (room, count),
        ).fetchall()
        return list(reversed(rows))

    def clear_history(self, room=None):
        with self.db:
            if room is None:
                cursor = self.db.execute("DELETE FROM messages")
            else:
                cursor = self.db.execute("DELETE FROM messages WHERE room=?", (room,))
        return cursor.rowcount