# Ledger v2 — design

Status: design proposal, 2026-10-21, revised the same day for portability. Nothing here changes a rule until
adopted. Relative paths cited as evidence (`docs/phase…`, `scripts/…`) are in the Release Intelligence
repository, where the v1 ledgers ran; `guard/` and `tools/` are in this repository. Written from an audit of
the two live ledgers (`docs/phase5/learning-loop/LEDGER.yaml`, 34 items,
25 commits; `docs/phase6/natural-agent/LEDGER.yaml`, 8 items, 5 commits), the guard's ledger code
(`~/.claude/fleet-guard/fleet_guard.py` §"window ledger (v4)"), the guard's event archives, the original
proposal (`docs/phase4/env-impact/proposals/2026-10-16-window-ledger.md`) and the fleetpilot report
(`docs/phase6/fleet-pilot/REPORT.md`).

The ledger is the core of the fleet system: the work queue, the authorization record and the window history.
Everything else (the guard, lane lifecycle, merge, enforcement hooks) wraps around it and depends on it. It
depends on nothing but an append-only history log, a SQLite index built from it (Python stdlib) and a directory
to put them in (§4.6); YAML is the authoring and viewing format, not the store; git is an optional backup of
the directory, and never the product repository. Release Intelligence is its first user, not
its definition.

## 0. Scope: what the ledger is, and what it must not know

**The ledger knows:** items, their typed relationships, their status, who may execute them, who may decide
them, what holds them, what they cost, and what happened to them, as an append-only log of changes from
which the current state is derived.

**The ledger must not know** (each of these is an adapter or a wrapper, declared in config, never in the core):

| Not in the core | Lives in | Today's instance |
|---|---|---|
| Provider names, their usage windows, how headroom is measured | `providers` config + a provider adapter | `claude` from statusline snapshots, `glm` from the Z.AI quota endpoint |
| Model names | item data (`run.model`), opaque strings | `claude-sonnet-5-5` |
| Terminal multiplexer, panes, agent lifecycle | fleet runtime wrapper | Herdr |
| Branches, worktrees, merge policy, test commands | fleet runtime wrapper + project config | `p6na/<lane>`, `go test ./...` |
| Agent harness, its hooks and permission model | enforcement adapter | Claude Code PreToolUse hooks |
| Where budget numbers come from | provider adapter | `meta.json tokens.processed`, `~/.claude/statusline-snapshots` |
| Where handoff events come from | event source, minimal schema (§4.5) | fleet guard `events.jsonl` |
| Hosted trackers, PR systems | gate adapters | GitHub via `gh` |
| Project-specific integrity paths | item data (`guard` lists), opaque globs | `eval/investigations/*/expected.yaml` |
| Memory, status files, commander state docs | out of scope | `status/<lane>.md`, `COMMANDER.md` |
| Where the ledger is stored, and whether that store is versioned | store adapter (§4.6) | today: the product repo's branch, one commit per change (the thing to stop doing) |

**Layering** (dependencies point down only):

```
L3  fleet runtime     lane start / watch / merge / cleanup; guard v5          ← wraps Herdr, git worktrees
L2  adapters          providers, gate evaluators, budget collectors,
                      event sources, enforcement writers                      ← tiny interfaces, one file each
L1  ledger CLI        lint, ready, gates, claim, close, add, windows, migrate  ← Python + PyYAML; store adapter
L0  ledger spec       file format + history log + derivation rules             ← this document §4
```

A second project adopts L0+L1 with a config file and zero code. It adds L2 adapters only for providers or gate
types the kit doesn't ship. L3 is optional: a project can run the ledger with a human commander and no fleet.

**Portability test (part of adoption, §8):** run the ledger on a second repository with different
providers and a different harness before calling v2 done. `go-rcana` is the candidate: its Locations
milestone is a ready-made queue of items with dependencies and a human owner.

## 1. What is working (keep as is)

