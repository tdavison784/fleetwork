import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
import yaml

from fleetwork.errors import VersionConflict
from fleetwork.ledger import history, index, view
from fleetwork.ledger.model import HistoryEntry


def entries():
    return [
        HistoryEntry(1, "2026-01-01T00:00:00Z", "owner", "header", None, {"ledger": "test"}),
        HistoryEntry(2, "2026-01-01T00:00:01Z", "owner", "add", "T-1", {"title": "Café", "kind": "task"}),
        HistoryEntry(3, "2026-01-01T00:00:02Z", "owner", "edit", "T-1", {"note": "done"}),
    ]


def test_rebuild_is_byte_identical_and_view_round_trips(tmp_path):
    history.append_many(tmp_path, entries(), 0)
    ledger = index.rebuild(tmp_path)
    view.write(tmp_path, ledger)
    db_bytes = (tmp_path / index.FILENAME).read_bytes()
    view_bytes = (tmp_path / view.FILENAME).read_bytes()
    assert index.current_version(tmp_path) == 3
    assert index.load(tmp_path).to_dict() == ledger.to_dict()
    assert view_bytes.decode().splitlines()[0] == view.BANNER
    assert yaml.safe_load(view_bytes) == ledger.to_dict()
    assert index.rebuild(tmp_path).to_dict() == ledger.to_dict()
    view.write(tmp_path, ledger)
    assert (tmp_path / index.FILENAME).read_bytes() == db_bytes
    assert (tmp_path / view.FILENAME).read_bytes() == view_bytes
    with sqlite3.connect(tmp_path / index.FILENAME) as db:
        assert db.execute("SELECT COUNT(*) FROM history").fetchone() == (3,)


def test_rebuild_rejects_conflict_without_replacing_cache(tmp_path):
    good = entries()
    index.rebuild(tmp_path, good)
    before = (tmp_path / index.FILENAME).read_bytes()
    with pytest.raises(VersionConflict):
        index.rebuild(tmp_path, [good[0], good[0]])
    assert (tmp_path / index.FILENAME).read_bytes() == before


def test_missing_and_corrupt_cache_are_not_current(tmp_path):
    assert index.current_version(tmp_path) is None
    (tmp_path / index.FILENAME).write_bytes(b"not sqlite")
    assert index.current_version(tmp_path) is None


def test_failed_view_replacement_preserves_existing_file(tmp_path, monkeypatch):
    ledger = history.replay(entries())
    view.write(tmp_path, ledger)
    before = (tmp_path / view.FILENAME).read_bytes()
    def fail(*args):
        raise OSError("replacement failed")
    monkeypatch.setattr(view.os, "replace", fail)
    with pytest.raises(OSError):
        view.write(tmp_path, ledger)
    assert (tmp_path / view.FILENAME).read_bytes() == before
    assert not list(tmp_path.glob(".ledger-view-*"))


def test_direct_rebuild_holds_writer_lock_until_replacement(tmp_path, monkeypatch):
    initial = entries()
    history.append_many(tmp_path, initial, 0)
    entered, release, writer_started = Event(), Event(), Event()
    original = index._rebuild

    def paused_rebuild(directory, snapshot):
        entered.set()
        assert release.wait(5)
        return original(directory, snapshot)

    def append():
        writer_started.set()
        history.append(tmp_path, HistoryEntry(4, "t", "owner", "edit", "T-1", {"note": "new"}), 3)

    monkeypatch.setattr(index, "_rebuild", paused_rebuild)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rebuilding = pool.submit(index.rebuild, tmp_path)
        try:
            assert entered.wait(5)
            writer = pool.submit(append)
            assert writer_started.wait(5)
            with pytest.raises(TimeoutError):
                writer.result(timeout=0.1)
        finally:
            release.set()
        rebuilding.result(timeout=5)
        writer.result(timeout=5)
    assert len(history.read(tmp_path)) == 4
