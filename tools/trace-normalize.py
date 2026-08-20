#!/usr/bin/env python3
"""Normalize an instruction trace to the records the two executors can both emit.

M0.6e (e5). The transplant's differential reference is the M0.4 oracle
(`cheri_riscv_sim_RV64`, upstream sail-cheri-riscv at the pinned commit), and the
two executors print traces in different dialects: the oracle is the old Sail C
backend and the curated model is the new C++ one. This turns either dialect into
one record stream so that a divergence is a difference in *behaviour* rather than
in formatting.

The record set is the intersection of what the two print today, which is
narrower than the capability-widened commit trace M0.12 versions:

    I <pc> <insn>            an instruction retired
    X <reg> <value>          a general-purpose register write
    R <addr> <value>         a data read

Three things are deliberately outside it, each because one executor cannot
supply it rather than because it does not matter:

  * The **capability half of a register write.** The oracle prints the whole
    capability (tag, seal, permissions, object type, base, length); the curated
    model's `xreg_full_write_callback` carries the address alone, which
    `core/regs.sail` books as M0.12's to widen. The address is what both agree
    on today, so the address is what is compared.
  * The **write side of the memory trace.** The curated model prints `mem[W,..]`
    and the oracle prints no store line at all under `-v`, so there is nothing
    to compare a store against.
  * **CSR accesses**, which the two print in unrelated shapes, and whose banks
    differ anyway: the curated bank is the frozen profile's (isa-profile.md §5).

Instruction fetches (`mem[X,..]`) are dropped rather than compared: both print
them in 16-bit granules, so they carry nothing the retire record does not.
"""

import argparse
import re
import sys

# `[7]: 0x0000000080000054 (0x00000113) addi x2, x0, 0x0`   (curated)
# `[7] [M]: 0x0000000080000054 (0x00000113) addi sp, zero, 0x0`  (oracle)
#
# The disassembly is not part of the record: the two print different register
# naming conventions for the same instruction, and the raw encoding beside it is
# the invariant.
RETIRE = re.compile(r"^\[\d+\](?: \[\w+\])?: 0x([0-9A-Fa-f]+) \(0x([0-9A-Fa-f]+)\)")

# `x1 <- 0x0000000000000000`                                      (curated)
# `x1 <-  t:0 s:0 perms:... type:... address:0x... base:... ...`  (oracle)
XWRITE_CURATED = re.compile(r"^x(\d+) <- 0x([0-9A-Fa-f]+)\s*$")
XWRITE_ORACLE = re.compile(r"^x(\d+) <-\s+t:\d+ .*\baddress:0x([0-9A-Fa-f]+)\b")

# `mem[R,0x0000000080002000] -> 0x00AA00AA`   (both)
MEMREAD = re.compile(r"^mem\[R,0x([0-9A-Fa-f]+)\] -> 0x([0-9A-Fa-f]+)\s*$")


def normalize(lines, dialect):
    xwrite = XWRITE_ORACLE if dialect == "oracle" else XWRITE_CURATED
    for line in lines:
        line = line.rstrip("\n")
        m = RETIRE.match(line)
        if m:
            yield "I %016X %08X" % (int(m.group(1), 16), int(m.group(2), 16))
            continue
        m = xwrite.match(line)
        if m:
            yield "X %2d %016X" % (int(m.group(1)), int(m.group(2), 16))
            continue
        m = MEMREAD.match(line)
        if m:
            yield "R %016X %s" % (int(m.group(1), 16), m.group(2).upper())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dialect", choices=("curated", "oracle"), required=True)
    ap.add_argument("input", nargs="?", type=argparse.FileType("r", errors="replace"),
                    default=sys.stdin)
    args = ap.parse_args()
    for record in normalize(args.input, args.dialect):
        print(record)


if __name__ == "__main__":
    main()
