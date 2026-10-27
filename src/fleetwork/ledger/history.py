"""Append-only ledger history, with a process-safe compare-and-set on its version."""
import copy
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

from fleetwork.errors import ConfigError, VersionConflict
from fleetwork.ledger.model import HistoryEntry, Ledger, OPS

FILENAME = "history.jsonl"
_LOCK = ".history.lock"


def _validate(entry, expected):
    if not isinstance(entry, HistoryEntry):
        raise ConfigError("history entry must be a HistoryEntry")
    if type(entry.v) is not int or entry.v != expected:
        raise VersionConflict(f"history version: expected {expected}, got {entry.v!r}")
    if not isinstance(entry.t, str) or not isinstance(entry.actor, str):
        raise ConfigError(f"history version {expected}: t and actor must be strings")
    if entry.op not in OPS or not isinstance(entry.diff, dict):
        raise ConfigError(f"history version {expected}: invalid op or diff")
    if entry.op == "header":
        if entry.item is not None:
            raise ConfigError(f"history version {expected}: header item must be null")
    elif not isinstance(entry.item, str) or not entry.item:
        raise ConfigError(f"history version {expected}: item must be a nonempty string")
    if any(not isinstance(key, str) for key in entry.diff):
        raise ConfigError(f"history version {expected}: diff keys must be strings")
    if entry.why is not None and not isinstance(entry.why, str):
        raise ConfigError(f"history version {expected}: why must be a string")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def _invalid_constant(value):
    raise ValueError(f"invalid JSON constant {value}")


def _read(path):
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    if data and not data.endswith(b"\n"):
        raise ConfigError("history has a torn final line")
    entries = []
    for line_number, line in enumerate(data.splitlines(), 1):
        try:
            raw = json.loads(line, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            if not isinstance(raw, dict) or not {"v", "t", "actor", "op", "item", "diff"} <= raw.keys():
                raise ConfigError("missing required fields")
            entry = HistoryEntry.from_dict(raw)
            _validate(entry, line_number)
        except VersionConflict:
            raise
        except (ConfigError, ValueError, TypeError, UnicodeDecodeError) as exc:
            raise ConfigError(f"malformed history line {line_number}: {exc}") from exc
        entries.append(entry)
    replay(entries)
    return entries


class _Transaction:
    def __init__(self, directory):
        self.path = directory / FILENAME

    def read(self):
        return _read(self.path)

    def append_many(self, entries, expected_v):
        existing = self.read()
        actual = len(existing)
        if type(expected_v) is not int or expected_v != actual:
            raise VersionConflict(f"history version: expected {expected_v}, got {actual}")
        entries = list(entries)
        for offset, entry in enumerate(entries, 1):
            _validate(entry, actual + offset)
        replay([*existing, *entries])
        # Encode the complete batch before touching the log.
        lines = b"".join((json.dumps(e.to_dict(), ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
                         for e in entries)
        if lines:
            with self.path.open("ab") as file:
                file.write(lines)
                file.flush()
                os.fsync(file.fileno())


@contextmanager
def transaction(ledger_dir):
    """Hold the ledger's writer lock across reads, appends and cache updates."""
    directory = Path(ledger_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / _LOCK).open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield _Transaction(directory)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def read(ledger_dir):
    """Every entry, in order, as HistoryEntry objects."""
    with transaction(ledger_dir) as tx:
        return tx.read()


def append_many(ledger_dir, entries, expected_v):
    """Append a batch only if its expected version matches the log."""
    with transaction(ledger_dir) as tx:
        tx.append_many(entries, expected_v)


def append(ledger_dir, entry, expected_v):
    """Append `entry` iff the log's last version is `expected_v`."""
    append_many(ledger_dir, [entry], expected_v)


def verify(ledger_dir):
    """Return findings for invalid or nonconsecutive log entries."""
    try:
        read(ledger_dir)
    except (ConfigError, VersionConflict) as exc:
        return [str(exc)]
    return []


def replay(entries):
    """Build a fresh Ledger from changed top-level keys; null deletes a key."""
    header, items = {}, {}
    for version, entry in enumerate(entries, 1):
        _validate(entry, version)
        if entry.op == "header":
            target = header
        elif entry.op == "add":
            if entry.item in items:
                raise ConfigError(f"history version {version}: item {entry.item!r} already exists")
            target = items[entry.item] = {"id": entry.item}
        else:
            if entry.item not in items:
                raise ConfigError(f"history version {version}: item {entry.item!r} does not exist")
            target = items[entry.item]
        for key, value in entry.diff.items():
            if value is None:
                target.pop(key, None)
            else:
                target[key] = copy.deepcopy(value)
        if entry.op != "header" and target.get("id") != entry.item:
            raise ConfigError(f"history version {version}: item id does not match entry")
    try:
        return Ledger.from_dict({**header, "items": list(items.values())})
    except (TypeError, ValueError, AttributeError) as exc:
        raise ConfigError(f"invalid history state: {exc}") from exc
