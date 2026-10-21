# Work packages

The build plan for the kit, cut so each package can be one lane: it owns a set of files, has an order, and has
a checkable "done". Each stub in the code raises `NotImplementedYet` naming its package, so
`grep -rn "WP-0X" src` shows exactly what a package has to fill in.

Until the kit can host its own ledger (after WP-01 and WP-02), this file is the queue and
`docs/status/<wp>.md` the status files. After that, these packages move into a fleetwork ledger through
`ledger apply`, and this file only records the plan.

Shared files (`ledger/model.py`, `ledger/cli.py`, `runtime/cli.py`, `adapters/__init__.py`, `adapters/base.py`,
`config.py`, `errors.py`, `packs/core/`) belong to no package: change them additively (a new field, a new
command row, a new exception), keep the change small, and list it in your status file.

| WP | Title | Needs | Order |
|---|---|---|---|
| WP-01 | Ledger storage: history, index, view, apply, rebuild | — | wave 1 |
| WP-02 | Lint and derived readiness | WP-01 (model only to start) | wave 1 |
| WP-03 | Migrate v1 → v2 | WP-01, WP-02 | wave 2 |
| WP-04 | History queries: windows, estimate, diff, blame | WP-01 | wave 2 |
| WP-05 | Portability test on go-rcana | WP-01, WP-02, WP-03 | wave 3 |
| WP-06 | Provider adapters and guard v5 | WP-02 | wave 3 |
| WP-07 | Mutations: gates, claim, close, decide, add, delegations, formulas | WP-01, WP-02 | wave 3 |
| WP-08 | Profiles and lane spec | — (design first) | wave 1 (design), wave 3 (code) |
| WP-09 | Lane start and watch; runtime and workspace adapters | WP-07, WP-08 | wave 4 |
| WP-10 | Lane merge; integration and enforcement adapters | WP-09 | wave 4 |
| WP-11 | eval-integrity pack: move the harness scripts | — | any time |
| WP-12 | Sync and mirrors: git store, beads mirror, GitHub gates | WP-01 | wave 3 |

## WP-01: Ledger storage

**Owns:** `src/fleetwork/ledger/{history,index,view,store}.py`, `src/fleetwork/adapters/stores/dir.py`,
`tests/ledger/test_storage*.py`, `tests/fixtures/v2/`.
**Spec:** LEDGER-DESIGN §4.6; apply-batch format in ARCHITECTURE.md.
**Done when:** `ledger apply seed.yaml` on a directory made by `fleet init` writes `history.jsonl`, `ledger.db`
and `LEDGER.yaml`; `ledger rebuild` reproduces the same index and view byte for byte from the log alone; a
second writer holding a stale `v` gets `VersionConflict`; the view's first line is `view.BANNER`.

## WP-02: Lint and derived readiness

**Owns:** `src/fleetwork/ledger/{lint,derive}.py`, `tests/ledger/test_lint.py`, `tests/ledger/test_derive.py`.
**Spec:** LEDGER-DESIGN §4.3, §6 (`ledger lint`, `ledger ready`).
**Done when:** every lint rule in §6 has a test with a failing and a passing fixture; `ready`, `offerable` and
`autostart` match the guard's `ledger_offered` / `ledger_autostartable` / `ledger_claude_ready` on the migrated
v1 fixtures (the comparison `tools/ledger-to-beads.py --compare-guard` makes today).

## WP-03: Migrate v1 → v2

**Owns:** `src/fleetwork/ledger/migrate.py`, `tests/ledger/test_migrate.py`, `tests/fixtures/v1/`.
**Spec:** LEDGER-DESIGN §9 step 2.
**Done when:** both fixtures in `tests/fixtures/v1/` migrate; lint on the output reports the audit's findings
(F1 X-0005 readiness, F3 W-0031 providers, F6 missing provenance) and nothing else; with `--git-repo`, history
entries carry each commit's author and date.

## WP-04: History queries

**Owns:** `src/fleetwork/ledger/windows.py`, `src/fleetwork/adapters/events/`, `tests/ledger/test_windows.py`.
**Spec:** LEDGER-DESIGN §4.5, §6 (`windows`, `estimate`, `diff`, `blame`).
**Done when:** `ledger windows` on a migrated Phase 5 ledger plus a guard `events.jsonl` sample lists each
window with executed and deferred items; guard event names (`HANDOFF`, `HANDBACK`, `RESUME`, `PAUSE`, `CTX`)
are normalised to the §4.5 names in `windows.py`, not in the adapter.

