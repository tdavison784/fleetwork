import pytest

from fleetwork import adapters
from fleetwork.errors import NotImplementedYet, UnknownAdapter


def test_get_imports_on_demand_and_lists_names():
    assert "dir" in adapters.available("store")
    assert adapters.get("store", "dir").adapter_name == "dir"
    assert adapters.get("provider", "claude-code").adapter_name == "claude-code"   # hyphen -> module claude_code


def test_unknown_adapter_lists_what_exists():
    with pytest.raises(UnknownAdapter, match="available: .*dir"):
        adapters.get("store", "nope")


def test_double_registration_is_refused():
    with pytest.raises(ValueError):
        adapters.register("store", "dir")(type("Other", (), {}))


def test_stubs_raise_with_their_work_package():
    with pytest.raises(NotImplementedYet, match="WP-06"):
        adapters.create("provider", "zai-quota").headroom()
