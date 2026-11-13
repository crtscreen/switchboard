def render(message):
    timestamp = message["created"]
    sender = message["sender"]
    body = message["body"]
    content = f"* {sender} {body}" if message["action"] else f"{sender}: {body}"
    return f"[{timestamp} UTC] {content}"

def show(chat, peer, count=20):
    peer.send(f"--- #{peer.room}: recent history ---")
    for message in chat.store.history(peer.room, count):
        peer.send(render(message))
    peer.send("--- live chat ---")

def install(chat):
    def history(peer, argument):
        try:
            count = int(argument or "20")
        except ValueError:
            raise ValueError("Usage: /history [1-100]") from None
        if not 1 <= count <= 100:
            raise ValueError("Choose a history count from 1 to 100.")
        show(chat, peer, count)

    chat.commands["history"] = (history, "/history [count] - read 1-100 recent room messages")