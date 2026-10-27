"""Errors shared by every layer. CLIs map them to exit codes in one place (EXIT_CODES)."""


class FleetworkError(Exception):
    """Base class; the message is shown to the user as is."""


class ConfigError(FleetworkError):
    """A config file (.fleet.toml, pack.toml, ledger header) is missing or malformed."""


class LintError(FleetworkError):
    """The ledger fails `ledger lint`; mutating commands refuse to run (LEDGER-DESIGN §6)."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__(f"ledger lint failed: {len(self.findings)} finding(s)")


class DelegationRefused(FleetworkError):
    """A non-owner actor tried something no delegation grants (LEDGER-DESIGN §5).

    `request` is the owner-facing text the commander relays instead of acting."""

    def __init__(self, actor, capability, request):
        self.actor, self.capability, self.request = actor, capability, request
        super().__init__(f"{actor} may not {capability}; ask the owner: {request}")


class VersionConflict(FleetworkError):
    """A compare-and-set on the history version failed: another writer moved it. Re-read and retry."""


class UnknownAdapter(FleetworkError):
    """A config names an adapter that is not registered."""


class NotImplementedYet(FleetworkError):
    """A planned piece of the kit that no work package has built yet.

    Raised by stubs so callers get a pointer to the owner of the work instead of a traceback."""

    def __init__(self, what, work_package, spec):
        self.what, self.work_package, self.spec = what, work_package, spec
        super().__init__(f"not implemented yet: {what} (work package {work_package} in docs/WORKPACKAGES.md; spec {spec})")


EXIT_CODES = {LintError: 4, DelegationRefused: 5, VersionConflict: 6, NotImplementedYet: 3}


def exit_code(err):
    for cls, code in EXIT_CODES.items():
        if isinstance(err, cls):
            return code
    return 1
