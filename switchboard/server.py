import asyncio
import logging
import signal
import sqlite3
import asyncssh
from .chat import Chat
from .limits import Failures
from .passwords import hash_password, verify_password
from .util import name as valid_name, password as valid_password

MAX_ACCOUNTS = 500

log = logging.getLogger(__name__)

class Session(asyncssh.SSHServerSession):
    def __init__(self, chat):
        self.chat = chat
        self.channel = None
        self.name = ""
        self.pty = False
        self.active = False
        self.buffer = ""

    def connection_made(self, channel):
        self.channel = channel
        channel.set_write_buffer_limits(high=65536, low=16384)
        self.name = channel.get_extra_info("username")

    def pty_requested(self, term_type, term_size, term_modes):
        self.pty = term_type in {
            "xterm", "xterm-256color", 
            "screen", "screen-256color",
            "tmux", "tmux-256color", 
            "vt100", "ansi", "linux",
            "xterm-kitty", "xterm-ghostty",
        }
        return self.pty

    def shell_requested(self):
        return self.pty

    def session_started(self):
        self.active = True
        try:
            self.chat.connect(self)
        except ValueError as exc:
            self.close(str(exc))
        except sqlite3.Error:
            log.exception("Database failure during session startup.")
            self.close("Database unavailable, please reconnect later.")

    def send(self, message):
        if self.active:
            self.channel.write(message + "\n")

    def close(self, message="Disconnected."):
        if self.active:
            self.send(message)
            self.active = False
            self.chat.disconnect(self)
        if self.channel:
            self.channel.close()

    def pause_writing(self):
        self.active = False
        self.chat.disconnect(self)
        self.channel.abort()

    def data_received(self, data, datatype):
        if datatype is not None or not self.active:
            return
        self.buffer += data
        while "\n" in self.buffer and self.active:
            line, self.buffer = self.buffer.split("\n", 1)
            try:
                self.chat.handle(self, line)
            except sqlite3.Error:
                log.exception("Database failure while handling a chat line.")
                self.close("Database unavailable, please reconnect later.")
        if len(self.buffer) > 500:
            self.close("input too long.")

    def eof_received(self):
        self.close("bye!")
        return False

    def connection_lost(self, exc):
        if self.active:
            self.active = False
            self.chat.disconnect(self)


class Server(asyncssh.SSHServer):
    def __init__(self, chat, failures):
        self.chat = chat
        self.failures = failures
        self.connection = None
        self.source = None
        self.registering = False
        self.session_used = False
        self.authorized_key = None

    def connection_made(self, connection):
        self.connection = connection
        peer = connection.get_extra_info("peername")
        self.source = peer[0] if peer else None
        if len(self.chat.connections) >= 128:
            connection.abort()
        else:
            self.chat.connections.add(connection)

    def connection_lost(self, exc):
        self.chat.connections.discard(self.connection)

    def begin_auth(self, username):
        return True

    def public_key_auth_supported(self):
        return True

    def validate_public_key(self, username, key):
        user = self.chat.store.user(username)
        # users with password have empty public key
        valid = bool(user and user["public_key"] and not user["disabled"] and
                     key == asyncssh.import_public_key(user["public_key"]))
        if valid:
            self.authorized_key = self.chat.store.credential(user)
        return valid

    def kbdint_auth_supported(self):
        return True

    def password_challenge(self, username, note=""):
        if self.registering:
            instructions = (note + " " if note else "") + (
                f"Creating account '{username}'. Choose a password that's 8-128 characters.")
            return ("Create account", instructions, "",
                    [("New password: ", False), ("Repeat password: ", False)])
        return ("", note, "", [("Password: ", False)])

    def get_kbdint_challenge(self, username, lang, submethods):
        self.registering = False
        if self.failures.blocked(self.source):
            return False
        user = self.chat.store.user(username)
        if user is None:
            try:
                valid_name(username)
            except ValueError:
                return False
            if len(self.chat.store.users()) >= MAX_ACCOUNTS:
                return False
            self.registering = True
        elif user["disabled"] or user["admin"] or not user["password_hash"]:
            return False
        return self.password_challenge(username)

    async def validate_kbdint_response(self, username, responses):
        if self.failures.blocked(self.source) or len(responses) != (2 if self.registering else 1):
            return False
        store = self.chat.store
        if self.registering:
            try:
                if responses[0] != responses[1]:
                    raise ValueError("The passwords did not match.")
                valid_password(responses[0])
            except ValueError as exc:
                self.failures.add(self.source)
                return self.password_challenge(username, f"{exc} Try again.")
            stored = await asyncio.to_thread(hash_password, responses[0])
            try:
                store.add_user(username, "", password_hash=stored)
            except sqlite3.IntegrityError:
                return False
            self.failures.add(self.source)
            self.registering = False
            self.authorized_key = store.credential(store.user(username))
            return True
        user = store.user(username)
        valid = bool(user and not user["disabled"] and not user["admin"] and
                     await asyncio.to_thread(verify_password, responses[0],
                                             user["password_hash"]))
        if not valid:
            self.failures.add(self.source)
            return False
        self.authorized_key = store.credential(user)
        return True

    def session_requested(self):
        user = self.chat.store.user(self.connection.get_extra_info("username"))
        if (self.session_used or not user or user["disabled"] or
                self.chat.store.credential(user) != self.authorized_key):
            return False
        self.session_used = True
        return Session(self.chat)

async def listen(chat, host, port, host_key, failures=None):
    failures = failures or Failures()
    return await asyncssh.create_server(
        lambda: Server(chat, failures), host, port,
        server_host_keys=[host_key],
        password_auth=False, kbdint_auth=True,
        agent_forwarding=False, x11_forwarding=False,
        line_editor=True, line_echo=False, line_history=50,
        max_line_length=500, login_timeout=60,
        keepalive_interval=30, keepalive_count_max=3,
        encoding="utf-8", errors="replace",
    )

async def serve(store, data, host, port):
    keypath = data / "host.key"
    if not keypath.exists():
        raise ValueError("host key not found (run init)")
    chat = Chat(store)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    server = await listen(chat, host, port, asyncssh.read_private_key(keypath))
    log.info("switchboard is listening on %s:%s", host, port)
    async def maintenance():
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=10)
            except TimeoutError:
                try:
                    chat.tick()
                except sqlite3.Error:
                    log.exception("Database failure during maintenance.")
                    stop.set()
    task = asyncio.create_task(maintenance())
    try:
        await stop.wait()
    finally:
        server.close()
        connections = list(chat.connections)
        chat.shutdown()
        await asyncio.gather(*(conn.wait_closed() for conn in connections))
        await server.wait_closed()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)