# SPDX-License-Identifier: Apache-2.0
"""M3.5b's RoT programs: the ROM, the RoT runtime and its item-6 service on the RoT hart.

[The boot-handoff contract's section 9](../../docs/implementation/contracts/boot-handoff.md#9-the-target-chain)
states what the ROM (9.5), the runtime (9.6), the item-6 service (9.7) and the watchdog
observations (9.10) owe, and [vos_chain.h](../../firmware/chain/vos_chain.h) owns every
constant, record and prototype they use; this module reads both headers and restates none
of their numbers. It composes the three kinds of RoT run as `Program`s that the chain
campaign writes with `image.write_elf` and hands to the golden emulator under
`verifiedos-rot.json`:

- `compose_rom`: R1, the boot run. The ROM program at the reset entry, the signed stage-0
  image and the stage-1 images in their store windows, and the ROM's root table.
- `compose_runtime_only`: a watchdog case. A harness preamble performs the ROM's two device
  acts and enters a placed (unsigned) runtime payload with a state record the ROM would
  leave.
- `compose_service`: R2. The placed payload, a `run.service` state record and the item-6
  request, entered at the runtime's base.

The C bodies are [rom.c](../../firmware/chain/rom.c) and
[runtime.c](../../firmware/chain/runtime.c), each one translation unit compiled by the
contained compiler with `-fverifiedos-typed -I<root>/firmware/include` and `COMPILE_ARGS`
(empty: both units reach `vos_chain.h` and `chain_common.c` by quote includes relative to
themselves). This module takes their compiled streams as text; it never runs a compiler.
The assembly beside them, the only code touching a door, is the tracked `.s` files named
below; the composer prepends one `.equ` per macro of vos_boot.h and vos_chain.h, per
numeric `ROT_*` door offset of rot.sail, per RoT window base of the composition, and per
selection of this module listed next.

**What this module selects that section 9 leaves unnamed.** The runs' HTIF word is the
doubleword after the capture (`tohost`), so a run's export is one window; the ROM's root
table, which the runtime also reads to verify stage 1 under the same roots (R-09-036a),
sits at `ROOT_TABLE_BASE`; the ROM program sits at the assembler's text and data bases;
the entropy-halt case's injected health word is `FAILED_HEALTH`. Each is a composition
fact the contract owes a name to (this item's findings).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vos import asm, boot_target, config, image
from vos import boot_handoff as bh
from vos.cli import compiler_diff as cd

ROM_SOURCE = "firmware/chain/rom.c"
RUNTIME_SOURCE = "firmware/chain/runtime.c"
COMMON_SOURCE = "firmware/chain/chain_common.c"
ROM_ASSEMBLY = "firmware/chain/rom_entry.s"
RUNTIME_ASSEMBLY = "firmware/chain/runtime_entry.s"
POLICY_ASSEMBLY = "firmware/chain/rot_policy.s"
PREAMBLE_ASSEMBLY = "firmware/chain/preamble.s"
# Every file a composed RoT program is a function of, beside the compiled streams and
# the bound sources the two units include.
SOURCES = (ROM_SOURCE, RUNTIME_SOURCE, COMMON_SOURCE, ROM_ASSEMBLY, RUNTIME_ASSEMBLY,
           POLICY_ASSEMBLY, PREAMBLE_ASSEMBLY, bh.CHAIN_HEADER, bh.HEADER, bh.ROT_STAGE,
           bh.ROT_MODEL, bh.ROT_CONFIG, "tools/vos/chain_rot.py")

# Extra compiler arguments beyond `-fverifiedos-typed -I{root}/firmware/include`, as
# templates over `{root}`. None is needed; `compile_args` formats the whole list.
COMPILE_ARGS: tuple[str, ...] = ()

# Section 9.10's two runtime mutants, text substitutions of RUNTIME_ASSEMBLY (the table
# walk and the pets are assembly, so the mutations live there and the compiled stream is
# the unmutated runtime.c's). Each `old` occurs exactly once in that file.
RUNTIME_MUTANTS: dict[str, tuple[str, str]] = {
    # watchdog-stalled-step: step.entropy's ready predicate reads bit 62, which the
    # health word never sets, so the step never completes and no pet is issued.
    "stall": (
        "        srli    t1, t1, 32                      # step.entropy ready: bit 32 set and bit 33 clear\n",
        "        srli    t1, t1, 62                      # stall: bit 62, which the health word never sets\n"),
    # watchdog-early-pet: step.arm's completion pets without reading the tick door.
    "early-pet": (
        "        ld      a0, ROT_WDT_TICKS(c20)          # step.arm's pet point reads the tick door\n"
        "        ld      a1, ROT_WDT_EARLY(c20)\n"
        "        ld      a2, ROT_WDT_LATE(c20)\n"
        "        call    vos_chain_pet_due\n",
        "        li      a0, 1                           # early pet: step.arm pets without the tick door\n"),
}

# The ROM program and the runtime-only preamble: the reset entry the emulator takes from
# the ELF, and the assembler's data base, as the bring-up release target places its body.
ROM_TEXT_BASE = asm.TEXT_BASE
ROM_DATA_BASE = asm.DATA_BASE
# The ROM's root table: a presence doubleword (bit i: lifecycle state i accepts a root),
# then one public key per state from KEYS_AT, each the boot root's size and so aligned
# for an exact bound. Clear of every chain window of the RoT composition.
ROOT_TABLE_BASE = 0x8030_0000
ROOT_TABLE_PRESENT_AT = 0
ROOT_TABLE_KEYS_AT = 64
# Each RoT program's bounded stack, the contained compiler harness's, and the outgoing
# area the runtime reserves on it for vos_chain_runtime_verify's ninth argument.
STACK_BYTES = cd.STACK_BYTES
OUTGOING_BYTES = 16
# A purecap pointer is one capability, R-15-203's eight-byte granule.
POINTER_BYTES = 8
# The entropy-halt case's health word: the fail-stop latched (bit 33), completion clear.
FAILED_HEALTH = 1 << 33
# Expanded permission masks over model/model/core/cap_common.sail's bit positions.
PERMISSIONS: dict[str, int] = {
    "PERMS_R_GLOBAL": 0x3,             # global, load
    "PERMS_RW_GLOBAL": 0x7,            # global, load, store
    "PERMS_R_CAP_LM_LG_GLOBAL": 0xcb,  # global, load, load-capability, load-global, load-mutable
    "PERMS_STACK": 0xFFE,              # every bit but global: perms_stack, local
}
# The floor the ROM establishes by advancing counter 0 in the same power-on (F-438).
FLOOR_ADVANCES = range(1, 17)
# The RoT windows the programs open and the door extent each must cover (rot.sail).
WINDOWS = (("otp", "OTP", "ROT_OTP_STATE"), ("trng", "TRNG", "ROT_TRNG_BYTES"),
           ("monotonic_counters", "COUNTERS", "ROT_CTR_BYTES"),
           ("watchdog", "WATCHDOG", "ROT_WDT_BYTES"))

_ROT_LET = re.compile(r"^let (ROT_[A-Z_]+)\s*:\s*int\s*=\s*(\d+)\b", re.MULTILINE)


@dataclass(frozen=True)
class Program:
    """One RoT run's image: its composed assembly, every loaded section and its symbols.

    `sections` carries the assembled text and data and every placed data window;
    `symbols` carries the assembler's labels and the emulator's three names, `tohost`,
    `begin_signature` and `end_signature`, the last two spanning exactly the capture.
    """

    assembly: str
    sections: list[image.Section]
    symbols: dict[str, tuple[str, int]]
    entry: int


@dataclass(frozen=True)
class RomInputs:
    """R1's inputs: the ROM roots by lifecycle index (a missing index accepts no root),
    the signed stage-0 image, the signed stage-1 images by slot code, the floor F and
    whether the device-reading assembly injects a failed health word."""

    roots: Mapping[int, bytes]
    runtime_image: bytes
    slot_images: Mapping[int, bytes]
    floor: int
    entropy_failed: bool


def layout(root: Path) -> bh.Layout:
    """vos_chain.h's constants over vos_boot.h's."""
    return bh.chain_layout(root)


def tohost(lay: bh.Layout) -> int:
    """The RoT runs' HTIF word: the doubleword after the capture."""
    return lay["CHAIN_ROT_CAPTURE_BASE"] + lay["CHAIN_CAPTURE_BYTES"]


