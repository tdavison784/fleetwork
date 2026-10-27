"""SQLite cache rebuilt deterministically from the authoritative history log."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing

from fleetwork.ledger import history
from fleetwork.ledger.model import Ledger

FILENAME = "ledger.db"


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rebuild(ledger_dir):
    """Rebuild the cache atomically and return the replayed ledger.

    Invalid history leaves the old cache untouched.
    """
    directory = Path(ledger_dir)
    with history.transaction(directory) as tx:
        return _rebuild(directory, tx.read())


def _rebuild(directory, entries):
    ledger = history.replay(entries)
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ledger-db-", dir=directory)
    os.close(fd)
    try:
        with closing(sqlite3.connect(tmp)) as db, db:
            db.execute("CREATE TABLE metadata (version INTEGER NOT NULL)")
            db.execute("CREATE TABLE state (data TEXT NOT NULL)")
            db.execute("CREATE TABLE history (version INTEGER PRIMARY KEY, data TEXT NOT NULL)")
            db.execute("INSERT INTO metadata VALUES (?)", (entries[-1].v if entries else 0,))
            db.execute("INSERT INTO state VALUES (?)", (_json(ledger.to_dict()),))
            db.executemany("INSERT INTO history VALUES (?, ?)",
                           [(entry.v, _json(entry.to_dict())) for entry in entries])
        os.replace(tmp, directory / FILENAME)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return ledger


def current_version(ledger_dir):
    """Return the cached version, or None when the cache is absent or invalid."""
    path = Path(ledger_dir) / FILENAME
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)) as db:
            row = db.execute("SELECT version FROM metadata").fetchone()
            return row[0] if row else None
    except sqlite3.DatabaseError:
        return None


def load(ledger_dir):
    """Read a valid cache as a Ledger; callers must verify its freshness."""
    path = Path(ledger_dir) / FILENAME
    with closing(sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)) as db:
        row = db.execute("SELECT data FROM state").fetchone()
        if row is None:
            raise ValueError("index has no ledger state")
        return Ledger.from_dict(json.loads(row[0]))
