# SPDX-License-Identifier: Apache-2.0
"""Atomic progress snapshots survive interruption and concurrent clock updates."""

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import timings


def _snapshots_keep_running_and_completed_units_separate() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-timing-progress-") as td:
        path = Path(td) / "units.json"
        clock = timings.Clock(snapshot=path)
        clock.add("phase", "setup", 0.5)
        with clock.timing("phase", "cases"):
            with clock.timing("case", "still running"):
                snapshot = timings.read(path) or []
                ensure({unit["name"] for unit in snapshot if unit.get("status") == "running"}
                       == {"cases", "still running"}, "active work must be explicit before it ends")
                ensure([unit["name"] for unit in clock.units()] == ["setup"],
                       "the completed-unit API must not include unfinished work")
            snapshot = timings.read(path) or []
            ensure({unit["name"] for unit in snapshot if unit.get("status") == "running"}
                   == {"cases"}, "finishing one span must leave its enclosing phase active")
        ensure(timings.read(path) == clock.units()
               and all("status" not in unit for unit in clock.units()),
               "normal completion must retain the established completed-unit schema and order")


def _snapshot_updates_are_serialized_across_threads() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-timing-threads-") as td:
        path = Path(td) / "units.json"
        clock = timings.Clock(snapshot=path)
        barrier = Barrier(4)

        def work(index: int) -> None:
            with clock.timing("case", f"worker {index}"):
                barrier.wait(timeout=10)
                clock.add("phase", f"done {index}", 0.25)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(work, range(4)))
        snapshot = timings.read(path)
        ensure(snapshot == clock.units() and len(snapshot or []) == 8,
               "a late atomic write must not overwrite a more complete concurrent snapshot")
        ensure([unit["name"] for unit in snapshot or []]
               == [*(f"worker {i}" for i in range(4)), *(f"done {i}" for i in range(4))],
               "snapshot completion must keep deterministic kind/name ordering")


def _failed_snapshot_preserves_previous_bytes_and_removes_temporary_file() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-timing-failure-") as td:
        path = Path(td) / "units.json"
        previous: list[timings.Unit] = [{"kind": "phase", "name": "already saved", "seconds": 1.0}]
        timings.write(path, previous)
        before = path.read_bytes()
        with patch.object(Path, "replace", side_effect=PermissionError("reader holds the target")):
            timings.write(path, [{"kind": "phase", "name": "new", "seconds": 2.0}])
            clock = timings.Clock(snapshot=path)
            with clock.timing("case", "diagnostics cannot change the result"):
                pass
        ensure(path.read_bytes() == before and timings.read(path) == previous,
               "a failed replacement must preserve the preceding complete snapshot")
        ensure(list(Path(td).iterdir()) == [path], "failed snapshots must not litter temporary files")
        ensure(len(clock.units()) == 1, "a diagnostic write failure must not lose the measurement")


def cases() -> list[Case]:
    return [Case("snapshots-keep-running-and-completed-units-separate",
                 _snapshots_keep_running_and_completed_units_separate),
            Case("snapshot-updates-are-serialized-across-threads",
                 _snapshot_updates_are_serialized_across_threads),
            Case("failed-snapshot-preserves-previous-bytes-and-removes-temporary-file",
                 _failed_snapshot_preserves_previous_bytes_and_removes_temporary_file)]
