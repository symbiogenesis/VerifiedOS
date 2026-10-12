# SPDX-License-Identifier: Apache-2.0
"""Independent finite host oracles and executed residency/work defects.

All magnitudes are declared synthetic inputs. These tests establish no native
proof correspondence, kernel WCET, physical memory placement or target behavior.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from itertools import product
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import inference_residency as residency
from vos.inference_contract import Costs, Refusal, Shape

INDEPENDENT_CASES = True


def _shape(experts: int, top_k: int) -> Shape:
    return Shape(40, 64, 5, experts, top_k, 16)


def _maps(extent: int) -> Iterator[tuple[bool, ...]]:
    yield from product((False, True), repeat=extent)


def _generated_residency() -> None:
    cases = 0
    for experts in range(5):
        for extent in range(experts + 2):
            for flags in _maps(extent):
                missing = set(range(experts)) - {
                    index for index, flag in enumerate(flags) if flag
                }
                for top_k in range(experts + 2):
                    shape = _shape(experts, top_k)
                    expected = (Refusal.EXPERT_NOT_RESIDENT if missing else
                                Refusal.TOP_K_NOT_THE_FIXED_VALUE if top_k > experts else None)
                    ensure(residency.all_experts_resident(shape, flags) == (not missing),
                           f"incomplete finite prefix: {shape}, {flags}")
                    ensure(residency.residency_refusal(shape, flags) == expected,
                           f"wrong residency/top-k refusal order: {shape}, {flags}")
                    cases += 1
    ensure(cases == 620, f"residency family lost a boundary: {cases}")


def _generated_routes() -> None:
    accepted = refused = 0
    for experts in range(4):
        for top_k in range(experts + 2):
            shape = _shape(experts, top_k)
            for extent in range(top_k + 2):
                for route in product(range(experts + 1), repeat=extent):
                    expected = len(route) == top_k and set(route) <= set(range(experts))
                    ensure(residency.routing_ok(shape, route) == expected,
                           f"route boundary disagrees: {shape}, {route}")
                    result = residency.checked_routed_work(
                        shape, Costs(10, 3, 100), (True,) * experts, route)
                    ensure(result == (10 + 3 * top_k if expected else None),
                           f"invalid route gained work or valid work differed: {shape}, {route}")
                    accepted += expected
                    refused += not expected
    ensure(accepted > 100 and refused > 1000, "route family lost accepted/refused cases")
    # Gallina permits repeats, while session admission independently bounds k.
    shape = _shape(1, 2)
    ensure(residency.checked_routed_work(shape, Costs(10, 3, 100), (True,), (0, 0)) == 16
           and residency.residency_refusal(shape, (True,)) == Refusal.TOP_K_NOT_THE_FIXED_VALUE,
           "route uniqueness or admission guard was silently added to routed work")


def _generated_fixed_work() -> None:
    cases = 0
    for experts in range(5):
        for top_k in range(experts + 2):
            shape = _shape(experts, top_k)
            for route in product(range(experts), repeat=top_k):
                for dense, expert_work, fetch_penalty in product((0, 1, 7), repeat=3):
                    costs = Costs(dense, expert_work, fetch_penalty)
                    # Independent fixed work, not the implementation's accumulation.
                    expected = dense + top_k * expert_work
                    ensure(residency.checked_routed_work(shape, costs, (True,) * experts, route)
                           == expected, f"uniform declared work varied: {shape}, {route}, {costs}")
                    cases += 1
                for flags in _maps(experts):
                    expected = (10 + 3 * top_k if all(flags) else None)
                    ensure(residency.checked_routed_work(shape, Costs(10, 3, 100), flags, route)
                           == expected, f"only routed experts checked for residency: {flags}, {route}")
    ensure(cases > 40000, "fixed-work family lost its route/cost boundaries")


def _storage_boundary_oracle() -> None:
    for extent in range(5):
        for flags in _maps(extent):
            for expert in range(extent + 2):
                expected = (residency.FromResidentBank(expert)
                            if expert in {index for index, flag in enumerate(flags) if flag}
                            else residency.FetchRefused(Refusal.ROUTED_FETCH_ACROSS_STORAGE))
                ensure(residency.serve(flags, expert) == expected,
                       f"storage boundary lost its resident source/typed refusal: {flags}, {expert}")


def _uniform_work_oracle() -> None:
    shape = _shape(4, 2)
    costs = Costs(10, 3, 100)
    observations = [residency.checked_routed_work(shape, costs, (True,) * 4, route)
                    for route in product(range(4), repeat=2)]
    ensure(observations == [16] * 16,
           "all-resident fixed top-k work depends on the expert indices")


@dataclass(frozen=True)
class _FromStorage:
    expert: int


def _storage_fetch_defect(flags: tuple[bool, ...], expert: int
                          ) -> residency.FromResidentBank | _FromStorage:
    # Executed alternative to the real serving function: demand paging.
    return (residency.FromResidentBank(expert) if expert < len(flags) and flags[expert]
            else _FromStorage(expert))


def _expert_dependent_defect(shape: Shape, costs: Costs, flags: tuple[bool, ...],
                            route: tuple[int, ...]) -> int | None:
    if not residency.routing_ok(shape, route) or not residency.all_experts_resident(shape, flags):
        return None
    # Every expert is resident, but the wrongly varying kernel width adds work.
    return costs.dense_work_per_token + sum(costs.expert_work_per_token * (expert + 1)
                                           for expert in route)


def _only_routed_residency_defect(shape: Shape, costs: Costs, flags: tuple[bool, ...],
                                 route: tuple[int, ...]) -> int | None:
    if not residency.routing_ok(shape, route):
        return None
    if not all(expert < len(flags) and flags[expert] for expert in route):
        return None
    return costs.dense_work_per_token + len(route) * costs.expert_work_per_token


def _caught(oracle: Callable[[], None], name: str) -> None:
    try:
        oracle()
    except AssertionError:
        return
    raise AssertionError(f"executed defect survived its independent oracle: {name}")


def _executed_defects() -> None:
    _storage_boundary_oracle()
    _uniform_work_oracle()
    with patch.object(residency, "serve", _storage_fetch_defect):
        _caught(_storage_boundary_oracle, "routed storage fetch")
    with patch.object(residency, "checked_routed_work", _expert_dependent_defect):
        _caught(_uniform_work_oracle, "expert-dependent work")
    with patch.object(residency, "checked_routed_work", _only_routed_residency_defect):
        _caught(_generated_fixed_work, "missing unrouted expert")
    _storage_boundary_oracle()
    _uniform_work_oracle()


def _must_reject(fn: Callable[[], object], where: str) -> None:
    try:
        fn()
    except (TypeError, ValueError):
        return
    raise AssertionError(f"invalid host input accepted: {where}")


def _numeric_and_container_domain() -> None:
    class IntegerSubclass(int):
        pass

    shape = _shape(2, 1)
    for value in (-1, True, False, 1.0, "1", IntegerSubclass(1), None):
        route = (cast(int, value),)
        ensure(not residency.routing_ok(shape, route)
               and residency.checked_routed_work(shape, Costs(10, 3, 100), (True, True), route)
               is None, f"mistyped routed index accepted: {value!r}")
        _must_reject(lambda value=value: residency.serve((True,), cast(int, value)),
                     f"serve index {value!r}")
    for value in ([True, True], (True, 1), (1, 1), ("true",), None):
        flags = cast(tuple[bool, ...], value)
        _must_reject(lambda flags=flags: residency.all_experts_resident(shape, flags),
                     f"residency {value!r}")
        _must_reject(lambda flags=flags: residency.serve(flags, 0), f"serve residency {value!r}")
    for value in ([0], "0", None):
        ensure(not residency.routing_ok(shape, cast(tuple[int, ...], cast(object, value))),
               f"mutable or malformed route accepted: {value!r}")
    _must_reject(lambda: residency.FetchRefused(cast(Refusal, cast(object, "RoutedFetchAcrossStorage"))),
                 "erased refusal type")
    large = 2 ** 200
    ensure(residency.checked_routed_work(shape, Costs(large, large, large), (True, True), (1,))
           == 2 * large, "declared work lost exact integer precision")
    # Reference operations have no resource/state mutator; their input stays exact.
    before = replace(shape)
    residency.residency_refusal(shape, (True, False))
    ensure(shape == before, "residency checking expanded the declared shape")


def cases() -> list[Case]:
    return [Case("finite complete residency and ordered top-k boundary", _generated_residency),
            Case("finite exact route length/index boundaries with repeats", _generated_routes),
            Case("finite declared uniform work and every missing expert", _generated_fixed_work),
            Case("finite resident sources and typed storage refusal", _storage_boundary_oracle),
            Case("executed storage, varying work and partial residency defects", _executed_defects),
            Case("exact numeric domain and immutable reference inputs", _numeric_and_container_domain)]