| Practice | Evidence it earns its place |
|---|---|
| **Authorization at enqueue time** (`providers`, `glm-executable`, `auto-start`) | Model-under-test items (W-0012, W-0017, W-0030) were never offered to a GLM window; the guard's offered set equals the pre-authorized set in every archived window. This is the idea the whole thing exists for. |
| **Decisions are items** with `decision-rights` | 7 decision items across the two ledgers; each one records who decided and what (W-0014, W-0028). Nothing was decided "in chat only" once it was an item. |
| **One writer per window; the guard only reads** | 30 ledger commits, zero merge conflicts, zero corrupt reads (`ledger unreadable` never fired). |
| **Git-versioned YAML** | Every change is a reviewable diff with an author and a time. |
| **`integrity` strings on items** | W-0005 ("sealed"), W-0007 ("never merge groundtruth5"), W-0027 ("secrets never weakened") were each honoured. |
| **Provenance with `because`** | 21 of 34 Phase 5 items say why they exist; the ones that don't are the ones nobody can place later. |
| **Commander-level granularity**; lanes keep their own status files | Item counts stayed readable (34, 8). Fine-grained task tracking lives in `status/<lane>.md`. |
| **Sequential, prefixed ids** (W-, X-) | With one writer they never collided; they read well in prose and commit messages. |

## 2. What is good but held together by discipline (the audit)

Each finding below was checked against the live files, not remembered.

**F1. Readiness is both stored and derived.** `status: ready` is set by hand, and the guard also computes
"ready ∧ all `depends` done". The two disagree today: X-0005 is stored `ready` while its dependency X-0004 is
`in-progress`. Nothing flags this; the guard silently treats it as not ready, the commander reads the file and
thinks it is. Two sources of truth for one fact.

