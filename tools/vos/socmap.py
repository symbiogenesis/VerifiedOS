# SPDX-License-Identifier: Apache-2.0
"""Generate [vos_soc_map_pkg.sv](../../rtl/vos_soc_map_pkg.sv) from [verifiedos.json](../../model/config/verifiedos.json).

Emits memory regions (`memory.regions`) and supported MMIO apertures (`platform.*`
entries carrying a boolean `supported` and integer `base`) for the SoC top (R-15-002b).
Apertures are discovered by shape rather than a hardcoded name list; unsized windows
(such as the revocation sidecar, whose extent depends on the tag plane) are emitted as
base-only constants outside the sized aperture table. [K-88](checks/generated.py)
verifies that the tracked package matches `emit()`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self

from . import jsonc
from .jsonc import Json

ARTIFACT = "rtl/vos_soc_map_pkg.sv"
COMPOSITION = "model/config/verifiedos.json"
PACKAGE = "vos_soc_map_pkg"

REPAIR = "python tools/run.py check --fix"


class MapError(ValueError):
    """Raised when `verifiedos.json` lacks required SoC map fields."""


def _int(node: dict[str, Json], key: str) -> int:
    """Read required integer field `key` from `node` (rejecting booleans)."""
    if key not in node:
        raise MapError(f"{COMPOSITION} carries no {key}")
    found = node[key]
    if isinstance(found, bool) or not isinstance(found, int):
        raise MapError(f"{COMPOSITION}'s {key} is not a whole number")
    return found


def _bitvector(node: Json, name: str) -> int:
    """Parse a `{"len": n, "value": "0x..."}` bitvector literal into an `int`."""
    if not isinstance(node, dict) or "value" not in node:
        raise MapError(f"{COMPOSITION}'s {name} is not a bitvector literal")
    raw = node["value"]
    if not isinstance(raw, str):
        raise MapError(f"{COMPOSITION}'s {name} states no value")
    try:
        return int(raw, 0)
    except ValueError as exc:
        raise MapError(f"{COMPOSITION}'s {name} is {raw!r}, "
                       f"which is not a numeral") from exc


def _flag(node: dict[str, Json], key: str, where: str) -> bool:
    """Read required boolean PMA attribute `key` from `node`."""
    if key not in node:
        raise MapError(f"{COMPOSITION}'s {where} states no {key}")
    found = node[key]
    if not isinstance(found, bool):
        raise MapError(f"{COMPOSITION}'s {where}.{key} is not a boolean")
    return found


def _identifier(key: str) -> str:
    """Convert `snake_case` composition key `key` to `PascalCase`."""
    return "".join(part.capitalize() for part in key.split("_"))


@dataclass(frozen=True, slots=True)
class Region:
    """A declared physical memory region and its PMA attributes."""

    base: int
    size: int
    io: bool
    executable: bool
    readable: bool
    writable: bool

    @classmethod
    def from_json(cls, index: int, node: Json) -> Self:
        where = f"memory.regions[{index}]"
        if not isinstance(node, dict):
            raise MapError(f"{COMPOSITION}'s {where} is not a region")
        base = _bitvector(node.get("base"), f"{where}.base")
        size = _bitvector(node.get("size"), f"{where}.size")
        attributes = node.get("attributes")
        if not isinstance(attributes, dict):
            raise MapError(f"{COMPOSITION}'s {where} declares no attributes")
        kind = attributes.get("mem_type")
        if kind not in ("IOMemory", "MainMemory"):
            raise MapError(f"{COMPOSITION}'s {where}.attributes.mem_type is "
                           f"{kind!r}, which is neither of the two kinds a region is")
        return cls(base=base, size=size, io=kind == "IOMemory",
                   executable=_flag(attributes, "executable", f"{where}.attributes"),
                   readable=_flag(attributes, "readable", f"{where}.attributes"),
                   writable=_flag(attributes, "writable", f"{where}.attributes"))


@dataclass(frozen=True, slots=True)
class Aperture:
    """A declared MMIO window (`size` is `None` when unsized in the composition)."""

    key: str
    base: int
    size: int | None

    @property
    def name(self) -> str:
        return _identifier(self.key)

    @classmethod
    def from_json(cls, key: str, node: dict[str, Json]) -> Self:
        return cls(key=key, base=_int(node, "base"),
                   size=_int(node, "size") if "size" in node else None)


def _apertures(platform: Json) -> list[Aperture]:
    """Discover enabled MMIO apertures in `platform` by `{supported: true, base: int}` shape."""
    if not isinstance(platform, dict):
        raise MapError(f"{COMPOSITION} declares no platform")
    found: list[Aperture] = []
    for key, node in platform.items():
        if not isinstance(node, dict):
            continue
        supported = node.get("supported")
        base = node.get("base")
        if not isinstance(supported, bool) or isinstance(base, bool):
            continue
        if not isinstance(base, int):
            continue
        if supported:
            found.append(Aperture.from_json(key, node))
    if not found:
        raise MapError(f"{COMPOSITION} declares no aperture at all, so a map "
                       "emitted from it would state a die with no device on it")
    return found


def _hex64(value: int) -> str:
    """Format `value` as a 64-bit SystemVerilog hex literal grouped by 16-bit nibbles."""
    digits = f"{value:016x}"
    return "64'h" + "_".join(digits[i:i + 4] for i in range(0, 16, 4))


def _bit(flag: bool) -> str:
    return "1'b1" if flag else "1'b0"


_HEADER = f"""\
// SPDX-License-Identifier: Apache-2.0
//
// The SoC address map.
//
// **Generated, and not edited by hand.** Every figure below is read out of
// {COMPOSITION}, which is the artifact that fixes the placement
// of every aperture on this die (R-15-002b); this file is that map said in the
// language the SoC top is written in. Rule K-88 holds these bytes against what
// `{REPAIR}` writes, so an edit here is a finding rather
// than a change.
//
// Two things this package deliberately is not. It is not a device list: what a
// window's device does at these addresses is not stated by the composition and is
// not invented here. And it is not a permission decision: the three PMA bits per
// region are the composition's own, and what an access to an address no aperture
// claims should do is owned by docs/hardware/platform-device-contracts.md and
// applied by vos_device_route. This package supplies geometry; vos_soc_decode
// reports the unclaimed case without embedding the route policy.
"""


def _regions(regions: list[Region]) -> list[str]:
    """Render the `VosRegions` table."""
    out = [
        "  // The memory regions this composition declares, in its own order. A region",
        "  // is where an access is decided before any aperture is consulted: the model",
        "  // runs `pmaCheck` over exactly these attributes ahead of the fall-through",
        "  // (model/model/sys/mem.sail), and an address outside every region is claimed",
        "  // by nothing at all.",
        f"  localparam int unsigned VosRegionCount = {len(regions)};",
        "",
        "  typedef struct packed {",
        "    logic [63:0] base;",
        "    logic [63:0] size;",
        "    logic        io;          // IOMemory rather than MainMemory",
        "    logic        executable;",
        "    logic        readable;",
        "    logic        writable;",
        "  } vos_soc_region_t;",
        "",
        "  localparam vos_soc_region_t VosRegions [VosRegionCount] = '{",
    ]
    rows = [
        f"    '{{ base: {_hex64(r.base)}, size: {_hex64(r.size)}, io: {_bit(r.io)}, "
        f"executable: {_bit(r.executable)}, readable: {_bit(r.readable)}, "
        f"writable: {_bit(r.writable)} }}"
        for r in regions
    ]
    out += [row + ("," if i + 1 < len(rows) else "") for i, row in enumerate(rows)]
    out.append("  };")
    return out


def _aperture_table(apertures: list[Aperture]) -> list[str]:
    """Render the `VosApertures` table and any unsized window base constants."""
    sized = [(a, size) for a in apertures if (size := a.size) is not None]
    unsized = [a for a in apertures if a.size is None]
    out = [
        "  // Every window the composition declares and gives an extent, in its own",
        "  // order. Found by shape rather than by a list of names, so a window the",
        "  // composition gains arrives here without an edit; what obliges each one to",
        "  // sit where it sits is R-15-002b, and what obliges the devices to exist at",
        "  // all is the implementation plan rather than the register.",
        f"  localparam int unsigned VosApertureCount = {len(sized)};",
        "",
        "  typedef struct packed {",
        "    logic [63:0] base;",
        "    logic [63:0] size;",
        "  } vos_soc_aperture_t;",
        "",
        "  localparam vos_soc_aperture_t VosApertures [VosApertureCount] = '{",
    ]
    rows = [f"    '{{ base: {_hex64(a.base)}, size: {_hex64(size)} }}"
            for a, size in sized]
    out += [row + ("," if i + 1 < len(rows) else "") for i, row in enumerate(rows)]
    out += ["  };", ""]
    out += ["  // The index each window sits at, so that a reader naming one window in",
            "  // this package can find it in the composition under the same name."]
    out += [f"  localparam int unsigned VosAp{a.name} = {i};"
            for i, (a, _) in enumerate(sized)]
    if unsized:
        # Keep the emitted comment generic over any unsized window rather than naming a
        # specific device, since windows are discovered by shape.
        out += ["",
                "  // The window or windows whose extent the composition does not state.",
                "  // An extent that is not a configuration key is a fact some other",
                "  // artifact owns, and inventing one here would be the unowned derived",
                "  // fact this repository refuses, so each is carried as a base alone and",
                "  // is outside the table above; a decoder over this package reaches one",
                "  // not at all rather than wrongly. Which artifact sizes a given window",
                "  // is read at that window and is deliberately not named here, this",
                "  // emitter finding windows by shape and knowing no window's name."]
        out += [f"  localparam int unsigned VosApertureCountUnsized = {len(unsized)};"]
        out += [f"  localparam logic [63:0] VosAp{a.name}Base = {_hex64(a.base)};"
                for a in unsized]
    return out


def emit(root: Path) -> str:
    """Render `vos_soc_map_pkg.sv` from `model/config/verifiedos.json`."""
    path = root / COMPOSITION
    if not path.is_file():
        raise MapError(f"{COMPOSITION} is not in this checkout")
    try:
        loaded = jsonc.load(path)
    except ValueError as exc:
        raise MapError(f"{COMPOSITION} does not parse: {exc}") from exc
    if not isinstance(loaded, dict):
        raise MapError(f"{COMPOSITION} is not a composition")

    memory = loaded.get("memory")
    if not isinstance(memory, dict):
        raise MapError(f"{COMPOSITION} declares no memory")
    raw_regions = memory.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise MapError(f"{COMPOSITION} declares no memory region")
    regions = [Region.from_json(i, node) for i, node in enumerate(raw_regions)]
    apertures = _apertures(loaded.get("platform"))

    lines = [_HEADER, f"package {PACKAGE};", ""]
    lines += [
        "  // R-15-002a: one physical address space, this wide. Every base and size",
        "  // below is stated at 64 bits and lies inside it.",
        f"  localparam int unsigned VosPhysAddrBits = "
        f"{_int(memory, 'physaddr_bits')};",
        "",
        "  // Where the attested devicetree is written (R-09-007). It shares the ROM",
        "  // region with the boot ROM and the two are held apart at composition and",
        "  // again where the blob is written, which is the only point its size is",
        "  // known (model/model/postlude/validate_config.sail).",
        f"  localparam logic [63:0] VosDtbAddress = "
        f"{_hex64(_bitvector(memory.get('dtb_address'), 'memory.dtb_address'))};",
        "",
    ]
    lines += _regions(regions)
    lines.append("")
    lines += _aperture_table(apertures)
    lines += ["", f"endpackage : {PACKAGE}", ""]
    return "\n".join(lines)
