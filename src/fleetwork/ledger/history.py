"""history.jsonl: the ledger's truth (LEDGER-DESIGN §4.6). Append-only; one HistoryEntry per mutation."""
from fleetwork.errors import NotImplementedYet

FILENAME = "history.jsonl"


def read(ledger_dir):
    """Every entry, in order, as HistoryEntry objects."""
    raise NotImplementedYet("history.read", "WP-01", "LEDGER-DESIGN §4.6")


def append(ledger_dir, entry, expected_v):
    """Append `entry` iff the log's last version is `expected_v`; else raise VersionConflict."""
    raise NotImplementedYet("history.append", "WP-01", "LEDGER-DESIGN §4.6")


def verify(ledger_dir):
    """Findings for gaps or repeats in `v` (and a broken hash chain, if the format adds one)."""
    raise NotImplementedYet("history.verify", "WP-01", "LEDGER-DESIGN §4.6, §5")


def replay(entries):
    """The Ledger state the entries produce (pure; the index and the view are both built from this)."""
    raise NotImplementedYet("history.replay", "WP-01", "LEDGER-DESIGN §4.6")
