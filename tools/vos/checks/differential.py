"""differential: the corpus manifest, the document over it, and the programs.

The differential corpus is two artifacts with one membership. [the
manifest](../../../corpus/manifest.json) carries what has been measured about
each member; [the document](../../../docs/differential-corpus.md) carries what
each member exercises and how a member is written. Nothing appears in both, so
the failure to catch is not a disagreement in a restated fact but a **member in
one and not the other**: a program added to the corpus and never described, or
described and never added, and either way something a milestone's figure quietly
does not cover.

The second rule is the one that keeps the corpus honest rather than merely
listed. It assembles every member in this process, which is possible because the
assembler is Python and needs no toolchain (M0.12), and it holds each member's
recorded check count against the count its source actually carries. A program
that has stopped assembling is then a finding on the host, in the run a person
does before committing, rather than a surprise in WSL after a build.

What is *not* here is the trace digest, and that is a boundary rather than an
omission: reproducing it needs the emulator, so `model.py corpus` decides it and
this group only requires the field to be present. A rule that cannot recompute a
figure should not pretend to check it.
"""

import json

from .. import differential

HEADING = "=== differential: the corpus manifest, its document, and its programs ==="

DOC = "docs/differential-corpus.md"


def run(ctx) -> None:
    rep, root = ctx.rep, ctx.root
    rep.line(HEADING)

    try:
        corpus = differential.load(root)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        rep.report("K-50", "corpus manifest(s) unreadable:",
                   [f"{differential.CORPUS_DIR}/{differential.MANIFEST}: {exc}"],
                   "the corpus manifest parses")
        rep.report("K-51", "corpus member(s) that do not assemble:", [],
                   "no members to assemble")
        rep.line()
        return

    ctx.shared["corpus_members"] = corpus.members

    # Membership, both directions. The document names a member by linking its
    # source, which is the one spelling that cannot drift from the manifest's
    # while still resolving: the links group already holds the link itself.
    doc = ctx.text(DOC)
    described = {m.name for m in corpus.members
                 if f"(../{differential.CORPUS_DIR}/{m.source})" in doc}
    listed = {m.name for m in corpus.members}
    linked = _linked_sources(doc)
    gaps = [f"{name} is in the manifest and {DOC} does not carry it"
            for name in sorted(listed - described)]
    gaps += [f"{DOC} carries {source}, which the manifest does not list"
             for source in sorted(linked - {m.source for m in corpus.members})]
    rep.report("K-50", "corpus member(s) in one artifact and not the other:", gaps,
               f"all {len(corpus.members)} members are listed and described")

    # Every member assembles, and the checks it declares are the checks it has.
    from .. import asm

    faults = []
    for member in corpus.members:
        source = corpus.source(member)
        if not source.is_file():
            faults.append(f"{member.name}: {member.source} is not in the repository")
            continue
        text = source.read_text(encoding="utf-8")
        try:
            assembler = asm.Assembler(text, member.source)
            assembler.assemble()
        except Exception as exc:                       # an assembler diagnostic
            faults.append(f"{member.name}: {exc}")
            continue
        checks = differential.count_checks(text)
        if checks != member.checks:
            faults.append(f"{member.name}: the manifest records {member.checks} checks "
                          f"and the program carries {checks}")
        if not member.digest:
            faults.append(f"{member.name}: no commit-trace digest; run "
                          f"`model.py corpus --refresh`")
    rep.report("K-51", "corpus member(s) that do not assemble as recorded:", faults,
               f"all {len(corpus.members)} members assemble, with "
               f"{sum(m.checks for m in corpus.members)} checks and a recorded digest")
    rep.line()


def _linked_sources(doc: str) -> set[str]:
    prefix = f"(../{differential.CORPUS_DIR}/"
    found = set()
    at = doc.find(prefix)
    while at != -1:
        end = doc.find(")", at)
        if end != -1:
            found.add(doc[at + len(prefix):end])
        at = doc.find(prefix, at + 1)
    return {name for name in found if name.endswith(".s")}
