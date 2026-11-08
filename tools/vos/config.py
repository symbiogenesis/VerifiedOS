# SPDX-License-Identifier: Apache-2.0
"""Read, flatten, compare, and schema-validate Sail model configuration files (`model/config/*.json`).

Provides:
- Memoized JSONC loading and key-path lookup ([`value`](#value), [`integer`](#integer),
  [`flat_of`](#flat_of)).
- Key-set comparison ([`compare_keys`](#compare_keys)) and bidirectional JSON Schema
  validation ([`validate`](#validate)) against the Sail-generated schema.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

from . import jsonc
from .jsonc import Json


@lru_cache(maxsize=128)
def _parse(path: Path, identity: tuple[int, int, int, int]) -> Json:
    """Parse `path` via [`jsonc.load`](jsonc.py#load), keyed by file stat metadata."""
    return jsonc.load(path)


def _load(path: Path) -> Json:
    """Load `path` with stat-keyed memoization (parse errors are not cached)."""
    path = path.absolute()
    stat = path.stat()
    return _parse(path, (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino))


def value(path: Path, *keys: str) -> Json:
    """Return the value at `*keys` in `path`, or `None` if missing or unparseable."""
    if not path.is_file():
        return None
    try:
        node: Json = _load(path)
    except ValueError, FileNotFoundError:
        return None
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = cast("Json", node[key])  # ty: ignore[redundant-cast]
    return node


def integer(path: Path, *keys: str) -> int | None:
    """Return the integer value at `*keys` in `path` (excluding `bool`), or `None`."""
    found = value(path, *keys)
    return found if isinstance(found, int) and not isinstance(found, bool) else None


def _is_value(node: Json) -> bool:
    """Return True if `node` is a Sail option (`Some`/`None`) or bitvector literal (`len`/`value`) dict."""
    if not isinstance(node, dict) or not node:
        return False
    return set(node) == {"len", "value"} or set(node) <= {"Some", "None"}


def keys(node: Json, prefix: str = "") -> set[str]:
    """Return all dotted key paths in `node` without descending into lists or value dicts."""
    found: set[str] = set()
    if isinstance(node, dict) and not _is_value(node):
        for key, value in node.items():
            found.add(prefix + key)
            found |= keys(value, prefix + key + ".")
    return found


def flat(node: Json, prefix: str = "") -> dict[str, Json]:
    """Flatten `node` into `{dotted_key_path: leaf_value}` (lists and `_is_value` dicts are leaves)."""
    found: dict[str, Json] = {}
    if isinstance(node, dict) and node and not _is_value(node):
        for key, value in node.items():
            found |= flat(value, prefix + key + ".")
    else:
        found[prefix.removesuffix(".")] = node
    return found


def flat_of(path: Path) -> dict[str, Json]:
    """Return [`flat`](#flat) for `path`, or `{}` if `path` is missing or unparseable."""
    if not path.is_file():
        return {}
    try:
        return flat(_load(path))
    except ValueError, FileNotFoundError:
        return {}


def compare_keys(left_path: Path, right_path: Path) -> tuple[int, list[str]]:
    left, right = keys(jsonc.load(left_path)), keys(jsonc.load(right_path))
    out: list[str] = []
    for label, missing in ((f"only in {left_path}", left - right),
                           (f"only in {right_path}", right - left)):
        if missing:
            out.append(label + ":")
            out.extend(f"  {key}" for key in sorted(missing))
    if out:
        return 1, out
    return 0, [f"key sets agree ({len(left)} keys)"]


def _undeclared(config: Json, schema: Json, path: str = "") -> list[str]:
    """Return config key paths not declared in `schema`'s `properties` / `allOf` subschemas."""
    found: list[str] = []

    def add(paths: list[str]) -> None:
        found.extend(p for p in paths if p not in found)

    if not (isinstance(config, dict) and isinstance(schema, dict)):
        return found
    members = schema.get("allOf")
    if isinstance(members, list):
        for member in members:
            add(_undeclared(config, member, path))
    props = schema.get("properties")
    if not isinstance(props, dict):
        return found

    for key, value in config.items():
        here = f"{path}/{key}" if path else key
        add([here] if key not in props else _undeclared(value, props[key], here))
    return found


def validate(schema_path: Path, config_path: Path) -> tuple[int, list[str]]:
    """Validate `config_path` against `schema_path` and reject any config keys absent from `schema_path`."""
    try:
        import jsonschema  # noqa: PLC0415
    except ModuleNotFoundError:
        return 1, ["jsonschema is not installed: use tools/run.py to synchronize tools/uv.lock"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    config = jsonc.load(config_path)

    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    errors = sorted(validator(schema).iter_errors(config),
                    key=lambda e: list(e.absolute_path))

    out = [f"SCHEMA MISMATCH at {'/'.join(str(p) for p in e.absolute_path) or '<root>'}: "
           f"{e.message}" for e in errors]
    out += [f"UNDECLARED CONFIG KEY {p}: not in the regenerated schema"
            for p in _undeclared(config, schema)]

    if out:
        return 1, out
    return 0, [f"{config_path.name} validates against the regenerated schema "
               "(key sets consistent)"]
