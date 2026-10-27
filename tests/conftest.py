"""Shared fixtures. Reuse these instead of building ledgers, projects or packs by hand in each test."""
from pathlib import Path

import pytest
import yaml

KIT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def kit_root():
    return KIT


@pytest.fixture
def v1_ledger():
    """Load a v1 ledger fixture by name: v1_ledger("pilot-a") -> dict."""
    def load(name):
        return yaml.safe_load((FIXTURES / "v1" / f"{name}.yaml").read_text())
    return load


@pytest.fixture
def v2_ledger():
    """Load a v2 sample (an apply batch with a header) as a fleetwork.ledger.model.Ledger."""
    from fleetwork.ledger.model import Ledger

    def load(name):
        d = yaml.safe_load((FIXTURES / "v2" / f"{name}.yaml").read_text())
        return Ledger.from_dict({**d.get("header", {}), "items": d.get("items", [])})
    return load


@pytest.fixture
def project(tmp_path):
    """Write a .fleet.toml into a temp project and return its fleetwork.config.ProjectConfig.

    project(packs=["core","git"], vars={...}, extra="[git]\\n...") ; the store is a `dir` store at tmp/fleet."""
    from fleetwork import config

    def make(packs=("core",), vars=None, extra=""):
        vars = {"owner": "owner-1", "provider": "p1", "runtime": "rt", "model": "m1", **(vars or {})}
        lines = ['[project]', 'name = "demo"', f'packs = {list(packs)!r}'.replace("'", '"'),
                 '[store]', 'adapter = "dir"', 'ledger = "goal"', 'path = "fleet"', '[vars]']
        lines += [f'{k} = "{v}"' for k, v in vars.items()]
        (tmp_path / ".fleet.toml").write_text("\n".join(lines) + "\n" + extra)
        return config.load(tmp_path / ".fleet.toml")
    return make
