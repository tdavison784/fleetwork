"""Beads (`bd`) mirror. tools/ledger-to-beads.py is the working v1 implementation to port (WP-12); it runs
bd with metrics disabled and its Dolt root outside $HOME."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("mirror", "beads")
class Beads:
    """Implements fleetwork.adapters.base.Mirror. Stub: WP-12."""

    def __init__(self, **config):
        self.config = config

    def export(self, ledger, dest):
        raise NotImplementedYet("mirror adapter beads: export", "WP-12", "LEDGER-DESIGN §6")
