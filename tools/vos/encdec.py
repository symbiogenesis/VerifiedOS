# SPDX-License-Identifier: Apache-2.0
"""Every form the model decodes, resolved out of its own `encdec` and `assembly` clauses.

[dialect.py](dialect.py) was one row per mnemonic **transcribed** from these clauses, and
the transcription is what this module removes. What it produces is the same fact from the
one artifact that owns it: for each mnemonic the model can spell, the bits its encoding
fixes, where each operand sits in the word, and the guard the clause is admitted under.

**This module is a parse and never a decision.** Whether a guard admits a form, which
configuration that is resolved at, and what an assembler does with a form whose guard it
cannot decide are all [dialectgen.py](dialectgen.py)'s.

## The join, and the one non-obvious step in it

`encdec` says how a form is encoded and `assembly` says how it is spelled, and the two
are related by the **constructor** they share. Neither alone is a row: `encdec` gives the
bits and no name, `assembly` gives the name and no bits.

Both clauses match the same constructor positionally, so position *is* the variable's
identity across the two, and that is the step a reader skips at its peril. A clause whose
left pattern fixes an argument by naming a constructor, `SHIFTIOP(shamt, rs1, rd, SLLI)`,
is one encoding of three the shared `assembly` clause spells, and a reader that took the
mnemonic mapping's arms without the binding hands back `slli`, `srli` and `srai` all
carrying `slli`'s funct7. Measured on this model: without the binding **49** mnemonics
come back with two or three candidate encodings, every one of them a row the transcribed
table already had, so the defect is invisible in the count and lethal in the bytes.

The same positional reading carries three more facts for free. A variable that is a
selector on one side and a plain field on the other has its field bits **fixed by the
mnemonic** (`sh1add.uw` against `sh2add.uw` is two values of one two-bit field, not two
opcodes). A left pattern of the shape `imm @ 0b0` states the implicit immediate scaling
structurally, so the branch and jump shift-by-one is recovered rather than transcribed.
And a mnemonic mapping and an encoding mapping over the same position are quantified
**jointly**, which is what makes `amoswap.d.aqrl` one row of a cross product rather than
a spelling somebody wrote out.

## What it over-approximates, said out loud

An enumeration of the cross product admits combinations the `encdec` clause forbids. The
model spells a load `"l" ^ width_mnemonic(width) ^ maybe_u(is_unsigned)` and rules out
the unsigned doubleword in the guard rather than in the spelling, so the product contains
`ldu`, which the model decodes nowhere. That is why every form here carries its guard
verbatim: this module hands back what the clauses *spell*, and refusing what the machine
cannot decode is the caller's, on the ground the caller states.
"""

import re
from dataclasses import dataclass
from itertools import product
from typing import Any

from .sailbundle import SOURCE_ROOT, Bundle, Site

# The call an `assembly` clause puts between the mnemonic and its first operand, and the
# one it puts between operands. `opt_spc` is optional whitespace inside an operand and
# carries no value at all.
MNEMONIC_END = "spc"
OPERAND_SEP = "sep"
OPTIONAL_SPACE = "opt_spc"

# The guard's own text begins after this word in the clause's source. The bundle carries
# no structured guard node, so the text is the whole of what a reader has.
_WHEN_RE = re.compile(r"\bwhen\b(.*)$", re.DOTALL)

# A wavedrom row: the field's width and its name, which is quoted where the field is a
# name and a hex literal where it is a constant. This is where a bare `id` on the right
# of an `encdec` clause gets its width, there being nothing else that carries it.
_WAVE_RE = re.compile(r"\{\s*bits:\s*(\d+),\s*name:\s*(?:'([^']*)'|0[xX][0-9a-fA-F]+|\d+)")

# A Sail bit literal, as the emitter spells one inside a pattern node.
_BITS_RE = re.compile(r"^0b([01_]+)$")


class UnreadableError(RuntimeError):
    """One clause this reader does not resolve, named where it is met.

    Raised per clause and caught by the walk rather than escaping it: a model with one
    clause this reader has no rule for still yields every other clause, and the residue
    is a finding the caller counts rather than a run that stopped.
    """


@dataclass(frozen=True)
class Piece:
    """One run of an operand's bits, and where in the word it lands.

    Four numbers rather than two because a RISC-V immediate is scattered: the B-type
    displacement reaches the word in four runs, and a placement stated as a single
    shift could not say so.
    """

    word_hi: int
    word_lo: int
    src_hi: int
    src_lo: int


@dataclass(frozen=True)
class Operand:
    """One operand of one form: the model's own name for it, how the model prints it,
    and where its bits go.

    `width` is the *value's* rather than the field's. A branch displacement is thirteen
    bits with its low bit implicitly zero, which the clause states as `imm @ 0b0` on its
    left and encodes as twelve bits on its right; carrying the field's twelve would lose
    the shift that makes the value an address. The shift itself needs no field of its
    own, being the lowest source bit no piece reaches.
    """

    name: str
    printer: str
    width: int
    pieces: tuple[Piece, ...]

    @property
    def align(self) -> int:
        """What the value must be a multiple of, which is one for every operand the
        encoding carries whole and two for a displacement it shifts."""
        return 1 << min(piece.src_lo for piece in self.pieces)


