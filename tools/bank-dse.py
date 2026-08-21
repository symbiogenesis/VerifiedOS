#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Score every candidate second-class bank count against the arithmetic that exists.

R-15-247p admits bank granularity against three quantities jointly: the island
bandwidth ceiling §11 consumes, the read energy per bit that bitline capacitance sets,
and the R-15-247g simultaneous-activation envelope, with the droop envelope a hard
admission constraint and the other two objectives. Six of the seven coefficients those
three need are pending on a measurement nobody has taken, which
docs/bank-count-dse-contract.md states one row at a time.

So this tool is not the search. It is the part of the search that can be run before the
coefficients arrive: the shape constraints a candidate must satisfy whatever the
coefficients turn out to be, computed from the composition rather than copied from it,
with every coefficient-dependent column printing the symbol it waits on. **It admits
nothing**, and its verdict line says so, because a hard constraint with no operands
prunes nothing and a report that quietly stopped saying that would be the instrument
turning into the answer.

Exit 0 where the tree is consistent, 1 on a finding. It may be run from anywhere: the
repository root is found from this file, never from the working directory.
"""

import argparse
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import banks
from vos.corpus import find_root


def _cycles(n: int) -> str:
    """A cycle count beside the wall time it is, so a deadline comparison is legible
    without the reader doing the division."""
    return f"{n:,}"


def report(root: Path) -> tuple[int, list[str]]:
    out: list[str] = []
    grant = banks.read(root)

    missing = [name for name, found in (
        ("the second class's bank count", grant.banks),
        ("its retention floor", grant.retention_floor_us),
        ("the sequencer's cadence", grant.banks_per_refresh_phase),
        ("the clock frequency", grant.clock_hz),
        ("the second-class region", grant.region_bytes),
    ) if found is None]
    if missing:
        out.append(f"FAIL: {banks.CONFIG} no longer declares " + ", ".join(missing))
        return 1, out
    if not grant.candidates:
        out.append(f"FAIL: {banks.DOCUMENT} declares no candidate set this tool reads")
        return 1, out

    out.append(f"=== second-class bank count, over {len(grant.candidates)} candidates ===")
    out.append("")
    out.append(f"{'banks':>7}  {'bank bytes':>12}  {'refresh phases':>15}  "
               f"{'sweep cycles':>16}  {'deadline':>16}  {'fits':>5}  "
               f"{'discharge dwell':>16}  {'divides':>7}  admitted")

    findings: list[str] = []
    cleared = 0
    for candidate in grant.candidates:
        row = banks.score(grant, candidate)
        if row is None:
            findings.append(f"{candidate} banks could not be scored from the composition")
            continue
        fits, divides = row.meets_deadline, row.divides_region
        if fits and divides:
            cleared += 1
        marker = " <-- declared" if candidate == grant.banks else ""
        out.append(
            f"{row.banks:>7}  {row.bank_bytes:>12,}  {row.refresh_phases:>15,}  "
            f"{_cycles(row.refresh_sweep_cycles):>16}  "
            f"{_cycles(row.refresh_deadline_cycles):>16}  {fits!s:>5}  "
            f"{_cycles(row.discharge_dwell_cycles):>16}  {divides!s:>7}  "
            f"{'n/a':>8}{marker}")

    out.append("")
    out.append("--- columns no candidate carries a value in ---")
    out.extend(f"  {column:<22} pending on {', '.join(symbols)}"
               for column, symbols in banks.PENDING_COLUMNS)

    out.append("")
    out.append("--- residuals ---")
    if grant.pending:
        out.append(f"  {len(grant.pending)} pending coefficient(s): "
                   + ", ".join(grant.pending))
    if grant.stated:
        out.append(f"  {len(grant.stated)} stated coefficient(s): "
                   + ", ".join(grant.stated))
    out.append(f"  the composition's own qualification flag is {grant.qualified}")

    out.append("")
    if findings:
        out.append(f"FAIL: {len(findings)} candidate(s) the composition cannot score")
        out.extend(f"       {f}" for f in findings)
        return 1, out
    out.append(f"ok: {cleared} of {len(grant.candidates)} candidates clear the shape "
               f"constraints the composition fixes, and none is admitted: the droop "
               f"envelope is the hard constraint and both of its coefficients are "
               f"pending (R-15-247p, R-15-247g).")
    return 0, out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score candidate second-class bank counts against the composition.")
    parser.parse_args(argv)

    code, out = report(find_root())
    print("\n".join(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
