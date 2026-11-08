# SPDX-License-Identifier: Apache-2.0
"""extraction: check that every normative section of the specification is extracted in the register (K-62).

Compares the top-level `## <n>.` sections of [docs/spec.md](../../../docs/spec.md)
(excluding sections marked `non-normative` in their heading) against the `## §<n>`
sections of [docs/requirements-register.md](../../../docs/requirements-register.md) in
both directions, and verifies that each extracted section in the register contains at
least one requirement entry.
"""

import re
from typing import TYPE_CHECKING

from vos.corpus import PROSE
from vos.register import REGISTER

if TYPE_CHECKING:
    from . import Context

HEADING = "=== extraction: every normative section of the prose, in the register ==="

_PROSE_SECTION_RE = re.compile(r"## (\d+)\.[ \t]*(.*)")
_REGISTER_SECTION_RE = re.compile(r"## §(\d+)")
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
