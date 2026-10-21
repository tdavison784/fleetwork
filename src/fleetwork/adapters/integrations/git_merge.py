"""Merges a lane branch into the integration branch with the project's policy (`squash` or `no-ff`), after
checking the diff against ownership and frozen paths."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("integration", "git-merge")
class GitMerge:
    """Implements fleetwork.adapters.base.Integration. Stub: WP-10."""

    def __init__(self, **config):
        self.config = config

    def integrate(self, lane, workspace, policy):
        raise NotImplementedYet("integration adapter git-merge: integrate", "WP-10", "LEDGER-DESIGN §7")
