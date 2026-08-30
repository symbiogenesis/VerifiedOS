# SPDX-License-Identifier: Apache-2.0
"""generated: every artifact a generator owns, against the generator and the owner.

A generated artifact is one no person may edit, because its content is a function of
something else in the repository. Until this group there were none: every fact the
model determined and a tool needed was re-derived by a regex written beside the tool,
which is the two-copies-of-one-parse defect this repository exists to catch, sitting in
the checker. The model already emitted a machine-readable bundle of itself on the way to
every other artifact and nothing read it.

Tracking that bundle buys the parses their owner and owes one rule in exchange, and the
rule is the load-bearing part rather than the artifact: a generated file nobody holds is
a file somebody edits, and the edit renders correctly, survives review, and silently
changes what four rules downstream decide.

## The claim, and the two lanes it is decided on

**The claim is one sentence: every artifact the table below names is byte-identical to
what its generator emits from its owners.** Neither lane can decide the whole of it, and
the split is a property of the machine rather than a weakening of the claim.

`check.py` runs on the Windows host, where there is no Sail, so the emitter for the one
row here **cannot run at this gate at all**. What the host can decide, it decides, and
what it cannot it names in its own `ok` line rather than passing over:

- **the artifact against the index.** The index is what this repository has been told
  the generator last emitted, and what review last saw, so a working tree that has
  drifted from it is a hand edit, which is the defect. It is the half `--fix` repairs,
  writing the staged bytes back. What every *other* rule reads is still the working
  tree's copy, on the same ground the corpus reads a document rather than its blob: the
  index says what is tracked and the file says what it says.
- **the artifact against its own owners.** The bundle records the md5 of all 158 files
  the emitter read, so the staleness question, *does this artifact still describe the
  model beside it*, is answered out of the artifact with no second list to maintain and
  no Sail to run. A curated source edited without a regeneration is caught here, on the
  host, at the gate the edit lands at.
- **the artifact against the layout it was emitted under**, which is the precondition
  [vos/sailbundle.py](../sailbundle.py) states and fails closed on.

What is left is exactly one question: *would Sail, run now, write these bytes?* That is
`run.py model bundle --check` and it runs in the guest, on the evidence sweep's path
rather than at every landing. It is named in the `ok` line, so a green K-88 says which
half it decided and never claims the other.

**Why not simply make the checker run the generator.** Two reasons, and both are
disqualifying on their own. The host has no Sail, so a rule that ran the generator would
be red on the machine this repository is edited from, which is a rule that gets turned
off rather than a rule that bites. And re-launching into the guest would put a 40-second
Sail run and a WSL dependency inside a three-gate wave that answers in 24 seconds, for a
question that changes only when the model does. What makes the split honest is that the
host's half is not vacuous: it catches the hand edit and it catches the stale artifact,
which are the two ways a generated file goes wrong in practice.

## Fail-closed, on K-67's and K-75's ground

Three states are findings rather than passes, each named where it is met: an empty
table, because a rule quantified over nothing reports agreement about nothing; a row
whose path the git index does not carry, because an untracked generated artifact is
outside the checker's corpus and every claim about it is vacuous; and a generator that
raises, which on this lane is the artifact refusing to parse as the schema its reader
was written against. The owner reading owes the floors group its own member count for
the same reason, so that the day the emitter stops recording what it read is the day
this says so rather than the day it starts agreeing with everything.

## Where this group sits, and why it is first

First in `GROUPS`, ahead of the counts group, because the artifact it holds is an
*input* to four rules downstream: the capability format, the block geometry, the
core-class table and the decode surface are all read out of the bundle now. A repair
that landed after them would leave the same run reporting counts taken from the defect
it had just repaired, so the bundle this group settles on is what it hands forward in
`ctx.shared`, repaired or not. That is the same ordering `--fix` already reserves one
level up, where the repair runs alone and before the rest of the wave.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vos import corpus as corpus_mod
from vos import sailbundle

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== generated: every generated artifact against its generator and its owner ==="


@dataclass(frozen=True)
class Row:
    """One generated artifact: what it is, what writes it, and what it is written from.

    `lane` is the whole of what makes this table honest on two machines. A `host` row's
    generator can be run at this gate and its byte identity is decided here outright; a
    `guest` row's cannot, so this gate decides the index and the owners and names the
    command that decides the rest. A row is never silently skipped for its lane.
    """

    path: str
    generator: str
    lane: str
    owners: str
    checker: str


# The generated artifacts, one row each. Adding one is a row here and nothing else: the
# reading below is over the table rather than over any particular member of it.
GENERATED: tuple[Row, ...] = (
    Row(path=sailbundle.BUNDLE,
        generator="run.py model bundle",
        lane="guest",
        owners="the curated Sail sources and the pinned Sail library",
        checker="run.py model bundle --check"),
)


def paths() -> frozenset[str]:
    """Every generated artifact's path, for the rules whose subject is what a person
    wrote. A machine-written file restates nothing: its content is a function of its
    owners, so a token inside one that *looks* like a transcription is not one and there
    is no edit a finding could ask for."""
    return frozenset(row.path for row in GENERATED)


@dataclass
class Reading:
    """What one row decided, kept apart from how it is worded.

    The bundle comes back with it because the group after this one reads the same
    artifact: settling which bytes are authoritative is this rule's, and reading a
    second copy off disk to answer a count would be the defect one file over.
    """

    findings: list[str]
    fixed: list[str]
    owners: int = 0
    bundle: sailbundle.Bundle | None = None


def _digest(path: Path) -> str | None:
    """One file's md5, or `None` where it is not there. md5 because that is what the
    emitter records; the question is agreement with the artifact's own record and not
    the strength of the digest, and choosing a different one would mean recomputing
    what Sail wrote rather than reading it."""
    try:
        return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
    except OSError:
        return None


def _owners(ctx: Context, row: Row, bundle: sailbundle.Bundle) -> tuple[int, list[str]]:
    """The artifact's own record of what it was emitted from, against this checkout.

    Both halves of the record are read and they are read differently, because they are
    different facts. The in-tree sources are here, so each is hashed and held against
    what the artifact says it was hashed at. The library's are not, so what is held is
    the precondition: `library_owners` raises on a key outside the pinned root, and that
    raise is this rule's finding rather than this rule's crash.
    """
    findings: list[str] = []
    for rel, recorded in sorted(bundle.owners().items()):
        got = _digest(ctx.root / rel)
        if got is None:
            findings.append(f"{row.path} was emitted from {rel}, which this checkout "
                            f"does not carry; regenerate it with `{row.generator}`")
        elif got != recorded:
            findings.append(f"{row.path} records {rel} at {recorded} and the file in "
                            f"this checkout hashes {got}, so the artifact describes a "
                            f"model that has moved; regenerate it with "
                            f"`{row.generator}`")
    return len(bundle.owners()) + len(bundle.library_owners()), findings


def _row(ctx: Context, row: Row) -> Reading:
    """One row of the table, decided as far as this lane can decide it.

    **The artifact handed forward is the working tree's**, which is the same choice the
    corpus makes about every document it reads: the index says what is *tracked* and the
    working tree says what it *says*, so the checker decides about the tree as it stands
    and a rule downstream reports about the file a person is looking at. The index is
    read for the one question it owns, whether the artifact has drifted from the bytes
    the generator last wrote, and for the repair that answers it.

    The one exception is that repair, and it is the reason this group runs first: where
    `--fix` writes the staged bytes back, what goes forward is what the run just wrote,
    so the same run does not report counts taken from the defect it has repaired.
    """
    out = Reading(findings=[], fixed=[])
    staged = corpus_mod.staged_bytes(ctx.root, row.path)
    if staged is None:
        out.findings.append(
            f"{row.path} is generated by `{row.generator}` and the git index does not "
            f"carry it, so nothing this checker decides about it means anything")
        return out

    on_disk = ctx.root / row.path
    working = on_disk.read_bytes() if on_disk.is_file() else None
    if working is None:
        out.findings.append(f"{row.path} is in the index and not in the working tree, "
                            f"so there is no artifact here to read")
        return out

    try:
        held = sailbundle.Bundle(_json(working), row.path)
    except sailbundle.BundleError as exc:
        out.findings.append(f"{row.path} is not readable: {exc}")
        return out

    out.owners, owner_findings = _owners(ctx, row, held)
    out.findings += owner_findings
    out.bundle = held

    if working != staged:
        where = next((i for i, (a, b) in enumerate(zip(staged, working, strict=False))
                      if a != b), min(len(staged), len(working)))
        line = staged.count(b"\n", 0, where) + 1
        out.findings.append(
            f"{row.path} is generated by `{row.generator}` and the working tree "
            f"differs from the index at line {line}, byte {where} of "
            f"{len(staged)}: a generated artifact is not edited by hand")
        _repair(ctx, row, staged, out)
    return out


def _repair(ctx: Context, row: Row, staged: bytes, out: Reading) -> None:
    """Write the staged bytes back, where the staged bytes are still the model's.

    Guarded rather than unconditional, because restoring a stale blob over a fresh
    regeneration would be the repair undoing the generator. So the index's own copy is
    parsed and held against the sources *it* records, and where that disagrees this
    reports and rewrites nothing: the repair for a stale artifact is the emitter's, and
    the emitter is not on this lane.
    """
    if not ctx.fix:
        return
    try:
        indexed = sailbundle.Bundle(_json(staged), row.path)
    except sailbundle.BundleError as exc:
        out.findings.append(f"the index's {row.path} is not readable either, so there "
                            f"are no generated bytes to restore: {exc}")
        return
    owners, stale = _owners(ctx, row, indexed)
    if stale:
        out.findings.append(
            f"the index's {row.path} is itself stale against the sources it records, so "
            f"restoring it would be this repair undoing the generator; regenerate it "
            f"with `{row.generator}`")
        return
    ctx.fixed[row.path] = staged.decode("utf-8")
    # what goes forward is what this run has just written, which is the whole of why
    # this group runs ahead of the ones that read the artifact
    out.bundle, out.owners = indexed, owners
    out.fixed.append(f"fixed: {row.path} restored from the index, "
                     f"{len(staged)} bytes")


def _json(raw: bytes) -> dict[str, Any]:
    """The staged blob as the mapping a bundle is, raising the reader's own error where
    it is not. Written here rather than in `sailbundle.load` because that one opens a
    path and this one is handed bytes git produced."""
    try:
        got = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise sailbundle.BundleError(f"the staged blob is not JSON: {exc}") from exc
    if not isinstance(got, dict):
        raise sailbundle.BundleError(
            f"the staged blob is a {type(got).__name__} and not a bundle")
    return got


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    findings: list[str] = []
    fixed: list[str] = []
    owners = 0
    if not GENERATED:
        findings.append("the generated-artifact table is empty, so this rule holds "
                        "nothing; a rule quantified over no members reports agreement "
                        "about nothing")
    for row in GENERATED:
        reading = _row(ctx, row)
        findings += reading.findings
        fixed += reading.fixed
        owners += reading.owners
        if row.path == sailbundle.BUNDLE and reading.bundle is not None:
            ctx.shared["bundle"] = reading.bundle

    ctx.shared["bundle_owners"] = owners
    guest = ", ".join(sorted({r.checker for r in GENERATED if r.lane == "guest"}))
    rep.report(
        "K-88", "generated artifact(s) that are not what their generator wrote:",
        findings,
        f"all {len(GENERATED)} generated artifact(s) are the bytes the index holds for "
        f"them and record {owners} owner(s) this checkout still hashes to; the emitter "
        f"itself is not on this lane, so `{guest}` is what holds them against Sail")
    for line in fixed:
        rep.line(line)
    rep.line()
