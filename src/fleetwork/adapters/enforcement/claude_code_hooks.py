"""PreToolUse hooks and settings for a Claude Code session: deny reads of forbid-read paths, writes to freeze
paths, `git push`, and trust-dialog answers. guard/lead_hook.sh is the existing hook to build from."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("enforcement", "claude-code-hooks")
class ClaudeCodeHooks:
    """Implements fleetwork.adapters.base.Enforcement. Stub: WP-10."""

    def __init__(self, **config):
        self.config = config

    def write(self, actor, guard, never, dest):
        raise NotImplementedYet("enforcement adapter claude-code-hooks: write", "WP-10", "LEDGER-DESIGN §5, §7")
