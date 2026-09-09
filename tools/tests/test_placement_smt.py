# SPDX-License-Identifier: Apache-2.0
"""Finite consistency reports cannot turn a sample or solver failure into a proof."""

import dataclasses
import subprocess

from tests.harness import Case, ensure
from tests.test_memplan import _TOY
from vos import env, memplan, placement_smt


def _plan() -> memplan.Plan:
    return memplan.plan_of(memplan.parse(_TOY), memplan.STANDING)


def _table_uses_the_exact_predicates() -> None:
    plan = _plan()
    table = placement_smt.build_table(plan, 0, 100)
    ensure(table.grid == 12 and table.complete, "the declared toy grid has twelve candidates")
    for i, bases in enumerate(table.bases):
        candidate = memplan.with_bases(plan, dict(zip(table.regions, bases, strict=True)))
        answers = memplan.admission_results(candidate)
        ensure(all((i in table.admitted[name]) == answer for name, answer in answers.items()),
               "the solver table must contain exactly the executable predicates' answers")
    emitted = placement_smt.emit(table, 1)
    ensure("R-08-014.colouring_ok" in emitted and "candidate_domain" in emitted,
           "contradiction evidence must identify requirements and the finite domain")


def _sat_witness_is_replayed() -> None:
    plan = _plan()
    table = placement_smt.build_table(plan, 0, 100)
    selected = next(i for i in range(len(table.bases))
                    if all(i in allowed for allowed in table.admitted.values()))

    def solver(script: str, timeout: float) -> str:
        return f"sat\n((candidate {selected}))" if "get-value" in script else "sat"

    found = placement_smt.decide(plan, table, 1, solver)
    ensure(found.verdict == "sat" and found.exit_code == 0 and bool(found.witness),
           f"the witness should be replayed and accepted: {found}")
    refused = next(i for i in range(len(table.bases))
                   if not all(i in allowed for allowed in table.admitted.values()))
    fake = placement_smt.decide(plan, table, 1,
                               lambda script, timeout: f"sat\n((candidate {refused}))"
                               if "get-value" in script else "sat")
    ensure(fake.verdict == "unknown" and "replay" in fake.reason,
           "a fabricated solver witness must fail exact replay")


def _unsat_requires_a_complete_grid() -> None:
    plan = _plan()
    table = placement_smt.build_table(plan, 0, 1)
    found = placement_smt.decide(plan, table, 1, lambda script, timeout: "unsat")
    ensure(found.verdict == "unknown" and found.exit_code == 2,
           "a prefix with no witness does not establish inconsistency")
    plan = dataclasses.replace(plan, island_spans=(32,))
    table = placement_smt.build_table(plan, 0, 100)
    found = placement_smt.decide(
        plan, table, 1, lambda script, timeout: "unsat\n(R-08-014.colouring_ok)"
        if "get-unsat-core" in script else "unsat")
    ensure(found.verdict == "unsat" and found.exit_code == 1
           and found.core == ("R-08-014.colouring_ok",),
           f"the complete impossible grid needs a replayable labelled core: {found}")


def _solver_failures_are_unknown() -> None:
    plan = _plan()
    table = placement_smt.build_table(plan, 0, 100)
    for answer in ("unknown", "", "success", "sat\n(error bad)"):
        found = placement_smt.decide(plan, table, 1,
                                    lambda script, timeout, reply=answer: reply)
        ensure(found.verdict == "unknown", f"unexpected solver result passed: {answer!r}")

    def timeout_solver(script: str, timeout: float) -> str:
        raise subprocess.TimeoutExpired("z3", timeout)

    ensure(placement_smt.decide(plan, table, 1, timeout_solver).verdict == "unknown",
           "process timeout must be a distinct undecided result")
    forged = placement_smt.decide(
        plan, table, 1, lambda script, timeout: "unsat\n(R-08-014.colouring_ok)"
        if "get-unsat-core" in script else "unsat")
    ensure(forged.verdict == "unknown" and "replay" in forged.reason,
           "a false contradiction core must fail finite-table replay")


def _limits_are_validated() -> None:
    plan = _plan()
    try:
        placement_smt.build_table(plan, 0, 0)
    except memplan.PlanError:
        pass
    else:
        raise AssertionError("a zero candidate budget must be rejected")
    table = placement_smt.build_table(plan, 0, 1)
    for limit in (0, -1, float("nan"), float("inf")):
        try:
            placement_smt.emit(table, limit)
        except memplan.PlanError:
            continue
        raise AssertionError(f"an invalid timeout passed: {limit}")


def _pinned_z3_decides_both_cases() -> None:
    binary = str(env.Z3_PREFIX / "bin" / "z3")

    def solver(script: str, timeout: float) -> str:
        return placement_smt.invoke(binary, script, timeout)

    for span, verdict in ((64, "sat"), (32, "unsat")):
        plan = dataclasses.replace(_plan(), island_spans=(span,))
        table = placement_smt.build_table(plan, 0, 100)
        found = placement_smt.decide(plan, table, 5, solver)
        ensure(found.verdict == verdict, f"pinned Z3 returned {found} for span {span}")


def cases() -> list[Case]:
    return [
        Case("table-uses-exact-predicates", _table_uses_the_exact_predicates),
        Case("sat-witness-replayed", _sat_witness_is_replayed),
        Case("unsat-needs-complete-grid", _unsat_requires_a_complete_grid),
        Case("solver-failures-unknown", _solver_failures_are_unknown),
        Case("limits-validated", _limits_are_validated),
        Case("pinned-z3-sat-and-unsat", _pinned_z3_decides_both_cases, lane="toolchain"),
    ]
