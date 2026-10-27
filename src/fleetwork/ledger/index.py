"""ledger.db: a SQLite index of the replayed state (stdlib sqlite3). A cache: `rebuild` recreates it from
history.jsonl at any time, and it is never committed or synced (LEDGER-DESIGN §4.6)."""
from fleetwork.errors import NotImplementedYet

FILENAME = "ledger.db"


def rebuild(ledger_dir):
    raise NotImplementedYet("index.rebuild", "WP-01", "LEDGER-DESIGN §4.6")


def current_version(ledger_dir):
    raise NotImplementedYet("index.current_version", "WP-01", "LEDGER-DESIGN §4.6")
