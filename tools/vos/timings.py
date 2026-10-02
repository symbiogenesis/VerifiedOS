# SPDX-License-Identifier: Apache-2.0
"""Component durations a gate member records beside its report.

`run.py gate --summary` names one file per member in `ENV`. A member that measures its
parts, the behavioral tests by module, the selftest by phase and case and the checker by
fixed phase, rule group, and the generated group's blob read and rows, writes them there
as a JSON list once it has reported, and the gate folds that list into the member's
record as `units`. A member claims the variable as it starts, removing it from the
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
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import NamedTuple

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
    """Record `units` at `path`; nothing is recorded where none was named or writing fails."""
    if path is None:
        return
    with suppress(OSError):
        path.write_text(json.dumps(units, indent=1) + "\n", encoding="utf-8")


def read(path: Path) -> list[Unit] | None:
    """The units a member recorded at `path`, or None where it recorded no readable list."""
    try:
        found: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
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
    """

    def __init__(self, cpu: bool = False, origin: float | None = None) -> None:
        self._cpu = cpu
        self._origin = time.perf_counter() if origin is None else origin
        self._origin_at = time.time() - (time.perf_counter() - self._origin)
        self._measured: list[tuple[str, str, float, float, float | None, float | None]] = []
        self._lock = threading.Lock()

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
    def timing(self, kind: str, name: str) -> Iterator[None]:
        """Measure the block, whether it returns or raises."""
        begun = reading()
        try:
            yield
        finally:
            self.span(kind, name, begun, reading())

    def _record(self, kind: str, name: str, seconds: float, begun: float,
                cpu: float | None, child: float | None) -> None:
        with self._lock:
            self._measured.append((kind, name, seconds, begun - self._origin, cpu, child))

    def units(self) -> list[Unit]:
        with self._lock:
            measured = sorted(self._measured, key=lambda m: m[:4])
        units: list[Unit] = []
        for kind, name, seconds, start, cpu, child in measured:
            unit: Unit = {"kind": kind, "name": name, "seconds": round(seconds, 3),
                          "start": round(start, 3), "at": round(self._origin_at + start, 3)}
            if cpu is not None:
                unit["cpu_seconds"] = round(cpu, 3)
            if child is not None:
                unit["child_cpu_seconds"] = round(child, 3)
            units.append(unit)
        return units