@dataclass(frozen=True)
class Form:
    """One mnemonic the model spells, with the encoding it spells it at.

    `word` and `mask` are the constant half: `word` is what the encoding fixes and `mask`
    says which bits it fixes, so that a caller can hold `word` against an encoder's
    output without asking which bits were operands. `syntax` is the operand run as the
    model prints it, one token per printed thing, so that a reader can see the spelling
    without re-walking the clause.
    """

    mnemonic: str
    ctor: str
    site: Site
    word: int
    mask: int
    guard: str
    operands: tuple[Operand, ...]
    syntax: tuple[str, ...]
    bindings: tuple[tuple[str, str], ...]


def _bits(text: str) -> tuple[int, int] | None:
    """A bit literal's value and width, or `None` where the text is not one."""
    found = _BITS_RE.match(text)
    if not found:
        return None
    body = found.group(1).replace("_", "")
    return int(body, 2), len(body)


def _quoted(text: str) -> str | None:
    return text[1:-1] if len(text) >= 2 and text[0] == '"' and text[-1] == '"' else None


def _widths(wavedrom: str) -> dict[str, int]:
    """Each named field's width, off the clause's own wavedrom row.

    The one place a bare `id` on the right of an `encdec` clause carries its width. A
    name appearing twice keeps the first row's width, the wavedrom being ordered and the
    duplicate being the same field drawn twice.
    """
    out: dict[str, int] = {}
    for bits, name in _WAVE_RE.findall(wavedrom or ""):
        if name:
            out.setdefault(str(name), int(bits))
    return out


def _spans(pieces: list[tuple[str, object, int]]) -> dict[str, int]:
    """Each scattered field's width, taken from the highest source bit the encoding
    reads of it.

    The second answer to the same question the wavedrom answers, and it is needed rather
    than redundant: a field the encoding places in runs is drawn under the *runs'* names
    (`imm[9..4]`), so the whole field's own name appears in no wavedrom row and a reader
    with only that source cannot size a store's displacement or a branch's.
    """
    out: dict[str, int] = {}
    for kind, payload, _ in pieces:
        if kind != "field":
            continue
        name, hi, _lo = _field(payload)
        out[name] = max(out.get(name, 0), hi + 1)
    return out


def arm_key(node: object) -> tuple[object, ...] | None:
    """A mapping arm's pattern as a comparable key, or `None` where it is not one shape.

    Four shapes and all four are load-bearing: a bare id (`SLLI`), a literal (a width),
    a tuple (`maybe_aqrl(aq, rl)`) and a struct (`mul_mnemonic`'s record pattern).
    Handling only the first two loses the whole atomic cross product and the four
    multiply forms.
    """
    if not isinstance(node, dict):
        return None
    kind = node.get("type")
    if kind == "id":
        return ("id", node.get("id"))
    if kind == "literal":
        return ("lit", node.get("value"))
    if kind == "tuple":
        parts = [arm_key(part) for part in node.get("patterns", [])]
        return None if any(p is None for p in parts) else ("tuple", *parts)
    if kind == "struct":
        fields = node.get("fields")
        if not isinstance(fields, dict):
            return None
        parts = [(name, arm_key(fields[name])) for name in sorted(fields)]
        if any(p[1] is None for p in parts):
            return None
        return ("struct", *parts)
    if kind == "app":
        parts = [arm_key(part) for part in node.get("patterns", [])]
        if any(p is None for p in parts):
            return None
        return ("app", node.get("id"), *parts)
    return None


Arms = dict[tuple[object, ...], object]


def _sided(clause: dict[str, Any], *, bits: bool
           ) -> tuple[tuple[object, ...], object, int] | None:
    """One arm read as `(key, value, width)`, whichever side carries the literal.

    `width` is the bit literal's and is zero for a string one, which is what lets the
    caller hold a bit mapping's arms to one width without a second walk.
    """
    for value_side, key_side in (("right", "left"), ("left", "right")):
        node = clause.get(value_side)
        if not isinstance(node, dict) or node.get("type") != "literal":
            continue
        text = str(node.get("value", ""))
        key = arm_key(clause.get(key_side))
        if key is None:
            continue
        if bits:
            found = _bits(text)
            if found is not None:
                return key, found[0], found[1]
        else:
            spelled = _quoted(text)
            if spelled is not None:
                return key, spelled, 0
    return None


