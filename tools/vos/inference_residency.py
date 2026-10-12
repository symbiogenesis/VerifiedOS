# SPDX-License-Identifier: Apache-2.0
"""Finite host residency and work reference for InferenceAdmission.v.

The immutable flags adapt Gallina's total Residency function: an absent index is
nonresident. Costs supplies one uniform declared expert contribution. Equal
symbolic work under that premise is not a measured WCET or physical residency
claim, and this module implements no session, resource or descriptor pipeline.
"""

from dataclasses import dataclass

from vos.inference_contract import Costs, Refusal, Shape, natural

type Residency = tuple[bool, ...]
type Routing = tuple[int, ...]


def _validate_residency(res: Residency) -> None:
    if type(res) is not tuple or any(type(flag) is not bool for flag in res):
        raise ValueError("residency must be an immutable tuple of exact booleans")


def _resident(res: Residency, expert: int) -> bool:
    return expert < len(res) and res[expert]


def all_experts_resident(shape: Shape, res: Residency) -> bool:
    """Decide the entire declared expert prefix, including the empty prefix."""
    _validate_residency(res)
    return len(res) >= shape.expert_count and all(res[:shape.expert_count])


def residency_refusal(shape: Shape, res: Residency) -> Refusal | None:
    """The residency/top-k guards of the single composition_opening wrapper."""
    if not all_experts_resident(shape, res):
        return Refusal.EXPERT_NOT_RESIDENT
    if shape.top_k > shape.expert_count:
        return Refusal.TOP_K_NOT_THE_FIXED_VALUE
    return None


def routing_ok(shape: Shape, route: Routing) -> bool:
    """Gallina's exact length and expert-index predicates; repeats are valid."""
    if type(route) is not tuple or len(route) != shape.top_k:
        return False
    try:
        for expert in route:
            if natural(expert, "routed expert") >= shape.expert_count:
                return False
    except ValueError:
        return False
    return True


def checked_routed_work(shape: Shape, costs: Costs, res: Residency,
                        route: Routing) -> int | None:
    """Return declared fixed work only for a valid route and full residency.

    All experts share costs.expert_work_per_token by explicit premise. Residency
    alone would not make differently sized expert kernels routing blind. This
    guard mirrors checked_routed_work, which is separate from the admission
    wrapper's top-k/count guard and does not impose route uniqueness.
    """
    if not routing_ok(shape, route) or not all_experts_resident(shape, res):
        return None
    return costs.dense_work_per_token + sum(costs.expert_work_per_token for _ in route)


@dataclass(frozen=True)
class FromResidentBank:
    expert: int

    def __post_init__(self) -> None:
        natural(self.expert, "resident expert")


@dataclass(frozen=True)
class FetchRefused:
    reason: Refusal

    def __post_init__(self) -> None:
        if not isinstance(self.reason, Refusal):
            raise TypeError("fetch refusal must retain its typed cause")


def serve(res: Residency, expert: int) -> FromResidentBank | FetchRefused:
    """Serve resident bank data or refuse the routed storage boundary."""
    _validate_residency(res)
    natural(expert, "routed expert")
    if _resident(res, expert):
        return FromResidentBank(expert)
    return FetchRefused(Refusal.ROUTED_FETCH_ACROSS_STORAGE)
