"""A provider with no window and no metering: a human, or an unmetered model (LEDGER-DESIGN §4.1)."""
from fleetwork.adapters import register
from fleetwork.adapters.base import Usage


@register("provider", "none")
class NoProvider:
    """Implements fleetwork.adapters.base.Provider."""

    def __init__(self, **config):
        self.config = config

    def headroom(self):
        return None

    def usage(self, session_ids):
        return Usage(tokens=0)