class Surface:
    """The model's decode surface, joined once and asked for its forms.

    Built around a bundle rather than around a path, because the caller that wants this
    already holds one: the generated-artifact rule opens the bundle to decide whether it
    is still the model's, and reading a second copy to answer a second question would be
    the two-copies defect one file over.
    """

    def __init__(self, bundle: Bundle) -> None:
        self.bundle = bundle
        self._bit_arms: dict[str, Arms | None] = {}
        self._str_arms: dict[str, Arms | None] = {}

    # -- the two mapping readings ----------------------------------------------------

    def _arms(self, name: str) -> list[dict[str, Any]]:
        return self.bundle.clauses(name)

    def bit_arms(self, name: str) -> Arms | None:
        """A mapping every arm of which produces a bit literal of one width, keyed by the
        arm's pattern. `None` where any arm does not, which is what tells a walk that the
        application is an operand field rather than a selector."""
        if name not in self._bit_arms:
            self._bit_arms[name] = self._read_arms(name, bits=True)
        return self._bit_arms[name]

    def str_arms(self, name: str) -> Arms | None:
        """The same, for a mapping every arm of which produces a string literal."""
        if name not in self._str_arms:
            self._str_arms[name] = self._read_arms(name, bits=False)
        return self._str_arms[name]

    def _read_arms(self, name: str, *, bits: bool) -> Arms | None:
        """One mapping's arms, keyed by the side that is *not* the literal being read.

        A Sail mapping is bidirectional and its clauses are written in whichever
        direction reads better, so the literal sits on either side: `encdec_vlewidth`
        writes `VLE8 <-> 0b000` and `encdec_nfields` writes `0b000 <-> 1`. A reader that
        looked only at the right-hand side would take the second for a mapping with no
        literal arms at all and fall through to reading `nf` as an operand field, which
        silently drops every segment and unit-stride vector access the model has.
        """
        if not self.bundle.has("mappings", name):
            return None
        out: Arms = {}
        widths: set[int] = set()
        for clause in self._arms(name):
            found = _sided(clause, bits=bits)
            if found is None:
                return None
            key, value, width = found
            out[key] = value
            if width:
                widths.add(width)
        if not out or (bits and len(widths) != 1):
            return None
        return out

    def arm_width(self, name: str) -> int:
        """One bit mapping's arm width. Called only where `bit_arms` answered, which is
        what makes the single width an invariant here rather than a lookup that can
        miss."""
        for clause in self._arms(name):
            found = _sided(clause, bits=True)
            if found is not None:
                return found[2]
        raise UnreadableError(f"{name} has no bit-literal arm after all")

    # -- the walk over one clause's right-hand side ----------------------------------

    def _walk(self, node: dict[str, Any], widths: dict[str, int],
              out: list[tuple[str, object, int]]) -> None:
        kind = node.get("type")
        if kind == "vector_concat":
            for part in node.get("patterns", []):
                if not isinstance(part, dict):
                    raise UnreadableError("a concatenation with an unstructured part")
                self._walk(part, widths, out)
            return
        if kind == "literal":
            found = _bits(str(node.get("value", "")))
            if found is None:
                raise UnreadableError(f"the literal {node.get('value')} is not a bit run")
            out.append(("const", found[0], found[1]))
            return
        if kind == "id":
            name = str(node.get("id"))
            if name not in widths:
                raise UnreadableError(f"nothing states the width of {name}")
            out.append(("field", (name, widths[name] - 1, 0), widths[name]))
            return
        if kind == "vector_subrange":
            name = str(node.get("id"))
            hi, lo = int(node.get("from", 0)), int(node.get("to", 0))
            out.append(("field", (name, hi, lo), hi - lo + 1))
            return
        if kind == "app":
            self._walk_app(node, widths, out)
            return
        raise UnreadableError(f"no reading for a {kind} node")

    def _walk_app(self, node: dict[str, Any], widths: dict[str, int],
                  out: list[tuple[str, object, int]]) -> None:
        name = str(node.get("id"))
        args = [part for part in node.get("patterns", []) if isinstance(part, dict)]
        arms = self.bit_arms(name)
        if arms is not None:
            width = self.arm_width(name)
            if len(arms) == 1:
                out.append(("const", next(iter(arms.values())), width))
                return
            out.append(("select", (name, tuple(_argument_names(args))), width))
            return
        # A mapping whose arms are not literals is the model's own register encoding:
        # `encdec_reg` and `encdec_vreg` are functions of the register, so what the
        # clause places here is the operand itself. Without this fallback only 8 of the
        # 253 clauses resolve; with it, 252 do.
        if len(args) == 1 and args[0].get("type") == "id":
            field = str(args[0].get("id"))
            if field in widths:
                out.append(("field", (field, widths[field] - 1, 0), widths[field]))
                return
        raise UnreadableError(f"no reading for the application {name}")

    # -- the join --------------------------------------------------------------------

    def forms(self) -> tuple[list[Form], list[str]]:
        """Every form the model spells, and the clauses this reader did not resolve.

        Both halves are returned because the residue is the finding: a clause dropped
        silently is a mnemonic an assembler will refuse for no stated reason, which is
        exactly the failure the transcription this replaces was capable of.
        """
        assembly = {ctor: clause for clause in self._arms("assembly")
                    if (ctor := _constructor(clause)) is not None}
        out: list[Form] = []
        residue: list[str] = []
        for clause in self._arms("encdec"):
            ctor = _constructor(clause)
            if ctor is None:
                residue.append("an encdec clause whose left side names no constructor")
                continue
            spelling = assembly.get(ctor)
            if spelling is None:
                residue.append(f"{ctor} has an encdec clause and no assembly clause")
                continue
            try:
                out += self._forms_of(ctor, clause, spelling)
            except UnreadableError as exc:
                residue.append(f"{ctor} at {_site(clause)}: {exc}")
        return out, residue

    def _forms_of(self, ctor: str, encoding: dict[str, Any],
                  spelling: dict[str, Any]) -> list[Form]:
        widths = _widths(str(encoding.get("right_wavedrom", "")))
        right = encoding.get("right")
        if not isinstance(right, dict):
            raise UnreadableError("the encdec clause has no structured right-hand side")
        pieces: list[tuple[str, object, int]] = []
        self._walk(right, widths, pieces)
        if sum(width for _, _, width in pieces) != 32:
            raise UnreadableError(f"the encoding is "
                             f"{sum(w for _, _, w in pieces)} bits and not 32")

        bound = _Binding(encoding, spelling, widths | _spans(pieces))
        run, printed = _split_spelling(spelling)
        constraints = self._constraints(bound, pieces, run)
        return [form for assignment in _assignments(constraints)
                if (form := self._one(ctor, encoding, bound, pieces, run, printed,
                                      constraints, assignment)) is not None]

    def _constraints(self, bound: _Binding, pieces: list[tuple[str, object, int]],
                     run: list[dict[str, Any]]) -> list[_Constraint]:
        """Every mapping that decides a position, from both sides of the join.

        The encoding's selectors and the mnemonic's spellings are collected into one
        list because they are one quantification: a position both of them read is read
        once, which is what makes `amoswap.d.aqrl` a row rather than a coincidence.
        """
        out: list[_Constraint] = []
        for kind, payload, _ in pieces:
            if kind != "select":
                continue
            name, args = _selector(payload)
            arms = self.bit_arms(name)
            if arms is None:
                raise UnreadableError(f"{name} stopped reading as a bit mapping")
            out.append(_Constraint("encoding", name, bound.positions(args), arms))
        for part in run:
            if part.get("type") != "app":
                continue
            name = str(part.get("id"))
            arms = self.str_arms(name)
            if arms is None:
                raise UnreadableError(f"the mnemonic mapping {name} has a non-literal arm")
            args = tuple(_argument_names(
                [p for p in part.get("patterns", []) if isinstance(p, dict)]))
            out.append(_Constraint("spelling", name, bound.positions(args, side="asm"),
                                   arms))
        return out

    def _one(self, ctor: str, encoding: dict[str, Any], bound: _Binding,
             pieces: list[tuple[str, object, int]], run: list[dict[str, Any]],
             printed: list[dict[str, Any]], constraints: list[_Constraint],
             assignment: dict[int, tuple[object, ...]]) -> Form | None:
        """One consistent assignment of every selector, as one row, or `None` where the
        clause's own left pattern rules that assignment out."""
        if any(assignment.get(at, key) != key for at, key in bound.fixed.items()):
            return None
        word, mask, placed = self._encode(bound, pieces, constraints, assignment)
        operands = _operands(bound, printed, placed)
        _covered(word, mask, operands)
        return Form(
            mnemonic=_spell(bound, run, constraints, assignment),
            ctor=ctor,
            site=_site(encoding),
            word=word,
            mask=mask,
            guard=_guard(encoding),
            operands=operands,
            syntax=_syntax(printed),
            bindings=_bindings(bound, assignment),
        )

    def _encode(self, bound: _Binding, pieces: list[tuple[str, object, int]],
                constraints: list[_Constraint],
                assignment: dict[int, tuple[object, ...]]
                ) -> tuple[int, int, dict[int, list[Piece]]]:
        """The word this assignment fixes, and where every unfixed field lands.

        The third case is the one a reader invents at its peril: a field the *encoding*
        leaves free that the *mnemonic* has decided is a constant, not an operand, and
        treating it as an operand leaves `sh1add.uw` and `sh3add.uw` sharing a word.
        """
        word = mask = 0
        placed: dict[int, list[Piece]] = {}
        at = 32
        for kind, payload, width in pieces:
            at -= width
            if kind == "const":
                word |= _integer(payload) << at
                mask |= ((1 << width) - 1) << at
                continue
            if kind == "select":
                name, args = _selector(payload)
                value = _selected(constraints, "encoding", name,
                                  bound.positions(args), assignment)
                word |= value << at
                mask |= ((1 << width) - 1) << at
                continue
            field, hi, lo = _field(payload)
            found = bound.parts.get(field)
            if found is None:
                raise UnreadableError(f"{field} is encoded and is no argument of the form")
            position, offset = found
            decided = assignment.get(position)
            if decided is not None:
                word |= _literal_of(decided, width) << at
                mask |= ((1 << width) - 1) << at
                continue
            placed.setdefault(position, []).append(
                Piece(word_hi=at + width - 1, word_lo=at,
                      src_hi=hi + offset, src_lo=lo + offset))
        return word, mask, placed


