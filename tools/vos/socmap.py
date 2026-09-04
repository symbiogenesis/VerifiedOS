# SPDX-License-Identifier: Apache-2.0
"""The SoC address map as SystemVerilog, generated from the frozen composition.

R1c-i wrote the platform's three device apertures into
[the frozen profile's composition](../../model/config/verifiedos.json) beside the
eight windows it already carried, and R1c-ii authors the SoC top over that map. The
top is SystemVerilog and the map is JSON, so the map has to be said twice or it has
to be emitted: this module emits it, and K-88 holds the tracked artifact against
what this writes.

**Nothing here decides a placement.** Every base, every size and every permission
below is read out of the composition, which is the one artifact that fixes them
(R-15-002b). What this module decides is the spelling.

## What is read, and how it is found

The regions are `memory.regions`, in the composition's own order, each with the
three PMA bits an access is decided by and the memory type that separates a device
endpoint from main memory.

The apertures are found **by shape rather than by name**, and that is the whole of
why this generator is worth having. The model's own whole-map check writes its
apertures out one row per window, so a window a composition gains joins the check
only when somebody adds a row (K-94 is what holds that list against the shipped
files). A generator that carried a list of names here would be that same defect one
language over. So an aperture is any member of `platform` that is an object
declaring a boolean `supported` beside an integer `base`, and a twelfth window
arrives in this package without an edit.

**One declared window has no size the composition states**, the revocation sidecar's,
whose extent is `revocation_bitmap_bytes` in `model/model/core/revocation.sail` and a
function of the plane it covers rather than a key. It is emitted as a base with no
extent and named as such, because a size invented here would be exactly the
unowned derived fact this repository refuses. A decoder over this package therefore
reaches ten of the eleven apertures, which the package says out loud rather than
leaving to be discovered. What it says out loud is that the window is unsized and
never who sizes it: this module finds windows by shape and knows no window's name,
so a comment naming this one's owner would be right by accident today and wrong the
day a composition declares a second unsized window, with K-88 green either way
because it compares this emitter's output to itself.

## Which composition, and why one is enough

`model/config/verifiedos.json` alone. The three shipped configurations are one model
handed different files rather than three machines, and K-65 holds each non-primary
file against the primary in both directions on every key outside its own declared
divergence set; no aperture key and no region is in any of those sets, so the map
this emits is the map all three declare and reading the other two would be reading
the same fact twice.
"""

from pathlib import Path
from typing import cast

from . import jsonc
from .jsonc import Json

# The artifact and its owner, named here because three callers spell neither.
ARTIFACT = "rtl/vos_soc_map_pkg.sv"
COMPOSITION = "model/config/verifiedos.json"
PACKAGE = "vos_soc_map_pkg"

# The generated file's own repair line, so the artifact names the command that
# rewrites it rather than leaving a reader to find it.
REPAIR = "python tools/run.py check --fix"


class MapError(ValueError):
    """The composition does not carry what this emitter reads.

    Raised rather than worked around, on the fail-closed ground the generated group
    already states: a map emitted from a composition this cannot read would be a
    package that compiles and states a machine nobody composed.
    """


def _int(node: Json, *keys: str) -> int:
    """One whole number out of a configuration node, by the key path naming it."""
    here: Json = node
    for key in keys:
        if not isinstance(here, dict) or key not in here:
            raise MapError(f"{COMPOSITION} carries no {'.'.join(keys)}")
        # `Json` is recursive and a walk that re-binds through it leaves the checker
        # holding the alias expanded one level, which is the same type spelled
        # longer; narrowed back to what it is at every step, as `config.value` does.
        here = cast("Json", here[key])  # ty: ignore[redundant-cast]
    if isinstance(here, bool) or not isinstance(here, int):
        raise MapError(f"{COMPOSITION}'s {'.'.join(keys)} is not a whole number")
    return here


def _bitvector(node: Json, name: str) -> int:
    """A `{"len": n, "value": "0x..."}` literal, as the number it spells.

    The dialect's bitvector form is the one place the composition writes an address
    as a string, and it is decoded here rather than matched: a literal whose `value`
    is not a numeral is a finding and not a zero.
    """
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


