# SPDX-License-Identifier: Apache-2.0
"""Finite consistency of the memory plan's existing executable predicates.

This is a truth-table encoding, not a second transcription of the arithmetic:
`memplan.admission_results` evaluates each candidate, and SMT asks whether one
candidate satisfies every labelled predicate. The finite grid is the same one
the enumerator uses. A truncated table can establish existence, never absence.
The proof status remains with MemoryPlan.v; no result interprets arbitrary prose.
"""

import itertools
import math
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from vos import memplan

type Verdict = Literal["sat", "unsat", "unknown"]
type Solver = Callable[[str, float], str]


@dataclass(frozen=True)
class Table:
    island: int
    regions: tuple[int, ...]
    grid: int
    bases: tuple[tuple[int, ...], ...]
    admitted: dict[str, tuple[int, ...]]

    @property
    def complete(self) -> bool:
        return len(self.bases) == self.grid


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    reason: str
    witness: tuple[tuple[int, int], ...] = ()
    core: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        return {"sat": 0, "unsat": 1, "unknown": 2}[self.verdict]


def build_table(plan: memplan.Plan, island: int, limit: int) -> Table:
    if limit < 1:
        raise memplan.PlanError("--max-candidates must be positive")
    regions, _, _, positions = memplan.candidate_grid(plan, island)
    grid = math.prod(len(domain) for domain in positions)
    accepted: dict[str, list[int]] = {name: [] for name in memplan.admission_results(plan)}
    standing = tuple(plan.base_of(r) for r in regions)
    choices: Iterator[tuple[int, ...]] = itertools.product(*positions)
    # Try the authored witness first when it belongs to the domain. A resource
    # cap should not overlook the very instance whose consistency is being asked.
    if all(base in domain for base, domain in zip(standing, positions, strict=True)):
        choices = itertools.chain((standing,), (choice for choice in choices if choice != standing))
    bases = tuple(itertools.islice(choices, limit))
    for i, choice in enumerate(bases):
        candidate = memplan.with_bases(plan, dict(zip(regions, choice, strict=True)))
        for name, admitted in memplan.admission_results(candidate).items():
            if admitted:
                accepted[name].append(i)
    return Table(island, regions, grid, bases,
                 {name: tuple(indices) for name, indices in accepted.items()})


def _label(name: str) -> str:
    return f"{dict(memplan.CONSTRAINTS)[name]}.{name}"


def emit(table: Table, timeout: float) -> str:
    """Only the finite relation is encoded; all arithmetic has one Python owner."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise memplan.PlanError("--timeout must be a finite positive number")
    lines = ["(set-logic QF_LIA)", "(set-option :produce-unsat-cores true)",
             f"(set-option :timeout {max(1, int(timeout * 1000))})",
             "(declare-const candidate Int)",
             f"(assert (! (and (<= 0 candidate) (< candidate {len(table.bases)}))"
             " :named candidate_domain))"]
    for name, accepted in table.admitted.items():
        expression = ("(or " + " ".join(f"(= candidate {i})" for i in accepted) + ")"
                      if accepted else "false")
        lines.append(f"(assert (! {expression} :named {_label(name)}))")
    return "\n".join([*lines, "(check-sat)", ""])


def invoke(binary: str, script: str, timeout: float) -> str:
    """One bounded solver process, with no global environment or shared files."""
    done = subprocess.run([binary, "-in", "-smt2"], input=script, capture_output=True,
                          text=True, encoding="utf-8", check=False, timeout=timeout + 1)
    if done.returncode:
        raise memplan.PlanError(f"Z3 exited {done.returncode}: {done.stderr or done.stdout}")
    return done.stdout.strip()


def decide(plan: memplan.Plan, table: Table, timeout: float, solver: Solver) -> Result:
    script = emit(table, timeout)
    try:
        first = solver(script, timeout).strip()
        if first == "unknown":
            return Result("unknown", "solver did not decide within its resource bound")
        if first not in ("sat", "unsat"):
            return Result("unknown", f"unrecognized solver output: {first!r}")
        if first == "unsat" and not table.complete:
            return Result("unknown", "sample is inconsistent; the candidate grid is incomplete")
        query = "(get-value (candidate))\n" if first == "sat" else "(get-unsat-core)\n"
        detail = solver(script + query, timeout).strip().splitlines()
        if not detail or detail[0] != first:
            return Result("unknown", "solver did not reproduce its verdict while producing evidence")
        payload = " ".join(detail[1:])
        if first == "sat":
            match = re.fullmatch(r"\(\(candidate (\d+)\)\)", payload)
            if match is None or int(match[1]) >= len(table.bases):
                return Result("unknown", f"invalid candidate witness: {payload!r}")
            bases = tuple(zip(table.regions, table.bases[int(match[1])], strict=True))
            if memplan.refused_by(memplan.with_bases(plan, dict(bases))):
                return Result("unknown", "solver witness failed exact predicate replay")
            return Result("sat", "witness replayed through the exact admission predicates", bases)
        if not payload.startswith("(") or not payload.endswith(")"):
            return Result("unknown", f"invalid contradiction core: {payload!r}")
        core = tuple(payload[1:-1].split())
        allowed = {"candidate_domain", *(_label(name) for name in table.admitted)}
        if not core or any(label not in allowed for label in core):
            return Result("unknown", f"unrecognized contradiction core: {payload!r}")
        remaining = set(range(len(table.bases)))
        for name, accepted in table.admitted.items():
            if _label(name) in core:
                remaining.intersection_update(accepted)
        if remaining:
            return Result("unknown", "contradiction core failed exact finite-table replay")
        return Result("unsat", "no candidate satisfies every predicate in the complete grid",
                      core=core)
    except subprocess.TimeoutExpired:
        return Result("unknown", "solver process exceeded its timeout")
