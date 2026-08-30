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

**The model's half is read out of the emitter's own bundle and not out of the Sail.**
An assembly clause is a *concatenation*, and the mnemonic is assembled at run time out
of literals and mappings:

    mapping clause assembly = AMO(op, aq, rl, rs2, rs1, width, rd)
      <-> amo_mnemonic(op) ^ "." ^ width_mnemonic(width) ^ maybe_aqrl(aq, rl) ^ ...

so `amoswap.d.aq` and `amoadd.b` are two spellings of one clause and neither appears in
the file. A text scan can take only the clause's **skeleton**, its string literals in
order, which for this clause is the single character `.`; everything the three mappings
decide is left out. [sailbundle.py](sailbundle.py) reads the clause as the emitter
structured it instead, resolves each mapping against its own literal arms, and hands
back the finished mnemonics. Over this model that turns 136 readable skeletons into 217
of 218 clauses enumerated, and the single residue is `FENCE`, whose `forwards ... when`
form the emitter leaves as body text with no structured right-hand side.

**The direction of the reading flips with it, and that is a different sentence rather
than a stronger one.** A skeleton under-approximates: a name is paired with a clause
when the name's literal fragments occur in the skeleton in order, which cannot see a
mnemonic built entirely inside a mapping and so misses forms that are there. Enumerated
spellings over-approximate: the cross product of `width_mnemonic` with `maybe_u` in

    mapping clause assembly = LOAD(imm, rs1, rd, is_unsigned, width)
      <-> "l" ^ width_mnemonic(width) ^ maybe_u(is_unsigned) ^ ...

yields `ldu`, which the model never decodes, the constraint that forbids it living in
the `encdec` clause and not in the assembly mapping. For a rule asking *is an excluded
form still on the surface* that is fail-safe, an over-report never being a false green;
for any rule that would count the surface it is a ceiling and not a census.

**Where the document can name the constructor instead there is no bound to take.** The
profile writes `amocas.q` and the clause that would have to spell it is the AMO clause
above, whose skeleton is `.` alone: no fragment of the one occurs in the other, so the
fragment test pairs that name with nothing whether or not the form is present. A
document whose subject is a *single instruction form* therefore names the Sail
constructor beside the mnemonic, and the reading it asks for is not a match at all but
membership: `sailbundle.Bundle.decoded` collects the names a word can decode *to*, and
a marker is in that set or is not. That reaches a form whose constructor is shared with
its neighbours and whose identity is a field value, which `AMOCAS` is: the model decodes
`AMO`, and `AMOCAS` is the `amoop` its five-bit field would decode to.

Both readings of the model's side stand, because they fail differently. An enumeration
cannot see a form re-added under a clause the emitter cannot structure; a marker cannot
see a form re-added under another constructor, and a marker that was misspelled or has
gone stale is absent for the same reason a deleted form is. Neither is the other's
replacement.
"""

import functools
import re

from . import dialect, sailbundle

# What a document writes where an encoding family varies: `<eew>` names the field,
# `*` stands for the rest of a family's names. Both mean *some text decided
# elsewhere*, which is exactly what a mapping in a Sail clause is.
_PLACEHOLDER_RE = re.compile(r"<[^>]*>|\*")

# What a placeholder can expand to in a finished mnemonic. Deliberately not `.*`: a
# placeholder stands for a field's rendering, so it is at least one character and
# never spans the separator or the suffix dot that the literals around it anchor.
_PLACEHOLDER_EXPANSION = r"[0-9a-z]+"


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

    Every literal fragment of the name, in the order the name writes them, inside the
    literals the clause writes. This is the *lower bound* reading, and it survives the
    move to the bundle because one clause still arrives as text: see this module's
    docstring for why the test runs in this direction and not the other, which is that
    asking whether the skeleton's fragments occur in the name pairs a fault-only-first
    load with the ordinary segment load beside it and cannot tell them apart.
    """
    at = 0
    for fragment in fragments(name):
        found = skeleton.find(fragment, at)
        if found < 0:
            return False
        at = found + len(fragment)
    return True


@functools.cache
def _expansion(name: str) -> re.Pattern[str]:
    """A written mnemonic as the pattern its finished spellings match. Cached in
    memory for the process, because one run asks about the same written names for
    every row that spells them and each ask compiled a fresh pattern."""
    parts = _PLACEHOLDER_RE.split(name)
    return re.compile(_PLACEHOLDER_EXPANSION.join(re.escape(p) for p in parts) + r"\Z")


def encoder_rows(name: str) -> list[str]:
    """Every row of the corpus assembler's table this written name covers."""
    pattern = _expansion(name)
    return [m for m in dialect.MNEMONICS if pattern.match(m)]


def spelled_by(clause: sailbundle.Spelled, name: str) -> list[str]:
    """Every mnemonic of one assembly clause that a written name covers.

    Two tests and not one, because the clause states which of them it has earned. An
    enumerated clause carries finished mnemonics, so the written name is expanded to the
    pattern its spellings match and the answer is exact against that clause. A clause the
    emitter left as text carries a skeleton instead, so the fragment test decides it and
    the answer is the lower bound it always was; the skeleton is handed back as the hit
    so that a finding still names something a person can look for.
    """
    if not clause.exact:
        return [s for s in clause.mnemonics if spells(s, name)]
    pattern = _expansion(name)
    return [m for m in clause.mnemonics if pattern.match(m)]
