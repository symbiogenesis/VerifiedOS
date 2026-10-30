# SPDX-License-Identifier: Apache-2.0
"""One authored rule registry, bound to callbacks and rendered as documentation."""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from vos.jsonutil import unique_object
from vos.schema import strict_integer_validator

if TYPE_CHECKING:
    from vos.checks import Context

SOURCE = "tools/check-registry.json"
DOCUMENT = "tools/check-rules.md"
TABLE_BEGIN = "<!-- BEGIN GENERATED CHECK REGISTRY -->"
TABLE_END = "<!-- END GENERATED CHECK REGISTRY -->"
REACH_BEGIN = "<!-- BEGIN GENERATED CHECK REACH -->"
REACH_END = "<!-- END GENERATED CHECK REACH -->"
ID_PATTERN = r"K-\d{2,3}[a-z]?"


class Reach(StrEnum):
    """The four ways a rule obtains the population it decides about."""

    NAME = "name"
    COMPUTED = "computed value"
    PATTERN = "pattern"
    TOTAL = "total"


@dataclass(frozen=True)
class Rule:
    """Required documentation and population metadata for one executable rule."""

    ident: str
    group: str
    meaning: str
    ground: str
    reach: Reach


@dataclass(frozen=True)
class Inactive:
    """A permanent ID kept unavailable after retirement or nonallocation."""

    ident: str
    kind: str
    ground: str


@dataclass(frozen=True)
class BoundGroup:
    """A callback and the rules whose verdicts its execution supplies."""

    name: str
    run: Callable[[Context], None]
    rules: tuple[Rule, ...]


@dataclass(frozen=True)
class Registry:
    rules: tuple[Rule, ...]
    inactive: tuple[Inactive, ...]

    @property
    def identifiers(self) -> frozenset[str]:
        return frozenset(rule.ident for rule in self.rules)

    def bind(self, implementations: Iterable[tuple[str, Callable[[Context], None]]]
             ) -> tuple[BoundGroup, ...]:
        """Require metadata and implementation in both directions, in execution order."""
        callbacks: dict[str, Callable[[Context], None]] = {}
        for name, run in implementations:
            if name in callbacks:
                raise ValueError(f"duplicate implementation group: {name}")
            if not callable(run):
                raise TypeError(f"group {name} has no callable implementation")
            callbacks[name] = run
        declared = {rule.group for rule in self.rules}
        if not any(rule.ident == "K-00" and rule.group == "meta" for rule in self.rules):
            raise ValueError("the registry requires K-00 in the final meta group")
        if not callbacks or next(reversed(callbacks)) != "meta":
            raise ValueError("the registry's meta group must execute last")
        if absent := declared - callbacks.keys():
            raise ValueError(f"rule group(s) with no implementation: {', '.join(sorted(absent))}")
        if absent := callbacks.keys() - declared:
            raise ValueError(f"implementation group(s) with no rule metadata: {', '.join(sorted(absent))}")
        return tuple(BoundGroup(name, run, tuple(r for r in self.rules if r.group == name))
                     for name, run in callbacks.items())


_TEXT: dict[str, object] = {"type": "string", "minLength": 1, "pattern": r"\S"}
_SCHEMA: dict[str, object] = {
    "type": "object", "required": ["version", "rules", "inactive"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": 1, "type": "integer"},
        "rules": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["id", "group", "meaning", "ground", "reach"],
            "additionalProperties": False,
            "properties": {"id": {"type": "string", "pattern": rf"^{ID_PATTERN}$"},
                           "group": {"type": "string", "pattern": r"^[a-z][a-z0-9_]*$"},
                           "meaning": _TEXT, "ground": _TEXT,
                           "reach": {"enum": [str(reach) for reach in Reach]}}}},
        "inactive": {"type": "array", "items": {
            "type": "object", "required": ["id", "kind", "ground"],
            "additionalProperties": False,
            "properties": {"id": {"type": "string", "pattern": rf"^{ID_PATTERN}$"},
                           "kind": {"enum": ["retired", "n/a"]}, "ground": _TEXT}}},
    },
}


def read(root: Path) -> Registry:
    """Decode required typed records; unknown fields and repeated IDs are refused."""
    raw = json.loads((root / SOURCE).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    validator = strict_integer_validator(_SCHEMA)
    errors = sorted(validator.iter_errors(raw), key=lambda err: str(list(err.path)))
    if errors:
        raise ValueError(f"{SOURCE}: {errors[0].message}")
    rules = tuple(Rule(row["id"], row["group"], row["meaning"], row["ground"],
                       Reach(row["reach"])) for row in raw["rules"])
    inactive = tuple(Inactive(row["id"], row["kind"], row["ground"])
                     for row in raw["inactive"])
    seen: set[str] = set()
    for record in (*rules, *inactive):
        if record.ident in seen:
            raise ValueError(f"duplicate rule ID: {record.ident}")
        seen.add(record.ident)
    return Registry(rules, inactive)


def _key(ident: str) -> tuple[int, str]:
    digits = ident[2:].rstrip("abcdefghijklmnopqrstuvwxyz")
    return int(digits), ident[2 + len(digits):]


def _replace(raw: str, begin: str, end: str, generated: str) -> str:
    """Replace one declared region, preserving every byte outside it."""
    if raw.count(begin) != 1 or raw.count(end) != 1:
        raise ValueError(f"{DOCUMENT} requires exactly one {begin} and {end}")
    before, rest = raw.split(begin)
    _, after = rest.split(end)
    newline = "\r\n" if "\r\n" in raw else "\n"
    body = generated.replace("\n", newline)
    return before + begin + newline + body + newline + end + after


def render(registry: Registry, raw: str) -> str:
    """Generate only the registry table and reach memberships; prose stays authored."""
    rows = {rule.ident: f"| {rule.ident} | {rule.group} | {rule.meaning} | {rule.ground} |"
            for rule in registry.rules}
    rows.update({row.ident: f"| ~~{row.ident}~~ | {row.kind} | n/a | {row.ground} |"
                 for row in registry.inactive})
    table = "\n".join(["| Rule | Group | Passing means | Ground |",
                       "| --- | --- | --- | --- |",
                       *(rows[ident] for ident in sorted(rows, key=_key))])
    reach = "\n".join(["| Reach class | Rules |", "| --- | --- |",
                       *(f"| {kind} | " + ", ".join(sorted(
                           (rule.ident for rule in registry.rules if rule.reach == kind),
                           key=_key)) + " |" for kind in Reach)])
    return _replace(_replace(raw, TABLE_BEGIN, TABLE_END, table),
                    REACH_BEGIN, REACH_END, reach)


def verdict_faults(rules: Iterable[Rule], reported: Iterable[str], *, clean: bool) -> list[str]:
    """Clean groups must decide every declared rule; no group may report an unknown one.

    One rule may emit several domain verdicts, as K-11 does for its vocabularies.
    A failed prerequisite may prevent dependent verdicts, but cannot yield a clean run.
    """
    expected = {rule.ident for rule in rules}
    actual = set(reported)
    faults = [f"undeclared rule verdict: {ident}" for ident in sorted(actual - expected)]
    if clean:
        faults += [f"declared rule produced no verdict: {ident}"
                   for ident in sorted(expected - actual)]
    return faults
