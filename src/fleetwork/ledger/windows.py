"""Read-only history queries: the derived window log, estimates, diff and blame (LEDGER-DESIGN §6).

Window log = event sources (§4.5) joined with history.jsonl. Event names are normalised here, not in the
adapters: the guard writes HANDOFF/HANDBACK/RESUME/PAUSE/CTX without a `provider` field."""
from fleetwork.errors import NotImplementedYet


def windows(ledger_dir, events):
    raise NotImplementedYet("windows.windows", "WP-04", "LEDGER-DESIGN §6 (ledger windows)")


def estimate(ledger_dir, kind, provider=None):
    raise NotImplementedYet("windows.estimate", "WP-04", "LEDGER-DESIGN §6 (ledger estimate)")


def diff(ledger_dir, v1, v2):
    raise NotImplementedYet("windows.diff", "WP-04", "LEDGER-DESIGN §6 (ledger diff)")


def blame(ledger_dir, item_id):
    raise NotImplementedYet("windows.blame", "WP-04", "LEDGER-DESIGN §6 (ledger blame)")
