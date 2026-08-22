# SPDX-License-Identifier: Apache-2.0
"""The decode surface: the names the curated model spells, and the names it can emit.

The surface has two halves and neither one is the whole of it. The Sail model decodes
a word and spells the result, which is what `mapping clause assembly` is; the corpus
assembler encodes a name into a word, which is what [dialect.py](dialect.py)'s table
is. A form removed from one and left in the other is still reachable: a program the
assembler will lay down that the model refuses is a corpus that cannot run, and a form
the model still decodes with no encoder row is a surface no test can reach but an
implementation still carries. So both halves are read here, together, and a rule over
them names which half it found something in.

The two are also parsed differently because they are written differently, and the
difference is the reason this module is a parse rather than a pattern at a call site.
`dialect.MNEMONICS` is a tuple of finished names, so a name matches it or does not.
A Sail assembly clause is a **concatenation**, and the mnemonic is assembled at run
time out of literals and mappings:

    mapping clause assembly = VLSEGFFTYPE(nf, vm, rs1, width, vd)
      <-> "vl" ^ nfields_string(nf) ^ "e" ^ vlewidth_bitsnumberstr(width) ^ "ff.v" ^ ...

so `vle8ff.v` and `vlseg2e16ff.v` are two spellings of one clause and neither appears
in the file. What does appear is the clause's **skeleton**: its string literals in
order, `vleff.v` here, with everything a mapping decides left out. A name written with
its variable parts marked, which is how a document states a family of encodings, is
matched against that skeleton by asking whether the name's own literal fragments occur
in it in order.

**The direction of that test is the whole of its precision, and the other direction
does not work.** Asking whether the *skeleton's* fragments occur in the *name* pairs
`vlseg<nf>e<eew>ff.v` with `VLSEGTYPE` (skeleton `vle.v`, fragments `vl`, `e`, `.v`,
all three of which occur in that order in the name) and so cannot tell the excluded
fault-only-first load from the ordinary segment load beside it. Asking whether the
*name's* fragments occur in the *skeleton* separates them, because `ff.v` is a literal
of the one clause and of no other: over the profile's whole exclusion table the test
pairs one name with one clause.

**A skeleton is a lower bound, and where the document can name the constructor
instead there is no bound to take.** `amocas.q` is spelled by a clause whose whole
mnemonic is `amo_mnemonic(op) ^ "." ^ width_mnemonic_wide(width)`, three mappings and
one dot: the skeleton is `.`, no fragment of the written name occurs in it, and the
test above pairs that name with nothing. So a document whose subject is a *single
instruction form* names the Sail constructor beside the mnemonic, and the reading it
asks for is not a match at all but membership: `read_decoded` below collects the
names a word can decode *to*, and a marker is in that set or is not. That reaches
the clauses the skeleton parse drops, and it reaches a form whose constructor is
shared with its neighbours and whose identity is a field value, which `AMOCAS` is: the
model decodes `AMO`, and `AMOCAS` is the `amoop` its five-bit field decodes to.

Both readings of the Sail side stand, because they fail differently. A skeleton
cannot see a mnemonic built inside a mapping; a marker cannot see a form re-added
under another constructor, and a marker that was misspelled or has gone stale is
absent for the same reason a deleted form is. Neither is the other's replacement.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from . import dialect

SAIL_SUFFIX = ".sail"

# The clause head is anchored at column zero because a Sail top-level declaration is,
# and the body runs to the next one. The argument list is stepped over by hand rather
# than matched, because it nests.
_ASSEMBLY_RE = re.compile(r"^mapping clause assembly\s*=\s*(\w+)", re.MULTILINE)

# One term of a right-hand side: a string literal, a call, or a bare name. The call
# alternative comes before the bare name so that `f(x)` is one term and not two.
_TERM_RE = re.compile(r'"([^"]*)"|[A-Za-z_]\w*\s*\([^()]*\)|[A-Za-z_]\w*')

# The call every assembly clause puts between the mnemonic and its first operand. A
# clause without one spells a mnemonic and nothing else.
_OPERAND_SEP = "spc()"

# The two shapes a decode site takes, both anchored at column zero because a Sail
# top-level declaration is. A clause head names an instruction constructor; a named
# `encdec` mapping decodes one field of one, and its arms name that field's values.
_DECODE_CLAUSE_RE = re.compile(r"^mapping clause (encdec\w*)\s*=\s*(\w+)", re.MULTILINE)
_DECODE_MAPPING_RE = re.compile(r"^mapping (encdec\w*)\s*:", re.MULTILINE)

# Where a mapping's body starts: the assignment that ends its signature, and never the
# first brace, because a signature carries its own (`bits(5) <-> {1, 2, 4, 8}`).
_BODY_RE = re.compile(r"=\s*\{")

# One arm's name, on each side of its arrow: an identifier, with an argument list
# stepped over where the arm destructures one (`Regidx(r) <-> r`). Which side of the
# arrow the encoding is on is the mapping's own choice, so both sides are read; a
# numeric side matches neither pattern, which is what leaves `1 <-> 0b00` naming
# nothing at all.
_ARM_LEFT_RE = re.compile(r"([A-Za-z_]\w*)\s*(?:\([^()]*\))?\s*$")
_ARM_RIGHT_RE = re.compile(r"\s*([A-Za-z_]\w*)")

# How far back of an arrow the arm's own name can be. Generous against the longest
# destructuring the model writes, and bounded so that the backward scan costs the same
# whether the arm is the mapping's first or its hundredth.
_ARM_WINDOW = 120

# What a document writes where an encoding family varies: `<eew>` names the field,
# `*` stands for the rest of a family's names. Both mean *some text decided
# elsewhere*, which is exactly what a mapping in a Sail clause is.
_PLACEHOLDER_RE = re.compile(r"<[^>]*>|\*")

# What a placeholder can expand to in a finished mnemonic. Deliberately not `.*`: a
# placeholder stands for a field's rendering, so it is at least one character and
# never spans the separator or the suffix dot that the literals around it anchor.
_PLACEHOLDER_EXPANSION = r"[0-9a-z]+"


@dataclass(frozen=True)
class Spelling:
    """One `mapping clause assembly`, reduced to what it can be asked about."""

    ctor: str        # the instruction-union constructor the clause spells
    file: str        # the tracked path it is written in
    line: int        # its 1-based line, for a finding a person has to go and visit
    skeleton: str    # its mnemonic's string literals, concatenated in order


def _balanced(text: str, start: int) -> int:
    """The offset just past the parenthesized group at `start`, or `start` itself.

    A Sail argument list nests, so it is stepped over rather than matched: the
    pattern that would do it is the one this exists to avoid writing.
    """
    if start >= len(text) or text[start] != "(":
        return start
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return start


def _skeleton(rhs: str) -> str:
    """A right-hand side's mnemonic, as its string literals in order.

    Everything a mapping or a function decides is left out rather than guessed at,
    so the result is a *lower bound* on what the clause spells and never a claim
    about the characters between its literals.
    """
    cut = rhs.find(_OPERAND_SEP)
    head = rhs[:cut] if cut >= 0 else rhs
    return "".join(m.group(1) for m in _TERM_RE.finditer(head)
                   if m.group(1) is not None)


def read_spellings(root: Path, tracked: list[str]) -> list[Spelling]:
    """Every assembly clause of every tracked Sail file, as a skeleton.

    A clause whose mnemonic is decided entirely by a mapping has an empty skeleton
    and is dropped, because a name matches an empty skeleton vacuously. Those are
    the clauses this parse cannot speak about, and a rule reading it owes that
    boundary out loud rather than counting them as checked.
    """
    out: list[Spelling] = []
    for rel in tracked:
        if not rel.endswith(SAIL_SUFFIX):
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for m in _ASSEMBLY_RE.finditer(text):
            after = _balanced(text, m.end())
            arrow = text.find("<->", after)
            if arrow < 0:
                continue
            # the body runs to the next top-level declaration, which is the next
            # line starting in column zero
            end = re.compile(r"^\S", re.MULTILINE).search(text, arrow)
            rhs = text[arrow + 3:end.start() if end else len(text)]
            skeleton = _skeleton(rhs)
            if skeleton:
                out.append(Spelling(ctor=m.group(1), file=rel,
                                    line=text.count("\n", 0, m.start()) + 1,
                                    skeleton=skeleton))
    return out


@dataclass(frozen=True)
class Decoded:
    """One name a word can decode to, and the decode site that names it."""

    ctor: str        # the constructor, exactly as the model spells it
    file: str        # the tracked path it is written in
    line: int        # its 1-based line, for a finding a person has to go and visit
    site: str        # the `encdec` clause or mapping that decodes to it


def _body(text: str, start: int) -> tuple[int, int]:
    """The span of a top-level declaration's body, from its `= {` to column zero.

    A Sail body runs to the next declaration, and the closing brace of a multi-line
    one is itself in column zero, so the same search ends both shapes.
    """
    opened = _BODY_RE.search(text, start)
    if not opened:
        return start, start
    end = re.compile(r"^\S", re.MULTILINE).search(text, opened.end())
    return opened.end(), end.start() if end else len(text)


def _arm_names(text: str, arrow: int, site: str) -> list[tuple[int, str, str]]:
    """The names either side of one arm's arrow, as offsets into `text`.

    The left side is read out of a window ending at the arrow rather than out of the
    whole body, because an arm's name is the token immediately before its arrow and
    an unbounded backward scan would re-read the body once per arm.
    """
    out: list[tuple[int, str, str]] = []
    left = _ARM_LEFT_RE.search(text, max(0, arrow - _ARM_WINDOW), arrow)
    if left:
        out.append((left.start(1), left.group(1), site))
    right = _ARM_RIGHT_RE.match(text, arrow + len("<->"))
    if right:
        out.append((right.start(1), right.group(1), site))
    return out


def read_decoded(root: Path, tracked: list[str]) -> list[Decoded]:
    """Every name the model's decode surface can decode a word to.

    Two shapes, because a form's identity is written in one of two places. It is the
    instruction constructor where a whole clause is the form, and it is a field value
    where the clause is shared and one field says which form it is. A reading that
    took only the first would hold `VLSEGFFTYPE` and miss `AMOCAS` entirely, and the
    difference between them is a Sail authoring choice rather than anything the
    document naming either one can be asked to know.
    """
    out: list[Decoded] = []
    for rel in tracked:
        if not rel.endswith(SAIL_SUFFIX):
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        found: list[tuple[int, str, str]] = [
            (m.start(), m.group(2), m.group(1))
            for m in _DECODE_CLAUSE_RE.finditer(text)]

        for m in _DECODE_MAPPING_RE.finditer(text):
            start, end = _body(text, m.end())
            for arrow in re.finditer("<->", text[start:end]):
                found += _arm_names(text, start + arrow.start(), m.group(1))

        out += [Decoded(ctor=ctor, file=rel,
                        line=text.count("\n", 0, offset) + 1, site=site)
                for offset, ctor, site in found]
    return out


def fragments(name: str) -> tuple[str, ...]:
    """A written mnemonic's literal parts, with its variable parts taken out.

    The pattern carries no capturing group, so every piece a split returns is a
    span of the name and never a group's `None`; saying so is what lets the
    result be the tuple of strings the callers below read it as.
    """
    parts: list[str] = [p for p in _PLACEHOLDER_RE.split(name) if isinstance(p, str)]
    return tuple(p for p in parts if p)


def spells(skeleton: str, name: str) -> bool:
    """Whether a clause with this skeleton can spell this written name.

    Every literal fragment of the name, in the order the name writes them, inside
    the literals the clause writes. See this module's docstring for why the test
    runs in this direction and not the other.
    """
    at = 0
    for fragment in fragments(name):
        found = skeleton.find(fragment, at)
        if found < 0:
            return False
        at = found + len(fragment)
    return True


def _expansion(name: str) -> re.Pattern[str]:
    """A written mnemonic as the pattern its finished spellings match."""
    parts = _PLACEHOLDER_RE.split(name)
    return re.compile(_PLACEHOLDER_EXPANSION.join(re.escape(p) for p in parts) + r"\Z")


def encoder_rows(name: str) -> list[str]:
    """Every row of the corpus assembler's table this written name covers."""
    pattern = _expansion(name)
    return [m for m in dialect.MNEMONICS if pattern.match(m)]
