# SPDX-License-Identifier: Apache-2.0
"""Symbolic bank spending for the finite InferenceAdmission.v host reference.

The declared grant is a composition input in bytes per second, not a measured
bandwidth. Both explicit KV placements mirror the proof's PerTokenBytes arms;
choosing a qualified physical placement remains the composition owner's work.
These functions decide arithmetic only. The common opening owns admission and
session state, and target throughput, kernel timing and DSE evidence remain open.
"""

from enum import StrEnum

from vos.inference_contract import Refusal, Shape, natural


class KvPlacement(StrEnum):
    BANK = "bank"
    OUTSIDE_BANK = "outside-bank"


def per_token_bytes(shape: Shape, placement: KvPlacement) -> int:
    """Read the proof's weights_and_cache or weights_only traffic declaration.

    Context length belongs to a separate footprint bound. It is not a multiplier
    in either PerTokenBytes definition. Neither arm is a physical qualification.
    """
    if placement is KvPlacement.BANK:
        return shape.resident_bytes + shape.kv_bytes_per_token
    if placement is KvPlacement.OUTSIDE_BANK:
        return shape.resident_bytes
    raise ValueError("KV placement must be explicitly declared")


def admitted_rate(grant_bytes_per_second: int, traffic: int | None) -> int | None:
    """Return the maximal integer rate, or no rate without positive byte demand.

    There is no load, queue, utilization or measured timing input. Zero grant with
    positive traffic has a declared rate of zero; zero/absent traffic has none.
    """
    natural(grant_bytes_per_second, "bank grant")
    if traffic is None:
        return None
    natural(traffic, "per-token traffic")
    if traffic == 0:
        return None
    return grant_bytes_per_second // traffic


def grant_refusal(grant_bytes_per_second: int, traffic: int | None,
                  requested_rate: int) -> Refusal | None:
    """Name the missing-demand or above-grant refusal without degrading a rate."""
    natural(requested_rate, "requested token rate")
    rate = admitted_rate(grant_bytes_per_second, traffic)
    if rate is None:
        return Refusal.PER_TOKEN_BYTES_NOT_DECLARED
    if requested_rate > rate:
        return Refusal.TOKEN_RATE_ABOVE_GRANT
    return None
