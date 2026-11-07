# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests for the Vela solver-trust ledger and its assumption audit."""

from tests.harness import Case, ensure
from vos.vela import solver_ledger

INDEPENDENT_CASES = True

_MODULE = "Vela_M"
_GALLINA = (
    "(* vela-solver-trust: vela_d3_Law at 7:5; theorem proof step discharged by the untrusted solver *)\n"
    "Axiom vela_solver_vela_d3_Law : forall (x : nat), x = x.\n"
    "Definition vela_d3_Law :=\n  vela_solver_vela_d3_Law.\n"
    "Definition vela_d4_Closed : nat := 0.\n"
)


def _ledger_reads_markers() -> None:
    entries = solver_ledger.ledger(_GALLINA)
    ensure(len(entries) == 1, f"expected one ledger entry, got {entries}")
    entry = entries[0]
    ensure(
        (entry.export, entry.axiom, entry.line, entry.column) == ("vela_d3_Law", "vela_solver_vela_d3_Law", 7, 5),
        f"unexpected ledger entry {entry}",
    )
    ensure(solver_ledger.ledger("Definition vela_d0_X : nat := 0.\n") == (), "closed output must have an empty ledger")


def _ledger_refuses_unmarked_axioms() -> None:
    for text in (
        "Axiom vela_solver_vela_d0_X : True.\nDefinition vela_d0_X := vela_solver_vela_d0_X.\n",
        _GALLINA + "Axiom hidden : False.\n",
        _GALLINA.replace("Axiom vela_solver_vela_d3_Law", "Axiom vela_solver_vela_d9_Other"),
    ):
        try:
            solver_ledger.ledger(text)
        except ValueError:
            continue
        raise AssertionError(f"ledger accepted an unmarked or misnamed axiom:\n{text}")


def _audit_matches_kernel_report() -> None:
    entries = solver_ledger.ledger(_GALLINA)
    report = (
        "Axioms:\n"
        "Vela_M.vela_solver_vela_d3_Law : forall x : nat, x = x\n"
        "Closed under the global context\n"
    )
    ensure(
        solver_ledger.audit(report, 2, _MODULE, entries) == ["Vela_M.vela_solver_vela_d3_Law"],
        "audit did not report the ledger axiom",
    )
    refusals = {
        "unledgered assumption": "Axioms:\nVela_M.hidden : False\nClosed under the global context\n",
        "missing report": "Axioms:\nVela_M.vela_solver_vela_d3_Law : forall x : nat, x = x\n",
        "unused ledger axiom": "Closed under the global context\nClosed under the global context\n",
    }
    for label, text in refusals.items():
        try:
            solver_ledger.audit(text, 2, _MODULE, entries)
        except ValueError:
            continue
        raise AssertionError(f"audit accepted a report with an {label}")


def cases() -> list[Case]:
    return [
        Case("ledger-reads-markers", _ledger_reads_markers),
        Case("ledger-refuses-unmarked-axioms", _ledger_refuses_unmarked_axioms),
        Case("audit-matches-kernel-report", _audit_matches_kernel_report),
    ]
