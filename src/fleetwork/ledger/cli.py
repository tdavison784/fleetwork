"""The `ledger` command (LEDGER-DESIGN §6).

COMMANDS is the single table of subcommands: name -> (work package, spec section, help, argument adder).
To build a command, replace its `_todo` handler in HANDLERS with a real one; don't restructure the table.
Every mutating command takes --actor; every command takes --ledger DIR (default: from .fleet.toml).
"""
import argparse
import sys
from pathlib import Path

import yaml

from fleetwork.errors import ConfigError, FleetworkError, NotImplementedYet, exit_code


def _actor(p):
    p.add_argument("--actor", required=True, help="who is making the change (mapped to a role, §5)")


def _why(p, required=False):
    p.add_argument("--why", required=required, help="reason; for owner-delegated acts, the owner's words and time")


def _args_lint(p):
    p.add_argument("--json", action="store_true")


def _args_apply(p):
    p.add_argument("file", help="YAML batch of items and/or header changes")
    _actor(p)


def _args_rebuild(p):
    pass


def _args_ready(p):
    p.add_argument("--provider")
    p.add_argument("--auto-start", action="store_true")
    p.add_argument("--json", action="store_true")


def _args_gates(p):
    sub = p.add_subparsers(dest="gates_cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("resolve")
    r.add_argument("id")
    r.add_argument("index", type=int)
    _actor(r)
    _why(r, required=True)


def _args_add(p):
    p.add_argument("--formula")
    p.add_argument("--var", action="append", default=[], metavar="K=V")
    p.add_argument("--file", help="YAML item(s) to add")
    _actor(p)
    _why(p)


def _args_claim(p):
    p.add_argument("id")
    p.add_argument("agent")
    _actor(p)


def _args_close(p):
    p.add_argument("id")
    p.add_argument("--merged")
    p.add_argument("--result")
    _actor(p)


def _args_decide(p):
    p.add_argument("id")
    _actor(p)
    _why(p, required=True)


def _args_windows(p):
    p.add_argument("--json", action="store_true")


def _args_diff(p):
    p.add_argument("v1", type=int)
    p.add_argument("v2", type=int)


def _args_blame(p):
    p.add_argument("id")


def _args_estimate(p):
    p.add_argument("kind")
    p.add_argument("--provider")


def _args_migrate(p):
    p.add_argument("v1_file")
    p.add_argument("--git-repo", help="replay this repository's history of the file as log entries")
    p.add_argument("--out", required=True, help="new ledger directory")


def _args_export(p):
    p.add_argument("--to", required=True, help="mirror adapter name (fleetwork/adapters/mirrors/)")
    p.add_argument("--dest", required=True, help="where the mirror writes (its own meaning per adapter)")


COMMANDS = {
    "lint":         ("WP-02", "§6", "check the ledger against the schema and rules", _args_lint),
    "apply":        (None, "§4.6", "ingest a hand-written YAML batch as history entries", _args_apply),
    "rebuild":      (None, "§4.6", "rebuild ledger.db and LEDGER.yaml from history.jsonl", _args_rebuild),
    "ready":        ("WP-02", "§4.3", "derived ready / offerable / auto-startable sets", _args_ready),
    "gates":        ("WP-07", "§6", "check or resolve gates", _args_gates),
    "add":          ("WP-07", "§4.4", "add items, optionally from a formula", _args_add),
    "claim":        ("WP-07", "§6", "claim an item for an agent (compare-and-set)", _args_claim),
    "close":        ("WP-07", "§6", "close an item with its merge or result", _args_close),
    "decide":       ("WP-07", "§5", "record a decision", _args_decide),
    "windows":      ("WP-04", "§6", "derived window log", _args_windows),
    "diff":         ("WP-04", "§6", "changes between two versions", _args_diff),
    "blame":        ("WP-04", "§6", "every change to one item", _args_blame),
    "estimate":     ("WP-04", "§6", "budget median/p90 for a kind of item", _args_estimate),
    "migrate":      ("WP-03", "§9", "convert a v1 LEDGER.yaml into a v2 ledger directory", _args_migrate),
    "export":       ("WP-12", "§6", "one-way export into a mirror adapter", _args_export),
}


def _todo(name):
    wp, section = COMMANDS[name][:2]

    def handler(args):
        raise NotImplementedYet(f"ledger {name}", wp, f"LEDGER-DESIGN {section}")

    return handler


HANDLERS = {name: _todo(name) for name in COMMANDS}


class _BatchLoader(yaml.SafeLoader):
    """Reject ambiguous authoring input instead of silently dropping a key."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            # YAML merge keys intentionally allow an explicit key to override
            # a value from an anchor; only repeated authored keys are ambiguous.
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
                seen.add(key)
            except TypeError:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    "unhashable key", key_node.start_mark,
                ) from None
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    f"duplicate key {key!r}", key_node.start_mark,
                )
        return super().construct_mapping(node, deep=deep)


def _apply(args):
    from fleetwork.ledger import store

    try:
        batch = yaml.load(Path(args.file).read_text(encoding="utf-8"), Loader=_BatchLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"{args.file}: {exc}") from None
    changes = store.apply(store.locate(args.ledger), batch, args.actor)
    print(f"applied {len(changes)} change(s)")


def _rebuild(args):
    from fleetwork.ledger import store

    store.rebuild(store.locate(args.ledger))
    print("rebuilt ledger index and view")


HANDLERS.update(apply=_apply, rebuild=_rebuild)


def build_parser():
    ap = argparse.ArgumentParser(prog="ledger", description="fleetwork ledger (docs/LEDGER-DESIGN.md)")
    ap.add_argument("--ledger", help="ledger directory (default: the one named by the nearest .fleet.toml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (_, _, help_, add_args) in COMMANDS.items():
        add_args(sub.add_parser(name, help=help_))
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.cmd](args) or 0
    except FleetworkError as e:
        print(f"ledger: {e}", file=sys.stderr)
        return exit_code(e)


if __name__ == "__main__":
    sys.exit(main())
