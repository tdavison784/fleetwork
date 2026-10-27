from fleetwork.ledger.cli import main


def test_apply_rejects_duplicate_yaml_keys_without_writing(tmp_path, capsys):
    batch = tmp_path / "batch.yaml"
    batch.write_text(
        "header:\n  roles:\n    owner:\n      actors: [owner]\n"
        "items:\n  - id: W-1\n    title: First\n    title: Second\n",
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger"

    assert main(["--ledger", str(ledger), "apply", str(batch), "--actor", "owner"]) == 1
    assert "duplicate key 'title'" in capsys.readouterr().err
    assert not (ledger / "history.jsonl").exists()
