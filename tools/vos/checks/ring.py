# SPDX-License-Identifier: Apache-2.0
"""ring: the generated interface artifact against the two owners it is a function of.

The typed IDL profile's rule is that the declaration is the one authored owner of
everything a composition fixes and the artifact is a function of that declaration and
of the register alone, so no hand edit of the artifact survives. That rule needs a
holder or it is a sentence: a generated Gallina file renders correctly, compiles, and
passes the proof gate whatever a person typed into it, and the two closed enumerations
it carries from the register are exactly the kind of transcription this repository
catches elsewhere by re-deriving rather than by comparing two copies.

**This rule re-runs the generator.** It does not compare the artifact against a
recorded digest, because a digest is a third copy of the same fact and goes stale in
the same edit; it emits the artifact again from `interfaces/ring-reference.json` and
from the register's own entry lines, and holds the working tree's bytes against what
came back. So a status added at R-12-093, a state reordered at R-12-094, a constant
moved in the declaration, and a token typed into the artifact by hand are one finding
each, at the gate the edit lands at.

**Why the generator rather than a second parse.** The emitter lives in
[vos/cli/ring.py](../cli/ring.py) and this rule imports it. Writing a checker-side
re-derivation would be the two-copies-of-one-parse defect these tools exist to catch,
in the tools, and it would decide agreement between two things this repository wrote
rather than between the artifact and its owners.

**Fail-closed, on the ground the generated group already states.** An artifact the git
index does not carry is outside the checker's corpus and every claim about it is
vacuous; an artifact absent from the working tree has no bytes to read; and a generator
that raises is an owner that no longer carries what the emitter reads out of it, which
is this rule's finding rather than this rule's crash. The third is caught on the
emitter's own refusal *and* on every other exception, because those are one fact
arriving twice: the emitter names in [vos/cli/ring.py](../cli/ring.py) every key it
reads and refuses on each, and an owner shaped in a way none of those guards reaches
would otherwise leave the whole run dead rather than one rule red.

**`--fix` does not repair it**, deliberately, and the ground is the one the co-read
ledger already states for blessing. The repair is `run.py ring emit`, which rewrites
the artifact from the owners; running it from inside the checker would let an edit to
the artifact be absorbed silently by the same wave that was supposed to report it, and
the interesting case is not the drift but which owner moved.

**K-99 is the other side of the same artifact and it is a different claim.** K-89 decides
that the artifact agrees with its *owners*, the declaration and the four register
entries the emitter reads, and that is the whole of what it decides: the emitter also
states the wire encoding, and where it takes that from is [the typed IDL
profile](../../../docs/idl-profile.md)'s §4, which is not an owner the emitter reads at
all. So a row edited in §4.2 moves neither side of K-89, and the drift is silent in both
directions. That gap is what that document's own *what nothing holds* section reported,
and this rule is the binding it said was owed.

**Three readings, and each is a different way for the two to part.** The **ladder** is
IDL-023's, a length form being one form, and the emitter writes it as a Gallina literal;
it is *recomputed* here from the rungs that entry states in its own words rather than
compared against a second copy, so a rung added to the profile and not to the emitter is
a finding at the edit that adds it. The **descriptor's members** are IDL-053's, which
names each member and the §4.2 row encoding it, and the emitter sums one term per member;
that pairing is held in both directions, so a member the profile gains and a row the
profile drops are each a finding. The **buffer reference's members** are `WF-11`'s own
row, which the emitter spends one declared encoding width on apiece.

**What the emitter is, and therefore which side is defective.** §4.3.6 makes the
artifact a function of the declaration and the register; §4.2 makes the *encoding* the
profile's. The emitter implements those rows and owns none of them, so where the two
disagree the repair is to the emitter, on the same terms as any derived view that
disagrees with the entry it derives from. Nothing here is rewritten under `--fix`
accordingly: which side moved is the fact worth having, exactly as it is one rule up.

**Fail-closed at every reading**, on K-67's and K-75's ground, which is why this rule
owes the floors group no member of its own: an absent profile, an IDL-023 whose rungs
this rule cannot read, a §4.2 carrying no row table, an IDL-053 it cannot find, and a
definition absent from the emitted text are each a finding rather than a comparison made
against nothing. An emitter that did not run is reported here as well as at K-89, and
that is one act priced at two lines on purpose: the two rules decide different things,
and a green line here over an artifact that was never emitted would be the false green
the second reading exists to prevent.

**What it does not read is declared rather than left to be met.** The completion's
members are R-12-093's, which the register owns and §4.2 does not place, so IDL-055
names no row for this rule to hold and the completion's encoded size is outside it.
And the direction a prose row cannot answer is stated too: a member *added* to `WF-11`'s
row is not caught, that row being one sentence rather than an enumeration with a shape,
where IDL-053's list of rows is read in both directions because each of its members
names a row id this rule can resolve.
"""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.cli import ring as emitter
from vos.corpus import staged_bytes

