# SPDX-License-Identifier: Apache-2.0
"""Both trace dialects: recognition, normalization, alignment, adjudication.

`COMMIT_RE` is coupled byte-for-byte to the emulator's emitter and to the
schema docs/differential-corpus.md versions, and every recorded digest stands
on the normalization here: a record shape that silently stops matching drops
records from the stream and moves every digest at once. The fixture lines are
the ones the module's own docstrings carry.
"""

import hashlib
from typing import Final

from tests.harness import Case, ensure
from vos import trace

# One line per documented record shape, exactly as the emitter spells them.
_ACCEPTS: Final[tuple[str, ...]] = (
    "I 12 0000000080000054 00000113",
    "X 2 0 0000000000000000",
    "X 31 1 FFFFFFFFFFFFFFFF",
    "S 28 1 0000000080000000",
    "C 300 0000000000000042",
    "R 0000000080002000 8 1 00000000000000AA",
    "W 80002000 4 0 DEADBEEF",
    "T 0 2",
    "T 1 11",
)

# Near-misses, each one field away from a record: a widened or narrowed field
# must fall out of the stream loudly here rather than silently in a digest.
_REJECTS: Final[tuple[str, ...]] = (
    "I 12 0000000080000054 0000113",           # 7-digit instruction word
    "I 12 000000008000005 00000113",           # 15-digit pc
    "I 12 00000000800000aa 00000113",          # lowercase hex
    "I 12 0000000080000054 00000113 extra",    # trailing field
    "I 0000000080000054 00000113",             # the emitted form carries an order
    "X 2 2 0000000000000000",                  # tag past 0/1
    "C 30 0000000000000042",                   # 2-hex CSR address
    "C 0300 0000000000000042",                 # 4-hex CSR address
    "R 80002000 4 0",                          # missing value
    "T 2 0",                                   # interrupt flag past 0/1
    "i 12 0000000080000054 00000113",          # lowercase record tag
)

# A raw emitter stream: noise, then one of each record. What normalize_commit
# keeps of it is the record set with the order counter dropped.
_STREAM: Final[tuple[str, ...]] = (
    "htif tohost located at 0x80001000",
    "I 1 0000000080000000 00000113",
    "X 2 0 0000000000000000",
    "R 0000000080002000 8 1 00000000000000AA",
    "W 80002000 4 0 DEADBEEF",
    "C 300 0000000000000042",
    "S 28 1 FFFFFFFFFFFFFFFF",
    "T 0 2",
)
_RECORDS: Final[tuple[str, ...]] = (
    "I 0000000080000000 00000113",
    "X 2 0 0000000000000000",
    "R 0000000080002000 8 1 00000000000000AA",
    "W 80002000 4 0 DEADBEEF",
    "C 300 0000000000000042",
    "S 28 1 FFFFFFFFFFFFFFFF",
    "T 0 2",
)


def _commit_shapes() -> None:
    for line in _ACCEPTS:
        ensure(trace.COMMIT_RE.match(line) is not None,
               f"COMMIT_RE must accept the documented record {line!r}")


def _commit_near_misses() -> None:
    for line in _REJECTS:
        ensure(trace.COMMIT_RE.match(line) is None,
               f"COMMIT_RE must reject the near-miss {line!r}")


def _normalize_commit_stream() -> None:
    got = trace.normalize_commit([line + "\n" for line in _STREAM])
    ensure(got == list(_RECORDS),
           f"normalize_commit kept {got}, expected the record set with the "
           f"order counter stripped")
    # Trailing whitespace on a record line is the emitter's newline handling,
    # not a different record.
    ensure(trace.normalize_commit(["I 7 0000000080000000 00000113  \n"])
           == ["I 0000000080000000 00000113"],
           "a record with trailing whitespace must still be recognized")


def _normalize_unifies_dialects() -> None:
    pairs = (
        # retire: the disassembly and its register-naming convention are not
        # part of the record; the raw encoding beside the pc is the invariant
        ("[7]: 0x0000000080000054 (0x00000113) addi x2, x0, 0x0", "curated",
         "I 0000000080000054 00000113"),
        ("[7] [M]: 0x0000000080000054 (0x00000113) addi sp, zero, 0x0", "oracle",
         "I 0000000080000054 00000113"),
        # register write: the oracle prints a whole capability, the curated
        # model a tagged word; the address field is the shared record
        ("x1 <- t:0 0x0000000000000000", "curated", "X  1 0000000000000000"),
        ("x1 <-  t:0 s:0 perms:0x0 type:0x0 address:0x0000000000000000 "
         "base:0x0 length:0x0", "oracle", "X  1 0000000000000000"),
        ("x13 <- t:1 0x00000000000000FF", "curated", "X 13 00000000000000FF"),
        # data read, with and without the curated model's tag field
        ("mem[R,0x080002000] -> t:0 0x00AA00AA", "curated",
         "R 0000000080002000 00AA00AA"),
        ("mem[R,0x0000000080002000] -> 0x00AA00AA", "oracle",
         "R 0000000080002000 00AA00AA"),
    )
    for line, dialect, want in pairs:
        got = trace.normalize([line], dialect)
        ensure(got == [want], f"normalize({line!r}, {dialect!r}) gave {got}, "
                              f"expected [{want!r}]")


