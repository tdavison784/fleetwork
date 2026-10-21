# Pack: eval-integrity

For fleets whose job is to measure something (a model, an agent, a pipeline) rather than only build it.
The rules are general: they also cover separation of duties (a reviewer can't see the author's notes),
secrets (a lane must never read `.env`) and compliance boundaries.

Templates: `PROTOCOL.md` (pre-registered, amendments appended), `rules/eval-integrity.md`,
`briefs/groundtruth.md`, `profiles/investigator.yaml` (the agent under test: model pinned, no fallback ever).

Harness scripts still to move here, as they are, with their coupling listed (WP-11): the isolated runner,
the canary that proves the isolation, extraction, and the quote-checking scorer, from Release Intelligence
`scripts/phase6/{lib.sh,run-natural.sh,canary.sh,extract.sh,scores.py}`.
