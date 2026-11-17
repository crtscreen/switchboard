from .util import name, text

def install(chat):
    def require_admin(peer):
        if not chat.store.user(peer.name)["admin"]:
            raise ValueError("Admin command.")

    def kick(peer, argument):
        require_admin(peer)
        target = chat.peers.get(name(argument))
        if not target:
            raise ValueError("That user is offline.")
        if chat.store.user(target.name)["admin"]:
            raise ValueError("Manage admin accounts through the local CLI.")
        target.close(f"You were kicked.")
        peer.send("User disconnected.")

    def ban(peer, argument):
        require_admin(peer)
        username = name(argument)
        user = chat.store.user(username)
        if not user:
            raise ValueError("Unknown user.")
        if user["admin"]:
            raise ValueError("Manage admin accounts through the local CLI.")
        chat.store.disable(username)
        if username in chat.peers:
            chat.peers[username].close("Account banned.")
        peer.send(f"{username} was banned.")

    def unban(peer, argument):
        require_admin(peer)
        username = name(argument)
        chat.store.disable(username, False)
        peer.send(f"Unbanned {username}")

    def announce(peer, argument):
        require_admin(peer)
        message = text(argument)
        for target in list(chat.peers.values()):
            target.send(f"[ANNOUNCEMENT by {peer.name}] {message}")

    chat.commands.update({
        "kick": (kick, "/kick user - ADMIN ONLY: disconnect a user"),
        "ban": (ban, "/ban user - ADMIN ONLY: disable a user's account"),
        "unban": (unban, "/unban user - ADMIN ONLY: re-enable an account"),
        "announce": (announce, "/announce text - ADMIN ONLY: send a message to every room"),
    })

    chat.admin_commands.update({"kick", "ban", "unban", "announce"})