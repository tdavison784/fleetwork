"""Ledger v2 data model (LEDGER-DESIGN §4.1, §4.2, §4.6). Every module in the kit uses these types.

Conversion is loss-free and exact: `from_dict` keeps keys it doesn't know in `extra` and remembers which known
keys were present; `to_dict` writes back exactly those keys plus any field that differs from its default, so a
round trip neither drops nor invents data (lint reports unknown keys; the model doesn't reject them). YAML/JSON keys are
hyphenated (`auto-start`); attributes are snake_case (`auto_start`). The model stores only what the spec
stores: `ready` is derived (derive.py) and never a status.

This module must not name any provider, harness, multiplexer, tracker or project (tests/test_architecture.py).
"""
from dataclasses import dataclass, field, fields

KINDS = ("lane", "task", "review", "decision", "evidence", "incident")
STATUSES = ("open", "in-progress", "blocked", "done", "dropped")
LINK_TYPES = ("discovered-from", "caused-by", "supersedes", "validates", "waits-for")
BUILTIN_GATES = ("human", "item", "timer", "window")
OPS = ("add", "edit", "claim", "close", "decide", "drop", "gate-resolve", "header")


def _key(attr):
    return attr.replace("_", "-")


class _Record:
    """from_dict/to_dict for flat dataclasses whose fields map 1:1 to hyphenated keys, plus `extra`."""

    _nested = {}   # attr -> class with from_dict/to_dict, or (list, class)
    _always = ()   # attrs always written by to_dict

    def __setattr__(self, name, value):
        # An explicit replacement supersedes the null originally read from disk.
        null_nested = self.__dict__.get("_null_nested")
        if null_nested is not None:
            null_nested.discard(name)
        object.__setattr__(self, name, value)

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        kw, extra, null_nested = {}, {}, set()
        names = {_key(f.name): f.name for f in fields(cls) if f.name != "extra"}
        for k, v in d.items():
            attr = names.get(k)
            if attr is None:
                extra[k] = v
                continue
            nested = cls._nested.get(attr)
            if nested is not None and v is None:
                # Keep the convenient empty object/list while remembering the original null.
                null_nested.add(attr)
                v = [] if isinstance(nested, tuple) else nested()
            elif isinstance(nested, tuple):
                v = [nested[1].from_dict(x) for x in (v or [])]
            elif nested is not None:
                v = nested.from_dict(v)
            kw[attr] = v
        obj = cls(**kw)
        obj.extra = extra
        obj._present = set(kw)
        obj._null_nested = null_nested
        return obj

    def to_dict(self):
        out = {}
        present = getattr(self, "_present", set())
        for f in fields(self):
            if f.name == "extra":
                continue
            v = getattr(self, f.name)
            nested = self._nested.get(f.name)
            if v is None:
                pass
            elif isinstance(nested, tuple):
                v = [x.to_dict() for x in v]
            elif nested is not None:
                v = v.to_dict()
            if f.name in getattr(self, "_null_nested", set()) and v == _default(f):
                v = None
            if f.name not in present and f.name not in self._always and v in (None, [], {}, _default(f)):
                continue
            out[_key(f.name)] = v
        out.update(self.extra)
        return out


def _default(f):
    from dataclasses import MISSING

    if f.default is not MISSING:
        return f.default
    if f.default_factory is not MISSING:
        v = f.default_factory()
        return v.to_dict() if isinstance(v, _Record) else v
    return None


@dataclass
class Gate(_Record):
    """A hold on an item. `spec` carries the type's own keys ({who, what} for human, {id} for item,
    {after} for timer, {provider, headroom} for window, adapter-defined for the rest)."""

    type: str = ""
    spec: dict = field(default_factory=dict)
    closed_by: dict = None             # {actor, t, why}; None = open
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        present = "closed-by" in d
        obj = cls(type=d.pop("type", ""), closed_by=d.pop("closed-by", None), spec=d)
        obj._closed_by_present = present
        return obj

    def to_dict(self):
        out = {"type": self.type, **self.spec}
        if self.closed_by is not None or getattr(self, "_closed_by_present", False):
            out["closed-by"] = self.closed_by
        return out

    @property
    def closed(self):
        return bool(self.closed_by)


@dataclass
class Run(_Record):
    """Enqueue-time authorization (§4.2): which declared providers may execute the item, and whether the
    runtime may start it unasked. `providers: []` = commander-only. `rights` is for decisions."""

    providers: list = field(default_factory=list)
    auto_start: bool = False
    model: str = None
    profile: str = None                # lane design (WP-08): the agent profile a lane runs under
    rights: str = None
    extra: dict = field(default_factory=dict)


@dataclass
class Guard(_Record):
    """Checkable integrity (§4.2); enforcement adapters turn these into hooks and merge checks."""

    forbid_read: list = field(default_factory=list)
    freeze: list = field(default_factory=list)
    no_push: bool = None
    note: str = None
    extra: dict = field(default_factory=dict)


@dataclass
class Budget(_Record):
    estimate: dict = field(default_factory=dict)   # {provider: {tokens: ...}}
    actual: dict = field(default_factory=dict)     # filled by `ledger close` through the provider adapter
    extra: dict = field(default_factory=dict)


@dataclass
class Item(_Record):
    id: str = ""
    title: str = ""
    kind: str = "task"
    status: str = "open"
    needs: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    run: Run = field(default_factory=Run)
    guard: Guard = field(default_factory=Guard)
    brief: str = None
    owner: str = None
    links: dict = field(default_factory=dict)      # {link-type: id or [ids]}
    budget: Budget = field(default_factory=Budget)
    result: str = None                             # a path, never the result text
    merged: str = None
    note: str = None
    why: str = None
    extra: dict = field(default_factory=dict)

    _nested = {"gates": (list, Gate), "run": Run, "guard": Guard, "budget": Budget}
    _always = ("id", "title", "kind", "status")


@dataclass
class Header(_Record):
    """The ledger's own configuration (§4.1, §5). Changes to it are `header` ops in the history log."""

    version: int = 2
    ledger: str = ""
    prefix: str = ""
    providers: dict = field(default_factory=dict)  # name -> {adapter, limits: {lanes: n}, ...}
    roles: dict = field(default_factory=dict)      # role -> {actors: [...]}
    delegations: list = field(default_factory=list)
    never: list = field(default_factory=list)
    formulas: dict = field(default_factory=dict)   # name -> path relative to the ledger directory
    events: list = field(default_factory=list)     # [{adapter, ...config}] event sources
    extra: dict = field(default_factory=dict)


@dataclass
class Ledger:
    header: Header
    items: list

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        items = [Item.from_dict(x) for x in d.pop("items", []) or []]
        return cls(header=Header.from_dict(d), items=items)

    def to_dict(self):
        return {**self.header.to_dict(), "items": [i.to_dict() for i in self.items]}

    def item(self, item_id):
        for i in self.items:
            if i.id == item_id:
                return i
        return None


@dataclass
class HistoryEntry:
    """One line of history.jsonl, the ledger's truth (§4.6): {v, t, actor, op, item, diff}.

    `v` is the ledger version after this entry (1, 2, ...); `item` is None for `header` ops; `diff` is the
    changed keys with their new values (None deletes a key)."""

    v: int
    t: str
    actor: str
    op: str
    item: str = None
    diff: dict = field(default_factory=dict)
    why: str = None

    def to_dict(self):
        d = {"v": self.v, "t": self.t, "actor": self.actor, "op": self.op, "item": self.item, "diff": self.diff}
        if self.why:
            d["why"] = self.why
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: d.get(k) for k in ("v", "t", "actor", "op", "item", "diff", "why")})
