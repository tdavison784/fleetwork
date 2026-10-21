"""Delegations (LEDGER-DESIGN §5): map an actor to its role and decide whether a capability is granted.

Capabilities: gates.resolve, items.add, items.drop, decide (and any added later, listed here). Owner actors
are never checked. `never` entries are refused for every non-owner role."""
from fleetwork.errors import NotImplementedYet

CAPABILITIES = ("gates.resolve", "items.add", "items.drop", "decide")


def role_of(header, actor):
    raise NotImplementedYet("delegations.role_of", "WP-07", "LEDGER-DESIGN §5")


def check(header, actor, capability, item=None, gate=None, why=None):
    """None if allowed; raises DelegationRefused with the owner-facing request otherwise."""
    raise NotImplementedYet("delegations.check", "WP-07", "LEDGER-DESIGN §5")
