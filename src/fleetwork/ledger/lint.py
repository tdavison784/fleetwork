"""`ledger lint` (LEDGER-DESIGN §6). Pure: takes a Ledger (and optionally its directory, for path checks)
and returns findings; it never raises on a bad ledger."""
from dataclasses import dataclass

from fleetwork.errors import NotImplementedYet


@dataclass
class Finding:
    item: str          # item id, or "header"
    rule: str          # short kebab-case rule name, e.g. "blocked-without-gate"
    message: str
    severity: str = "error"   # error | warning


def lint(ledger, ledger_dir=None):
    """All findings for the ledger; [] means clean."""
    raise NotImplementedYet("lint.lint", "WP-02", "LEDGER-DESIGN §6 (ledger lint)")
