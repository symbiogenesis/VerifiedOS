# SPDX-License-Identifier: Apache-2.0
"""Elaborated constant-by-constant proof corpus reading and comparison.

[run.py proof-reading](cli/proof_reading.py) drives the prover; this module emits the
queries, parses the framed answers, validates readings against
[proof-reading.schema.json](../proof-reading.schema.json), and compares two readings.

For every constant enumerated by [proofaudit.py](proofaudit.py)'s `inventory_query`, a
reading records (under `Set Printing All` and `Set Printing Universes`):
- `check`: the output of `Check @name`.
- `about`: the output of `About name` without `Declared in` location lines, plus parsed
  `kind`, `opacity`, and `universes`.
- `print`: the output of `Print name` for transparent constants and inductives, or `null`
  for opaque constants and constructors.

Two normalizations are applied: `About`'s `Declared in` lines are dropped, and fresh
query-local universe levels (`<query_file>.<counter>`) in `Check` output are renamed
`?u1`, `?u2`, ... in first-appearance order.
"""

import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TypedDict, cast, override

from vos import proofaudit
from vos import schema as schema_mod
from vos.jsonutil import unique_object

FORMAT = "verifiedos-proof-reading"
SCHEMA = 1
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "proof-reading.schema.json"

MARKER = "VOS_PROOF_READING|"

# Derive `Set Printing` settings from `proofaudit.SETTINGS` plus `Set Printing Universes.`.
SETTINGS = "".join(line + "\n" for line in proofaudit.SETTINGS.splitlines()
                   if line.startswith("Set Printing")) + "Set Printing Universes.\n"

# Reserved module-name prefix for generated query files (used in fresh universe names).
QUERY_PREFIX = "VosReading"
PHASES = ("Inventory", "Facts", "Bodies")
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

KINDS = ("Constant", "Inductive", "Constructor")
LOCATION = "Declared in "
_EXPANDS = re.compile(r"Expands to: (\w+) (\S+)")
_UNIVERSES = re.compile(r"\S+ is (not universe polymorphic|universe polymorphic"
                        r"|template universe polymorphic(?: .*)?)")
_OPACITY = re.compile(r"\S+ is (transparent|opaque)")
# Non-default reduction strategies printed by Rocq 9.3 (`Global Opaque` / `Global Strategy`).
_STRATEGY = re.compile(r"\S+ is (?:opaque but may be made transparent"
                       r"|transparent \((?:level -?\d+|expand)\))")

FIELDS = ("kind", "opacity", "universes", "check", "about", "print")


class ReadingError(ValueError):
    """Raised when a native query answer or recorded reading is malformed or incomplete."""


class Entry(TypedDict):
    kind: str
    opacity: str
    universes: str
    check: str
    about: str
    print: str | None


class Module(TypedDict):
    constants: dict[str, Entry]


class Reader(TypedDict):
    prover: str
    prover_sha256: str
    query_flags: list[str]
    inventory_settings: str
    reading_settings: str


class Provenance(TypedDict):
    sources: dict[str, str]
    objects: dict[str, str]


class Reading(TypedDict):
    format: str
    schema: int
    reader: Reader
    modules: dict[str, Module]
    provenance: Provenance


@dataclass(frozen=True)
class About:
    """Parsed `About` metadata (`kind`, `opacity`, `universes`) and normalized text."""

    kind: str
    opacity: str
    universes: str
    text: str

    @property
    def printed(self) -> bool:
        """Whether `Print` output is expected (inductives and transparent constants)."""
        return self.kind == "Inductive" or (self.kind == "Constant"
                                            and self.opacity == "transparent")


class Difference(NamedTuple):
    """A single difference between two proof readings."""

    subject: str
    what: str
    detail: str = ""

    @override
    def __str__(self) -> str:
        return f"{self.subject}: {self.what}" + (f": {self.detail}" if self.detail else "")


def query_module(phase: str, module: str) -> str:
    """Return the logical query-file name for `phase` and `module`."""
    if phase not in PHASES:
        raise ValueError(f"unknown query phase {phase!r}")
    return f"{QUERY_PREFIX}{phase}_{module}"