**F2. `ready-when` is prose nobody evaluates.** Five Phase 5 items carry it ("fresh Claude window", "PR #7
merged", "ri-guard no longer runs in it", "Phase 5 report done"). W-0012's was edited mid-window into a
conversation ("product owner 09:35 — current window is fine (50%)"). The guard ignores the field entirely.
These are gates; today a human re-reads them each window.

**F3. Authorization is encoded twice, and once inconsistently.** `providers` and `glm-executable` say the
same thing in 33 of 34 items; W-0031 has `providers: [claude, glm]` with `glm-executable: false`. The guard
requires both, so it was safe, but only because the stricter field happened to be the right one. The field
name itself hard-codes one provider.

**F4. The window log was designed and never written.** `windows: []` in Phase 5, absent in Phase 6. Yet the
data exists: the guard's archives hold 26 HANDOFF, 24 HANDBACK and 9 RESUME events with timestamps, and
`git log -p LEDGER.yaml` has every status change with a time. The log was assigned to the commander as a chore,
and chores at handback lose to the resume burst — the exact problem the proposal set out to fix.

**F5. Cost history never accumulated.** `quota-estimate` appears on 2 items, `quota-actual` on 1 (typed by
hand). The point was that "arm B needs ~1.4M tokens — fresh Claude window only" becomes a recorded fact. It
didn't, because recording it was manual. The numbers exist: statusline snapshots per session, `meta.json`
`tokens.processed` per Phase 6 run, `herdr agent get` per lane.

**F6. The schema drifted between phases because there is none.** Phase 6 dropped `version`, `goal`,
`windows`, `auto-start` and `provenance` (0 of 8 items say why they exist). Phase 5 used `owner` and `lane`
for the same thing. Nothing lints the file; `ledger-to-beads.py` had to special-case missing ids.

**F7. `result` and `note` became a second status file.** W-0012's `result` is a 70-word run summary;
W-0033's is a paragraph of analysis; X-0007's `note` holds four incident reports. Results belong in files
with the ledger pointing at them; otherwise the ledger is read less, not more.

**F8. `queued` means two different things:** "dependencies unmet" (X-0006) and "held by policy until the
report is out" (W-0026, W-0034). The first is derivable; the second is a gate. Conflating them is why F1 exists.

**F9. The same decision exists twice.** W-0020 (Phase 5) and X-0008 (Phase 6) are the same gascity question,
with nothing linking them, because ledgers are per phase and there is no `supersedes` edge.

**F10. Lane lifecycle state is scattered.** "LANE DONE" lives in a pane, the merge SHA in `merged:`, the owner
in `owner:` and in `herdr agent list`, the tab in Herdr, the worktree in `git worktree list`. Each phase we
re-derive the cleanup checklist by hand, and the one time it slipped (Phase 4, W-0021) it stayed open for a
phase. Merging a lane is one transaction with six side effects; nothing treats it as one.

**F11. Limits are hard-coded in the guard.** `MAX_AUTOSTART = 2` is a fleet policy living in a Python
constant. WIP limits per provider belong in the ledger header.

**F12. Incidents have no home.** fleetpilot's four brief deviations were recorded in X-0007's `note`. They are
findings that should change future briefs; nothing links a deviation to the rule it produced.

**F13. The commander's own authority is prose.** What the commander may do on the owner's behalf (resolve a
hold on a chat "yes", drop an item, add a lane) is scattered across briefs and memory, and differs between the
Claude commander and the GLM commander. The ledger pre-authorizes lanes at enqueue time but has no equivalent
for the commander (see §5, delegations).

## 3. What to draw from beads and other systems

Fleetpilot proved what beads does well and where it doesn't fit. Take the ideas, not the tool.

| From | Idea | Take it? | Why |
|---|---|---|---|
| beads `bd ready` | Readiness is **derived**, never stored; status is only open / in-progress / blocked / closed | **Yes** | Fixes F1 and F8 outright. |
| beads gates | A wait is an explicit object with a type (`human`, `timer`, `bead`, `gh:pr`, `gh:run`) that a `gate check` command evaluates | **Yes, plus one of ours** | Fixes F2. Our novel gate type is `window` (provider headroom), which neither beads nor gascity has. |
| beads typed edges | Non-blocking links: `discovered-from`, `caused-by`, `supersedes`, `validates`, `waits-for` (fan-in) | **A small subset** | `discovered-from` replaces free-text `because`; `supersedes` fixes F9; `caused-by` gives incidents a home (F12); `waits-for` expresses "merge wave 1 when all five lanes are done" without five edges. |
| beads formulas / molecules | A repeated workflow is a template that stamps out linked child items | **Yes, as YAML** | Every lane follows the same five steps (brief → run → done → review-merge → cleanup). Phase 5 hand-wrote them 12 times. A `lane` formula emits them with the edges in place. Formulas are per project, in config. |
| beads actor-per-write + Dolt history | Every change has an actor and the history is queryable | **Yes: the log is the truth** (§4.6) | Each CLI mutation is one entry `{v, t, actor, op, item, diff}` in `history.jsonl`; state is derived from it. Beads made the database the truth and then needed Dolt to merge databases; an append-only text log merges and syncs on its own. The v1 draft used one git commit per change, which is what fills a product PR with ledger commits. |
| beads CAS claim | `--claim` is atomic | **Yes, natively** | SQLite transaction on the expected version `v`; a second writer that read the same `v` fails and re-reads. |
| beads wisps | Operational items that are worthless once done are ephemeral | **Partly** | Guard checkpoints, canary runs and probes stay in the event stream, not in the ledger. The rule, not the mechanism. |
| beads hash ids | Collision-free ids for many writers | No | One writer; sequential ids read better. Revisit only if a project runs several independent commanders. |
| beads labels, Dolt, telemetry, `bd prime` | — | No | Fleetpilot: labels were a lossy encoding of our typed fields; Dolt, telemetry and home-dir writes are costs without a buyer; memory lives in the harness. |
| gascity reconciler | Desired vs running state, re-converged on a timer | **No, deliberately** | Fleetpilot's riskiest finding: a reconciler fights a window policy that wants lanes *stopped*. The ledger states what is **authorized**, never what should be running. Wrappers react to events; they do not reconcile. |
| gascity `max_active_sessions` | WIP limit per agent template | Yes | F11: `limits` in the ledger header, per provider. |
| Temporal | Idempotent activities; durable timers | **Idempotency only** | Every command keyed by item id, so a replayed `close X-0001` is a no-op. A `timer` gate is a durable timer without the server. |
| Pre-registration (science) | Rules fixed before the run; amendments appended, dated | **Already ours; make it checkable** | `integrity` prose becomes `guard:` lists that an enforcement adapter turns into hooks and pre-merge diffs — the layer fleetpilot found missing. |
| Kanban | WIP limits, pull not push | Yes | Same as `limits`. |
| Capability-based security | Authority is granted explicitly, narrowly, at the point of delegation, and is inspectable | **Yes, for the commander** | §5 delegations: the owner grants the commander named capabilities, with conditions, in the ledger header. Same shape as `run.providers` for lanes. |
| Jira / Linear / GitHub Issues | Hosted trackers | No | The ledger must be readable by an agent with `cat`, offline, inside a worktree, with no credentials. |

## 4. Schema v2

### 4.1 Header: the project's configuration

```yaml
version: 2
ledger: locations-milestone                 # name; ids use `prefix`
prefix: L
providers:                                  # declared here; the core never hard-codes a provider
  claude:  {adapter: claude-code,  limits: {lanes: 4}}
  glm:     {adapter: zai-quota,    limits: {lanes: 2}}
  local:   {adapter: none}                  # a provider with no window (e.g. a human, or an unmetered model)
roles:
  owner:     {actors: ["tdavison784"]}                       # humans; the final authority
  commander: {actors: ["ri-commander", "fleet-commander"]}   # primary commander agent(s)
  deputy:    {actors: ["glm-commander"]}                     # a commander with less delegated authority
delegations: [...]                          # §5
formulas:   {lane: formulas/lane.yaml}      # §4.4
events:     [".fleet/events.jsonl"]         # §4.5; zero or more sources
```

### 4.2 Items

The example is deliberately from a different project (the go-rcana Locations milestone) to keep RI out of
the spec.

```yaml
items:
  - id: L-0007
    title: PlayLocation action + move cost (one ink per character moved)
    kind: lane                              # lane | task | review | decision | evidence | incident
    status: open                            # open | in-progress | blocked | done | dropped   ('ready' is DERIVED)
    needs: [L-0003, L-0004]                 # blocking edges: CardLocation type, loader mapping
    gates:                                  # explicit holds; `ledger gates check` evaluates them
      - {type: human, who: owner, what: "confirm move cost is paid per character, not per move"}
      - {type: window, provider: claude, headroom: 30%}
      - {type: item, id: L-0006}            # same-ledger item; cross-ledger: {ledger: path, id}
      - {type: timer, after: 24h}
      - {type: pr, number: 12}              # evaluated by the configured tracker adapter
    run:                                    # enqueue-time authorization; replaces providers + <p>-executable + auto-start
      providers: [claude, glm]              # allow-list of declared providers; [] = commander-only
      auto-start: true
      model: claude-sonnet-5-5              # optional pin, opaque string
      rights: owner                         # decisions only: the role that may mark it done
    guard:                                  # checkable integrity; enforcement adapters turn these into hooks + merge checks
      forbid-read: ["internal/game/testdata/sealed/**"]
      freeze: ["cards.json"]
      no-push: true
      note: "locations never deal damage; don't add Strength logic"
    brief: briefs/locations-play.md         # required for kind: lane; path relative to the ledger
    owner: ri-locations                     # set by `ledger claim`, cleared by `ledger close`
    links: {discovered-from: L-0002, supersedes: L-0001}   # non-blocking typed edges
    budget:
      estimate: {claude: {tokens: 200k}}
      actual:   {claude: {tokens: 184k}, sessions: [a1b2c3]}   # filled by `ledger close` via the provider adapter
    result: runs/L-0007/REPORT.md           # a path; never the result text
    merged: 8286e36f
    note: one line, at most
    why: "Locations milestone phase 3; see CLAUDE.md"   # provenance; queued-by/at come from the history log
```

### 4.3 Derivation rules (the spec)

```
ready(i)        = status(i) = open ∧ owner(i) = ∅ ∧ ∀n ∈ needs(i): status(n) = done ∧ ∀g ∈ gates(i): closed(g)
offerable(i, p) = ready(i) ∧ p ∈ run.providers(i) ∧ kind(i) ≠ decision ∧ |in-progress lanes on p| < providers[p].limits.lanes
autostart(i, p) = offerable(i, p) ∧ run.auto-start(i) ∧ kind(i) = lane ∧ brief(i) exists
decidable(i, r) = kind(i) = decision ∧ (r = run.rights(i) ∨ delegated(r, "decide", i))     # §5
```

Status transitions, all through the CLI: `open → in-progress` (claim), `in-progress → done` (close, needs
`result` or `merged`), `in-progress → blocked` (an actor says so and adds a gate), `open|blocked → dropped`
(with `why`). `blocked` without a gate is a lint error. `ready` never appears in the file.

### 4.4 Formulas

A formula is a YAML template that `ledger add --formula <name>` expands into linked items. The kit ships
`lane` (lane → review `waits-for` lane → cleanup `needs` review, `guard` inherited); projects add their own.

### 4.5 Events: the minimal schema any wrapper may emit

The window log (§6) is derived from event sources declared in the header. Each line is JSON with at least
`{t, event, provider}` where `event ∈ {handoff, handback, resume, pause, checkpoint}`; extra fields are
kept verbatim. Today's guard already emits a superset; a different guard, or a cron job, emits the same five.

### 4.6 Storage: a log, an index and a view; never the product repository

Two owner concerns, 2026-10-21: "multi-hundred-commit PRs won't fly" at work (a consequence of two v1
choices, both dropped: the ledger lived on the product branch, and every change was a commit), and "is a YAML
file the best option, not a database?" (no; v1's worst findings, F1, F3 and F6, were all hand edits of a file
that was also the store).

