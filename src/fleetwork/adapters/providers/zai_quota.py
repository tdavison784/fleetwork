"""Z.AI quota endpoint. The key is read from a file named in config at call time and never printed or logged.

The guard's Z.AI reader is the reference implementation (guard/fleet_guard.py)."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("provider", "zai-quota")
class ZaiQuota:
    """Implements fleetwork.adapters.base.Provider. Stub: WP-06."""

    def __init__(self, **config):
        self.config = config

    def headroom(self):
        raise NotImplementedYet("provider adapter zai-quota: headroom", "WP-06", "LEDGER-DESIGN §6.1")

    def usage(self, session_ids):
        raise NotImplementedYet("provider adapter zai-quota: usage", "WP-06", "LEDGER-DESIGN §6.1")