# `Context` lives in this package's __init__, which imports this module in turn.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== ring: the generated interface artifact against its owners ==="

REPAIR = "run.py ring emit"

PROFILE = "docs/idl-profile.md"

LADDER_ENTRY = "IDL-023"
DESCRIPTOR_ENTRY = "IDL-053"
BUFFER_ROW = "WF-11"

# The rungs, in the entry's own words, and the ceiling the criterion restates. Both are
# anchored on the sentence rather than on a number: a reworded entry is a finding here
# and never a reading that quietly stopped happening.
_RUNGS_RE = re.compile(r"the smallest of ([a-z]+(?:, [a-z]+)*,? or [a-z]+) bytes")
_CEILING_RE = re.compile(r"its ([a-z]+)-byte ceiling")

# A row of §4.2, by the id in its first cell.
_WF_ROW_RE = re.compile(r"(?m)^\| `(WF-\d+)` \|(.*)$")

# A row id a profile sentence names.
_WF_CITED_RE = re.compile(r"`(WF-\d+)`")

# The descriptor's members: the term the emitter spends on each, the words IDL-053
# spells that member with, and the §4.2 row that entry names for it. Held in both
# directions against the entry's own sentence, so a member added there with a row of its
# own is a finding rather than a member this table happens not to carry.
_DESCRIPTOR: tuple[tuple[str, str, str], ...] = (
    ("tag_width", "the operation tag", "WF-7"),
    ("enc_request_id_bytes", "the request identifier", "WF-1"),
    ("op_scalar_bytes", "the operation-specific scalars", "WF-1"),
    ("buffer_ref_bytes", "each buffer reference", "WF-11"),
    ("deadline_width", "the deadline", "WF-8"),
    ("enc_flag_set_bytes", "the flag set", "WF-10"),
)

# The buffer reference's members: the declared encoding width the emitter spends on each,
# and the words `WF-11`'s own row spells it with.
_BUFFER_REF: tuple[tuple[str, str], ...] = (
    ("enc_session_index_bytes", "session-table index"),
    ("enc_offset_bytes", "offset"),
    ("enc_length_bytes", "length"),
    ("enc_direction_bytes", "direction"),
    ("enc_content_type_bytes", "content type"),
)


def _entry_re(ident: str) -> re.Pattern[str]:
    """One entry of the profile, from its bold id to the blank line ending its block.

    The criterion and trace lines are read with the requirement rather than dropped,
    because IDL-023 states its rungs in the requirement and its ceiling in the
    criterion, and both are this rule's.
    """
    return re.compile(rf"(?s)\*\*{ident}\*\*[^*].*?(?=\n\n)")


def _definition(text: str, name: str) -> str | None:
    """A Gallina definition's body, whitespace-normalized, or None if it is not there.

    The terminator is a period at end of line, which the `Nat.leb` inside a body is
    not, so a definition spanning several lines comes back whole.
    """
    hit = re.search(rf"(?ms)^Definition\s+{re.escape(name)}\b[^\n]*?:=(.*?)\.$", text)
    return " ".join(hit.group(1).split()) if hit else None


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    findings: list[str] = []
    owners = 0
    try:
        wanted = emitter.emit(ctx.root, register=ctx.reg)
        owners = len(emitter.OWNED_ENTRIES)
    except emitter.RingError as exc:
        findings.append(f"{emitter.ARTIFACT} cannot be emitted: {exc}")
        wanted = None
    # The emitter's own refusal is above; this is the same fact arriving as any other
    # exception, which is what an owner shaped in a way no guard names looks like from
    # here. Both are this rule's finding, because a checker that dies on one owner
    # decides nothing about the rest of the run.
    except Exception as exc:
        findings.append(f"{emitter.ARTIFACT} cannot be emitted: the emitter raised "
                        f"{type(exc).__name__}: {exc}, so an owner no longer carries "
                        f"what it reads out of it in a shape any guard names")
        wanted = None

    if wanted is not None:
        if staged_bytes(ctx.root, emitter.ARTIFACT) is None:
            findings.append(
                f"{emitter.ARTIFACT} is generated by `{REPAIR}` and the git index does "
                f"not carry it, so nothing this checker decides about it means anything")
        else:
            path = ctx.root / emitter.ARTIFACT
            got = path.read_text(encoding="utf-8") if path.is_file() else None
            if got is None:
                findings.append(f"{emitter.ARTIFACT} is in the index and not in the "
                                f"working tree, so there is no artifact here to read")
            elif got != wanted:
                want_lines, got_lines = wanted.splitlines(), got.splitlines()
                where = next((i for i, (a, b) in enumerate(
                    zip(want_lines, got_lines, strict=False)) if a != b),
                    min(len(want_lines), len(got_lines)))
                findings.append(
                    f"{emitter.ARTIFACT}:{where + 1} is not what `{REPAIR}` writes from "
                    f"{emitter.DECLARATION} and the register; either an owner moved and "
                    f"the artifact was not regenerated, or the artifact was edited by "
                    f"hand")

    rep.report("K-89", "generated interface artifact(s) adrift from an owner:", findings,
               f"{emitter.ARTIFACT} is what `{REPAIR}` writes from "
               f"{emitter.DECLARATION} and the {owners} register entries it reads")
    _encoding(ctx, wanted)
    rep.line()


