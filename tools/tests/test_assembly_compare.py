# SPDX-License-Identifier: Apache-2.0
"""Positive and refusal controls for the M1.2b byte comparison predicate."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tests.harness import Case, ensure
from vos.assembly_compare import compare
from vos.cli import assembly_compare as cli

_PROGRAM = b""".text
.globl example
# Compartment 42
example:
    addi x5, x10, 8
    ld x6, 0(x5)
    add x10, x6, x11
    sd x10, 8(x5)
    beq x10, x0, finish
    call other@plt
finish:
    ret
.data
pointer:
    .quad example
message:
    .asciz "# Compartment 42"
"""


def _positive_identity() -> None:
    for original in (_PROGRAM, _PROGRAM.replace(b"\n", b"\r\n")):
        result = compare(original, original)
        ensure(result.verdict == "equal" and result.exit_code == 0, "identity must pass")
        ensure(result.left.sha256 == hashlib.sha256(original).hexdigest(),
               "hashes must bind original bytes")
        ensure(result.left.byte_count == len(original), "byte counts must be measured")
        ensure(result.left.annotations == 1 and result.left.instruction_witnesses == 3,
               "annotation and finite witness counts must be computed")
    for suffix in (b"", b"\n", b"\r\n"):
        original = b".text\nret\n\t# Compartment 42 \t" + suffix
        changed = original.replace(b"42", b"000001")
        result = compare(original, changed)
        ensure(result.verdict == "equal", "only the full annotation's digits may change")
        ensure(result.left.sha256 != result.right.sha256, "original hashes remain different")


def _semantic_changes_refused() -> None:
    replacements = (
        (b"x5", b"x7"), (b"x10", b"x11"), (b"x0", b"x1"),
        (b"x10, 8", b"x10, 9"), (b"ld x6", b"lw x6"),
        (b"sd x10", b"sw x10"), (b"0(x5)", b"8(x5)"),
        (b", finish", b", example"), (b"other@plt", b"wrong@plt"),
        (b"finish:", b"wrong:"), (b".quad example", b".quad example+8"),
        (b".data", b".rodata"), (b".globl", b".weak"),
        (b'"# Compartment 42"', b'"# Compartment 36"'),
        (b"# Compartment 42\n", b"# Compartment 42 extra\n"),
        (b"# Compartment 42\n", b"# Compartment -42\n"),
        (b"# Compartment 42\n", b"# Compartment 42\n# Compartment 43\n"),
        (b"# Compartment 42\n", b""),
        (b"# Compartment 42\nexample:", b"example:\n# Compartment 42"),
        (b"    ld x6, 0(x5)\n    add x10, x6, x11\n",
         b"    add x10, x6, x11\n    ld x6, 0(x5)\n"),
        (b"    ret", b"\tret"), (b"\n", b"\r\n"),
    )
    for before, after in replacements:
        candidate = _PROGRAM.replace(before, after)
        result = compare(_PROGRAM, candidate)
        ensure(result.verdict == "different" and result.exit_code == 1,
               f"changed bytes must fail: {before!r} -> {after!r}: {result}")
        ensure(result.first_difference is not None and result.left_line is not None,
               "a difference needs a byte and source line")
    comment = _PROGRAM + b"# other metadata 42\n"
    ensure(compare(comment, comment.replace(b"metadata 42", b"metadata 36")).exit_code == 1,
           "other comments must remain exact")


def _no_vacuous_equality() -> None:
    for data in (b"", b"# Compartment 42\n", b".text\n# Compartment 42\n",
                 b".data\nret\n", b'.text\n.asciz "ret"\n',
                 b"ret\n", b".text\nret x1\n", b".text\nmv x32, x10\n",
                 b".text\naddi x1,x2,2048\n", b".text\naddi x1,x2,-2049\n",
                 b".text\n.section .data\nret\n"):
        result = compare(data, data)
        ensure(result.verdict == "unsupported" and result.exit_code == 2,
               f"ineligible equal inputs must refuse: {data!r}")
        ensure(result.left.annotations is None, "ineligible counts must not pretend to be zero")
    for data in (b".text\naddi x1,x2,-2048\n", b".section .text\naddi x1,x2,+2047\n",
                 b".text\nf: mv x31,x0\n", b".text; ret # instruction witness\n"):
        ensure(compare(data, data).verdict == "equal", "valid witness boundary must pass")
    for digits, verdict in ((b"0" * 5000, "equal"), (b"9" * 5000, "unsupported")):
        data = b".text\naddi x1,x2," + digits + b"\n"
        ensure(compare(data, data).verdict == verdict, "long decimal input must not crash")


def _unsupported_syntax() -> None:
    inputs = (
        b'.data\n.ascii "start\n# Compartment 42\nend"\n',
        b"/*\n# Compartment 42\n*/\n", b".if 0\nret\n.endif\n",
        b".macro m\nret\n.endm\n", b".rept 0\nret\n.endr\n",
        b".text; .ifdef absent\nret\n.endif\n", b'.include "external.s"\n',
        b'.incbin "external.bin"\n', b".pushsection .text\nret\n.popsection\n",
        b".previous\n", b".irp x,0\n.endr\n", b".altmacro\n",
        b".text\\\n", b"\x00", b"\x7f", b"\xff", b"\r",
    )
    for suffix in inputs:
        original = _PROGRAM + suffix
        candidate = original.replace(b"# Compartment 42", b"# Compartment 36")
        result = compare(original, candidate)
        ensure(result.verdict == "unsupported", f"unsafe lexical input must refuse: {suffix!r}")
    # Markers inside an ordinary one-line string or a line comment are harmless.
    for suffix in (b'.asciz "/* # Compartment 42 */"\n',
                   b'.asciz "escaped \\" quote; # Compartment 42"\n',
                   b"# /* commentary only\n"):
        data = _PROGRAM + suffix
        ensure(compare(data, data).exit_code == 0, "quoted/comment markers must stay opaque")


def _difference_positions() -> None:
    original = b".text\n# Compartment 42\nret\n"
    changed = b".text\n# Compartment 1\nret\n.data\n"
    result = compare(original, changed)
    ensure(result.verdict == "different" and result.left_line == 4 and result.right_line == 4,
           "length mismatch after normalization must identify the source end")
    ensure(compare(original, b"").verdict == "unsupported", "a missing side is not a diff")


def _generated_byte_changes() -> None:
    annotation = _PROGRAM.index(b"# Compartment 42\n") + len(b"# Compartment ")
    allowed = {annotation, annotation + 1}
    for offset, byte in enumerate(_PROGRAM):
        candidate = _PROGRAM[:offset] + bytes([byte ^ 1]) + _PROGRAM[offset + 1:]
        result = compare(_PROGRAM, candidate)
        ensure((result.verdict == "equal") == (offset in allowed),
               f"single-byte mutation at {offset} escaped the metadata boundary: {result}")


def _cli_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-assembly-compare-") as temporary:
        root = Path(temporary)
        left, right = root / "left.s", root / "right.s"
        left.write_bytes(_PROGRAM)
        right.write_bytes(_PROGRAM.replace(b"# Compartment 42\n", b"# Compartment 36\n"))
        outputs: list[str] = []
        for _ in range(2):
            output = StringIO()
            with redirect_stdout(output):
                code = cli.main([str(left), str(right), "--json"])
            payload = json.loads(output.getvalue())
            ensure(code == 0 and payload["verdict"] == "equal", "CLI positive pair")
            ensure(payload["milestone_acceptance"] == "open", "pair equality is no campaign")
            ensure(all(len(digest) == 64 for digest in payload["sources_sha256"].values()),
                   "tool and contract identities must be present")
            ensure(payload["left"]["sha256"] == hashlib.sha256(left.read_bytes()).hexdigest(),
                   "file evidence must hash actual source bytes")
            outputs.append(output.getvalue())
        ensure(outputs[0] == outputs[1], "pair evidence must be deterministic")
        for data, expected in ((_PROGRAM.replace(b"x5", b"x7"), 1), (b"", 2)):
            right.write_bytes(data)
            with redirect_stdout(StringIO()):
                ensure(cli.main([str(left), str(right)]) == expected, "CLI verdict exit code")
        for flags in ([], ["--json"]):
            with redirect_stdout(StringIO()):
                ensure(cli.main([str(left), str(root / "absent.s"), *flags]) == 2,
                       "unreadable file must refuse without traceback")


def cases() -> list[Case]:
    return [Case("positive-identity", _positive_identity),
            Case("semantic-changes-refused", _semantic_changes_refused),
            Case("no-vacuous-equality", _no_vacuous_equality),
            Case("unsupported-syntax", _unsupported_syntax),
            Case("difference-positions", _difference_positions),
            Case("generated-byte-changes", _generated_byte_changes),
            Case("cli-evidence", _cli_evidence)]
