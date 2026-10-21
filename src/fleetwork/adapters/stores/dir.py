"""The default store: a plain directory per ledger, `<root>/<ledger>/` (LEDGER-DESIGN §4.6). No backup."""
from pathlib import Path

from fleetwork.adapters import register


@register("store", "dir")
class DirStore:
    """Implements fleetwork.adapters.base.Store."""

    def __init__(self, path, **config):
        self.root = Path(path).expanduser()
        self.config = config

    def open(self, ledger):
        d = self.root / ledger
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sync(self, path):
        pass
