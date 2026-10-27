import json
import multiprocessing

import pytest

from fleetwork.errors import ConfigError, VersionConflict
from fleetwork.ledger import history
from fleetwork.ledger.model import HistoryEntry


def entry(v, op="add", item="A-1", diff=None):
    return HistoryEntry(v, "2026-01-01", "owner", op, item, diff or {})


def _writer(directory, start, results):
    start.wait()
    try:
        history.append(directory, entry(1, diff={"title": "x"}), 0)
        results.put("ok")
    except VersionConflict:
        results.put("conflict")


def test_concurrent_processes_compare_and_set(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    start, results = ctx.Event(), ctx.Queue()
    workers = [ctx.Process(target=_writer, args=(tmp_path, start, results)) for _ in range(2)]
    for worker in workers:
        worker.start()
    start.set()
    for worker in workers:
        worker.join(10)
        assert worker.exitcode == 0
    assert sorted(results.get(timeout=2) for _ in workers) == ["conflict", "ok"]
    assert len(history.read(tmp_path)) == 1


def test_batch_checks_all_before_writing(tmp_path):
    history.append(tmp_path, entry(1), 0)
    before = (tmp_path / history.FILENAME).read_bytes()
    with pytest.raises(VersionConflict):
        history.append_many(tmp_path, [entry(2), entry(4)], 1)
    assert (tmp_path / history.FILENAME).read_bytes() == before
    with pytest.raises(VersionConflict):
        history.append(tmp_path, entry(2), 0)


@pytest.mark.parametrize("data,exception", [
    (b'{"v":1}', ConfigError),
    (b'not json\n', ConfigError),
    (b'\n', ConfigError),
    ((json.dumps(entry(2).to_dict()) + '\n').encode(), VersionConflict),
])
def test_invalid_history_is_reported_and_never_appended(tmp_path, data, exception):
    path = tmp_path / history.FILENAME
    path.write_bytes(data)
    assert history.verify(tmp_path)
    with pytest.raises(exception):
        history.read(tmp_path)
    with pytest.raises(exception):
        history.append(tmp_path, entry(1), 0)
    assert path.read_bytes() == data


def test_replay_replaces_keys_deletes_null_and_does_not_mutate_input():
    changes = [entry(1, "header", None, {"ledger": "x", "never": ["a"]}),
               entry(2, diff={"title": "one", "kind": "task", "status": "open",
                              "custom": {"x": 1}, "note": "old"}),
               entry(3, "edit", diff={"custom": {"y": 2}, "note": None}),
               entry(4, "header", None, {"never": None})]
    state = history.replay(changes).to_dict()
    assert state == {"ledger": "x", "items": [{"id": "A-1", "title": "one", "kind": "task",
                                                  "status": "open", "custom": {"y": 2}}]}
    state["items"][0]["custom"]["y"] = 3
    assert changes[2].diff["custom"] == {"y": 2}
    with pytest.raises(VersionConflict):
        history.replay([entry(2)])


def test_replay_rejects_duplicate_add_and_edits_of_missing_items():
    added = entry(1, diff={"title": "first"})
    with pytest.raises(ConfigError, match="already exists"):
        history.replay([added, entry(2, diff={"title": "second"})])
    for op in ("edit", "claim", "close", "decide", "drop", "gate-resolve"):
        with pytest.raises(ConfigError, match="does not exist"):
            history.replay([entry(1, op)])
    assert history.replay([added]).item("A-1").title == "first"


def test_append_rejects_invalid_item_lifecycle_without_modifying_log(tmp_path):
    history.append(tmp_path, entry(1), 0)
    path = tmp_path / history.FILENAME
    original = path.read_bytes()
    with pytest.raises(ConfigError, match="already exists"):
        history.append(tmp_path, entry(2), 1)
    with pytest.raises(ConfigError, match="does not exist"):
        history.append(tmp_path, entry(2, "edit", "B-1"), 1)
    assert path.read_bytes() == original


@pytest.mark.parametrize("data", [
    b'{"v":1,"v":1,"t":"t","actor":"a","op":"add","item":"A-1","diff":{}}\n',
    b'{"v":1,"t":"t","actor":"a","op":"add","item":"A-1","diff":{"x":{"a":1,"a":2}}}\n',
    b'{"v":1,"t":"t","actor":"a","op":"add","item":"A-1","diff":{"x":NaN}}\n',
])
def test_ambiguous_json_is_rejected(tmp_path, data):
    (tmp_path / history.FILENAME).write_bytes(data)
    with pytest.raises(ConfigError):
        history.read(tmp_path)
    assert history.verify(tmp_path)


def test_verify_reports_invalid_lifecycle_in_existing_log(tmp_path):
    lines = [entry(1).to_dict(), entry(2).to_dict()]
    (tmp_path / history.FILENAME).write_text(''.join(json.dumps(x) + '\n' for x in lines))
    assert "already exists" in history.verify(tmp_path)[0]
