"""fleetwork: a ledger-centred method for running a fleet of agents against one goal.

Layers (dependencies point down only; docs/ARCHITECTURE.md):
  L3 fleetwork.runtime   lane lifecycle, profiles, `fleet` CLI
  L2 fleetwork.adapters  stores, providers, gates, enforcement, events, runtimes, workspaces, integrations
  L1 fleetwork.ledger    the `ledger` CLI and its library
  L0 the spec            docs/LEDGER-DESIGN.md §4
"""
__version__ = "0.0.1"
