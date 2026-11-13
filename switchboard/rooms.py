from .util import name, text
from .history import show

def install(chat):
    def rooms(peer, argument):
        for room in chat.store.rooms():
            count = sum(p.room == room["name"] for p in chat.peers.values())
            peer.send(f"#{room['name']} ({count} online) {room['topic']}")

    def join(peer, argument):
        room = name(argument.removeprefix("#"))
        if room == peer.room:
            peer.send(f"Already in #{room}.")
            return
        chat.store.create_room(room)
        old = peer.room
        peer.room = room
        chat.broadcast(old, f"* {peer.name} left for #{room}.")
        chat.broadcast(room, f"* {peer.name} joined #{room}.")
        peer.send(f"Topic: {chat.store.room(room)['topic'] or '(not set)'}")
        show(chat, peer)

    def topic(peer, argument):
        if argument:
            if not chat.store.user(peer.name)["admin"]:
                raise ValueError("Only admins can set room topics.")
            chat.store.set_topic(peer.room, text(argument, 160))
            chat.broadcast(peer.room, f"* Topic: {argument}")
        else:
            peer.send(f"Topic: {chat.store.room(peer.room)['topic'] or not '(not set)'}")

    chat.commands.update({
        "rooms": (rooms, "/rooms - list public rooms"),
        "join": (join, "/join room - join or create a public room"),
        "topic": (topic, "/topic [text] - read topic"),
    })