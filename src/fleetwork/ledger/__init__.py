"""The ledger (L0 spec + L1 library and CLI). docs/LEDGER-DESIGN.md is the spec; this package implements it.

Module map (one owner each; docs/WORKPACKAGES.md):
  model.py        data model (shared; changes need the commander)       all
  history.py      history.jsonl: append with CAS, read, verify          WP-01
  index.py        ledger.db: SQLite index rebuilt from the log          WP-01
  view.py         LEDGER.yaml: the generated read-only view             WP-01
  store.py        open a ledger directory; apply/rebuild glue           WP-01
  lint.py         `ledger lint` findings                                WP-02
  derive.py       ready / offerable / autostart / decidable (§4.3)      WP-02
  migrate.py      v1 -> v2                                              WP-03
  windows.py      derived window log, estimate, diff, blame             WP-04
  gates.py        gate check/resolve; built-in gate types               WP-07
  delegations.py  role lookup and capability checks (§5)                WP-07
  formulas.py     formula expansion for `ledger add --formula`          WP-07
  cli.py          the `ledger` command (shared; add commands, don't restructure)

The core imports only the standard library, PyYAML, fleetwork.errors, fleetwork.config and the
store/provider/gate/events adapter kinds through fleetwork.adapters. Never fleetwork.runtime.
"""
