"""`fleet init`: render the packs' templates into a ledger directory.

Each pack's templates/ tree is copied into the target in pack order (core first); a later pack may add files
but not replace an earlier pack's file (that's a conflict to resolve in the packs, reported as an error).
Text files are rendered: `{{name}}` is replaced from, in increasing precedence, pack [vars] defaults, the
built-ins below, the project's [vars], and --var flags. Any placeholder left unresolved aborts the whole init
before a single file is written, listing every missing name. Existing files are kept unless force=True.

Built-in variables: project, ledger, date (YYYY-MM-DD), packs (comma-separated).
"""
import datetime
import json
import re
from pathlib import Path

import yaml

from fleetwork.errors import ConfigError

PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


def render(text, variables):
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in variables})
    return PLACEHOLDER.sub(lambda m: str(variables.get(m.group(1), m.group(0))), text), missing


def render_yaml(text, variables, source):
    """Substitute YAML scalar contents without allowing values to change its structure."""
    names = PLACEHOLDER.findall(text)
    missing = sorted({name for name in names if name not in variables})
    if missing:
        return text, missing

    # Mask placeholders before parsing so they are valid even in flow mappings.
    tokens = {}
    def mask(match):
        token = f"FLEETPLACEHOLDER{len(tokens)}END"
        while token in text:
            token += "X"
        tokens[token] = match.group(1)
        return token

    masked = PLACEHOLDER.sub(mask, text)
    try:
        root = yaml.compose(masked, Loader=yaml.SafeLoader)
        replacements = []
        visited = set()

        def visit(node):
            if id(node) in visited:
                return
            visited.add(id(node))
            if isinstance(node, yaml.ScalarNode):
                matches = [token for token in tokens if token in node.value]
                if not matches:
                    return
                value = node.value
                for token in matches:
                    value = value.replace(token, str(variables[tokens[token]]))
                if len(matches) == 1 and node.value == matches[0] and tokens[matches[0]] in {
                    "lane_limit", "context_checkpoint"
                }:
                    if not re.fullmatch(r"[0-9]+", value):
                        raise ConfigError(f"{source}: {tokens[matches[0]]} must be an integer")
                    encoded = str(int(value))
                else:
                    encoded = json.dumps(value, ensure_ascii=True)
                replacements.append((node.start_mark.index, node.end_mark.index, encoded))
            elif isinstance(node, yaml.SequenceNode):
                for child in node.value:
                    visit(child)
            elif isinstance(node, yaml.MappingNode):
                for key, value in node.value:
                    visit(key)
                    visit(value)

        if root is not None:
            visit(root)
        # Remaining tokens occur in comments. Keep comment substitutions on one line.
        for token, name in tokens.items():
            start = masked.find(token)
            if not any(begin <= start < end for begin, end, _ in replacements):
                value = str(variables[name]).replace("\n", " ").replace("\r", " ")
                replacements.append((start, start + len(token), value))
        for start, end, value in sorted(replacements, reverse=True):
            masked = masked[:start] + value + masked[end:]
        yaml.safe_load(masked)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML template {source}: {exc}") from exc
    return masked, []


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
            rendered, miss = (render_yaml(text, variables, f"{pack.name}:{rel}")
                              if src.suffix.lower() in {".yaml", ".yml"}
                              else render(text, variables))
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
