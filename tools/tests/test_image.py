# SPDX-License-Identifier: Apache-2.0
"""The ELF writer, held to the loader contract and to byte determinism.

`write_elf`'s whole contract is c_emulator/elf_loader.cpp: PT_LOAD segments at
physical addresses and a `.symtab` carrying three magic names. The output is a
pure function of its inputs, so one golden hash pins the entire header layout,
and the header arithmetic and the section filter are pinned beside it where a
regression would otherwise hide inside a hash mismatch with no wording.
"""

import hashlib
import struct
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import image


def _fixture(path: Path) -> bytes:
    """The two-section fixture image, written to `path` and read back."""
    text = image.Section(".text", 0x80000000,
                         bytearray(b"\x13\x00\x00\x00\x73\x00\x00\x00"),
                         executable=True)
    data = image.Section(".data", 0x80008000, bytearray(b"\xaa\xbb\xcc\xdd"),
                         writable=True)
    symbols = {"_start": (".text", 0x80000000),
               "tohost": (".data", 0x80008000),
               "begin_signature": (".data", 0x80008000),
               "end_signature": (".data", 0x80008004)}
    image.write_elf(path, [text, data], symbols, 0x80000000)
    return path.read_bytes()


def _header_counts(blob: bytes) -> tuple[int, int, int]:
    """(e_phnum, e_shnum, e_shstrndx) out of an ELF64 header."""
    e_phnum = int(struct.unpack_from("<H", blob, 56)[0])
    e_shnum = int(struct.unpack_from("<H", blob, 60)[0])
    e_shstrndx = int(struct.unpack_from("<H", blob, 62)[0])
    return e_phnum, e_shnum, e_shstrndx


def _golden_elf() -> None:
    # Recorded from image.write_elf over the fixture above. The hash pins every
    # header field, offset, and table at once; on a mismatch, read the diff of
    # the writer against the loader contract before rerecording with
    # hashlib.sha256 over the rewritten fixture.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        blob = _fixture(Path(td) / "f.elf")
    ensure(len(blob) == 792, f"the fixture image is {len(blob)} bytes, recorded 792")
    digest = hashlib.sha256(blob).hexdigest()
    ensure(digest == "6e6a6cd71c0bb5d94272a1fc3cbd0f60b039707ff2f66477adb2dd23aadce02e",
           f"the fixture image hashes to {digest}, not the recorded value")


def _header_arithmetic() -> None:
    # Two emitted sections, then the null header plus .symtab/.strtab/.shstrtab:
    # e_shnum = sections + 4 and e_shstrndx = sections + 3, with one PT_LOAD per
    # section.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        blob = _fixture(Path(td) / "f.elf")
    e_phnum, e_shnum, e_shstrndx = _header_counts(blob)
    ensure(e_phnum == 2, f"e_phnum is {e_phnum}, expected one PT_LOAD per section")
    ensure(e_shnum == 2 + 4, f"e_shnum is {e_shnum}, expected sections + 4")
    ensure(e_shstrndx == 2 + 3, f"e_shstrndx is {e_shstrndx}, expected sections + 3")


def _symbol_in_no_section() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        text = image.Section(".text", 0x80000000, bytearray(b"\x13\x00\x00\x00"),
                             executable=True)
        try:
            image.write_elf(Path(td) / "f.elf", [text],
                            {"ghost": (".bss", 0x80009000)}, 0x80000000)
        except ValueError as err:
            ensure("ghost" in str(err),
                   f"the refusal must name the symbol, said {str(err)!r}")
            return
        raise AssertionError("a symbol in no emitted section must be a ValueError")


def _symbol_only_section_kept() -> None:
    # An empty section carrying a symbol survives the filter, or the symbol
    # would be written against SHN_UNDEF and the emulator would skip it; an
    # empty section carrying nothing is dropped.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        text = image.Section(".text", 0x80000000, bytearray(b"\x13\x00\x00\x00"),
                             executable=True)
        data = image.Section(".data", 0x80008000, writable=True)
        kept = Path(td) / "kept.elf"
        image.write_elf(kept, [text, data],
                        {"_start": (".text", 0x80000000),
                         "tohost": (".data", 0x80008000)}, 0x80000000)
        e_phnum, e_shnum, _ = _header_counts(kept.read_bytes())
        ensure((e_phnum, e_shnum) == (2, 6),
               f"a symbol-only section must be emitted: headers say {(e_phnum, e_shnum)}")

        text = image.Section(".text", 0x80000000, bytearray(b"\x13\x00\x00\x00"),
                             executable=True)
        data = image.Section(".data", 0x80008000, writable=True)
        dropped = Path(td) / "dropped.elf"
        image.write_elf(dropped, [text, data],
                        {"_start": (".text", 0x80000000)}, 0x80000000)
        e_phnum, e_shnum, _ = _header_counts(dropped.read_bytes())
        ensure((e_phnum, e_shnum) == (1, 5),
               f"an empty unnamed section must be dropped: headers say {(e_phnum, e_shnum)}")


def cases() -> list[Case]:
    return [
        Case("golden-elf", _golden_elf),
        Case("header-arithmetic", _header_arithmetic),
        Case("symbol-in-no-section", _symbol_in_no_section),
        Case("symbol-only-section-kept", _symbol_only_section_kept),
    ]
