# SPDX-License-Identifier: Apache-2.0
"""Explicit priced-leaf membership and a bounded authoring/join view.

This is an accounting and dispatch record, not a scheduler. Unknown leaves,
ambiguous parent names and missing inputs are findings, never implicit commitment.
Only item completion and named artifact availability are computed; external
conditions remain explicit unmet predicates until their owner discharges them.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, cast

from vos.jsonutil import unique_object
from vos.schema import validate

OWNER = "docs/implementation/work-order.json"
SCHEMA = "docs/implementation/work-order.schema.json"
BUCKETS = ("m8a", "m8b", "committed", "conditional", "option")
START = "<!-- work-order:start -->"
END = "<!-- work-order:end -->"
HEADER = "| Leaf | Authoring inputs | Open acceptance joins |"
RULE = "| --- | --- | --- |"


@dataclass
class WorkOrder:
    buckets: dict[str, list[str]] = field(default_factory=dict)
    rows: list[tuple[str, str, str]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def table(self) -> str:
        return "\n".join([HEADER, RULE, *(f"| {a} | {b} | {c} |" for a, b, c in self.rows)])


class Join(TypedDict):
    item: str
    output: str


class Dispatch(TypedDict):
    item: str
    start: list[str]
    artifacts: list[str]
    unmet: list[str]
    join: list[Join]


class Declaration(TypedDict):
    version: int
    buckets: dict[str, list[str]]
    dispatch: list[Dispatch]
    unpriced: list[str]


def _read(root: Path, leaves: dict[str, bool]) -> WorkOrder:
    """Read full leaf labels with completion flags; unique short IDs are permitted."""
    result = WorkOrder()
    raw: object = json.loads((root / OWNER).read_text(encoding="utf-8"),
                             object_pairs_hook=unique_object)
    validate(root / SCHEMA, raw)
    owner = cast(Declaration, raw)

    def resolve(key: str) -> str:
        candidates = [label for label in leaves
                      if label == key or label.partition(" · ")[0] == key]
        if len(candidates) != 1:
            raise ValueError(f"{key}: must name one priced leaf, found {len(candidates)}")
        return candidates[0]

    def artifact(path: str) -> bool:
        candidate = Path(path)
        if candidate.is_absolute() or candidate.drive or ".." in candidate.parts or "\\" in path:
            raise ValueError(f"unsafe repository artifact path: {path}")
        return (root / candidate).is_file()

    assigned: set[str] = set()
    for bucket in BUCKETS:
        labels = [resolve(key) for key in owner["buckets"][bucket]]
        for label in labels:
            if label in assigned:
                raise ValueError(f"{label}: assigned to multiple buckets")
            assigned.add(label)
        result.buckets[bucket] = labels
    missing = sorted(label for label, done in leaves.items() if not done and label not in assigned)
    if missing:
        raise ValueError("unclassified open priced leaves: " + "; ".join(missing))
    for path in owner["unpriced"]:
        if not artifact(path):
            raise ValueError(f"unpriced owner is missing: {path}")
    seen: set[str] = set()
    for row in owner["dispatch"]:
        key = row["item"]
        label = resolve(key)
        if label in seen or label not in result.buckets["m8a"]:
            raise ValueError(f"{key}: duplicate or non-M8a dispatch row")
        seen.add(label)
        starts = [resolve(k) for k in row["start"]]
        if label in starts:
            raise ValueError(f"{key}: a leaf cannot require its own completion to start")
        blockers = [s.partition(" · ")[0] for s in starts if not leaves[s]]
        blockers += [p for p in row["artifacts"] if not artifact(p)]
        blockers += row["unmet"]
        pending: list[str] = []
        joined: set[str] = set()
        for join in row["join"]:
            producer, output = join["item"], join["output"]
            dependency = resolve(producer)
            if dependency == label or dependency in joined:
                raise ValueError(f"{key}: self or repeated join")
            joined.add(dependency)
            if not leaves[dependency]:
                pending.append(f"{producer}: {output}")
        if not leaves[label]:
            result.rows.append((key, "blocked: " + "; ".join(blockers) if blockers else
                                "available for authoring", "; ".join(pending) or "n/a"))
    required = set(result.buckets["m8a"])
    if seen != required:
        raise ValueError("dispatch must name every M8a leaf exactly once")
    return result


def read(root: Path, leaves: dict[str, bool]) -> WorkOrder:
    """Return findings rather than partial commitments for an unreadable owner."""
    try:
        return _read(root, leaves)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return WorkOrder(findings=[f"{OWNER}: {exc}"])
