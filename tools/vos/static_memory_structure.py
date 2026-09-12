# SPDX-License-Identifier: Apache-2.0
"""Executable laminar construction and bounded deletion witnesses, not a prover.

The constructor uses binary integers and never enumerates addresses. Independent
placement and load checks validate its output. Deletion search concerns the actual
reservation intervals only and establishes no parameterized placement theorem.
"""

import itertools
from typing import Any

from vos import static_memory as memory


def crossing_pairs(case: memory.Case) -> list[tuple[str, str]]:
    """Pairwise violations of laminarity, irrespective of placement or size."""
    result: list[tuple[str, str]] = []
    for i, left in enumerate(case.objects):
        for right in case.objects[i + 1:]:
            disjoint = left.reuse <= right.start or right.reuse <= left.start
            contains = left.start <= right.start and right.reuse <= left.reuse
            contained = right.start <= left.start and left.reuse <= right.reuse
            if not (disjoint or contains or contained):
                result.append((min(left.id, right.id), max(left.id, right.id)))
    return sorted(result)


def laminar_placement(case: memory.Case) -> list[dict[str, Any]]:
    """Construct stack placement under the baseline theorem's exact premises.

    Equal intervals are ordered by identity and nest on the stack, which places
    their objects consecutively. The independent checker runs after construction;
    its quadratic replay is separate from the sorting/stack algorithm's cost.
    """
    if len(case.arenas) != 1 or any(o.alignment != 1 for o in case.objects):
        raise memory.CaseError("laminar theorem requires one arena and unit alignment")
    stack: list[tuple[memory.Object, int]] = []
    placement: list[dict[str, Any]] = []
    for obj in sorted(case.objects, key=lambda o: (o.start, -o.reuse, o.id)):
        while stack and stack[-1][0].reuse <= obj.start:
            stack.pop()
        if stack and obj.reuse > stack[-1][0].reuse:
            raise memory.CaseError("crossing reservation intervals violate laminarity")
        base = stack[-1][1] if stack else 0
        placement.append({"id": obj.id, "arena": obj.arena, "base": base})
        stack.append((obj, base + obj.size))
    placement.sort(key=lambda row: row["id"])
    errors = memory.check_placement(case, placement)
    if errors:
        raise memory.CaseError("constructed placement refused: " + "; ".join(errors))
    return placement


def deletion_witness(case: memory.Case, max_subsets: int = 10000) -> dict[str, Any]:
    """Minimum interval deletions by bounded subset enumeration of crossing edges.

    Every crossing edge needs an endpoint removed. Edges are independent of any
    deletion, so hitting every edge is exactly the required laminarity condition.
    Only fully exhausted smaller cardinalities contribute to the lower bound.
    """
    if type(max_subsets) is not int or max_subsets < 1:
        raise memory.CaseError("max_subsets must be a positive integer")
    pairs = crossing_pairs(case)
    identifiers = sorted(o.id for o in case.objects)
    subsets = 0
    for count in range(len(identifiers) + 1):
        for removed in itertools.combinations(identifiers, count):
            if subsets >= max_subsets:
                return {"status": "incomplete", "minimum": None,
                        "proven_lower_bound": count, "removed": None,
                        "subsets": subsets, "crossing_pairs": pairs}
            subsets += 1
            discarded = set(removed)
            if all(left in discarded or right in discarded for left, right in pairs):
                return {"status": "optimal", "minimum": count,
                        "proven_lower_bound": count, "removed": list(removed),
                        "subsets": subsets, "crossing_pairs": pairs}
    raise RuntimeError("deleting all intervals must remove every crossing")


def _contract(name: str, rows: list[tuple[str, int, int, int]],
              alignment: int = 1) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    base = 0
    for identifier, size, start, end in rows:
        base = (base + alignment - 1) // alignment * alignment
        objects.append({"id": identifier, "arena": "arena", "size": size,
                        "payload": size, "alignment": alignment, "base": base,
                        "start": start, "payload_end": end, "authority_end": end,
                        "sweep_end": end, "reuse": end})
        base += size
    return {"name": name, "provenance": "synthetic structural witness",
            "mode": "one declared execution",
            "arenas": [{"id": "arena", "owner": "owner", "capacity": max(1, base)}],
            "objects": objects}


def report(source_revision: str = "unspecified") -> dict[str, Any]:
    """Replay scoped positive and assumption-breaking construction witnesses."""
    huge = 1 << 256
    contracts = [
        _contract("equal-nested-disjoint", [("outer", 2, 0, 10),
                  ("equal", 3, 0, 10), ("left", 4, 1, 4), ("right", 6, 4, 9)]),
        _contract("crossing", [("a", 1, 0, 2), ("b", 1, 1, 3)]),
        _contract("three-mutually-crossing", [("a", 1, 0, 3),
                  ("b", 1, 1, 4), ("c", 1, 2, 5)]),
        _contract("alignment-breaks-equality", [("a", 1, 0, 1),
                  ("b", 1, 0, 1)], alignment=2),
        _contract("binary-address-scale", [("outer", huge, 0, huge),
                  ("left", huge + 1, 1, 3), ("right", huge + 2, 3, huge - 1)]),
        _contract("empty-family", []),
    ]
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in contracts:
        case = memory.parse_case(raw)
        item: dict[str, Any] = {
            "contract": raw, "contract_sha256": memory.contract_hash(case),
            "deletion": deletion_witness(case),
            "charged_load_lower_bound": memory.peak_load(case, "arena"),
        }
        supported = not crossing_pairs(case) and all(o.alignment == 1 for o in case.objects)
        try:
            placement = laminar_placement(case)
        except memory.CaseError as error:
            item.update({"construction": "outside-premises", "reason": str(error)})
            if supported:
                errors.append(f"{case.name}: supported construction refused: {error}")
        else:
            span = memory.placement_spans(case, placement)["arena"]
            item.update({"construction": "checked", "placement": placement,
                         "span": span, "attains_load": span == item["charged_load_lower_bound"]})
            if not item["attains_load"]:
                errors.append(f"{case.name}: laminar construction failed to attain load")
            if not supported:
                errors.append(f"{case.name}: construction accepted unsupported premises")
        if case.name == "alignment-breaks-equality":
            item["exact"] = memory.solve_exact(case)
            item["optimality_replay"] = memory.verify_optimality(case, item["exact"])
            if item["optimality_replay"]["status"] != "verified":
                errors.append("alignment witness optimality did not replay")
        results.append(item)
    return {
        "schema": "static-memory-structure-v1", "source_revision": source_revision,
        "scope": "executable finite evidence and a laminar constructor; no machine-checked theorem",
        "settings": {"deletion_max_subsets": 10000, "address_enumeration_in_constructor": False},
        "cases": results, "errors": errors,
        "open_obligations": [
            "source and admitted execution refinement to reservation intervals",
            "machine-checked general construction and optimality theorem",
            "parameterized placement algorithm or hardness proof for nonzero deletion count",
            "full CHERI, bank, owner and multiple-execution constraints",
        ],
    }
