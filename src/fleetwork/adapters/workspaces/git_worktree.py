"""One git worktree and branch `<lane-prefix>/<lane>` per lane. `remove` only ever uses `git branch -d`."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("workspace", "git-worktree")
class GitWorktree:
    """Implements fleetwork.adapters.base.Workspace. Stub: WP-09."""

    def __init__(self, **config):
        self.config = config

    def create(self, lane, base):
        raise NotImplementedYet("workspace adapter git-worktree: create", "WP-09", "ROADMAP 'The kit'")

    def remove(self, lane):
        raise NotImplementedYet("workspace adapter git-worktree: remove", "WP-09", "ROADMAP 'The kit'")
