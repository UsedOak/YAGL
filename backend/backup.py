"""Consistent online SQLite backup: python -m backend.backup /tmp/yagl-backup.sqlite3"""
import sqlite3
import sys
from pathlib import Path
from .db import DB_PATH


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m backend.backup /tmp/yagl-backup.sqlite3")
    output = Path(sys.argv[1])
    if output.resolve() == DB_PATH.resolve():
        raise SystemExit("Destination cannot be the live database")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    destination = sqlite3.connect(output)
    try:
        source.backup(destination)
        print(f"Backup created: {output}")
    finally:
        destination.close()
        source.close()


if __name__ == "__main__":
    main()