## WP-05: Portability test on go-rcana

**Owns:** `examples/go-rcana/`, `docs/status/WP-05.md` (the findings).
**Spec:** LEDGER-DESIGN §9 step 3.
**Done when:** a go-rcana ledger runs `init`, `apply`, `lint`, `ready` from `examples/go-rcana/` config alone.
Every change the run needed is listed and made in the core as a bug fix, never as a go-rcana special case.

## WP-06: Provider adapters and guard v5

**Owns:** `src/fleetwork/adapters/providers/{claude_code,zai_quota}.py`, `guard/`, `packs/providers/`.
**Spec:** LEDGER-DESIGN §6.1, §9 step 4; ROADMAP step 4.
**Done when:** both adapters implement `headroom()` and `usage()` (the Z.AI key is read at call time and never
printed); the guard calls `ledger ready --provider … --auto-start` instead of parsing the ledger, takes
prefixes and paths from `.fleet.toml` `[guard]` and `[runtime]`, and its 23 tests still pass.

## WP-07: Mutations

**Owns:** `src/fleetwork/ledger/{gates,delegations,formulas}.py`, the `gates`, `add`, `claim`, `close`, `decide`
handlers in `ledger/cli.py`, `tests/ledger/test_{gates,delegations,formulas,mutations}.py`.
**Spec:** LEDGER-DESIGN §4.3 (`decidable`), §4.4, §5, §6.
**Done when:** every command is idempotent on item id; a non-owner actor without a delegation gets
`DelegationRefused` with the owner-facing request; a resolve requiring a quote without `--why` is refused; only
owner actors can change `delegations`; `ledger add --formula lane` expands `packs/core/templates/formulas/lane.yaml`.

## WP-08: Profiles and lane spec

**Owns:** `docs/LANE-DESIGN.md` (new), `src/fleetwork/runtime/profiles.py`, `packs/*/templates/profiles/`.
**Spec:** the lane-design proposal (profile = who, lane = what; `run.profile` on the item; profile keys in
`packs/core/templates/profiles/README.md`). Write it up as `docs/LANE-DESIGN.md` first, for the owner. Open
questions to put to the owner: can a lane change profile mid-life (proposal: no, make a new lane); pools of
identical lanes (proposal: not yet); is "lane" the user-facing word.
**Done when:** the design is accepted by the owner; `profiles.load` validates every shipped profile; lint
flags a lane whose `run.profile` doesn't exist.

## WP-09: Lane start and watch

**Owns:** `src/fleetwork/runtime/lanes.py` (`start`, `watch`), `src/fleetwork/adapters/{runtimes,workspaces}/`.
**Spec:** LEDGER-DESIGN §7; ROADMAP "The kit".
**Done when:** `fleet lane start <id>` claims, creates the workspace, writes enforcement, starts the profile's
agent with the brief and `DO_NOT_TRACK=1`; a `blocked` agent (trust or permission dialog) is reported, never
answered; `watch` returns on tip moved + agent idle/done; both runtimes (herdr, headless) pass the same tests
with fakes.

## WP-10: Lane merge

**Owns:** `src/fleetwork/runtime/lanes.py` (`merge`), `src/fleetwork/adapters/{integrations,enforcement}/`.
**Spec:** LEDGER-DESIGN §5 (`never`), §7.
**Done when:** `fleet lane merge` is one re-runnable transaction (checks, integrate, stop, remove, close);
it refuses a diff off ownership or touching a frozen path; the enforcement adapter's hooks deny forbidden
reads, frozen writes, `git push` and trust-dialog answers in a canary session.

## WP-11: eval-integrity pack

**Owns:** `packs/eval-integrity/`.
**Spec:** ROADMAP "Experiment module".
**Done when:** the isolated runner, canary, extraction and quote-checking scorer are in the pack as they ran
in Release Intelligence, with their coupling to it listed in the pack README rather than fixed.

## WP-12: Sync and mirrors

**Owns:** `src/fleetwork/adapters/stores/git.py`, `src/fleetwork/adapters/mirrors/`,
`src/fleetwork/adapters/gates/github.py`, `tools/`.
**Spec:** LEDGER-DESIGN §4.6, §6 (`ledger export`).
**Done when:** the `git` store commits `history.jsonl` and the view (never `ledger.db`) at its cadence;
`ledger export --to beads` matches `tools/ledger-to-beads.py` output on a migrated fixture; `pr` gates close
when the PR is merged (tested with a fake `gh`).
