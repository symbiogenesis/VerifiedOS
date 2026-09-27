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
    "**R-15-181a** IS: The ECC codeword's data payload is 256 bits, "
    "under a DECTED code of about 7 bits; the tag plane with its own code "
    "is 11, some 4.3% of the payload.\n\n"
    "**R-15-247a** MUST: native validity tags.\n"
    "· Accept: One validity bit per 64-bit granule is 15.6 MB per GB of data "
    "and about 43–63 MB of SRAM per GB; a 40 GB bulk tier would consume "
    "172–504% of a 0.5–1 GB first class; native tags cost 1.5625% plus that "
    "code, some 4.3–6.3% of the bulk array.\n")
_TAG_SPEC = (
    "# Specification\n\nThe granule is 15.6 MB per GB of data; "
    "native tags cost 1.5625% plus that code; "
    "the tag plane doubles to 1.56% of the array; "
    "the tag plane's ~1.56% share of the array.\n")


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
                     _TAG_REGISTER.replace("code is 11", "code is 12")):
        with sandbox_tree({REGISTER: register, counts_tagplane.SPEC: _TAG_SPEC}) as root:
            ctx = _context(root)
            counts_tagplane.tag_plane(ctx)
            ensure(ctx.rep.findings > 0,
                   "the canonical granule and code-inclusive share remain guarded")


def cases() -> list[Case]:
    return [
        Case("candidate-calculation-without-numeric-prose",
             _candidate_calculation_without_numeric_prose),
        Case("candidate-repair-and-missing-calculation",
             _candidate_repair_and_missing_calculation),
        Case("geometry-decisions-remain-guarded", _geometry_decisions_remain_guarded),
        Case("tag-calculation-without-background-copies",
             _tag_calculation_without_background_copies),
    ]
