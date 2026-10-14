# SPDX-License-Identifier: Apache-2.0
"""The image the emulator loads: a position-fixed ELF64 with nothing in it.

The curated emulator loads `PT_LOAD` segments at their **physical** addresses
and reads `.symtab` for three names, `tohost`, `begin_signature`, and
`end_signature` (c_emulator/elf_loader.cpp, c_emulator/riscv_sim.cpp). That is
the whole contract this writer has to meet, so it emits exactly that and no
more: no dynamic table, no relocation section, no note, no interpreter, no
program headers past the ones that carry the two loadable sections.

The image is **position-fixed** by construction, which is the profile's own
composition-time-absolute reading rather than a simplification made here: the
physical space is 36 bits and dense, `satp` is Bare, and there is no loader to
relocate anything (R-15-002, R-15-002b, R-15-036l). So a section's address is
decided at layout and every symbol is an absolute number by the time this module
sees it.

M0.12 wrote this writer so that hand-written corpus programs had something to run.
Since M1.4-prime the backend's emitted mix is assembled into the same container, and
[compose.py](compose.py) composes images from it; M1.4 re-homes only LLVM's
disassembly and object tooling beside them, so another composer needs a reviewed
replacement contract.
"""

import struct
from dataclasses import dataclass, field
from pathlib import Path

EM_RISCV = 243
ET_EXEC = 2

PT_LOAD = 1
PF_X, PF_W, PF_R = 1, 2, 4

SHT_PROGBITS, SHT_SYMTAB, SHT_STRTAB, SHT_NOBITS = 1, 2, 3, 8
SHF_WRITE, SHF_ALLOC, SHF_EXECINSTR = 0x1, 0x2, 0x4

STB_GLOBAL = 1
STT_NOTYPE = 0

EHDR_SIZE, PHDR_SIZE, SHDR_SIZE, SYM_SIZE = 64, 56, 64, 24


@dataclass
class Section:
    """One loadable section: a name, the address it is composed at, and bytes."""

    name: str
    addr: int
    data: bytearray = field(default_factory=bytearray)
    writable: bool = False
    executable: bool = False

    @property
    def flags(self) -> int:
        return (SHF_ALLOC | (SHF_WRITE if self.writable else 0)
                | (SHF_EXECINSTR if self.executable else 0))

    @property
    def p_flags(self) -> int:
        return PF_R | (PF_W if self.writable else 0) | (PF_X if self.executable else 0)


class _Strtab:
    def __init__(self) -> None:
        self.blob = bytearray(b"\0")

    def add(self, name: str) -> int:
        if not name:
            return 0
        offset = len(self.blob)
        self.blob += name.encode() + b"\0"
        return offset