def _align_reset_vector() -> None:
    records = ["X  1 0000000000001004",
               "I 0000000000001000 00000297",
               "I 0000000080000000 00000113",
               "X  1 0000000000000005"]
    ensure(trace._align(records, 0x80000000) == records[2:],
           "_align must drop everything before the first matching retire pc")
    ensure(trace._align(records, 0xDEAD) == [],
           "_align must answer [] when the pc never appears")


def _adjudicate_ok() -> None:
    curated = ["I 0000000080000000 00000113", "X  2 0000000000000000",
               "I 0000000080000004 00000073"]
    oracle = ["I 0000000000001000 00000297", "X  5 0000000000001004", *curated]
    verdict = trace.adjudicate(curated, oracle)
    ensure(verdict.ok and verdict.compared == 3,
           f"an agreeing pair must be ok over 3 records, got {verdict}")
    ensure(verdict.line() == "agreed over 3 records",
           f"the ok wording moved: {verdict.line()!r}")


def _adjudicate_divergence() -> None:
    curated = ["I 0000000080000000 00000113", "X  2 0000000000000000",
               "I 0000000080000004 00000073"]
    oracle = [curated[0], "X  2 0000000000000001", curated[2]]
    verdict = trace.adjudicate(curated, oracle)
    ensure(not verdict.ok and verdict.error is None,
           "a mismatching record is a divergence, not an error")
    ensure(verdict.prefix == 1 and verdict.compared == 3,
           f"the divergence sits after a 1-record prefix, got {verdict}")
    ensure(verdict.divergence == (curated[1], oracle[1]),
           "the report names what each side produced, declaring neither right")
    ensure(verdict.agreed == (curated[0],),
           f"the agreed context must be the records just before, got {verdict.agreed}")


def _adjudicate_errors() -> None:
    verdict = trace.adjudicate(["X  1 0000000000000000"], ["I 0 0"])
    ensure(verdict.error == "no retire records in the curated trace",
           f"a retire-free curated trace is its own error, got {verdict.error!r}")
    verdict = trace.adjudicate(["I 0000000080000000 00000113"],
                               ["I 0000000000001000 00000297"])
    ensure(verdict.error is not None
           and verdict.error.startswith("the oracle never reaches"),
           f"an unreachable first pc is its own error, got {verdict.error!r}")


def _shorter_stream_not_divergence() -> None:
    # The two machines halt on different conditions: a shorter stream that
    # agrees to its end is what the corpus is asking about, not a divergence.
    curated = ["I 0000000080000000 00000113", "X  2 0000000000000000",
               "I 0000000080000004 00000073", "X  3 0000000000000001"]
    verdict = trace.adjudicate(curated, curated[:2])
    ensure(verdict.ok and verdict.compared == 2,
           f"a shorter agreeing stream must be ok over 2 records, got {verdict}")


def _digest() -> None:
    got = trace.digest(list(_RECORDS))
    ensure(len(got) == 16, "the digest is sixteen hex characters, for a manifest row")
    # Recorded from trace.digest over _RECORDS. The digest is coupled to the
    # normalization's exact spelling: a legitimate change to either is a
    # trace_schema version bump, and only then is this rerecorded.
    ensure(got == "5d248d5df9c3d467",
           f"the fixture stream digests to {got}, not the recorded value")
    ensure(got == hashlib.sha256("\n".join(_RECORDS).encode()).hexdigest()[:16],
           "the digest is truncated SHA-256 over newline-joined records")


def cases() -> list[Case]:
    return [
        Case("commit-shapes", _commit_shapes),
        Case("commit-near-misses", _commit_near_misses),
        Case("normalize-commit-stream", _normalize_commit_stream),
        Case("normalize-unifies-dialects", _normalize_unifies_dialects),
        Case("align-reset-vector", _align_reset_vector),
        Case("adjudicate-ok", _adjudicate_ok),
        Case("adjudicate-divergence", _adjudicate_divergence),
        Case("adjudicate-errors", _adjudicate_errors),
        Case("shorter-stream-not-divergence", _shorter_stream_not_divergence),
        Case("digest", _digest),
    ]