def compile_args(root: Path) -> list[str]:
    """The arguments after the compiler and its configuration, section 9.13's two first."""
    return ["-fverifiedos-typed", f"-I{root / 'firmware/include'}",
            *(argument.format(root=root) for argument in COMPILE_ARGS)]


def _struct_fields(root: Path, name: str) -> list[str]:
    """The member names of vos_chain.h's `typedef struct {...} name;`, all uint64_t."""
    text = (root / bh.CHAIN_HEADER).read_text(encoding="utf-8")
    match = re.search(r"typedef struct \{([^}]*)\} " + re.escape(name) + ";", text)
    if match is None:
        raise ValueError(f"{bh.CHAIN_HEADER} declares no struct {name}")
    fields: list[str] = []
    for raw in match.group(1).splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        member = re.fullmatch(r"uint64_t (\w+);", line)
        if member is None:
            raise ValueError(f"{bh.CHAIN_HEADER}: {name} has a member this composer cannot lay out: {line}")
        fields.append(str(member.group(1)))
    return fields


def _policy_bytes(root: Path, lay: bh.Layout) -> int:
    text = (root / bh.CHAIN_HEADER).read_text(encoding="utf-8")
    match = re.search(r"typedef struct \{([^}]*)\} vos_chain_rom_policy;", text)
    body = [line.split("//", 1)[0].strip() for line in (match.group(1) if match else "").splitlines()]
    if [line for line in body if line] != ["const uint8_t *root[VOS_LIFECYCLE_COUNT];"]:
        raise ValueError(f"{bh.CHAIN_HEADER}: vos_chain_rom_policy is not one root per lifecycle state")
    return lay["LIFECYCLE_COUNT"] * POINTER_BYTES


