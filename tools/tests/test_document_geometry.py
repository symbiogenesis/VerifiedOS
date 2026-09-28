# SPDX-License-Identifier: Apache-2.0
"""Canonical geometry calculations remain guarded without incidental prose copies."""

from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import capformat, geometry
from vos import corpus as corpus_mod
from vos.checks import Context, counts_geometry, counts_tagplane
from vos.register import REGISTER, read_artifacts, read_register
from vos.report import Reporter

_CANDIDATES = ("**the block is 32, 64, 128, 256, or 512 bytes**, which is "
               "4, 8, 16, 32, or 64 granules")
_GEOMETRY_REGISTER = (
    "# Register\n\n## §15. Hardware\n\n"
    "**R-15-007q** IS: return the tag group.\n"
    "· Accept: the block at most **512 bytes**.\n\n"
    "**R-15-181a** IS: The ECC codeword's data payload is 256 bits.\n")
_TAG_REGISTER = (
    "# Register\n\n## §15. Hardware\n\n"
    "**R-15-203** MUST: one validity tag per **64-bit** granule.\n"
    "· Accept: tag-plane density doubles to 1.56% of the array; "
    "the tag plane's ~1.56% share of the array.\n\n"
    "**R-15-181a** IS: The ECC codeword's data payload is 256 bits with 10 SECDED check "
    "bits, under a DECTED code of 8 check bits, the fewest any code of minimum distance 6 "
    "over 4 bits admits, for total metadata of some 22 bits per 256 data bits (8.6%), of "
    "which the tag plane with its own code is 12, some 4.7% of the payload; 128 bits (18 "
    "per 128, 14.1%, the tag plane with its code 9 of them at 7.0%) is the fallback.\n"
    "· Accept: the tag code's cost (5, 7, 8, 9 check bits at 1, 2, 4, 8 tag bits, the "
    "fewest a linear code of minimum distance 6 admits) so that the full ladder is "
    "21.9 / 14.1 / 8.6 / 5.5% where the data code alone reads 12.5 / 7.0 / 3.9 / 2.1%; "
    "512 is declined as the smallest ladder step.\n\n"
    "**R-15-247a** MUST: native validity tags.\n"
    "· Accept: One validity bit per 64-bit granule is 15.6 MB per GB of data "
    "and about 47–70 MB of SRAM per GB; a 40 GB bulk tier would consume "
    "188–560% of a 0.5–1 GB first class; native tags cost 1.5625% plus that "
    "code, some 4.7–7.0% of the bulk array.\n")
_TAG_SPEC = (
    "# Specification\n\nThe granule is 15.6 MB per GB of data; "
    "the tag plane doubles to 1.56% of the array; "
    "the tag plane's ~1.56% share of the array.\n\n"
    "Sidecars cost about 47–70 MB of SRAM per GB, so a 40 GB bulk tier's sidecar would "
    "consume 188–560% of a 0.5–1 GB first class; native tags cost 1.5625% plus that "
    "code, some 4.7–7.0% of the bulk array.\n\n"
    "SECDED alone falls 12.5 → 7.0 → 3.9 → 2.1% across payloads of 64, 128, 256, and "
    "512 data bits, the tag code (5, 7, 8, and 9 check bits at 1, 2, 4, and 8 tag bits, "
    "the fewest a linear code of minimum distance 6 admits) aside. With it, total "
    "metadata per byte of data falls **21.9 → 14.1 → 8.6 → 5.5%**, and the step from "
    "128 to 256 is worth 5.5 points where the data code alone showed 3.1. The tag plane "
    "with its own code is 12 of the 22 at 256 and 9 of the 18 at 128.\n\n"
    "512 is not taken, its further 3.1 points being the smallest step on the ladder.\n")

# A width no code reaches, with every figure built on it consistent: a DECTED code of
# about 7 check bits over 4 tag bits and an implied 6 over 2, every total, share and
# band agreeing with them, so that nothing but the distance-6 floor can see that no code
# of that distance is so short.
_BELOW_FLOOR = [
    ("under a DECTED code of 8 check bits, the fewest any code of minimum distance 6 "
     "over 4 bits admits, for total metadata of some 22 bits per 256 data bits (8.6%), of "
     "which the tag plane with its own code is 12, some 4.7% of the payload; 128 bits (18 "
     "per 128, 14.1%, the tag plane with its code 9 of them at 7.0%)",
     "under a DECTED code of about 7 bits, for total metadata of some 21 bits per 256 data "
     "bits (8.2%), of which the tag plane with its own code is 11, some 4.3% of the "
     "payload; 128 bits (17 per 128, 13.3%, the tag plane with its code 8 of them at "
     "6.3%)"),
    ("about 47–70 MB", "about 43–63 MB"),
    ("consume 188–560%", "consume 172–504%"),
    ("some 4.7–7.0%", "some 4.3–6.3%"),
    ("12 of the 22 at 256 and 9 of the 18 at 128", "11 of the 21 at 256 and 8 of the 17 at 128"),
]


