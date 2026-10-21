# Pack: core

Always included. It is the method with every use-case detail taken out: a goal, a ledger, a commander, lanes
with briefs and status files, profiles for who does the work, and the rules that make agents replaceable.

`fleet init` renders `templates/` into the ledger directory. Files whose names start with `_` are templates
for the commander to copy (one per lane), not files to fill in place.

Placeholders, by when they are filled:

| Syntax | Filled by | Example |
|---|---|---|
| `{{name}}` | `fleet init`, from pack `[vars]`, `.fleet.toml` `[vars]` and `--var` | `{{owner}}` |
| `${name}` | `ledger add --formula`, from `--var` | `${lane}` |
| `<what>` | a person or the commander, by hand | `<one-line goal>` |