def equates(root: Path, run: Mapping[str, int] | None = None) -> dict[str, int]:
    """Every name the RoT assembly uses, with its value, from its owner."""
    lay = layout(root)
    values: dict[str, int] = dict(lay.c)
    for name, value in _ROT_LET.findall((root / bh.ROT_MODEL).read_text(encoding="utf-8")):
        values[name] = int(value)
    for key, label, extent in WINDOWS:
        base = config.integer(root / bh.ROT_CONFIG, "platform", key, "base")
        size = config.integer(root / bh.ROT_CONFIG, "platform", key, "size")
        need = values[extent] + (8 if extent == "ROT_OTP_STATE" else 0)
        if base is None or size is None or base % 8 or size < need:
            raise ValueError(f"the RoT composition lacks the {key} window")
        values[f"ROT_WINDOW_{label}"] = base
    for prefix, struct in (("CHAIN_INPUT", "vos_chain_rot_inputs"),
                           ("CHAIN_SELECTION", "vos_chain_selection")):
        fields = _struct_fields(root, struct)
        values.update({f"{prefix}_{field.upper()}_AT": 8 * at for at, field in enumerate(fields)})
        values[f"{prefix}_BYTES"] = 8 * len(fields)
    values["CHAIN_POLICY_BYTES"] = _policy_bytes(root, lay)
    values["CHAIN_POINTER_BYTES"] = POINTER_BYTES
    values["CHAIN_STACK_BYTES"] = STACK_BYTES
    values["CHAIN_ROT_TOHOST"] = tohost(lay)
    values["CHAIN_ROOT_TABLE_BASE"] = ROOT_TABLE_BASE
    values["CHAIN_ROOT_TABLE_PRESENT_AT"] = ROOT_TABLE_PRESENT_AT
    values["CHAIN_ROOT_TABLE_KEYS_AT"] = ROOT_TABLE_KEYS_AT
    values["CHAIN_FAILED_HEALTH"] = FAILED_HEALTH
    values.update(PERMISSIONS)
    values.update(run or {})
    return values


def _equ_block(values: Mapping[str, int]) -> str:
    return ("# --- composition constants (tools/vos/chain_rot.py) ---\n"
            + "".join(f"        .equ    {name}, {value:#x}\n" for name, value in sorted(values.items())))


def _body(stream: str, name: str) -> str:
    """A compiled stream the assembler takes whose frames fit the program's stack."""
    found = cd.refusals(stream)
    if found:
        raise ValueError(f"the {name} stream is outside the assembler dialect: {found[0]}")
    frames = boot_target.stack_ceiling(stream)
    if frames + OUTGOING_BYTES > STACK_BYTES:
        raise ValueError(f"the {name} stream's frames ({frames}) exceed its {STACK_BYTES}-byte stack")
    body = cd.normalize(stream)
    return body if body.endswith("\n") else body + "\n"


def _read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def _assemble(source: str, name: str, text_base: int,
              data_base: int) -> tuple[list[image.Section], dict[str, tuple[str, int]], int]:
    sections, symbols, entry = asm.Assembler(source, name, text_base=text_base,
                                             data_base=data_base).assemble()
    text = next(s for s in sections if s.name == ".text")
    if text.addr + len(text.data) > data_base:
        raise ValueError(f"the {name} text overruns its data base {data_base:#x}")
    if entry != text_base:
        raise ValueError(f"the {name} entry is not its first instruction")
    return sections, symbols, entry


