# SPDX-License-Identifier: Apache-2.0
"""Component durations a gate member records beside its report.

`run.py gate --summary` names one file per member in `ENV`. A member that measures its
parts, the behavioral tests by module and the selftest by phase and case, writes them
there as a JSON list once it has reported, and the gate folds that list into the
member's record as `units`. A member claims the variable as it starts, removing it from
the environment its own children inherit, so a nested run cannot write over its
parent's file. The durations are diagnostic: they never reach a member's printed report
or its exit code, and a file that cannot be written or read records nothing rather than
failing the run.
"""

import json
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

ENV = "VOS_GATE_TIMINGS"

type Unit = dict[str, object]


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
    order does not depend on which measurement finished first."""

    def __init__(self) -> None:
        self._measured: list[tuple[str, str, float]] = []
        self._lock = threading.Lock()

    def add(self, kind: str, name: str, seconds: float) -> None:
        with self._lock:
            self._measured.append((kind, name, seconds))

    @contextmanager
    def timing(self, kind: str, name: str) -> Iterator[None]:
        """Measure the block, whether it returns or raises."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.add(kind, name, time.perf_counter() - started)

    def units(self) -> list[Unit]:
        with self._lock:
            measured = sorted(self._measured)
        return [{"kind": kind, "name": name, "seconds": round(seconds, 3)}
                for kind, name, seconds in measured]
