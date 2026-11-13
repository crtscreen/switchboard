from .util import name, text

def install(chat):
    def private_message(peer, argument):
        recipient, separator, body = argument.partition(" ")
        if not separator:
            raise ValueError("Usage: /msg username message")
        recipient = name(recipient)
        body = text(body)
        target = chat.peers.get(recipient)
        if target is None:
            raise ValueError("That user is offline, so your message wasn't delivered.")
        target.send(f"[DM from {peer.name}] {body}")
        if target is not peer:
            peer.send(f"[DM to {recipient}] {body}")

    def action(peer, argument):
        chat.say(peer, text(argument), action=True)

    chat.commands.update({
        "msg": (private_message, "/msg user message - send a private message to another online user"),
        "me": (action, "/me action - describe an action"),
    })