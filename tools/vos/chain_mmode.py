# SPDX-License-Identifier: Apache-2.0
"""The target chain's M-mode stage and kernel stage, as bytes and as the main-die run.

[The boot-handoff contract](../../docs/implementation/contracts/boot-handoff.md)
section 9 states the composition; [vos_chain.h](../../firmware/chain/vos_chain.h) owns
every constant, and this module reads them through `boot_handoff.chain_layout` and hands
them to the in-tree assembler as imported constants, so neither it nor the assembly it
composes restates one. Three pieces:

- **The stage-1 payload** (`mmode_payload`): [the hand-lowered entry](../../firmware/chain/mmode_entry.s)
  followed by the contained compiler's stream for [the body](../../firmware/chain/mmode.c),
  text from `chain.mmode_load_base` and data from `chain.mmode_data_at`, the data being
  the ML-DSA-87 kernel-stage root, then one eight-byte slot tag. The body's 32 KiB stack
  is the region's top, outside every payload; the RoT zeroes it when it places the
  image. The stream must be refusal-free and its frame sum within that stack.
- **The stage-2 payload** (`kernel_payload`): [the kernel stage](../../firmware/chain/kernel_stage.s),
  the bring-up kernel-entry fixture's eleven checks laid out by the `kernel.*` table from
  `chain.kernel_load_base`. Every label the M-mode stage derives state for is held
  against that table, so the stage's constants and the image cannot part silently.
- **R3, the main-die run** (`compose_main`): the sections and symbols of section 9.11's
  main-die run, built from bytes the RoT run captured and the campaign signed.

`COMPILE_ARGS` is empty: beyond `-fverifiedos-typed -I<root>/firmware/include`, which
every chain unit carries (section 9.13), the body needs nothing, because it reaches
`vos_chain.h` and the bound `../crypto` sources by quoted includes that the compiler's
preprocessing resolves beside the source.

The compiler is never run here: the campaign stages its stream where the contained
compiler is provisioned (section 9.14) and hands it to `mmode_payload`.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from vos import asm, boot_target, image
from vos import boot_handoff as bh
from vos.cli import compiler_diff as cd

MMODE_SOURCE: Final = "firmware/chain/mmode.c"
MMODE_ENTRY: Final = "firmware/chain/mmode_entry.s"
KERNEL_STAGE: Final = "firmware/chain/kernel_stage.s"
COMPILE_ARGS: Final[tuple[str, ...]] = ()
# The body's entry the hand-lowered stage calls, and the label of the root it carries.
ENTRY_SYMBOL: Final = "vos_chain_mmode_entry"
ROOT_LABEL: Final = "vos_chain_kernel_root"
SLOT_TAGS: Final = ("VOS_CHAIN_SLOT_TAG_A", "VOS_CHAIN_SLOT_TAG_B", "VOS_CHAIN_SLOT_TAG_RECOVERY")
# The kernel stage's labels, each with the vos_chain.h macros whose sum is its offset
# inside the kernel region: the M-mode stage derives the kernel-entry state from those
# macros, and the fixture's checks compare against these labels.
_KERNEL_LABELS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("kernel_text_base", ("CHAIN_KERNEL_TEXT_AT",)),
    ("kernel_entry", ("CHAIN_KERNEL_TEXT_AT", "CHAIN_KERNEL_ENTRY_AT")),
    ("kernel_trap", ("CHAIN_KERNEL_TEXT_AT", "CHAIN_KERNEL_TRAP_AT")),
    ("kernel_text_end", ("CHAIN_KERNEL_TEXT_AT", "CHAIN_KERNEL_TEXT_BYTES")),
    ("kdata_base", ("CHAIN_KERNEL_DATA_AT",)),
    ("tohost", ("CHAIN_KERNEL_DATA_AT",)),
    ("kdata_end", ("CHAIN_KERNEL_DATA_AT", "CHAIN_KERNEL_DATA_BYTES")),
    ("kstack_base", ("CHAIN_KERNEL_STACK_AT",)),
    ("kstack_end", ("CHAIN_KERNEL_STACK_AT", "CHAIN_KERNEL_STACK_BYTES")),
    ("root_table", ("CHAIN_KERNEL_ROOT_TABLE_AT",)),
    ("root_table_end", ("CHAIN_KERNEL_ROOT_TABLE_AT", "CHAIN_KERNEL_ROOT_TABLE_BYTES")),
    ("init_desc", ("CHAIN_KERNEL_INIT_AT",)),
    ("init_desc_end", ("CHAIN_KERNEL_INIT_AT", "CHAIN_KERNEL_INIT_BYTES")),
)


@dataclass(frozen=True)
class Program:
    """One run's program: the composite source, every loaded section, the symbols the
    emulator reads and the entry. A run composed from captured bytes has no source, and
    its `assembly` is empty."""

    assembly: str
    sections: list[image.Section]
    symbols: dict[str, tuple[str, int]]
    entry: int


@dataclass(frozen=True)
class Assembled:
    """One unit flattened from its text base to the end of its data, the gap zero."""

    assembly: str
    payload: bytes
    symbols: dict[str, int]
    constants: dict[str, int]


def externals(root: Path) -> dict[str, int]:
    """Every integer macro of vos_boot.h and vos_chain.h, by its C name."""
    return dict(bh.chain_layout(root).c)


def _flatten(source: str, name: str, text_base: int, data_base: int,
             imported: dict[str, int]) -> Assembled:
    assembler = asm.Assembler(source, name, text_base=text_base, data_base=data_base,
                              externals=imported)
    sections, _, entry = assembler.assemble()
    text = next(section for section in sections if section.name == ".text")
    data = next(section for section in sections if section.name == ".data")
    if entry != text_base:
        raise ValueError(f"{name}'s entry {entry:#x} is not its text base {text_base:#x}")
    if text.addr + len(text.data) > data.addr:
        raise ValueError(f"{name}'s text overruns its data base {data.addr:#x}")
    flat = bytearray(data.addr + len(data.data) - text.addr)
    flat[:len(text.data)] = text.data
    flat[data.addr - text.addr:] = data.data
    constants = {key: value for key, (value, _) in assembler.constants.items()}
    return Assembled(source, bytes(flat), dict(assembler.symbols), constants)


def _bytes_directives(blob: bytes) -> str:
    return "".join("        .byte " + ",".join(str(b) for b in blob[at:at + 32]) + "\n"
                   for at in range(0, len(blob), 32))


def mmode_assembly(root: Path, mmode_stream: str, kernel_root: bytes) -> str:
    """The stage-1 composite: the entry, the compiled stream, then the root as data."""
    lay = bh.chain_layout(root)
    if len(kernel_root) != lay["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"]:
        raise ValueError("the kernel-stage root is not an ML-DSA-87 public key's length")
    found = cd.refusals(mmode_stream)
    if found:
        raise ValueError(f"the M-mode stream is outside the assembler's dialect: {found[:3]}")
    body = cd.normalize(mmode_stream)
    if not re.search(rf"^\s*{ENTRY_SYMBOL}\s*:", body, re.MULTILINE):
        raise ValueError(f"the M-mode stream defines no {ENTRY_SYMBOL}")
    if not body.endswith("\n"):
        body += "\n"
    # The root is the data half's first item, at chain.mmode_data_at, which is aligned
    # beyond any power of two its extent rounds to.
    extent = 1 << (len(kernel_root) - 1).bit_length()
    entry = (root / MMODE_ENTRY).read_text(encoding="utf-8")
    return (entry + body + "# --- the kernel-stage root, carried as data ---\n"
            f"        .data\n        .balign {extent}\n{ROOT_LABEL}:\n" + _bytes_directives(kernel_root))


def mmode_image(root: Path, mmode_stream: str, kernel_root: bytes) -> Assembled:
    """The stage-1 image without its slot tag, held to its stack and its region."""
    lay = bh.chain_layout(root)
    source = mmode_assembly(root, mmode_stream, kernel_root)
    base = lay["CHAIN_MMODE_LOAD_BASE"]
    built = _flatten(source, "chain-mmode", base, base + lay["CHAIN_MMODE_DATA_AT"], externals(root))
    if built.symbols.get(ROOT_LABEL) != base + lay["CHAIN_MMODE_DATA_AT"]:
        raise ValueError("the kernel-stage root is not the M-mode image's first datum")
    stack_bytes = built.constants["MMODE_STACK_BYTES"]
    stack_base = built.constants["MMODE_STACK_BASE"]
    if built.constants["MMODE_STACK_TOP"] != base + lay["CHAIN_MMODE_REGION_BYTES"]:
        raise ValueError("the M-mode stage's stack is not the region's top")
    frames = boot_target.stack_ceiling(mmode_stream)
    if frames > stack_bytes:
        raise ValueError(f"the M-mode body's frame sum {frames} exceeds its {stack_bytes}-byte stack")
    if base + len(built.payload) + lay["CHAIN_SLOT_TAG_BYTES"] > stack_base:
        raise ValueError("a tagged M-mode payload would reach the stage's stack")
    return built


def slot_tag_bytes(root: Path) -> tuple[bytes, ...]:
    """The three slot tags, A, B and recovery, as vos_chain.h spells them."""
    tags = bh.string_constants(root, bh.CHAIN_HEADER)
    return tuple(tags[name].encode("ascii") for name in SLOT_TAGS)


def mmode_payload(root: Path, mmode_stream: str, kernel_root: bytes, slot_tag: bytes) -> bytes:
    """The stage-1 payload: the M-mode stage laid out from chain.mmode_load_base with
    data at chain.mmode_data_at, the kernel-stage root its first datum, then the slot
    tag (VOSSLOTA, VOSSLOTB or VOSRCVRY) appended."""
    if slot_tag not in slot_tag_bytes(root):
        raise ValueError(f"{slot_tag!r} is not one of vos_chain.h's slot tags")
    return mmode_image(root, mmode_stream, kernel_root).payload + slot_tag


def kernel_image(root: Path) -> Assembled:
    """The stage-2 image from chain.kernel_load_base, every label at its kernel.* place."""
    lay = bh.chain_layout(root)
    base = lay["CHAIN_KERNEL_LOAD_BASE"]
    built = _flatten((root / KERNEL_STAGE).read_text(encoding="utf-8"), "chain-kernel",
                     base + lay["CHAIN_KERNEL_TEXT_AT"], base + lay["CHAIN_KERNEL_DATA_AT"],
                     externals(root))
    for label, macros in _KERNEL_LABELS:
        want = base + sum(lay[macro] for macro in macros)
        if built.symbols.get(label) != want:
            raise ValueError(f"{KERNEL_STAGE}'s {label} is not at {want:#x}")
    if built.symbols["tohost"] != lay["CHAIN_TOHOST_BASE"]:
        raise ValueError(f"{KERNEL_STAGE}'s tohost is not chain.tohost_base")
    if len(built.payload) > lay["CHAIN_KERNEL_REGION_BYTES"]:
        raise ValueError("the kernel stage exceeds the kernel region")
    return built


def kernel_payload(root: Path) -> bytes:
    """The stage-2 payload, chain.kernel_region_bytes or shorter."""
    return kernel_image(root).payload


def compose_main(root: Path, window: bytes, record: bytes, mailbox: bytes,
                 kernel_store: bytes) -> Program:
    """R3: the released M-mode window at chain.mmode_load_base, the record at
    chain.handoff_base, the mailbox (request slot zero, response slot filled) at
    chain.mailbox_base inside the signature region, the signed stage-2 image in the
    kernel store, and a zero kernel region holding `tohost` at chain.tohost_base.
    The signature region is chain.main_signature_bytes from the mailbox base: the
    mailbox, then the M-mode capture. The entry is chain.mmode_load_base."""
    lay = bh.chain_layout(root)
    if len(window) != lay["CHAIN_MMODE_REGION_BYTES"]:
        raise ValueError("the released M-mode window is not chain.mmode_region_bytes long")
    if len(record) != lay["HANDOFF_BYTES"]:
        raise ValueError("the handoff record is not record.bytes long")
    if len(mailbox) != lay["CHAIN_MAILBOX_BYTES"]:
        raise ValueError("the mailbox is not mailbox.bytes long")
    request = lay["CHAIN_MAILBOX_REQUEST_AT"]
    if any(mailbox[request:request + lay["CHAIN_REQUEST_BYTES"]]):
        raise ValueError("the mailbox's request slot is not zero")
    if not lay["CHAIN_KSTAGE_HEADER_BYTES"] <= len(kernel_store) <= lay["CHAIN_KERNEL_STORE_BYTES"]:
        raise ValueError("the stage-2 image does not fit the kernel store window")
    signature = bytearray(lay["CHAIN_MAIN_SIGNATURE_BYTES"])
    signature[:len(mailbox)] = mailbox
    store = bytearray(lay["CHAIN_KERNEL_STORE_BYTES"])
    store[:len(kernel_store)] = kernel_store
    base, kernel = lay["CHAIN_MMODE_LOAD_BASE"], lay["CHAIN_KERNEL_LOAD_BASE"]
    sections = [
        image.Section(".mmode", base, bytearray(window), writable=True, executable=True),
        image.Section(".handoff", lay["CHAIN_HANDOFF_BASE"], bytearray(record), writable=True),
        image.Section(".signature", lay["CHAIN_MAILBOX_BASE"], signature, writable=True),
        image.Section(".kstore", lay["CHAIN_KERNEL_STORE_BASE"], store, writable=True),
        image.Section(".kernel", kernel, bytearray(lay["CHAIN_KERNEL_REGION_BYTES"]),
                      writable=True, executable=True),
    ]
    symbols = {
        "tohost": (".kernel", lay["CHAIN_TOHOST_BASE"]),
        "begin_signature": (".signature", lay["CHAIN_MAILBOX_BASE"]),
        "end_signature": (".signature", lay["CHAIN_MAILBOX_BASE"] + lay["CHAIN_MAIN_SIGNATURE_BYTES"]),
        "kernel_entry": (".kernel", kernel + lay["CHAIN_KERNEL_TEXT_AT"] + lay["CHAIN_KERNEL_ENTRY_AT"]),
    }
    return Program("", sections, symbols, base)
