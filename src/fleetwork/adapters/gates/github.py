"""`pr` and `ci` gates evaluated through the `gh` CLI."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("gate", "github")
class GitHubGates:
    """Implements fleetwork.adapters.base.GateEvaluator. Stub: WP-12."""

    types = ("pr", "ci")

    def __init__(self, **config):
        self.config = config

    def check(self, gate, ledger):
        raise NotImplementedYet("gate adapter github: check", "WP-12", "LEDGER-DESIGN §4.2, §6")
