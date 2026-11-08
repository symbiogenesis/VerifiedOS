# SPDX-License-Identifier: Apache-2.0
"""Component timing snapshots recorded by gate members for `run.py gate --summary`.

`run.py gate --summary` passes each member a file path in `VOS_GATE_TIMINGS`. The member
pops the variable on startup (so child processes do not overwrite it) and writes JSON
duration units that the gate folds into the member's summary record. Timing I/O is
diagnostic and never affects a member's stdout or exit code.
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

# `os.times` reports child CPU seconds only on POSIX platforms.
_CHILDREN_COUNTED = sys.platform != "win32"

type Unit = dict[str, object]


class Reading(NamedTuple):
    """Wall-clock, process CPU, and waited-child CPU clock readings."""

    wall: float
    cpu: float
    child_cpu: float


def reading() -> Reading:
    """Return current wall, process CPU, and waited-child CPU readings."""
    times = os.times()
    return Reading(time.perf_counter(), time.process_time(),
                   times.children_user + times.children_system)


def claim() -> Path | None:
    """Pop and return the `VOS_GATE_TIMINGS` file path from the environment, if set."""
    value = os.environ.pop(ENV, "")
    return Path(value) if value else None


def write(path: Path | None, units: list[Unit]) -> None:
    """Best-effort atomic write of `units` to `path`."""
    if path is None:
        return
    try:
        with (atomic_path(path) as pending,
              pending.open("w", encoding="utf-8", newline="") as stream):
            stream.write(json.dumps(units, indent=1) + "\n")
    except OSError:
        pass


def read(path: Path) -> list[Unit] | None:
    """Read recorded timing units from `path`, or return `None` if missing or invalid."""
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
    """Thread-safe recorder for component durations and optional progress snapshots.

    Each unit records `start` (seconds since clock origin), `at` (epoch seconds), and
    `seconds`. When `cpu=True`, timed spans also record `cpu_seconds` and (on POSIX)
    `child_cpu_seconds`. When `snapshot` is given, active and completed spans are
    atomically checkpointed on each update while `units()` returns only completed spans.
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
        """Record a duration of `seconds` starting at `started` (or ending now)."""
        begun = time.perf_counter() - seconds if started is None else started
        self._record(kind, name, seconds, begun, None, None)

    def span(self, kind: str, name: str, begun: Reading, ended: Reading) -> None:
        """Record the span between `begun` and `ended`."""
        cpu = ended.cpu - begun.cpu if self._cpu else None
        child = ended.child_cpu - begun.child_cpu if self._cpu and _CHILDREN_COUNTED else None
        self._record(kind, name, ended.wall - begun.wall, begun.wall, cpu, child)

    @contextmanager
    def timing(self, kind: str, name: str) -> Generator[None]:
        """Context manager that times a block whether it returns or raises."""
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
        """Write a serialized snapshot while holding `_lock`."""
        if self._snapshot is not None:
            write(self._snapshot, self._units_locked(running=True))

    def units(self) -> list[Unit]:
        """Return completed timing units sorted by `(kind, name, seconds, start)`."""
        with self._lock:
            return self._units_locked()

    def _units_locked(self, *, running: bool = False) -> list[Unit]:
        """Render completed durations and, when `running=True`, active spans."""
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
