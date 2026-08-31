# SPDX-License-Identifier: Apache-2.0
"""The image composer, and the two of §4's three inputs it produces.

M1.4 excludes general dynamic linking by its own first line, so *the linker* here is an
image composer, which [image.py](image.py) already is for the emulator's ELF. What this
module adds is the half [the measurement contract](../../docs/freeze-measurement-contract.md)'s
§4 declares and M1.8b joins into its one table: the **link map** from S5, one row per
site with the bundle and slot that carry it, and the **encoded image** from S7 as its
bytes beside a per-site entry-and-escape table.

The third input is the sidecar stream, and it is deliberately not here. Its
`operand_class` and `producer` columns are the emitter's *intent*, which is why §4 has
the backend label them before assembly rather than have an analyzer infer them after it;
an assembler inventing those labels would be a label inferred over a measurement, which
is the failure that whole schema exists to prevent. It is M1.2's.

## The dictionary is empty, and the report that says so is the honest one

FD-1 states that it has no default arm, because the dictionary *is* the encoding: a
composer that left S6 out and called it a variant would be selecting by omission. So the
default dictionary here is **empty**, and under an empty dictionary every site is a
two-slot verbatim escape, which is exactly what the canonical 32-bit stream this
composer already lays down is. Every row's `entry` is then `-` and its `escape` is `1`,
and the analyzer's stratified hit rate reads zero.

That is a true statement about a machine nobody has selected a dictionary for, not a
degenerate one: FD-1 has not run, no dictionary exists to select from, and a composer
that selected one would be an instrument grading its own homework. What this produces is
the *wiring* the sweep needs, with the geometry and the dictionary both parameters of the
run.

## The geometry is a parameter of the run and never a verdict

§8 declares the candidate set `(h, k)` in {(16,3), (16,7), (16,15)} at `w = 16`, and §6's
FD-2 states **no default arm at all**, which M1.8a recorded as an owed act against the
contract. So `Geometry` carries the reference instantiation as its default value and this
module says, here and in what it emits, that a run at 128 bits is a run at a declared
parameter and not a freeze verdict. A caller sweeping FD-2 passes the other two.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from . import freezeschema
from .asm import Site

# The canonical instruction this composer lays down, in bits. It is what an escape has to
# carry verbatim, and it is why two slots of sixteen bits is the escape's width.
CANONICAL_BITS: Final[int] = 32


@dataclass(frozen=True)
class Geometry:
    """One bundle geometry: header bits, slots per bundle, and slot width.

    The defaults are §6's reference instantiation and are **not** a default arm: FD-2
    declares none, so what this carries is the one instantiation the contract names in
    prose, spelled as a parameter so that a sweep passes the others and a report can say
    which was used.
    """

    header: int = 16
    slots: int = 7
    width: int = 16

    @property
    def bits(self) -> int:
        return self.header + self.slots * self.width

    @property
    def escape_slots(self) -> int:
        """How many slots one verbatim instruction costs.

        Derived rather than declared, so that a sweep at another slot width cannot leave
        this saying two: a canonical instruction is `CANONICAL_BITS` wide and a slot
        carries `width` of them, rounded up.
        """
        return -(-CANONICAL_BITS // self.width)


@dataclass(frozen=True)
class Placed:
    """One site after packing: where it landed, and how it was encoded."""

    site: Site
    bundle: int
    slot: int
    entry: str
    escape: bool


@dataclass
class Composition:
    """One composed image: its bytes, its placed sites, and the geometry it used."""

    geometry: Geometry
    placed: list[Placed]
    image: bytes

    @property
    def hit_rate(self) -> float:
        """The aggregate hit rate, which R-15-036k forbids quoting alone.

        Here so that a caller can see it is zero and say why, never so that a report can
        print it on its own: §9 enforces the prohibition mechanically and the stratified
        rate is the analyzer's to compute from the sidecar labels this composer does not
        have.
        """
        if not self.placed:
            return 0.0
        return sum(1 for row in self.placed if not row.escape) / len(self.placed)


def compose(sites: list[Site], image: bytes, geometry: Geometry | None = None,
            dictionary: dict[str, str] | None = None) -> Composition:
    """Pack an assembled image's sites into bundles, at one geometry.

    `dictionary` maps a site's own opcode-and-operand key to the dictionary entry that
    encodes it, and the **empty** dictionary is the default for the reason this module's
    docstring states. A site the dictionary does not carry takes an escape, which costs
    `escape_slots` slots and reproduces the canonical word verbatim.

    The image's bytes are carried through rather than re-encoded, because the bundle
    format is not implemented in the model and an image this composer packed would be one
    the emulator could not fetch (see [dialect.py](dialect.py)'s own statement of that
    absence). What is produced is therefore the *placement* the freeze measures, over the
    stream the emulator actually runs.
    """
    geometry = geometry or Geometry()
    table = dictionary or {}
    placed: list[Placed] = []
    bundle = 0
    slot = 0
    for site in sites:
        entry = table.get(site.opcode)
        cost = 1 if entry is not None else geometry.escape_slots
        if slot + cost > geometry.slots:
            bundle += 1
            slot = 0
        placed.append(Placed(site=site, bundle=bundle, slot=slot,
                             entry=entry if entry is not None else "-",
                             escape=entry is None))
        slot += cost
    return Composition(geometry=geometry, placed=placed, image=image)


def link_map(composition: Composition) -> str:
    """S5's link map, under the header §4's schema fixes."""
    lines = [freezeschema.header(freezeschema.LINK_MAP_FIELDS)]
    lines += [freezeschema.row(freezeschema.LINK_MAP_FIELDS, {
        "site_id": row.site.site_id,
        "address": f"{row.site.address:#010x}",
        "bundle": str(row.bundle),
        "slot": str(row.slot),
    }) for row in composition.placed]
    return "\n".join(lines) + "\n"


def image_sites(composition: Composition) -> str:
    """The composer's per-site entry-and-escape table, under §4's header.

    `escape` is written `1` and `0` rather than `true` and `false` because the analyzer
    reads `-`, the empty cell, `0` and `false` as false and everything else as true, and
    a producer writing the one spelling that is unambiguous under that reading is the
    producer that cannot be misread if the reading is ever widened.
    """
    lines = [freezeschema.header(freezeschema.IMAGE_SITE_FIELDS)]
    lines += [freezeschema.row(freezeschema.IMAGE_SITE_FIELDS, {
        "site_id": row.site.site_id,
        "entry": row.entry,
        "escape": "1" if row.escape else "0",
    }) for row in composition.placed]
    return "\n".join(lines) + "\n"


def emit(composition: Composition, into: Path) -> list[tuple[str, int]]:
    """Write the two inputs this composer produces, and the image beside them.

    Returns `(path, size)` per file written, so that a caller reports what it produced
    rather than restating the paths it asked for. The directory is created; the sidecar
    stream is not written, and its absence is what a `freeze-report.py` run will name.
    """
    into.mkdir(parents=True, exist_ok=True)
    out: list[tuple[str, int]] = []
    for name, text in (("link-map.tsv", link_map(composition)),
                       ("image-sites.tsv", image_sites(composition))):
        path = into / name
        # `newline=""` and explicit UTF-8, which is this directory's own convention: a
        # stream the analyzer splits on `\n` must not acquire a `\r` from the host it
        # was written on.
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        out.append((str(path), len(text.encode("utf-8"))))
    binary = into / "image.bin"
    binary.write_bytes(composition.image)
    out.append((str(binary), len(composition.image)))
    return out
