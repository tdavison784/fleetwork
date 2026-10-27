"""A non-interactive agent CLI run as a background process (e.g. `claude -p`), for CI and machines without a
multiplexer. Long runs go under nohup, never as a child of a watcher."""
from fleetwork.adapters import register
from fleetwork.errors import NotImplementedYet


@register("runtime", "headless")
class Headless:
    """Implements fleetwork.adapters.base.Runtime. Stub: WP-09."""

    def __init__(self, **config):
        self.config = config

    def start(self, name, profile, cwd, prompt):
        raise NotImplementedYet("runtime adapter headless: start", "WP-09", "ROADMAP 'The kit'")

    def state(self, name):
        raise NotImplementedYet("runtime adapter headless: state", "WP-09", "ROADMAP 'The kit'")

    def send(self, name, text):
        raise NotImplementedYet("runtime adapter headless: send", "WP-09", "ROADMAP 'The kit'")

    def stop(self, name):
        raise NotImplementedYet("runtime adapter headless: stop", "WP-09", "ROADMAP 'The kit'")
