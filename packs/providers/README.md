# Pack: providers

For fleets that run on more than one model provider, or on one provider with usage windows. Adapters:
provider `claude-code`, `zai-quota`, `none`; the fleet guard (`guard/`, run with `fleet guard`). Declare the
providers in the ledger header; give profiles a `fallback`. Adds `rules/providers.md`.

The guard is v4 today and still takes Release Intelligence defaults on its command line; WP-06 turns it into
v5, which calls `ledger ready` and reads this pack's `[guard]` table.
