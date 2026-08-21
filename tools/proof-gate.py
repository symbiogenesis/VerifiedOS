#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The R-05-163 assumption gate, wired ahead of the first closing theorem as R-05-168
requires.

It compiles every shipped proof artifact and compares the mechanically enumerated
assumption set of each constant the artifact prints (its trailing Print Assumptions
block) against the declared set, which R-05-164 reads from the register: the admission
axioms of R-06-011, the bootstrap root of R-06-014, and the Ax ledger of R-18-031(c).
None of those is authored yet, so the declared set is empty and the only passing output
is "Closed under the global context". When the register's declared set gains an entry,
this gate grows an allowlist read from it, never from the development.

An admitted lemma, an unresolved obligation, a locally declared parameter, or any axiom
fails this gate rather than shipping green.

Needs the pinned Rocq switch, which `vos.env` locates and which is deliberately not the
switch the Sail toolchain lives in. From Windows: wsl -e python3 tools/proof-gate.py
"""

import subprocess
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import env
from vos.corpus import find_root

PROOFS = "proofs"
CLOSED = "Closed under the global context"

# The statement artifact compiles first because every companion imports it; the rest
# follow in name order.
STATEMENT = "ApexTheorem.v"

# The declared set, which R-05-164 reads from the register. It is empty today, and an
# entry is added here only when the register grows one, never to make a run pass.
DECLARED: set[str] = set()


def _compile(root: Path, source: Path) -> str:
    # -Q roots the logical path so a companion's Require Import resolves to the .vo
    # built here, never to an installed one
    proc = subprocess.run(
        [*env.rocq_command(), "-q", "-Q", PROOFS, "",
         str(source.relative_to(root).as_posix())],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)
    if proc.returncode != 0:
        raise SystemExit(f"FAIL: {source.name} did not compile:\n{proc.stderr.strip()}")
    return proc.stdout


def main() -> int:
    root = find_root()
    proofs = root / PROOFS
    statement = proofs / STATEMENT
    if not statement.exists():
        print(f"FAIL: {PROOFS}/{STATEMENT} is not in the repository")
        return 1

    sources = [statement] + sorted(p for p in proofs.glob("*.v") if p != statement)
    output = "".join(_compile(root, source) for source in sources)

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    closed = [line for line in lines if line == CLOSED]
    undeclared = [line for line in lines if line != CLOSED and line not in DECLARED]

    if undeclared:
        print("FAIL: an assumption outside the declared set, which is empty (R-05-164):")
        for line in undeclared:
            print(line)
        return 1
    if not closed:
        print("FAIL: no constant was enumerated; the artifact must end in Print Assumptions")
        return 1
    print(f"ok: {len(closed)} constant(s), each closed under the global context")
    return 0


if __name__ == "__main__":
    sys.exit(main())