**Three artifacts, one truth.** A ledger is a directory, `<store>/<ledger>/`:

| Artifact | Role | Notes |
|---|---|---|
| `history.jsonl` | **The truth.** Append-only; one entry per mutation: `{v, t, actor, op, item, diff}` | Text. Merges, syncs and diffs on its own; survives any tool; readable with `tail`. |
| `ledger.db` | **The index.** SQLite (Python stdlib), rebuilt from the log at any time by `ledger rebuild` | ACID; the CAS on `v`; concurrent readers; queries for `ready`, `windows`, `estimate`; state and history written in one transaction so they cannot drift. |
| `LEDGER.yaml` | **A view.** Regenerated on every write; read-only | What agents `cat` and humans read in a PR to the fleet store. Editing it changes nothing. |

Beside them: the ledger-relative files items point at (`briefs/`, `runs/`, `formulas/`). The product
repository holds one pointer file, `.fleet.toml`, naming the store; product PRs carry product changes only.

**Humans still author in YAML.** `ledger apply <file.yaml>` ingests a hand-written batch of items or edits as
log entries (delegation-checked per entry); formulas, seeds and the v1 migration all go through it. Authoring
ergonomics stay; the store stops accepting edits. The CLI is the only writer, which is what makes the
owner-only rule on `delegations` (§5) enforceable rather than linted after the fact.

