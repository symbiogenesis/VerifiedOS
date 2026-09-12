# SPDX-License-Identifier: Apache-2.0
"""Permanent requirement IDs across readers, references and repeated bookmarks.

The suffix may grow past one letter. Parsing only its prefix can merge acceptance
criteria into a neighbor, skip a dead citation, or detach repeated prose from its
entry. These fixtures distinguish those failures at the consuming interfaces.
"""

from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import coread, proofcites
from vos import corpus as corpus_mod
from vos.checks import Context, citations, names, traces
from vos.cli import selftest, view
from vos.corpus import PROSE
from vos.register import REGISTER, REQ_TOKEN_RE, read_artifacts, read_register
from vos.report import Reporter

_IDS = ["R-17-030", "R-17-030z", "R-17-030za", "R-17-030zab"]
_WORDS = ["base", "single", "double", "triple"]


def _fixture(spaced: bool = False) -> dict[str, str]:
    entries = [f"**{ident}** MUST hold the {word} obligation.\n"
               f"· Accept: {word} criterion.\n"
               f"· Fail-closed: {word} seam.\n"
               "· Trace: derived\n"
               for ident, word in zip(_IDS, _WORDS, strict=True)]
    prose = [f'{word} prose. <a id="{ident.lower()}"></a>\n'
             for ident, word in zip(_IDS, _WORDS, strict=True)]
    prose.append('double repeated. <a id="r-17-030za-2"></a>\n')
    return {REGISTER: "# Register\n\n## §17\n\n"
                     + ("\n" if spaced else "").join(entries),
            PROSE: "# Specification\n\n## 17. Fixture\n\n" + "\n".join(prose)}


def _context(root: Path) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root=root, corpus=corpus, reg=read_register(corpus),
                   art=read_artifacts(corpus), rep=Reporter(), fix=False)


def _tokens_are_complete() -> None:
    text = ", ".join(_IDS) + "; R-17-030za-2"
    expected = [*_IDS, "R-17-030za"]
    ensure(REQ_TOKEN_RE.findall(text) == expected,
           "alphabetic suffixes are part of the ID; numeric repeats are not")
    ensure(proofcites.ids(text) == expected,
           "proof citations must keep the complete requirement identity")


def _entry_and_coread_boundaries() -> None:
    # Adjacent headers deliberately carry no blank separator. A missed header
    # would append its criterion and conferral to the previously parsed entry.
    with sandbox_tree(_fixture()) as root:
        ctx = _context(root)
        ensure(ctx.reg.ids == _IDS, f"entry order/identity changed: {ctx.reg.ids!r}")
        pairs = coread.pairs(ctx.corpus, ctx.reg)
        for ident, word in zip(_IDS, _WORDS, strict=True):
            ensure(ctx.reg.accepts[ident] == 1,
                   f"{ident} must own only its own acceptance criterion")
            ensure(ctx.reg.accept_text[ident].strip() == f"· Accept: {word} criterion.",
                   f"the next header's criterion was absorbed into {ident}")
            prose, entry = pairs[ident]
            ensure(f"{word} prose." in prose and f"{word} criterion." in entry,
                   f"the co-read pair lost {ident}'s own statement")
            for other in set(_WORDS) - {word}:
                ensure(f"{other} prose." not in prose and f"{other} criterion." not in entry,
                       f"{ident} absorbed a neighbor's co-read material")
        ensure("double repeated." in pairs["R-17-030za"][0],
               "the numeric citation suffix must still join its multi-letter entry")
        ensure(coread.bookmarks(ctx.corpus, ctx.reg)["R-17-030za"]
               == ["r-17-030za", "r-17-030za-2"],
               "the base bookmark and its repeat are distinct sites of one ID")


