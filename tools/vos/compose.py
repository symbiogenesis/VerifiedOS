# SPDX-License-Identifier: Apache-2.0
"""Bundle-placement composer for [freeze-measurement.md](../../docs/implementation/contracts/freeze-measurement.md) (§4).

Produces the S5 link map (`link-map.tsv`) and S7 per-site entry/escape table (`image-sites.tsv`)
alongside the raw canonical image (`image.bin`) for a given bundle `Geometry` and dictionary.
The sidecar stream (`operand_class` and `producer`) is emitted upstream before assembly.
"""

from dataclasses import dataclass
from pathlib import Path

from . import freezeschema
from .asm import CANONICAL_BITS, Site


@dataclass(frozen=True)
class Geometry:
    """Bundle geometry (`header` bits, `slots` per bundle, `width` bits per slot).

    Defaults to the provisional reference instantiation `(16, 7, 16)` (R-15-014a).
    """

    header: int = 16
    slots: int = 7
    width: int = 16

    def __post_init__(self) -> None:
        for name, value in (("header", self.header), ("slots", self.slots), ("width", self.width)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"bundle {name} must be a positive integer")
        if self.header < self.slots:
            raise ValueError("bundle header needs one escape-start bit per slot")
        if self.escape_slots > self.slots:
            raise ValueError("a verbatim instruction must fit within one bundle")

    @property
    def bits(self) -> int:
        return self.header + self.slots * self.width

    @property
    def escape_slots(self) -> int:
        """Number of slots required to encode one verbatim `CANONICAL_BITS` instruction."""
        return -(-CANONICAL_BITS // self.width)


@dataclass(frozen=True)
class Placed:
    """Bundle/slot placement and dictionary encoding for one instruction `Site`."""

    site: Site
    bundle: int
    slot: int
    entry: str
    escape: bool


@dataclass
class Composition:
    """Composed image bytes, placed sites, and bundle geometry."""

    geometry: Geometry
    placed: list[Placed]
    image: bytes

    @property
    def hit_rate(self) -> float:
        """Unstratified dictionary hit rate across placed sites (diagnostic only; R-15-036k)."""
        if not self.placed:
            return 0.0
        return sum(1 for row in self.placed if not row.escape) / len(self.placed)


def _dictionary(dictionary: dict[int, int] | None, width: int) -> dict[int, int]:
    """Validate that `dictionary` maps 32-bit canonical words to contiguous `width`-bit indices."""
    if dictionary is None:
        return {}
    if not isinstance(dictionary, dict):
        raise TypeError("dictionary must map canonical words to integer indices")
    for word, index in dictionary.items():
        if type(word) is not int or not 0 <= word < 1 << CANONICAL_BITS:
            raise ValueError("dictionary key must be an unsigned 32-bit instruction word")
        if type(index) is not int or not 0 <= index < 1 << width:
            raise ValueError("dictionary index must be an unsigned integer fitting the slot width")
    if len(set(dictionary.values())) != len(dictionary):
        raise ValueError("dictionary indices must be distinct")
    if set(dictionary.values()) != set(range(len(dictionary))):
        raise ValueError("dictionary indices must be contiguous from zero")
    return dict(dictionary)


def compose(sites: list[Site], image: bytes, geometry: Geometry | None = None,
            dictionary: dict[int, int] | None = None) -> Composition:
    """Pack assembled `sites` into bundles under `geometry` and `dictionary` (default empty)."""
    geometry = geometry or Geometry()
    table = _dictionary(dictionary, geometry.width)
    placed: list[Placed] = []
    bundle = 0
    slot = 0
    for site in sites:
        entry = table.get(site.word)
        cost = 1 if entry is not None else geometry.escape_slots
        if slot + cost > geometry.slots:
            bundle += 1
            slot = 0
        placed.append(Placed(site=site, bundle=bundle, slot=slot,
                             entry=str(entry) if entry is not None else "-",
                             escape=entry is None))
        slot += cost
    return Composition(geometry=geometry, placed=placed, image=image)


def link_map(composition: Composition) -> str:
    """Format the S5 `link-map.tsv` table."""
    lines = [freezeschema.header(freezeschema.LINK_MAP_FIELDS)]
    lines += [freezeschema.row(freezeschema.LINK_MAP_FIELDS, {
        "site_id": row.site.site_id,
        "address": f"{row.site.address:#010x}",
        "bundle": str(row.bundle),
        "slot": str(row.slot),
    }) for row in composition.placed]
    return "\n".join(lines) + "\n"


def image_sites(composition: Composition) -> str:
    """Format the S7 `image-sites.tsv` per-site entry/escape table."""
    lines = [freezeschema.header(freezeschema.IMAGE_SITE_FIELDS)]
    lines += [freezeschema.row(freezeschema.IMAGE_SITE_FIELDS, {
        "site_id": row.site.site_id,
        "entry": row.entry,
        "escape": "1" if row.escape else "0",
    }) for row in composition.placed]
    return "\n".join(lines) + "\n"


def emit(composition: Composition, into: Path) -> list[tuple[str, int]]:
    """Write `link-map.tsv`, `image-sites.tsv`, and `image.bin` to `into`; return `(path, size)`."""
    into.mkdir(parents=True, exist_ok=True)
    out: list[tuple[str, int]] = []
    for name, text in (("link-map.tsv", link_map(composition)),
                       ("image-sites.tsv", image_sites(composition))):
        path = into / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        out.append((str(path), len(text.encode("utf-8"))))
    binary = into / "image.bin"
    binary.write_bytes(composition.image)
    out.append((str(binary), len(composition.image)))
    return out
