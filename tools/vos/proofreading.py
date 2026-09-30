# SPDX-License-Identifier: Apache-2.0
"""What a compiled proof corpus elaborates to, read constant by constant, and compared.

An edit across many proof sources that means to change no elaborated meaning needs an
instrument that would show a change, and none of the existing three does. The native
receipt holds each constant's `Search` type and assumptions, with no transparent body,
opacity, universe or inductive declaration; the [CIC corpus exporter](cli/cic_corpus.py)
prints bodies and deletes them once it has read its features; and the statement
freeze's contract reads one target's closure. This module is the parse half of the
reading that does: the queries it writes, the framed answers it reads back, the reading
it assembles and the comparison of two readings.
[run.py proof-reading](cli/proof_reading.py) drives the prover.

**A reading holds, for every constant the native inventory names, what Rocq printed
about it** in a process that only `Require`s the constant's module, under `Set Printing
All`, `Set Printing Universes` and the depth and width the proof audit sets:

- `check`, the answer to `Check @name`;
- `about`, the answer to `About name` less its location lines, which keeps the kind,
  opacity and universe sentences and every other line About prints, `Arguments` and
  projection lines among them;
- `print`, the answer to `Print name` for a transparent constant and for an inductive,
  and null for an opaque constant and a constructor, whose inductive's own `Print`
  declares it.

The inventory is the audit's own: [proofaudit.py](proofaudit.py)'s `inventory_query`,
read by its `inventory`, so this reading enumerates exactly what the gate enumerates.
`kind`, `opacity` and `universes` are read out of `about`, and whether a constant is
printed is decided from them rather than from its source keyword.

**Two normalizations, and no others.** About's `Declared in` lines are dropped, since
any edit above a declaration moves them. And `Check` on a universe-polymorphic constant
instantiates fresh universe levels that Rocq names after the query file and a counter
running over the whole query process, so that one constant's answer would depend on
how many were asked before it; those levels, and only those, are renamed `?u1`, `?u2`
in the order they first appear within the one answer. Everything else is byte for
byte what Rocq printed, binder names included.

**Every refusal is loud.** Each query is framed by a marker, as the audit frames its
own, and a line before the first marker, a marker out of order or repeated, a query
that answered nothing and an About this parse cannot place each stop the reading
rather than shortening it.

**Comparing two readings** names every difference: a changed reader, an added or
removed module, an added or removed constant, and each field of a constant present in
both. `provenance` records the source and object digests the reading was taken from
and is never compared, since two compiles of one source can differ in their objects
and mean the same thing.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TypedDict, cast, override

from jsonschema import Draft202012Validator

from vos import proofaudit
from vos.jsonutil import unique_object

FORMAT = "verifiedos-proof-reading"
SCHEMA = 1
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "proof-reading.schema.json"

MARKER = "VOS_PROOF_READING|"

# The audit's own printing settings, less its search filters, plus the universes the
# statement freeze reads. Taken from the audit's text rather than restated, so that the
# depth and width here are the audit's by construction.
SETTINGS = "".join(line + "\n" for line in proofaudit.SETTINGS.splitlines()
                   if line.startswith("Set Printing")) + "Set Printing Universes.\n"

# The query files this reading compiles are named after their phase and module, and a
# fresh universe level a query creates is named after its file, so the prefix is
# reserved: no module of that name may be read.
QUERY_PREFIX = "VosReading"
PHASES = ("Inventory", "Facts", "Bodies")
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# About's kinds this reading places. A kind outside them is a printer change or a
# declaration the inventory never returned before, and it refuses.
KINDS = ("Constant", "Inductive", "Constructor")
LOCATION = "Declared in "
_EXPANDS = re.compile(r"Expands to: (\w+) (\S+)")
_UNIVERSES = re.compile(r"\S+ is (not universe polymorphic|universe polymorphic"
                        r"|template universe polymorphic(?: .*)?)")
_OPACITY = re.compile(r"\S+ is (transparent|opaque)")

# The fields a comparison reads, in the order it reports them.
FIELDS = ("kind", "opacity", "universes", "check", "about", "print")


class ReadingError(ValueError):
    """A native answer, or a recorded reading, cannot support a complete reading."""


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
    """What About says a symbol is, and the answer this reading keeps."""

    kind: str
    opacity: str
    universes: str
    text: str

    @property
    def printed(self) -> bool:
        """Whether `Print` belongs in the reading: a transparent body or a declaration."""
        return self.kind == "Inductive" or (self.kind == "Constant"
                                            and self.opacity == "transparent")


class Difference(NamedTuple):
    """One entry two readings disagree about, and what the disagreement is."""

    subject: str
    what: str
    detail: str = ""

    @override
    def __str__(self) -> str:
        return f"{self.subject}: {self.what}" + (f": {self.detail}" if self.detail else "")


def query_module(phase: str, module: str) -> str:
    """The logical name of one phase's query file for one module."""
    if phase not in PHASES:
        raise ValueError(f"unknown query phase {phase!r}")
    return f"{QUERY_PREFIX}{phase}_{module}"


