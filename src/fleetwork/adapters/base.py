"""The adapter interfaces (LEDGER-DESIGN §6.1, plus the runtime-side kinds from the lane design).

Each kind is a Protocol. An adapter class is constructed with its config table as keyword arguments
(`adapters.create(kind, name, **table)`) and must implement every method of its kind. Return plain data
(dicts, lists, str, Path), never adapter-specific objects, so the ledger core stays ignorant of them.

Which layer may call which kind:
  ledger (L1):   store, provider, gate, events, mirror
  runtime (L3):  every kind, including enforcement, runtime, workspace, integration
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Protocol, runtime_checkable


@dataclass
class Usage:
    tokens: int
    cost: Optional[float] = None


# --- used by the ledger (L1) -------------------------------------------------------------------------

@runtime_checkable
class Store(Protocol):
    """Where a ledger directory lives and how it is backed up (§4.6). The core only ever sees the Path."""

    def open(self, ledger: str) -> Path: ...

    def sync(self, path: Path) -> None: ...


@runtime_checkable
class Provider(Protocol):
    """A source of agent capacity with an optional usage window (§0, §6.1)."""

    def headroom(self) -> Optional[float]:
        """Fraction of the current window left, 0..1; None = unmetered."""
        ...

    def usage(self, session_ids: list) -> Usage: ...


@runtime_checkable
class GateEvaluator(Protocol):
    """Evaluates gate types the core doesn't build in (window, pr, ci, ...). `types` lists them."""

    types: tuple

    def check(self, gate: dict, ledger) -> bool: ...


@runtime_checkable
class EventSource(Protocol):
    """Yields events with at least {t, event, provider}; event in handoff|handback|resume|pause|checkpoint (§4.5)."""

    def read(self) -> Iterator[dict]: ...


@runtime_checkable
class Mirror(Protocol):
    """A one-way export of the ledger into another tracker (beads, an issue tracker). Never a source of
    truth: nothing is read back (LEDGER-DESIGN §4.6). Returns a one-line summary of what was written."""

    def export(self, ledger, dest: str) -> str: ...


# --- used only by the fleet runtime (L3) -------------------------------------------------------------

@runtime_checkable
class Enforcement(Protocol):
    """Turns an actor's guard lists and the `never` floor into harness settings/hooks (§5, §7).

    Returns the files written so `fleet lane start` can report them."""

    def write(self, actor: str, guard: dict, never: list, dest: Path) -> list: ...


@runtime_checkable
class Runtime(Protocol):
    """Where agents run (a terminal multiplexer, a headless CLI, a cloud session)."""

    def start(self, name: str, profile: dict, cwd: Path, prompt: str) -> str:
        """Starts an agent; returns the runtime's handle for it."""
        ...

    def state(self, name: str) -> str:
        """One of idle | working | blocked | done | gone | unknown."""
        ...

    def send(self, name: str, text: str) -> None: ...

    def stop(self, name: str) -> None: ...


@runtime_checkable
class Workspace(Protocol):
    """How a lane is isolated (a git worktree, a copied directory, a container)."""

    def create(self, lane: str, base: str) -> Path: ...

    def remove(self, lane: str) -> None: ...


@runtime_checkable
class Integration(Protocol):
    """How a lane's output joins the whole (a merge, a PR, assembling a document). Returns a reference
    (commit sha, PR URL, path) that `ledger close --merged` records."""

    def integrate(self, lane: str, workspace: Path, policy: dict) -> str: ...


PROTOCOLS = {
    "store": Store,
    "provider": Provider,
    "gate": GateEvaluator,
    "events": EventSource,
    "enforcement": Enforcement,
    "runtime": Runtime,
    "workspace": Workspace,
    "integration": Integration,
    "mirror": Mirror,
}
