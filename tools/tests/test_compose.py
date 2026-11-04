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
to the same bytes it always did. Each reviewed member binds its own source and encoded
image bytes; adding a member cannot rerecord an old image.
"""

import argparse
import io
import struct
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from typing import Final, cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import asm, compose, corpus, corpus_images, env, freezeschema
from vos.cli import model as model_cli

_ROOT: Final[Path] = corpus.find_root(Path(__file__).resolve())

# The per-member fixture is reviewed evidence, never a generated-artifact repair.


def _program(rows: int) -> str:
    body = "".join(f"    addi t0, t0, {n % 16}\n" for n in range(rows))
    return f".text\n_start:\n{body}    ecall\n"


def _compose(rows: int, geometry: compose.Geometry | None = None,
             dictionary: dict[int, int] | None = None) -> compose.Composition:
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
    composed = _compose(6, dictionary={0x00028293: 0})
    hits = [row for row in composed.placed if not row.escape]
    ensure(len(hits) == 1 and hits[0].site.address == asm.TEXT_BASE,
           f"only addi t0,t0,0 takes its entry, got {[row.site.address for row in hits]}")
    ensure(all(row.entry == "0" for row in hits),
           "a hit carries the entry it took")
    ensure(composed.placed[-1].site.opcode == "ecall"
           and composed.placed[-1].escape,
           "the site the dictionary does not carry still escapes")


def _assembled_sites(source: str) -> tuple[list[asm.Site], bytes]:
    with tempfile.TemporaryDirectory() as scratch:
        program, executable = Path(scratch) / "word-sites.s", Path(scratch) / "word-sites.elf"
        program.write_text(source, encoding="utf-8", newline="")
        sites: list[asm.Site] = []
        asm.assemble_file(program, executable, sites)
        elf = executable.read_bytes()
    phoff = struct.unpack_from("<Q", elf, 32)[0]
    kind, flags, offset, _virtual, physical, size, _memory, _alignment = struct.unpack_from(
        "<IIQQQQQQ", elf, phoff)
    ensure((kind, flags, physical) == (1, 5, asm.TEXT_BASE),
           "the fixture's first ELF segment must load its executable text")
    return sites, elf[offset:offset + size]


def _dictionary_identity_includes_operands() -> None:
    sites, image = _assembled_sites(""".text
_start:
    addi t0, t0, 1
    addi t0, t0, 2
    addi t0, t1, 1
    addi t1, t0, 1
    addi t0, t0, 1
    ecall
""")
    expected = [0x00128293, 0x00228293, 0x00130293, 0x00128313, 0x00128293, 0x00000073]
    ensure([site.word for site in sites] == expected,
           "instruction identity must include immediate, source and destination registers")
    ensure(image == b"".join(word.to_bytes(4, "little") for word in expected),
           "the recorded words must be the independently specified ELF text bytes")
    composed = compose.compose(sites, image, dictionary={0x00128293: 0, 0x00130293: 1})
    ensure([row.entry for row in composed.placed] == ["0", "-", "1", "-", "0", "-"],
           "only complete word matches may take a dictionary entry")
    ensure([row.escape for row in composed.placed] == [False, True, False, True, False, True],
           "a changed register or immediate needs its own dictionary entry")
    ensure(composed.image == image, "placement must preserve the canonical bytes")


def _expanded_and_alignment_sites_keep_their_words() -> None:
    sites, image = _assembled_sites(""".text
_start:
    li t0, 0x12345678
    .balign 16
    ecall