def check_module(module: str) -> None:
    """Reject invalid module names or names starting with `QUERY_PREFIX`."""
    if MODULE.fullmatch(module) is None:
        raise ReadingError(f"a module name this reading cannot Require: {module!r}")
    if module.startswith(QUERY_PREFIX):
        raise ReadingError(f"{module} carries the prefix reserved for this reading's "
                           "own query files")


def _names(names: list[str]) -> list[str]:
    for name in names:
        if not proofaudit.QUALIFIED.fullmatch(name):
            raise ReadingError(f"invalid native symbol name {name!r}")
    return names


def _frame(key: str) -> str:
    # Open a proof before `idtac` to avoid Rocq 9.3 warnings outside proof mode.
    return f'Goal True. Proof. idtac "{MARKER}{key}". Abort.\n'


def facts_query(module: str, names: list[str]) -> str:
    """Build a framed `Check` and `About` query script for `names` in `module`."""
    lines = [f"Require {module}.\n", SETTINGS]
    for name in _names(names):
        lines += [_frame(f"{name}|check"), f"Check @{name}.\n",
                  _frame(f"{name}|about"), f"About {name}.\n"]
    return "".join(lines)


def bodies_query(module: str, names: list[str]) -> str:
    """Build a framed `Print` query script for `names` in `module`."""
    lines = [f"Require {module}.\n", SETTINGS]
    for name in _names(names):
        lines += [_frame(f"{name}|print"), f"Print {name}.\n"]
    return "".join(lines)