def _ladder(entry: str, emitted: str, findings: list[str]) -> None:
    """K-99's first reading: the emitter's width rule is the ladder IDL-023 states.

    The ladder is recomputed from the rungs rather than compared against a second copy
    of it, which is what makes a rung added to the profile a finding at the edit that
    adds it: a rung of `k` bytes holds every case count up to `2 ** (8 * k)`, the rungs
    below the top take an arm apiece, and the top rung is the ceiling and takes the
    `else`. The word-to-figure map is built from `figures.words`, so the spelling this
    reads is the one every other count word in this repository is written in.
    """
    numeral = {figures.words(n): n for n in range(1, 17)}
    # Every statement of the ladder and not the first, because that entry states it
    # twice, once of a length or count and once of a discriminant, and the second is the
    # one the emitter's `disc_width` implements. A rule reading one of them would leave
    # the other free to move with every gate green, which is the drift this rule exists
    # for arriving inside its own subject.
    said = _RUNGS_RE.findall(entry)
    if not said:
        findings.append(f"{PROFILE}'s {LADDER_ENTRY} no longer states its rungs as the "
                        "smallest of a list of byte widths, so the ladder the emitter "
                        "writes is held against nothing")
        return
    if len(set(said)) != 1:
        findings.append(f"{PROFILE}'s {LADDER_ENTRY} states "
                        f"{len(set(said))} different ladders, "
                        + " and ".join(f"'{one}'" for one in sorted(set(said)))
                        + "; a length form is one form, so the widths and the "
                        "discriminants climb one ladder or the entry disagrees with "
                        "itself")
        return

    words = [word.strip() for word in said[0].replace(", or ", ", ")
             .replace(" or ", ", ").split(",") if word.strip()]
    rungs = [numeral[word] for word in words if word in numeral]
    if len(rungs) != len(words) or len(rungs) < 2 or rungs != sorted(set(rungs)):
        findings.append(f"{PROFILE}'s {LADDER_ENTRY} states its rungs as "
                        f"'{said[0]}', which is not two or more ascending byte "
                        "widths this rule can read as a ladder")
        return

    ceiling = _CEILING_RE.search(entry)
    if ceiling is None:
        findings.append(f"{PROFILE}'s {LADDER_ENTRY} no longer restates its ceiling as "
                        "an n-byte ceiling, so the top of the ladder is stated once")
    elif ceiling.group(1) != figures.words(rungs[-1]):
        findings.append(f"{PROFILE}'s {LADDER_ENTRY} restates its ceiling as "
                        f"{ceiling.group(1)}-byte over a ladder whose top rung is "
                        f"{rungs[-1]}")

    want = "".join(f"if Nat.leb cases {2 ** (8 * rung)} then {rung} else "
                   for rung in rungs[:-1]) + str(rungs[-1])
    got = _definition(emitted, "disc_width")
    if got is None:
        findings.append(f"{emitter.ARTIFACT} states no disc_width in a form this rule "
                        f"reads, so {LADDER_ENTRY}'s ladder is held against nothing")
    elif got != want:
        findings.append(f"{emitter.ARTIFACT}'s disc_width is `{got}` where "
                        f"{LADDER_ENTRY}'s rungs give `{want}`; the profile owns the "
                        "ladder and the emitter implements it, so the repair is the "
                        "emitter's")


