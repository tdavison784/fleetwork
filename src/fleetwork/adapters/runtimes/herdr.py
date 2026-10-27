"""Herdr panes and agents through the `herdr` CLI. Never answers a trust or permission dialog: a `blocked`
state is reported to the caller, not resolved."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("runtime", "herdr")
class Herdr:
    """Implements fleetwork.adapters.base.Runtime. Stub: WP-09."""

    def __init__(self, **config):
        self.config = config

    def start(self, name, profile, cwd, prompt):
        raise NotImplementedYet("runtime adapter herdr: start", "WP-09", "ROADMAP 'The kit'")

    def state(self, name):
        raise NotImplementedYet("runtime adapter herdr: state", "WP-09", "ROADMAP 'The kit'")

    def send(self, name, text):
        raise NotImplementedYet("runtime adapter herdr: send", "WP-09", "ROADMAP 'The kit'")

    def stop(self, name):
        raise NotImplementedYet("runtime adapter herdr: stop", "WP-09", "ROADMAP 'The kit'")
