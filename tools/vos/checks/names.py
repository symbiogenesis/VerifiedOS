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

    pattern = re.compile(
        r"(?<![\w-])(?:" + "|".join(token for _, token, _, _ in vocab) + r")(?![\w-])"
    )

    # a declared id is the overwhelming case and needs no line, so it is one set
    # lookup; only an unknown id pays for finding its line, and a fenced one names
    # nothing anyway
    for doc in ctx.corpus.docs:
        for m in pattern.finditer(doc.raw):
            kind = by_initial[m.group()[0]]
            if m.group() in declared[kind]:
                continue
            if doc.is_fenced(m.start()):
                continue
            home = next(h for k, _, _, h in vocab if k == kind)
            unknown[kind].append(
                f"{doc.name}:{doc.at(m.start())} uses {m.group()}, which {home} does not declare"
            )

    for kind, _, _, home in vocab:
        rep.report("K-11", f"{kind} id(s) naming nothing:", unknown[kind],
                   f"every {kind} id used names one of the {len(declared[kind])} {home} declares")
    rep.line()
