import pytest

from fleetwork.errors import ConfigError
from fleetwork.ledger import history, index, store
from fleetwork.ledger.model import HistoryEntry


def seeded(path):
    store.apply(path, {"header": {"roles": {"owner": {"actors": ["owner"]}}},
                       "items": [{"id": "A-1", "title": "Original", "kind": "task"}]}, "owner")


@pytest.mark.parametrize("operation", [store.load, store.rebuild, index.rebuild])
@pytest.mark.parametrize("retained", [("ledger.db",), ("LEDGER.yaml",), ("ledger.db", "LEDGER.yaml")])
def test_missing_history_never_overwrites_derived_artifacts(tmp_path, operation, retained):
    seeded(tmp_path)
    (tmp_path / history.FILENAME).unlink()
    for name in {"ledger.db", "LEDGER.yaml"} - set(retained):
        (tmp_path / name).unlink()
    before = {name: (tmp_path / name).read_bytes() for name in retained}
    with pytest.raises(ConfigError, match="history.jsonl.*missing"):
        operation(tmp_path)
    assert {name: (tmp_path / name).read_bytes() for name in retained} == before


def test_fresh_bootstrap_and_missing_history_write_guard(tmp_path):
    with pytest.raises(ConfigError, match="history.jsonl.*missing"):
        store.rebuild(tmp_path)
    seeded(tmp_path)
    (tmp_path / history.FILENAME).unlink()
    before = (tmp_path / "LEDGER.yaml").read_bytes()
    with pytest.raises(ConfigError, match="history.jsonl.*missing"):
        seeded(tmp_path)
    assert (tmp_path / "LEDGER.yaml").read_bytes() == before
    assert not (tmp_path / history.FILENAME).exists()


def test_nested_json_values_rebuild_identically(tmp_path):
    seeded(tmp_path)
    store.apply(tmp_path, {"items": [{"id": "A-1", "custom": {"1": [None, {"x": True}]}}]}, "owner")
    before = {name: (tmp_path / name).read_bytes() for name in ("ledger.db", "LEDGER.yaml")}
    store.rebuild(tmp_path)
    assert {name: (tmp_path / name).read_bytes() for name in before} == before


@pytest.mark.parametrize("value", [None, [], {"id": "shadow"}])
def test_header_items_reserved_on_every_write_path(tmp_path, value):
    seeded(tmp_path)
    before = (tmp_path / history.FILENAME).read_bytes()
    entries = history.read(tmp_path)
    with pytest.raises(ConfigError, match="reserved"):
        store.apply(tmp_path, {"header": {"items": value}}, "owner")
    with pytest.raises(ConfigError, match="reserved"):
        store.commit(tmp_path, "owner", "header", None, {"items": value})
    entry = HistoryEntry(len(entries) + 1, "now", "owner", "header", None, {"items": value})
    with pytest.raises(ConfigError, match="reserved"):
        history.replay([*entries, entry])
    assert (tmp_path / history.FILENAME).read_bytes() == before


@pytest.mark.parametrize("key", ["title", "kind"])
@pytest.mark.parametrize("value", [None, "", "  ", 1])
def test_required_item_fields_cannot_be_deleted_or_invalid(tmp_path, key, value):
    seeded(tmp_path)
    before = (tmp_path / history.FILENAME).read_bytes()
    with pytest.raises(ConfigError):
        store.apply(tmp_path, {"items": [{"id": "A-1", key: value}]}, "owner")
    with pytest.raises(ConfigError):
        store.commit(tmp_path, "owner", "edit", "A-1", {key: value})
    assert (tmp_path / history.FILENAME).read_bytes() == before


@pytest.mark.parametrize("value", [(1, 2), {1, 2}, float("nan"), float("inf")])
def test_non_json_values_rejected_by_direct_write_apis(tmp_path, value):
    seeded(tmp_path)
    before = (tmp_path / history.FILENAME).read_bytes()
    diff = {"custom": [{"value": value}]}
    with pytest.raises(ConfigError):
        store.apply(tmp_path, {"items": [{"id": "A-1", **diff}]}, "owner")
    with pytest.raises(ConfigError):
        store.commit(tmp_path, "owner", "edit", "A-1", diff)
    with pytest.raises(ConfigError):
        history.append(tmp_path, HistoryEntry(3, "now", "owner", "edit", "A-1", diff), 2)
    assert (tmp_path / history.FILENAME).read_bytes() == before
