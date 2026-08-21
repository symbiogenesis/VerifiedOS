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

This is *not* the image composer M1.4 ships. That one consumes a linker's output
for a whole base system; this one exists so that hand-written corpus programs
have something to run before any of that exists, and it is the acceptance corpus
M1.4 is later checked against (M0.12).
"""

import struct
from dataclasses import dataclass, field

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
    def __init__(self):
        self.blob = bytearray(b"\0")

    def add(self, name: str) -> int:
        if not name:
            return 0
        offset = len(self.blob)
        self.blob += name.encode() + b"\0"
        return offset


def write_elf(path, sections: list[Section], symbols: dict[str, tuple[str, int]],
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
    for section, file_offset in zip(sections, sh_offsets):
        out += struct.pack("<IIQQQQQQ", PT_LOAD, section.p_flags, file_offset,
                           section.addr, section.addr,
                           len(section.data), len(section.data), 16)

    for at, blob in blobs:
        out += b"\0" * (at - len(out))
        out += blob
    out += b"\0" * (shoff - len(out))

    out += bytes(SHDR_SIZE)  # the null section header
    for i, (section, file_offset) in enumerate(zip(sections, sh_offsets)):
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
