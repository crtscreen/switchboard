import time
from .limits import Bucket
from .util import text
from . import rooms, history, social, moderation

class Chat:
    def __init__(self, store):
        self.store = store
        self.peers = {}
        self.connections = set()
        self.admin_commands = set()
        self.commands = {
            "help": (self.help, "/help - show commands"),
            "clear": (self.clear, "/clear - clear your terminal"),
            "who": (self.who, "/who - list connected members"),
            "q": (self.quit, "/q - disconnect"),
            "quit": (self.quit, "/quit - disconnect"),
        }

        rooms.install(self)
        history.install(self)
        social.install(self)
        moderation.install(self)

    def connect(self, peer):
        user = self.store.user(peer.name)
        if not user or user["disabled"]:
            raise ValueError("account unavailable.")
        if peer.name in self.peers:
            raise ValueError("this account is already connected!")
        if len(self.peers) >= 64:
            raise ValueError("The server is full, sorry! Try again later.")
        peer.bucket = Bucket()
        peer.last_active = time.monotonic()
        peer.authorized_key = self.store.credential(user)
        peer.room = "lobby"
        self.peers[peer.name] = peer
        peer.send("\x1b[1;36mSWITCHBOARD\x1b")
        peer.send(f"Hello {peer.name}! You are currently in #lobby.")
        peer.send(f"Topic: {self.store.room('lobby')['topic'] or '(not set)'}")
        peer.send("You're connected! Type /help for commands.")
        history.show(self, peer)
        self.broadcast(peer.room, f"* {peer.name} joined.")

    def disconnect(self, peer):
        if self.peers.get(peer.name) is peer:
            del self.peers[peer.name]
            self.broadcast(peer.room, f"* {peer.name} left.")

    def broadcast(self, room, message):
        for target in list(self.peers.values()):
            if target.room == room:
                target.send(message)

    def say(self, peer, message, action=False):
        record = self.store.save_message(peer.room, peer.name, message, action)
        self.broadcast(peer.room, history.render(record))

    def handle(self, peer, line):
        if not line.strip() or self.peers.get(peer.name) is not peer:
            return
        try:
            user = self.store.user(peer.name)
            if not user or user["disabled"]:
                peer.close("Account disabled.")
                return
            if line.strip() == "/q":
                self.quit(peer, "")
                return
            if not peer.bucket.allow():
                peer.close("Too many lines. Wait a bit, then reconnect.")
                return
            peer.last_active = time.monotonic()
            line = text(line)
            if line.startswith("/"):
                command, _, argument = line[1:].partition(" ")
                entry = self.commands.get(command.lower())
                if not entry:
                    raise ValueError("Unknown command. Type /help.")
                entry[0](peer, argument.strip())
            else:
                self.say(peer, line)
        except ValueError as exc:
            peer.send(f"! {exc}")

    def clear(self, peer, argument):
        peer.send("\x1b[2J\x1b[H")
        peer.send(f"SWITCHBOARD | #{peer.room} | /help")

    def tick(self):
        now = time.monotonic()
        for peer in list(self.peers.values()):
            user = self.store.user(peer.name)
            if not user or user["disabled"] or self.store.credential(user) != peer.authorized_key:
                peer.close("Account changed. Please reconnect.")
            elif now - peer.last_active >= 3600:
                peer.close("You were disconnect for being AFK.")

    def help(self, peer, argument):
        is_admin = bool(self.store.user(peer.name)["admin"])
        for command, (_, description) in self.commands.items():
            if is_admin or command not in self.admin_commands:
                peer.send(description)

    def who(self, peer, argument):
        peer.send("Online: " + ", ".join(
            f"{p.name}@{p.room}" for p in sorted(self.peers.values(), key=lambda p: p.name)
        ))

    def quit(self, peer, argument):
        peer.close("bye!")

    def shutdown(self):
        for peer in list(self.peers.values()):
            peer.close("SHUTTING DOWN SERVER")
        for connection in list(self.connections):
            connection.close()