**Why the log is the truth and not the database.** A binary file does not merge or diff, and syncing it
between machines or people is exactly where SQLite breaks; beads made the database the truth and then needed
Dolt to merge databases. An append-only text log is the sync and backup unit; the index is a local cache of
it. Two writers on different machines can still append the same `v`; `rebuild` reports the conflict, and the
fleet rule "one writer per window" keeps it rare. The design says this rather than claiming multi-master.

**Store adapters** (chosen in `.fleet.toml`; the core sees a directory):

| Store | What it adds | When |
|---|---|---|
| `dir` | Nothing; a directory (default a sibling `<project>-fleet/`, or `~/.fleet/<project>/`) | Single machine, personal use, the first weeks of any adoption |
| `git` | The same directory as its own repository, committing `history.jsonl` and the view (never `ledger.db`); cadence `per-window` or `manual`; push for backup or sharing | A team sharing a fleet, or wanting an off-machine copy |
| `github-issues` / `jira` | A **mirror**, like `export-beads`: items become issues with the typed fields in the body, one way | Workplaces that require work to be visible in the tracker. Never the source of truth: agents need offline, atomic, schema-complete access. |

**Lane commits are a separate knob.** The product history question also covers lane branches. `fleet merge`
takes `merge: squash | no-ff` from the project's `fleet.toml`. `no-ff` kept GLM-authored commits individually
reviewable in this personal repository; a workplace sets `squash`.

**Consequence for cross-references.** `merged: <sha>` and `result:` paths point across stores: the sha into
the product repository, the path into the ledger directory. They were cached fields already (F10); lint checks
that the sha exists when the product repository is reachable and warns otherwise.

## 5. Delegations: what the commander may do on the owner's behalf

Decision recorded 2026-10-21 (owner): the commander **may** resolve a `human` gate on the owner's say-so,
and the owner wants **a rule set for what the commander may do on their behalf**. Delegations are that rule
set, kept in the ledger header where every actor can read it and the history log shows every change to it.

```yaml
delegations:
  - role: commander
    may: gates.resolve
    gate: {type: human, who: owner}
    requires: {quote: true}          # the owner's words and time go into `why`; lint rejects a resolve without them
  - role: commander
    may: items.add
    kinds: [task, review, evidence, incident, lane]
    budget-cap: {claude: {tokens: 500k}}   # above this, adding the item needs the owner
  - role: commander
    may: items.drop
    kinds: [task, evidence]
  - role: commander
    may: decide
    rights: commander                # only decisions whose run.rights is commander; never owner's
  - role: deputy
    may: gates.resolve
    gate: {type: timer}              # a deputy (GLM commander) resolves nothing human
  - role: deputy
    may: items.add
    kinds: [evidence]
never:                               # applies to every role but owner; enforcement adapters turn these into hooks
  - push
  - force-delete-branch
  - answer-trust-dialog
  - edit-delegations                 # only the owner changes this section (lint: the log entry's actor must be an owner actor)
```

