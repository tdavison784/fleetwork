# fleetwork

A method for running a fleet of coding agents against one goal: a commander session, one agent per lane in its
own worktree, and a work ledger that says who may do what. The ledger core is designed to stay provider-neutral.
An optional guard can hand work between supported model providers as their usage windows fill; it runs only
when explicitly invoked with `fleet guard`. An experiment kit is also available for when the fleet's job is to
measure something rather than build it. The method was worked out over four fleet phases of a pilot project and
is being extracted here so it can be reused on any repository.

The **ledger** is the core. Everything else wraps around it.

## Layout

Start with `AGENTS.md` (how to work here), then `docs/ARCHITECTURE.md` (where everything lives).

| Path | What | State |
|---|---|---|
| `AGENTS.md` | The contract for anyone building the kit: read order, rules, workflow, commands | — |
| `docs/LEDGER-DESIGN.md` | Ledger v2 spec: audit of v1, what to take from beads and others, schema, derivation, delegations, storage, CLI | Design |
| `docs/ROADMAP.md` | The kit around the ledger; extraction order | Plan |
| `docs/ARCHITECTURE.md` | Vocabulary, layers, repository layout, config files, ledger directory, apply batches, how to add things | Current |
| `docs/WORKPACKAGES.md` | The build plan as 12 work packages: what each owns, order, done criteria | Queue |
| `docs/DECISIONS.md` | Owner decisions and structural choices, append-only | Current |
| `src/fleetwork/ledger/` | L1: data model (working), `ledger` CLI with every command registered, stubs per work package | Skeleton |
| `src/fleetwork/adapters/` | L2: registry and interfaces (working); `dir` store, `none` provider, `jsonl` events (working); the rest stubs | Skeleton |
| `src/fleetwork/runtime/` | L3: packs and `fleet init` (working), `fleet guard` (runs the v4 guard), lane lifecycle stubs | Skeleton |
| `packs/` | `core`, `git`, `providers`, `eval-integrity`: templates, profiles, rules and config tables per kind of use case | Working |
| `examples/` | `.fleet.toml` for go-rcana (portability test) and a two-provider sealed-evaluation fleet | Working |
| `guard/` | Optional fleet guard v4: provider usage windows, handoff and handback, context checkpoints, ledger auto-start. Herdr-based | Working; explicit `fleet guard` invocation; command-line defaults until WP-06 |
| `tools/ledger-to-beads.py` | One-way mirror of a v1 ledger into beads | Working; ported in WP-12 |
| `tests/` | Kit tests, including `test_architecture.py`, which keeps the core generic and the layers pointing down | — |

## Adopting it in a project

```
cp examples/go-rcana/.fleet.toml <your-repo>/        # then edit [project], [store], [vars], pack tables
cd <your-repo> && fleet init                          # renders the packs into the ledger directory
# fill MISSION.md; then, once WP-01 lands: ledger apply seed.yaml --actor <owner>
```

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

Skeleton in place: data model, config, adapter registry and interfaces, packs and `fleet init` work and are
tested; every other command exists and names the work package that builds it (`docs/WORKPACKAGES.md`). The
guard and the beads mirror are the running code carried over from the pilot project. Wave 1: WP-01
(storage), WP-02 (lint and ready), WP-08 (lane design).
