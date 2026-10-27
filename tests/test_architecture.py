"""Structural rules the whole kit relies on (docs/ARCHITECTURE.md). If one fails, fix the code, not the test."""
import ast
import re
from pathlib import Path

import pytest

from fleetwork import adapters
from fleetwork.adapters.base import PROTOCOLS

SRC = Path(__file__).resolve().parents[1] / "src" / "fleetwork"
DOCS = Path(__file__).resolve().parents[1] / "docs"

CORE_FILES = sorted((SRC / "ledger").glob("*.py")) + [SRC / "config.py", SRC / "errors.py"]
# Names that must never appear in the core: providers, harnesses, multiplexers, trackers, projects.
FORBIDDEN = re.compile(
    r"claude|anthropic|\bglm\b|z\.ai|\bzai\b|herdr|tmux|worktree|github|\bgh\b|beads|\bbd\b|gascity|jira|linear"
    r"|release.intelligence|\bri-|go-rcana",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_names_nothing_specific(path):
    hits = [f"{path.name}:{n}: {line.strip()}" for n, line in enumerate(path.read_text().splitlines(), 1)
            if FORBIDDEN.search(line)]
    assert not hits, "core names a specific provider/harness/tracker/project:\n" + "\n".join(hits)


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


@pytest.mark.parametrize("path", sorted((SRC / "ledger").glob("*.py")), ids=lambda p: p.name)
def test_ledger_imports_point_down(path):
    for mod in _imports(path):
        assert not mod.startswith("fleetwork.runtime"), f"{path.name} imports {mod}"
        if mod.startswith("fleetwork.adapters"):
            assert mod in ("fleetwork.adapters", "fleetwork.adapters.base"), \
                f"{path.name} imports a concrete adapter ({mod}); use the registry"


@pytest.mark.parametrize("path", sorted((SRC / "adapters").rglob("*.py")), ids=lambda p: p.parent.name + "/" + p.name)
def test_adapters_do_not_import_runtime(path):
    for mod in _imports(path):
        assert not mod.startswith("fleetwork.runtime"), f"{path} imports {mod}"


ADAPTERS = [(kind, name) for kind in adapters.KINDS for name in adapters.available(kind)]


@pytest.mark.parametrize("kind,name", ADAPTERS, ids=lambda x: str(x))
def test_every_adapter_registers_and_implements_its_protocol(kind, name):
    cls = adapters.get(kind, name)
    assert cls.adapter_kind == kind and cls.adapter_name == name
    proto = PROTOCOLS[kind]
    missing = [m for m in vars(proto) if not m.startswith("_") and callable(getattr(proto, m, None))
               and not callable(getattr(cls, m, None))]
    assert not missing, f"{kind}:{name} lacks {missing}"


def test_every_kind_has_a_protocol():
    assert set(PROTOCOLS) == set(adapters.KINDS)


def test_ledger_cli_covers_the_design_commands():
    from fleetwork.ledger.cli import COMMANDS

    design = (DOCS / "LEDGER-DESIGN.md").read_text()
    section = design.split("## 6. The ledger CLI", 1)[1].split("### 6.1", 1)[0]
    named = set(re.findall(r"`ledger ([a-z][a-z-]*)", section))
    assert named <= set(COMMANDS), f"design commands missing from cli.COMMANDS: {sorted(named - set(COMMANDS))}"


def test_every_work_package_named_in_code_exists():
    plan = (DOCS / "WORKPACKAGES.md").read_text()
    declared = set(re.findall(r"^## (WP-\d\d):", plan, re.M))
    used = set()
    for p in SRC.rglob("*.py"):
        used |= set(re.findall(r"WP-\d\d", p.read_text()))
    assert used <= declared, f"code cites undeclared work packages: {sorted(used - declared)}"
