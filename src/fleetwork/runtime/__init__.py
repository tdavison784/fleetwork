"""The fleet runtime (L3): packs, `fleet init`, agent profiles, lane lifecycle, the `fleet` CLI.

Module map (docs/WORKPACKAGES.md):
  packs.py      find and load packs (packs/<name>/pack.toml + templates/)   shared
  init.py       `fleet init`: render pack templates into a ledger directory  shared
  profiles.py   agent profiles: who does the work (lane design)             WP-08
  lanes.py      lane start / watch / merge over runtime, workspace,
                integration and enforcement adapters                        WP-09, WP-10
  cli.py        the `fleet` command (shared; add commands, don't restructure)
"""
