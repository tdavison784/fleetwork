# Architecture: where everything lives

The map from the designs (`LEDGER-DESIGN.md`, `ROADMAP.md`) to the code. If you are about to create a
directory, a config file or a base class, check here first: it probably has a home already.

## Vocabulary

| Term | Means | Lives in |
|---|---|---|
| **Goal** | What a fleet is for, with checkable success criteria | `<ledger>/MISSION.md` |
| **Ledger** | Work items, their edges, authorization, decisions and history, for one goal | `<store>/<ledger>/` (§ Ledger directory) |
| **Item** | One unit in the ledger: `lane`, `task`, `review`, `decision`, `evidence`, `incident` | `fleetwork.ledger.model.Item` |
| **Lane** | An item of kind `lane`: work with its own workspace, brief, status file and contract | item + `briefs/<lane>.md` + `status/<lane>.md` |
| **Profile** | Who does a lane's work: runtime, provider, model, fallback, env, `never`, hooks. Reusable | `<ledger>/profiles/<name>.yaml`, `fleetwork.runtime.profiles` |
| **Agent** | A running instance of a profile in a lane. Replaceable; several may occupy one lane over its life | the runtime adapter's state |
| **Commander** | The role that writes the ledger and integrates lanes | `briefs/commander.md`, `roles:` in the header |
| **Pack** | An optional bundle of templates, profiles, rules and config tables for one kind of use case | `packs/<name>/` |
| **Adapter** | One module behind one small interface, chosen by name in config | `src/fleetwork/adapters/<kind>/` |
| **Project** | A repository (or any workspace) that adopts fleetwork | its `.fleet.toml` |

## Layers

```
L3  fleetwork.runtime    fleet init, packs, profiles, lane start/watch/merge, `fleet` CLI
L2  fleetwork.adapters   store, provider, gate, events, mirror        (the ledger may use these)
                         enforcement, runtime, workspace, integration  (only the runtime uses these)
L1  fleetwork.ledger     the `ledger` CLI and library
L0  the spec             LEDGER-DESIGN.md §4
```

Dependencies point down only, and `tests/test_architecture.py` enforces it:
- `fleetwork.ledger` never imports `fleetwork.runtime` or a concrete adapter module; it gets adapters by name
  through the registry (`fleetwork.adapters.get/create`).
- `fleetwork.adapters` never imports `fleetwork.runtime`.
- No file in `fleetwork/ledger/`, `config.py` or `errors.py` names a provider, harness, multiplexer, tracker
  or project. Those names belong in adapters, packs, examples and config.

## Repository layout

```
AGENTS.md                 the contract for anyone working in this repository (read first)
docs/
  LEDGER-DESIGN.md        ledger spec and rationale (L0)
  ROADMAP.md              the kit around the ledger; extraction order
  ARCHITECTURE.md         this file
  WORKPACKAGES.md         the build plan: work packages, what each owns, order, done criteria
  DECISIONS.md            owner decisions and structural choices, append-only
  status/<wp>.md          one status file per work package in flight
src/fleetwork/
  errors.py               shared exceptions and exit codes
  config.py               .fleet.toml loader
  ledger/                 L1: model, history, index, view, store, lint, derive, migrate, windows,
                          gates, delegations, formulas, cli
  adapters/               L2: registry (__init__), interfaces (base.py), one sub-package per kind
  runtime/                L3: packs, init, profiles, lanes, cli
packs/<name>/             pack.toml, README.md, templates/ (rendered into a ledger directory)
examples/<project>/       a project's .fleet.toml and first apply batch; also test fixtures
guard/                    fleet guard v4 (working; becomes v5 in WP-06)
tools/                    ledger-to-beads.py (working v1 mirror; ported into adapters/mirrors in WP-12)
tests/                    the kit's tests; fixtures/v1 are the two live v1 ledgers, fixtures/v2 v2 samples
```

## Config: three files, three owners

| File | Owner | Holds |
|---|---|---|
| `<project>/.fleet.toml` | the project | `[project]` name, packs, pack-path · `[store]` adapter, ledger, adapter keys · `[vars]` template values · one table per pack (`[git]`, `[checks]`, `[runtime]`, `[guard]`, `[eval]`) |
| `<ledger>` header (in `history.jsonl`, shown in `LEDGER.yaml`) | owner and commander, via `ledger` | providers and limits, roles, delegations, `never`, formulas, event sources |
| `packs/<name>/pack.toml` | the pack's author | `[pack]` name, description, requires · `[vars]` defaults · `[config.<table>]` the `.fleet.toml` tables it owns, `{key: doc}` |

The core reads only `[project]`, `[store]` and `[vars]`; each pack validates its own tables. That is the
extension point for a new use case: a new pack, not a change to the core. Why policy is in the ledger header
and not in `.fleet.toml`: so every change to who may do what is in the history log with an actor and a time.

## Ledger directory

What `fleet init` creates and `ledger` maintains, at `<store>/<ledger>/`:

```
history.jsonl     the truth: one {v, t, actor, op, item, diff} per mutation       ledger (WP-01)
ledger.db         SQLite index, rebuilt from the log; never committed or synced    ledger (WP-01)
LEDGER.yaml       generated read-only view                                         ledger (WP-01)
seed.yaml         the first apply batch (header + first decision)                  fleet init
MISSION.md  FLEET.md  COMMANDER.md  PROTOCOL.md (eval-integrity)                   fleet init, then people
briefs/  status/  profiles/  formulas/  rules/  runs/                              fleet init, then commander/lanes
```

It is never inside the product repository; the product holds only `.fleet.toml` (LEDGER-DESIGN §4.6).

## Apply batches

The authoring format for `ledger apply` (and `seed.yaml`, formulas' output, `migrate`'s output):

```yaml
header:          # optional; keys merged into the ledger header (an `header` op; delegations: owner only)
  never: [push]
items:           # optional; each entry adds an item, or edits the existing item with that id
  - id: L-0002
    title: …
    kind: lane
```

An edit lists only the keys it changes; `null` deletes a key. Status changes go through `claim`, `close`,
`decide`, not through `apply`.

## Placeholders

| Syntax | Filled by | When |
|---|---|---|
| `{{name}}` | `fleet init` (pack `[vars]` < built-ins < `.fleet.toml [vars]` < `--var`) | once, when the ledger directory is created |
| `${name}`, `@key` | `ledger add --formula` | each time a formula is expanded |
| `<what>` | a person or the commander | by hand, e.g. when copying `briefs/_lane.md` |

## Adding things

| You want to add | Do this | Don't |
|---|---|---|
| A provider, store, gate type, event source, mirror, runtime, workspace or integration | One module in `adapters/<kind>/<name>.py`, `@register(kind, name)`, implement the Protocol in `base.py`, a test in `tests/adapters/` | Edit the registry or the core |
| Support for a new kind of use case (research lanes, docs, data migrations) | A pack: `packs/<name>/pack.toml` + templates + rules, an example project, adapters if it needs a non-git workspace | Add use-case fields to the ledger model; put them in a pack table or item `extra` |
| A `ledger` command | A row in `ledger/cli.py` `COMMANDS`, a handler in `HANDLERS`, the logic in the matching library module | Parse arguments in library modules |
| A ledger field | Change `LEDGER-DESIGN.md` §4 first (commander), then `model.py`, `lint.py`, a fixture | Add it silently; `extra` keeps unknown keys so nothing is lost meanwhile |
| A rule every lane must follow | `packs/core/templates/FLEET.md` (or a pack's `rules/`), and an enforcement hook if it can be checked | Put it in one brief |
