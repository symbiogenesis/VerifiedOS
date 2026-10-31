# SPDX-License-Identifier: Apache-2.0
"""Component durations a gate member records beside its report.

`run.py gate --summary` names one file per member in `ENV`. A member that measures its
parts, the behavioral tests by module, the selftest by phase and case and the checker by
fixed phase, rule group, and the generated group's blob read and rows, writes them there
as a JSON list, and the gate folds that list into the member's record as `units`.
Long-running members may checkpoint completed and still-running units so a timeout
retains progress; a normal completed record carries only completed units. A member
claims the variable as it starts, removing it from the
environment its own children inherit, so a nested run cannot write over its parent's
file. The durations are diagnostic: they never reach a member's printed report or its
exit code, and a member's file that cannot be written or read records nothing rather
than failing the run. The gate's scratch directory for those files is a temporary
directory like the others a run needs.
"""

import json
import os
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from vos.atomic import atomic_path

ENV = "VOS_GATE_TIMINGS"

# Windows's `os.times` reports no child process's CPU seconds, so a clock records them
# only where the platform counts them.
_CHILDREN_COUNTED = sys.platform != "win32"

type Unit = dict[str, object]


class Reading(NamedTuple):
    """The clocks read on either side of a timed block."""

    wall: float  # the `perf_counter` reading
    cpu: float  # this process's CPU seconds so far
    child_cpu: float  # those of the child processes it has waited for so far


def reading() -> Reading:
    """The clocks as they read now."""
    times = os.times()
    return Reading(time.perf_counter(), time.process_time(),
                   times.children_user + times.children_system)


def claim() -> Path | None:
    """This process's timings file, if the gate named one, taken out of the environment."""
    value = os.environ.pop(ENV, "")
    return Path(value) if value else None


def write(path: Path | None, units: list[Unit]) -> None:
    """Atomically replace a diagnostic snapshot, keeping its predecessor on failure."""
    if path is None:
        return
    try:
        with (atomic_path(path) as pending,
              pending.open("w", encoding="utf-8", newline="") as stream):
            stream.write(json.dumps(units, indent=1) + "\n")
    except OSError:
        pass


def read(path: Path) -> list[Unit] | None:
    """The units a member recorded at `path`, or None where it recorded no readable list."""
    try:
        found: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    if not isinstance(found, list):
        return None
    units: list[Unit] = []
    for unit in found:
        if not isinstance(unit, dict):
            return None
        units.append({str(key): value for key, value in unit.items()})
    return units


class Clock:
    """Durations measured from any thread, listed by kind, name and duration, so their
    order does not depend on which measurement finished first.

    Each unit's `start` is its offset in seconds from the clock's origin, the
    `perf_counter` reading it was made at unless it is given one, which places a member's
    parts on that member's timeline. Its `at` is the wall-clock time it began, in seconds
    since the epoch, which places the parts of the members that ran at once on one
    machine on one timeline. A clock made with `cpu` also records over each block it
    times this process's CPU seconds as `cpu_seconds`, and, except on Windows, those of
    the child processes it waited for as `child_cpu_seconds`: they are the block's own
    only where nothing else in the process runs beside it, as in the checker.

    A `snapshot` path opts into best-effort atomic progress records after a duration
    is added or a timed span starts or finishes. Active spans carry `status: running`
    and elapsed time at the last snapshot; `units()` still returns completed spans
    alone. The lock serializes both measurement updates and publication so an older
    writer cannot replace a newer snapshot after another thread finishes work.
    """

    def __init__(self, cpu: bool = False, origin: float | None = None,
                 snapshot: Path | None = None) -> None:
        self._cpu = cpu
        self._origin = time.perf_counter() if origin is None else origin
        self._origin_at = time.time() - (time.perf_counter() - self._origin)
        self._measured: list[tuple[str, str, float, float, float | None, float | None]] = []
        self._lock = threading.Lock()
        self._snapshot = snapshot
        self._active: dict[int, tuple[str, str, float]] = {}
        self._next_active = 0

    def add(self, kind: str, name: str, seconds: float, started: float | None = None) -> None:
        """Record a duration that began at the `perf_counter` reading `started`, or,
        where none is given, one that ends as it is recorded."""
        begun = time.perf_counter() - seconds if started is None else started
        self._record(kind, name, seconds, begun, None, None)

    def span(self, kind: str, name: str, begun: Reading, ended: Reading) -> None:
        """Record the block between two readings, with its CPU seconds on a CPU clock."""
        cpu = ended.cpu - begun.cpu if self._cpu else None
        child = ended.child_cpu - begun.child_cpu if self._cpu and _CHILDREN_COUNTED else None
        self._record(kind, name, ended.wall - begun.wall, begun.wall, cpu, child)

    @contextmanager
    def timing(self, kind: str, name: str) -> Generator[None]:
        """Measure the block, whether it returns or raises."""
        begun = reading()
        active: int | None = None
        if self._snapshot is not None:
            with self._lock:
                active = self._next_active
                self._next_active += 1
                self._active[active] = (kind, name, begun.wall)
                self._checkpoint_locked()
        try:
            yield
        finally:
            ended = reading()
            cpu = ended.cpu - begun.cpu if self._cpu else None
            child = ended.child_cpu - begun.child_cpu if self._cpu and _CHILDREN_COUNTED else None
            self._record(kind, name, ended.wall - begun.wall, begun.wall, cpu, child, active)

    def _record(self, kind: str, name: str, seconds: float, begun: float,
                cpu: float | None, child: float | None, active: int | None = None) -> None:
        with self._lock:
            self._measured.append((kind, name, seconds, begun - self._origin, cpu, child))
            if active is not None:
                self._active.pop(active)
            self._checkpoint_locked()

    def _checkpoint_locked(self) -> None:
        """Publish one serialized snapshot while no other thread can supersede it."""
        if self._snapshot is not None:
            write(self._snapshot, self._units_locked(running=True))

    def units(self) -> list[Unit]:
        """Completed measurements, in the same order whether checkpointing or not."""
        with self._lock:
            return self._units_locked()

    def _units_locked(self, *, running: bool = False) -> list[Unit]:
        """Render completed durations and, for snapshots, explicitly unfinished spans."""
        measured = [(measurement, False) for measurement in self._measured]
        if running:
            now = time.perf_counter()
            measured.extend(((kind, name, now - begun, begun - self._origin, None, None), True)
                            for kind, name, begun in self._active.values())
        measured.sort(key=lambda item: item[0][:4])
        units: list[Unit] = []
        for (kind, name, seconds, start, cpu, child), unfinished in measured:
            unit: Unit = {"kind": kind, "name": name, "seconds": round(seconds, 3),
                          "start": round(start, 3), "at": round(self._origin_at + start, 3)}
            if cpu is not None:
                unit["cpu_seconds"] = round(cpu, 3)
            if child is not None:
                unit["child_cpu_seconds"] = round(child, 3)
            if unfinished:
                unit["status"] = "running"
            units.append(unit)
        return units
