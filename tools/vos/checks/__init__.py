# SPDX-License-Identifier: Apache-2.0
"""The checks, one module per rule group.

Each module owns one `=== group ===` heading of a run and the K- rules under it, and
each states in its own prose what the group decides and why that defect is worth a
tool. The order below is the order a run reports in, and it is a dependency order as
well: a group may read what an earlier one computed, through the `Context` every
group is handed, and never the other way round.

Adding a rule is three edits and no more: the check, its row in `check-rules.md`,
and its mutant in `check-selftest.py`. The meta group holds the first two in
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
    banks,
    bindings,
    compounds,
    confers,
    counts,
    differential,
    estimates,
    floors,
    glyphs,
    links,
    marks,
    meta,
    names,
    tables,
    traces,
    views,
)

GROUPS = [
    traces,
    names,
    links,
    views,
    confers,
    bindings,
    counts,
    compounds,
    estimates,
    differential,
    banks,
    tables,
    glyphs,
    marks,
    floors,
    meta,
]
