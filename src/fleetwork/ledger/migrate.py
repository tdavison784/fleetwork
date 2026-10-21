"""v1 -> v2 (LEDGER-DESIGN §9 step 2). Input: a v1 LEDGER.yaml and, optionally, its git history (each
commit becomes history entries with the commit's author and date as actor and time). Fixtures:
tests/fixtures/v1/*.yaml. Expected lint findings on the output are the audit's F1-F9."""
from fleetwork.errors import NotImplementedYet


def from_v1(v1_dict):
    """A v2 Ledger from one v1 document (no history)."""
    raise NotImplementedYet("migrate.from_v1", "WP-03", "LEDGER-DESIGN §9")


def history_from_git(repo, path):
    """HistoryEntry list replaying every commit that touched `path` in `repo`."""
    raise NotImplementedYet("migrate.history_from_git", "WP-03", "LEDGER-DESIGN §9")
