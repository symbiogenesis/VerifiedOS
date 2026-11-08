# SPDX-License-Identifier: Apache-2.0
"""Compose RoT boot-chain programs (`compose_rom`, `compose_runtime_only`, `compose_service`).

Implements the RoT program compositions specified in
[boot-handoff.md §9](../../docs/implementation/contracts/boot-handoff.md#9-the-target-chain)
over constants from [vos_chain.h](../../firmware/chain/vos_chain.h), compiled assembly
streams for [rom.c](../../firmware/chain/rom.c) and [runtime.c](../../firmware/chain/runtime.c),
and the entry/policy `.s` files under `firmware/chain/`.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vos import asm, boot_target, config, image
from vos import boot_handoff as bh
from vos import compiler_diff as cd

ROM_SOURCE = "firmware/chain/rom.c"
RUNTIME_SOURCE = "firmware/chain/runtime.c"
COMMON_SOURCE = "firmware/chain/chain_common.c"
ROM_ASSEMBLY = "firmware/chain/rom_entry.s"
RUNTIME_ASSEMBLY = "firmware/chain/runtime_entry.s"
POLICY_ASSEMBLY = "firmware/chain/rot_policy.s"
PREAMBLE_ASSEMBLY = "firmware/chain/preamble.s"
SOURCES = (ROM_SOURCE, RUNTIME_SOURCE, COMMON_SOURCE, ROM_ASSEMBLY, RUNTIME_ASSEMBLY,
           POLICY_ASSEMBLY, PREAMBLE_ASSEMBLY, bh.CHAIN_HEADER, bh.HEADER, bh.ROT_STAGE,
           bh.ROT_MODEL, bh.ROT_CONFIG, "tools/vos/chain_rot.py")

COMPILE_ARGS: tuple[str, ...] = ()

# Section 9.10 runtime source mutants (`stall` and `early-pet`).
RUNTIME_MUTANTS: dict[str, tuple[str, str]] = {
    "stall": (
        "    uint64_t completed = (value >> 32) & 1u;  // the start-up tests completed for every source\n",
        "    uint64_t completed = (value >> 62) & 1u;  // stall: a bit the health word never sets\n"),
    "early-pet": (
        "  return (ticks >= early && ticks <= late) ? 1u : 0u;\n",
        "  (void)ticks;\n  (void)early;\n  (void)late;\n"
        "  return 1u;  // early pet: no tick count is consulted\n"),
}

ROM_TEXT_BASE = asm.TEXT_BASE
ROM_DATA_BASE = asm.DATA_BASE
# ROM root table layout: 8-byte presence mask at offset 0, followed by per-lifecycle public keys at offset 64.
ROOT_TABLE_BASE = 0x8030_0000
ROOT_TABLE_PRESENT_AT = 0
ROOT_TABLE_KEYS_AT = 64
STACK_BYTES = cd.STACK_BYTES
OUTGOING_BYTES = 16
POINTER_BYTES = 8
# Injected entropy-halt health word: fail-stop latched (bit 33), completion clear.
FAILED_HEALTH = 1 << 33
# Expanded permission masks over `model/model/core/cap_common.sail`.
PERMISSIONS: dict[str, int] = {
    "PERMS_R_GLOBAL": 0x3,
    "PERMS_RW_GLOBAL": 0x7,
    "PERMS_R_CAP_LM_LG_GLOBAL": 0xcb,
    "PERMS_STACK": 0xFFE,
}
FLOOR_ADVANCES = range(1, 17)
WINDOWS = (("otp", "OTP", "ROT_OTP_STATE"), ("trng", "TRNG", "ROT_TRNG_BYTES"),
           ("monotonic_counters", "COUNTERS", "ROT_CTR_BYTES"),
           ("watchdog", "WATCHDOG", "ROT_WDT_BYTES"))

_ROT_LET = re.compile(r"^let (ROT_[A-Z_]+)\s*:\s*int\s*=\s*(\d+)\b", re.MULTILINE)


@dataclass(frozen=True)
class Program:
    """Assembled RoT program image (`assembly`, loaded `sections`, ELF `symbols`, and `entry`)."""

    assembly: str
    sections: list[image.Section]
    symbols: dict[str, tuple[str, int]]
    entry: int


@dataclass(frozen=True)
class RomInputs:
    """Inputs for `compose_rom` (R1): ROM root keys by lifecycle index, stage-0/stage-1 images, floor, and health fault flag."""

    roots: Mapping[int, bytes]
    runtime_image: bytes
    slot_images: Mapping[int, bytes]
    floor: int
    entropy_failed: bool


def layout(root: Path) -> bh.Layout:
    """Return `vos_chain.h` and `vos_boot.h` layout constants."""
    return bh.chain_layout(root)


def tohost(lay: bh.Layout) -> int:
    """Return the HTIF `tohost` address immediately following the RoT capture window."""
    return lay["CHAIN_ROT_CAPTURE_BASE"] + lay["CHAIN_CAPTURE_BYTES"]


def compile_args(root: Path) -> list[str]:
    """Return the compiler flags for RoT C translation units (§9.13)."""
    return ["-fverifiedos-typed", f"-I{root / 'firmware/include'}",
            *(argument.format(root=root) for argument in COMPILE_ARGS)]


def _struct_fields(root: Path, name: str) -> list[str]:
    """Return the `uint64_t` field names of `typedef struct {...} <name>;` in `vos_chain.h`."""
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
    """Collect `.equ` constants for RoT assembly from headers, `rot.sail`, and the RoT config."""
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
    """Validate dialect and stack ceiling for compiled assembly `stream` and normalize it."""
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
    """Create the zero-initialized `.capture` and `.htif` sections and signature symbols."""
    base = lay["CHAIN_ROT_CAPTURE_BASE"]
    sections = [image.Section(".capture", base, bytearray(lay["CHAIN_CAPTURE_BYTES"]), writable=True),
                image.Section(".htif", tohost(lay), bytearray(8), writable=True)]
    symbols = {"begin_signature": (".capture", base),
               "end_signature": (".capture", base + lay["CHAIN_CAPTURE_BYTES"]),
               "tohost": (".htif", tohost(lay))}
    return sections, symbols


def mutated_source(root: Path, mutant: str) -> str:
    """Return `RUNTIME_SOURCE` with `RUNTIME_MUTANTS[mutant]` applied once."""
    if mutant not in RUNTIME_MUTANTS:
        raise ValueError(f"no runtime mutant {mutant}")
    text = _read(root, RUNTIME_SOURCE)
    old, new = RUNTIME_MUTANTS[mutant]
    if text.count(old) != 1:
        raise ValueError(f"the {mutant} mutant's text occurs {text.count(old)} times in {RUNTIME_SOURCE}")
    return text.replace(old, new, 1)


def rom_assembly(root: Path, rom_stream: str, floor: int, entropy_failed: bool) -> str:
    """Compose the ROM assembly source for `floor` and `entropy_failed`."""
    if floor not in FLOOR_ADVANCES:
        raise ValueError(f"the floor must be {FLOOR_ADVANCES.start} to {FLOOR_ADVANCES.stop - 1} advances")
    values = equates(root, {"ROM_FLOOR_ADVANCES": floor, "ROM_ENTROPY_FAILED": int(entropy_failed)})
    return (_equ_block(values) + _read(root, ROM_ASSEMBLY) + _read(root, POLICY_ASSEMBLY)
            + "# --- the compiled ROM body ---\n" + _body(rom_stream, "ROM"))


def root_table(lay: bh.Layout, roots: Mapping[int, bytes]) -> bytes:
    """Serialize the ROM root table (presence mask + per-lifecycle public keys)."""
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
    """Compose R1: ROM at reset entry, root table, stage-0/stage-1 store windows, and state/capture windows."""
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


def runtime_assembly(root: Path, runtime_stream: str) -> str:
    """Compose the RoT runtime assembly source over compiled `runtime_stream`."""
    return (_equ_block(equates(root)) + _read(root, RUNTIME_ASSEMBLY) + _read(root, POLICY_ASSEMBLY)
            + "# --- the compiled runtime body ---\n" + _body(runtime_stream, "runtime"))


def runtime_payload(root: Path, runtime_stream: str) -> bytes:
    """Assemble and flatten the stage-0 RoT runtime payload (§9.3)."""
    lay = layout(root)
    base = lay["CHAIN_ROT_RUNTIME_BASE"]
    data_base = base + lay["CHAIN_ROT_RUNTIME_DATA_AT"]
    sections, _, _ = _assemble(runtime_assembly(root, runtime_stream), "chain-runtime",
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
    """Compose a runtime-only watchdog run (§9.2) with preamble, placed runtime `payload`, and `state`."""
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
    """Compose R2 (§9.11): placed runtime `payload`, `run.service` `state`, and item-6 `request`."""
    lay = layout(root)
    if len(state) != lay["CHAIN_STATE_BYTES"] or len(request) != lay["CHAIN_REQUEST_BYTES"]:
        raise ValueError(f"a service run takes a {lay['CHAIN_STATE_BYTES']}-byte state record "
                         f"and a {lay['CHAIN_REQUEST_BYTES']}-byte request")
    window = state + bytes(lay["CHAIN_STATE_REQUEST_AT"] - len(state)) + request
    sections = [_placed_runtime(lay, payload),
                _window(".state", lay["CHAIN_ROT_STATE_BASE"], window, lay["CHAIN_ROT_STATE_WINDOW_BYTES"])]
    capture, named = _capture(lay)
    return Program("", sections + capture, named, lay["CHAIN_ROT_RUNTIME_BASE"])
