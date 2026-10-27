"""Project configuration: the one file a project writes, `.fleet.toml` at its repository root.

    [project]   name, packs, pack-path              core (this module)
    [store]     adapter, ledger, + adapter config   core (this module)
    [vars]      values for template placeholders    core (fleet init)
    [<pack>]    one table per pack, e.g. [git]      owned and validated by that pack (packs/<pack>/pack.toml)

The core reads only [project], [store] and [vars]; every other table is handed to its pack untouched. That is
what lets a new use case add a pack without editing the core. Ledger-level policy (providers, roles,
delegations, limits) is NOT here: it lives in the ledger header (LEDGER-DESIGN §4.1), so it is versioned in
the history log with every other ledger change.
"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fleetwork.errors import ConfigError

FILENAME = ".fleet.toml"
CORE_TABLES = ("project", "store", "vars")


@dataclass
class StoreConfig:
    adapter: str
    ledger: str
    options: dict = field(default_factory=dict)  # the adapter's own keys, e.g. path for `dir`


@dataclass
class ProjectConfig:
    root: Path                                     # directory holding .fleet.toml
    name: str
    packs: list
    store: StoreConfig
    pack_path: list = field(default_factory=list)  # extra pack directories, relative to root
    vars: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)     # pack-owned tables, verbatim

    def table(self, pack):
        """The config table a pack owns ({} if the project sets none)."""
        return self.tables.get(pack, {})

    def ledger_dir(self):
        """The ledger directory, opened through the configured store adapter."""
        from fleetwork import adapters

        opts = dict(self.store.options)
        if "path" in opts:
            opts["path"] = str((self.root / Path(opts["path"]).expanduser()).resolve())
        return adapters.create("store", self.store.adapter, **opts).open(self.store.ledger)


def find(start=None):
    """The nearest .fleet.toml at or above `start` (default: cwd), or None."""
    d = Path(start or Path.cwd()).resolve()
    for p in (d, *d.parents):
        if (p / FILENAME).is_file():
            return p / FILENAME
    return None


def load(path=None):
    path = Path(path) if path else find()
    if path is None:
        raise ConfigError(f"no {FILENAME} here or in any parent directory")
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"{path}: {e}") from None
    return parse(data, path.parent)


def parse(data, root):
    proj, store = data.get("project"), data.get("store")
    if not isinstance(proj, dict) or not proj.get("name"):
        raise ConfigError("[project] needs name")
    if not isinstance(store, dict) or not store.get("adapter") or not store.get("ledger"):
        raise ConfigError("[store] needs adapter and ledger")
    packs = proj.get("packs", ["core"])
    if "core" not in packs:
        packs = ["core", *packs]
    opts = {k: v for k, v in store.items() if k not in ("adapter", "ledger")}
    return ProjectConfig(
        root=Path(root),
        name=proj["name"],
        packs=list(packs),
        store=StoreConfig(store["adapter"], store["ledger"], opts),
        pack_path=list(proj.get("pack-path", [])),
        vars=dict(data.get("vars", {})),
        tables={k: v for k, v in data.items() if k not in CORE_TABLES},
    )
