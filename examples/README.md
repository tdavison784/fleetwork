# examples/

Each directory is what one project adds to adopt fleetwork: a `.fleet.toml` at its repository root and,
optionally, a first apply batch. They double as test fixtures (tests/test_examples.py renders every example
with `fleet init` and parses every batch with the ledger model).

| Example | Shows | Packs |
|---|---|---|
| `go-rcana/` | The portability test (LEDGER-DESIGN §9 step 3): one provider, no fallback, a game-engine milestone as a queue | core, git |
| `two-provider-eval/` | Two providers with usage-window handoff, and a sealed evaluation of the agent under test | core, git, providers, eval-integrity |

To start a new use case: copy the closest example's `.fleet.toml` into your repository, change `[project]`,
`[store]` and `[vars]`, keep the packs you need, then run `fleet init`.