# --- the positional binding, which is the join's own step ---------------------------


class _Binding:
    """One constructor's argument positions, read from both clauses at once.

    Position is the variable's identity across the two clauses, so this holds the maps
    that let one side's name be looked up by the other's: which name the encoding calls
    each position, which name the spelling calls it, and which positions either side has
    fixed to a value outright.

    One argument may be spelled by several names on the encoding side, and that is the
    shape a reader most easily gets wrong. A jump's displacement is written
    `CJAL(imm_19 @ imm_7_0 @ imm_8 @ imm_18_13 @ imm_12_9 @ 0b0, cd)`: five names and a
    zero bit are one twenty-one-bit operand, permuted, with the implicit shift stated by
    the literal. So `parts` carries each name's offset **inside the argument's value**,
    which is what turns the permutation and the shift into arithmetic instead of two
    more facts to transcribe.
    """

    def __init__(self, encoding: dict[str, Any], spelling: dict[str, Any],
                 widths: dict[str, int]) -> None:
        left = _patterns(encoding)
        right = _patterns(spelling)
        self.parts: dict[str, tuple[int, int]] = {}
        self.spelling: dict[str, int] = {}
        self.width: dict[int, int] = {}
        self.fixed: dict[int, tuple[object, ...]] = {}
        used = _referenced(encoding.get("right"))
        printed = _referenced(spelling.get("right"))
        for at in range(min(len(left), len(right))):
            self._bind_encoding(at, left[at], used, widths)
            self._bind_spelling(at, right[at], printed)

    def _bind_encoding(self, at: int, node: dict[str, Any], used: frozenset[str],
                       widths: dict[str, int]) -> None:
        """One position of the encoding's own left pattern.

        A bare `id` is a *variable* only where the clause's own right-hand side reads it;
        where it does not, the id is a constructor and the position is fixed. That test
        is the whole of the 49-row defect: `SHIFTIOP(shamt, rs1, rd, SLLI)` names `SLLI`
        exactly once, and a reader that took every id for a variable takes three
        encodings for one.
        """
        parts = _composite(node)
        if parts is not None and all(name in used or name == "" for name, _ in parts):
            offset = 0
            total = 0
            for name, width in reversed(parts):
                size = width or widths.get(name, 0)
                if not size:
                    raise UnreadableError(f"nothing states the width of {name}")
                if name:
                    self.parts[name] = (at, offset)
                offset += size
                total += size
            self.width[at] = total
            return
        key = arm_key(node)
        if key is not None:
            self.fixed[at] = key

    def _bind_spelling(self, at: int, node: dict[str, Any],
                       printed: frozenset[str]) -> None:
        found = _variable(node)
        if found is not None and found[0] in printed:
            self.spelling[found[0]] = at
            return
        key = arm_key(node)
        if key is not None:
            self.fixed[at] = key

    def positions(self, names: tuple[str, ...],
                  side: str = "enc") -> tuple[int, ...]:
        out: list[int] = []
        for name in names:
            if side == "asm":
                at = self.spelling.get(name)
            else:
                found = self.parts.get(name)
                at = None if found is None else found[0]
            if at is None:
                raise UnreadableError(f"{name} names no argument position")
            out.append(at)
        return tuple(out)