def check_module(module: str) -> None:
    """Refuse a module name this reading cannot query or could confuse with its own."""
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
    # Proof opens each marker goal, as in the audit: Rocq 9.3 warns otherwise, and a
    # diagnostic refuses the query.
    return f'Goal True. Proof. idtac "{MARKER}{key}". Abort.\n'


def facts_query(module: str, names: list[str]) -> str:
    """`Check` and `About` for every named constant, each answer under its own marker."""
    lines = [f"Require {module}.\n", SETTINGS]
    for name in _names(names):
        lines += [_frame(f"{name}|check"), f"Check @{name}.\n",
                  _frame(f"{name}|about"), f"About {name}.\n"]
    return "".join(lines)


def bodies_query(module: str, names: list[str]) -> str:
    """`Print` for every named constant, each answer under its own marker."""
    lines = [f"Require {module}.\n", SETTINGS]
    for name in _names(names):
        lines += [_frame(f"{name}|print"), f"Print {name}.\n"]
    return "".join(lines)


def _trimmed(lines: list[str]) -> str:
    """One answer's lines, verbatim between its first and last nonblank line."""
    start = next((index for index, line in enumerate(lines) if line.strip()), len(lines))
    end = len(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def answers(stdout: str, keys: list[str]) -> dict[str, str]:
    """Split one query's output into the answer each marker introduced.

    The keys are supplied and their order is the query's own, so an answer missing,
    repeated or out of place refuses here rather than landing under its neighbour.
    Nothing may precede the first marker: the settings print nothing, so a line there
    is output this reading did not ask for.
    """
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
    """The answer with the fresh universe levels its own query created renamed.

    Rocq names such a level `<query file>.<counter>`, and the counter runs over the
    whole process, so the name records how many questions came before rather than
    anything about the constant. Each is renamed `?u<n>` by first appearance, which
    keeps which occurrences are one level and drops only the count.
    """
    pattern = re.compile(rf"(?<![\w'.]){re.escape(query)}\.\d+(?![\w'])")
    renamed: dict[str, str] = {}
    return pattern.sub(
        lambda found: renamed.setdefault(found.group(), f"?u{len(renamed) + 1}"), text)


def parse_about(name: str, text: str) -> About:
    """About, read for the three facts this reading decides with, less its locations.

    About prints the symbol and its type, a blank line, and then one sentence per
    fact. The sentences are read only after that blank line, so a type that wraps
    cannot be taken for one. Each fact must be stated exactly once, the expansion must
    name the constant asked about, and a constant must state its opacity where nothing
    else may: a missing, doubled or unexpected sentence is a printer this parse has not
    read, and it refuses rather than defaulting.
    """
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
    """One constant's reading, refusing a body where none belongs or none where one does."""
    if about.printed != (printed is not None):
        raise ReadingError(f"a {about.opacity} {about.kind} was "
                           f"{'printed' if printed is not None else 'not printed'}")
    return {"kind": about.kind, "opacity": about.opacity, "universes": about.universes,
            "check": check, "about": about.text, "print": printed}


def _first_difference(base: str | None, candidate: str | None) -> str:
    """Where two answers first part, short enough to print beside the entry's name."""
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
    """Every entry the two readings disagree about; an empty list is equality.

    Provenance is not compared: it names the compile each reading was taken from,
    which is what two readings of one meaning are expected to differ in.
    """
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


def validate(reading: object) -> Reading:
    """The reading, refused unless the tracked schema describes it."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    failure = next(iter(Draft202012Validator(schema).iter_errors(reading)), None)
    if failure is not None:
        raise ReadingError(f"not a proof reading at {failure.json_path}: {failure.message}")
    return cast("Reading", reading)


def load(path: Path) -> Reading:
    """One recorded reading, refusing a repeated key and anything the schema refuses."""
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"),
                                    object_pairs_hook=unique_object)
    except ValueError as error:
        raise ReadingError(f"{path}: {error}") from error
    return validate(loaded)