def write_elf(path: Path, sections: list[Section], symbols: dict[str, tuple[str, int]],
              entry: int) -> None:
    """Write `sections` as one ELF64 executable.

    `symbols` maps a name to the section it belongs to and its absolute address.
    A symbol in no section would load as `SHN_UNDEF` and the emulator would skip
    it, so every symbol here names one.
    """
    # A section with neither bytes nor a symbol carries nothing; one with a
    # symbol and no bytes still has to survive, or the symbol would be written
    # against `SHN_UNDEF` and the emulator would skip it.
    named = {section for section, _ in symbols.values()}
    sections = [s for s in sections if s.data or s.name in named]
    index_of = {s.name: i + 1 for i, s in enumerate(sections)}
    for name, (section, _) in symbols.items():
        if section not in index_of:
            raise ValueError(f"symbol {name} is in no emitted section")

    shstrtab, strtab = _Strtab(), _Strtab()
    # Section header names, in the order the headers are written.
    sh_names = [shstrtab.add("")] + [shstrtab.add(s.name) for s in sections]
    sh_names += [shstrtab.add(n) for n in (".symtab", ".strtab", ".shstrtab")]

    symtab = bytearray(SYM_SIZE)  # the null symbol
    for name, (section, value) in sorted(symbols.items()):
        symtab += struct.pack("<IBBHQQ", strtab.add(name),
                              (STB_GLOBAL << 4) | STT_NOTYPE, 0,
                              index_of[section], value, 0)

    # The file: headers, then each section's bytes at an aligned offset, then
    # the two string tables and the symbol table, then the section headers.
    offset = EHDR_SIZE + PHDR_SIZE * len(sections)
    blobs: list[tuple[int, bytes]] = []
    sh_offsets: list[int] = []
    for section in sections:
        # Segment file offset and address agree modulo the page size for any
        # loader that maps rather than copies; this one copies, and matching
        # them anyway costs padding and buys an image other tools will load.
        offset = _align_up(offset, 16)
        sh_offsets.append(offset)
        blobs.append((offset, bytes(section.data)))
        offset += len(section.data)

    tables = []
    for blob in (bytes(symtab), bytes(strtab.blob), bytes(shstrtab.blob)):
        offset = _align_up(offset, 8)
        tables.append((offset, blob))
        blobs.append((offset, blob))
        offset += len(blob)

    shoff = _align_up(offset, 8)

    out = bytearray()
    out += struct.pack(
        "<4sBBBBB7xHHIQQQIHHHHHH",
        b"\x7fELF", 2, 1, 1, 0, 0,          # class 64, little-endian, SYSV
        ET_EXEC, EM_RISCV, 1,
        entry, EHDR_SIZE, shoff, 0,
        EHDR_SIZE, PHDR_SIZE, len(sections),
        SHDR_SIZE, len(sections) + 4, len(sections) + 3,
    )
    # `sh_offsets` gets one entry per section above, so `strict` is asserting that
    # rather than testing it: a program header written against the wrong section's
    # offset produces an image that loads and is silently wrong.
    for section, file_offset in zip(sections, sh_offsets, strict=True):
        out += struct.pack("<IIQQQQQQ", PT_LOAD, section.p_flags, file_offset,
                           section.addr, section.addr,
                           len(section.data), len(section.data), 16)

    for at, blob in blobs:
        out += b"\0" * (at - len(out))
        out += blob
    out += b"\0" * (shoff - len(out))

    out += bytes(SHDR_SIZE)  # the null section header
    for i, (section, file_offset) in enumerate(zip(sections, sh_offsets, strict=True)):
        out += struct.pack("<IIQQQQIIQQ", sh_names[i + 1], SHT_PROGBITS,
                           section.flags, section.addr, file_offset,
                           len(section.data), 0, 0, 16, 0)
    symtab_off, symtab_blob = tables[0]
    strtab_off, strtab_blob = tables[1]
    shstrtab_off, shstrtab_blob = tables[2]
    out += struct.pack("<IIQQQQIIQQ", sh_names[-3], SHT_SYMTAB, 0, 0, symtab_off,
                       len(symtab_blob), len(sections) + 2, 1, 8, SYM_SIZE)
    out += struct.pack("<IIQQQQIIQQ", sh_names[-2], SHT_STRTAB, 0, 0, strtab_off,
                       len(strtab_blob), 0, 0, 1, 0)
    out += struct.pack("<IIQQQQIIQQ", sh_names[-1], SHT_STRTAB, 0, 0, shstrtab_off,
                       len(shstrtab_blob), 0, 0, 1, 0)

    path.write_bytes(bytes(out))


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def read_only_section(blob: bytes, name: str) -> Section:
    """Read an allocated section and verify the bytes the physical loader sees.

    This accepts the position-fixed ELF64 RISC-V format the in-tree writer emits.
    A section header alone is no loading evidence: exactly one read-only,
    non-executable PT_LOAD must carry all its bytes, and no other load segment
    may overwrite its physical extent, including with a zero-filled tail.
    """
    def file_bytes(offset: int, size: int) -> bytes:
        if offset + size > len(blob):
            raise ValueError("ELF extent exceeds the image bytes")
        return blob[offset:offset + size]

    if len(blob) < EHDR_SIZE:
        raise ValueError("image is not a supported ELF64 RISC-V executable")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", blob)
    ident, kind, machine, version = header[:4]
    if (ident[:7] != b"\x7fELF\x02\x01\x01" or kind != ET_EXEC
            or machine != EM_RISCV or version != 1 or header[8] != EHDR_SIZE
            or header[9] != PHDR_SIZE or header[11] != SHDR_SIZE):
        raise ValueError("image is not a supported ELF64 RISC-V executable")
    phoff, shoff = header[5:7]
    phnum, shnum, strings_index = header[10], header[12], header[13]
    if not 0 < strings_index < shnum or not 0 < phnum < 0xffff:
        raise ValueError("ELF graph binding requires ordinary section and program tables")
    file_bytes(phoff, phnum * PHDR_SIZE)
    file_bytes(shoff, shnum * SHDR_SIZE)
    sections = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + index * SHDR_SIZE)
                for index in range(shnum)]
    strings = sections[strings_index]
    if strings[1] != SHT_STRTAB:
        raise ValueError("ELF section-name table is not a string table")
    names = file_bytes(strings[4], strings[5])
    matching = []
    for section in sections:
        offset = section[0]
        end = names.find(b"\0", offset)
        if offset >= len(names) or end < 0:
            raise ValueError("ELF section name is outside the string table")
        if names[offset:end] == name.encode("utf-8"):
            matching.append(section)
    if len(matching) != 1:
        raise ValueError(f"ELF must contain exactly one {name} section")
    section = matching[0]
    kind, flags, address, offset, size = section[1:6]
    if (kind != SHT_PROGBITS or size == 0
            or flags & (SHF_ALLOC | SHF_WRITE | SHF_EXECINSTR) != SHF_ALLOC):
        raise ValueError(f"ELF {name} section must be allocated, read-only and non-executable")
    if address + size > 1 << 64:
        raise ValueError(f"ELF {name} section wraps its physical address extent")
    data = file_bytes(offset, size)
    carriers = 0
    for index in range(phnum):
        segment = struct.unpack_from("<IIQQQQQQ", blob, phoff + index * PHDR_SIZE)
        kind, flags, offset, _, physical, file_size, memory_size, _ = segment
        if kind != PT_LOAD:
            continue
        if file_size > memory_size:
            raise ValueError("ELF load segment's file extent exceeds its memory extent")
        if physical + memory_size > 1 << 64:
            raise ValueError("ELF load segment wraps its physical address extent")
        file_bytes(offset, file_size)
        if physical >= address + size or address >= physical + memory_size:
            continue
        if carriers:
            raise ValueError(f"ELF load segments overlap {name}")
        if (physical > address or physical + file_size < address + size
                or flags & (PF_R | PF_W | PF_X) != PF_R):
            raise ValueError(f"ELF {name} needs a complete read-only, non-executable load segment")
        loaded = file_bytes(offset + address - physical, size)
        if loaded != data:
            raise ValueError(f"ELF load segment substitutes {name} bytes")
        carriers += 1
    if carriers != 1:
        raise ValueError(f"ELF {name} is not physically loaded")
    return Section(name, address, bytearray(data))
