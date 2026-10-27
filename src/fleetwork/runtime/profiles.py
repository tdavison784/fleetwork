"""Agent profiles: WHO does a lane's work, reusable across lanes, ledgers and projects (lane design, WP-08).

A lane is the work (a ledger item with a brief, a workspace, a contract and a status file); a profile is the
worker the runtime starts for it: runtime, model, fallback, permission mode, environment, `never` list,
hooks, context-checkpoint threshold. Several agents may occupy one lane over its life (a fallback provider
during a usage window, a fresh session after a context reset); continuity lives in the lane, never the agent.

Profiles live in <ledger>/profiles/<name>.yaml (seeded from packs). Keys are documented in
packs/core/templates/profiles/README.md. Item field `run.profile` names the profile a lane runs under.
"""
from dataclasses import dataclass, field

from fleetwork.errors import NotImplementedYet


@dataclass
class Profile:
    name: str
    runtime: str                                   # runtime adapter name
    model: str = None                              # opaque string
    provider: str = None                           # a provider declared in the ledger header
    fallback: dict = None                          # {provider, model, when}
    permission_mode: str = None
    env: dict = field(default_factory=dict)
    never: list = field(default_factory=list)
    hooks: list = field(default_factory=list)
    context_checkpoint: int = None                 # percent
    read_only: bool = False
    extra: dict = field(default_factory=dict)


def load(ledger_dir, name):
    raise NotImplementedYet("profiles.load", "WP-08", "lane design (docs/WORKPACKAGES.md WP-08)")
