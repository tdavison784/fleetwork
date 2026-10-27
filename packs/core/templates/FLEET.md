# Fleet rules: {{ledger}}

Every agent in this fleet follows these rules. Read order for any agent: this file, `MISSION.md`, the
`rules/` files of this fleet's packs ({{packs}}), the project's own rules if `MISSION.md` names any, then your
brief. If two rules conflict, the stricter one wins and you say so in your status file.

## Roles

- **Owner** ({{owner}}): decides. Decisions are ledger items of kind `decision`; nothing is decided in chat
  only. The owner's standing delegations in the ledger header say what the commander may do unasked.
- **Commander** (`{{commander_agent}}`): the only writer of the ledger and the only integrator. It writes
  briefs, starts lanes, answers lane questions within the contract, reviews and integrates finished lanes,
  and keeps `COMMANDER.md` current. It does not do lane work itself.
- **Lanes**: one unit of work each, in its own isolated workspace, with its own brief and status file. Lanes
  propose; they never integrate, never edit the ledger, never edit another lane's files.

## The rules that make agents replaceable

1. **Work state lives outside agents.** Ledger, brief, `status/<lane>.md` and the workspace's history hold
   everything. Any agent can be replaced mid-task (another model, a fresh session after a context reset,
   another provider during a usage window) and continue from those alone.
2. **Each lane is isolated.** Work only in your workspace. Read other lanes' work only when your brief says so.
3. **One writer per shared thing.** One commander writes the ledger and integrates; lanes only propose.
4. **Authorization is decided when work is queued.** What an item may run on, and whether it may start
   unasked, are fields on the item (`run:`). No agent widens its own authority mid-run.
5. **Contracts are fixed before work starts; changes are appended,** dated, with a reason.
6. **"Done" is checked, not claimed.** A lane reports; the commander's checks verify the report.
7. **Humans own decisions.** If you need one, write it in your status file, say so in your final message, and
   stop that line of work. Pick sensible defaults on local questions; never guess on contract questions.

## Ownership

Your brief lists what you own. Edit outside it only when unavoidable, keep such edits minimal, and list them
in your status file. Files your brief or the item's `guard:` marks frozen or forbidden are never edited or
read; the enforcement hooks deny them, and a denial is a signal to stop, not something to route around.

## Never (every agent, every pack)

- Push, publish, open or merge pull requests, or contact anything outside the machine unless your brief says so.
- Answer a trust, permission or login dialog on the owner's behalf. Report it and wait.
- Delete anything you did not create. Branch deletes are safe deletes only (`-d`, never `-D`).
- Print, log or copy secrets, tokens or keys. Read key files only at the moment of use.
- Run a third-party CLI before setting `DO_NOT_TRACK=1` (and the tool's own telemetry opt-out if it has one).
- In any `rm`, use a literal path or `"${VAR:?}"`. An `rm` on an empty variable is never acceptable.

## Status and continuity

- Keep `status/<lane>.md` current **as you go** (template: `status/_lane.md`): done, in progress with the
  exact next step, decisions with why, files touched outside ownership, open questions, check results.
- If you receive `CONTEXT CHECKPOINT`: update and save your status file now, then continue.
- Long-running jobs run detached (`nohup … &` with a log file), never as a child of a watcher or a tool call
  that can time out. Wait on observable state (a file, a commit, an agent's state), never on screen text.

## Finishing

1. Run the checks your brief names (and `.fleet.toml` `[checks]`). They must pass, or your report says
   exactly which fail and why.
2. Clean up what you created: servers, clusters, large scratch output. Say what you cleaned.
3. Save everything (commit in your workspace if it is a repository).
4. Final message starts with `LANE DONE:` followed by at most 15 lines: where the work is, what works, check
   results, known gaps. The commander integrates and removes your workspace; you don't.