def _window(name: str, base: int, data: bytes, capacity: int, *, executable: bool = False) -> image.Section:
    if len(data) > capacity:
        raise ValueError(f"{name} holds {len(data)} bytes; its window holds {capacity}")
    return image.Section(name, base, bytearray(data), writable=True, executable=executable)


def _capture(lay: bh.Layout) -> tuple[list[image.Section], dict[str, tuple[str, int]]]:
    """The capture, zero at load, and the HTIF word after it."""
    base = lay["CHAIN_ROT_CAPTURE_BASE"]
    sections = [image.Section(".capture", base, bytearray(lay["CHAIN_CAPTURE_BYTES"]), writable=True),
                image.Section(".htif", tohost(lay), bytearray(8), writable=True)]
    symbols = {"begin_signature": (".capture", base),
               "end_signature": (".capture", base + lay["CHAIN_CAPTURE_BYTES"]),
               "tohost": (".htif", tohost(lay))}
    return sections, symbols


def _mutated(text: str, mutant: str | None) -> str:
    if mutant is None:
        return text
    if mutant not in RUNTIME_MUTANTS:
        raise ValueError(f"no runtime mutant {mutant}")
    old, new = RUNTIME_MUTANTS[mutant]
    if text.count(old) != 1:
        raise ValueError(f"the {mutant} mutant's text occurs {text.count(old)} times in {RUNTIME_ASSEMBLY}")
    return text.replace(old, new, 1)


def rom_assembly(root: Path, rom_stream: str, floor: int, entropy_failed: bool) -> str:
    """The ROM program's composed assembly for one run's floor and health injection."""
    if floor not in FLOOR_ADVANCES:
        raise ValueError(f"the floor must be {FLOOR_ADVANCES.start} to {FLOOR_ADVANCES.stop - 1} advances")
    values = equates(root, {"ROM_FLOOR_ADVANCES": floor, "ROM_ENTROPY_FAILED": int(entropy_failed)})
    return (_equ_block(values) + _read(root, ROM_ASSEMBLY) + _read(root, POLICY_ASSEMBLY)
            + "# --- the compiled ROM body ---\n" + _body(rom_stream, "ROM"))


def root_table(lay: bh.Layout, roots: Mapping[int, bytes]) -> bytes:
    """The ROM's root table: the presence word, then one key slot per lifecycle state."""
    width = lay["BOOT_PUBLIC_KEY_BYTES"]
    table = bytearray(ROOT_TABLE_KEYS_AT + lay["LIFECYCLE_COUNT"] * width)
    present = 0
    for state, key in roots.items():
        if not 0 <= state < lay["LIFECYCLE_COUNT"] or len(key) != width:
            raise ValueError(f"a ROM root must be a {width}-byte key for a lifecycle index")
        present |= 1 << state
        at = ROOT_TABLE_KEYS_AT + state * width
        table[at:at + width] = key
    table[ROOT_TABLE_PRESENT_AT:ROOT_TABLE_PRESENT_AT + 8] = present.to_bytes(8, "little")
    return bytes(table)


def compose_rom(root: Path, rom_stream: str, inputs: RomInputs) -> Program:
    """R1: the ROM at the reset entry, which on release enters the runtime it placed."""
    lay = layout(root)
    source = rom_assembly(root, rom_stream, inputs.floor, inputs.entropy_failed)
    sections, symbols, entry = _assemble(source, "chain-rom", ROM_TEXT_BASE, ROM_DATA_BASE)
    stores = {lay["CHAIN_SLOT_A"]: (".store-a", lay["CHAIN_STORE_A_BASE"]),
              lay["CHAIN_SLOT_B"]: (".store-b", lay["CHAIN_STORE_B_BASE"]),
              lay["CHAIN_SLOT_RECOVERY"]: (".store-recovery", lay["CHAIN_STORE_RECOVERY_BASE"])}
    if set(inputs.slot_images) - set(stores):
        raise ValueError(f"slot images name no slot: {sorted(set(inputs.slot_images) - set(stores))}")
    sections.append(_window(".roots", ROOT_TABLE_BASE, root_table(lay, inputs.roots),
                            lay["CHAIN_ROT_STATE_BASE"] - ROOT_TABLE_BASE))
    sections.append(_window(".store-runtime", lay["CHAIN_STORE_RUNTIME_BASE"], inputs.runtime_image,
                            lay["CHAIN_STORE_RUNTIME_BYTES"]))
    for slot, blob in sorted(inputs.slot_images.items()):
        name, base = stores[slot]
        sections.append(_window(name, base, blob, lay["CHAIN_STORE_MMODE_BYTES"]))
    sections.append(_window(".state", lay["CHAIN_ROT_STATE_BASE"],
                            bytes(lay["CHAIN_ROT_STATE_WINDOW_BYTES"]),
                            lay["CHAIN_ROT_STATE_WINDOW_BYTES"]))
    capture, named = _capture(lay)
    return Program(source, sections + capture, {**symbols, **named}, entry)


