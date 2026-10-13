# SPDX-License-Identifier: Apache-2.0
"""Malformed host records refuse before getters or early semantic decisions."""

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import fields
from typing import cast, override
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import inference_admission as admission
from vos import inference_grant as grant
from vos import inference_residency as residency
from vos.inference_contract import Ceiling, Costs, Refusal, Shape

SHAPE = Shape(40, 128, 1, 4, 2, 8)
CEILING = Ceiling(40, 128, (1,), 4, 2, 8, 200)
COSTS = Costs(10, 3, 100)
SERVER = admission.Server(7, (3, 5), 4096, 2)
RECORDS: tuple[type[Shape] | type[Ceiling] | type[Costs] | type[admission.Server], ...] = (
    Shape, Ceiling, Costs, admission.Server)
FIELD_NAMES: frozenset[str] = frozenset(item.name for record in RECORDS for item in fields(record))
READS: list[str] = []


def _observe(record: object, name: str) -> object:
    if name in FIELD_NAMES:
        READS.append(name)
    return object.__getattribute__(record, name)


class _Observed:
    @override
    def __getattribute__(self, name: str) -> object:
        return _observe(self, name)


class _Unchecked:
    # A derived record can replace constructor validation as well as its getters.
    def __post_init__(self) -> None:
        pass


class _ShapeGetter(_Unchecked, _Observed, Shape):
    pass


class _CeilingGetter(_Unchecked, _Observed, Ceiling):
    pass


class _CostsGetter(_Unchecked, _Observed, Costs):
    pass


class _ServerGetter(_Unchecked, _Observed, admission.Server):
    pass


class _Mutable(_Observed):
    def __init__(self, record: Shape | Ceiling | Costs | admission.Server) -> None:
        for item in fields(record):
            object.__setattr__(self, item.name, getattr(record, item.name))


def _refused_without_reads(action: Callable[[], object]) -> None:
    READS.clear()
    # Observe canonical peers too: a malformed Server cannot allow Shape traffic
    # calculation, and a malformed Costs cannot allow route predicates to run.
    with ExitStack() as stack:
        for record in RECORDS:
            stack.enter_context(patch.object(record, "__getattribute__", _observe))
        try:
            action()
        except ValueError:
            pass
        else:
            raise AssertionError("malformed record reached a semantic result")
    ensure(READS == [], f"record fields read before malformed-container refusal: {READS}")


def _getter_control(record: object, field: str, expected: object) -> None:
    READS.clear()
    ensure(getattr(record, field) == expected and READS == [field],
           "hostile record getter observation did not execute")


def _constructors_refuse_derived_records() -> None:
    class ShapeAlias(_Observed, Shape):
        pass

    class CeilingAlias(_Observed, Ceiling):
        pass

    class CostsAlias(_Observed, Costs):
        pass

    class ServerAlias(_Observed, admission.Server):
        pass

    constructors: tuple[Callable[[], object], ...] = (
        lambda: ShapeAlias(40, 128, 1, 4, 2, 8),
        lambda: CeilingAlias(40, 128, (1,), 4, 2, 8, 200),
        lambda: CostsAlias(10, 3, 100),
        lambda: ServerAlias(7, (3, 5), 4096, 2),
    )
    for action in constructors:
        _refused_without_reads(action)


def _shape_consumers_refuse_getters_and_mutable_lookalikes() -> None:
    hostile = _ShapeGetter(40, 128, 1, 4, 2, 8)
    mutable = _Mutable(SHAPE)
    for record in (hostile, mutable):
        _getter_control(record, "expert_count", 4)
        shape = cast(Shape, record)
        actions: tuple[Callable[[], object], ...] = (
            lambda: residency.all_experts_resident(shape, (True,) * 4),
            lambda: residency.all_experts_resident(shape, ()),
            lambda: residency.residency_refusal(shape, (False,) * 4),
            lambda: residency.routing_ok(shape, (0, 2)),
            lambda: residency.routing_ok(shape, ()),
            lambda: residency.checked_routed_work(shape, COSTS, (True,) * 4, (0, 2)),
            lambda: residency.checked_routed_work(shape, COSTS, (False,) * 4, ()),
            lambda: grant.per_token_bytes(shape, grant.KvPlacement.BANK),
            lambda: grant.per_token_bytes(shape, grant.KvPlacement.OUTSIDE_BANK),
            lambda: admission.why_refused(CEILING, shape),
            lambda: admission.opening(shape, CEILING, (True,) * 4,
                                      grant.KvPlacement.BANK, SERVER, 0, 4),
            lambda: admission.opening(shape, CEILING, (False,) * 4,
                                      grant.KvPlacement.BANK, SERVER, 2, 5),
        )
        for action in actions:
            _refused_without_reads(action)


