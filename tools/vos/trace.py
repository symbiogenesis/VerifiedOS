"""The differential rig: two executors' traces, normalized and adjudicated.

The rig's second executor is the M0.4 oracle (`cheri_riscv_sim_RV64`, upstream
sail-cheri-riscv at the pinned commit) for as long as the two models share a capability
format, which is until the 64+1-bit re-parameterization: an oracle is a reference only
where it implements the same machine, and upstream implements ISAv9's 128-bit encoding
with a hybrid mode and a default data capability. The rig outlives it. Its standing
second executor is the CHERI-QEMU fork of M2, a second implementation of the *frozen*
profile from an independent code lineage, and its corpus is M0.12's purecap programs;
what is between the two is a period in which the rig runs and its prefix is read as a
fact about how far two different machines happen to agree.

The two executors print traces in different dialects: the oracle is the old Sail C
backend and the curated model is the new C++ one. Normalizing turns either dialect into
one record stream, so that a divergence is a difference in *behaviour* rather than in
formatting.

The record set is the intersection of what the two print today, which is narrower than
the capability-widened commit trace M0.12 versions:

    I <pc> <insn>            an instruction retired
    X <reg> <value>          a general-purpose register write
    R <addr> <value>         a data read

Three things are deliberately outside it, each because one executor cannot supply it
rather than because it does not matter:

  * The **capability half of a register write.** The oracle prints the whole capability
    (tag, seal, permissions, object type, base, length); the curated model's
    `xreg_full_write_callback` carries the address alone, which `core/regs.sail` books
    as M0.12's to widen. The address is what both agree on today, so the address is what
    is compared.
  * The **write side of the memory trace.** The curated model prints `mem[W,..]` and the
    oracle prints no store line at all under `-v`, so there is nothing to compare a
    store against.
  * **CSR accesses**, which the two print in unrelated shapes, and whose banks differ
    anyway: the curated bank is the frozen profile's (isa-profile.md §5).

Instruction fetches (`mem[X,..]`) are dropped rather than compared: both print them in
16-bit granules, so they carry nothing the retire record does not.

The **agreeing prefix** is the figure to read, not the verdict. Over `riscv-tests` the
two machines part company inside the test prologue, and the ground is the corpus rather
than either model: every program there addresses memory with an integer base register,
which a purecap machine reads as an untagged capability and faults on, so the prefix
ends at the prologue's first load. A corpus both can execute in lockstep is what M0.12
versions, over the two executors the profile actually has.
"""

import re
from dataclasses import dataclass

# `[7]: 0x0000000080000054 (0x00000113) addi x2, x0, 0x0`         (curated)
# `[7] [M]: 0x0000000080000054 (0x00000113) addi sp, zero, 0x0`   (oracle)
#
# The disassembly is not part of the record: the two print different register naming
# conventions for the same instruction, and the raw encoding beside it is the invariant.
RETIRE_RE = re.compile(r"^\[\d+\](?: \[\w+\])?: 0x([0-9A-Fa-f]+) \(0x([0-9A-Fa-f]+)\)")

# `x1 <- 0x0000000000000000`                                      (curated)
# `x1 <-  t:0 s:0 perms:... type:... address:0x... base:... ...`  (oracle)
XWRITE_RE = {
    "curated": re.compile(r"^x(\d+) <- 0x([0-9A-Fa-f]+)\s*$"),
    "oracle": re.compile(r"^x(\d+) <-\s+t:\d+ .*\baddress:0x([0-9A-Fa-f]+)\b"),
}

# `mem[R,0x0000000080002000] -> 0x00AA00AA`   (both)
MEMREAD_RE = re.compile(r"^mem\[R,0x([0-9A-Fa-f]+)\] -> 0x([0-9A-Fa-f]+)\s*$")

DIALECTS = tuple(XWRITE_RE)


def normalize(lines, dialect: str) -> list[str]:
    xwrite = XWRITE_RE[dialect]
    records = []
    for line in lines:
        line = line.rstrip("\n")
        m = RETIRE_RE.match(line)
        if m:
            records.append("I %016X %08X" % (int(m.group(1), 16), int(m.group(2), 16)))
            continue
        m = xwrite.match(line)
        if m:
            records.append("X %2d %016X" % (int(m.group(1)), int(m.group(2), 16)))
            continue
        m = MEMREAD_RE.match(line)
        if m:
            records.append("R %016X %s" % (int(m.group(1), 16), m.group(2).upper()))
    return records


def _first_retire_pc(records: list[str]) -> int | None:
    for record in records:
        if record.startswith("I "):
            return int(record.split()[1], 16)
    return None


def _align(records: list[str], first_pc: int) -> list[str]:
    """Drop the records before the executor reaches `first_pc`.

    The two executors do not start at the same instruction: the oracle enters through a
    reset-vector ROM at 0x1000 that this platform does not have, so the streams are
    aligned on the first program counter the curated model retires rather than on the
    step number, which counts different things on each side.
    """
    for i, record in enumerate(records):
        if record.startswith("I ") and int(record.split()[1], 16) == first_pc:
            return records[i:]
    return []


@dataclass
class Verdict:
    prefix: int = 0
    compared: int = 0
    divergence: tuple[str, str] | None = None
    error: str | None = None
    agreed: list[str] | None = None       # the records just before a divergence

    @property
    def ok(self) -> bool:
        return self.error is None and self.divergence is None

    def line(self) -> str:
        if self.error:
            return self.error
        if self.divergence:
            return f"prefix {self.prefix} of {self.compared} compared"
        return f"agreed over {self.compared} records"


def adjudicate(curated: list[str], oracle: list[str], context: int = 4) -> Verdict:
    """Align the two streams and walk them until they disagree.

    The Sail model is the reference on every divergence, so the report names what each
    side produced rather than declaring one right.
    """
    start = _first_retire_pc(curated)
    if start is None:
        return Verdict(error="no retire records in the curated trace")
    aligned = _align(oracle, start)
    if not aligned:
        return Verdict(error="the oracle never reaches the curated model's first PC "
                             "0x%016X" % start)

    compared = min(len(curated), len(aligned))
    for i in range(compared):
        if curated[i] != aligned[i]:
            return Verdict(prefix=i, compared=compared,
                           divergence=(curated[i], aligned[i]),
                           agreed=curated[max(0, i - context):i])
    # One stream running out is not a divergence: the two machines halt on different
    # conditions, and a shorter range that agrees to its end is what the corpus is
    # asking about until M0.12 fixes the stopping point too.
    return Verdict(prefix=compared, compared=compared)