Semantics:
- Every mutating `ledger` command takes `--actor`; the CLI maps the actor to a role via `roles` and checks the
  delegation list. No matching delegation ⇒ the command refuses and prints the owner-facing request instead
  (which the commander relays). An owner actor is never checked.
- A delegation with `requires: {quote: true}` makes the command demand `--why` containing the owner's words
  and a time; the quote lands in the gate's `closed-by` record and in the history entry. W-0028 did exactly
  this by hand ("decided-by: product owner 2026-10-17T10:53").
- `never` is the capability floor: the enforcement adapter writes it into the commander session's hooks, so
  it is not only a ledger rule. The four entries above are the lessons from Phase 6 (fleetpilot's trust
  dialogs, the p4ei/eval `-D` hold, the no-push rule).
- Delegations are per role, not per provider, but roles are assigned to actors, and actors run on providers,
  so "the GLM commander may do less" is expressed by putting `glm-commander` in `deputy`.
- `edit-delegations` in `never` plus the CLI being the only writer (§4.6) means the commander cannot widen
  its own authority, by construction rather than by vigilance. The residual hole is an agent passing a forged
  `--actor`, or appending to `history.jsonl` by hand; `rebuild` flags entries whose `v` or hash chain is wrong,
  the `git` store can additionally sign commits, and the design says this rather than pretending otherwise.

Decision recorded 2026-10-21 (owner): a `window` gate **may** delay an item automatically, including
`providers: [claude]` items; that is what the field is for. Operationally: `ledger gates check` leaves the
gate open while `providers[p].adapter.headroom() < gate.headroom`, and the wrapper re-checks on every
`resume` event.

## 6. The ledger CLI

All commands are idempotent on item id, append one history entry per call with `--actor`, refuse to run if
`lint` fails, and check delegations for non-owner actors.

| Command | Does |
|---|---|
| `ledger lint` | Schema; ids monotonic and unique; `needs` exist; `blocked` has a gate; `lane` has an existing brief; `decision` has `run.rights`; `done` has `result` or `merged`; `in-progress` has `owner`; providers referenced are declared; `limits` not exceeded; delegations changed only by owner actors; index matches the log. Runs before every mutating command and on any `apply` batch. |
| `ledger apply <file.yaml> --actor a` | Ingests hand-authored items or edits as log entries; the YAML authoring path (§4.6). |
| `ledger rebuild` | Rebuilds `ledger.db` and `LEDGER.yaml` from `history.jsonl`; reports version conflicts. |
| `ledger ready [--provider p] [--auto-start]` | The derived sets (§4.3). Today's `ledger_offered` / `ledger_autostartable` / `ledger_claude_ready`, moved out of the guard. |
| `ledger gates check [--dry-run]` | Evaluates `timer`, `item` (built in), `window` (provider adapter), `pr` (tracker adapter); closes satisfied ones. `human` closes only by `gates resolve`. |
| `ledger gates resolve <id> <n> --actor a --why "…"` | Delegation-checked (§5). |
| `ledger add [--formula f --var k=v…] --actor a` | Stamps out items with edges; checks `items.add` delegation and `budget-cap`. |
| `ledger claim <id> <agent> --actor a` | One transaction on the expected version; fails if it moved. |
| `ledger close <id> [--merged sha] [--result path] --actor a` | Fills `budget.actual` through the provider adapter, clears owner, sets done. |
| `ledger decide <id> --actor a --why "…"` | Marks a decision done; `decidable` rule (§4.3). |
| `ledger windows` | Derived window log: per window, executed, deferred (with the gate or provider that held it), merges, budget start/end. Joins the event sources with `history.jsonl`. Nobody writes it, so it is never stale. |
| `ledger diff <v1> <v2>`, `ledger blame <id>` | From `history.jsonl`: what changed between two versions; every change to one item with actor and time. |
| `ledger estimate <kind> [--provider p]` | From `budget.actual` history: median and p90. |
| `ledger migrate v1→v2` | Converts the two live ledgers; the lint findings on the output are F1–F9. |
| `ledger export --to <mirror> --dest …` | One-way export through a mirror adapter. `beads` first: `tools/ledger-to-beads.py`, ported, for `bd ready` / `bd graph` views. (Was `export-beads`; renamed 2026-10-21 so the core names no tracker, §8.) |

