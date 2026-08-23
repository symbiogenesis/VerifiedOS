# SPDX-License-Identifier: Apache-2.0
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

The third rule is the derived-fact discipline pointed at the one thing the two
halves both commit to. `trace_schema` in the manifest and the version word in the
document's §4 heading are two statements of one grammar: a record type added or a
field widened advances both, and nothing owned the pair, so the manifest could
declare a grammar the document does not describe with every other rule green.
K-71 holds them equal and is fail-closed in the reading itself: a heading it
cannot parse in the form written today is a finding, never a pass over nothing.

The manifest's other number, the corpus **edition**, is deliberately not held
here, and the reason is the split the two halves are built on. The document says
what `version` *means* and never what it is; its only prose sites are completion
evidence frozen on checked milestones, which record what an edition measured at
its gate, so a rule holding the live manifest against them would be red the day
the edition advances, which is the day the corpus is working as designed. The
check the edition does want is that a refresh which moves a member advances it,
and that is `model.py corpus --refresh`'s to make, because it is the tool that
writes both fields.
"""

import json
import re
from typing import TYPE_CHECKING

from vos import asm, differential

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== differential: the corpus manifest, its document, and its programs ==="

DOC = "docs/differential-corpus.md"

# The document's §4 heading, which is the one place it writes the record grammar's
# version. The section number is a wildcard because renumbering the section is not
# this rule's subject; the version is captured alone, so a disagreement names the two
# figures and nothing else, and the spellings are compared rather than their values,
# so a padded or reformatted number is a finding rather than a silent equality.
_SCHEMA_HEADING_RE = re.compile(
    r"(?m)^## (\d+)\. The commit-trace schema, version (\d+)\s*$")


def run(ctx: Context) -> None:
    rep, root = ctx.rep, ctx.root
    rep.line(HEADING)

    try:
        corpus = differential.load(root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        # TypeError is a manifest whose members is not the list of row mappings the
        # parse iterates, which is as unreadable as a row missing a key
        rep.report("K-50", "corpus manifest(s) unreadable:",
                   [f"{differential.CORPUS_DIR}/{differential.MANIFEST}: {exc}"],
                   "the corpus manifest parses")
        rep.report("K-51", "corpus member(s) that do not assemble:", [],
                   "no members to assemble")
        # the manifest is the rule's other side, so an unreadable one is a finding
        # rather than a rule that quietly does not run
        _schema(ctx, None)
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
        except asm.AsmError as exc:
            # the assembler's own diagnostic and nothing broader: any other exception
            # is a defect in the checker, which crashes loudly rather than reading as
            # one more corpus finding
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

    _schema(ctx, corpus.trace_schema)
    rep.line()


def _schema(ctx: Context, declared: int | None) -> None:
    """K-71: the manifest's trace_schema is the version the document's §4 heading states.

    Fail-closed on the reading itself, in the shape K-67 uses over the tools' own
    pins: the manifest's field and the heading either answer in the form written
    today or are findings, so a reworded heading takes the comparison down loudly
    instead of leaving the rule green over a version nothing states.
    """
    rep = ctx.rep
    findings: list[str] = []
    manifest = f"{differential.CORPUS_DIR}/{differential.MANIFEST}"
    section, stated = "", ""

    if declared is None:
        findings.append(f"{manifest} does not state a trace_schema this rule can read")

    m = _SCHEMA_HEADING_RE.search(ctx.text(DOC))
    if m is None:
        findings.append(f"{DOC} no longer states the commit-trace schema's version in "
                        "its section heading, in a form this rule reads")
    else:
        section, stated = m.group(1), m.group(2)
        if declared is not None and stated != str(declared):
            findings.append(f"{DOC}'s §{section} heading states version {stated}, "
                            f"{manifest} declares trace_schema {declared}")

    rep.report("K-71", "commit-trace schema version(s) the document and the manifest "
               "disagree on:", findings,
               f"{DOC}'s §{section} heading states commit-trace schema version "
               f"{stated}, the grammar {manifest} declares")


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
