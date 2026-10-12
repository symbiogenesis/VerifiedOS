# SPDX-License-Identifier: Apache-2.0
"""Finite spending oracle and live arithmetic defects for the M6.8 reference."""

from collections.abc import Callable
from dataclasses import replace
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import inference_grant as g
from vos.inference_contract import Refusal, Shape

INDEPENDENT_CASES = True


def spending_oracle(grant: int, traffic: int) -> int:
    """Spend one declared token at a time, independently of integer division."""
    remaining = grant
    rate = 0
    while remaining >= traffic:
        remaining -= traffic
        rate += 1
    return rate


def every_generated_rate_is_the_exact_spending_limit() -> None:
    for grant in range(65):
        for traffic in range(1, 33):
            rate = g.admitted_rate(grant, traffic)
            expected = spending_oracle(grant, traffic)
            ensure(rate == expected, f"rate differs from direct spending: {grant}/{traffic}/{rate}")
            ensure(rate is not None and rate * traffic <= grant,
                   "derived rate spends above the bank grant")
            ensure(rate is not None and (rate + 1) * traffic > grant,
                   "derived rate is not the maximal declared integer bound")


def every_generated_request_boundary_has_its_typed_verdict() -> None:
    for grant in range(65):
        for traffic in range(1, 33):
            boundary = spending_oracle(grant, traffic)
            for request in {0, max(0, boundary - 1), boundary, boundary + 1}:
                expected = None if request * traffic <= grant else Refusal.TOKEN_RATE_ABOVE_GRANT
                ensure(g.grant_refusal(grant, traffic, request) is expected,
                       f"request admitted/degraded with wrong spending verdict: {grant}/{traffic}/{request}")


def both_explicit_kv_placements_follow_the_source() -> None:
    shape = Shape(40, 64, 4, 8, 2, 8)
    ensure(g.per_token_bytes(shape, g.KvPlacement.BANK) == 48,
           "bank traffic omitted KV or multiplied it by context")
    ensure(g.per_token_bytes(shape, g.KvPlacement.OUTSIDE_BANK) == 40,
           "outside-bank KV was charged to the bank")
    ensure(g.admitted_rate(200, g.per_token_bytes(shape, g.KvPlacement.BANK)) == 4,
           "the bank-resident proof example changed")
    ensure(g.admitted_rate(200, g.per_token_bytes(shape, g.KvPlacement.OUTSIDE_BANK)) == 5,
           "the weights-only proof example changed")
    for resident in range(9):
        for kv in range(9):
            candidate = replace(shape, resident_bytes=resident, kv_bytes_per_token=kv)
            for placement in g.KvPlacement:
                expected = resident + kv if placement is g.KvPlacement.BANK else resident
                ensure(g.per_token_bytes(candidate, placement) == expected,
                       "generated traffic disagrees with the explicit placement")


def unrelated_shape_fields_cannot_supply_a_rate() -> None:
    shape = Shape(40, 64, 4, 8, 2, 8)
    for field in ("context_length", "format", "expert_count", "top_k"):
        for value in (0, 1, 99, 2 ** 64):
            changed = replace(shape, **{field: value})
            for placement in g.KvPlacement:
                ensure(g.per_token_bytes(changed, placement) == g.per_token_bytes(shape, placement),
                       f"rate followed unrelated {field}")


def undeclared_and_zero_traffic_refuse_even_a_zero_request() -> None:
    for grant in (0, 1, 200, 2 ** 128):
        for traffic in (None, 0):
            ensure(g.admitted_rate(grant, traffic) is None, "undeclared traffic supplied a rate")
            for request in (0, 1, 99):
                ensure(g.grant_refusal(grant, traffic, request)
                       is Refusal.PER_TOKEN_BYTES_NOT_DECLARED,
                       "zero/absent demand bypassed the opening refusal")
    ensure(g.admitted_rate(0, 1) == 0, "zero grant is confused with undeclared traffic")
    ensure(g.grant_refusal(0, 1, 0) is None, "zero request exceeds a declared zero rate")
    ensure(g.grant_refusal(0, 1, 1) is Refusal.TOKEN_RATE_ABOVE_GRANT,
           "a positive request escaped a zero grant")


def large_exact_integers_do_not_round_or_overflow() -> None:
    traffic = 2 ** 126 + 1
    grant = 4 * traffic - 1
    ensure(g.admitted_rate(grant, traffic) == 3, "large rate rounded up through floating point")
    ensure(g.grant_refusal(grant, traffic, 3) is None, "large inside-grant request refused")
    ensure(g.grant_refusal(grant, traffic, 4) is Refusal.TOKEN_RATE_ABOVE_GRANT,
           "large one-byte excess admitted")
    ensure(g.admitted_rate(4 * traffic, traffic) == 4, "exact large boundary refused")
    ensure(g.admitted_rate(2 ** 256, 1) == 2 ** 256, "rate truncated to a machine integer")


def rejected(action: Callable[[], object]) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("accepted a value outside the declared input domain")


def runtime_inputs_require_exact_naturals_and_explicit_placement() -> None:
    shape = Shape(40, 64, 4, 8, 2, 8)
    for value in (-1, True, 1.5, "1"):
        invalid = cast(int, value)
        rejected(lambda invalid=invalid: g.admitted_rate(invalid, 1))
        rejected(lambda invalid=invalid: g.admitted_rate(200, invalid))
        rejected(lambda invalid=invalid: g.grant_refusal(200, 48, invalid))
    for value in (None, "bank", "outside-bank", False):
        invalid_placement = cast(g.KvPlacement, cast(object, value))
        rejected(lambda invalid_placement=invalid_placement:
                 g.per_token_bytes(shape, invalid_placement))


def killed(target: str, candidate: Callable[..., object], oracle: Callable[[], None]) -> None:
    """Execute a live candidate against the same checks as the accepted reference."""
    with patch.object(g, target, candidate):
        try:
            oracle()
        except AssertionError:
            return
    raise AssertionError(f"live arithmetic defect survived: {target}")


def all_live_arithmetic_defects_are_killed() -> None:
    original = g.admitted_rate

    def adds_one(grant: int, traffic: int | None) -> int | None:
        rate = original(grant, traffic)
        return None if rate is None else rate + 1

    def rounds_up(grant: int, traffic: int | None) -> int | None:
        return None if not traffic else (grant + traffic - 1) // traffic

    def drops_grant(grant: int, traffic: int | None) -> int | None:
        return None if not traffic else 1

    def omits_kv(shape: Shape, placement: g.KvPlacement) -> int:
        return shape.resident_bytes

    def bypasses_above_grant(grant: int, traffic: int | None,
                            requested: int) -> Refusal | None:
        return None if traffic else Refusal.PER_TOKEN_BYTES_NOT_DECLARED

    for candidate in (adds_one, rounds_up, drops_grant):
        killed("admitted_rate", candidate, every_generated_rate_is_the_exact_spending_limit)
    killed("per_token_bytes", omits_kv, both_explicit_kv_placements_follow_the_source)
    killed("grant_refusal", bypasses_above_grant,
           every_generated_request_boundary_has_its_typed_verdict)


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        every_generated_rate_is_the_exact_spending_limit,
        every_generated_request_boundary_has_its_typed_verdict,
        both_explicit_kv_placements_follow_the_source,
        unrelated_shape_fields_cannot_supply_a_rate,
        undeclared_and_zero_traffic_refuse_even_a_zero_request,
        large_exact_integers_do_not_round_or_overflow,
        runtime_inputs_require_exact_naturals_and_explicit_placement,
        all_live_arithmetic_defects_are_killed,
    )]
