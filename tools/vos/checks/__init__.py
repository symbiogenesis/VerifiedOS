# SPDX-License-Identifier: Apache-2.0
"""The checks, one module per rule group.

Each module owns one `=== group ===` heading of a run and the K- rules under it, and
each states in its own prose what the group decides and why that defect is worth a
tool. The order below is the order a run reports in, and it is a dependency order as
well: a group may read what an earlier one computed, through the `Context` every
group is handed, and never the other way round.

`generated` is first for that reason and not for prominence: it settles which bytes of
each generated artifact this run is about, and four rules in the counts group read the
model through one of them. A repair that landed after them would leave the same run
reporting counts taken from the defect it had just repaired.

One group is larger than one module, and the split is inside the group rather than a
second entry below: `counts` is entered at `counts.py`, which holds its claim table
and its run, and its families are the `counts_*.py` modules beside it, which nothing
outside that group imports. A rule belongs to the group whose heading reports it and
not to the file carrying it, which is what `check-rules.md` registers; the meta
group's scan reads every module in this directory, so a rule id in one of those
files is carried exactly as one in a group module is.

Adding a rule is three edits and no more: the check, its row in `check-rules.md`,
and its mutant in `vos/cli/selftest.py`. The meta group holds the first two in
agreement and the selftest holds the third, so none of them can be forgotten
quietly.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vos.corpus import Corpus
from vos.register import Artifacts, Register
from vos.report import Reporter

# The view table belongs to the views group, which this module imports below. Same
# guard as every group uses for `Context`, in the other direction.
if TYPE_CHECKING:
    from .views import View


@dataclass
class Context:
    """Everything a group reads, and the slate it writes its own results onto.

    The parsed artifacts are fixed for the run. The rest is what one group computes
    and a later one needs: the quantity table the counts group holds against the
    prose, the enumerations the floors group requires to be non-empty, and the
    pending rewrites `-Fix` flushes at the end.
    """

    root: Path
    corpus: Corpus
    reg: Register
    art: Artifacts
    rep: Reporter
    fix: bool = False

    # file -> its rewritten text, held until the run ends so that a later group reads
    # what an earlier one repaired rather than the text on disk
    fixed: dict[str, str] = field(default_factory=dict)

    # what later groups need from earlier ones
    q: dict[str, int] = field(default_factory=dict)          # quantity -> value
    # one registered figure claim: the document asserting it, the quantity it is a
    # count of, whether it is spelled in words or digits, and the pattern that finds
    # it. The floors group reads only the quantity, and reads it positionally.
    claims: list[tuple[str, str, str, str]] = field(default_factory=list)
    floors: dict[str, int] = field(default_factory=dict)     # enumeration -> its size
    views: list[View] = field(default_factory=list)
    # Everything a group leaves for a later one that has no shape worth naming.
    # `Any` is the honest type here and not a shortcut: the values are lists of four
    # different record types, and narrowing happens at each reader.
    shared: dict[str, Any] = field(default_factory=dict)

    def text(self, name: str) -> str:
        """A document's text as the run currently holds it, repaired or not."""
        if name in self.fixed:
            return self.fixed[name]
        doc = self.corpus.get(name)
        return doc.raw if doc else ""


# Below `Context` and not above it: every module named here reads `Context` from this
# one, so importing them any earlier would be a cycle through a name that does not
# exist yet.
from . import (  # noqa: E402
    bindings,
    compounds,
    confers,
    coread,
    costated,
    counts,
    differential,
    estimates,
    extraction,
    findings,
    floors,
    generated,
    glyphs,
    links,
    marks,
    meta,
    names,
    pins,
    ring,
    tables,
    traces,
    views,
)

GROUPS = [
    generated,
    ring,
    traces,
    coread,
    extraction,
    names,
    links,
    views,
    confers,
    bindings,
    counts,
    compounds,
    estimates,
    differential,
    findings,
    costated,
    tables,
    glyphs,
    marks,
    pins,
    floors,
    meta,
]
