"""The adapters that work today: dir store, none provider, jsonl events."""
import json

from fleetwork import adapters


def test_dir_store_opens_a_directory_per_ledger(tmp_path):
    d = adapters.create("store", "dir", path=str(tmp_path)).open("goal")
    assert d == tmp_path / "goal" and d.is_dir()


def test_none_provider_is_unmetered():
    p = adapters.create("provider", "none")
    assert p.headroom() is None and p.usage(["s"]).tokens == 0


def test_jsonl_events_skip_bad_lines_and_default_provider(tmp_path):
    f = tmp_path / "events.jsonl"
    f.write_text("\n".join([json.dumps({"t": "1", "event": "HANDOFF", "lane": "a"}), "not json",
                            json.dumps({"no": "t"}), json.dumps({"t": "2", "event": "resume", "provider": "p1"})]))
    evs = list(adapters.create("events", "jsonl", paths=[str(f), str(tmp_path / "missing.jsonl")]).read())
    assert evs == [{"t": "1", "event": "HANDOFF", "lane": "a", "provider": None},
                   {"t": "2", "event": "resume", "provider": "p1"}]