def _trimmed(lines: list[str]) -> str:
    """Join `lines` between the first and last non-blank line."""
    start = next((index for index, line in enumerate(lines) if line.strip()), len(lines))
    end = len(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def answers(stdout: str, keys: list[str]) -> dict[str, str]:
    """Split framed query `stdout` into a map over expected `keys` in exact order."""
    found: list[tuple[str, list[str]]] = []
    for line in stdout.splitlines():
        if line.startswith(MARKER):
            found.append((line[len(MARKER):], []))
        elif found:
            found[-1][1].append(line)
        elif line.strip():
            raise ReadingError(f"unframed query output: {line[:200]}")
    named = [key for key, _ in found]
    if named != keys:
        at = next((index for index, (asked, got) in enumerate(zip(keys, named, strict=False))
                   if asked != got), min(len(keys), len(named)))
        asked = keys[at] if at < len(keys) else "nothing"
        got = named[at] if at < len(named) else "nothing"
        raise ReadingError(f"the query's {len(named)} answer(s) do not enumerate its "
                           f"{len(keys)} question(s): at {at}, asked {asked}, answered {got}")
    out: dict[str, str] = {}
    for key, lines in found:
        text = _trimmed(lines)
        if not text:
            raise ReadingError(f"the query answered nothing for {key}")
        out[key] = text
    return out


def fresh_universes(text: str, query: str) -> str:
    """Rename `<query>.<counter>` universe levels in `text` to `?u1`, `?u2`, ... in order."""
    pattern = re.compile(rf"(?<![\w'.]){re.escape(query)}\.\d+(?![\w'])")
    renamed: dict[str, str] = {}
    return pattern.sub(
        lambda found: renamed.setdefault(found.group(), f"?u{len(renamed) + 1}"), text)


def parse_about(name: str, text: str) -> About:
    """Parse `About` output for `name` and strip `Declared in` location lines."""
    lines = text.splitlines()
    gap = next((index for index, line in enumerate(lines) if not line.strip()), None)
    if gap is None:
        raise ReadingError(f"About {name} printed no sentence after its statement")
    expands: list[tuple[str, str]] = []
    universes: list[str] = []
    opacity: list[str] = []
    for line in lines[gap + 1:]:
        if found := _EXPANDS.fullmatch(line):
            expands.append((found.group(1), found.group(2)))
        elif found := _UNIVERSES.fullmatch(line):
            universes.append(found.group(1))
        elif found := _OPACITY.fullmatch(line):
            opacity.append(found.group(1))
        elif _STRATEGY.fullmatch(line):
            raise ReadingError(f"About {name} states a reduction strategy this reading "
                               f"does not place: {line}")
    if len(expands) != 1:
        raise ReadingError(f"About {name} stated {len(expands)} expansions, not one")
    kind, target = expands[0]
    if kind not in KINDS:
        raise ReadingError(f"About {name} expands to a {kind}, which this reading "
                           "does not place")
    if target != name:
        raise ReadingError(f"About {name} expands to {target}")
    if len(universes) != 1:
        raise ReadingError(f"About {name} stated {len(universes)} universe sentences, "
                           "not one")
    if kind == "Constant" and not opacity:
        raise ReadingError(f"About {name} states no opacity, as for a constant with no "
                           "body: an axiom, a parameter, an admitted proof or a primitive, "
                           "which this reading does not place")
    if len(opacity) != (1 if kind == "Constant" else 0):
        raise ReadingError(f"About {name}, a {kind}, stated {len(opacity)} opacity "
                           "sentences")
    stated = universes[0]
    return About(
        kind=kind, opacity=opacity[0] if opacity else "n/a",
        universes=("monomorphic" if stated.startswith("not ")
                   else "template" if stated.startswith("template ") else "polymorphic"),
        text=_trimmed([line for line in lines if not line.startswith(LOCATION)]))


def entry(check: str, about: About, printed: str | None) -> Entry:
    """Construct one constant's `Entry`, verifying `printed` presence matches `about.printed`."""
    if about.printed != (printed is not None):
        raise ReadingError(f"a {about.opacity} {about.kind} was "
                           f"{'printed' if printed is not None else 'not printed'}")
    return {"kind": about.kind, "opacity": about.opacity, "universes": about.universes,
            "check": check, "about": about.text, "print": printed}


def _first_difference(base: str | None, candidate: str | None) -> str:
    """Format a compact summary of the first difference between `base` and `candidate`."""
    if base is None or candidate is None:
        return " -> ".join("not printed" if text is None else "printed"
                           for text in (base, candidate))
    if "\n" not in base and "\n" not in candidate and len(base) + len(candidate) < 120:
        return f"{base} -> {candidate}"
    old, new = base.splitlines(), candidate.splitlines()
    at = next((index for index, (left, right) in enumerate(zip(old, new, strict=False))
               if left != right), min(len(old), len(new)))
    left = old[at] if at < len(old) else "(ends)"
    right = new[at] if at < len(new) else "(ends)"
    return f"line {at + 1}: {left[:160]!r} -> {right[:160]!r}"


def compare(base: Reading, candidate: Reading) -> list[Difference]:
    """Compare `base` and `candidate` across `reader`, `modules`, and `FIELDS` (ignoring `provenance`)."""
    found: list[Difference] = []
    old_reader = cast("dict[str, object]", base["reader"])
    new_reader = cast("dict[str, object]", candidate["reader"])
    found.extend(Difference("reader", key, "differs")
                 for key in sorted(set(old_reader) | set(new_reader))
                 if old_reader.get(key) != new_reader.get(key))
    old, new = base["modules"], candidate["modules"]
    found.extend(Difference(stem, "module removed",
                            f"{len(old[stem]['constants'])} constant(s)")
                 for stem in sorted(set(old) - set(new)))
    found.extend(Difference(stem, "module added",
                            f"{len(new[stem]['constants'])} constant(s)")
                 for stem in sorted(set(new) - set(old)))
    for stem in sorted(set(old) & set(new)):
        before, after = old[stem]["constants"], new[stem]["constants"]
        found.extend(Difference(name, "removed") for name in sorted(set(before) - set(after)))
        found.extend(Difference(name, "added") for name in sorted(set(after) - set(before)))
        for name in sorted(set(before) & set(after)):
            was = cast("dict[str, str | None]", before[name])
            now = cast("dict[str, str | None]", after[name])
            found.extend(Difference(name, field, _first_difference(was[field], now[field]))
                         for field in FIELDS if was[field] != now[field])
    return found


@functools.cache
def _reading_validator() -> schema_mod.Validator:
    schema = cast("dict[str, object]", json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    return schema_mod.strict_integer_validator(schema)


def validate(reading: object) -> Reading:
    """Validate `reading` against `SCHEMA_PATH`."""
    failure = next(iter(_reading_validator().iter_errors(reading)), None)
    if failure is not None:
        raise ReadingError(f"not a proof reading at {failure.json_path}: {failure.message}")
    return cast("Reading", reading)


def load(path: Path) -> Reading:
    """Load and schema-validate a proof reading JSON file, rejecting duplicate keys."""
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"),
                                    object_pairs_hook=unique_object)
    except ValueError as error:
        raise ReadingError(f"{path}: {error}") from error
    return validate(loaded)
