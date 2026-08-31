# SPDX-License-Identifier: Apache-2.0
"""The composer, the schema it writes under, and the images it must not move.

Three subjects, and the first is the one the freeze contract's §4 spends its whole
schema on: **the header is the join's only defence**, because a stream read positionally
would be read into the wrong labels and a mis-stratified hit rate that is precise is
worse than one that is absent. So the headers this producer writes are held against the
tuples the analyzer requires, in order, from the module that owns both.

The second is the composition: an empty dictionary is FD-1's own position, which states
no default arm because the dictionary *is* the encoding, and under one every site is a
verbatim escape and the hit rate is zero. That is a true statement about a machine
nobody has selected a dictionary for, and the case here is that it stays a statement
rather than becoming a measurement by accident.

The third is the regression M1.4-prime may not move: the differential corpus assembles
to the same bytes it always did. The digest is over every member's image in manifest
order, one figure rather than twenty-six, because it moves for exactly the reasons the
twenty-six would and a table of them would be twenty-six chances to rerecord one.
"""

import hashlib
import tempfile
from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import asm, compose, corpus, differential, freezeschema

_ROOT: Final[Path] = corpus.find_root(Path(__file__).resolve())

# Recorded from this tree: the sha256 over every corpus member's image, concatenated in
# manifest order, and their total size. This is M1.4-prime's own acceptance criterion and
# the one figure the encoder's generation was not allowed to move. On a mismatch, read
# the model's `encdec` clause for whichever mnemonic moved before touching either side;
# never repair a red run by rerecording.
_CORPUS_IMAGES: Final[str] = \
    "03f88f69731aabf59047dbc57b0a3778c908de727278e4e693d52addbf0c0d89"
_CORPUS_BYTES: Final[int] = 55_992


def _program(rows: int) -> str:
    body = "".join(f"    addi t0, t0, {n % 16}\n" for n in range(rows))
    return f".text\n_start:\n{body}    ecall\n"


def _compose(rows: int, geometry: compose.Geometry | None = None,
             dictionary: dict[str, str] | None = None) -> compose.Composition:
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "probe.s"
        with source.open("w", encoding="utf-8", newline="") as handle:
            handle.write(_program(rows))
        elf = Path(scratch) / "probe.elf"
        sites: list[asm.Site] = []
        asm.assemble_file(source, elf, sites)
        return compose.compose(sites, elf.read_bytes(), geometry, dictionary)


def _headers_are_the_schema_s() -> None:
    composed = _compose(4)
    for text, fields, what in (
        (compose.link_map(composed), freezeschema.LINK_MAP_FIELDS, "the link map"),
        (compose.image_sites(composed), freezeschema.IMAGE_SITE_FIELDS,
         "the per-site table"),
    ):
        header = text.splitlines()[0]
        ensure(header == "\t".join(fields),
               f"{what} heads its columns {header!r} and §4's schema names "
               f"{fields}: the analyzer refuses to read a stream positionally")
        for line in text.splitlines()[1:]:
            ensure(len(line.split("\t")) == len(fields),
                   f"{what} carries a row of {len(line.split('\t'))} cells under a "
                   f"{len(fields)}-column header")


def _every_site_is_recorded() -> None:
    composed = _compose(7)
    ensure(len(composed.placed) == 8,
           f"seven `addi` and one `ecall` are eight sites, got "
           f"{len(composed.placed)}")
    ids = [row.site.site_id for row in composed.placed]
    ensure(len(set(ids)) == len(ids), f"the site ids repeat: {ids}")
    ensure(ids == sorted(ids),
           "the ids are ordinals in source order, so they sort into emission order")
    addresses = [row.site.address for row in composed.placed]
    ensure(addresses == sorted(addresses) and addresses[0] == asm.TEXT_BASE,
           f"the sites carry ascending addresses from the text base, got {addresses}")


