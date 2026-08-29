# SPDX-License-Identifier: Apache-2.0
"""The RVFI-DII wire format, the projection onto the commit trace, and the shrinker.

Everything here decides on the host and needs no emulator, which is the point:
the codec is coupled byte-for-byte to a format nothing in this repository owns,
so the fixtures below are built from the byte offsets `RVFI-DII.md` states and
the bit offsets `core/rvfi_dii.sail` states rather than from what the decoder
happens to do. A field that moves has to fail here, on a laptop, before it fails
against a socket.

The shrinker is tested against a synthetic oracle for the same reason: delta
debugging is arithmetic over a predicate, and holding it to a predicate whose
answer is known is what separates a shrink that converges from one that merely
returns something shorter.
"""

from collections.abc import Sequence
from typing import Final

from tests.harness import Case, ensure
from vos import dialect, rvfi, trace, vengine


def _place(size: int, fields: dict[int, tuple[int, int]]) -> bytes:
    """A little-endian buffer of `size` bytes with `offset: (width, value)` in it."""
    out = bytearray(size)
    for at, (width, value) in fields.items():
        out[at:at + width] = value.to_bytes(width, "little")
    return bytes(out)


# The v1 packet of RVFI-DII.md, at that document's own byte offsets.
_V1: Final = _place(rvfi.EXEC_V1_BYTES, {
    0: (8, 7),                        # rvfi_order      [00 - 07]
    8: (8, 0x80000004),               # rvfi_pc_rdata   [08 - 15]
    16: (8, 0x80000008),              # rvfi_pc_wdata   [16 - 23]
    24: (8, 0x00100293),              # rvfi_insn       [24 - 31]
    32: (8, 0x1111),                  # rvfi_rs1_data   [32 - 39]
    40: (8, 0x2222),                  # rvfi_rs2_data   [40 - 47]
    48: (8, 0xDEAD),                  # rvfi_rd_wdata   [48 - 55]
    56: (8, 0x80002000),              # rvfi_mem_addr   [56 - 63]
    64: (8, 0xAA),                    # rvfi_mem_rdata  [64 - 71]
    72: (8, 0xBB),                    # rvfi_mem_wdata  [72 - 79]
    80: (1, 0x0F),                    # rvfi_mem_rmask  [80]
    81: (1, 0xFF),                    # rvfi_mem_wmask  [81]
    82: (1, 3),                       # rvfi_rs1_addr   [82]
    83: (1, 4),                       # rvfi_rs2_addr   [83]
    84: (1, 5),                       # rvfi_rd_addr    [84]
    85: (1, 1),                       # rvfi_trap       [85]
    86: (1, 0),                       # rvfi_halt       [86]
    87: (1, 1),                       # rvfi_intr       [87]
})


def _v2(*, integer: bool = True, memory: bool = True) -> bytes:
    """A v2 packet with the extensions it announces, at `rvfi_dii_v2.sail`'s offsets."""
    size = (rvfi.EXEC_V2_BYTES + (rvfi.EXT_INTEGER_BYTES if integer else 0)
            + (rvfi.EXT_MEMACCESS_BYTES if memory else 0))
    head = bytearray(_place(rvfi.EXEC_V2_BYTES, {
        8: (8, size),                 # trace_size, in bytes
        16: (8, 9),                   # basic_data.rvfi_order
        24: (8, 0x0FF0000B),          # basic_data.rvfi_insn
        32: (1, 1),                   # basic_data.rvfi_trap
        33: (1, 0),                   # basic_data.rvfi_halt
        34: (1, 1),                   # basic_data.rvfi_intr
        35: (1, 3),                   # basic_data.rvfi_mode
        36: (1, 2),                   # basic_data.rvfi_ixl
        40: (8, 0x80000010),          # pc_data.rvfi_pc_rdata
        48: (8, 0x80000014),          # pc_data.rvfi_pc_wdata
        56: (1, int(integer) | (int(memory) << 1)),
    }))
    head[0:8] = rvfi.MAGIC_V2
    out = bytearray(head)
    if integer:
        ext = bytearray(_place(rvfi.EXT_INTEGER_BYTES, {
            8: (8, 0xC800000080000000),   # rvfi_rd_wdata
            16: (8, 0x1111),              # rvfi_rs1_rdata
            24: (8, 0x2222),              # rvfi_rs2_rdata
            32: (1, 17),                  # rvfi_rd_addr
            33: (1, 3),                   # rvfi_rs1_addr
            34: (1, 4),                   # rvfi_rs2_addr
            35: (1, 1),                   # rvfi_rd_tag, bit 280
        }))
        ext[0:8] = rvfi.MAGIC_INTEGER
        out += ext
    if memory:
        ext = bytearray(_place(rvfi.EXT_MEMACCESS_BYTES, {
            8: (8, 0x00AA00AA),           # rvfi_mem_rdata, low 8 of 32
            40: (8, 0xDEADBEEF),          # rvfi_mem_wdata, low 8 of 32
            72: (4, 0x0F),                # rvfi_mem_rmask: four bytes, no tag
            76: (4, 0x1FF),               # rvfi_mem_wmask: eight bytes and a tag
            80: (8, 0x80002000),          # rvfi_mem_addr
        }))
        ext[0:8] = rvfi.MAGIC_MEMORY
        out += ext
    return bytes(out)


