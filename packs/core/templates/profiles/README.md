# Profiles: who does the work

A profile is the worker the runtime starts for a lane. A lane names its profile in its ledger item
(`run.profile`). Profiles are reusable across lanes; edit them here, not in briefs, so a brief can never
forget a rule.

| Key | Meaning |
|---|---|
| `runtime` | runtime adapter that starts the agent |
| `provider` | a provider declared in the ledger header |
| `model` | model string passed to the runtime, opaque to the ledger |
| `fallback` | `{provider, model, when}`: who continues the lane when `when` holds (e.g. a usage window) |
| `permission-mode` | the harness's permission mode |
| `env` | environment set before the agent starts (`DO_NOT_TRACK` is always set) |
| `never` | extra entries for the `never` floor, on top of the ledger header's |
| `hooks` | enforcement hooks the enforcement adapter installs |
| `context-checkpoint` | percent of context at which the agent is told to save its status |
| `read-only` | true: the agent may not write in its workspace |
