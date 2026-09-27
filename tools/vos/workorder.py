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
from typing import cast

from vos.jsonutil import unique_object

OWNER = "docs/implementation/work-order.json"
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


def _object(value: object, keys: set[str], where: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{where}: requires exactly {', '.join(sorted(keys))}")
    return cast(dict[str, object], value)


def _strings(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or any(
            not isinstance(v, str) or not v.strip() or any(c in v for c in "|\r\n")
            for v in value):
        raise ValueError(f"{where}: requires a list of nonempty single-line strings")
    values = cast(list[str], value)
    if len(values) != len(set(values)):
        raise ValueError(f"{where}: duplicate entry")
    return values


def _read(root: Path, leaves: dict[str, bool]) -> WorkOrder:
    """Read full leaf labels with completion flags; unique short IDs are permitted."""
    result = WorkOrder()
    raw: object = json.loads((root / OWNER).read_text(encoding="utf-8"),
                             object_pairs_hook=unique_object)
    owner = _object(raw, {"version", "buckets", "dispatch", "unpriced"}, OWNER)
    if type(owner["version"]) is not int or owner["version"] != 1:
        raise ValueError(f"{OWNER}: unsupported version")
    buckets = _object(owner["buckets"], set(BUCKETS), "buckets")

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
        labels = [resolve(key) for key in _strings(buckets[bucket], bucket)]
        for label in labels:
            if label in assigned:
                raise ValueError(f"{label}: assigned to multiple buckets")
            assigned.add(label)
        result.buckets[bucket] = labels
    missing = sorted(label for label, done in leaves.items() if not done and label not in assigned)
    if missing:
        raise ValueError("unclassified open priced leaves: " + "; ".join(missing))
    unpriced = _strings(owner["unpriced"], "unpriced")
    if not unpriced:
        raise ValueError("unpriced: requires the named obligation owner")
    for path in unpriced:
        if not artifact(path):
            raise ValueError(f"unpriced owner is missing: {path}")
    dispatch = owner["dispatch"]
    if not isinstance(dispatch, list):
        raise TypeError("dispatch: requires a list")
    seen: set[str] = set()
    for entry in dispatch:
        row = _object(entry, {"item", "start", "artifacts", "unmet", "join"}, "dispatch row")
        key = row["item"]
        if not isinstance(key, str):
            raise TypeError("dispatch item must be a string")
        label = resolve(key)
        if label in seen or label not in result.buckets["m8a"]:
            raise ValueError(f"{key}: duplicate or non-M8a dispatch row")
        seen.add(label)
        starts = [resolve(k) for k in _strings(row["start"], f"{key} start")]
        if label in starts:
            raise ValueError(f"{key}: a leaf cannot require its own completion to start")
        paths = _strings(row["artifacts"], f"{key} artifacts")
        unmet = _strings(row["unmet"], f"{key} unmet")
        if not starts and not paths and not unmet:
            raise ValueError(f"{key}: no authoring input or explicit missing predicate")
        blockers = [s.partition(" · ")[0] for s in starts if not leaves[s]]
        blockers += [p for p in paths if not artifact(p)]
        blockers += unmet
        joins = row["join"]
        if not isinstance(joins, list):
            raise TypeError(f"{key} join: requires a list")
        pending: list[str] = []
        joined: set[str] = set()
        for link in joins:
            join = _object(link, {"item", "output"}, f"{key} join")
            producer, output = join["item"], join["output"]
            if not isinstance(producer, str) or not isinstance(output, str) or not output.strip() \
                    or any(c in output for c in "|\r\n"):
                raise ValueError(f"{key} join: requires an item and a single-line output")
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