def _members(profile: str, emitted: str, findings: list[str]) -> None:
    """K-99's second and third readings: the encoded sizes against the rows placing them.

    Two pairings and they are not symmetrical, because their owners are not. IDL-053
    names its members *and* the row encoding each, so its row set is read in both
    directions and a member added there is a finding. `WF-11`'s row is one sentence
    naming what a data-plane resource reference carries, so what is held is that the
    emitter spends a declared width on each thing that sentence names.
    """
    rows = dict(_WF_ROW_RE.findall(profile))
    if not rows:
        findings.append(f"{PROFILE}'s §4.2 yields no row table this rule can read, so "
                        "no encoded size is held against a row at all")

    entry = _entry_re(DESCRIPTOR_ENTRY).search(profile)
    body = _definition(emitted, "descriptor_bytes")
    if entry is None:
        findings.append(f"{PROFILE} carries no {DESCRIPTOR_ENTRY} in a form this rule "
                        "reads, so the descriptor's members are held against nothing")
    elif body is None:
        findings.append(f"{emitter.ARTIFACT} states no descriptor_bytes in a form this "
                        "rule reads")
    else:
        said = entry.group(0)
        for term, member, row in _DESCRIPTOR:
            if term not in body:
                findings.append(f"{emitter.ARTIFACT}'s descriptor_bytes spends nothing "
                                f"on `{term}`, where {DESCRIPTOR_ENTRY} carries "
                                f"{member}")
            if member not in said:
                findings.append(f"{DESCRIPTOR_ENTRY} no longer carries {member}, which "
                                f"{emitter.ARTIFACT}'s descriptor_bytes encodes")
            if row not in said:
                findings.append(f"{DESCRIPTOR_ENTRY} no longer names `{row}` for "
                                f"{member}")
            elif rows and row not in rows:
                findings.append(f"{DESCRIPTOR_ENTRY} encodes {member} by `{row}`, which "
                                "§4.2 carries no row for")
        claimed = {row for _, _, row in _DESCRIPTOR}
        findings += [f"{DESCRIPTOR_ENTRY} names `{row}` and no member "
                     f"{emitter.ARTIFACT}'s descriptor_bytes encodes is placed by it"
                     for row in sorted(set(_WF_CITED_RE.findall(said)) - claimed)]

    body = _definition(emitted, "buffer_ref_bytes")
    row_text = rows.get(BUFFER_ROW)
    if row_text is None:
        if rows:
            findings.append(f"{PROFILE}'s §4.2 carries no `{BUFFER_ROW}` row, which is "
                            f"what {emitter.ARTIFACT}'s buffer_ref_bytes encodes")
    elif body is None:
        findings.append(f"{emitter.ARTIFACT} states no buffer_ref_bytes in a form this "
                        "rule reads")
    else:
        for term, member in _BUFFER_REF:
            if term not in body:
                findings.append(f"{emitter.ARTIFACT}'s buffer_ref_bytes spends nothing "
                                f"on `{term}`, where `{BUFFER_ROW}` carries the "
                                f"{member}")
            if member not in row_text:
                findings.append(f"§4.2's `{BUFFER_ROW}` row no longer carries the "
                                f"{member}, which {emitter.ARTIFACT}'s buffer_ref_bytes "
                                "spends a declared width on")


def _encoding(ctx: Context, emitted: str | None) -> None:
    """K-99: what the emitter states about the wire encoding, against §4 that states it.

    The emitted text is the run's own, so the artifact this reads is the one K-89 has
    just held against its owners rather than a second emission or a file on disk. An
    emitter that did not run is this rule's own fail-closed finding, named as such: K-89
    says why, and a green line here would claim agreement with §4.2 over nothing.
    """
    rep = ctx.rep
    findings: list[str] = []
    profile = ctx.text(PROFILE)

    if emitted is None:
        findings.append(f"{emitter.ARTIFACT} was not emitted at this gate, which K-89 "
                        "names, so nothing the emitter states about the encoding was "
                        "held against §4.2")
    if not profile:
        findings.append(f"{PROFILE} is not in the repository, so the rows the emitter "
                        "implements are held against nothing")

    if emitted is not None and profile:
        entry = _entry_re(LADDER_ENTRY).search(profile)
        if entry is None:
            findings.append(f"{PROFILE} carries no {LADDER_ENTRY} in a form this rule "
                            "reads, so the width ladder is held against nothing")
        else:
            _ladder(entry.group(0), emitted, findings)
        _members(profile, emitted, findings)

    rep.report("K-99", "statement(s) of the wire encoding the emitter and the profile "
               "disagree on:", findings,
               f"{emitter.ARTIFACT}'s width ladder is the one {LADDER_ENTRY}'s rungs "
               f"give, and its two encoded sizes spend one declared width on each of "
               f"{DESCRIPTOR_ENTRY}'s {len(_DESCRIPTOR)} descriptor members and each of "
               f"`{BUFFER_ROW}`'s {len(_BUFFER_REF)}")
