"""The `fleet` command (ROADMAP 'The kit').

  fleet init                 render pack templates into the ledger directory           working
  fleet packs                list the packs on the search path                         working
  fleet lane start|watch|merge                                                         WP-09, WP-10
  fleet guard [-- ARGS]      run the fleet guard (guard/fleet_guard.py) with ARGS      working (v4, until WP-06)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from fleetwork import config
from fleetwork.errors import ConfigError, FleetworkError, exit_code
from fleetwork.runtime import init as init_mod
from fleetwork.runtime import lanes, packs

_ASSETS = Path(__file__).resolve().parents[1] / "_assets"
GUARD = (_ASSETS / "guard" / "fleet_guard.py" if _ASSETS.is_dir()
         else Path(__file__).resolve().parents[3] / "guard" / "fleet_guard.py")


def _kv(pairs):
    out = {}
    for p in pairs:
        if "=" not in p:
            raise ConfigError(f"--var wants name=value, got {p!r}")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def cmd_init(a):
    project = None
    if a.dir is None or a.config:
        project = config.load(a.config)
    names = a.packs.split(",") if a.packs else (project.packs if project else ["core"])
    resolved = packs.resolve(names, packs.search_path(project))
    target = Path(a.dir) if a.dir else project.ledger_dir()
    variables = init_mod.variables_for(
        resolved,
        project.name if project else a.project or target.name,
        project.store.ledger if project else target.name,
        project.vars if project else {},
        _kv(a.var),
    )
    written, kept = init_mod.init(target, resolved, variables, force=a.force)
    print(f"fleet init: {target} (packs: {', '.join(p.name for p in resolved)})")
    for rel in written:
        print(f"  wrote {rel}")
    for rel in kept:
        print(f"  kept  {rel} (exists; --force to overwrite)")
    print("next: fill MISSION.md, then `ledger apply seed.yaml --actor <owner>`")
    return 0


def cmd_packs(a):
    project = None
    try:
        project = config.load(a.config) if a.config or config.find() else None
    except ConfigError:
        pass
    seen = set()
    for d in packs.search_path(project):
        if not Path(d).is_dir():
            continue
        for f in sorted(Path(d).glob("*/pack.toml")):
            name = f.parent.name
            if name in seen:
                continue
            seen.add(name)
            p = packs.load(name, [d])
            print(f"{name:<16} {p.description}  [{d}]")
    return 0


def cmd_lane(a):
    project = config.load(a.config)
    ledger_dir = project.ledger_dir()
    if a.lane_cmd == "start":
        return lanes.start(project, ledger_dir, a.id, a.actor)
    if a.lane_cmd == "watch":
        return lanes.watch(project, ledger_dir, a.id, a.timeout)
    return lanes.merge(project, ledger_dir, a.id, a.actor)


def cmd_guard(a):
    # The guard reads its key files itself; nothing from here is logged or passed on but ARGS.
    return subprocess.call([sys.executable, str(GUARD), *a.args], env={**os.environ, "DO_NOT_TRACK": "1"})


def build_parser():
    ap = argparse.ArgumentParser(prog="fleet", description="fleetwork fleet runtime")
    ap.add_argument("--config", help="path to .fleet.toml (default: nearest one above cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="render pack templates into a ledger directory")
    p.add_argument("--dir", help="target directory (default: the ledger directory from .fleet.toml)")
    p.add_argument("--packs", help="comma-separated packs (default: [project] packs, else core)")
    p.add_argument("--project", help="project name when there is no .fleet.toml")
    p.add_argument("--var", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("packs", help="list available packs")
    p.set_defaults(fn=cmd_packs)

    p = sub.add_parser("lane", help="lane lifecycle")
    ls = p.add_subparsers(dest="lane_cmd", required=True)
    for name in ("start", "watch", "merge"):
        q = ls.add_parser(name)
        q.add_argument("id", help="ledger item id of the lane")
        if name == "watch":
            q.add_argument("--timeout", type=int)
        else:
            q.add_argument("--actor", required=True)
    p.set_defaults(fn=cmd_lane)

    p = sub.add_parser("guard", help="run the fleet guard; arguments after -- go to it")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_guard)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.cmd == "guard" and a.args[:1] == ["--"]:
        a.args = a.args[1:]
    try:
        return a.fn(a) or 0
    except FleetworkError as e:
        print(f"fleet: {e}", file=sys.stderr)
        return exit_code(e)


if __name__ == "__main__":
    sys.exit(main())
