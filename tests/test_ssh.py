"""Real SSH handshakes on ephemeral loopback ports, using temporary keys."""
import asyncio
import unittest
import asyncssh
from switchboard.chat import Chat
from switchboard.server import listen
from switchboard.store import Store


class SSHTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.key = asyncssh.generate_private_key("ssh-ed25519")
        self.host_key = asyncssh.generate_private_key("ssh-ed25519")
        self.store.add_user("alice", self.key.export_public_key().decode().strip(), True)
        self.chat = Chat(self.store)
        self.server = await listen(self.chat, "127.0.0.1", 0, self.host_key)
        self.addAsyncCleanup(self.stop_server)
        self.port = self.server.get_port()

    async def stop_server(self):
        self.server.close()
        await self.server.wait_closed()

    async def connect(self, key=None, username="alice"):
        conn = await asyncssh.connect(
            "127.0.0.1", self.port, username=username,
            client_keys=[key or self.key], agent_path=None,
            known_hosts=([self.host_key.convert_to_public()], [], []),
        )
        self.addAsyncCleanup(conn.wait_closed)
        self.addCleanup(conn.close)
        return conn

    async def read_until(self, process, needle):
        async with asyncio.timeout(3):
            output = ""
            while needle not in output:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    self.fail(f"EOF waiting for {needle!r}: {output!r}")
                output += chunk
            return output

    async def test_login_echo_quit(self):
        conn = await self.connect()
        proc = await conn.create_process(term_type="xterm")
        await self.read_until(proc, "SWITCHBOARD")
        proc.stdin.write("hello\n")
        await self.read_until(proc, "alice: hello")
        proc.stdin.write("/quit\n")
        await asyncio.wait_for(proc.wait_closed(), 3)

    async def test_wrong_key_and_disabled_account(self):
        with self.assertRaises(asyncssh.PermissionDenied):
            await self.connect(asyncssh.generate_private_key("ssh-ed25519"))
        self.store.disable("alice")
        with self.assertRaises(asyncssh.PermissionDenied):
            await self.connect()

    async def test_no_exec_sftp_or_forwarding(self):
        conn = await self.connect()
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.create_process("id")
        conn = await self.connect()
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.create_process(subsystem="sftp")
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.open_connection("127.0.0.1", 80)
        with self.assertRaises(asyncssh.ChannelListenError):
            await conn.create_server(lambda: None, "127.0.0.1", 0)

    async def test_requires_terminal(self):
        conn = await self.connect()
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.create_process()

    async def test_two_real_sessions(self):
        self.store.add_user("bob", self.key.export_public_key().decode().strip())
        alice = await self.connect()
        bob = await self.connect(username="bob")
        a = await alice.create_process(term_type="xterm")
        b = await bob.create_process(term_type="xterm")
        await self.read_until(b, "SWITCHBOARD")
        a.stdin.write("hello bob\n")
        await self.read_until(b, "alice: hello bob")
        bob.close()
        await bob.wait_closed()
        await self.read_until(a, "bob left")

    async def test_extra_channel_and_shutdown(self):
        conn = await self.connect()
        proc = await conn.create_process(term_type="xterm")
        await self.read_until(proc, "SWITCHBOARD")
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.create_process(term_type="xterm")
        self.chat.shutdown()
        await asyncio.wait_for(conn.wait_closed(), 3)
        self.assertFalse(self.chat.peers)

    async def test_partial_input_survives_incoming_message(self):
        self.store.add_user("bob", self.key.export_public_key().decode().strip())
        alice = await self.connect()
        bob = await self.connect(username="bob")
        a = await alice.create_process(term_type="xterm")
        b = await bob.create_process(term_type="xterm")
        await self.read_until(a, "SWITCHBOARD")
        await self.read_until(b, "SWITCHBOARD")
        a.stdin.write("half")
        await self.read_until(a, "half")
        b.stdin.write("incoming\n")
        await self.read_until(a, "bob: incoming")
        a.stdin.write(" typed\n")
        await self.read_until(b, "alice: half typed")

    async def test_revoked_key_cannot_open_late_session(self):
        conn = await self.connect()
        self.store.set_key("alice", "replacement")
        with self.assertRaises(asyncssh.ChannelOpenError):
            await conn.create_process(term_type="xterm")
