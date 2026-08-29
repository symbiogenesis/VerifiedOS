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

import os
import subprocess
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import env
from vos import proofs as proofs_mod
from vos.corpus import find_root

PROOFS = "proofs"
CLOSED = "Closed under the global context"

# The statement artifact, whose absence is reported by name: a gate over an empty
# directory would pass green with nothing enumerated to fail it.
STATEMENT = "ApexTheorem.v"

# The declared set, which R-05-164 reads from the register. It is empty today, and an
# entry is added here only when the register grows one, never to make a run pass.
DECLARED: set[str] = set()


def _hold(proofs: Path) -> int:
    """Hold the proofs directory for the whole run.

    Two concurrent gates rewrite each other's .vo mid-Require, so the second blocks
    until the first is done, which the unconditional recompile then makes a correct
    second verdict rather than a stale one. The lock is the directory's own descriptor
    rather than a lock file, because everything this gate writes is gitignored and a
    lock file beside the proofs would be a tree write nothing owns. The descriptor
    stays open, and locked, until the process exits.

    POSIX-only, and this file is typed on the host as well as run in the guest, so the
    import is deferred the way `vos.env` defers its own.
    """
    import fcntl  # noqa: PLC0415
    fd = os.open(str(proofs), os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _compile(root: Path, source: Path) -> subprocess.CompletedProcess[str]:
    # -Q roots the logical path so a companion's Require Import resolves to the .vo
    # built here, never to an installed one
    return subprocess.run(
        [*env.rocq_command(), "-q", "-Q", PROOFS, "",
         source.relative_to(root).as_posix()],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def _assumptions(stdout: str) -> tuple[int, list[str]]:
    """One compile's Print Assumptions output, read back block by block.

    An `Axioms:` header opens a block and is structure rather than a finding, and a
    wrapped axiom type's indented continuation lines belong to the entry above them,
    so an axiom compares against the declared set whole rather than line by line.
    Anything else the compiler printed is an entry too: chatter fails the gate rather
    than passing beneath it.
    """
    closed = 0
    entries: list[str] = []
    in_axioms = False
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == CLOSED:
            closed += 1
            in_axioms = False
            continue
        if line == "Axioms:":
            in_axioms = True
            continue
        if in_axioms and raw[:1].isspace() and entries:
            entries[-1] += f" {line}"
            continue
        entries.append(line)
    return closed, entries


def main() -> int:
    root = find_root()
    proofs = root / PROOFS
    statement = proofs / STATEMENT
    if not statement.exists():
        print(f"FAIL: {PROOFS}/{STATEMENT} is not in the repository")
        return 1
    _hold(proofs)

    # Every source is compiled and every verdict kept, so a run with two broken proofs
    # reports two rather than whichever came first. The recompile is unconditional on
    # every run, fresh .vo or not: the Print Assumptions output produced during
    # compilation is the evidence this gate reads, and a skipped compile is a skipped
    # enumeration.
    failures: list[tuple[Path, str]] = []
    closed = 0
    undeclared: list[str] = []
    for wave in proofs_mod.waves(sorted(proofs.glob("*.v"))):
        for source in wave:
            done = _compile(root, source)
            if done.returncode != 0:
                failures.append((source, done.stderr.strip()))
                continue
            enumerated, entries = _assumptions(done.stdout)
            closed += enumerated
            undeclared.extend(entry for entry in entries if entry not in DECLARED)

    if failures:
        for source, stderr in failures:
            print(f"FAIL: {source.name} did not compile:\n{stderr}")
        return 1
    if undeclared:
        print("FAIL: an assumption outside the declared set, which is empty (R-05-164):")
        for entry in undeclared:
            print(entry)
        return 1
    if not closed:
        print("FAIL: no constant was enumerated; the artifact must end in Print Assumptions")
        return 1
    print(f"ok: {closed} constant(s), each closed under the global context")
    return 0


if __name__ == "__main__":
    sys.exit(main())