@dataclass(frozen=True)
class _Constraint:
    """One mapping over one or more argument positions, and the arms it admits."""

    side: str
    name: str
    positions: tuple[int, ...]
    arms: Arms


def _assignments(constraints: list[_Constraint]
                 ) -> list[dict[int, tuple[object, ...]]]:
    """Every assignment of positions to arm keys that every constraint agrees on.

    A product over the arms rather than over the positions, because a constraint may
    read two positions at once (`maybe_aqrl(aq, rl)`) and the agreement test is then
    between constraints rather than inside one.
    """
    if not constraints:
        return [{}]
    # Constraints over the *same* positions are intersected before the product rather
    # than filtered after it, and on this model that is the difference between a walk
    # and a wait: an atomic's operation is decided by its mnemonic mapping and by its
    # encoding mapping both, so a product that enumerated the two independently walks
    # eighty-one pairings of nine to keep nine, and the same happens on the width and on
    # the two ordering bits, twenty thousand combinations against five hundred.
    grouped: dict[tuple[int, ...], list[dict[int, tuple[object, ...]]]] = {}
    for constraint in constraints:
        here: list[dict[int, tuple[object, ...]]] = []
        for key in constraint.arms:
            parts = _spread(key, len(constraint.positions))
            if parts is None:
                continue
            here.append(dict(zip(constraint.positions, parts, strict=True)))
        already = grouped.get(constraint.positions)
        grouped[constraint.positions] = here if already is None \
            else [one for one in already if one in here]
    out: list[dict[int, tuple[object, ...]]] = []
    for combination in product(*grouped.values()):
        merged: dict[int, tuple[object, ...]] = {}
        if all(_merge(merged, binding) for binding in combination):
            out.append(merged)
    return out


