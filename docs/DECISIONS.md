# Decisions

Append-only. Each entry: date, who decided, the decision, why, where it applies. Owner decisions are quoted or
attributed; structural choices made while building are marked as such and can be overturned by the owner.

## 2026-10-21 — owner

- **The ledger is the core** of a reusable fleet kit; everything else wraps around it. It must not be designed
  around Release Intelligence ("this system needs to be re-usable for all other projects as well").
- **Storage:** the ledger is never stored in the product repository and not one commit per change ("multi
  hundred commit PRs won't fly"). The history log is the truth, SQLite the index, YAML a generated view
  (LEDGER-DESIGN §4.6).
- **Window gates** may delay items automatically, including provider-pinned ones.
- **Human gates:** the commander may resolve them on the owner's say-so, with the quote recorded.
- **Delegations:** a standing rule set in the ledger header says what the commander may do on the owner's
  behalf, with a `never` floor (push, force-delete-branch, answer-trust-dialog, edit-delegations).
- **Not adopted:** gascity + beads as the substrate (fleetpilot report); ideas taken instead (ROADMAP).

## 2026-10-21 — structural choices (scaffold)

- **One project file, `.fleet.toml`.** ROADMAP named a `fleet.toml` and LEDGER-DESIGN a `.fleet.toml` pointer;
  they are one file. Core tables `[project]`, `[store]`, `[vars]`; every other table belongs to a pack. Ledger
  policy (providers, roles, delegations) stays in the ledger header so its changes are in the history log.
- **`ledger export --to <mirror>`** replaces `ledger export-beads`, with a `mirror` adapter kind, so the core
  names no tracker (LEDGER-DESIGN §8). LEDGER-DESIGN §6 updated.
- **Packs** (`core`, `git`, `providers`, `eval-integrity`) carry use-case templates, profiles and rules; a
  project can add its own via `[project] pack-path`. From the lane-design discussion (core + packs + project
  config); the profile/lane split itself is WP-08 and awaits the owner.
- **Three placeholder syntaxes** by fill time: `{{x}}` at `fleet init`, `${x}` at formula expansion, `<x>` by
  hand.
- **Packaging:** `src/` layout, setuptools, console scripts `ledger` and `fleet`; tests run from the checkout
  with `PYTHONPATH=src` (pytest config does this).
