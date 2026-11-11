from .util import text

class Chat:
    def __init__(self, store):
        self.store = store

    def connect(self, peer):
        peer.send("SWITCHBOARD")
        peer.send("type a line or /quit to disconnect")

    def disconnect(self, peer):
        pass

    def handle(self, peer, line):
        if not line.strip():
            return
        try:
            line = text(line)
            if line == "/quit":
                peer.close("bye!")
            else:
                peer.send(f"{peer.name}: {line}")
        except ValueError as exc:
            peer.send(f"! {exc}")