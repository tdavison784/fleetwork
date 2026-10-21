# Fleet guard v3

Token-free watchdog for a Herdr fleet (no model calls). Reads Claude usage from statusline snapshots
(`~/.claude/statusline-snapshots/*.json`) and Z.AI usage from the quota API (key in `~/.claude_token_zai`,
never printed). Files: `fleet_guard.py`, `lead_hook.sh` (lane-lead PreToolUse hook), `models.txt`
(relaunch model map), `state.json`, `PAUSED`, `events.jsonl`, `archive/`, `fleet_guard.v2.py` (rollback).

## What it does
1. **Claude window ≥ `--threshold` (90 %)**: Esc every *working* `fw-*` agent (`PAUSE`), then hand off:
   **first** the commander (`fw-commander` → `glm-commander`, split of its pane, `--cwd <commander-cwd>`,
   `.lane-lead` there set to `glm`, prompt = follow `<fleet-dir>/briefs/commander.md` GLM protocol),
   **then** each paused lane (`fw-<lane>` → `glm-<lane>`, same worktree). The commander is handed off
   even if it is idle (it usually is while lanes work); a still-working one waits (`handoff-wait`).
   Commander not found ⇒ `handoff-skip`, lanes proceed (v2 behaviour).
2. **Z.AI window ≥ `--zai-threshold`**: pause working `glm-*` agents until the Z.AI reset.
3. **Claude reset** (`wake_at` = reset + `--buffer`): hand back **lanes first, commander last**
   (`HANDBACK` → wait → `/exit` → close pane → lead back to `claude`), relaunch agents that had to be
   ended (`models.txt`), resume each `fw-*` lane with a GLM-commit review note, and send the Claude
   commander ONE combined RESUME (lane summary, commits on the integration branch since the handoff base,
   "read the GLM commander log in COMMANDER.md and review GLM merges", plus any `glm-*` agents the guard
   did not start, which are listed and **not** closed).
4. **Context checkpoints**: every live `fw-*`/`glm-*` agent's session (`agent_session.value`) is matched to
   its snapshot `context_window.used_percentage` (snapshots >1 h old ignored). At ≥ `--ctx-threshold` (80)
   it gets one `CONTEXT CHECKPOINT (fleet guard)…` prompt (event `CTX`); re-armed after it drops below
   threshold−30 (compaction). Not sent to agents the guard has paused. State persisted in `state.json`.

## Flags
`--commander-agent` (fw-commander) · `--commander-cwd` (integration worktree; required unless `--no-handoff`) ·
`--fleet-dir` (fleet; relative to each agent's worktree) · `--commander-session` (optional,
only for the commander ctx % in the log) · `--prefix fw-` · `--glm-prefix glm-` · `--glm-model glm-5.3` ·
`--threshold 90` · `--zai-threshold 90` · `--ctx-threshold 80` · `--interval 30` · `--zai-interval 120` ·
`--buffer 90` · `--handback-timeout 600` · `--state-dir` (override state/log dir) · `--reset-state` (archive
`state.json`, `PAUSED`, `events.jsonl` to `archive/<YYYY-MM-DD-HHMMSS>/`, start clean) · `--no-handoff` ·
`--dry-run` (log herdr mutations instead of running them). `--commander-pane` is accepted and ignored (v2).

## Start (first real start; run in herdr tab `fw-guard`)
```
cd ~/.claude/fleet-guard && python3 fleet_guard.py --reset-state \
  --commander-cwd <path to the commander worktree>
```
Drop `--reset-state` on restarts (state is restored). Stop: Ctrl+C in that tab (logs `stop`). If stopped
mid-window, a restart with `PAUSED` + `state.json` present resumes the window (`restore`).
The commander adds new lanes with `echo "fw-<lane> <model>" >> ~/.claude/fleet-guard/models.txt`.

## Test
`python3 -m unittest -v test_fleet_guard` (no network, no real herdr). Smoke:
`python3 fleet_guard.py --dry-run --interval 2 --state-dir $(mktemp -d) --commander-cwd <wt>` for a few seconds.

## Rollback
The pre-ledger v3 behaviour is what you get when the ledger is unreadable (logged once); there is no separate rollback file.
