"""Gate evaluation (LEDGER-DESIGN §4.2, §6). Built in: `human` (closes only by resolve), `item`, `timer`,
`window` (asks the provider adapter for headroom). Any other type goes to the gate adapter whose `types`
lists it (fleetwork/adapters/gates/)."""
from fleetwork.errors import NotImplementedYet


def check(ledger, providers, gate_adapters, dry_run=False):
    """Gates that are now satisfied, as (item_id, gate_index) pairs; closes them unless dry_run."""
    raise NotImplementedYet("gates.check", "WP-07", "LEDGER-DESIGN §6 (ledger gates check)")


def resolve(ledger_dir, item_id, index, actor, why):
    raise NotImplementedYet("gates.resolve", "WP-07", "LEDGER-DESIGN §5, §6")
