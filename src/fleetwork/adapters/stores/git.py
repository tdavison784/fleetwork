"""The `dir` store as its own git repository: commits history.jsonl and the view (never ledger.db) at the configured cadence."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("store", "git")
class GitStore:
    """Implements fleetwork.adapters.base.Store. Stub: WP-12."""

    def __init__(self, **config):
        self.config = config

    def open(self, ledger):
        raise NotImplementedYet("store adapter git: open", "WP-12", "LEDGER-DESIGN §4.6")

    def sync(self, path):
        raise NotImplementedYet("store adapter git: sync", "WP-12", "LEDGER-DESIGN §4.6")
