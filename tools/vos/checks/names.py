# SPDX-License-Identifier: Apache-2.0
"""names: every id a document uses, against the artifact that declares it.

Five vocabularies run across these documents: the register's R- requirements and its
CJ- crown-jewel targets, the absence contract's A- absences, and the coverage
matrix's B- boundaries and P- properties. Each is declared by exactly one artifact
and cited from everywhere, which makes a citation a derived fact of the coarsest
granularity, a whole id. Retire or renumber one and every sentence arguing from it
still reads, and argues from nothing. IDs are permanent here (a retired requirement
is struck, never reused), and that is what makes the check total rather than
advisory: a name either resolves to something live or is an error, with no third
case to adjudicate.
"""

import re

HEADING = "=== names: every id used, against the artifact that declares it ==="

# The character an id may not be preceded by, which is the left half of the boundary the
# citation must stand on. It is the same class the pattern below states on its right,
# spelled once here so the two halves cannot come to mean different things.
WORDISH = re.compile(r"[\w-]")


def run(ctx) -> None:
    rep, reg, art = ctx.rep, ctx.reg, ctx.art
    rep.line(HEADING)

    tally: dict[str, int] = {}
    for ident in reg.ids:
        tally[ident] = tally.get(ident, 0) + 1
    rep.report("K-10", "requirement id(s) the register declares twice:",
               [f"{k}, declared {n} times" for k, n in tally.items() if n > 1],
               f"all {len(reg.ids)} register ids are distinct")

    vocab = [
        ("requirement", r"R-\d\d-\d+[a-z]?", reg.ids, "the register"),
        ("crown-jewel target", r"CJ-[A-Z][A-Z-]*", reg.cj_targets, "the register's CJ- table"),
        ("absence", r"A-\d+", art.absence_ids, "docs/absence-contract.md"),
        ("boundary", r"B-\d+", art.cm_bounds, "docs/coverage-matrix.md"),
        ("property", r"P-\d+", art.cm_props, "docs/coverage-matrix.md"),
    ]

    # the five tokens start with five different letters, so one alternation walks the
    # corpus once and the first letter of each hit picks its vocabulary back out
    by_initial = {}
    unknown: dict[str, list[str]] = {}
    declared: dict[str, set[str]] = {}
    for kind, token, ids, home in vocab:
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
