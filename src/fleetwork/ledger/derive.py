"""The derivation rules (LEDGER-DESIGN §4.3). Pure functions of a Ledger; nothing here touches disk.

  ready(i)        = open ∧ no owner ∧ every need done ∧ every gate closed
  offerable(i, p) = ready(i) ∧ p ∈ run.providers ∧ kind ≠ decision ∧ in-progress lanes on p < limit
  autostart(i, p) = offerable(i, p) ∧ run.auto-start ∧ kind = lane ∧ brief exists
  decidable(i, r) = kind = decision ∧ (r = run.rights ∨ delegated(r, "decide", i))

Reference behaviour to match: the guard's ledger derivations (guard/fleet_guard.py, the `ledger_*`
functions) on the v1 fixtures once migrated (tests/fixtures/v1).
"""
from fleetwork.errors import NotImplementedYet


def ready(ledger, item):
    raise NotImplementedYet("derive.ready", "WP-02", "LEDGER-DESIGN §4.3")


def offerable(ledger, item, provider):
    raise NotImplementedYet("derive.offerable", "WP-02", "LEDGER-DESIGN §4.3")


def autostart(ledger, item, provider, ledger_dir=None):
    raise NotImplementedYet("derive.autostart", "WP-02", "LEDGER-DESIGN §4.3")


def decidable(ledger, item, role):
    raise NotImplementedYet("derive.decidable", "WP-07", "LEDGER-DESIGN §4.3, §5")
