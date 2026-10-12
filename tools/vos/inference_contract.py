# SPDX-License-Identifier: Apache-2.0
"""Shared host inputs for the finite InferenceAdmission.v reference.

These records preserve the Gallina natural-number domain. They carry declared
composition inputs, never measured bandwidth, WCET or physical qualification.
"""

from dataclasses import dataclass, fields
from enum import StrEnum


def natural(value: int, name: str) -> int:
    """Refuse Python values outside Gallina's natural-number input domain."""
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _natural_fields(record: Shape | Costs) -> None:
    for item in fields(record):
        natural(getattr(record, item.name), item.name)


@dataclass(frozen=True)
class Shape:
    resident_bytes: int
    context_length: int
    format: int
    expert_count: int
    top_k: int
    kv_bytes_per_token: int

    def __post_init__(self) -> None:
        _natural_fields(self)


@dataclass(frozen=True)
class Ceiling:
    max_resident_bytes: int
    max_context_length: int
    admitted_formats: tuple[int, ...]
    max_expert_count: int
    fixed_top_k: int
    max_kv_bytes_per_token: int
    ceiling_grant: int

    def __post_init__(self) -> None:
        for item in fields(self):
            if item.name != "admitted_formats":
                natural(getattr(self, item.name), item.name)
        if type(self.admitted_formats) is not tuple:
            raise ValueError("admitted_formats must be an immutable tuple")
        for value in self.admitted_formats:
            natural(value, "admitted format")


@dataclass(frozen=True)
class Costs:
    dense_work_per_token: int
    expert_work_per_token: int
    fetch_penalty: int

    def __post_init__(self) -> None:
        _natural_fields(self)


class Refusal(StrEnum):
    DESCRIPTOR_NOT_CANONICAL = "DescriptorNotCanonical"
    RESIDENT_BYTES_ABOVE_CEILING = "ResidentBytesAboveCeiling"
    CONTEXT_ABOVE_CEILING = "ContextAboveCeiling"
    FORMAT_NOT_ADMITTED = "FormatNotAdmitted"
    EXPERT_COUNT_ABOVE_CEILING = "ExpertCountAboveCeiling"
    TOP_K_NOT_THE_FIXED_VALUE = "TopKNotTheFixedValue"
    # These are proof-constructor labels; "token" names inference traffic.
    KV_PER_TOKEN_ABOVE_CEILING = "KvPerTokenAboveCeiling"  # noqa: S105
    PER_TOKEN_BYTES_NOT_DECLARED = "PerTokenBytesNotDeclared"  # noqa: S105
    SESSION_POOL_EXHAUSTED = "SessionPoolExhausted"
    TOKEN_RATE_ABOVE_GRANT = "TokenRateAboveGrant"  # noqa: S105
    EXPERT_NOT_RESIDENT = "ExpertNotResident"
    ROUTED_FETCH_ACROSS_STORAGE = "RoutedFetchAcrossStorage"
    ROUTE_NOT_QUALIFIED = "RouteNotQualified"
