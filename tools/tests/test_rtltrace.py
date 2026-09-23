# SPDX-License-Identifier: Apache-2.0
"""The RTL frame: its protocol, its projection onto the commit trace, and its verdicts.

Every case here decides on the host and needs no emulator and no RTL. **What these
fixtures establish is protocol handling and nothing about a core**: the golden
stream below is written in the commit trace's record grammar by hand, and the frames
are built by `rtltrace.encode` from retirements stated here, so a green run says the
adapter decodes what the contract says, refuses what it forbids, and reports what it
is seeded with. Whether the curated core writes such a frame, and agrees, is the
co-simulation gate's question and waits on the integrated RTL.

The instruction words are not decoded by anything in the adapter, which compares
them as strings; the few that are real encodings are named beside them only so a
reader can follow the fixture.
"""

import io
import re
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import Final

from tests.harness import TOOLS, Case, ensure
from vos import dialect, rtltrace, rvfi, trace
from vos.cli import testrig

# A golden run as the emulator writes it: orders in, one line of noise the
# normalizer drops, and the capability-register, CSR and trap records a frame
# carries only in part.
_GOLDEN: Final = [
    "tohost located at 0x0000000080001000",
    "I 0 0000000080000000 00100293",                 # addi x5, x0, 1
    "X 5 0 0000000000000001",
    "I 1 0000000080000004 FE12825B",                 # a capability derivation
    "X 9 1 C8000000FFFF0400",
    "I 2 0000000080000008 0094B023",                 # a capability store
    "W 0000000080000400 8 1 C8000000FFFF0400",
    "I 3 000000008000000C 00042303",                 # lw x6, 0(c8)
    "R 0000000080000400 4 0 FFFF0400",
    "X 6 0 FFFFFFFFFFFF0400",
    "I 4 0000000080000010 00A4A3AF",                 # an atomic: read, write, register
    "R 0000000080000408 8 0 0000000000000003",
    "W 0000000080000408 8 0 0000000000000007",
    "X 7 0 0000000000000003",
    "I 5 0000000080000014 34029473",                 # a CSR write that returns zero
    "C 340 0000000000000005",
    "X 8 0 0000000000000000",
    "I 6 0000000080000018 00050003",                 # a load that faults
    "C 341 0000000080000018",
    "C 342 000000000000001C",
    "C 343 0000000000000402",
    "S 29 1 C8000000FFFF0018",
    "T 0 28",
]

_TAGGED_CAP: Final = 0xC8000000FFFF0400


_BASE: Final = rvfi.Execution(wire=rtltrace.WIRE, integer_present=True,
                              memory_present=True)


def _retires() -> list[rtltrace.Retire]:
    """The same run as a harness following the contract writes it."""
    return [
        rtltrace.Retire(replace(_BASE, order=0, pc_rdata=0x80000000, pc_wdata=0x80000004,
                                insn=0x00100293, rd_addr=5, rd_wdata=1)),
        rtltrace.Retire(replace(_BASE, order=1, pc_rdata=0x80000004, pc_wdata=0x80000008,
                                insn=0xFE12825B, rd_addr=9, rd_wdata=_TAGGED_CAP,
                                rd_tag=True)),
        rtltrace.Retire(replace(_BASE, order=2, pc_rdata=0x80000008, pc_wdata=0x8000000C,
                                insn=0x0094B023, mem_addr=0x80000400, mem_wmask=0x1FF,
                                mem_wdata=_TAGGED_CAP)),
        # The port at the pin reports a load's result where the record carries the
        # bytes read; the projection keeps the access's own width either way.
        rtltrace.Retire(replace(_BASE, order=3, pc_rdata=0x8000000C, pc_wdata=0x80000010,
                                insn=0x00042303, mem_addr=0x80000400, mem_rmask=0xF,
                                mem_rdata=0xFFFFFFFFFFFF0400, rd_addr=6,
                                rd_wdata=0xFFFFFFFFFFFF0400)),
        rtltrace.Retire(replace(_BASE, order=4, pc_rdata=0x80000010, pc_wdata=0x80000014,
                                insn=0x00A4A3AF, mem_addr=0x80000408, mem_rmask=0xFF,
                                mem_wmask=0xFF, mem_rdata=3, mem_wdata=7, rd_addr=7,
                                rd_wdata=3)),
        rtltrace.Retire(replace(_BASE, order=5, pc_rdata=0x80000014, pc_wdata=0x80000018,
                                insn=0x34029473, rd_addr=8, rd_wdata=0)),
        rtltrace.Retire(replace(_BASE, order=6, pc_rdata=0x80000018, pc_wdata=0x00000000,
                                insn=0x00050003, trap=1), cause=28),
    ]


