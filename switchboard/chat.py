from .util import text
from . import rooms, history, social, moderation

class Chat:
    def __init__(self, store):
        self.store = store
        self.peers = {}
        self.commands = {
            "help": (self.help, "/help - show commands"),
            "who": (self.who, "/who - list connected members"),
            "q": (self.quit, "/q - disconnect"),
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
        peer.room = "lobby"
        self.peers[peer.name] = peer
        peer.send("SWITCHBOARD")
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

    def help(self, peer, argument):
        for _, description in self.commands.values():
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