# Working in fleetwork

Read this before changing anything. It is the contract for every agent and person building the kit.

## Read order

1. `docs/ARCHITECTURE.md`: where everything lives, the layers, how to add things.
2. Your work package in `docs/WORKPACKAGES.md`: what you own, the spec section, "done when".
3. The spec sections it cites (`docs/LEDGER-DESIGN.md`, `docs/ROADMAP.md`).
4. `docs/DECISIONS.md`: decisions already made; don't re-open them.

## Rules

- **Stay in your package's files.** Shared files (listed in WORKPACKAGES.md) take small additive changes only,
  listed in your status file. A change to the spec (`LEDGER-DESIGN.md` §4, the data model) is proposed in your
  status file, not made.
- **The core stays generic.** Nothing in `src/fleetwork/ledger/`, `config.py` or `errors.py` names a
  provider, harness, multiplexer, tracker or project. Those go in adapters, packs, examples and config.
  `tests/test_architecture.py` fails if they leak.
- **Dependencies:** Python ≥ 3.11 standard library and PyYAML. Nothing else without a decision in
  `docs/DECISIONS.md`. An adapter may call an external CLI (`git`, `herdr`, `gh`, `bd`) through `subprocess`.
- **Tests use no network** and no real external tools: fakes, fixtures, temporary directories. A test that
  needs a real binary skips with a clear message when it is missing.
- **Stubs show the work.** Unbuilt pieces raise `NotImplementedYet(what, "WP-xx", spec)`. Replace the stub;
  don't add a parallel module. When your package is done, `grep -rn "WP-xx" src` returns nothing for it.
- **Secrets:** read key files only at the moment of use; never print, log or copy them. Guard runtime state
  (`guard/state.json`, `events.jsonl`, `archive/`) is never committed.
- Never push, never force-delete a branch, never answer a trust or permission dialog for the owner.

## Workflow

- Branch `wp/<nn>-<slug>` (e.g. `wp/01-storage`) in a worktree at `.claude/worktrees/wp-<nn>`, cut from the
  integration branch the commander names. Commit early; imperative subject, body says why.
- Keep `docs/status/WP-<nn>.md` current as you go (template: `packs/core/templates/status/_lane.md`).
- Done = your package's "done when" holds, `make check` passes, the status file is current, and your final
  message starts with `LANE DONE:` (at most 15 lines). The commander merges; you don't.

## Commands

```
make test                                   all tests (kit, guard, beads mirror)
make check                                  what "done" requires
PYTHONPATH=src python3 -m fleetwork.ledger.cli --help
PYTHONPATH=src python3 -m fleetwork.runtime.cli init --dir /tmp/x --packs core,git --var owner=me …
```
