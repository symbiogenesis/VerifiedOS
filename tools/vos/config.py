# SPDX-License-Identifier: Apache-2.0
"""The model's configuration, held against the schema and against the max build.

Two questions are asked of `model/config/verifiedos.json`, and they catch different
things. The first is whether it still declares the same *keys* as the generated max
configuration, which is what a deletion batch must leave true even where the two
disagree on values: a key present in only one of them is either dead configuration
surface the cut missed, or a profile row the generated file no longer offers. The
second is whether it validates against the schema a fresh emission regenerates, which
catches the class the Sail typechecker cannot see: a stray `config extensions.<Name>`
read left behind by a cut, which surfaces as a schema/config collision only at emission
(the c1 "sixth touch" finding).

Both are approximations of the simulator's own `--validate-config`, which also runs the
model's semantic `config_is_valid`, so the full build stays the exit criterion for each
batch.
"""

import json
from pathlib import Path
from typing import cast

from . import jsonc
from .jsonc import Json

# One parse per file per process, keyed on the file's identity and mtime so an edit
# between two calls is still seen. In memory only, deliberately: a cache file on disk
# would land inside the selftest's sandboxes and change what their baseline reads. The
# memo is why eleven queries of one configuration in one run cost one strip-and-parse
# rather than eleven; nothing here rewrites a configuration, so a parse cannot go
# stale within a run.
_PARSED: dict[tuple[str, int], Json] = {}


def _load(path: Path) -> Json:
    """`jsonc.load`, memoized. A parse error is not memoized, so a broken file is
    re-read on every query and stays the caller's finding each time."""
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _PARSED:
        _PARSED[key] = jsonc.load(path)
    return _PARSED[key]


def value(path: Path, *keys: str) -> Json:
    """One value out of the model's configuration, by the key path that names it.

    The dialect is decoded here and nowhere else. A tool wanting a figure out of a
    configuration asks this rather than growing a second decoder of the same file,
    which is the two-copies-of-one-fact defect the checker exists to catch running
    loose inside it.

    A file that is not there, a file that does not parse, and a key path that runs out
    all answer `None`. An absent figure is a finding the caller words in its own terms,
    never an exception it has to catch to say so.
    """
    if not path.is_file():
        return None
    try:
        node: Json = _load(path)
    except ValueError:
        return None
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    # `Json` is recursive, and a walk that re-binds through it leaves the checker
    # holding the alias expanded one level rather than the alias, which is the same
    # type spelled longer. Narrowed back to what it is, as `jsonc.load` narrows the
    # untyped boundary it stands on.
    return cast("Json", node)


def integer(path: Path, *keys: str) -> int | None:
    """The same, narrowed to a whole number. `True` is an `int` in Python and a
    boolean in the configuration, so the narrowing has to exclude it by name."""
    found = value(path, *keys)
    return found if isinstance(found, int) and not isinstance(found, bool) else None


def _is_value(node: Json) -> bool:
    """True where a dict is one configuration *value* rather than more surface.

    Two shapes reach here. An option is spelled `{"Some": ...}` or `{"None": ...}`, and
    a bitvector literal is spelled `{"len": n, "value": "0x..."}`. Descending into
    either compares payloads instead of keys: `dtb_address` is the row a cut can delete,
    and `dtb_address.value` is just the address it holds.

    Recognized by shape and not by name, deliberately. A leaf-name match (`value$`,
    `len$`) drops any key so called at any depth, including one a cut really did leave
    on a single side, and the run then still prints "key sets agree". An exclusion that
    widens on its own is worse than none in a tool whose whole job is to notice what
    widened.
    """
    if not isinstance(node, dict) or not node:
        return False
    return set(node) == {"len", "value"} or set(node) <= {"Some", "None"}


def keys(node: Json, prefix: str = "") -> set[str]:
    # `memory.regions` needs no exclusion: it is a list, whose entries differ between
    # the two files by design and are never keys, and the walk does not enter lists.
    found: set[str] = set()
    if isinstance(node, dict) and not _is_value(node):
        for key, value in node.items():
            found.add(prefix + key)
            found |= keys(value, prefix + key + ".")
    return found


def flat(node: Json, prefix: str = "") -> dict[str, Json]:
    """Every leaf of a configuration, by the key path that names it.

    `keys` above answers what a configuration *declares*; this answers what it
    *says*. The two questions separated when a second configuration of the same model
    started shipping (M0.8b): two configurations of one composition may differ only
    where the core they compose differs, and a key set alone cannot see a value that
    drifted (R-15-005).

    A list is a leaf here, as it is in `keys`, and for the same reason: the walk does
    not enter one, so `memory.regions` is compared whole or not at all.
    """
    found: dict[str, Json] = {}
    if isinstance(node, dict) and node and not _is_value(node):
        for key, value in node.items():
            found |= flat(value, prefix + key + ".")
    else:
        found[prefix.removesuffix(".")] = node
    return found


def flat_of(path: Path) -> dict[str, Json]:
    """The same, read from a file. A file that is not there and a file that does not
    parse both answer empty, which is `value`'s contract: an absent configuration is a
    finding the caller words rather than an exception it has to catch."""
    if not path.is_file():
        return {}
    try:
        return flat(_load(path))
    except ValueError:
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
    # Recurse only where the subschema plainly declares "properties"; anyOf/oneOf nodes
    # are left alone.
    found: list[str] = []
    if not (isinstance(config, dict) and isinstance(schema, dict)):
        return found
    # bound before the test rather than re-read after it, so that what was checked to
    # be a mapping is what gets indexed below
    props = schema.get("properties")
    if not isinstance(props, dict):
        return found

    for key, value in config.items():
        here = f"{path}/{key}" if path else key
        if key not in props:
            found.append(here)
        else:
            found.extend(_undeclared(value, props[key], here))
    return found


def validate(schema_path: Path, config_path: Path) -> tuple[int, list[str]]:
    """Two directions are checked, because the generated schema closes only its
    bitvector-literal leaves (`additionalProperties: false`) and plain validation
    therefore misses a config key whose schema entry a cut deleted. c1's verified state
    is required-key set == config-key set, so an undeclared key is always drift."""
    try:
        # The one dependency in this directory that is not the standard library. The
        # import is here rather than at the top because only this function needs it,
        # and its absence is a finding rather than a crash for whoever runs the tools
        # without it. It carries no `ty: ignore`: a directive is only correct where the
        # import does not resolve, so one written for a lane that lacks the package is
        # itself a finding on the lane that has it, and the gate then depends on what
        # happens to be installed rather than on what the code says. The package is a
        # prerequisite of both lanes instead, recorded in tools/README.md beside the
        # two checkers, which leaves every unresolved import in this file an error.
        import jsonschema  # noqa: PLC0415
    except ModuleNotFoundError:
        return 1, ["jsonschema is not installed: apt install python3-jsonschema"]

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