""")
    expected = [0x123452B7, 0x6782829B, 0x00000013, 0x00000013, 0x00000073]
    ensure([site.word for site in sites] == expected,
           "each expanded instruction and each padding nop needs its actual word")
    ensure([site.address - asm.TEXT_BASE for site in sites] == [0, 4, 8, 12, 16],
           "instruction identities must follow emitted instruction boundaries")
    ensure(image == b"".join(word.to_bytes(4, "little") for word in expected),
           "pseudo and alignment metadata must agree with the loaded ELF text bytes")
    composed = compose.compose(sites, image, dictionary={0x00000013: 0, 0x123452B7: 1})
    ensure([row.entry for row in composed.placed] == ["1", "-", "0", "0", "-"],
           "pseudo expansion and repeated alignment nops use complete-word lookup")


def _invalid_dictionaries_are_refused() -> None:
    for dictionary, message in (
        ([], "map canonical words"),
        ({"addi": 0}, "unsigned 32-bit instruction word"),
        ({True: 0}, "unsigned 32-bit instruction word"),
        ({-1: 0}, "unsigned 32-bit instruction word"),
        ({1 << 32: 0}, "unsigned 32-bit instruction word"),
        ({0x13: "e0"}, "fitting the slot width"),
        ({0x13: True}, "fitting the slot width"),
        ({0x13: -1}, "fitting the slot width"),
        ({0x13: 1 << 16}, "fitting the slot width"),
        ({0x13: 0, 0x73: 0}, "indices must be distinct"),
        ({0x13: 1}, "contiguous from zero"),
    ):
        try:
            compose.compose([], b"", dictionary=cast("dict[int, int]", dictionary))
        except ValueError as error:
            ensure(message in str(error), f"unhelpful dictionary diagnostic: {error}")
        else:
            raise AssertionError(f"invalid dictionary was accepted: {dictionary!r}")


def _invalid_site_words_are_refused() -> None:
    for word in (True, -1, 1 << 32):
        try:
            asm.Site(site_id="bad#0", address=asm.TEXT_BASE, opcode="addi", word=word,
                     source=1, section=".text")
        except ValueError as error:
            ensure("unsigned 32-bit integer" in str(error), f"unhelpful site diagnostic: {error}")
        else:
            raise AssertionError(f"invalid instruction word was accepted: {word!r}")


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


def _invalid_geometry_is_refused() -> None:
    for header, slots, width, message in (
        (0, 7, 16, "header must be a positive integer"),
        (16, 0, 16, "slots must be a positive integer"),
        (16, 7, 0, "width must be a positive integer"),
        (-1, 7, 16, "header must be a positive integer"),
        (16, -1, 16, "slots must be a positive integer"),
        (16, 7, -1, "width must be a positive integer"),
        (6, 7, 16, "header needs one escape-start bit per slot"),
        (16, 1, 16, "verbatim instruction must fit within one bundle"),
        (16, 3, 8, "verbatim instruction must fit within one bundle"),
    ):
        try:
            compose.Geometry(header=header, slots=slots, width=width)
        except ValueError as error:
            ensure(message in str(error), f"unhelpful geometry diagnostic: {error}")
        else:
            raise AssertionError(f"invalid geometry was accepted: {(header, slots, width)}")


def _exploratory_widths_still_pack() -> None:
    for width, slots in ((8, 4), (12, 3), (32, 1), (64, 1)):
        geometry = compose.Geometry(header=slots, slots=slots, width=width)
        composed = _compose(4, geometry)
        ensure(composed.placed[0].bundle == 0,
               "the first escape should fit in the first bundle")
        ensure(all(row.slot + geometry.escape_slots <= slots for row in composed.placed),
               f"an escape ran past its bundle at width {width}")
        ensure(geometry.escape_slots * width >= compose.CANONICAL_BITS,
               f"an escape lost canonical bits at width {width}")


def _freeze_cli_refuses_geometry_before_loading_inputs() -> None:
    environment = env.Environment(_ROOT, _ROOT / "model", _ROOT, _ROOT,
                                  "geometry-test", 1, 0, 1, 1)
    for header, slots, width in ((16, 7, 0), (16, 1, 16), (6, 7, 16)):
        args = argparse.Namespace(header=header, slots=slots, width=width)
        error = io.StringIO()
        with patch.object(model_cli.differential, "load",
                          side_effect=AssertionError("invalid geometry must not load the corpus")), \
                redirect_stderr(error):
            code = model_cli.cmd_freeze_emit(environment, args)
        ensure(code == 1 and "FAIL freeze-emit:" in error.getvalue(),
               f"invalid geometry must produce a CLI refusal, got {code}: {error.getvalue()}")


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
    faults = corpus_images.check(_ROOT)
    ensure(not faults, "; ".join(faults))


def cases() -> list[Case]:
    return [
        Case("headers-are-the-schemas", _headers_are_the_schema_s),
        Case("every-site-is-recorded", _every_site_is_recorded),
        Case("empty-dictionary-is-all-escapes", _empty_dictionary_is_all_escapes),
        Case("a-dictionary-is-a-parameter", _a_dictionary_is_a_parameter),
        Case("dictionary-identity-includes-operands", _dictionary_identity_includes_operands),
        Case("expanded-and-alignment-site-words", _expanded_and_alignment_sites_keep_their_words),
        Case("invalid-dictionaries-are-refused", _invalid_dictionaries_are_refused),
        Case("invalid-site-words-are-refused", _invalid_site_words_are_refused),
        Case("geometry-is-a-parameter", _geometry_is_a_parameter),
        Case("invalid-geometry-is-refused", _invalid_geometry_is_refused),
        Case("exploratory-widths-still-pack", _exploratory_widths_still_pack),
        Case("freeze-cli-refuses-invalid-geometry", _freeze_cli_refuses_geometry_before_loading_inputs),
        Case("emitted-files-are-the-declared-ones", _emitted_files_are_the_declared_ones),
        Case("corpus-images-have-not-moved", _corpus_images_have_not_moved),
    ]
