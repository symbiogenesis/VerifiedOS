# SPDX-License-Identifier: Apache-2.0
"""extraction: every normative section of the prose, extracted by the register.

The register opens by asserting that **all eighteen normative sections are extracted**,
and the counts group holds that figure the way it holds every other: by recomputing it.
What it recomputes it from is `len(reg.per_section)`, the number of `## §n` sections the
register itself carries. So the figure is arithmetic over the register alone, and the
claim it discharges is *the register has eighteen sections*, which is not the claim the
sentence makes. Whether eighteen is **all** of them is a fact about the prose, and
nothing read it.

The gap is not hypothetical and was not reasoned about: a normative `## 20.` seeded into
the prose, extracted by nothing, leaves a run green. Every other rule looks past it. The
traces group decides bookmarks, and an unextracted section declares none; the coread
group decides pairs, and an unextracted section is in no pair; the links group decides
that a `§n` a sentence names is numbered by some heading, which this one is. A whole
section of obligations can enter the specification and the tool will say that every
derived fact agrees with its artifact.

So this group holds the two section sets against each other, in both directions, and
requires each register section to carry an entry: a section extracted into no
requirement is not extracted, it is a heading. The reverse direction is the one that
costs nothing today and is the reason the rule exists, exactly as it is for the views
group, where the omission a hand-maintained extraction makes is silent in precisely this
direction.

**Normativity is read off the heading rather than from a list here.** The prose marks
its one non-normative section in the heading text (§19, *Evaluated Architectural
Alternatives (non-normative)*), and the register's own coverage note says so beside the
count. Reading the document's own declaration is what keeps this rule from carrying a
skip list, which would be a proviso needing its own audit and would silently exempt the
next section somebody added to it, the failure marks.py states for file kinds.

What this cannot decide is whether a section's *contents* are fully extracted, which is
the extraction-defect residue R-05-153 books and R-05-150's gate asks. This is the
coarsest granularity of that question and the only one a machine can answer: a section
present in one document and absent from the other. An entry-by-entry sweep of a
section's obligations remains a reading, and the register declines to call its own empty
defect list a clean bill for the same reason.
"""

import re
from typing import TYPE_CHECKING

from vos.corpus import PROSE
from vos.register import REGISTER

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== extraction: every normative section of the prose, in the register ==="

# The prose numbers a section and titles it on one line; the register numbers the same
# section with a section sign. Both are matched against a line rather than scanned over
# the whole text, for the reason corpus.py states once for every rule that walks lines.
_PROSE_SECTION_RE = re.compile(r"## (\d+)\.[ \t]*(.*)")
_REGISTER_SECTION_RE = re.compile(r"## §(\d+)")

# The prose's own marker for a section that states no obligation. Read from the heading
# rather than kept as a list of excused numbers: a list would need auditing itself, and
# would exempt whatever was added to it.
_NON_NORMATIVE = "non-normative"


def run(ctx: Context) -> None:
    rep, reg, corpus = ctx.rep, ctx.reg, ctx.corpus
    rep.line(HEADING)

    prose = corpus.get(PROSE)
    if prose is None or REGISTER not in corpus:
        rep.report("K-62", "missing artifact:",
                   [f"{PROSE if prose is None else REGISTER} is not in the repository"])
        rep.line()
        return

    normative: dict[str, str] = {}   # section number -> its title
    excused: list[str] = []
    for _, m in prose.unfenced("## ", _PROSE_SECTION_RE):
        number, title = m.group(1), m.group(2).strip()
        if _NON_NORMATIVE in title.lower():
            excused.append(number)
        else:
            normative[number] = title

    findings = [
        f"§{n} of the prose, '{title}', states obligations and the register carries no "
        f"§{n}; a section extracted by nothing is the coarsest extraction defect"
        for n, title in normative.items() if n not in reg.per_section
    ]
    findings += [
        f"the register carries §{n} and the prose numbers no normative section {n}"
        for n in reg.per_section if n not in normative
    ]
    # A section heading with no entry beneath it is an extraction that decided nothing,
    # and it reads from the count exactly as a full one does.
    findings += [
        f"the register's §{n} carries no requirement, so it is a heading rather than "
        f"an extraction"
        for n, count in reg.per_section.items() if n in normative and not count
    ]

    rep.report("K-62", "section(s) the prose and the register disagree on:", findings,
               f"all {len(normative)} normative sections of the prose are extracted, "
               f"and no register section stands over the {len(excused)} the prose "
               f"marks non-normative")
    rep.line()
