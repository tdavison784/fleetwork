# fleetwork

A method for running a fleet of coding agents against one goal: a commander session, one agent per lane in its
own worktree, a work ledger that says who may do what, a guard that hands work between model providers as
their usage windows fill, and an experiment kit for when the fleet's job is to measure something rather than
build it. It was worked out over four phases of the Release Intelligence project and is being extracted here
so it can be reused on any repository.

The **ledger** is the core. Everything else wraps around it.

## Layout

| Path | What | State |
|---|---|---|
| `docs/LEDGER-DESIGN.md` | Ledger v2: audit of the v1 ledgers, what to take from beads and other systems, the schema, derivation rules, delegations, storage, the CLI, adoption plan | Design, awaiting implementation |
| `docs/ROADMAP.md` | The whole kit: layers, commands, extraction order | Plan |
| `guard/` | Fleet guard v4: token-free watchdog that reads provider usage windows, pauses/hands off/hands back agents between providers, nudges agents to checkpoint before their context fills, and auto-starts pre-authorized ledger items. Herdr-based. 23 tests. | Working; still carries Release Intelligence defaults (`ri-` prefix, fleet dir) to be moved into config |
| `tools/ledger-to-beads.py` | One-way mirror of a v1 ledger into a beads store, with a `--compare-guard` check that `bd ready` matches the guard's derived sets | Working; defaults point at RI paths |

## Layers (dependencies point down)

```
L3  fleet runtime     lane start / watch / merge / cleanup; the guard          wraps Herdr, git worktrees
L2  adapters          providers, gate evaluators, budget collectors,
                      event sources, enforcement writers, stores               tiny interfaces, one file each
L1  ledger CLI        lint, ready, gates, claim, close, apply, windows, migrate  Python stdlib + PyYAML
L0  ledger spec       history log (truth) + SQLite index + YAML view + rules   docs/LEDGER-DESIGN.md §4
```

A project adopts L0+L1 with a config file and no code. The ledger is an append-only log of changes with a
SQLite index and a generated YAML view; it is never stored in the product repository.

## Rules the code must keep

- The ledger core names no provider, harness, multiplexer, tracker or project path. Those live in config and
  adapters (`docs/LEDGER-DESIGN.md` §0).
- Authorization is decided when work is queued, by whoever has the right to decide it, and recorded as data.
  Agents never widen their own authority; the owner's standing delegations say what the commander may do unasked.
- The ledger states what is authorized, never what should be running. Nothing in here reconciles.
- Guard runtime state (`state.json`, `events.jsonl`, `archive/`) is never committed.

## Status

Design stage. The guard and the beads mirror are the only running code, both copied from where they ran
(`~/.claude/fleet-guard`, which was never under version control, and Release Intelligence `scripts/fleet/`).
First implementation target: the read-only ledger commands (`lint`, `ready`, `migrate`, `windows`), verified
against the guard's current derivations, then a portability test on a second repository.
