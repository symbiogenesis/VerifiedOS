# SPDX-License-Identifier: Apache-2.0
"""Deterministic, disjoint partitions of an ordered test population."""

import argparse
from dataclasses import dataclass
from typing import override


@dataclass(frozen=True)
class Shard:
    index: int
    total: int

    def __post_init__(self) -> None:
        if not 1 <= self.index <= self.total:
            raise ValueError("a shard must satisfy 1 <= INDEX <= TOTAL")

    @override
    def __str__(self) -> str:
        return f"{self.index}/{self.total}"

    def select[T](self, items: list[T]) -> list[T]:
        """Stride over discovery order, preserving order within each partition."""
        if self.total > len(items):
            raise ValueError(f"{self.total} shards exceed the {len(items)} available items")
        return items[self.index - 1::self.total]


def parse(value: str) -> Shard:
    """An argparse type, with the same validation as programmatic callers."""
    try:
        index, total = value.split("/")
        return Shard(int(index), int(total))
    except ValueError as err:
        raise argparse.ArgumentTypeError("use INDEX/TOTAL with 1 <= INDEX <= TOTAL") from err
