# SPDX-License-Identifier: Apache-2.0
"""Normalize and adjudicate commit traces (`--trace-commit`) and verbose oracle traces (`-v`).

Commit-trace schema and corpus digests are defined in
[docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md).
"""

import hashlib
import re
from dataclasses import dataclass

# Commit-trace record formats emitted by `model/c_emulator/riscv_callbacks_commit.cpp`:
#   I <order> <pc> <insn>            retired instruction
#   X <reg> <tag> <value>            merged register write
#   S <scr> <tag> <value>            special capability register write
#   C <csr> <value>                  CSR write
#   R <addr> <width> <tag> <value>   memory read
#   W <addr> <width> <tag> <value>   memory write
#   T <interrupt> <cause>            trap
COMMIT_RE = re.compile(r"^(?:I \d+ [0-9A-F]{16} [0-9A-F]{8}"
                       r"|X \d+ [01] [0-9A-F]{16}"
                       r"|S \d+ [01] [0-9A-F]{16}"
                       r"|C [0-9A-F]{3} [0-9A-F]{16}"
                       r"|[RW] [0-9A-F]+ \d+ [01] [0-9A-F]+"
                       r"|T [01] \d+)$")

# Strip the retire sequence number (`I <order> `) before comparing or hashing traces.
ORDER_RE = re.compile(r"^I \d+ ")


def normalize_commit(lines: list[str]) -> list[str]:
    """Filter `lines` to valid commit-trace records with retire sequence numbers stripped."""
    records: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n").rstrip()
        if COMMIT_RE.match(line):
            records.append(ORDER_RE.sub("I ", line))
    return records


def digest(records: list[str]) -> str:
    """Return the first 16 hex digits of the SHA-256 over newline-joined `records`."""
    blob = "\n".join(records).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# Verbose (`-v`) trace normalization between the curated C++ emulator and the upstream C oracle.
RETIRE_RE = re.compile(r"^\[\d+\](?: \[\w+\])?: 0x([0-9A-Fa-f]+) \(0x([0-9A-Fa-f]+)\)")

XWRITE_RE = {
    "curated": re.compile(r"^x(\d+) <- t:\d+ 0x([0-9A-Fa-f]+)\s*$"),
    "oracle": re.compile(r"^x(\d+) <-\s+t:\d+ .*\baddress:0x([0-9A-Fa-f]+)\b"),
}

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
    """Drop records before the first instruction retired at `first_pc`."""
    for i, record in enumerate(records):
        if record.startswith("I ") and int(record.split()[1], 16) == first_pc:
            return records[i:]
    return []


@dataclass(frozen=True)
class Verdict:
    """Adjudication result comparing two normalized trace streams."""

    prefix: int = 0
    compared: int = 0
    divergence: tuple[str, str] | None = None
    error: str | None = None
    agreed: tuple[str, ...] = ()          # records immediately preceding a divergence

    @property
    def ok(self) -> bool:
        return self.error is None and self.divergence is None

    def line(self) -> str:
        if bool(self.error):
            return self.error
        if self.divergence:
            return f"prefix {self.prefix} of {self.compared} compared"
        return f"agreed over {self.compared} records"


def adjudicate(curated: list[str], oracle: list[str], context: int = 4) -> Verdict:
    """Align `oracle` to `curated`'s first retired PC and compare records up to the shorter stream."""
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
    return Verdict(prefix=compared, compared=compared)