def _dii_packet() -> None:
    packet = rvfi.dii(0x00100293, cmd=rvfi.CMD_INSTRUCTION, time=0x1234)
    ensure(len(packet) == rvfi.DII_BYTES,
           f"an instruction packet is {rvfi.DII_BYTES} bytes, got {len(packet)}")
    ensure(packet[0:4] == (0x00100293).to_bytes(4, "little"),
           f"insn sits at bytes [0-3], got {packet[0:4]!r}")
    ensure(packet[4:6] == (0x1234).to_bytes(2, "little"),
           f"time sits at bytes [4-5], got {packet[4:6]!r}")
    ensure(packet[6] == rvfi.CMD_INSTRUCTION, f"cmd sits at byte [6], got {packet[6]}")
    ensure(packet[7] == 0, f"byte [7] is padding, got {packet[7]}")

    ensure(rvfi.end_of_trace()[6] == rvfi.CMD_END_OF_TRACE,
           "an end-of-trace carries command 0")
    probe = rvfi.version_probe()
    ensure(probe[6] == rvfi.CMD_END_OF_TRACE and probe[0:4] == b"SREV",
           f"the version probe is an end-of-trace carrying 'VERS', got {probe!r}")
    ensure(rvfi.select_version(2)[6] == rvfi.CMD_SET_VERSION,
           "selecting a wire format carries the 'v' command")


def _dii_refuses_wide_fields() -> None:
    for insn, cmd, time in ((1 << 32, 1, 0), (0, 1 << 8, 0), (0, 1, 1 << 16)):
        try:
            rvfi.dii(insn, cmd=cmd, time=time)
        except ValueError:
            continue
        raise AssertionError(f"dii({insn:#x}, cmd={cmd:#x}, time={time:#x}) "
                             f"must refuse a field wider than the wire")


def _decode_v1() -> None:
    packet = rvfi.decode_v1(_V1)
    for name, want in (("wire", 1), ("order", 7), ("pc_rdata", 0x80000004),
                       ("pc_wdata", 0x80000008), ("insn", 0x00100293),
                       ("rs1_rdata", 0x1111), ("rs2_rdata", 0x2222),
                       ("rd_wdata", 0xDEAD), ("mem_addr", 0x80002000),
                       ("mem_rdata", 0xAA), ("mem_wdata", 0xBB),
                       ("mem_rmask", 0x0F), ("mem_wmask", 0xFF),
                       ("rs1_addr", 3), ("rs2_addr", 4), ("rd_addr", 5),
                       ("trap", 1), ("halt", 0), ("intr", 1)):
        got = getattr(packet, name)
        ensure(got == want, f"v1 {name} decoded {got!r}, expected {want!r}")
    ensure(packet.retired, "a packet with halt 0 reports a retirement")
    ensure(not packet.rd_tag,
           "v1 has no rd_tag field at all, so a v1 packet never claims a tag")


def _decode_v1_length() -> None:
    try:
        rvfi.decode_v1(_V1[:-1])
    except ValueError:
        return
    raise AssertionError("a short v1 packet must be refused, not decoded")


