# SPDX-License-Identifier: Apache-2.0
"""The differential rig: executors' traces, normalized and adjudicated.

Two dialects, and they answer different questions.

The **commit trace** is the schema of M0.12, versioned in
[docs/differential-corpus.md](../../docs/differential-corpus.md) and emitted by
the curated model under `--trace-commit`. It is capability-widened: a register
write carries the tag beside the 64 data bits, a memory access carries the tag
of the access, and the four capability registers outside the merged file get
records of their own. It is what every executor of the frozen profile emits and
what the rig compares, so it is the dialect the corpus is versioned against.

The **oracle dialect** is the M0.4 oracle's `-v` output, and it is not a
reference for the frozen profile: upstream implements ISAv9's 128-bit encoding
with a hybrid mode and a default data capability, where the curated model
carries the 64+1-bit purecap dialect (M0.6f), so the two are different machines
and the agreeing prefix is read as a fact about how far they happen to agree.
The rig outlives it. Its standing second executor is the CHERI-QEMU fork of M2,
a second implementation of the *frozen* profile from an independent code
lineage.

Against one executor the rig still has a question to ask, and the corpus is what
lets it: a member's normalized record stream has a **digest**, the manifest
carries it, and a model change that alters what a program does changes it. That
is the same instrument §10 names for the composed images, where instruction
lockstep is too slow and a boot is compared by digest.
"""

import hashlib
import re
from dataclasses import dataclass

# --- the commit trace ------------------------------------------------------
#
# One record per retired instruction and one per effect under it, the effects
# following the instruction that caused them. Every field is fixed-radix so a
# record is comparable as a string:
#
#   I <order> <pc> <insn>                  an instruction retired
#   X <reg> <tag> <value>                  a register write, tag included
#   S <scr> <tag> <value>                  a capability register outside the file
#   C <csr> <value>                        a CSR write
#   R <addr> <width> <tag> <value>         a data read
#   W <addr> <width> <tag> <value>         a data write
#   T <interrupt> <cause>                  a trap
#
# The emitter is c_emulator/riscv_callbacks_commit.cpp; the schema and what each
# field means is docs/differential-corpus.md.
COMMIT_RE = re.compile(r"^(?:I \d+ [0-9A-F]{16} [0-9A-F]{8}"
                       r"|X \d+ [01] [0-9A-F]{16}"
                       r"|S \d+ [01] [0-9A-F]{16}"
                       r"|C [0-9A-F]{3} [0-9A-F]{16}"
                       r"|[RW] [0-9A-F]+ \d+ [01] [0-9A-F]+"
                       r"|T [01] \d+)$")

# The order field is the one part of a record that is not a property of the
# machine's state: it counts retires from the start of the run, so two executors
# that enter through different reset vectors disagree on it while agreeing on
# everything else. It is kept in the emitted record, where it is what makes the
# stream readable, and dropped from the compared one.
ORDER_RE = re.compile(r"^I \d+ ")


def normalize_commit(lines: list[str]) -> list[str]:
    """The records in `lines`, with anything else dropped.

    Anything else is real: the emulator prints its HTIF address, its entry
    point, and whatever other trace flags were passed on the same stream. A
    record is recognized by its shape rather than by its position.
    """
    records: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n").rstrip()
        if COMMIT_RE.match(line):
            records.append(ORDER_RE.sub("I ", line))
    return records


def digest(records: list[str]) -> str:
    """A stream's fingerprint, short enough to sit in a manifest row.

    Sixteen hex characters of SHA-256 over the records, newline-separated. The
    truncation is a readability choice and not a security one: nothing here
    defends against a chosen collision, and what the digest catches is a model
    change nobody meant to make.
    """
    blob = "\n".join(records).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# --- the M0.4 oracle's dialect ---------------------------------------------
#
# The two executors print in different dialects: the oracle is the old Sail C
# backend and the curated model is the new C++ one. Normalizing turns either
# into one record stream, so that a divergence is a difference in *behaviour*
# rather than in formatting. The record set is the intersection of what the two
# print, which is narrower than the commit trace above.

