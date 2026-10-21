# Roadmap: from a method we repeated five times to a kit

What exists today, where it came from, and the order to extract it. The ledger design is in
`LEDGER-DESIGN.md`; this file is everything around it.

## What the method is

| Piece | Origin (Release Intelligence) | Reusable as is? |
|---|---|---|
| Commander session plus lanes: one Herdr tab, worktree and `<prefix>/<lane>` branch each | Every phase's `FLEET.md` | Yes |
| Written rules every lane follows: ownership, commits, status files, finishing with `LANE DONE:`, cleanup, only the commander merges | `docs/phase5/learning-loop/FLEET.md` | ~70%; the rest is project (Go/Temporal) rules that belong in the project's own addendum |
| Lane instructions: a shared preamble plus one brief per lane | `docs/phase*/…/briefs/` | Yes, as templates |
| Work ledger: items, provider authorization, auto-start, decision items, provenance | Phases 5 and 6 `LEDGER.yaml` | Yes; v2 in `LEDGER-DESIGN.md` |
| Fleet guard: usage windows, provider handoff and handback, context checkpoints, ledger auto-start | `guard/` here | Yes, once prefixes and paths are config |
| Commander state doc and memory notes for resuming after a context reset | `COMMANDER.md` per phase | Yes, as templates |
| Experiment-integrity kit: pre-registered protocol (amendments only appended), sealed answer files, isolated runs of the agent under test, a canary that proves the isolation, scoring that checks every quote against the text | `PROTOCOL.md`, `scripts/phase6/{lib,canary,scores}.*` | Yes; the unusual part |
| Hard lessons: never answer trust dialogs, `DO_NOT_TRACK` before third-party CLIs, `rm "${VAR:?}"`, bash 3.2, long jobs under nohup not a watcher, wait on branch tip + agent state not screen text | memory and commander notes | They belong in code, not prose |

## The kit

**`fleet` CLI** (Python, PyYAML; wraps `git` and the multiplexer through adapters):
- `fleet init <goal>`: fleet directory from templates (MISSION, FLEET, commander brief, preamble, LEDGER, COMMANDER, `status/`).
- `fleet lane start <lane>`: worktree, branch, pane, named agent, brief sent; always `DO_NOT_TRACK`, never answers a trust dialog.
- `fleet watch <lane>`: waits on branch tip moved + agent idle/done.
- `fleet merge <lane>`: one transaction: done signal and status file present, diff inside ownership and off frozen paths, project tests pass, `merge` per project policy (`squash` at work, `no-ff` where lane commits must stay reviewable), close pane, remove worktree, `branch -d`, `ledger close`. Re-runnable.
- `fleet guard`: today's guard with provider, prefix and fleet dir from config.
- `ledger …`: the commands in `LEDGER-DESIGN.md` §6.

**Per-project `fleet.toml`**, the only file a new repository writes: integration branch and lane prefix; build
and test commands; frozen files and sealed paths; providers allowed; merge policy; where the ledger store is;
cleanup commands. Project-specific rules (Go, Temporal, game engine) stay in that project's own `FLEET.md`
addendum.

**Agent-harness plugin** (Claude Code first): commander skill, lane skill, and hooks generated from the
ledger's `guard:` lists and `never:` floor: deny reads of sealed paths, writes to frozen paths, `git push`,
trust-dialog answers. The pilot of gascity showed that prompt rules plus sparse checkout still left
`git log -p` and cross-worktree `cat` open; hooks are the second layer, a sealed branch the first.

**Experiment module** (optional): protocol template, sealed ground-truth lane brief, isolated runner, canary,
quote-checking scorer.

## Extraction order

1. **Move, don't redesign.** Guard, mirror and design are here. Next: templates and the Phase 6 harness
   scripts, as they are, with their RI coupling listed rather than fixed.
2. **Ledger v2 read-only commands** (`lint`, `ready`, `migrate`, `windows`), checked against the guard's
   current functions the way `ledger-to-beads.py --compare-guard` does.
3. **Portability test** on a second repository with different providers and no fleet runtime. Whatever breaks
   is RI coupling in the core, fixed in the core.
4. **Guard v5** = v4 minus its ledger parsing, calling `ledger ready`; prefixes and paths from `fleet.toml`.
5. `gates`, `claim`, `close`, `decide`, `add --formula`, delegations; then `fleet merge`.
6. Release Intelligence moves its operational churn (ledgers, status files, COMMANDER.md, briefs) into a
   sibling fleet store; its experiment records stay in its repository as product documentation.

## Not adopted, and why

gascity + beads as the substrate (pilot report in Release Intelligence `docs/phase6/fleet-pilot/REPORT.md`):
every integrity rule and the whole provider-window layer would be ours to build as plugins (~9–13 days), the
herdr runtime needed six workarounds on macOS, the projects merge >1,000 PRs a month, and a reconciler fights a
window policy that wants lanes stopped. Ideas taken instead: derived readiness, gates, typed edges, formulas.