def _decode_v2() -> None:
    packet = rvfi.decode_v2(_v2())
    for name, want in (("wire", 2), ("order", 9), ("insn", 0x0FF0000B),
                       ("trap", 1), ("halt", 0), ("intr", 1), ("mode", 3), ("ixl", 2),
                       ("pc_rdata", 0x80000010), ("pc_wdata", 0x80000014),
                       ("rd_addr", 17), ("rd_wdata", 0xC800000080000000),
                       ("rs1_addr", 3), ("rs2_addr", 4),
                       ("mem_addr", 0x80002000), ("mem_rmask", 0x0F),
                       ("mem_wmask", 0x1FF)):
        got = getattr(packet, name)
        ensure(got == want, f"v2 {name} decoded {got!r}, expected {want!r}")
    ensure(packet.rd_tag, "bit 280 of the integer extension is the destination's tag")
    ensure(packet.integer_present and packet.memory_present,
           "both availability bits were set and both extensions followed")


def _decode_v2_without_extensions() -> None:
    packet = rvfi.decode_v2(_v2(integer=False, memory=False))
    ensure(not packet.integer_present and not packet.memory_present,
           "an announced-nothing packet carries no extension")
    ensure(packet.rd_addr == 0 and packet.mem_rmask == 0,
           "and nothing is invented for the fields it did not carry")
    ensure(rvfi.v2_trace_size(_v2()) == len(_v2()),
           "a v2 packet states its own total length")


def _decode_v2_refuses_wrong_magic() -> None:
    for at, what in ((0, "the packet"), (rvfi.EXEC_V2_BYTES, "the integer extension"),
                     (rvfi.EXEC_V2_BYTES + rvfi.EXT_INTEGER_BYTES,
                      "the memory extension")):
        broken = bytearray(_v2())
        broken[at:at + 8] = b"not-here"
        try:
            rvfi.decode_v2(bytes(broken))
        except ValueError:
            continue
        raise AssertionError(f"a wrong magic on {what} must be a finding: read at the "
                             f"wrong offset, an extension decodes as plausible values")


def _mask_access() -> None:
    # width, tag -> the mask rvfi_mask_with_tag builds, and back again
    for width, tag in ((1, False), (2, False), (4, False), (8, False), (16, False),
                       (2, True), (4, True), (8, True), (16, True)):
        mask = (1 << width) - 1
        if tag:
            mask |= 1 << width
        got = rvfi.mask_access(mask)
        ensure(got == (width, tag),
               f"a mask of {mask:#x} is a {width}-byte access with tag {tag}, got {got}")
    ensure(rvfi.mask_access(0) is None, "an empty mask is no access at all")
    # The one ambiguity the encoding has, decided the way the tag granule
    # decides it: no access narrower than eight bytes carries a tag.
    ensure(rvfi.mask_access(0b11) == (2, False),
           "a run of two is a two-byte untagged access, not a one-byte tagged one")


def _mask_access_refuses_nonsense() -> None:
    # 0b101 and 0b110 are not low runs of ones at all; six and seven ones name
    # neither a width nor a width and its tag, both being one away from no
    # power of two.
    for mask in (0b101, 0b110, (1 << 6) - 1, (1 << 7) - 1):
        try:
            rvfi.mask_access(mask)
        except ValueError:
            continue
        raise AssertionError(f"a mask of {mask:#x} names no access this machine has "
                             f"and must be refused")


def _records_are_commit_grammar() -> None:
    got = rvfi.records(rvfi.decode_v2(_v2()))
    for line in got:
        ensure(trace.COMMIT_RE.match(line) is not None,
               f"the projection must be inside the commit grammar: {line!r}")
    ensure(got == [
        "I 9 0000000080000010 0FF0000B",
        "R 0000000080002000 4 0 00AA00AA",
        "W 0000000080002000 8 1 00000000DEADBEEF",
        "X 17 1 C800000080000000",
    ], f"the projection moved: {got}")


def _records_omit_x0() -> None:
    packet = rvfi.decode_v2(_v2(integer=False, memory=False))
    ensure(rvfi.records(packet) == ["I 9 0000000080000010 0FF0000B"],
           "a packet naming no destination register writes no X record")


