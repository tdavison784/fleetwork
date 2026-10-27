# Fleet guard

The guard is optional and starts only when invoked with `fleet guard` or `python3 guard/fleet_guard.py`.
It monitors Claude Code statusline snapshots and pauses the configured Herdr agents when a Claude
window reaches the threshold. Automatic handoff is **off by default**: without `--handoff` the guard
neither reads the Z.AI key nor calls its quota API. Context checkpoints and resumption still run.

To opt into the existing GLM fallback, supply `--handoff --commander-cwd <worktree>`. This uses the
Z.AI quota API and `~/.claude_token_zai`; the guard reads the key when polling quota, and the fallback
pane reads it when starting. The guard hands off the commander and paused lanes, then hands them back
when the Claude window resets. It waits for the fallback quota window before handback and extends wake
times when a later window crosses its threshold. Failed starts and lead restoration are tracked for retry.

```sh
python3 guard/fleet_guard.py --handoff --commander-cwd /path/to/worktree
```

This implementation supports the existing Claude-to-GLM handoff. Generalizing the guard to other
providers is planned separately; the provider adapter interfaces are not implemented yet.

Other options include `--prefix`, `--glm-prefix`, `--glm-model`, `--threshold`, `--zai-threshold`,
`--ctx-threshold`, `--interval`, `--zai-interval`, `--buffer`, `--handback-timeout`, `--state-dir`,
`--reset-state` and `--dry-run`; use `--help` for defaults. Do not reset state when restarting a paused
guard; pass `--handoff` again when resuming an active GLM handoff so Z.AI quota monitoring is enabled.
State includes handoff progress so cleanup and lead restoration can be retried before agents resume.

Tests use fakes and need no network or real Herdr: `python3 -m unittest guard/test_fleet_guard.py`.
