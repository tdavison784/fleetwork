"""A ledger directory and the operations every command shares: open, load state, write one change.

Layout of a ledger directory (LEDGER-DESIGN §4.6; packs/core/templates/ledger creates the rest):
  history.jsonl   the truth             ledger.db   the index (cache)     LEDGER.yaml   the view
  briefs/ runs/ formulas/ profiles/ status/   files items point at, relative to the directory
"""
from pathlib import Path

from fleetwork import config
from fleetwork.errors import NotImplementedYet


def locate(ledger_dir=None):
    """The ledger directory: an explicit path, else the one named by the nearest .fleet.toml."""
    if ledger_dir:
        return Path(ledger_dir)
    return config.load().ledger_dir()


def load(ledger_dir):
    """The current Ledger (from the index, rebuilt from the log if missing or stale)."""
    raise NotImplementedYet("store.load", "WP-01", "LEDGER-DESIGN §4.6")


def commit(ledger_dir, actor, op, item_id, diff, why=None):
    """The single write path: lint, delegation check, CAS append to history, index update, view rewrite."""
    raise NotImplementedYet("store.commit", "WP-01", "LEDGER-DESIGN §4.6, §6")


def apply(ledger_dir, batch, actor):
    """Ingest a hand-authored YAML batch (items and/or header changes) as history entries."""
    raise NotImplementedYet("store.apply", "WP-01", "LEDGER-DESIGN §4.6")