def _packet_view_elides() -> None:
    commit = [
        "I 0000000080000000 00000113",
        "X 2 0 0000000000000000",
        "I 0000000080000004 0000A00B",
        "R 0000000080002000 8 1 00000000000000AA",
        "R 0000000080002008 8 1 00000000000000BB",
        "W 0000000080002000 8 0 00000000DEADBEEF",
        "W 0000000080002008 8 0 00000000DEADBEEF",
        "C 300 0000000000000042",
        "S 28 1 FFFFFFFFFFFFFFFF",
        "T 0 2",
        "X 5 0 0000000000000001",
    ]
    view, elided = rvfi.packet_view(commit)
    ensure(view == [
        "I 0000000080000000 00000113",
        "X 2 0 0000000000000000",
        "I 0000000080000004 0000A00B",
        "R 0000000080002000 8 1 00000000000000AA",
        "W 0000000080002000 8 0 00000000DEADBEEF",
        "X 5 0 0000000000000001",
    ], f"the view keeps one read, one write and the register write, in "
       f"{rvfi.EFFECT_ORDER} order; got {view}")
    ensure((elided.scr, elided.csr, elided.traps, elided.extra_reads,
            elided.extra_writes) == (1, 1, 1, 1, 1),
           f"every record the packet cannot carry is counted, got {elided}")
    ensure(elided.total == 5, f"the total is the sum of the five, got {elided.total}")


def _blocked_words() -> None:
    for mnemonic, operands in (("cbo.zero", [25]), ("cbo.scrub", [25]),
                               ("cloadtags", [5, 25]), ("creclaim", [5, 25])):
        word = dialect.encode(mnemonic, operands, 0)
        ensure(vengine.blocked(word),
               f"{mnemonic} moves more than one packet-sized access and must be "
               f"kept out of a generated stream")
    for mnemonic, operands in (("lc", [5, 0, 25]), ("sc", [5, 0, 25]),
                               ("add", [5, 6, 7]), ("cmove", [16, 1])):
        word = dialect.encode(mnemonic, operands, 0)
        ensure(not vengine.blocked(word),
               f"{mnemonic} fits the packet and must not be filtered out")


def _generation_is_reproducible() -> None:
    for name in vengine.TEMPLATES:
        first = vengine.generate(name, 11, 40)
        ensure(first == vengine.generate(name, 11, 40),
               f"the {name} template must replay from its seed alone")
        ensure(first != vengine.generate(name, 12, 40),
               f"the {name} template must not ignore its seed")
        ensure(all(0 <= word < (1 << 32) for word in first),
               f"the {name} template must generate 32-bit words")
        ensure(not any(vengine.blocked(word) for word in first),
               f"the {name} template must generate no block operation")
    # The profile excludes `C` and fixes ILEN at 32, so a word whose low two
    # bits are not 11 is not an instruction this machine has.
    ensure(all(word & 0b11 == 0b11 for word in vengine.generate("random", 3, 200)),
           "the random template must not spend its stream on compressed encodings")


def _defects_need_a_witness() -> None:
    plain = rvfi.decode_v2(_v2(integer=False, memory=False))
    for defect in vengine.DEFECTS.values():
        ensure(defect.apply(plain) == plain,
               f"the defect `{defect.name}` must be silent on a packet with no "
               f"witness: {defect.witness}")


def _defect_w_form() -> None:
    defect = vengine.DEFECTS["w-form-no-sext"]
    # addiw x5, x5, -1738, whose 32-bit result is negative: the shrunk
    # counterexample the rig reports against the curated emulator.
    negative = rvfi.Execution(wire=2, insn=0x9366829B, rd_addr=5,
                              rd_wdata=0xFFFFFFFFFFFFF936)
    ensure(defect.apply(negative).rd_wdata == 0x00000000FFFFF936,
           "the W-form defect drops the sign extension a 32-bit result needs")
    # The same instruction whose result is positive shows nothing.
    positive = rvfi.Execution(wire=2, insn=0x9366829B, rd_addr=5, rd_wdata=0x0936)
    ensure(defect.apply(positive) == positive,
           "and it is invisible where the 32-bit result has its top bit clear")
    # An instruction outside the W space is not touched whatever it computed.
    other = rvfi.Execution(wire=2, insn=0x00100293, rd_addr=5,
                           rd_wdata=0xFFFFFFFFFFFFF936)
    ensure(defect.apply(other) == other, "and it reaches only the W-form opcodes")