### 6.1 Adapter interfaces (L2)

Each is one small Python module registered by name in the header. Shipped with the kit: `claude-code`,
`zai-quota`, `none`, `github`, `claude-code-hooks`, `beads` (mirror). The code layout is in `ARCHITECTURE.md`.

```
store:        open(uri) -> Dir; sync()            # dir | git: where the directory lives and how it is backed up; mirrors are one-way exporters
provider:     headroom() -> float | None          # fraction of the current window left; None = unmetered
              usage(session_ids) -> {tokens: int, cost: float | None}
gate:         check(gate, ledger) -> bool          # for adapter-provided gate types (window, pr, ci, …)
enforcement:  write(actor, guard_lists, never) -> None   # emits hooks / settings for that actor's session
events:       read() -> iter of {t, event, provider, …}
mirror:       export(ledger, dest) -> str             # one-way; nothing is read back
```

## 7. The runtime wrapper (L3), for projects that want a fleet

`fleet lane start`, `fleet watch`, `fleet merge`, `fleet guard` from the kit proposal. They call `claim` and
`close`; `fleet merge` is the one transaction for F10: check the lane's done signal and status file, diff
against `guard.freeze`, run the project's test command, `merge --no-ff`, close the pane, remove the worktree,
`branch -d`, `ledger close`. Any failure leaves the item `in-progress` with a note; the command is re-runnable.
Pane, worktree and test command come from the project's `fleet.toml`, never from the ledger.

`guard:` lists and `never:` become enforcement through the adapter: per-actor hooks that deny reads of
`forbid-read` paths, writes to `freeze` paths, `git push`, and trust-dialog answers; `fleet merge` refuses a
diff touching a frozen path. Fleetpilot showed the remaining holes (`git log -p`, relative-path `cat` across
worktrees): those close only when sealed objects are absent from the lane's repository, so hooks stay the
second layer and a sealed branch stays the first.

## 8. What stays deliberately simple

- **A log, a stdlib SQLite index and a generated YAML view, one directory per ledger, one writer per
  window.** No server, no new dependency, no database as the unit of sync.
- **Not in the product repository.** Its PRs stay about the product; the ledger's own history is the log.
- **Commander-level items.** Lanes keep their own status files; the ledger never lists a lane's sub-tasks.
- **Sequential ids.**
- **The guard never writes the ledger.** It calls `ledger ready` and emits events; the derived window log is
  how the two meet.
- **No reconciler.** The ledger is authorization and history, not desired running state.
- **No provider, harness or tracker named in the core.** If a name from §0's left column appears in
  `ledger.py`, that is a bug.

## 9. Migration and adoption

1. `ledger/` in this repository with `lint`, `ready`, `migrate`, `windows`; read-only, checked against the
   guard's current functions the way `tools/ledger-to-beads.py --compare-guard` does today.
2. Convert both RI ledgers into a sibling store (`../Release-Intelligence-fleet/`, `dir` first, `git` once it
   has something worth backing up): `migrate` replays `git log -p` of the old files as log entries, with the
   commit author and date as actor and time, so no history is lost; fix the lint findings (X-0005 readiness, W-0031 providers, missing provenance); write the RI
   header: providers `claude`/`glm`, roles, the delegations in §5, events from the guard. The experiment
   records (PROTOCOL, SCORES, REPORT, runs) are product documentation and stay in the RI repository; the
   operational churn (ledgers, status files, COMMANDER.md, briefs) moves.
3. **Portability test:** a `go-rcana` ledger for the Locations milestone (CLAUDE.md already lists the items
   and their order) with providers `{claude}` only and no fleet runtime. If step 1's code needs a change to
   run there, the change is a bug fix in the core, not a go-rcana adapter.
4. Guard v5 = v4 minus the ledger functions, calling `ledger ready --provider glm --auto-start`; the 23 guard
   tests move with the code.
5. `gates`, `claim`, `close`, `decide`, `add --formula`, delegations; then `fleet merge` last.
6. Release Intelligence and go-rcana become the first two project configs of this repository.

**Decisions recorded** (owner, 2026-10-21): window gates may delay items automatically, including
provider-pinned ones; the commander may resolve human gates on the owner's say-so with the quote recorded; the
owner sets standing delegations (§5) for what else the commander may do unasked.
