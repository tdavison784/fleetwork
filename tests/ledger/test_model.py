import yaml

from fleetwork.ledger.model import Gate, Item, Ledger


def test_round_trip_keeps_every_key(v2_ledger, kit_root):
    raw = yaml.safe_load((kit_root / "tests/fixtures/v2/minimal.yaml").read_text())
    led = v2_ledger("minimal")
    assert led.to_dict() == {**raw["header"], "items": raw["items"]}


def test_hyphenated_keys_map_to_attributes(v2_ledger):
    thing = v2_ledger("minimal").item("D-0002")
    assert thing.run.auto_start is True and thing.run.profile == "builder"
    assert thing.guard.forbid_read == ["sealed/**"]
    assert thing.extra == {"custom-field": "kept verbatim"}


def test_gate_keeps_type_specific_keys():
    g = Gate.from_dict({"type": "window", "provider": "p1", "headroom": "30%"})
    assert g.type == "window" and g.spec == {"provider": "p1", "headroom": "30%"} and not g.closed
    assert Gate.from_dict(g.to_dict()) == g


def test_defaults_are_open_tasks():
    i = Item.from_dict({"id": "X-1", "title": "t"})
    assert i.kind == "task" and i.status == "open" and i.to_dict() == {"id": "X-1", "title": "t", "kind": "task", "status": "open"}


def test_example_batches_parse(v2_ledger):
    led = v2_ledger("go-rcana-items")
    assert [i.id for i in led.items][:2] == ["L-0002", "L-0003"]
    assert led.item("L-0009").gates[0].type == "human"


def test_v1_fixtures_parse_without_loss(v1_ledger):
    # v1 keys the model doesn't know land in `extra`; migration (WP-03) maps them properly.
    for name in ("pilot-a", "pilot-b"):
        d = v1_ledger(name)
        led = Ledger.from_dict(d)
        assert len(led.items) == len(d["items"])
        assert [i.to_dict() for i in led.items] == d["items"]
