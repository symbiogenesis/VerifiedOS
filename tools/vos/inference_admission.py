# SPDX-License-Identifier: Apache-2.0
"""One host opening adapter joining finite residency and symbolic grant checks.

Inputs are decoded shapes, not wire descriptors. No target-server, physical
admission, measured token rate or parser correspondence is established here.
"""

from dataclasses import dataclass

from vos.inference_contract import Ceiling, Refusal, Shape, natural, require_record
from vos.inference_grant import KvPlacement, admitted_rate, grant_refusal, per_token_bytes
from vos.inference_residency import residency_refusal


@dataclass(frozen=True)
class Server:
    slot: int
    workers: tuple[int, ...]
    pool_bytes: int
    session_capacity: int

    def __post_init__(self) -> None:
        require_record(self, Server)
        natural(self.slot, "slot")
        natural(self.pool_bytes, "pool_bytes")
        natural(self.session_capacity, "session_capacity")
        if type(self.workers) is not tuple:
            raise ValueError("workers must be an immutable tuple")
        for worker in self.workers:
            natural(worker, "worker")


@dataclass(frozen=True)
class Step:
    server: Server
    sessions_open: int
    admitted_rate: int | None
    refusal: Refusal | None


def why_refused(ceiling: Ceiling, shape: Shape) -> Refusal | None:
    """Use the six ceiling predicates and their exact Gallina precedence."""
    require_record(ceiling, Ceiling)
    require_record(shape, Shape)
    checks = (
        (shape.resident_bytes <= ceiling.max_resident_bytes,
         Refusal.RESIDENT_BYTES_ABOVE_CEILING),
        (shape.context_length <= ceiling.max_context_length, Refusal.CONTEXT_ABOVE_CEILING),
        (shape.format in ceiling.admitted_formats, Refusal.FORMAT_NOT_ADMITTED),
        (shape.expert_count <= ceiling.max_expert_count, Refusal.EXPERT_COUNT_ABOVE_CEILING),
        (shape.top_k == ceiling.fixed_top_k, Refusal.TOP_K_NOT_THE_FIXED_VALUE),
        (shape.kv_bytes_per_token <= ceiling.max_kv_bytes_per_token,
         Refusal.KV_PER_TOKEN_ABOVE_CEILING),
    )
    return next((reason for valid, reason in checks if not valid), None)


def opening(shape: Shape, ceiling: Ceiling, residency: tuple[bool, ...],
            placement: KvPlacement, server: Server, sessions_open: int,
            requested_rate: int) -> Step:
    """Preserve resources and change occupancy only after every check succeeds."""
    require_record(shape, Shape)
    require_record(ceiling, Ceiling)
    require_record(server, Server)
    natural(sessions_open, "sessions_open")
    natural(requested_rate, "requested_rate")
    traffic = per_token_bytes(shape, placement)
    reason = residency_refusal(shape, residency) or why_refused(ceiling, shape)
    if reason is None:
        if traffic == 0:
            reason = Refusal.PER_TOKEN_BYTES_NOT_DECLARED
        elif sessions_open >= server.session_capacity:
            reason = Refusal.SESSION_POOL_EXHAUSTED
        else:
            reason = grant_refusal(ceiling.ceiling_grant, traffic, requested_rate)
    if reason is not None:
        return Step(server, sessions_open, None, reason)
    return Step(server, sessions_open + 1,
                admitted_rate(ceiling.ceiling_grant, traffic), None)