def _flag(node: Json, key: str, where: str) -> bool:
    """One PMA bit of a region, which has to be stated and has to be a boolean."""
    if not isinstance(node, dict) or key not in node:
        raise MapError(f"{COMPOSITION}'s {where} states no {key}")
    found = node[key]
    if not isinstance(found, bool):
        raise MapError(f"{COMPOSITION}'s {where}.{key} is not a boolean")
    return found


def _identifier(key: str) -> str:
    """A composition key as the name this package spells it with.

    `monotonic_counters` becomes `MonotonicCounters`, which is the configuration
    package's own convention beside it and is what makes a reader able to find a
    window in the composition from its name here.
    """
    return "".join(part.capitalize() for part in key.split("_"))


class Region:
    """One declared memory region: where it is, and what it permits."""

    def __init__(self, index: int, node: Json) -> None:
        where = f"memory.regions[{index}]"
        if not isinstance(node, dict):
            raise MapError(f"{COMPOSITION}'s {where} is not a region")
        self.index = index
        self.base = _bitvector(node.get("base"), f"{where}.base")
        self.size = _bitvector(node.get("size"), f"{where}.size")
        attributes = node.get("attributes")
        if not isinstance(attributes, dict):
            raise MapError(f"{COMPOSITION}'s {where} declares no attributes")
        kind = attributes.get("mem_type")
        if kind not in ("IOMemory", "MainMemory"):
            raise MapError(f"{COMPOSITION}'s {where}.attributes.mem_type is "
                           f"{kind!r}, which is neither of the two kinds a region is")
        self.io = kind == "IOMemory"
        self.executable = _flag(attributes, "executable", f"{where}.attributes")
        self.readable = _flag(attributes, "readable", f"{where}.attributes")
        self.writable = _flag(attributes, "writable", f"{where}.attributes")


class Aperture:
    """One declared MMIO window: the key that names it and the extent it claims.

    `size` is `None` for the one window whose extent the composition does not state.
    """

    def __init__(self, key: str, node: dict[str, Json]) -> None:
        self.key = key
        self.name = _identifier(key)
        self.base = _int(node, "base")
        self.size = _int(node, "size") if "size" in node else None


def _apertures(platform: Json) -> list[Aperture]:
    """Every window the composition declares, found by shape and never by name.

    A member of `platform` is an aperture where it is an object carrying a boolean
    `supported` beside an integer `base`. A window a composition switches off is not
    one: the map this package states is the map the composed die has.
    """
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
            found.append(Aperture(key, node))
    if not found:
        raise MapError(f"{COMPOSITION} declares no aperture at all, so a map "
                       "emitted from it would state a die with no device on it")
    return found


def _hex64(value: int) -> str:
    """A 64-bit SystemVerilog literal, grouped as the composition writes addresses."""
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
// claims should do is decided by no artifact in this repository and by nothing in
// this file (see vos_soc_decode.sv, which reports that case rather than resolving
// it).
"""


def _regions(regions: list[Region]) -> list[str]:
    """The region table, as the package states it."""
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
    """The aperture table, and the residue the composition does not size."""
    sized = [a for a in apertures if a.size is not None]
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
    rows = [f"    '{{ base: {_hex64(a.base)}, size: {_hex64(a.size or 0)} }}"
            for a in sized]
    out += [row + ("," if i + 1 < len(rows) else "") for i, row in enumerate(rows)]
    out += ["  };", ""]
    out += ["  // The index each window sits at, so that a reader naming one window in",
            "  // this package can find it in the composition under the same name."]
    out += [f"  localparam int unsigned VosAp{a.name} = {i};"
            for i, a in enumerate(sized)]
    if unsized:
        # Written about *any* unsized window and never about the one that is unsized
        # today, which is the same discipline the finding above it keeps: this emitter
        # knows no window's name, so it cannot know which artifact sizes one, and a
        # comment naming the revocation sidecar's owner would be right by accident
        # until a composition declares a second unsized window and wrong from then on
        # with the gate still green, K-88 comparing this emitter's output to itself.
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
    """The whole artifact, from the composition alone."""
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
    regions = [Region(i, node) for i, node in enumerate(raw_regions)]
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
