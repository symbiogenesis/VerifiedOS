# SPDX-License-Identifier: Apache-2.0
"""Bounded two-stack candidate behind the portable planner's independent checker.

Only the recognized one-pool interval subset is converted. The structural
producer supplies feasible candidates, while optimality certification remains
the portable planner's separate finite replay. No exponential fallback is used.
"""

from dataclasses import asdict
from typing import Any

from vos import memory_planner as planner
from vos import memory_planner_candidates as candidates
from vos import static_memory as memory
from vos import static_memory_structure as structure


def object_limit(max_objects: int) -> int:
    """The caller declares the quadratic recognizer's maximum input count."""
    if type(max_objects) is not int or not 1 <= max_objects <= planner.MAX_INTEGER:
        raise planner.PlannerError("two-stack max_objects must be a positive bounded integer")
    return max_objects


def convert(instance: planner.Instance, *, max_objects: int) -> memory.Case:
    """Preserve identities and [start,end) exactly, refusing every richer constraint."""
    object_limit(max_objects)
    instance = planner.parse_instance(asdict(instance))
    if not 1 <= len(instance.buffers) <= max_objects:
        raise planner.UnsupportedError(f"two-stack requires 1..{max_objects} buffers")
    if len(instance.pools) != 1:
        raise planner.UnsupportedError("two-stack requires exactly one pool")
    pool = instance.pools[0]
    if pool.reserved:
        raise planner.UnsupportedError("two-stack does not support reserved ranges")
    if instance.conflicts:
        raise planner.UnsupportedError("two-stack does not support explicit conflicts")
    objects = []
    for buffer in instance.buffers:
        if buffer.size == 0 or buffer.alignment != 1 or len(buffer.intervals) != 1:
            raise planner.UnsupportedError(
                f"two-stack {buffer.id}: requires positive size, unit alignment and one nonempty interval")
        if buffer.fixed_pool is not None or buffer.fixed_offset is not None:
            raise planner.UnsupportedError(f"two-stack {buffer.id}: fixed locations are unsupported")
        if buffer.alias_of is not None or buffer.alias_offset:
            raise planner.UnsupportedError(f"two-stack {buffer.id}: aliases are unsupported")
        start, end = buffer.intervals[0]
        objects.append(memory.Object(buffer.id, pool.id, buffer.size, buffer.size, 1,
                                     start, end, end, end, end, 0))
    return memory.Case(instance.name, "portable-instance:" + planner.instance_digest(instance),
                       "unchanged-half-open-intervals", (memory.Arena(pool.id, pool.id, pool.capacity),),
                       tuple(objects))


class TwoStackCandidate:
    """A bounded synchronous producer with a separately retained diagnostic record."""

    def __init__(self, *, max_objects: int) -> None:
        self.max_objects = object_limit(max_objects)
        self.last_evidence: dict[str, Any] = {
            "method": "two-laminar-stacks", "max_objects": max_objects,
            "status": "not attempted", "findings": [],
            "certification": "separate portable finite replay required",
        }

    def __call__(self, instance: planner.Instance) -> planner.Placement:
        self.last_evidence = {
            "method": "two-laminar-stacks", "max_objects": self.max_objects,
            "status": "unsupported", "findings": [],
            "certification": "separate portable finite replay required",
            "instance_digest": planner.instance_digest(instance), "objects": len(instance.buffers),
        }
        try:
            placement = self._produce(instance)
        except (planner.PlannerError, memory.CaseError) as error:
            self.last_evidence["findings"] = [str(error)]
            raise
        else:
            return placement

    def _produce(self, instance: planner.Instance) -> planner.Placement:
        case = convert(instance, max_objects=self.max_objects)
        colouring = structure.two_colouring(case)
        self.last_evidence["crossing_graph"] = colouring
        if not colouring["bipartite"]:
            raise planner.UnsupportedError("two-stack crossing graph is not bipartite")
        self.last_evidence["peak_live_load"] = memory.peak_load(case, case.arenas[0].id)
        raw = structure.two_stack_placement(case, colouring["lower"], colouring["upper"])
        placement = [{"id": row["id"], "pool": row["arena"], "offset": row["base"]}
                     for row in raw]
        findings = planner.check_placement(instance, placement)
        if findings:
            self.last_evidence["status"] = "rejected candidate"
            raise planner.PlannerError("two-stack candidate refused: " + "; ".join(findings))
        heights = planner.pool_heights(instance, placement)
        if heights[case.arenas[0].id] != self.last_evidence["peak_live_load"]:
            self.last_evidence["status"] = "rejected candidate"
            raise planner.PlannerError("two-stack candidate did not attain the peak live load")
        self.last_evidence.update(status="checked candidate", pool_heights=heights)
        return placement


def corpus_report(*, max_objects: int) -> dict[str, Any]:
    """Report eligibility and checked spans on the existing synthetic corpus, without timing."""
    object_limit(max_objects)
    results: list[dict[str, Any]] = []
    for instance in candidates.comparison_corpus():
        baseline = candidates.separate_baseline(instance)
        candidate = TwoStackCandidate(max_objects=max_objects)
        result = planner.plan(instance, baseline, candidates=(candidate,))
        results.append({"name": instance.name, "instance_digest": planner.instance_digest(instance),
                        "objects": len(instance.buffers), "candidate": candidate.last_evidence,
                        "eligible": candidate.last_evidence["status"] == "checked candidate",
                        "baseline_pool_heights": planner.pool_heights(instance, baseline),
                        "selected_pool_heights": planner.pool_heights(instance, result["placement"]),
                        "selected": result})
    return {"schema": "vos-two-stack-corpus-v1", "max_objects": max_objects,
            "scope": "existing synthetic interval corpus; eligibility and byte spans only; no timing or target capacity evidence",
            "results": results}