def _edited(edits: list[tuple[str, str]]) -> dict[str, str]:
    """Both tag fixtures with every edit made wherever it applies, and each edit made
    somewhere, so a fixture that drifted cannot turn a negative case into a no-op."""
    files: dict[str, str] = {REGISTER: _TAG_REGISTER, counts_tagplane.SPEC: _TAG_SPEC}
    for find, repl in edits:
        ensure(any(find in text for text in files.values()), f"no fixture carries {find!r}")
        files = {rel: text.replace(find, repl) for rel, text in files.items()}
    return files


def _tag_findings(files: dict[str, str]) -> list[str]:
    with sandbox_tree(files) as root:
        ctx = _context(root)
        counts_tagplane.tag_plane(ctx)
        return [line.strip() for line in ctx.rep.out if line.startswith("       ")]


def _context(root: Path, *, fix: bool = False) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root, corpus, read_register(corpus), read_artifacts(corpus),
                   Reporter(), fix=fix)


def _geometry(ctx: Context, *, block: int = 6, mismatch: bool = False,
              granule: int | None = 3, xlen: int | None = 64) -> None:
    declared = geometry.Geometry(
        sites={"model": block, "configuration": block + int(mismatch)},
        granule_exp=granule)
    widths = capformat.Format(defined={"xlen": xlen})
    with patch.object(geometry, "read", return_value=declared), \
            patch.object(capformat, "read", return_value=widths):
        counts_geometry.block_geometry(ctx)


def _candidate_calculation_without_numeric_prose() -> None:
    files = {REGISTER: _GEOMETRY_REGISTER, geometry.DOCUMENT: _CANDIDATES}
    with sandbox_tree(files) as root:
        ctx = _context(root)
        _geometry(ctx)
        ensure(ctx.rep.findings == 0, "a single candidate calculation suffices: "
               + "\n".join(ctx.rep.out))
        ensure(ctx.shared["block_candidates"] == 5,
               "the admissible set remains available to the owner floor")


def _candidate_repair_and_missing_calculation() -> None:
    stale = _CANDIDATES.replace("512 bytes", "1024 bytes").replace(
        "64 granules", "128 granules")
    with sandbox_tree({REGISTER: _GEOMETRY_REGISTER, geometry.DOCUMENT: stale}) as root:
        ctx = _context(root, fix=True)
        _geometry(ctx)
        ensure(ctx.rep.findings == 0 and ctx.text(geometry.DOCUMENT) == _CANDIDATES,
               "repair restores both units of the single candidate calculation")
        ensure((root / geometry.DOCUMENT).read_text(encoding="utf-8") == stale,
               "a rule fixture records repairs without writing its source document")
    with sandbox_tree({REGISTER: _GEOMETRY_REGISTER,
                       geometry.DOCUMENT: "See the normative bound.\n"}) as root:
        ctx = _context(root)
        _geometry(ctx)
        ensure(ctx.rep.findings > 0, "the retained calculation cannot disappear silently")


def _geometry_decisions_remain_guarded() -> None:
    with sandbox_tree({REGISTER: _GEOMETRY_REGISTER,
                       geometry.DOCUMENT: _CANDIDATES}) as root:
        variants: list[tuple[int, bool, int | None, int | None, str]] = [
            (6, True, 3, 64, "declarations must still agree"),
            (10, False, 3, 64, "an agreed value must still satisfy the candidate bounds"),
            (6, False, None, 64, "the granule source cannot be missing"),
            (6, False, 3, None, "the destination-width source cannot be missing"),
        ]
        for block, mismatch, granule, xlen, message in variants:
            ctx = _context(root)
            _geometry(ctx, block=block, mismatch=mismatch, granule=granule, xlen=xlen)
            ensure(ctx.rep.findings > 0, message)
    for register in (_GEOMETRY_REGISTER.replace("**512 bytes**", "**256 bytes**"),
                     _GEOMETRY_REGISTER.replace("data payload is 256", "payload omitted")):
        with sandbox_tree({REGISTER: register, geometry.DOCUMENT: _CANDIDATES}) as root:
            ctx = _context(root, fix=True)
            _geometry(ctx)
            ensure(ctx.rep.findings > 0 and REGISTER not in ctx.fixed,
                   "a wrong normative bound or missing payload is reported, not repaired")


def _tag_calculation_without_background_copies() -> None:
    files = {REGISTER: _TAG_REGISTER, counts_tagplane.SPEC: _TAG_SPEC}
    with sandbox_tree(files) as root:
        ctx = _context(root)
        counts_tagplane.tag_plane(ctx)
        ensure(ctx.rep.findings == 0, "canonical tag arithmetic needs no narrative copies: "
               + "\n".join(ctx.rep.out))
    for register in (_TAG_REGISTER.replace("**64-bit**", "width unstated"),
                     _TAG_REGISTER.replace("code is 12", "code is 13")):
        with sandbox_tree({REGISTER: register, counts_tagplane.SPEC: _TAG_SPEC}) as root:
            ctx = _context(root)
            counts_tagplane.tag_plane(ctx)
            ensure(ctx.rep.findings > 0,
                   "the canonical granule and code-inclusive share remain guarded")


