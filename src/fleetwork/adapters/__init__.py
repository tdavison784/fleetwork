"""Adapter registry (L2). Every adapter is one module in `fleetwork/adapters/<package>/<name>.py` that
registers one class with `@register(kind, name)`. Configs name adapters by `name`; `get` imports the module
on first use, so an adapter's own dependencies (a CLI, a network endpoint) are never touched unless chosen.

Adding an adapter: copy the closest sibling module, change the name, implement the Protocol from `base.py`,
add a test in tests/adapters/. Nothing else needs editing; the registry finds modules by file name.
"""
import importlib
import pkgutil

from fleetwork.errors import UnknownAdapter

# kind -> sub-package holding that kind's adapters
KINDS = {
    "store": "stores",
    "provider": "providers",
    "gate": "gates",
    "enforcement": "enforcement",
    "events": "events",
    "runtime": "runtimes",
    "workspace": "workspaces",
    "integration": "integrations",
    "mirror": "mirrors",
}

_REGISTRY = {}


def register(kind, name):
    if kind not in KINDS:
        raise ValueError(f"unknown adapter kind {kind!r}; kinds: {', '.join(KINDS)}")

    def deco(cls):
        key = (kind, name)
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"adapter {kind}:{name} registered twice")
        _REGISTRY[key] = cls
        cls.adapter_kind, cls.adapter_name = kind, name
        return cls

    return deco


def _module_for(name):
    return name.replace("-", "_")


def available(kind):
    """Adapter names shipped for `kind` (module names with '_' shown as '-')."""
    pkg = importlib.import_module(f"{__name__}.{KINDS[kind]}")
    return sorted(m.name.replace("_", "-") for m in pkgutil.iter_modules(pkg.__path__) if not m.name.startswith("_"))


def get(kind, name):
    """The adapter class registered as kind:name, importing its module if needed."""
    if kind not in KINDS:
        raise UnknownAdapter(f"unknown adapter kind {kind!r}")
    if (kind, name) not in _REGISTRY:
        try:
            importlib.import_module(f"{__name__}.{KINDS[kind]}.{_module_for(name)}")
        except ModuleNotFoundError as e:
            raise UnknownAdapter(f"no {kind} adapter {name!r}; available: {', '.join(available(kind))}") from e
    try:
        return _REGISTRY[(kind, name)]
    except KeyError:
        raise UnknownAdapter(f"module for {kind} adapter {name!r} does not register it") from None


def create(kind, name, **config):
    """An instance of kind:name built from its config table."""
    return get(kind, name)(**config)
