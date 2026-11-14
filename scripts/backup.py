import argparse
import os
from pathlib import Path
import shutil
import sqlite3

def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not (source / "host.key").is_file():
        raise ValueError("Source has no host.key")
    os.umask(0o077)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    original = sqlite3.connect((source / "chat.sqlitre3").as_uri() + "?mode=ro", uri=True)
    snapshot = sqlite3.connect(destination / "chat.sqlite3")
    try:
        original.backup(snapshot)
        shutil.copyfile(source / "host.key", destination / "host.key")
    finally:
        snapshot.close()
        original.close()
    print(f"Backup complete: {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        backup(args.source, args.destination)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Backup failed: {exc}\n")