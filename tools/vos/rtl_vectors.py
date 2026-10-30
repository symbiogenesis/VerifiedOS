# SPDX-License-Identifier: Apache-2.0
"""The RTL capability campaign's questions, using the shared oracle printer.

The authored Sail input retains the helpers and exact ordered sweeps. This module
declares each model call and its wire fields; oracle owns their formatting and
the shift register. The independently authored SystemVerilog consumes the text.
"""

from pathlib import Path

from vos import oracle

CAMPAIGN = "tools/cheri-equiv/campaign.sail"
SPLIT = "// The ordered sweeps."
SOURCES: tuple[str, ...] = (
    "model/model/prelude/prelude.sail",
    "model/model/prelude/errors.sail",
    "model/model/core/xlen.sail",
    "model/model/core/cap_format.sail",
    "model/model/core/cap_common.sail",
)


def _fields(*pairs: tuple[str, str]) -> tuple[oracle.Show, ...]:
    return tuple(oracle.Show(*pair) for pair in pairs)


# The wire fields are declarations, including the derived decode tag. Every
# answer remains a call on the model, never a Python copy of its semantics.
PRINTERS: tuple[oracle.Printer, ...] = (
    oracle.Printer("dec", (("c", "CapBits"),),
        _fields(("t", "b1"), ("c", "h16")),
        ("let probe = capBitsToCapability(false, c)",
         "let (base, top) = getCapBoundsBits(probe)",
         "let mal : bool = unsigned(top) < unsigned(0b0 @ base)",
         "let t : bool = not(mal)", "let cap = capBitsToCapability(t, c)",
         "let len = getCapLength(cap)"),
        _fields(("cap.perms", "h2"), ("cap.otype", "h1"),
                ("cap.normalized", "b1"), ("cap.E", "h2"),
                ("cap.B", "h2"), ("cap.T", "h2"), ("cap.address", "h9"),
                ("capToBits(cap)", "h16"), ("base", "h9"), ("top", "h10"),
                ("to_bits_truncate(cap_len_width, len)", "h10"), ("mal", "b1"))),
    oracle.Printer("sb", (("c", "CapBits"), ("base", "CapAddrBits"),
                          ("top", "CapLenBits")),
        _fields(("c", "h16"), ("base", "h9"), ("top", "h10")),
        ("let cap = capBitsToCapability(false, c)",
         "let (exact, out) = setCapBounds(cap, base, top)",
         "let (dbase, dtop) = getCapBoundsBits(out)", "let len = getCapLength(out)"),
        _fields(("exact", "b1"), ("out.normalized", "b1"), ("out.E", "h2"),
                ("out.B", "h2"), ("out.T", "h2"), ("out.address", "h9"),
                ("dbase", "h9"), ("dtop", "h10"),
                ("to_bits_truncate(cap_len_width, len)", "h10"))),
    oracle.Printer("sa", (("t", "bool"), ("c", "CapBits"), ("addr", "xlenbits")),
        _fields(("t", "b1"), ("c", "h16"), ("addr", "h16")),
        ("let cap = capBitsToCapability(t, c)",
         "let (rep, moved) = setCapAddr(cap, addr)",
         "let checked = setCapAddrChecked(cap, addr)"),
        _fields(("rep", "b1"), ("moved.address", "h9"), ("checked.tag", "b1"))),
    oracle.Printer("so", (("t", "bool"), ("c", "CapBits"), ("offset", "xlenbits")),
        _fields(("t", "b1"), ("c", "h16"), ("offset", "h16")),
        ("let cap = capBitsToCapability(t, c)",
         "let (rep, moved) = setCapOffset(cap, offset)",
         "let checked = setCapOffsetChecked(cap, offset)"),
        _fields(("rep", "b1"), ("moved.address", "h9"), ("checked.tag", "b1"))),
    oracle.Printer("io", (("t", "bool"), ("c", "CapBits"), ("delta", "xlenbits")),
        _fields(("t", "b1"), ("c", "h16"), ("delta", "h16")),
        ("let cap = capBitsToCapability(t, c)",
         "let (rep, moved) = incCapOffset(cap, delta)"),
        _fields(("rep", "b1"), ("moved.address", "h9"))),
    oracle.Printer("frc", (("c", "CapBits"), ("i", "CapAddrBits")),
        _fields(("c", "h16"), ("i", "h9")),
        ("let cap = capBitsToCapability(false, c)",),
        _fields(("fastRepCheck(cap, i)", "b1"))),
    oracle.Printer("ib", (("c", "CapBits"), ("addr", "xlenbits"),
                          ("size", "CapLenBits")),
        _fields(("c", "h16"), ("addr", "h16"), ("size", "h10")),
        ("let cap = capBitsToCapability(false, c)",),
        _fields(("inCapBounds(cap, addr, unsigned(size))", "b1"))),
    oracle.Printer("pe", (("code", "CapPermsCode"),), _fields(("code", "h2")),
        ("let cap = { null_cap with perms = code }",),
        _fields(("perms_expand(code)", "h3"), ("accessor_bitmap(cap)", "h3"))),
    oracle.Printer("pn", (("want", "CapPermsBits"),), _fields(("want", "h3")),
        ("let code = perms_narrow(want)",),
        _fields(("code", "h2"), ("perms_expand(code)", "h3"))),
    oracle.Printer("sl", (("c", "CapBits"), ("otyp", "CapOTypeBits")),
        _fields(("c", "h16"), ("otyp", "h1")),
        ("let cap = capBitsToCapability(true, c)", "let sealed = sealCap(cap, otyp)"),
        _fields(("isCapSealed(sealed)", "b1"), ("hasReservedOType(sealed)", "b1"),
                ("isSentry(sealed)", "b1"), ("capToBits(sealed)", "h16"),
                ("capToBits(unsealCap(sealed))", "h16"))),
    oracle.Printer("mb", (("t", "bool"), ("c", "CapBits")),
        _fields(("t", "b1"), ("c", "h16")),
        ("let cap = capBitsToCapability(t, c)", "let mem = capToMemBits(cap)",
         "let back = memBitsToCapability(t, mem)"),
        _fields(("mem", "h16"), ("back.tag", "b1"), ("capToBits(back)", "h16"))),
    oracle.Printer("it", (("v", "xlenbits"),), _fields(("v", "h16")),
        ("let cap = int_to_cap(v)",),
        _fields(("cap.tag", "b1"), ("capToBits(cap)", "h16"), ("cap.address", "h9"))),
    oracle.Printer("ac", (("c", "CapBits"),), _fields(("c", "h16")),
        ("let cap = capBitsToCapability(false, c)",),
        _fields(("to_bits_truncate(cap_addr_width, getCapCursor(cap))", "h9"),
                ("capAddrBits(cap)", "h16"), ("getCapBaseBits(cap)", "h16"),
                ("getCapTopBits(cap)", "h10"), ("getCapOffsetBits(cap)", "h16"),
                ("cap_to_integer_pc(cap)", "h16"))),
)


def harness(root: Path) -> str:
    """Place shared printing between the campaign's helpers and ordered calls."""
    domain = (root / CAMPAIGN).read_text(encoding="utf-8")
    if domain.count(SPLIT) != 1:
        raise oracle.SpecError(f"{CAMPAIGN}: expected one sweep boundary")
    helpers, schedule = domain.split(SPLIT)
    return "\n".join((helpers, oracle.printer_functions(PRINTERS), SPLIT, schedule))
