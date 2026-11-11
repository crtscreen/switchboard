import argparse
import asyncio
import logging
import os
from pathlib import Path
import sqlite3
import asyncssh
from .store import Store
from .util import name


def public_key(path):
    return asyncssh.read_public_key(path).export_public_key().decode().strip()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Switchboard SSH chat")
    parser.add_argument("--data", default="data", help="Private server data directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create data directory, database and host key")
    add = sub.add_parser("add-user", help="Register a public key")
    add.add_argument("name", type=name)
    add.add_argument("--key", required=True)
    add.add_argument("--admin", action="store_true")
    rotate = sub.add_parser("set-key", help="Replace a user's public key")
    rotate.add_argument("name", type=name)
    rotate.add_argument("--key", required=True)
    for command in ("disable", "enable"):
        p = sub.add_parser(command)
        p.add_argument("name", type=name)
    sub.add_parser("users")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=2222)
    args = parser.parse_args()
    data = Path(args.data).resolve()
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(data / "chat.sqlite3")
    try:
        if args.command == "serve":
            from .server import serve
            logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
            asyncio.run(serve(store, data, args.host, args.port))
        elif args.command == "init":
            keypath = data / "host.key"
            if not keypath.exists():
                key = asyncssh.generate_private_key("ssh-ed25519")
                with keypath.open("xb") as out:
                    out.write(key.export_private_key())
            key = asyncssh.read_private_key(keypath)
            print("Host fingerprint:", key.get_fingerprint())
        elif args.command == "add-user":
            store.add_user(args.name, public_key(args.key), args.admin)
            print("Registered", args.name)
        elif args.command == "set-key":
            store.set_key(args.name, public_key(args.key))
            print("Key replaced; existing sessions must reconnect.")
        elif args.command in ("disable", "enable"):
            store.disable(args.name, args.command == "disable")
            print("Account updated.")
        elif args.command == "users":
            for user in store.users():
                print(user["name"], "admin" if user["admin"] else "member",
                      "disabled" if user["disabled"] else "enabled")
    except (ValueError, OSError, sqlite3.Error, asyncssh.Error) as exc:
        parser.exit(1, f"Error: {exc}\n")
    finally:
        store.close()