def _spread(key: tuple[object, ...], width: int) -> list[tuple[object, ...]] | None:
    """One arm key over `width` positions, or `None` where it does not cover them."""
    if width == 1:
        return [key]
    if key and key[0] == "tuple" and len(key) - 1 == width:
        return [part for part in key[1:] if isinstance(part, tuple)]
    return None


def _merge(into: dict[int, tuple[object, ...]],
           binding: dict[int, tuple[object, ...]]) -> bool:
    return all(into.setdefault(at, value) == value for at, value in binding.items())


def _selected(constraints: list[_Constraint], side: str, name: str,
              positions: tuple[int, ...],
              assignment: dict[int, tuple[object, ...]]) -> int:
    """The bits one selector's chosen arm lays down.

    Keyed on the **positions** as well as the mapping's name, which is not a refinement:
    one clause applies `bool_bit` twice, once to the acquire flag and once to release,
    and a lookup by name alone gives both bits the first one's value. Measured, that
    silently mislabels every `.aq` form as `.aqrl` and every `.rl` form as unordered.
    """
    for constraint in constraints:
        if constraint.side != side or constraint.name != name \
                or constraint.positions != positions:
            continue
        key = _spread_back(constraint, assignment)
        value = constraint.arms.get(key)
        if isinstance(value, int):
            return value
    raise UnreadableError(f"the assignment picks no arm of {name}")


def _spread_back(constraint: _Constraint,
                 assignment: dict[int, tuple[object, ...]]) -> tuple[object, ...]:
    parts = [assignment[at] for at in constraint.positions]
    return parts[0] if len(parts) == 1 else ("tuple", *parts)


def _bindings(bound: _Binding,
              assignment: dict[int, tuple[object, ...]]) -> tuple[tuple[str, str], ...]:
    """Each of the form's arguments the mnemonic and the encoding between them have
    fixed, spelled as the model spells it.

    This is what makes the clause's own guard *decidable* for one row rather than for
    the whole clause: `valid_load_encdec(width, is_unsigned)` is a fact about the
    doubleword-unsigned combination, and a reader without the binding could only carry
    the guard forward as text.
    """
    out: list[tuple[str, str]] = []
    for name, (at, _offset) in sorted(bound.parts.items()):
        key = assignment.get(at, bound.fixed.get(at))
        if key is not None and len(key) == 2 and key[0] in ("lit", "id"):
            out.append((name, str(key[1])))
    return tuple(out)


def _spell(bound: _Binding, run: list[dict[str, Any]], constraints: list[_Constraint],
           assignment: dict[int, tuple[object, ...]]) -> str:
    """The mnemonic this assignment spells, part by part.

    Matched on positions beside the mapping's name for the reason `_selected` states: a
    clause may apply one mapping to two different arguments, and a lookup by name alone
    would spell both from the first.
    """
    out: list[str] = []
    for part in run:
        if part.get("type") == "literal":
            text = _quoted(str(part.get("value", "")))
            if text is None:
                raise UnreadableError("a mnemonic literal that is not a string")
            out.append(text)
            continue
        name = str(part.get("id"))
        args = tuple(_argument_names(
            [p for p in part.get("patterns", []) if isinstance(p, dict)]))
        positions = bound.positions(args, side="asm")
        for constraint in constraints:
            if constraint.side != "spelling" or constraint.name != name \
                    or constraint.positions != positions:
                continue
            value = constraint.arms.get(_spread_back(constraint, assignment))
            if isinstance(value, str):
                out.append(value)
                break
        else:
            raise UnreadableError(f"the assignment spells no arm of {name}")
    return "".join(out)


# --- reading one clause's parts -----------------------------------------------------


def _constructor(clause: dict[str, Any]) -> str | None:
    left = clause.get("left")
    if not isinstance(left, dict):
        return None
    if left.get("type") in ("app", "id"):
        ident = left.get("id")
        return str(ident) if isinstance(ident, str) else None
    return None


def _patterns(clause: dict[str, Any]) -> list[dict[str, Any]]:
    left = clause.get("left")
    if not isinstance(left, dict) or left.get("type") != "app":
        return []
    return [part for part in left.get("patterns", []) if isinstance(part, dict)]


def _variable(node: dict[str, Any]) -> tuple[str, int] | None:
    """A left pattern that is one named variable, or `None`."""
    if node.get("type") == "id":
        return (str(node.get("id")), 0)
    return None