# `[7]: 0x0000000080000054 (0x00000113) addi x2, x0, 0x0`         (curated)
# `[7] [M]: 0x0000000080000054 (0x00000113) addi sp, zero, 0x0`   (oracle)
#
# The disassembly is not part of the record: the two print different register
# naming conventions for the same instruction, and the raw encoding beside it is
# the invariant.
RETIRE_RE = re.compile(r"^\[\d+\](?: \[\w+\])?: 0x([0-9A-Fa-f]+) \(0x([0-9A-Fa-f]+)\)")

# `x1 <- t:0 0x0000000000000000`                                  (curated)
# `x1 <-  t:0 s:0 perms:... type:... address:0x... base:... ...`  (oracle)
XWRITE_RE = {
    "curated": re.compile(r"^x(\d+) <- t:\d+ 0x([0-9A-Fa-f]+)\s*$"),
    "oracle": re.compile(r"^x(\d+) <-\s+t:\d+ .*\baddress:0x([0-9A-Fa-f]+)\b"),
}

# `mem[R,0x0000000080002000] -> 0x00AA00AA`         (oracle)
# `mem[R,0x080002000] -> t:0 0x00AA00AA`            (curated)
MEMREAD_RE = re.compile(r"^mem\[R,0x([0-9A-Fa-f]+)\] -> (?:t:\d+ )?0x([0-9A-Fa-f]+)\s*$")

DIALECTS = tuple(XWRITE_RE)


def normalize(lines: list[str], dialect: str) -> list[str]:
    xwrite = XWRITE_RE[dialect]
    records: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        m = RETIRE_RE.match(line)
        if m:
            records.append(f"I {int(m.group(1), 16):016X} {int(m.group(2), 16):08X}")
            continue
        m = xwrite.match(line)
        if m:
            records.append(f"X {int(m.group(1)):2d} {int(m.group(2), 16):016X}")
            continue
        m = MEMREAD_RE.match(line)
        if m:
            records.append(f"R {int(m.group(1), 16):016X} {m.group(2).upper()}")
    return records


def _first_retire_pc(records: list[str]) -> int | None:
    for record in records:
        if record.startswith("I "):
            return int(record.split()[1], 16)
    return None


def _align(records: list[str], first_pc: int) -> list[str]:
    """Drop the records before the executor reaches `first_pc`.

    The two executors do not start at the same instruction: the oracle enters
    through a reset-vector ROM at 0x1000 that this platform does not have, so
    the streams are aligned on the first program counter the curated model
    retires rather than on the step number, which counts different things on
    each side.
    """
    for i, record in enumerate(records):
        if record.startswith("I ") and int(record.split()[1], 16) == first_pc:
            return records[i:]
    return []


@dataclass(frozen=True)
class Verdict:
    """The result of one adjudication, and frozen because callers reason from it.

    A reader that has ruled out `ok` and `error` is entitled to `divergence`, which
    is an invariant spread across this class and its caller rather than something
    either can see locally. Freezing is what keeps that entitlement true: on a
    mutable record it holds only until something assigns a field.
    """

    prefix: int = 0
    compared: int = 0
    divergence: tuple[str, str] | None = None
    error: str | None = None
    agreed: tuple[str, ...] = ()          # the records just before a divergence

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

    The Sail model is the reference on every divergence, so the report names
    what each side produced rather than declaring one right.
    """
    start = _first_retire_pc(curated)
    if start is None:
        return Verdict(error="no retire records in the curated trace")
    aligned = _align(oracle, start)
    if not aligned:
        return Verdict(error="the oracle never reaches the curated model's first PC "
                             f"0x{start:016X}")

    compared = min(len(curated), len(aligned))
    for i in range(compared):
        if curated[i] != aligned[i]:
            return Verdict(prefix=i, compared=compared,
                           divergence=(curated[i], aligned[i]),
                           agreed=tuple(curated[max(0, i - context):i]))
    # One stream running out is not a divergence: the two machines halt on
    # different conditions, and a shorter range that agrees to its end is what
    # the corpus is asking about.
    return Verdict(prefix=compared, compared=compared)
