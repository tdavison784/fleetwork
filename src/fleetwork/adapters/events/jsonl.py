"""Events from one or more JSON-lines files (LEDGER-DESIGN §4.5). Lines that are not JSON objects, or lack
`t` or `event`, are skipped; `provider` defaults to None. Extra fields are kept verbatim."""
import json
from pathlib import Path

from fleetwork.adapters import register


@register("events", "jsonl")
class JsonlEvents:
    """Implements fleetwork.adapters.base.EventSource."""

    def __init__(self, paths, **config):
        self.paths = [Path(p).expanduser() for p in ([paths] if isinstance(paths, str) else paths)]
        self.config = config

    def read(self):
        for p in self.paths:
            if not p.exists():
                continue
            with p.open() as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict) and "t" in ev and "event" in ev:
                        ev.setdefault("provider", None)
                        yield ev