def _composite(node: dict[str, Any]) -> list[tuple[str, int]] | None:
    """A left pattern as the runs its value is made of, most significant first.

    Each run is a name and a width, with the width `0` where the name's own declaration
    carries it and the name `""` where the run is a literal. Both cases are real: a
    branch writes `imm @ 0b0`, one named run over one anonymous zero, and a jump writes
    five named runs over one.
    """
    if node.get("type") == "id":
        return [(str(node.get("id")), 0)]
    if node.get("type") != "vector_concat":
        return None
    out: list[tuple[str, int]] = []
    for part in node.get("patterns", []):
        if not isinstance(part, dict):
            return None
        if part.get("type") == "id":
            out.append((str(part.get("id")), 0))
            continue
        found = _bits(str(part.get("value", ""))) \
            if part.get("type") == "literal" else None
        if found is None or found[0] != 0:
            return None
        out.append(("", found[1]))
    return out


def _referenced(node: object) -> frozenset[str]:
    """Every name a clause's right-hand side reads.

    The test that separates a variable from a constructor in a left pattern, and it is a
    whole-subtree walk rather than a top-level scan because a name can sit three
    applications deep.
    """
    out: set[str] = set()
    _collect(node, out)
    return frozenset(out)


def _collect(node: object, out: set[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") in ("id", "vector_subrange"):
            ident = node.get("id")
            if isinstance(ident, str):
                out.add(ident)
        for value in node.values():
            _collect(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect(item, out)


def _split_spelling(clause: dict[str, Any]
                    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One assembly clause's mnemonic run and its printed operand run, split at `spc()`.

    A clause with no separator is a mnemonic and no operands, which is what every
    zero-operand form is: the split is on the token rather than on a count, so a form
    that grows an operand moves the split with it.
    """
    right = clause.get("right")
    if not isinstance(right, dict):
        raise UnreadableError("the assembly clause has no structured right-hand side")
    parts = right.get("patterns") if right.get("type") == "string_append" else [right]
    if not isinstance(parts, list):
        raise UnreadableError("the assembly clause spells nothing")
    mnemonic: list[dict[str, Any]] = []
    printed: list[dict[str, Any]] = []
    seen = False
    for part in parts:
        if not isinstance(part, dict):
            raise UnreadableError("an unstructured part of the assembly clause")
        if not seen and part.get("type") == "app" and part.get("id") == MNEMONIC_END:
            seen = True
            continue
        # Whitespace inside the operand run, of both kinds. `opt_spc` is optional and
        # `spc` is not, and neither carries a value: the indexed access is spelled
        # `cs1[rs2 << scale]` with a `spc()` on each side of the shift, which a reader
        # taking every application for an operand reads as an operand printing nothing.
        if seen and part.get("type") == "app" \
                and part.get("id") in (OPTIONAL_SPACE, MNEMONIC_END):
            continue
        (printed if seen else mnemonic).append(part)
    return mnemonic, printed


def _syntax(printed: list[dict[str, Any]]) -> tuple[str, ...]:
    """The operand run as the model prints it: the mapping that prints each operand, the
    separators, and the punctuation between them, one token each."""
    out: list[str] = []
    for part in printed:
        if part.get("type") == "literal":
            text = _quoted(str(part.get("value", "")))
            out.append("," if text is None else text)
        elif part.get("id") == OPERAND_SEP:
            out.append(",")
        else:
            out.append(str(part.get("id")))
    return tuple(out)


def _operands(bound: _Binding, printed: list[dict[str, Any]],
              placed: dict[int, list[Piece]]) -> tuple[Operand, ...]:
    """The operands in the order the model prints them.

    Print order rather than encoding order, because the print order is the *source*
    order an assembler reads and the encoding order is an artifact of the word's layout.
    A printed thing whose bits the encoding fixed is not an operand at all and is left
    out here, having become part of the constant.

    A printer taking several arguments prints **one** operand, and the one that does it
    is `vsetvli`'s: `vtype_assembly(vtr, ma, ta, sew, lmul)` is five encoded fields and
    one number a program writes. So its pieces are joined into one value in the order
    the encoding lays them down, which is exactly the eleven-bit `vtype` image, taken
    out of the model rather than declared beside it.
    """
    out: list[Operand] = []
    for part in printed:
        if part.get("type") != "app" or part.get("id") == OPERAND_SEP:
            continue
        args = [p for p in part.get("patterns", []) if isinstance(p, dict)]
        names = _argument_names(args)
        pieces: list[Piece] = []
        width = 0
        for name in names:
            at = bound.spelling.get(name)
            found = placed.get(at) if at is not None else None
            if at is None or found is None:
                raise UnreadableError(f"{name} is printed and the encoding places it nowhere")
            pieces += found
            width += bound.width.get(at, 0)
        if len(names) > 1:
            pieces = _joined(pieces)
            width = sum(piece.word_hi - piece.word_lo + 1 for piece in pieces)
        if width != max(piece.src_hi for piece in pieces) + 1:
            raise UnreadableError(f"{'+'.join(names)} is declared {width} bits and reaches "
                             f"{max(p.src_hi for p in pieces) + 1}")
        out.append(Operand(name="+".join(names), printer=str(part.get("id")),
                           width=width, pieces=tuple(pieces)))
    return tuple(out)


def _joined(pieces: list[Piece]) -> list[Piece]:
    """Several arguments' placements read as one value's, most significant first.

    The order is the encoding's own, which is what makes the joined value the one the
    model would print: `vtype_assembly`'s five fields are adjacent in the word and their
    concatenation *is* the `vtype` image a program writes.
    """
    out: list[Piece] = []
    at = sum(piece.word_hi - piece.word_lo + 1 for piece in pieces)
    for piece in sorted(pieces, key=lambda p: p.word_hi, reverse=True):
        width = piece.word_hi - piece.word_lo + 1
        at -= width
        out.append(Piece(word_hi=piece.word_hi, word_lo=piece.word_lo,
                         src_hi=at + width - 1, src_lo=at))
    return out


def _covered(word: int, mask: int, operands: tuple[Operand, ...]) -> None:
    """Every bit of the word is either fixed or reachable by exactly one operand.

    Raised rather than asserted, and it is the check this whole join most needs to
    survive `python -O`. Two silent defects land here and nowhere else: a field the
    mnemonic decided but the encoding left free, which leaves two mnemonics sharing one
    word, and a field the encoding places that the clause never prints, which leaves an
    instruction with bits no operand can set. Both assemble cleanly and run as a
    different program.
    """
    reached = 0
    for operand in operands:
        for piece in operand.pieces:
            run = ((1 << (piece.word_hi - piece.word_lo + 1)) - 1) << piece.word_lo
            if reached & run or mask & run:
                raise UnreadableError("two operands reach one bit of the word")
            reached |= run
    if reached | mask != (1 << 32) - 1:
        loose = ((1 << 32) - 1) & ~(reached | mask)
        raise UnreadableError(f"the encoding leaves {loose:#010x} decided by nothing")
    if word & ~mask:
        raise UnreadableError("the constant sets a bit the mask does not claim")


def _argument_names(args: list[dict[str, Any]]) -> list[str]:
    """The variable names one application reads, flattening the single tuple argument a
    two-variable mapping takes (`maybe_aqrl((aq, rl))`)."""
    if len(args) == 1 and args[0].get("type") == "tuple":
        args = [part for part in args[0].get("patterns", []) if isinstance(part, dict)]
    out: list[str] = []
    for arg in args:
        ident = arg.get("id")
        if arg.get("type") != "id" or not isinstance(ident, str):
            raise UnreadableError("an application over something that is not a variable")
        out.append(ident)
    return out


def _guard(clause: dict[str, Any]) -> str:
    source = clause.get("source")
    text = str(source.get("contents", "")) if isinstance(source, dict) else ""
    found = _WHEN_RE.search(text)
    return " ".join(found.group(1).split()) if found else ""


def _site(clause: dict[str, Any]) -> Site:
    source = clause.get("source")
    if not isinstance(source, dict):
        raise UnreadableError("a clause with no source slot")
    file, loc = source.get("file"), source.get("loc")
    if not isinstance(file, str) or not isinstance(loc, list) or not loc:
        raise UnreadableError("a clause with no file:line")
    return Site(f"{SOURCE_ROOT}/{file}", int(loc[0]))


# --- small narrowings, each stated where the invariant is relied on -----------------


def _integer(payload: object) -> int:
    if not isinstance(payload, int):
        raise UnreadableError(f"a constant run carrying {payload!r}")
    return payload


def _selector(payload: object) -> tuple[str, tuple[str, ...]]:
    if not isinstance(payload, tuple) or len(payload) != 2:
        raise UnreadableError(f"a selector carrying {payload!r}")
    name, args = payload
    if not isinstance(name, str) or not isinstance(args, tuple):
        raise UnreadableError(f"a selector carrying {payload!r}")
    return name, tuple(str(arg) for arg in args)


def _field(payload: object) -> tuple[str, int, int]:
    if not isinstance(payload, tuple) or len(payload) != 3:
        raise UnreadableError(f"a field carrying {payload!r}")
    name, hi, lo = payload
    if not isinstance(name, str) or not isinstance(hi, int) or not isinstance(lo, int):
        raise UnreadableError(f"a field carrying {payload!r}")
    return name, hi, lo


def _literal_of(key: tuple[object, ...], width: int) -> int:
    """An arm key as the constant it fixes a field to.

    Fail-closed on any other shape: a key that is a constructor rather than a literal
    names a value this reader has no bits for, and guessing zero would encode a form the
    model spells differently.
    """
    if len(key) == 2 and key[0] == "lit":
        text = str(key[1])
        found = _bits(text)
        if found is not None and found[1] <= width:
            return found[0]
        if text.isdigit() and int(text) < (1 << width):
            return int(text)
    raise UnreadableError(f"the mnemonic fixes a field to {key!r}, which is not a literal")