def _refused(text: str, kind: str) -> None:
    try:
        rtltrace.decode(text)
    except rtltrace.FrameError as exc:
        ensure(exc.kind == kind, f"expected a `{kind}` refusal, got `{exc.kind}`: {exc}")
        return
    raise AssertionError(f"a frame with a `{kind}` break must be refused, not decoded:\n"
                         f"{text}")


def _lines() -> list[str]:
    return rtltrace.encode(_retires()).splitlines()


def _frame(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _round_trip() -> None:
    retires = _retires()
    text = rtltrace.encode(retires)
    ensure(text.startswith(rtltrace.HEADER + "\n"), "a frame opens with its header")
    ensure(text.endswith(f"E {len(retires)}\n"), "and closes with its counted trailer")
    ensure(rtltrace.decode(text) == retires,
           "a decode of an encoded frame is the retirements again")
    lower = "".join(("P " + line[2:].lower() if line.startswith("P ") else line) + "\n"
                    for line in text.splitlines())
    ensure(lower != text and rtltrace.decode(lower) == retires,
           "lowercase hexadecimal decodes to the same retirements")


def _agrees_whole() -> None:
    result = rtltrace.compare(_GOLDEN, rtltrace.encode(_retires()))
    ensure(result.verdict.ok, f"the fixture run agrees, got {result.line()}")
    ensure(result.complete, f"and both streams are consumed whole, got {result.line()}")
    ensure(result.retired == 7 and result.reference == result.candidate == 17,
           f"seven retirements and seventeen compared records, got {result}")
    ensure((result.elided.scr, result.elided.csr, result.elided.traps) == (1, 4, 0),
           f"the S and C records are elided and counted and the T record is not, "
           f"got {result.elided}")


def _trap_cause_is_compared() -> None:
    wrong = _retires()
    wrong[6] = replace(wrong[6], cause=2)
    result = rtltrace.compare(_GOLDEN, rtltrace.encode(wrong))
    ensure(result.verdict.divergence == ("T 0 28", "T 0 2"),
           f"a wrong cause is a divergence at the T record, got {result.verdict}")
    silent = _retires()
    silent[6] = rtltrace.Retire(replace(silent[6].packet, trap=0))
    result = rtltrace.compare(_GOLDEN, rtltrace.encode(silent))
    ensure(not result.complete and result.verdict.divergence is None,
           f"a retirement that reports no trap loses the T record, got {result.line()}")


def _seeded_divergence_is_caught() -> None:
    """The defect S11 seeds first, now in the RTL's frame: a W form not sign-extended."""
    golden = [*_GOLDEN, "I 7 000000008000001C 0FF2829B", "X 5 0 FFFFFFFFFFFFFFF0"]
    retires = [*_retires(), rtltrace.Retire(rvfi.Execution(
        wire=rtltrace.WIRE, order=7, pc_rdata=0x8000001C, pc_wdata=0x80000020,
        insn=0x0FF2829B, rd_addr=5, rd_wdata=0x00000000FFFFFFF0))]
    result = rtltrace.compare(golden, rtltrace.encode(retires))
    ensure(result.verdict.divergence == ("X 5 0 FFFFFFFFFFFFFFF0", "X 5 0 00000000FFFFFFF0"),
           f"the missing sign extension is named at its record, got {result.verdict}")
    ensure(result.verdict.prefix == 18, f"after 18 agreed records, got {result.verdict}")
    ensure(not result.complete, "and a divergence is never green")


def _every_seed_is_reported() -> None:
    retires = _retires()
    golden, elided = rtltrace.view(_GOLDEN)
    for seed in rtltrace.SEEDS:
        sites = [at for at in range(len(retires))
                 if rtltrace.seed(retires, at, seed.name) is not None]
        ensure(bool(sites), f"the fixture carries a witness for seed `{seed.name}`")
        for at in sites:
            seeded = rtltrace.seed(retires, at, seed.name)
            if seeded is None or seeded == retires:
                raise AssertionError(f"seed `{seed.name}` at {at} changes the frame")
            decoded = rtltrace.decode(rtltrace.encode(seeded))
            result = rtltrace.compare_decoded(golden, decoded, elided)
            ensure(not result.complete,
                   f"seed `{seed.name}` at retirement {at} ({seed.what}) must be "
                   f"reported, got {result.line()}")


def _seeds_need_a_witness() -> None:
    retires = _retires()
    ensure(rtltrace.seed(retires, 2, "rd-value") is None,
           "a register seed has no witness at a store")
    ensure(rtltrace.seed(retires, 3, "access-tag") is None,
           "a tag seed has no witness at a four-byte access")
    ensure(rtltrace.seed(retires, 0, "cause") is None,
           "a cause seed has no witness where nothing trapped")
    try:
        rtltrace.seed(retires, 0, "no-such-seed")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown seed must be refused rather than read as silent")


def _incomplete_is_not_green() -> None:
    short = rtltrace.encode(_retires()[:-1])
    result = rtltrace.compare(_GOLDEN, short)
    ensure(result.verdict.ok and not result.complete,
           f"a candidate that stops early agrees over a prefix and is incomplete, "
           f"got {result.line()}")
    long = [*_retires(), rtltrace.Retire(rvfi.Execution(
        wire=rtltrace.WIRE, order=7, pc_rdata=0x8000001C, insn=0x00000013))]
    result = rtltrace.compare(_GOLDEN, rtltrace.encode(long))
    ensure(result.verdict.ok and not result.complete,
           f"a candidate that retires past the reference is incomplete, got {result.line()}")
    ahead = [rtltrace.Retire(rvfi.Execution(wire=rtltrace.WIRE, order=0, pc_rdata=0x1000,
                                            insn=0x00000013))]
    ahead += [replace(r, packet=replace(r.packet, order=r.packet.order + 1))
              for r in _retires()]
    result = rtltrace.compare(_GOLDEN, rtltrace.encode(ahead))
    ensure(result.verdict.ok and not result.complete,
           f"a candidate that retires before the reference's first pc is aligned past "
           f"it and is incomplete, not green, got {result.line()}")


def _protocol_refusals() -> None:
    good = _lines()
    p1 = good[1].split(" ")

    def with_field(name: str, token: str) -> str:
        index = [n for n, _ in rtltrace.FIELDS].index(name) + 1
        fields = list(p1)
        fields[index] = token
        return _frame([good[0], " ".join(fields), *good[2:-1], f"E {len(good) - 2}"])

    _refused("", "header")
    _refused(_frame(["vos-rtl-trace 1", *good[1:]]), "header")
    _refused(_frame([f"{rtltrace.FORMAT} 2", *good[1:]]), "version")
    _refused(rtltrace.encode(_retires())[:-1], "torn")
    _refused(rtltrace.encode(_retires())[:-40], "torn")
    _refused(rtltrace.encode(_retires()).replace("\n", "\r\n"), "carriage-return")
    _refused(_frame(good[:-1]), "partial")
    _refused(_frame(good[:3]), "partial")
    _refused(_frame([*good[:-1], "E 6"]), "trailer")
    _refused(_frame([*good[:-1], "E seven"]), "trailer")
    _refused(_frame([*good, "P 0"]), "after-trailer")
    _refused(_frame([good[0], "X 5 0 0000000000000001", *good[1:]]), "record")
    _refused(_frame([good[0], good[1] + " 00", *good[2:]]), "field-count")
    _refused(_frame([good[0], good[1][:-1], *good[2:]]), "field-width")
    _refused(with_field("insn", "0010029G"), "field-width")
    _refused(with_field("trap", "2"), "flag")
    _refused(with_field("rd_addr", "20"), "register")
    _refused(with_field("rd_addr", "00"), "rd-x0")
    _refused(with_field("cause", "000000000000001C"), "cause")
    _refused(with_field("mem_rmask", "05"), "mask")
    _refused(with_field("mem_rtag", "1"), "tag")
    lost = [good[0], good[1], *good[3:-1], f"E {len(good) - 3}"]
    _refused(_frame(lost), "order")
    repeated = [good[0], good[1], good[1], *good[2:-1], f"E {len(good) - 1}"]
    _refused(_frame(repeated), "order")


def _narrow_tag_is_refused() -> None:
    """R-15-203: only a whole granule carries a tag, and the frame keeps it so."""
    text = rtltrace.encode(_retires())
    lines = text.splitlines()
    index = [n for n, _ in rtltrace.FIELDS].index("mem_rtag") + 1
    fields = lines[4].split(" ")                     # the four-byte load
    ensure(fields[index] == "0", "the fixture's load carries no tag")
    fields[index] = "1"
    _refused(_frame([*lines[:4], " ".join(fields), *lines[5:]]), "tag")


def _packet_view_carries_only_what_it_is_told() -> None:
    commit = trace.normalize_commit(_GOLDEN)
    plain, elided = rvfi.packet_view(commit)
    ensure(not any(r.startswith("T ") for r in plain) and elided.traps == 1,
           "the standard packet's view elides the trap and counts it")
    carried, elided = rvfi.packet_view(commit, carried=rtltrace.CARRIED)
    ensure(carried[-1] == "T 0 28" and elided.traps == 0,
           "a view told the executor carries causes keeps the trap and does not count it")
    try:
        rvfi.packet_view(commit, carried=frozenset({"S"}))
    except ValueError:
        pass
    else:
        raise AssertionError("no executor view carries the S record, and asking is refused")


def _address_width_is_measured() -> None:
    golden, _ = rtltrace.view(_GOLDEN)
    ensure(rvfi.address_digits(golden) == 16, "the fixture writes sixteen-digit addresses")
    narrow = ["I 0000000080000000 00042303", "R 080000400 4 0 FFFF0400"]
    ensure(rvfi.address_digits(narrow) == 9, "and the width is read off the record")
    ensure(rvfi.address_digits(["I 0000000080000000 00100293"]) == rvfi.PHYSADDR_DIGITS,
           "a view with no memory record answers the default")


def _carry_round_trips() -> None:
    golden, elided = rtltrace.view(_GOLDEN)
    retires, refusals = rtltrace.carry(golden)
    ensure(not refusals, f"every fixture retirement fits a frame line, got {refusals}")
    decoded = rtltrace.decode(rtltrace.encode(retires))
    result = rtltrace.compare_decoded(golden, decoded, elided)
    ensure(result.complete, f"the golden run re-encoded agrees whole, got {result.line()}")


def _carry_names_what_no_line_holds() -> None:
    golden = [
        "I 0000000080000000 0001200F",               # a block write of 64 bytes
        "W 0000000080000400 64 0 " + "0" * 128,
        "I 0000000080000004 00000013",
        "X 5 0 0000000000000001",
        "X 6 0 0000000000000002",
        "I 0000000080000008 00000013",
        "R 0000000080000400 8 0 0000000000000001",
        "W 0000000080000440 8 0 0000000000000002",
    ]
    retires, refusals = rtltrace.carry(golden)
    got = [(r.at, r.reason) for r in refusals]
    ensure(got == [(0, "wide-access"), (1, "two-registers"), (2, "two-addresses")],
           f"each shape no frame line holds is named at its retirement, got {got}")
    ensure(set(rtltrace.REASONS) >= {r.reason for r in refusals},
           "every refusal names a declared reason")
    decoded = rtltrace.decode(rtltrace.encode(retires))
    result = rtltrace.compare_decoded(golden, decoded, rvfi.Elided())
    ensure(not result.complete,
           "a refused retirement is still written, so the comparison diverges at it "
           "rather than agreeing over a stream that skipped it")


def _adapt_command() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        scratch = Path(td)
        reference = scratch / "golden.trace"
        reference.write_text("\n".join(_GOLDEN) + "\n", encoding="utf-8", newline="")
        cases = {
            "whole": (rtltrace.encode(_retires()), 0, "TOTAL"),
            "torn": (rtltrace.encode(_retires())[:-5], 1, "FAIL protocol"),
            "short": (rtltrace.encode(_retires()[:-1]), 1, "not a corpus-green"),
        }
        for name, (text, want, marker) in cases.items():
            frame = scratch / f"{name}.frame"
            frame.write_text(text, encoding="utf-8", newline="")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = testrig.main(["adapt", str(frame), str(reference)])
            said = out.getvalue() + err.getvalue()
            ensure(code == want and marker in said,
                   f"`testrig adapt` on the {name} frame exits {want} saying {marker!r}, "
                   f"got {code}: {said[-300:]!r}")


_FIELD_RE: Final = re.compile(r"^\s*logic\s*(?:\[(\d+):0\])?\s*(\w+);", re.MULTILINE)


def _stimulus_matches_its_bench() -> None:
    """The Python copy of `stim_t` against the bench that declares it.

    The bench is the owner; `framesim` would report a drifted copy as a frame that
    does not come back, and this reports it on the host, by field.
    """
    bench = (TOOLS / "rvfi-harness" / "vos_rvfi_frame_tb.sv").read_text(encoding="utf-8")
    struct = bench[bench.index("typedef struct packed {"):bench.index("} stim_t;")]
    declared = tuple((name, int(high) + 1 if high else 1)
                     for high, name in _FIELD_RE.findall(struct))
    ensure(declared == testrig.STIMULUS,
           f"the stimulus layout differs from the bench's stim_t: {declared} against "
           f"{testrig.STIMULUS}")
    ensure(sum(width for _, width in declared) == testrig.STIMULUS_BITS,
           "the stimulus word is the width the bench reads")


def _stimulus_places_each_field() -> None:
    retire = _retires()[4]                         # the atomic: read, write and register
    word = int(testrig.stimulus_line(testrig.Drive(retire)), 16)
    fields: dict[str, int] = {}
    shift = testrig.STIMULUS_BITS
    for name, width in testrig.STIMULUS:
        shift -= width
        fields[name] = (word >> shift) & ((1 << width) - 1)
    ensure((fields["valid"], fields["trap"], fields["rd_addr"], fields["rd_bits"]) == (1, 0, 7, 3),
           f"the register fields land where the bench reads them, got {fields}")
    ensure((fields["mem_rmask"], fields["mem_wmask"], fields["mem_rdata"],
            fields["mem_wdata"]) == (0xFF, 0xFF, 3, 7),
           f"the access fields land where the bench reads them, got {fields}")
    trap = testrig.stimulus_line(testrig.Drive(_retires()[6]))
    stale = testrig.stimulus_line(testrig.Drive(_retires()[5], stale_cause=5))
    ensure(int(trap, 16) >> (testrig.STIMULUS_BITS - 8) & 0b11 == 0b01,
           "a trap drives trap and not valid, which is how the imported port presents it")
    ensure(int(stale, 16) != int(testrig.stimulus_line(testrig.Drive(_retires()[5])), 16),
           "a stale cause is driven where the port would present one")


def _family_is_the_decoding_directory() -> None:
    rows = testrig.family_rows()
    for mnemonic, operands, want in (("add", [5, 6, 7], "I"), ("mul", [5, 6, 7], "M"),
                                     ("lc", [5, 0, 25], "CHERI"),
                                     ("csrrw", [0, 0x300, 5], "Zicsr")):
        got = testrig.family(dialect.encode(mnemonic, operands, 0), rows)
        ensure(got == want, f"`{mnemonic}` decodes under {want}, got {got}")
    ensure(testrig.family(0xFFFFFFFF, rows) == "unmatched",
           "a word no row decodes is named as such rather than assigned a family")


def cases() -> list[Case]:
    return [
        Case("round-trip", _round_trip),
        Case("agrees-whole", _agrees_whole),
        Case("trap-cause-is-compared", _trap_cause_is_compared),
        Case("seeded-divergence-is-caught", _seeded_divergence_is_caught),
        Case("every-seed-is-reported", _every_seed_is_reported),
        Case("seeds-need-a-witness", _seeds_need_a_witness),
        Case("incomplete-is-not-green", _incomplete_is_not_green),
        Case("protocol-refusals", _protocol_refusals),
        Case("narrow-tag-is-refused", _narrow_tag_is_refused),
        Case("packet-view-carries-only-what-it-is-told",
             _packet_view_carries_only_what_it_is_told),
        Case("address-width-is-measured", _address_width_is_measured),
        Case("carry-round-trips", _carry_round_trips),
        Case("carry-names-what-no-line-holds", _carry_names_what_no_line_holds),
        Case("adapt-command", _adapt_command),
        Case("stimulus-matches-its-bench", _stimulus_matches_its_bench),
        Case("stimulus-places-each-field", _stimulus_places_each_field),
        Case("family-is-the-decoding-directory", _family_is_the_decoding_directory),
    ]
