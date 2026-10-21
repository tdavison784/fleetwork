"""Claude Code accounts: headroom from the per-session statusline snapshots, usage from session metadata.

The guard's read_claude_windows() is the reference implementation (guard/fleet_guard.py)."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("provider", "claude-code")
class ClaudeCode:
    """Implements fleetwork.adapters.base.Provider. Stub: WP-06."""

    def __init__(self, **config):
        self.config = config

    def headroom(self):
        raise NotImplementedYet("provider adapter claude-code: headroom", "WP-06", "LEDGER-DESIGN §6.1")

    def usage(self, session_ids):
        raise NotImplementedYet("provider adapter claude-code: usage", "WP-06", "LEDGER-DESIGN §6.1")
