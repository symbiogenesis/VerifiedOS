# SPDX-License-Identifier: Apache-2.0
"""Independent finite tests of the scoped laminar construction and deletion bound."""

import itertools
from dataclasses import replace
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory as memory
from vos import static_memory_structure as structure


def _case(intervals: tuple[tuple[int, int], ...],
          sizes: tuple[int, ...]) -> memory.Case:
    objects = tuple(memory.Object(str(i), "a", size, size, 1, start, end, end, end,
                                  end, 0)
                    for i, ((start, end), size) in enumerate(zip(intervals, sizes, strict=True)))
    return memory.Case("test", "private finite fixture", "one trace",
                       (memory.Arena("a", "owner", max(1, sum(sizes))),), objects)


def _is_laminar(intervals: tuple[tuple[int, int], ...]) -> bool:
    # Crossing is the strict interlacing endpoint order; equal endpoints nest.
    return not any(a < c < b < d or c < a < d < b
                   for (a, b), (c, d) in itertools.combinations(intervals, 2))


def _finite_constructor() -> None:
    domain = tuple(itertools.combinations(range(4), 2))
    accepted = refused = 0
    for intervals in itertools.product(domain, repeat=3):
        for sizes in itertools.product((1, 2), repeat=3):
            case = _case(intervals, sizes)
            try:
                placement = structure.laminar_placement(case)
            except memory.CaseError:
                ensure(not _is_laminar(intervals), "constructor refused a laminar family")
                refused += 1
                continue
            ensure(_is_laminar(intervals), "constructor accepted crossing reservations")
            by_id = {row["id"]: row["base"] for row in placement}
            peak = 0
            for tick in range(4):
                used: set[int] = set()
                load = 0
                for obj in case.objects:
                    if obj.start <= tick < obj.reuse:
                        cells = set(range(by_id[obj.id], by_id[obj.id] + obj.size))
                        ensure(not used & cells, "byte oracle found overlapping live slots")
                        used.update(cells)
                        load += obj.size
                peak = max(peak, load)
            span = max(by_id[o.id] + o.size for o in case.objects)
            ensure(span == peak, "independent live-byte bound differs from span")
            accepted += 1
    ensure(accepted > 0 and refused > 0, "finite corpus must exercise both outcomes")


def _deletion_minimality_and_cutoff() -> None:
    domain = tuple(itertools.combinations(range(4), 2))
    for intervals in itertools.product(domain, repeat=3):
        case = _case(intervals, (1, 1, 1))
        receipt = structure.deletion_witness(case)
        minimum = min(len(intervals) - len(retained)
                      for count in range(4)
                      for retained in itertools.combinations(range(3), count)
                      if _is_laminar(tuple(intervals[i] for i in retained)))
        ensure(receipt["minimum"] == minimum, "deletion minimum differs from retained-set oracle")
        kept = tuple(interval for i, interval in enumerate(intervals)
                     if str(i) not in receipt["removed"])
        ensure(_is_laminar(kept), "deletion witness leaves a crossing")
        short = structure.deletion_witness(case, max_subsets=1)
        if minimum:
            ensure(short["status"] == "incomplete" and short["minimum"] is None,
                   "cutoff must never become an optimum")
            ensure(short["proven_lower_bound"] <= minimum, "cutoff lower bound unsound")
    for invalid in (0, -1, True):
        try:
            structure.deletion_witness(_case((), ()), invalid)
        except memory.CaseError:
            continue
        raise AssertionError("invalid subset budget accepted")


def _premises_and_binary_scale() -> None:
    huge = 1 << 1024
    case = _case(((0, huge), (1, 2), (2, 3)), (huge, huge + 1, huge + 2))
    placement = structure.laminar_placement(case)
    ensure(memory.placement_spans(case, placement)["a"] == 2 * huge + 2,
           "binary magnitudes must not require address enumeration")
    variants = [replace(case, arenas=(case.arenas[0], memory.Arena("b", "peer", 1))),
                replace(case, objects=(replace(case.objects[0], alignment=2),)),
                replace(case, arenas=(replace(case.arenas[0], capacity=1),))]
    for mutant in variants:
        try:
            structure.laminar_placement(mutant)
        except memory.CaseError:
            continue
        raise AssertionError("unsupported theorem premise or insufficient capacity accepted")
    ensure(structure.laminar_placement(_case((), ())) == [], "empty family needs zero span")
    changed = replace(case, objects=tuple(reversed(case.objects)))
    ensure(placement == structure.laminar_placement(changed), "identity must fix tie order")


def _report() -> None:
    receipt: dict[str, Any] = structure.report("test-revision")
    ensure(not receipt["errors"], "structural witness replay failed")
    ensure(receipt == structure.report("test-revision"), "structural report must reproduce")
    gap = next(row for row in receipt["cases"]
               if row["contract"]["name"] == "alignment-breaks-equality")
    ensure(gap["exact"]["arenas"][0]["best_span_over_load"] == 1,
           "equal lifetimes with constrained bases must retain the negative result")


def cases() -> list[Case]:
    return [
        Case("structure laminar finite byte oracle", _finite_constructor),
        Case("structure deletion independent minimum and cutoff", _deletion_minimality_and_cutoff),
        Case("structure premises and binary magnitude", _premises_and_binary_scale),
        Case("structure replayable scoped report", _report),
    ]
