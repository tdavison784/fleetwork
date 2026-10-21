"""`fleet init`: render the packs' templates into a ledger directory.

Each pack's templates/ tree is copied into the target in pack order (core first); a later pack may add files
but not replace an earlier pack's file (that's a conflict to resolve in the packs, reported as an error).
Text files are rendered: `{{name}}` is replaced from, in increasing precedence, pack [vars] defaults, the
built-ins below, the project's [vars], and --var flags. Any placeholder left unresolved aborts the whole init
before a single file is written, listing every missing name. Existing files are kept unless force=True.

Built-in variables: project, ledger, date (YYYY-MM-DD), packs (comma-separated).
"""
import datetime
import re
from pathlib import Path

from fleetwork.errors import ConfigError

PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


def render(text, variables):
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in variables})
    return PLACEHOLDER.sub(lambda m: str(variables.get(m.group(1), m.group(0))), text), missing


def plan(packs, variables):
    """[(relative path, rendered bytes)] for every template file, or raise ConfigError."""
    out, owner, missing = {}, {}, {}
    for pack in packs:
        if not pack.templates.is_dir():
            continue
        for src in sorted(p for p in pack.templates.rglob("*") if p.is_file()):
            rel = src.relative_to(pack.templates).as_posix()
            if rel in owner:
                raise ConfigError(f"template {rel} is provided by both {owner[rel]} and {pack.name}")
            owner[rel] = pack.name
            data = src.read_bytes()
            try:
                text = data.decode()
            except UnicodeDecodeError:
                out[rel] = data
                continue
            rendered, miss = render(text, variables)
            for m in miss:
                missing.setdefault(m, []).append(f"{pack.name}:{rel}")
            out[rel] = rendered.encode()
    if missing:
        lines = [f"  {k}  (used in {', '.join(v)})" for k, v in sorted(missing.items())]
        raise ConfigError("unresolved template variables; pass --var name=value or set [vars]:\n" + "\n".join(lines))
    return sorted(out.items())


def variables_for(packs, project_name, ledger, project_vars=None, cli_vars=None):
    v = {}
    for p in packs:
        v.update(p.vars)
    v.update(project=project_name, ledger=ledger, date=datetime.date.today().isoformat(),
             packs=", ".join(p.name for p in packs))
    v.update(project_vars or {})
    v.update(cli_vars or {})
    return v


def init(target, packs, variables, force=False):
    """Writes the files; returns (written, kept) lists of relative paths."""
    target = Path(target)
    written, kept = [], []
    for rel, data in plan(packs, variables):
        dest = target / rel
        if dest.exists() and not force:
            kept.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(rel)
    return written, kept
