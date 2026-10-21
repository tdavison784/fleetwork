import pytest

from fleetwork.ledger import cli


def test_every_command_parses_help():
    for name in cli.COMMANDS:
        with pytest.raises(SystemExit) as e:
            cli.main([name, "--help"])
        assert e.value.code == 0


def test_unbuilt_command_points_at_its_work_package(capsys, tmp_path):
    assert cli.main(["--ledger", str(tmp_path), "lint"]) == 3
    err = capsys.readouterr().err
    assert "ledger lint" in err and "WP-02" in err and "LEDGER-DESIGN" in err