def _impossible_width_is_refused_by_the_floor() -> None:
    """Consistent arithmetic over a width no code reaches.

    Every total, share and band agrees with the 7 and the implied 6, so a rule that held
    only the figures against each other passes them; what is asserted is that the floor,
    and nothing but the floor, reports both codewords.
    """
    found = _tag_findings(_edited(_BELOW_FLOOR))
    ensure(len(found) == 2 and all("below the" in f and "minimum distance 6" in f
                                   for f in found),
           "only the distance-6 floor refuses the width, at both codewords: "
           + "\n".join(found))
    ensure(any("7 check bits over 4 tag bits, below the 8" in f for f in found)
           and any("6 check bits over 2 tag bits, below the 7" in f for f in found),
           "the floor names the width it refuses and the floor it falls under: "
           + "\n".join(found))


def _code_inclusive_figures_remain_guarded() -> None:
    """Each figure built on the width, moved alone, is reported where it is stated."""
    variants: list[tuple[list[tuple[str, str]], str, str]] = [
        ([("about 47–70 MB of SRAM", "about 47–71 MB of SRAM")], "closes at 71",
         "the band's upper end is the fallback codeword's arithmetic"),
        ([("188–560%", "188–520%")], "high end",
         "the sidecar's upper end is the product of the figures beside it"),
        ([("21.9 / 14.1 / 8.6 / 5.5%", "21.9 / 14.1 / 8.6 / 5.3%")], "the full ladder",
         "a register ladder rung is extended Hamming plus tags plus the linear floor"),
        ([("**21.9 → 14.1 → 8.6 → 5.5%**", "**21.9 → 13.3 → 8.6 → 5.5%**")],
         "the full ladder", "the specification's bold ladder is held too"),
        ([("SECDED alone falls 12.5 → 7.0", "SECDED alone falls 12.5 → 7.1")],
         "the data code's ladder", "the data-code ladder is held in the specification"),
        ([("(5, 7, 8, 9 check bits", "(5, 6, 7, 8 check bits")], "linear code",
         "the per-rung list is the linear floor"),
        ([("worth 5.5 points", "worth 5.1 points")], "step from 128 to 256",
         "the specification's step is the difference of its rungs"),
        ([("further 3.1 points", "further 2.9 points")], "step onto 512",
         "the declined rung's step is the difference of its rungs"),
        ([("(18 per 128, 14.1%", "(17 per 128, 14.1%")], "fallback's metadata",
         "the fallback total is SECDED plus the plane"),
        ([("with 10 SECDED check bits", "with 9 SECDED check bits")], "extended Hamming",
         "the SECDED width is extended Hamming's over the payload"),
        ([("some 22 bits per 256 data bits (8.6%)", "some 22 bits per 256 data bits (8.5%)")],
         "total metadata as 8.5%", "the total's percentage is its quotient"),
        ([("12 of the 22 at 256", "12 of the 21 at 256")], "12 of the 21",
         "the specification's plane-of-total restates R-15-181a"),
        ([("DECTED code of 8 check bits", "DECTED code of 9 check bits"),
          ("code is 12, some 4.7%", "code is 13, some 5.1%"),
          ("some 22 bits per 256 data bits (8.6%)", "some 23 bits per 256 data bits (9.0%)")],
         "calls its 9 check bits the fewest",
         "a width above the floor may not be called the fewest"),
    ]
    for edits, needle, message in variants:
        found = _tag_findings(_edited(edits))
        ensure(any(needle in f for f in found), f"{message}: " + "\n".join(found))
    spec_copy = {REGISTER: _TAG_REGISTER,
                 counts_tagplane.SPEC: _TAG_SPEC.replace("a 40 GB bulk", "a 20 GB bulk")}
    found = _tag_findings(spec_copy)
    ensure(any("restates R-15-247a's bands" in f for f in found),
           "the specification's copy of the bands is held against the entry: "
           + "\n".join(found))
    untabled = {REGISTER: _TAG_REGISTER.replace("**64-bit**", "**16-bit**"),
                counts_tagplane.SPEC: _TAG_SPEC}
    found = _tag_findings(untabled)
    ensure(any("does not cover" in f for f in found),
           "a tag count outside the floor table fails closed: " + "\n".join(found))


def cases() -> list[Case]:
    return [
        Case("candidate-calculation-without-numeric-prose",
             _candidate_calculation_without_numeric_prose),
        Case("candidate-repair-and-missing-calculation",
             _candidate_repair_and_missing_calculation),
        Case("geometry-decisions-remain-guarded", _geometry_decisions_remain_guarded),
        Case("tag-calculation-without-background-copies",
             _tag_calculation_without_background_copies),
        Case("impossible-width-is-refused-by-the-floor",
             _impossible_width_is_refused_by_the_floor),
        Case("code-inclusive-figures-remain-guarded", _code_inclusive_figures_remain_guarded),
    ]
