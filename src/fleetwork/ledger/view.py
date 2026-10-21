"""LEDGER.yaml: the read-only view regenerated after every write (LEDGER-DESIGN §4.6). Editing it changes
nothing; its first line says so."""
from fleetwork.errors import NotImplementedYet

FILENAME = "LEDGER.yaml"
BANNER = "# GENERATED from history.jsonl by `ledger` — do not edit; author changes with `ledger apply`."


def render(ledger):
    """The YAML text for a Ledger."""
    raise NotImplementedYet("view.render", "WP-01", "LEDGER-DESIGN §4.6")


def write(ledger_dir, ledger):
    raise NotImplementedYet("view.write", "WP-01", "LEDGER-DESIGN §4.6")
