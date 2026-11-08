# SPDX-License-Identifier: Apache-2.0
"""Emitter-provenance TSV schemas and build paths for
[docs/implementation/contracts/freeze-measurement.md](../../docs/implementation/contracts/freeze-measurement.md)."""

from typing import Final

# Tab-separated sidecar fields per emitted instruction site (`-` when not applicable).
SIDECAR_FIELDS: Final[tuple[str, ...]] = (
    "site_id", "unit", "compartment", "function", "opcode", "operand_class",
    "producer", "region_id", "region_class", "ct_arm", "knob",
)

# Link-map fields recording each site's final address, bundle index, and slot.
LINK_MAP_FIELDS: Final[tuple[str, ...]] = ("site_id", "address", "bundle", "slot")

# Per-site dictionary index / escape fields emitted alongside the encoded image.
IMAGE_SITE_FIELDS: Final[tuple[str, ...]] = ("site_id", "entry", "escape")

# `(name, path, description, producer, stream_category)` for freeze-measurement inputs.
INPUTS: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    ("sidecars", "build/freeze/sidecars.tsv",
     "the provenance sidecar stream from S1 and S4", "M1.2's backend",
     "the sidecar stream"),
    ("link_map", "build/freeze/link-map.tsv",
     "the link map from S5", "M1.4-prime's composer", "the link map"),
    ("image", "build/freeze/image.bin",
     "the encoded image from S7", "M1.4-prime's composer", "the encoded image"),
    ("image_sites", "build/freeze/image-sites.tsv",
     "the composer's per-site encoding table", "M1.4-prime's composer",
     "the encoded image"),
)

# Distinct stream categories derived from `INPUTS`.
STREAMS: Final[tuple[str, ...]] = tuple(dict.fromkeys(row[4] for row in INPUTS))

# Output directory for freeze-measurement artifacts.
BUILD_DIR: Final[str] = "build/freeze"


def header(fields: tuple[str, ...]) -> str:
    """Return the tab-separated header line for `fields`."""
    return "\t".join(fields)


def row(fields: tuple[str, ...], values: dict[str, str]) -> str:
    """Format `values` as a tab-separated row in `fields` order, rejecting unknown or missing keys."""
    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise KeyError(f"the record carries {', '.join(unknown)}, which §4's schema "
                       f"has no field for")
    missing = [name for name in fields if name not in values]
    if missing:
        raise KeyError(f"the record states no {', '.join(missing)}, which §4's schema "
                       f"requires of every site")
    return "\t".join(values[name] for name in fields)
