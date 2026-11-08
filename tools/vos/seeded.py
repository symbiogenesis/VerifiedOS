# SPDX-License-Identifier: Apache-2.0
"""Mutation-run verdicts, scope accounting, journaling, and reporting.

Verdicts:
- `killed`: reached the oracle and changed its output.
- `survived`: reached the oracle without changing its output (finding).
- `stillborn`: failed to compile before reaching the oracle (counted separately, not a
  finding; live score excludes stillborn mutants).
- `unseeded`: authored seed did not apply to the target artifact (finding).
- `undecided`: oracle timed out, died on a signal, or produced an unclassifiable status
  (finding).
"""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

KILLED = "killed"
SURVIVED = "survived"
STILLBORN = "stillborn"
UNSEEDED = "unseeded"
UNDECIDED = "undecided"


class Seeded(Protocol):
    """Protocol for a generated or authored mutant."""

    @property
    def what(self) -> str: ...


@dataclass(frozen=True)
class Scope:
    """Population coverage of a mutation run."""

    whole: int
    ran: int
    left: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        return self.ran < self.whole

    def decided(self, ran: int) -> Scope:
        """Return a copy updated with the count of mutants actually evaluated."""
        return Scope(whole=self.whole, ran=ran, left=self.left)

    def stated(self) -> str:
        """Format the scope clause for summary headers and closing lines."""
        if not self.partial:
            return f"over the whole population of {self.whole} mutant(s)"
        return (f"over {self.ran} of {self.whole} mutant(s), which is a sample and "
                "not the population")


@dataclass(frozen=True)
class Verdict:
    """Oracle outcome for a single mutant."""

    mutant: Seeded
    outcome: str
    detail: str
    moved: int = 0


class Journal:
    """Incremental line-flushed verdict log for long-running mutation campaigns."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._n = 0
        self._undecided = 0

    def start(self, subject: str, oracle_name: str, scope: Scope) -> str:
        """Initialize the journal file with the run header and return a status banner."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write("w", [f"== {subject} against the {oracle_name} oracle",
                          f"   scope: {scope.stated()}",
                          "   one line per verdict, as it is decided, and any note the "
                          "loop writes on lines opening `-- `; the closing line is "
                          "written only by a run that finished"])
        return (f"== every verdict is written to {self.path} as it is decided, so a "
                "run that does not finish still says what it decided")

    def record(self, verdict: Verdict, about: str = "") -> Verdict:
        """Append `verdict` (and optional `about` note) to the journal and return it."""
        with self._lock:
            self._n += 1
            if verdict.outcome == UNDECIDED:
                self._undecided += 1
            self._write("a", [*([f"-- {about} is verdict {self._n}"] if about else []),
                              f"{self._n:>5}  {verdict.outcome:<9} "
                              f"{verdict.mutant.what}: {verdict.detail}"])
        return verdict

    def note(self, text: str) -> None:
        """Append `-- `-prefixed diagnostic note lines to the journal."""
        with self._lock:
            self._write("a", [f"-- {line}" for line in text.splitlines() or [""]])

    def close(self, code: int) -> None:
        """Write the completion footer line with decided/undecided counts and exit code."""
        undecided = f", {self._undecided} undecided" if self._undecided else ""
        self._write("a", [f"== complete: {self._n - self._undecided} verdict(s) decided"
                          f"{undecided}, exit {code}"])

    def _write(self, mode: str, lines: list[str]) -> None:
        with self.path.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write("".join(f"{line}\n" for line in lines))


def findings_in(verdicts: list[Verdict]) -> int:
    """Count failing verdicts (`survived`, `unseeded`, `undecided`), or 1 if none are live."""
    counted = sum(1 for v in verdicts if v.outcome in (SURVIVED, UNSEEDED, UNDECIDED))
    live = any(v.outcome in (KILLED, SURVIVED) for v in verdicts)
    return counted + (0 if live or counted else 1)


def chosen[T](population: list[T], limit: int, sample: int) -> list[T]:
    """Select a `--sample` stride or `--limit` prefix of `population`."""
    if sample and sample < len(population):
        step = len(population) / sample
        return [population[int(n * step)] for n in range(sample)]
    return population[:limit] if limit else population


def shard[T](population: list[T], parts: int) -> list[list[T]]:
    """Partition `population` into `parts` strided shards to balance operator cost."""
    return [population[i::parts] for i in range(parts)]


def unshard[T](parts: list[list[T]]) -> list[T]:
    """Reconstruct population order from strided shards produced by `shard`."""
    return [part[k] for k in range(max((len(p) for p in parts), default=0))
            for part in parts if k < len(part)]


def summarize(out: list[str], verdicts: list[Verdict], subject: str,
              oracle_name: str, scope: Scope | None = None) -> int:
    """Append the mutation summary report to `out` and return the exit code (0 or 1)."""
    killed = [v for v in verdicts if v.outcome == KILLED]
    survived = [v for v in verdicts if v.outcome == SURVIVED]
    still = [v for v in verdicts if v.outcome == STILLBORN]
    unseeded = [v for v in verdicts if v.outcome == UNSEEDED]
    undecided = [v for v in verdicts if v.outcome == UNDECIDED]
    live = len(killed) + len(survived)

    out.append("")
    out.append(f"== {subject} against the {oracle_name} oracle")
    counted = (f"{len(killed)} killed, {len(survived)} survived, "
               f"{len(still)} stillborn")
    out.append(f"   {len(verdicts)} mutant(s) run: {counted}"
               + (f", {len(unseeded)} unseeded" if unseeded else "")
               + (f", {len(undecided)} undecided" if undecided else ""))
    if scope is not None:
        out.append(f"   scope: {scope.stated()}")
        if scope.left:
            out.append("   not asked about at all: " + ", ".join(scope.left))
    if killed:
        moved = [v.moved for v in killed if v.moved]
        span = (f", on between {min(moved)} and {max(moved)} lines"
                if moved else "")
        out.append(f"   every kill{span}")
        out.extend(f"     {v.mutant.what}: {v.detail}" for v in killed)
    if still:
        out.append(f"   {len(still)} stillborn, which decide nothing about the oracle:")
        out.extend(f"     {v.mutant.what}: {v.detail}" for v in still)
    out.append("")

    found = bool(findings_in(verdicts))
    if unseeded:
        out.append(f"FAIL {len(unseeded)} of {len(verdicts)} mutant(s) seeded nothing, "
                   f"so the {oracle_name} oracle was never asked about them:")
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in unseeded)
    if survived:
        out.append(f"FAIL {len(survived)} of {live} live mutant(s) survived the "
                   f"{oracle_name} oracle, so it does not reach the site:")
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in survived)
    if undecided:
        out.append(f"FAIL {len(undecided)} of {len(verdicts)} mutant(s) went undecided, "
                   f"the {oracle_name} oracle giving no answer about them:")
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in undecided)
    if not live and not unseeded and not undecided:
        out.append(f"FAIL every one of {len(verdicts)} mutant(s) was stillborn, so the "
                   f"{oracle_name} oracle decided nothing")
    if found:
        return 1
    said = f"ok all {live} live mutant(s) were killed by the {oracle_name} oracle"
    out.append(said if scope is None else f"{said}, {scope.stated()}")
    return 0
