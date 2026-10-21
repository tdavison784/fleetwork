import tomllib

import pytest
import yaml

from fleetwork import config
from fleetwork.errors import ConfigError
from fleetwork.ledger.model import Ledger
from fleetwork.runtime import cli, init, packs

VARS = {"owner": "owner-1", "provider": "p1", "runtime": "rt", "model": "m1"}


def test_core_first_and_requires_resolved():
    names = [p.name for p in packs.resolve(["eval-integrity", "git"])]
    assert names[0] == "core" and set(names) == {"core", "git", "eval-integrity"} and len(names) == 3


def test_every_shipped_pack_loads_and_declares_its_tables(kit_root):
    for f in (kit_root / "packs").glob("*/pack.toml"):
        p = packs.load(f.parent.name)
        assert p.description and (p.path / "README.md").is_file()
        for table, keys in p.config.items():
            assert table not in config.CORE_TABLES and isinstance(keys, dict)


def test_no_two_packs_claim_the_same_table(kit_root):
    owners = {}
    for f in (kit_root / "packs").glob("*/pack.toml"):
        for table in tomllib.loads(f.read_text()).get("config", {}):
            assert table not in owners, f"[{table}] claimed by {owners[table]} and {f.parent.name}"
            owners[table] = f.parent.name


def test_missing_variables_abort_before_writing(tmp_path):
    with pytest.raises(ConfigError) as e:
        init.init(tmp_path / "out", packs.resolve(["core"]), {"project": "x", "ledger": "y"})
    assert "owner" in str(e.value) and "model" in str(e.value)
    assert not (tmp_path / "out").exists()


def test_init_renders_all_packs_and_keeps_existing_files(tmp_path):
    ps = packs.resolve(["git", "providers", "eval-integrity"])
    v = init.variables_for(ps, "demo", "goal", VARS)
    written, kept = init.init(tmp_path, ps, v)
    assert {"FLEET.md", "seed.yaml", "rules/git.md", "rules/providers.md", "PROTOCOL.md",
            "profiles/investigator.yaml", "formulas/lane.yaml"} <= set(written)
    assert "{{" not in (tmp_path / "FLEET.md").read_text()
    assert "${lane}" in (tmp_path / "formulas/lane.yaml").read_text()    # formula placeholders survive init
    (tmp_path / "MISSION.md").write_text("mine")
    written2, kept2 = init.init(tmp_path, ps, v)
    assert "MISSION.md" in kept2 and (tmp_path / "MISSION.md").read_text() == "mine"


def test_rendered_seed_is_a_valid_ledger(tmp_path):
    ps = packs.resolve(["core"])
    init.init(tmp_path, ps, init.variables_for(ps, "demo", "goal", VARS))
    seed = yaml.safe_load((tmp_path / "seed.yaml").read_text())
    led = Ledger.from_dict({**seed["header"], "items": seed["items"]})
    assert led.header.ledger == "goal" and led.items[0].id == "W-0001" and led.items[0].kind == "decision"
    assert led.header.roles["owner"]["actors"] == ["owner-1"]
    for name in ("commander", "builder", "reviewer"):
        prof = yaml.safe_load((tmp_path / "profiles" / f"{name}.yaml").read_text())
        assert prof["provider"] == "p1" and prof["env"]["DO_NOT_TRACK"] == "1"


def test_template_conflicts_between_packs_are_errors(tmp_path):
    for name in ("core", "dup"):
        d = tmp_path / "packs" / name
        (d / "templates").mkdir(parents=True)
        (d / "pack.toml").write_text(f'[pack]\nname = "{name}"\ndescription = "x"\n')
        (d / "templates" / "FLEET.md").write_text("x")
    ps = packs.resolve(["dup"], [tmp_path / "packs"])
    with pytest.raises(ConfigError, match="both core and dup"):
        init.plan(ps, {})


@pytest.mark.parametrize("example", ["go-rcana", "two-provider-eval"])
def test_examples_render_completely(example, kit_root, tmp_path):
    cfg = config.load(kit_root / "examples" / example / ".fleet.toml")
    ps = packs.resolve(cfg.packs, packs.search_path(cfg))
    written, _ = init.init(tmp_path, ps, init.variables_for(ps, cfg.name, cfg.store.ledger, cfg.vars))
    assert written
    for table in cfg.tables:
        assert any(table in p.config for p in ps), f"{example}: [{table}] is owned by no pack it uses"


def test_fleet_cli_init_and_packs(tmp_path, capsys):
    args = ["init", "--dir", str(tmp_path / "f"), "--packs", "core,git"] + [f"--var={k}={v}" for k, v in VARS.items()]
    assert cli.main(args) == 0
    assert (tmp_path / "f" / "rules" / "git.md").is_file()
    assert cli.main(["packs"]) == 0
    out = capsys.readouterr().out
    for name in ("core", "git", "providers", "eval-integrity"):
        assert name in out


def test_fleet_lane_commands_point_at_their_work_package(project, capsys, monkeypatch, tmp_path):
    project()
    monkeypatch.chdir(tmp_path)
    assert cli.main(["lane", "start", "W-0002", "--actor", "a"]) == 3
    assert "WP-09" in capsys.readouterr().err
