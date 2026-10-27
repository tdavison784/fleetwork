"""Packs: optional, composable bundles of templates, profiles, formulas and rules for one kind of use case.

    packs/<name>/pack.toml     [pack] name, description, requires; [vars] placeholder defaults;
                               [config.<table>] the .fleet.toml tables this pack owns, as {key: doc}
    packs/<name>/templates/    files rendered into the ledger directory by `fleet init`
    packs/<name>/README.md     what the pack is for and which adapters it expects

Search path, first match wins: the project's `[project] pack-path` entries (relative to .fleet.toml), then
$FLEETWORK_PACKS (os.pathsep-separated), then the kit's own packs/ directory. A project can therefore ship
its own pack, or override one, without touching the kit.
"""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fleetwork.errors import ConfigError

_ASSETS = Path(__file__).resolve().parents[1] / "_assets"
# Editable installs and the checkout use the repository's packs directly.
KIT_PACKS = _ASSETS / "packs" if _ASSETS.is_dir() else Path(__file__).resolve().parents[3] / "packs"


@dataclass
class Pack:
    name: str
    path: Path
    description: str = ""
    requires: list = field(default_factory=list)
    vars: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)     # .fleet.toml table -> {key: doc}

    @property
    def templates(self):
        return self.path / "templates"


def search_path(project=None):
    dirs = []
    if project is not None:
        dirs += [project.root / p for p in project.pack_path]
    dirs += [Path(p) for p in os.environ.get("FLEETWORK_PACKS", "").split(os.pathsep) if p]
    dirs.append(KIT_PACKS)
    return dirs


def load(name, dirs=None):
    for d in dirs or search_path():
        f = Path(d) / name / "pack.toml"
        if f.is_file():
            try:
                data = tomllib.loads(f.read_text())
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"{f}: {e}") from None
            meta = data.get("pack", {})
            if meta.get("name") != name:
                raise ConfigError(f"{f}: [pack] name must be {name!r}")
            return Pack(name=name, path=f.parent, description=meta.get("description", ""),
                        requires=list(meta.get("requires", [])), vars=dict(data.get("vars", {})),
                        config=dict(data.get("config", {})))
    raise ConfigError(f"pack {name!r} not found in: {', '.join(str(d) for d in dirs or search_path())}")


def resolve(names, dirs=None):
    """Packs in dependency order (requires first), each once; `core` is always first."""
    order, seen = [], set()

    def visit(n, chain):
        if n in seen:
            return
        if n in chain:
            raise ConfigError(f"pack cycle: {' -> '.join(chain + [n])}")
        p = load(n, dirs)
        for r in p.requires:
            visit(r, chain + [n])
        seen.add(n)
        order.append(p)

    for n in ["core", *[x for x in names if x != "core"]]:
        visit(n, [])
    return order
