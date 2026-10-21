import pytest

from fleetwork import config
from fleetwork.errors import ConfigError


def test_load_separates_core_and_pack_tables(project):
    cfg = project(packs=["git"], extra='[git]\nintegration-branch = "main"\n')
    assert cfg.name == "demo"
    assert cfg.packs == ["core", "git"]
    assert cfg.store.adapter == "dir" and cfg.store.ledger == "goal" and cfg.store.options == {"path": "fleet"}
    assert cfg.table("git") == {"integration-branch": "main"}
    assert "project" not in cfg.tables and "vars" not in cfg.tables
    assert cfg.vars["owner"] == "owner-1"


def test_ledger_dir_is_opened_through_the_store(project, tmp_path):
    d = project().ledger_dir()
    assert d == (tmp_path / "fleet" / "goal").resolve() and d.is_dir()


def test_find_walks_up(project, tmp_path):
    project()
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert config.find(sub) == tmp_path / ".fleet.toml"


@pytest.mark.parametrize("data", [{}, {"project": {"name": "x"}}, {"project": {"name": "x"}, "store": {"adapter": "dir"}}])
def test_missing_required_keys(data, tmp_path):
    with pytest.raises(ConfigError):
        config.parse(data, tmp_path)
