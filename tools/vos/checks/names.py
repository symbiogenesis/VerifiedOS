# SPDX-License-Identifier: Apache-2.0
"""names: check identifier uniqueness and resolution across the document corpus (K-10, K-11).

- **K-10**: Every requirement ID in [docs/requirements-register.md](../../../docs/requirements-register.md)
  is declared at most once.
- **K-11**: Every unfenced citation of a requirement (`R-*`), crown-jewel target (`CJ-*`),
  hardware absence (`A-*` in [docs/hardware/absence-contract.md](../../../docs/hardware/absence-contract.md)),
  or coverage-matrix boundary (`B-*`) or property (`P-*` in
  [docs/assurance/coverage-matrix.md](../../../docs/assurance/coverage-matrix.md))
  resolves to a live declaration in its owning artifact.
"""

import re
from typing import TYPE_CHECKING

from vos.register import REQ_ID_PATTERN

if TYPE_CHECKING:
    from . import Context

HEADING = "=== names: every id used, against the artifact that declares it ==="

WORDISH = re.compile(r"[\w-]")


def run(ctx: Context) -> None:
    rep, reg, art = ctx.rep, ctx.reg, ctx.art
    rep.line(HEADING)

    tally: dict[str, int] = {}
    for ident in reg.ids:
        tally[ident] = tally.get(ident, 0) + 1
    rep.report("K-10", "requirement id(s) the register declares twice:",
               [f"{k}, declared {n} times" for k, n in tally.items() if n > 1],
               f"all {len(reg.ids)} register ids are distinct")

    vocab = [
        ("requirement", REQ_ID_PATTERN, reg.ids, "the register"),
        ("crown-jewel target", r"CJ-[A-Z][A-Z-]*", reg.cj_targets, "the register's CJ- table"),
        # the absence token carries the suffix for the same reason the requirement one
        # does: `A-12a` is an id, and a pattern stopping at the digits does not report
        # it as unknown but fails the right boundary and skips the citation entirely
        ("absence", r"A-\d+[a-z]?", art.absence_ids, "docs/hardware/absence-contract.md"),
        ("boundary", r"B-\d+", art.cm_bounds, "docs/assurance/coverage-matrix.md"),
        ("property", r"P-\d+", art.cm_props, "docs/assurance/coverage-matrix.md"),
    ]

    # the five tokens start with five different letters, so one alternation walks the
    # corpus once and the first letter of each hit picks its vocabulary back out; a
    # sixth vocabulary sharing an initial would silently reclassify every hit of the
    # earlier one, so the invariant is raised where the table is built rather than
    # left to a dict overwrite
    by_initial: dict[str, str] = {}
    unknown: dict[str, list[str]] = {}
    declared: dict[str, set[str]] = {}
    for kind, token, ids, _home in vocab:
        if token[0] in by_initial:
            raise RuntimeError(
                f"the {by_initial[token[0]]} and {kind} tokens share the initial "
                f"{token[0]!r}, and the dispatch below reads the first letter")
        by_initial[token[0]] = kind
        declared[kind] = set(ids)
        unknown[kind] = []

    # The five token shapes share no prefix, so the engine has no literal to pre-scan
    # for and must try each branch at every position. Stating the left boundary as a
    # leading lookbehind makes that worse rather than cheaper, because it is re-decided
    # at each of those positions: measured over this corpus it was four fifths of the
    # scan. So the pattern carries only its right boundary and the left one is decided
    # here, on the few thousand hits instead of on three million positions.
    #
    # The two agree, and not by coincidence: a hit this rejects is preceded by a word
    # character, and every character inside a token is one, so no citation can begin
    # inside a rejected hit and be skipped along with it.
    pattern = re.compile(
        r"(?:" + "|".join(token for _, token, _, _ in vocab) + r")(?![\w-])"
    )

    # a declared id is the overwhelming case and needs no line, so it is one set
    # lookup; only an unknown id pays for finding its line, and a fenced one names
    # nothing anyway
    for doc in ctx.corpus.docs:
        raw = doc.raw
        for m in pattern.finditer(raw):
            start = m.start()
            if start and WORDISH.match(raw, start - 1, start):
                continue                       # inside a longer word, so it cites nothing
            ident = m[0]
            kind = by_initial[ident[0]]
            if ident in declared[kind]:
                continue
            if doc.is_fenced(start):
                continue
            home = next(h for k, _, _, h in vocab if k == kind)
            unknown[kind].append(
                f"{doc.name}:{doc.at(start)} uses {ident}, which {home} does not declare"
            )

    for kind, _, _, home in vocab:
        rep.report("K-11", f"{kind} id(s) naming nothing:", unknown[kind],
                   f"every {kind} id used names one of the {len(declared[kind])} {home} declares")
    rep.line()
