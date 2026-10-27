# Rules: providers (pack)

- Items say which providers may execute them (`run.providers`). An item without your provider is not yours,
  even if it is ready. Items pinned to one provider (the model under test, a provider's own data) are never
  continued on another.
- When a provider's window fills, the guard pauses working agents and hands lanes to their profile's
  `fallback`, in the same workspace. The continuing agent reads the brief and status file, commits with the
  `{{fallback_tag}}` subject prefix, and never starts or stops agents on the paused provider.
- At handback, the fallback agent stops starting work, finishes or cleanly aborts what is in flight, saves,
  and replies `HANDBACK DONE`. The returning agent reviews every `{{fallback_tag}}` commit before building on it.
- A `window` gate may hold any item, including provider-pinned ones, until its provider has the headroom it
  names.