def _empty_dictionary_is_all_escapes() -> None:
    composed = _compose(6)
    ensure(all(row.escape for row in composed.placed),
           "under an empty dictionary every site is a verbatim escape")
    ensure(all(row.entry == "-" for row in composed.placed),
           "a site that took no dictionary entry writes `-` rather than an index")
    ensure(composed.hit_rate == 0.0,
           f"the hit rate under an empty dictionary is zero, got {composed.hit_rate}")


def _a_dictionary_is_a_parameter() -> None:
    """A supplied dictionary changes the packing, which is what makes the empty one a
    *default* rather than a limitation of the composer."""
    composed = _compose(6, dictionary={"addi": "e0"})
    hits = [row for row in composed.placed if not row.escape]
    ensure(len(hits) == 6,
           f"six `addi` sites take the one entry, got {len(hits)}")
    ensure(all(row.entry == "e0" for row in hits),
           "a hit carries the entry it took")
    ensure(composed.placed[-1].site.opcode == "ecall"
           and composed.placed[-1].escape,
           "the site the dictionary does not carry still escapes")


def _geometry_is_a_parameter() -> None:
    """FD-2 declares no default arm, so the geometry is a run's parameter: the three
    candidate `(h, k)` pairs §8 declares must each pack, and pack differently."""
    seen: list[int] = []
    for slots in (3, 7, 15):
        composed = _compose(9, compose.Geometry(header=16, slots=slots, width=16))
        ensure(composed.geometry.bits == 16 + slots * 16,
               f"a {slots}-slot bundle is {16 + slots * 16} bits")
        ensure(composed.geometry.escape_slots == 2,
               "a 32-bit instruction is two 16-bit slots")
        ensure(all(row.slot + 2 <= slots for row in composed.placed),
               f"a site's escape ran past the {slots} slots the bundle carries")
        seen.append(composed.placed[-1].bundle + 1)
    ensure(seen == sorted(seen, reverse=True),
           f"a wider bundle carries the same sites in fewer of them, got {seen}")


def _emitted_files_are_the_declared_ones() -> None:
    composed = _compose(3)
    with tempfile.TemporaryDirectory() as scratch:
        into = Path(scratch) / "freeze"
        written = {Path(path).name for path, _size in compose.emit(composed, into)}
    declared = {Path(path).name for _n, path, _w, producer, _s in freezeschema.INPUTS
                if "composer" in producer}
    ensure(written == declared,
           f"the composer wrote {sorted(written)} and §4 declares {sorted(declared)} "
           f"for it")


def _corpus_images_have_not_moved() -> None:
    manifest = differential.load(_ROOT)
    digest = hashlib.sha256()
    total = 0
    with tempfile.TemporaryDirectory() as scratch:
        for member in manifest.members:
            elf = Path(scratch) / f"{member.name}.elf"
            asm.assemble_file(manifest.source(member), elf)
            blob = elf.read_bytes()
            digest.update(blob)
            total += len(blob)
    ensure(len(manifest.members) == 26,
           f"the corpus carries {len(manifest.members)} members, recorded 26")
    ensure(total == _CORPUS_BYTES,
           f"the corpus assembles to {total} bytes, recorded {_CORPUS_BYTES}")
    ensure(digest.hexdigest() == _CORPUS_IMAGES,
           f"the corpus images hash {digest.hexdigest()}, recorded {_CORPUS_IMAGES}: "
           f"read the moved mnemonic's own encdec clause before rerecording")


def cases() -> list[Case]:
    return [
        Case("headers-are-the-schemas", _headers_are_the_schema_s),
        Case("every-site-is-recorded", _every_site_is_recorded),
        Case("empty-dictionary-is-all-escapes", _empty_dictionary_is_all_escapes),
        Case("a-dictionary-is-a-parameter", _a_dictionary_is_a_parameter),
        Case("geometry-is-a-parameter", _geometry_is_a_parameter),
        Case("emitted-files-are-the-declared-ones", _emitted_files_are_the_declared_ones),
        Case("corpus-images-have-not-moved", _corpus_images_have_not_moved),
    ]
