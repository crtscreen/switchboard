import asyncio
import logging
import signal
import sqlite3
import asyncssh
from .chat import Chat

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
    def __init__(self, chat):
        self.chat = chat
        self.connection = None
        self.session_used = False
        self.authorized_key = None

    def connection_made(self, connection):
        self.connection = connection
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
        valid = bool(user and not user["disabled"] and
                     key == asyncssh.import_public_key(user["public_key"]))
        if valid:
            self.authorized_key = user["public_key"]
        return valid

    def session_requested(self):
        user = self.chat.store.user(self.connection.get_extra_info("username"))
        if (self.session_used or not user or user["disabled"] or
                user["public_key"] != self.authorized_key):
            return False
        self.session_used = True
        return Session(self.chat)

async def listen(chat, host, port, host_key):
    return await asyncssh.create_server(
        lambda: Server(chat), host, port,
        server_host_keys=[host_key],
        password_auth=False, kbdint_auth=False,
        agent_forwarding=False, x11_forwarding=False,
        line_editor=True, line_echo=False, line_history=50,
        max_line_length=500, login_timeout=30,
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