def _cost_consumers_refuse_before_invalid_routes_or_missing_residency() -> None:
    hostile = _CostsGetter(10, 3, 100)
    mutable = _Mutable(COSTS)
    for record in (hostile, mutable):
        _getter_control(record, "expert_work_per_token", 3)
        costs = cast(Costs, record)
        for flags, route in (((True,) * 4, (0, 2)), ((True,) * 4, ()),
                             ((False,) * 4, (0, 2)), ((False,) * 4, (4, 4))):
            _refused_without_reads(
                lambda flags=flags, route=route:
                residency.checked_routed_work(SHAPE, costs, flags, route))


def _ceiling_and_server_refuse_before_opening_field_reads() -> None:
    ceiling_getter = _CeilingGetter(40, 128, (1,), 4, 2, 8, 200)
    server_getter = _ServerGetter(7, (3, 5), 4096, 2)
    for record in (ceiling_getter, _Mutable(CEILING)):
        _getter_control(record, "ceiling_grant", 200)
        ceiling = cast(Ceiling, record)
        _refused_without_reads(lambda: admission.why_refused(ceiling, SHAPE))
        for flags, occupancy, requested in (((True,) * 4, 0, 4),
                                            ((False,) * 4, 2, 5)):
            _refused_without_reads(
                lambda flags=flags, occupancy=occupancy, requested=requested:
                admission.opening(SHAPE, ceiling, flags, grant.KvPlacement.BANK,
                                  SERVER, occupancy, requested))
    for record in (server_getter, _Mutable(SERVER)):
        _getter_control(record, "session_capacity", 2)
        server = cast(admission.Server, record)
        for flags, occupancy, requested in (((True,) * 4, 0, 4),
                                            ((False,) * 4, 2, 5)):
            _refused_without_reads(
                lambda flags=flags, occupancy=occupancy, requested=requested:
                admission.opening(SHAPE, CEILING, flags, grant.KvPlacement.BANK,
                                  server, occupancy, requested))


def _canonical_retries_preserve_work_rates_and_resource_identity() -> None:
    flags = (True,) * 4
    for route in ((0, 2), (1, 3), (0, 0)):
        ensure(residency.routing_ok(SHAPE, route)
               and residency.checked_routed_work(SHAPE, COSTS, flags, route) == 16,
               "canonical uniform work differs from independent dense/top-k expectation")
    ensure(residency.all_experts_resident(SHAPE, flags)
           and residency.residency_refusal(SHAPE, flags) is None,
           "canonical full residency failed after hostile-container controls")
    missing = (True, True, False, True)
    ensure(residency.residency_refusal(SHAPE, missing) is Refusal.EXPERT_NOT_RESIDENT
           and residency.checked_routed_work(SHAPE, COSTS, missing, (0, 1)) is None,
           "canonical missing unrouted expert lost its refusal")
    for placement, traffic, rate in ((grant.KvPlacement.BANK, 48, 4),
                                    (grant.KvPlacement.OUTSIDE_BANK, 40, 5)):
        ensure(grant.per_token_bytes(SHAPE, placement) == traffic
               and grant.admitted_rate(200, traffic) == rate,
               "canonical KV placement lost independently expected traffic or rate")
        accepted = admission.opening(SHAPE, CEILING, flags, placement, SERVER, 1, rate)
        ensure(accepted.refusal is None and accepted.admitted_rate == rate
               and accepted.sessions_open == 2 and accepted.server is SERVER,
               "canonical retry changed opening occupancy or declared server identity")
        excess = admission.opening(SHAPE, CEILING, flags, placement, SERVER, 1, rate + 1)
        ensure(excess.refusal is Refusal.TOKEN_RATE_ABOVE_GRANT
               and excess.admitted_rate is None and excess.sessions_open == 1
               and excess.server is SERVER,
               "canonical above-grant retry changed resources or degraded its request")
    ensure(admission.why_refused(CEILING, SHAPE) is None,
           "canonical ceiling retry failed after hostile-container controls")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        _constructors_refuse_derived_records,
        _shape_consumers_refuse_getters_and_mutable_lookalikes,
        _cost_consumers_refuse_before_invalid_routes_or_missing_residency,
        _ceiling_and_server_refuse_before_opening_field_reads,
        _canonical_retries_preserve_work_rates_and_resource_identity,
    )]
