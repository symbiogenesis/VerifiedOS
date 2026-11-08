# SPDX-License-Identifier: Apache-2.0
"""Check groups executed by [check.py](../../check.py#run).

Each module in `GROUPS` owns one `=== <group> ===` heading and the `K-nn` rules bound
to that group in [check-registry.json](../../check-registry.json). `GROUPS` is ordered by
data dependency: earlier groups populate [`Context`](#Context) fields (`fixed`, `q`,
`floors`, `views`, `shared`, `proof_reading`) read by later groups. In particular,
[`generated`](generated.py#run) runs first so downstream groups read the settled Sail
bundle and generated artifacts.

The [`counts`](counts.py#run) group delegates its metric families to the internal
`counts_*.py` helper modules in this package.

To add a rule, implement its check, declare its metadata in
[check-registry.json](../../check-registry.json), regenerate
[check-rules.md](../../check-rules.md), and add a mutant in
[vos/cli/selftest.py](../cli/selftest.py) (see
[tools/README.md](../../README.md#adding-a-rule-to-the-checker)).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vos import proofcites, timings
from vos.corpus import Corpus
from vos.register import Artifacts, Register
from vos.report import Reporter

if TYPE_CHECKING:
    from vos.checkregistry import Registry

    from .views import View


@dataclass
class Context:
    """Shared state and intermediate results passed across check groups in a single run."""

    root: Path
    corpus: Corpus
    reg: Register
    art: Artifacts
    rep: Reporter
    fix: bool = False
    clock: timings.Clock = field(default_factory=timings.Clock)
    registry: Registry | None = None
    registry_faults: list[str] = field(default_factory=list)
    group_start: int = 0
    group_findings: int = 0

    # Rewritten file texts held in memory so later groups read repaired content
    # before `--fix` flushes changes to disk at the end of the run.
    fixed: dict[str, str] = field(default_factory=dict)

    # Cross-group state populated by earlier groups and consumed by later ones.
    q: dict[str, int] = field(default_factory=dict)          # quantity -> value
    floors: dict[str, int] = field(default_factory=dict)     # enumeration -> its size
    views: list[View] = field(default_factory=list)
    shared: dict[str, Any] = field(default_factory=dict)
    proof_reading: proofcites.ParseCache = field(default_factory=proofcites.ParseCache)

    def text(self, name: str) -> str:
        """Return a document's current text, preferring any in-memory repair in `fixed`."""
        if name in self.fixed:
            return self.fixed[name]
        doc = self.corpus.get(name)
        return doc.raw if doc else ""


# Import check modules after defining `Context` to avoid circular-import errors.
from . import (  # noqa: E402
    bindings,
    citations,
    compounds,
    confers,
    consttab,
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
    headers,
    instructions,
    instruments,
    interims,
    keccak,
    ledger,
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
    keccak,
    consttab,
    citations,
    ledger,
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
    interims,
    headers,
    instruments,
    instructions,
    floors,
    meta,
]