def runtime_assembly(root: Path, runtime_stream: str, mutant: str | None = None) -> str:
    """The runtime's composed assembly, with one of RUNTIME_MUTANTS applied if named."""
    entry = _mutated(_read(root, RUNTIME_ASSEMBLY), mutant)
    return (_equ_block(equates(root)) + entry + _read(root, POLICY_ASSEMBLY)
            + "# --- the compiled runtime body ---\n" + _body(runtime_stream, "runtime"))


def runtime_payload(root: Path, runtime_stream: str, mutant: str | None = None) -> bytes:
    """Stage 0's payload: the runtime laid out for chain.rot_runtime_base, its text from
    the base and its data from chain.rot_runtime_data_at, the gap zero (section 9.3)."""
    lay = layout(root)
    base = lay["CHAIN_ROT_RUNTIME_BASE"]
    data_base = base + lay["CHAIN_ROT_RUNTIME_DATA_AT"]
    sections, _, _ = _assemble(runtime_assembly(root, runtime_stream, mutant), "chain-runtime",
                               base, data_base)
    text = next(s for s in sections if s.name == ".text")
    data = next(s for s in sections if s.name == ".data")
    flat = bytearray(data_base + len(data.data) - base)
    flat[0:len(text.data)] = text.data
    flat[data_base - base:] = data.data
    if not 0 < len(flat) <= lay["CHAIN_ROT_RUNTIME_REGION_BYTES"]:
        raise ValueError(f"the runtime payload is {len(flat)} bytes; its region holds "
                         f"{lay['CHAIN_ROT_RUNTIME_REGION_BYTES']}")
    return bytes(flat)


def _placed_runtime(lay: bh.Layout, payload: bytes) -> image.Section:
    if not payload:
        raise ValueError("the runtime payload is empty")
    return _window(".runtime", lay["CHAIN_ROT_RUNTIME_BASE"], payload,
                   lay["CHAIN_ROT_RUNTIME_REGION_BYTES"], executable=True)


def compose_runtime_only(root: Path, payload: bytes, state: bytes, floor: int) -> Program:
    """A runtime-only run (section 9.2): the preamble's device acts, then the runtime
    placed at its base with `state` at chain.rot_state_base, entered at its base."""
    lay = layout(root)
    if len(state) != lay["CHAIN_STATE_BYTES"]:
        raise ValueError(f"a state record is {lay['CHAIN_STATE_BYTES']} bytes")
    if floor not in FLOOR_ADVANCES:
        raise ValueError(f"the floor must be {FLOOR_ADVANCES.start} to {FLOOR_ADVANCES.stop - 1} advances")
    source = _equ_block(equates(root, {"PREAMBLE_FLOOR_ADVANCES": floor})) + _read(root, PREAMBLE_ASSEMBLY)
    sections, symbols, entry = _assemble(source, "chain-preamble", ROM_TEXT_BASE, ROM_DATA_BASE)
    sections.append(_placed_runtime(lay, payload))
    sections.append(_window(".state", lay["CHAIN_ROT_STATE_BASE"], state,
                            lay["CHAIN_ROT_STATE_WINDOW_BYTES"]))
    capture, named = _capture(lay)
    return Program(source, sections + capture, {**symbols, **named}, entry)


def compose_service(root: Path, payload: bytes, state: bytes, request: bytes) -> Program:
    """R2 (section 9.11): the runtime placed at its base, a `run.service` state record at
    chain.rot_state_base and the request at state.request_at, entered at the runtime's
    base. No harness code runs, so `assembly` is empty."""
    lay = layout(root)
    if len(state) != lay["CHAIN_STATE_BYTES"] or len(request) != lay["CHAIN_REQUEST_BYTES"]:
        raise ValueError(f"a service run takes a {lay['CHAIN_STATE_BYTES']}-byte state record "
                         f"and a {lay['CHAIN_REQUEST_BYTES']}-byte request")
    window = state + bytes(lay["CHAIN_STATE_REQUEST_AT"] - len(state)) + request
    sections = [_placed_runtime(lay, payload),
                _window(".state", lay["CHAIN_ROT_STATE_BASE"], window, lay["CHAIN_ROT_STATE_WINDOW_BYTES"])]
    capture, named = _capture(lay)
    return Program("", sections + capture, named, lay["CHAIN_ROT_RUNTIME_BASE"])
