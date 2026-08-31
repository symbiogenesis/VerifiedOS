# SPDX-License-Identifier: Apache-2.0
"""§4's emitter-provenance schema, owned once and read from both ends.

[The measurement contract](../../docs/freeze-measurement-contract.md)'s §4 fixes three
record shapes and the analyzer refuses to read any of them positionally: a header naming
exactly these fields in exactly this order is required, because a stream whose columns
moved would be read into the wrong labels and *a mis-stratified hit rate that is precise
is the one failure the whole schema exists to prevent*.

That refusal is only worth anything while the two ends agree, and until M1.4-prime there
was one end: the analyzer declared the fields and no producer existed. Now there are two,
so the declaration lives here and both read it. Written down twice, the schema would be a
transcription held together by nothing, which is the defect this repository is built to
catch; and the direction is the one K-83 permits, the deferred instruments reading `vos/`
and nothing under `tools/` reaching the other way. That rule reads a *path* as a
coupling, so the README stating the condition is named here in prose rather than linked:
a module on the landing loop's side that spelled the directory would be the finding.

**The paths are the instrument's declaration rather than the contract's.** §4 fixes the
record's fields and leaves the transport to whoever streams it. They sit under a build
tree no signing or storage path reads, because an image built under the provisional
profile is a measurement artifact and is neither deployed nor stored (R-18-003c).

**Three inputs arrive on four paths**, and the extra one is a circularity rather than a
convenience: recovering a site's dictionary index or escape from the encoded image means
decoding the bundle format, whose header width and slot count are exactly what FD-2
decides, so an analyzer that decoded the image would need the answer FD-1 and FD-2 are
jointly measuring. The composer knows the geometry it encoded at, so the encoded image is
delivered as its bytes and a per-site encoding table beside them.
"""

from typing import Final

# §4's record, in the line-oriented form the analyzer streams: one tab-separated row per
# emitted instruction site under a header naming these fields in this order, with `-` for
# a field the site does not carry.
SIDECAR_FIELDS: Final[tuple[str, ...]] = (
    "site_id", "unit", "compartment", "function", "opcode", "operand_class",
    "producer", "region_id", "region_class", "ct_arm", "knob",
)

# The link map from S5: where each site landed, and which bundle and slot carry it.
LINK_MAP_FIELDS: Final[tuple[str, ...]] = ("site_id", "address", "bundle", "slot")

# The per-site encoding table is the composer's rather than the analyzer's, for the
# circularity this module's docstring names.
IMAGE_SITE_FIELDS: Final[tuple[str, ...]] = ("site_id", "entry", "escape")

# Where each of §4's three inputs is looked for, and which of them each path carries:
# `(name, path, what it is, who produces it, which of the three streams it belongs to)`.
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

# The three inputs §4 names, derived from the paths that carry them rather than counted
# beside them.
STREAMS: Final[tuple[str, ...]] = tuple(dict.fromkeys(row[4] for row in INPUTS))

# Where a producer writes what it emits. One directory rather than a path per stream,
# because the paths above already say which file each is and a producer that had to know
# both would be restating half the table.
BUILD_DIR: Final[str] = "build/freeze"


def header(fields: tuple[str, ...]) -> str:
    """One stream's header line, as the producer writes it and the analyzer requires it.

    A function rather than a constant per stream, so that the header a producer writes
    and the tuple the analyzer compares against cannot be two statements of one fact even
    by accident: there is only the tuple, and this is how it is spelled.
    """
    return "\t".join(fields)


def row(fields: tuple[str, ...], values: dict[str, str]) -> str:
    """One record as its line, in the field order the schema fixes.

    Fail-closed on a value the schema has no field for and on a field the caller left
    out, because both are the same defect seen from the two sides: a producer whose
    record has drifted from the schema, which is exactly what the header requirement
    exists to catch one stream later.
    """
    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise KeyError(f"the record carries {', '.join(unknown)}, which §4's schema "
                       f"has no field for")
    missing = [name for name in fields if name not in values]
    if missing:
        raise KeyError(f"the record states no {', '.join(missing)}, which §4's schema "
                       f"requires of every site")
    return "\t".join(values[name] for name in fields)