def _names_resolve_complete_ids() -> None:
    files = _fixture()
    files["docs/references.md"] = "# References\n\n" + ", ".join(_IDS) + ".\n"
    with sandbox_tree(files) as root:
        ctx = _context(root)
        names.run(ctx)
        ensure(ctx.rep.findings == 0, f"live IDs failed: {ctx.rep.out!r}")
    files["docs/references.md"] += "R-17-030zz is absent.\n"
    with sandbox_tree(files) as root:
        ctx = _context(root)
        names.run(ctx)
        ensure(ctx.rep.findings == 1
               and any("uses R-17-030zz," in line for line in ctx.rep.out),
               f"a dead multi-letter ID must be reported whole: {ctx.rep.out!r}")


def _numeric_repeats_keep_their_requirement() -> None:
    files = _fixture()
    with sandbox_tree(files) as root:
        ctx = _context(root)
        traces.run(ctx)
        ensure(ctx.rep.findings == 0, f"live repeat did not resolve: {ctx.rep.out!r}")
    files[PROSE] += '\nOrphan. <a id="r-17-030zz-2"></a>\n'
    with sandbox_tree(files) as root:
        ctx = _context(root)
        traces.run(ctx)
        ensure(ctx.rep.findings == 1
               and any("#r-17-030zz-2: no requirement R-17-030zz " in line
                       for line in ctx.rep.out),
               f"a dead repeat must name its full missing base: {ctx.rep.out!r}")


def _proof_manifests_and_dead_citations() -> None:
    files = _fixture()
    manifest = (f"Owner: {REGISTER}\n"
                f"   Requirements: {' '.join(_IDS)}\n"
                f"   SHA256: {'0' * 64}\n")
    files["proofs/Fixture.v"] = (
        f"(* {' '.join(_IDS)}\n{proofcites.DERIVED_BEGIN}\n"
        f"{manifest}{proofcites.DERIVED_END}\n*)\nDefinition fixture := 0.\n")
    with sandbox_tree(files) as root:
        ctx = _context(root)
        citations.run(ctx)
        ensure(ctx.rep.findings == 0,
               f"multi-letter references must remain valid manifest data: {ctx.rep.out!r}")
    files["proofs/Fixture.v"] += "(* R-17-030zz *)\n"
    with sandbox_tree(files) as root:
        ctx = _context(root)
        citations.run(ctx)
        ensure(ctx.rep.findings == 1
               and any("cites R-17-030zz," in line for line in ctx.rep.out),
               f"authored dead references must survive manifest exclusion: {ctx.rep.out!r}")


def _view_places_complete_entries() -> None:
    with sandbox_tree(_fixture(spaced=True)) as root:
        lines, placed, homeless = view.weave(corpus_mod.load(root))
        ensure(placed == len(_IDS) and not homeless,
               f"multi-letter entries must have homes: {placed}, {homeless!r}")
        for ident, word in zip(_IDS, _WORDS, strict=True):
            ensure(lines.count(f"> **{ident}** MUST hold the {word} obligation.") == 1,
                   f"the complete block of {ident} must appear once")
        ensure(any("cited here again: R-17-030za," in line for line in lines),
               "a repeat must cite the full ID without reprinting its block")


def _mutations_preserve_only_the_own_id() -> None:
    line = "**R-17-030za** MUST join R-17-030zab and R-17-030z."
    ensure(selftest._keep_own_id(line)
           == "**R-17-030za** MUST join R-01-001 and R-01-001.",
           "the mutation must preserve the complete header and replace complete references")


def cases() -> list[Case]:
    return [
        Case("tokens-are-complete", _tokens_are_complete),
        Case("entry-and-coread-boundaries", _entry_and_coread_boundaries),
        Case("names-resolve-complete-ids", _names_resolve_complete_ids),
        Case("numeric-repeats-keep-their-requirement", _numeric_repeats_keep_their_requirement),
        Case("proof-manifests-and-dead-citations", _proof_manifests_and_dead_citations),
        Case("view-places-complete-entries", _view_places_complete_entries),
        Case("mutations-preserve-only-the-own-id", _mutations_preserve_only_the_own_id),
    ]
