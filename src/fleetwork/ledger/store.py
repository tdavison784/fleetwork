"""Ledger storage operations; history is authoritative and the other files are caches.

Until delegation and lint are implemented, writes are restricted to owner actors and
the apply format is checked locally. This prevents unfinished policy code from granting
authority; WP-02 and WP-07 will replace those restrictions with their full rules.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from fleetwork import config
from fleetwork.errors import ConfigError, DelegationRefused, VersionConflict
from fleetwork.ledger import history, index, view
from fleetwork.ledger.model import HistoryEntry


def locate(ledger_dir=None):
    """The ledger directory: an explicit path, else the configured store."""
    return Path(ledger_dir) if ledger_dir else config.load().ledger_dir()


def _owners(header):
    roles = header.get("roles") or {}
    if not isinstance(roles, dict) or not isinstance(roles.get("owner"), dict):
        return []
    actors = roles["owner"].get("actors", [])
    return [actor for actor in actors if isinstance(actor, str) and actor.strip()] if isinstance(actors, list) else []


def _validate_owners(header):
    roles = header.get("roles")
    owner = roles.get("owner") if isinstance(roles, dict) else None
    actors = owner.get("actors") if isinstance(owner, dict) else None
    if (not isinstance(actors, list) or not actors
            or any(not isinstance(actor, str) or not actor.strip() for actor in actors)):
        raise ConfigError("ledger must retain at least one owner actor; owner actors must be nonempty strings")


def _authorize(entries, actor, initial_header=None):
    if not isinstance(actor, str) or not actor.strip():
        raise ConfigError("actor must be a nonempty string")
    if entries:
        header = history.replay(entries).header.to_dict()
    else:
        header = initial_header or {}
    if actor not in _owners(header):
        raise DelegationRefused(actor, "write the ledger", "ask an owner to make this change")


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _refresh(ledger_dir, entries):
    # Callers hold the history lock, so this snapshot cannot become stale.
    ledger = index._rebuild(Path(ledger_dir), entries)
    view.write(ledger_dir, ledger)
    return ledger


def _refresh_after_commit(ledger_dir, entries):
    try:
        return _refresh(ledger_dir, entries)
    except Exception as exc:
        raise ConfigError(
            f"history committed through version {entries[-1].v}, but index or view refresh failed: {exc}; "
            "run ledger rebuild to repair derived files"
        ) from exc


def load(ledger_dir):
    """Load the log's current state, repairing missing or stale derived files."""
    with history.transaction(ledger_dir) as tx:
        entries = tx.read()
        # Rebuilding also detects changed history with the same version, or a corrupt cache.
        return _refresh(ledger_dir, entries)


def rebuild(ledger_dir):
    """Rebuild both derived artifacts from a consistent snapshot of the log."""
    with history.transaction(ledger_dir) as tx:
        return _refresh(ledger_dir, tx.read())


def commit(ledger_dir, actor, op, item_id, diff, why=None, expected_v=None):
    """Append one checked change and refresh derived artifacts under the writer lock."""
    if not isinstance(diff, dict):
        raise ConfigError("change diff must be a mapping")
    with history.transaction(ledger_dir) as tx:
        entries = tx.read()
        _authorize(entries, actor, diff if op == "header" else None)
        version = entries[-1].v if entries else 0
        if expected_v is not None and expected_v != version:
            raise VersionConflict(f"expected version {expected_v}, found {version}")
        entry = HistoryEntry(v=version + 1, t=_timestamp(), actor=actor, op=op,
                             item=item_id, diff=diff, why=why)
        result = history.replay([*entries, entry])  # reject invalid operations before changing the log
        if op == "header":
            _validate_owners(result.header.to_dict())
        tx.append_many([entry], version)
        _refresh_after_commit(ledger_dir, [*entries, entry])
        return entry


def apply(ledger_dir, batch, actor):
    """Apply a complete YAML batch, checking every change before appending any."""
    if not isinstance(batch, dict) or not set(batch) <= {"header", "items"}:
        raise ConfigError("batch must contain only header and/or items")
    header = batch.get("header", {})
    items = batch.get("items", [])
    if not isinstance(header, dict) or not isinstance(items, list):
        raise ConfigError("batch header must be a mapping and items must be a list")
    try:
        json.dumps(batch, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"batch contains a non-JSON value: {exc}") from None
    with history.transaction(ledger_dir) as tx:
        entries = tx.read()
        _authorize(entries, actor, header)
        version = entries[-1].v if entries else 0
        planned = []
        current = history.replay(entries)

        def add(op, item_id, diff):
            # A preceding header entry may have changed the actor's authority.
            _authorize([*entries, *planned], actor, header)
            entry = HistoryEntry(v=version + len(planned) + 1, t=_timestamp(), actor=actor,
                                 op=op, item=item_id, diff=diff)
            planned.append(entry)
            return history.replay([*entries, *planned])

        if header:
            old_header = current.header.to_dict()
            changed = {key: value for key, value in header.items()
                       if (key in old_header if value is None else old_header.get(key) != value)}
            if changed:
                next_header = dict(old_header)
                for key, value in changed.items():
                    if value is None:
                        next_header.pop(key, None)
                    else:
                        next_header[key] = value
                _validate_owners(next_header)
                current = add("header", None, changed)
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                raise ConfigError("each item needs a nonempty string id")
            item_id = item["id"]
            existing = current.item(item_id)
            if existing is None:
                if not isinstance(item.get("title"), str) or not item["title"].strip():
                    raise ConfigError(f"{item_id}: new item needs a title")
                if item.get("status", "open") != "open" or item.get("owner") is not None:
                    raise ConfigError(f"{item_id}: new items must be open and unowned")
                current = add("add", item_id, item)
            else:
                old_item = existing.to_dict()
                if any(key in item and item[key] != old_item.get(key) for key in ("status", "owner")):
                    raise ConfigError(f"{item_id}: status and owner changes require a mutation command")
                diff = {key: value for key, value in item.items()
                        if key not in ("id", "status", "owner")
                        and (key in old_item if value is None else old_item.get(key) != value)}
                if diff:
                    current = add("edit", item_id, diff)
        if planned:
            tx.append_many(planned, version)
            _refresh_after_commit(ledger_dir, [*entries, *planned])
        else:
            _refresh(ledger_dir, entries)
        return planned
