# Pack: providers

This is an optional pack for projects that choose provider usage-window management. The ledger core is designed
to stay provider-neutral; choosing this pack adds provider-related templates and config, but does not start the
guard. In the current CLI, the guard runs only when explicitly invoked with `fleet guard`.

The pack includes provider entries for `claude-code`, `zai-quota` and `none`, plus the fleet guard (`guard/`).
Declare providers in the ledger header and give profiles a `fallback` where appropriate. Adds
`rules/providers.md`. The `claude-code` and `zai-quota` adapter modules are still WP-06 stubs; their presence
does not mean those runtime adapters are implemented.

The guard is v4 today and still takes the pilot project's defaults on its command line; WP-06 turns it into
v5, which calls `ledger ready` and reads this pack's `[guard]` table.
