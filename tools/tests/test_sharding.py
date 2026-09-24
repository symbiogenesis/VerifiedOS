# SPDX-License-Identifier: Apache-2.0
"""Shard unions cover discovery exactly, including duplicate-valued cases."""

import argparse

from tests.harness import Case, ensure
from vos import sharding


def _complete_disjoint_partitions() -> None:
    for size in (1, 7, 16, 31):
        items = list(range(size))
        for count in range(1, size + 1):
            parts = [sharding.Shard(index, count).select(items)
                     for index in range(1, count + 1)]
            ensure(sorted(item for part in parts for item in part) == items,
                   "sharding omitted or duplicated a discovered item")
            ensure(all(part and part == sorted(part) for part in parts),
                   "a shard must be nonempty and retain discovery order")
            ensure(max(map(len, parts)) - min(map(len, parts)) <= 1,
                   "partition sizes differ by more than one")
    # Partition positions, not values: equal rule identifiers still own distinct cases.
    repeated = ["K-01"] * 9
    ensure(sum(len(sharding.Shard(i, 4).select(repeated)) for i in range(1, 5)) == 9,
           "duplicate-valued cases disappeared")


def _invalid_partitions() -> None:
    for value in ("", "1", "1/2/3", "x/2", "0/2", "3/2", "1/0", "-1/2"):
        try:
            sharding.parse(value)
        except argparse.ArgumentTypeError:
            pass
        else:
            raise AssertionError(f"invalid shard accepted: {value!r}")
    for index, total in ((0, 1), (2, 1), (1, 0)):
        try:
            sharding.Shard(index, total)
        except ValueError:
            pass
        else:
            raise AssertionError("programmatic callers bypassed shard validation")
    for items in ([], [1]):
        try:
            sharding.Shard(1, 2).select(items)
        except ValueError:
            pass
        else:
            raise AssertionError("a partition with empty peers must fail")
    ensure(str(sharding.parse("2/4")) == "2/4", "shard identity did not round-trip")


def cases() -> list[Case]:
    return [
        Case("complete-disjoint-partitions", _complete_disjoint_partitions),
        Case("invalid-partitions", _invalid_partitions),
    ]