def _defect_tags() -> None:
    tagged = rvfi.Execution(wire=2, rd_addr=16, rd_wdata=0xC800000000000000, rd_tag=True)
    ensure(not vengine.DEFECTS["tag-dropped"].apply(tagged).rd_tag,
           "the tag defect reports the integer reading and not the tag beside it")
    stored = rvfi.Execution(wire=2, mem_addr=0x80000440, mem_wmask=0x1FF,
                            mem_wdata=0xC800000000000000)
    got = vengine.DEFECTS["store-tag-dropped"].apply(stored).mem_wmask
    ensure(got == 0xFF, f"the store defect clears the bit above the byte mask, got {got:#x}")


def _defect_load_sign() -> None:
    defect = vengine.DEFECTS["load-sign-extends"]
    # lhu x6, 0x60(c25): sixteen bits delivered, top bit set.
    unsigned = rvfi.Execution(wire=2, insn=0x060CD303, rd_addr=6, rd_wdata=0xFB60,
                              mem_rmask=0b11)
    ensure(defect.apply(unsigned).rd_wdata == 0xFFFFFFFFFFFFFB60,
           "the unsigned-load defect sign-extends what the load zero-extended")
    signed = rvfi.Execution(wire=2, insn=0x060C9303, rd_addr=6, rd_wdata=0xFB60,
                            mem_rmask=0b11)
    ensure(defect.apply(signed) == signed, "and it leaves the signed forms alone")


def _shrink_converges() -> None:
    """ddmin against an oracle whose answer is known, so convergence is decidable."""
    needed = {0xAA, 0xBB}
    stream = list(range(300))
    stream[100] = 0xAA
    stream[250] = 0xBB

    seen: list[int] = [0]

    def diverges(candidate: Sequence[int]) -> bool:
        seen[0] += 1
        return needed <= set(candidate)

    got, runs = vengine.shrink(stream, diverges)
    ensure(sorted(got) == sorted(needed),
           f"ddmin must converge on exactly the two witnesses, got {got}")
    ensure(runs == seen[0], f"the run count is what the predicate saw: {runs} against "
                            f"{seen[0]}")
    ensure(runs < len(stream), f"and it must cost fewer runs than the stream is long, "
                               f"got {runs} for {len(stream)}")


def _shrink_keeps_a_budget() -> None:
    stream = list(range(200))

    def diverges(candidate: Sequence[int]) -> bool:
        return len(candidate) == len(stream)

    got, runs = vengine.shrink(stream, diverges, budget=5)
    ensure(runs <= 5, f"the budget bounds the runs, got {runs}")
    ensure(got == stream, "a predicate nothing smaller satisfies leaves the stream whole")


def _shrink_needs_no_witness() -> None:
    def never(candidate: Sequence[int]) -> bool:
        return False

    got, _ = vengine.shrink([1, 2, 3, 4], never)
    ensure(got == [1, 2, 3, 4],
           "a predicate no subsequence satisfies returns the stream unchanged")


def cases() -> list[Case]:
    return [
        Case("dii-packet", _dii_packet),
        Case("dii-refuses-wide-fields", _dii_refuses_wide_fields),
        Case("decode-v1", _decode_v1),
        Case("decode-v1-length", _decode_v1_length),
        Case("decode-v2", _decode_v2),
        Case("decode-v2-without-extensions", _decode_v2_without_extensions),
        Case("decode-v2-refuses-wrong-magic", _decode_v2_refuses_wrong_magic),
        Case("mask-access", _mask_access),
        Case("mask-access-refuses-nonsense", _mask_access_refuses_nonsense),
        Case("records-are-commit-grammar", _records_are_commit_grammar),
        Case("records-omit-x0", _records_omit_x0),
        Case("packet-view-elides", _packet_view_elides),
        Case("blocked-words", _blocked_words),
        Case("generation-is-reproducible", _generation_is_reproducible),
        Case("defects-need-a-witness", _defects_need_a_witness),
        Case("defect-w-form", _defect_w_form),
        Case("defect-tags", _defect_tags),
        Case("defect-load-sign", _defect_load_sign),
        Case("shrink-converges", _shrink_converges),
        Case("shrink-keeps-a-budget", _shrink_keeps_a_budget),
        Case("shrink-needs-no-witness", _shrink_needs_no_witness),
    ]
