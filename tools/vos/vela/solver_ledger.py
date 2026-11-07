# SPDX-License-Identifier: Apache-2.0
"""Solver-trust ledger for elaborated Vela Gallina and its kernel assumption audit.

The mathematical elaborator emits an obligation it cannot kernel-prove as a named
`vela_solver_*` axiom carrying the real statement, preceded by a marker naming its
export, source location and reason. This module reads that ledger from emitted
text and checks that `Print Assumptions` reports exactly those axioms and nothing
else. A non-empty ledger is never acceptance evidence.
"""

import re
from dataclasses import dataclass

_MARKER = re.compile(
    r"^\(\* vela-solver-trust: (?P<export>\S+) at (?P<line>\d+):(?P<column>\d+); (?P<reason>.*?) \*\)\n"
    r"Axiom (?P<axiom>vela_solver_[A-Za-z0-9_]+) :",
    flags=re.MULTILINE,
)
_AXIOM = re.compile(r"^Axiom (\S+)", flags=re.MULTILINE)
_ASSUMPTION_NAME = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_'.]*) :")


@dataclass(frozen=True)
class TrustedObligation:
    """One obligation the kernel sees only as an assumption."""

    export: str
    axiom: str
    line: int
    column: int
    reason: str

    def as_json(self) -> dict[str, object]:
        return {"export": self.export, "axiom": self.axiom, "line": self.line,
                "column": self.column, "reason": self.reason}


def ledger(gallina: str) -> tuple[TrustedObligation, ...]:
    """Return every solver-trusted obligation declared in emitted Gallina.

    Every `Axiom` in the text must be a marked solver-trust axiom; anything else is
    an unledgered assumption and refuses.
    """
    entries = tuple(
        TrustedObligation(match["export"], match["axiom"], int(match["line"]),
                          int(match["column"]), match["reason"])
        for match in _MARKER.finditer(gallina)
    )
    declared = _AXIOM.findall(gallina)
    marked = [entry.axiom for entry in entries]
    if sorted(declared) != sorted(marked) or len(set(marked)) != len(marked):
        unmarked = sorted(set(declared) - set(marked))
        raise ValueError(f"emitted Gallina declares unledgered or duplicate axioms: {unmarked or marked}")
    for entry in entries:
        if entry.axiom != f"vela_solver_{entry.export}":
            raise ValueError(f"solver-trust axiom {entry.axiom} does not name its export {entry.export}")
    return entries


def audit(output: str, audited: int, module: str,
          entries: tuple[TrustedObligation, ...]) -> list[str]:
    """Check `Print Assumptions` output for `audited` exports against the ledger.

    Returns the sorted ledger axioms the kernel reported. Any other assumption,
    a missing report or a ledger axiom no export depends on refuses.
    """
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    reports = sum(1 for line in lines if line in {"Closed under the global context", "Axioms:"})
    if reports != audited:
        raise ValueError(f"expected {audited} assumption reports, found {reports}")
    allowed = {f"{module}.{entry.axiom}" for entry in entries}
    reported: set[str] = set()
    for line in lines:
        if line in {"Closed under the global context", "Axioms:"} or line[0].isspace():
            continue
        match = _ASSUMPTION_NAME.match(line)
        if match is None:
            continue
        name = match["name"]
        if name not in allowed:
            raise ValueError(f"exports depend on an unledgered assumption: {name}")
        reported.add(name)
    if reported != allowed:
        raise ValueError(f"ledger axioms not reported by any export: {sorted(allowed - reported)}")
    return sorted(reported)
