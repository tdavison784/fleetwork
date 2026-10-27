"""End-to-end storage contract tests through the shipped CLIs."""
import json
import os
import subprocess
import sys

import pytest
import yaml

from fleetwork.errors import VersionConflict
from fleetwork.ledger import history
from fleetwork.ledger.model import HistoryEntry


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run_module(module, *args, cwd=None):
    env = {**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")}
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def fleet_init(ledger_dir):
    return run_module(
        "fleetwork.runtime.cli",
        "init",
        "--dir",
        ledger_dir,
        "--packs",
        "core",
        "--var",
        "owner=owner",
        "--var",
        "provider=local",
        "--var",
        "runtime=headless",
        "--var",
        "model=test-model",
    )


def ledger(ledger_dir, *args):
    return run_module("fleetwork.ledger.cli", "--ledger", ledger_dir, *args)


def apply(ledger_dir, source, actor="owner"):
    return ledger(ledger_dir, "apply", source, "--actor", actor)


def make_ledger(tmp_path):
    ledger_dir = tmp_path / "store" / "demo"
    initialized = fleet_init(ledger_dir)
    assert initialized.returncode == 0, initialized.stderr
    seeded = apply(ledger_dir, ledger_dir / "seed.yaml")
    assert seeded.returncode == 0, seeded.stderr
    return ledger_dir


def write_batch(path, batch):
    path.write_text(yaml.safe_dump(batch, sort_keys=False), encoding="utf-8")
    return path


def test_init_apply_and_rebuild_reproduce_index_and_view(tmp_path):
    ledger_dir = tmp_path / "store" / "demo"
    initialized = fleet_init(ledger_dir)
    assert initialized.returncode == 0, initialized.stderr
    assert (ledger_dir / "seed.yaml").is_file()

    seeded = apply(ledger_dir, ledger_dir / "seed.yaml")
    assert seeded.returncode == 0, seeded.stderr
    for name in ("history.jsonl", "ledger.db", "LEDGER.yaml"):
        assert (ledger_dir / name).is_file()

    history_before = (ledger_dir / "history.jsonl").read_bytes()
    index_before = (ledger_dir / "ledger.db").read_bytes()
    view_before = (ledger_dir / "LEDGER.yaml").read_bytes()
    assert view_before.decode("utf-8").splitlines()[0] == "# GENERATED from history.jsonl by `ledger` — do not edit; author changes with `ledger apply`."

    rebuilt = ledger(ledger_dir, "rebuild")
    assert rebuilt.returncode == 0, rebuilt.stderr
    assert (ledger_dir / "history.jsonl").read_bytes() == history_before
    assert (ledger_dir / "ledger.db").read_bytes() == index_before
    assert (ledger_dir / "LEDGER.yaml").read_bytes() == view_before


def test_apply_edits_items_and_rebuild_discards_hand_edits_to_view(tmp_path):
    ledger_dir = make_ledger(tmp_path)
    first = write_batch(
        tmp_path / "first.yaml",
        {"items": [{"id": "W-9001", "title": "Before", "kind": "task", "note": "keep?"}]},
    )
    result = apply(ledger_dir, first)
    assert result.returncode == 0, result.stderr

    edit = write_batch(
        tmp_path / "edit.yaml",
        {"items": [{"id": "W-9001", "title": "After", "note": None}]},
    )
    result = apply(ledger_dir, edit)
    assert result.returncode == 0, result.stderr

    current = yaml.safe_load((ledger_dir / "LEDGER.yaml").read_text(encoding="utf-8"))
    item = next(item for item in current["items"] if item["id"] == "W-9001")
    assert item["title"] == "After"
    assert "note" not in item

    (ledger_dir / "LEDGER.yaml").write_text("items: []\n", encoding="utf-8")
    rebuilt = ledger(ledger_dir, "rebuild")
    assert rebuilt.returncode == 0, rebuilt.stderr
    regenerated = (ledger_dir / "LEDGER.yaml").read_text(encoding="utf-8")
    assert regenerated.startswith("# GENERATED from history.jsonl")
    state = yaml.safe_load(regenerated)
    assert any(item["id"] == "W-9001" and item["title"] == "After" for item in state["items"])


def test_stale_history_writer_gets_version_conflict(tmp_path):
    ledger_dir = make_ledger(tmp_path)
    entries = history.read(ledger_dir)
    expected_v = len(entries)
    current = HistoryEntry(
        expected_v + 1,
        "2026-01-01T00:00:00Z",
        "owner",
        "edit",
        "W-0001",
        {"note": "first writer"},
    )
    stale = HistoryEntry(
        expected_v + 1,
        "2026-01-01T00:00:01Z",
        "owner",
        "edit",
        "W-0001",
        {"note": "stale writer"},
    )
    history.append(ledger_dir, current, expected_v)
    after_first = (ledger_dir / "history.jsonl").read_bytes()
    with pytest.raises(VersionConflict):
        history.append(ledger_dir, stale, expected_v)
    assert (ledger_dir / "history.jsonl").read_bytes() == after_first


def test_apply_rejects_status_edits_and_non_owner_header_changes(tmp_path):
    ledger_dir = make_ledger(tmp_path)
    status_edit = write_batch(
        tmp_path / "status.yaml",
        {"items": [{"id": "W-0001", "status": "done"}]},
    )
    before_history = (ledger_dir / "history.jsonl").read_bytes()
    refused = apply(ledger_dir, status_edit)
    assert refused.returncode != 0
    assert (ledger_dir / "history.jsonl").read_bytes() == before_history

    header_edit = write_batch(tmp_path / "header.yaml", {"header": {"never": ["push", "sneak"]}})
    refused = apply(ledger_dir, header_edit, actor="unrecognized")
    assert refused.returncode != 0
    assert (ledger_dir / "history.jsonl").read_bytes() == before_history


def test_invalid_later_entry_does_not_partially_apply_batch(tmp_path):
    ledger_dir = make_ledger(tmp_path)
    batch = write_batch(
        tmp_path / "mixed.yaml",
        {
            "items": [
                {"id": "W-9010", "title": "Would be valid", "kind": "task"},
                {"id": "W-0001", "status": "done"},
            ]
        },
    )
    old_history = (ledger_dir / "history.jsonl").read_bytes()
    old_index = (ledger_dir / "ledger.db").read_bytes()
    old_view = (ledger_dir / "LEDGER.yaml").read_bytes()

    refused = apply(ledger_dir, batch)
    assert refused.returncode != 0
    assert (ledger_dir / "history.jsonl").read_bytes() == old_history
    assert (ledger_dir / "ledger.db").read_bytes() == old_index
    assert (ledger_dir / "LEDGER.yaml").read_bytes() == old_view
    assert not any(
        item.get("id") == "W-9010"
        for item in yaml.safe_load((ledger_dir / "LEDGER.yaml").read_text(encoding="utf-8"))["items"]
    )
