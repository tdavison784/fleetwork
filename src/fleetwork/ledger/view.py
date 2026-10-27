"""LEDGER.yaml: a generated, read-only view of the ledger history."""
import os
from pathlib import Path
import tempfile

import yaml

FILENAME = "LEDGER.yaml"
BANNER = "# GENERATED from history.jsonl by `ledger` — do not edit; author changes with `ledger apply`."


def render(ledger):
    """Return deterministic YAML for a Ledger, including the read-only banner."""
    return BANNER + "\n" + yaml.safe_dump(ledger.to_dict(), allow_unicode=True, sort_keys=True)


def write(ledger_dir, ledger):
    """Atomically replace the view with the rendered ledger."""
    directory = Path(ledger_dir)
    directory.mkdir(parents=True, exist_ok=True)
    content = render(ledger)
    fd, tmp = tempfile.mkstemp(prefix=".ledger-view-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        os.replace(tmp, directory / FILENAME)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
