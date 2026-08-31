# SPDX-License-Identifier: Apache-2.0
"""The frozen dialect's encoder table, generated from the model's own bundle.

[encdec.py](encdec.py) reads what the model *spells*; this decides what an assembler
**admits**, and writes the table [dialect.py](dialect.py) encodes from. It is the one
module of this pair that holds a question, and the question is one sentence: an
enumeration of the model's spellings over-approximates, so which of the forms it spells
may an assembler emit?

## The three kinds of guard, and the one answer each gets

183 of the model's 253 `encdec` clauses carry a `when`, over 51 distinct guard texts, and
they split three ways. Nothing here matches those texts: each is parsed by
[sailexpr.py](sailexpr.py) and evaluated against the model's own definitions, so the
split below is a property of what the evaluation *reaches* rather than a list somebody
transcribed.

- **Extension presence resolves.** `currentlyEnabled(Ext_Zbc)` walks the model's own
  clause chain down to `config extensions.Zbc.supported` and answers. This is the half
  that decides, and it decides against the shipped configurations rather than in the
  abstract: `clmulr` is guarded on `Zbc` alone and is refused, where `clmul` and `clmulh`
  are `Zbc | Zbkc` and are admitted, which reproduces the hand-written table's own
  exclusion without being told about it.
- **Machine state does not resolve, and must not be guessed at.** `currentlyEnabled` is
  `hartSupports & misa[X] == 0b1`, so *enablement* is a function of a CSR and an
  assembler can only ever decide *presence*. A guard reaching a register answers
  `UNKNOWN`, the form is admitted, and the machine traps what it will not decode, which
  is this table's own stated division of labour: what a row can express is the encoder's
  business and what an encoding means is the machine's.
- **A joint constraint over the encoding's own fields decides outright.** The model
  spells a load `"l" ^ width_mnemonic(width) ^ maybe_u(is_unsigned)` and rules out the
  unsigned doubleword in `valid_load_encdec` rather than in the spelling, so an
  enumeration hands back `ldu`, which the model decodes nowhere. Every field the mnemonic
  and the encoding fix is bound into the environment before the guard is evaluated, so
  that guard is a fact about the row and `ldu` is refused by arithmetic.

## Fail-closed, and why an assembler's default is the opposite of a census's

A guard whose text the evaluator does not reach **refuses** the form. For a census that
would be the wrong default: an enumeration that drops what it cannot read reports a
surface smaller than the model's and calls it complete. For an assembler it is the only
safe one, because the two failures are not symmetric. A mnemonic refused that the model
would have decoded is a program that does not assemble, said out loud at the line that
wrote it. A mnemonic admitted that the model cannot decode is an image that assembles
clean, loads, and traps somewhere else entirely. K-67 and K-75 are the same reading one
level up.

## The two questions this module leaves open, and does not close by fiat

**Which configuration admission is taken at is fixed by no artifact.** The dialect is
the frozen profile's and is one ISA across all five core classes, while `currentlyEnabled`
is per-composition and the three shipped configurations differ on six vector-crypto keys.
An assembler serving every class wants the union, so the union is what is taken here and
`CONFIGURATIONS` names every file it is taken over; nothing in the register says so, and
the checklist cell reports it as open rather than settling it.

**Whether this table carries the whole admitted surface or a declared scope** is fixed by
no artifact either. The hand-written table scoped the vector rows deliberately, on the
ground that a row nothing in the corpus writes is a row nothing checks; generation
removes that ground, the cost that decision was against having been the transcription.
The whole admitted surface is carried, and the reversal is reported rather than performed
silently.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

from . import config, encdec, sailexpr
from .jsonc import Json
from .sailbundle import Bundle
from .sailexpr import UNKNOWN, Bits, Environment, Sym, UnresolvedError, Value

# Tracked beside the bundle, and generated from it. Under `tools/generated/` for the
# reason that directory exists: `model/` is `-text` and vendored byte-identically from
# its upstream pin, so a generated artifact there would break both properties at once.
TABLE = "tools/generated/dialect-table.json"

# The only shape this reader and its writer share.
VERSION = 1

# The compositions admission is taken over, and the union is over exactly these. Named
# as a table rather than globbed, because a fourth configuration appearing in that
# directory is a decision somebody makes and not a file this quietly starts admitting on.
CONFIGURATIONS: Final[tuple[str, ...]] = (
    "model/config/verifiedos.json",
    "model/config/verifiedos-v.json",
    "model/config/verifiedos-rot.json",
)

# Applications this evaluator answers itself, because they are the language's rather than
# the model's: a width change and a constructor wrapper both leave the value alone at the
# arithmetic this admission does.
_TRANSPARENT: Final[frozenset[str]] = frozenset(
    {"zero_extend", "sign_extend", "unsigned", "signed", "truncate", "Regidx",
     "Vregidx", "bits_of", "regidx_bits", "vregidx_bits"})


class RefusedError(RuntimeError):
    """One form this policy does not admit, carrying the reason a person needs."""


# How the model's own operand printers land in this assembler's operand vocabulary. The
# whole printed surface is 22 applications and six literals over 218 clauses, so this is
# a closed set rather than a growing one, and a printer absent from it refuses the row.
#
# `cap_reg_name` and `reg_name` are one kind here and two in the model, which is not a
# conflation: a register is one register with two readings, and the capability spelling
# is a reading rather than a file (R-15-007i).
SPELLINGS: Final[dict[str, str]] = {
    "reg_name": "reg", "cap_reg_name": "reg", "vreg_name": "vreg",
    "maybe_vmask": "vm", "csr_name_map": "csr", "scr_name_map": "scr",
    "vtype_assembly": "imm",
}

# The two constructors whose immediate is a displacement from the instruction's own
# address, which is the one fact about an operand the *encoding* does not carry: the
# model states it in the execute clause, where the value is added to `PC`, and the
# encoding of a branch is the same whatever the value means. So an assembler that wants
# to be handed a label rather than a displacement has to be told, here, which two forms
# take one. Signedness rides with it: a displacement is signed by construction, where
# `CJAL`'s printer spells its twenty-one bits unsigned.
PC_RELATIVE: Final[frozenset[str]] = frozenset({"BTYPE", "CJAL"})

# The bracketed shapes, each as the tokens between the commas. Every one is a single
# source operand that the parser flattens into several encoded values, in this order.
_SHAPES: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("imm", "(", "reg", ")"), "mem"),
    (("(", "reg", ")"), "mem0"),
    (("reg", "[", "reg", "<<", "imm", "]"), "index"),
)

_IMMEDIATE = re.compile(r"^(hex_bits|hex_bits_signed|dec_bits)_(\d+)$")

# How the model's own `execute` clause reads a field, which is where an operand's
# admitted range actually comes from. The `encdec` clause states the field's *width* and
# every pattern of that width decodes, so the encoding says nothing about the range; the
# `assembly` printer says how a disassembler *displays* it, which is a different
# question again and answers it wrongly twice on this model (`lui`'s upper immediate is
# printed signed and materialized above the signed half; `cincoffsetimm`'s is printed
# unsigned and is an offset increment). The execute clause is the one place the model
# says which reading is meant, and it says so in one word.
_READING: Final[tuple[tuple[str, bool], ...]] = (
    ("sign_extend", True), ("signed", True),
    ("zero_extend", False), ("unsigned", False),
)


@dataclass(frozen=True)
class Slot:
    """One operand as the encoder needs it: what it is, how wide, and where it goes."""

    kind: str
    name: str
    width: int
    signed: bool
    align: int
    pieces: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True)
class Row:
    """One admitted mnemonic, as the generated artifact carries it."""

    form: encdec.Form
    requires: tuple[tuple[str, str, tuple[int, ...]], ...]
    signature: tuple[str, ...]
    slots: tuple[Slot, ...]


class Facts:
    """The parts of the environment that do not depend on the form being decided.

    Held apart because they are expensive and constant: the scattered-member reading
    walks every function body in the model, and building it per form rather than per run
    is the difference between a gate that costs four seconds and one that costs a
    fraction of one. The state-boundedness answers are memoized here for the same
    reason and are sound to share, being a property of the model rather than of a row.
    """

    def __init__(self, bundle: Bundle, root: Path) -> None:
        self.bundle = bundle
        self.registers = bundle.registers()
        self.enums = bundle.enum_members()
        self.scattered = bundle.scattered_members()
        self.configs = [root / name for name in CONFIGURATIONS]
        self.stateful: dict[str, bool] = {}
        self.executes = bundle.constructor_bodies("execute")
        self.decided: dict[tuple[str, tuple[tuple[str, str], ...]],
                           tuple[tuple[str, str, tuple[int, ...]], ...] | str] = {}


class _Model(Environment):
    """The model's own definitions, as the environment a guard is evaluated in.

    Built once per form over one shared `Facts`, and asked many times. The recursion
    guard is not a nicety: `currentlyEnabled(Ext_Zvfhmin)` reaches
    `currentlyEnabled(Ext_Zvfh)` which reaches `Ext_Zve32f`, and a cycle in a chain like
    that would be a stack overflow reported as a crash in the checker rather than as a
    defect in the model.
    """

    def __init__(self, facts: Facts, bindings: dict[str, Value] | None = None) -> None:
        self.facts = facts
        self.bundle = facts.bundle
        self.bindings = bindings or {}
        self.registers = facts.registers
        self.enums = facts.enums
        self.scattered = facts.scattered
        self._open: set[str] = set()
        self._configs = facts.configs

    # -- the Environment protocol ----------------------------------------------------

    @override
    def is_state(self, name: str) -> bool:
        return name in self.registers

    @override
    def value_of(self, name: str) -> Value:
        if name in self.bindings:
            return self.bindings[name]
        if name in self.enums:
            enum, ordinal = self.enums[name]
            return Sym(name, enum, ordinal)
        if name in self.scattered:
            return Sym(name, "scattered", sailexpr.UNORDERED)
        if self.bundle.has("lets", name):
            return self._nested(name, self.bundle.let_value(name))
        raise UnresolvedError(f"nothing in the model defines {name}")

    @override
    def call(self, name: str, args: list[Value]) -> Value:
        if name in _TRANSPARENT:
            if len(args) != 1:
                raise UnresolvedError(f"{name} takes one argument here")
            return args[0]
        if self.bundle.has("mappings", name):
            return self._mapped(name, args)
        if self.bundle.has("functions", name):
            return self._applied(name, args)
        raise UnresolvedError(f"nothing in the model defines {name}()")

    @override
    def config(self, path: str) -> Value:
        """One configuration key, read across every shipped composition.

        The union, and it is a decision this module's docstring states rather than a
        convenience: a boolean is true where any composition sets it, a number takes its
        largest, and a value naming an enum member takes the member the model's own
        declaration orders highest. All three are the widest admission the compositions
        between them justify. A key no composition carries raises, because a guard
        resting on a key that is not there is a guard about nothing.
        """
        seen: list[Json] = [found for path_ in self._configs
                            if (found := config.value(path_, *path.split("."))) is not None]
        if not seen:
            raise UnresolvedError(f"no shipped configuration carries {path}")
        if all(isinstance(value, bool) for value in seen):
            return any(bool(value) for value in seen)
        numbers = [value for value in seen
                   if isinstance(value, int) and not isinstance(value, bool)]
        if len(numbers) == len(seen):
            return max(numbers)
        return self._widest(seen, path)

    def _widest(self, seen: list[Json], path: str) -> Value:
        """A key whose values name enum members, as the highest member named.

        RefusedError where any value is not a member the model declares: a configuration
        naming something this reader cannot place in the enum's order is one the union
        cannot be taken over, and taking the first would make the answer depend on the
        order `CONFIGURATIONS` happens to list.
        """
        found: list[Sym] = []
        for value in seen:
            member = self.enums.get(str(value)) if isinstance(value, str) else None
            if member is None:
                raise UnresolvedError(f"the shipped configurations set {path} to {value!r}, "
                                 f"which names no enum member")
            found.append(Sym(str(value), member[0], member[1]))
        return max(found, key=lambda sym: sym.ordinal)

    @override
    def size_of(self, name: str) -> Value:
        text = self.bundle.type_text(name)
        _, _, body = text.partition("=")
        if not body.strip():
            raise UnresolvedError(f"the type {name} states no value")
        return self._nested(f"type {name}", body)

    # -- resolution ------------------------------------------------------------------

    def _nested(self, what: str, text: str) -> Value:
        if what in self._open:
            raise UnresolvedError(f"{what} is defined in terms of itself")
        self._open.add(what)
        try:
            return sailexpr.evaluate(sailexpr.parse(text), self)
        finally:
            self._open.discard(what)

    def _mapped(self, name: str, args: list[Value]) -> Value:
        """One mapping applied, by looking the argument up among its arms.

        Either side may be the key, because a Sail mapping is bidirectional and is
        written in whichever direction reads better: `vlewidth_pow` writes
        `VLE8 <-> 3`, and asking it for the exponent means matching on the left. So each
        arm is tried both ways round and the *other* side is evaluated, which also
        removes the restriction to bit and string literals that the encoding reading
        needs and this one does not.
        """
        if len(args) != 1:
            raise UnresolvedError(f"{name} is applied to {len(args)} arguments")
        for clause in self.bundle.clauses(name):
            for key_side, value_side in (("left", "right"), ("right", "left")):
                key = encdec.arm_key(clause.get(key_side))
                if key is None or not _matches(key, args[0]):
                    continue
                node = clause.get(value_side)
                if not isinstance(node, dict) or node.get("type") != "literal":
                    continue
                return sailexpr.evaluate(
                    sailexpr.parse(str(node.get("value", ""))), _Nothing())
        raise UnresolvedError(f"{name} has no arm this reader matches to {args[0]!r}")

    def _applied(self, name: str, args: list[Value]) -> Value:
        """One function applied.

        The clause is chosen by its pattern where the function is a family over an enum,
        which is what `hartSupports` and `currentlyEnabled` are; a single-clause function
        takes its one clause and binds its parameters positionally.
        """
        clauses = self.bundle.function_bodies(name)
        if not clauses:
            raise UnresolvedError(f"{name} has no clause this reader can read")
        if len(clauses) > 1:
            wanted = args[0].name if args and isinstance(args[0], Sym) else None
            picked = [c for c in clauses if c[0] == (wanted,)]
            if len(picked) != 1:
                raise UnresolvedError(f"{name} has no single clause for {wanted}")
            return self._body(f"{name}({wanted})", picked[0][1], {})
        names, body, _site = clauses[0]
        if len(names) != len(args):
            raise UnresolvedError(f"{name} names {len(names)} parameters and is applied to "
                             f"{len(args)}")
        return self._body(name, body, dict(zip(names, args, strict=True)))

    def _state_bound(self, text: str, seen: set[str] | None = None) -> bool:
        """Whether an expression's value depends on machine state, through any depth.

        A name scan closed over the call graph, and it is a scan rather than a walk for
        one reason: what is being asked is whether the value depends on state, and a
        register read is spelled with the register's own name and nothing else in Sail
        spells it, so the names *are* the evidence. Nothing else here is a scan.

        Transitive because one level is not the question. `keccak_unit_present()` reads
        no register and calls `this_core_class()`, which reads the core roster; a
        one-level test reports it unreadable, which would refuse the whole Keccak
        surface for the wrong reason and say so in the wrong words. The two verdicts
        this separates, *cannot decide* and *cannot read*, are the ones this module
        turns on.
        """
        seen = set() if seen is None else seen
        words = _words(text)
        if words & self.registers:
            return True
        for name in sorted(words - seen):
            if name in seen or not self.bundle.has("functions", name):
                continue
            remembered = self.facts.stateful.get(name)
            if remembered is not None:
                if remembered:
                    return True
                continue
            seen.add(name)
            found = any(self._state_bound(body, seen)
                        for _names, body, _site in self.bundle.function_bodies(name))
            self.facts.stateful[name] = found
            if found:
                return True
        return False

    def _body(self, what: str, text: str, extra: dict[str, Value]) -> Value:
        """One function body, with the machine-state test taken *before* the parse.

        A body reading a register is machine state whatever else it does, and answering
        that before parsing is what keeps `get_sew()` from being reported as an
        expression this reader does not cover: it is not, and the distinction between
        *cannot decide* and *cannot read* is the one this whole module turns on.
        """
        if self._state_bound(text):
            return UNKNOWN
        if what in self._open:
            raise UnresolvedError(f"{what} is defined in terms of itself")
        self._open.add(what)
        nested = _Model(self.facts, {**self.bindings, **extra})
        nested._open = self._open
        try:
            return sailexpr.evaluate(sailexpr.parse(text), nested)
        finally:
            self._open.discard(what)


def _words(text: str) -> frozenset[str]:
    """Every identifier a body spells, which is the whole of what a name scan needs."""
    out: set[str] = set()
    current = ""
    for char in text:
        if char.isalnum() or char == "_":
            current += char
            continue
        if current:
            out.add(current)
        current = ""
    if current:
        out.add(current)
    return frozenset(out)


def _matches(key: tuple[object, ...], value: Value) -> bool:
    if len(key) != 2:
        return False
    spelled = str(key[1])
    if key[0] == "id":
        return isinstance(value, Sym) and value.name == spelled
    try:
        wanted = sailexpr.evaluate(sailexpr.parse(spelled), _Nothing())
    except UnresolvedError:
        return False
    return _same(wanted, value)


def _same(left: Value, right: Value) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, _Unknownish) or isinstance(right, _Unknownish):
        return False
    return _as_int(left) == _as_int(right)


_Unknownish = type(UNKNOWN)


def _as_int(value: Value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Bits):
        return value.value
    if isinstance(value, Sym):
        return value.ordinal
    return None


class _Nothing(Environment):
    """An environment that defines nothing, for reading a literal out of an arm key."""

    @override
    def is_state(self, name: str) -> bool:
        return False

    @override
    def value_of(self, name: str) -> Value:
        raise UnresolvedError(f"{name} is not a literal")

    @override
    def call(self, name: str, args: list[Value]) -> Value:
        raise UnresolvedError(f"{name}() is not a literal")

    @override
    def config(self, path: str) -> Value:
        raise UnresolvedError(f"config {path} is not a literal")

    @override
    def size_of(self, name: str) -> Value:
        raise UnresolvedError(f"sizeof({name}) is not a literal")


# --- the policy ---------------------------------------------------------------------


def admit(form: encdec.Form, facts: Facts) -> Row:
    """One form, admitted or `RefusedError` with the reason.

    The bindings the row fixed go into the environment first, which is what makes a
    guard over the encoding's own fields a fact about *this* row: without them
    `valid_load_encdec(width, is_unsigned)` is a statement about a clause and `ldu` walks
    straight through it.
    """
    signature, slots = _spelling(form, facts.executes.get(form.ctor, ""))
    return Row(form=form, requires=_guarded(form, facts), signature=signature,
               slots=slots)


def _guarded(form: encdec.Form, facts: Facts
             ) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    """The guard's verdict for this row, memoized on the guard and what it reads.

    Keyed on the bindings the guard's own text *names* rather than on all of them,
    which is the whole of what makes the memo worth having: 495 rows share one vector
    guard and differ only in a `funct6` that guard never mentions, so a key over every
    binding would collapse nothing at all.
    """
    relevant = tuple((name, spelled) for name, spelled in form.bindings
                     if name in _words(form.guard))
    key = (form.guard, relevant)
    remembered = facts.decided.get(key)
    if isinstance(remembered, str):
        raise RefusedError(remembered)
    if remembered is not None:
        return remembered
    bound: dict[str, Value] = {}
    for name, spelled in form.bindings:
        try:
            bound[name] = sailexpr.evaluate(sailexpr.parse(spelled), _Nothing())
        except UnresolvedError:
            member = facts.enums.get(spelled)
            bound[name] = Sym(spelled, member[0], member[1]) if member \
                else Sym(spelled, "scattered", sailexpr.UNORDERED)
    env = _Model(facts, bound)
    requires: list[tuple[str, str, tuple[int, ...]]] = []
    try:
        for text in _conjuncts(form.guard):
            _decide(text, env, form, requires)
    except (RefusedError, UnresolvedError) as exc:
        facts.decided[key] = str(exc)
        raise
    facts.decided[key] = tuple(requires)
    return tuple(requires)


def _spelling(form: encdec.Form,
              execute: str) -> tuple[tuple[str, ...], tuple[Slot, ...]]:
    """How a program writes this form, and where each thing it writes lands.

    The two are returned together because they have to agree: the parser fills the
    signature in source order and hands the encoder a flat list of values, and a source
    operand of a bracketed shape contributes several. A form whose spelling this
    vocabulary cannot read is `RefusedError` rather than carried with a signature guessed at,
    which is the same fail-closed reading the guards get and for the same reason.
    """
    kinds: list[str] = []
    at = 0
    for group in _groups(form.syntax):
        tail = ["vm"] if group and group[-1] == "maybe_vmask" else []
        head = group[:-1] if tail else group
        if head:
            kinds.append(_shape(head, form))
        kinds += tail
    slots: list[Slot] = []
    for operand in form.operands:
        slots.append(_slot(operand, form, execute))
        at += 1
    if at != len(form.operands):
        raise RefusedError("the printed run and the encoded operands do not correspond")
    return tuple(kinds), tuple(slots)


def _groups(syntax: tuple[str, ...]) -> list[list[str]]:
    """The printed run split at its commas, one group per source operand."""
    out: list[list[str]] = []
    current: list[str] = []
    for part in syntax:
        if part == ",":
            out.append(current)
            current = []
        else:
            current.append(part)
    out.append(current)
    return [group for group in out if group]


def _shape(group: list[str], form: encdec.Form) -> str:
    """One printed group as the operand kind a program writes."""
    if len(group) == 1:
        printer = group[0]
        if printer in SPELLINGS:
            return SPELLINGS[printer]
        if _IMMEDIATE.match(printer):
            return "sym" if form.ctor in PC_RELATIVE else "imm"
        if printer == "v0":
            # The model prints the mask register as a literal where the form takes no
            # `vm` bit, so a program writes `v0` and the encoding carries nothing.
            return "v0"
        raise RefusedError(f"the operand printer {printer} is not in this "
                           f"assembler's vocabulary")
    reduced = tuple(_reduce(token) for token in group)
    for shape, kind in _SHAPES:
        if reduced == shape:
            return kind
    raise RefusedError(f"the printed shape {' '.join(group)} is not one this assembler "
                  f"writes")


def _reduce(printer: str) -> str:
    if printer in SPELLINGS:
        return SPELLINGS[printer]
    return "imm" if _IMMEDIATE.match(printer) else printer


def _slot(operand: encdec.Operand, form: encdec.Form, execute: str) -> Slot:
    """One encoded operand: its kind, its width, and how a value reaches the word."""
    found = _IMMEDIATE.match(operand.printer)
    kind = SPELLINGS.get(operand.printer, "imm" if found else "")
    if not kind:
        raise RefusedError(f"the operand printer {operand.printer} is not in this "
                      f"assembler's vocabulary")
    # Only an immediate has a reading at all. A register number, a CSR address and a
    # mask bit are indices into something, so the question does not arise for them and
    # asking it of the execute clause would answer about the value the index selects.
    signed = False
    if kind == "imm":
        derived = _reading(operand.name, execute)
        signed = derived if derived is not None \
            else bool(found and found.group(1) == "hex_bits_signed")
    if kind == "imm" and form.ctor in PC_RELATIVE:
        kind, signed = "sym", True
    return Slot(kind=kind, name=operand.name, width=operand.width, signed=signed,
                align=operand.align, pieces=tuple(
                    (piece.word_hi, piece.word_lo, piece.src_hi, piece.src_lo)
                    for piece in operand.pieces))


def _reading(name: str, execute: str) -> bool | None:
    """How the form's own `execute` clause reads this field, where it says.

    A scan for one call over one name, and it is a scan for the same reason the
    machine-state test is: what is being asked is which of two words the body spells
    around the field, and the words are the evidence. `None` where the clause does not
    widen the field at all, which is every field used as an index or a register number,
    and the printer's reading stands there.
    """
    for call, verdict in _READING:
        needle = f"{call}({name}"
        at = execute.find(needle)
        # Bounded on both sides. `signed` is a substring of `unsigned` and the name is a
        # prefix of longer names, so a scan without either boundary reads `unsigned(vs2)`
        # as a signed reading of `vs2` and refuses every vector register above fifteen.
        while at >= 0:
            before = execute[at - 1] if at else " "
            after = execute[at + len(needle)] if at + len(needle) < len(execute) else " "
            if not (before.isalnum() or before == "_") and not after.isalnum() \
                    and after != "_":
                return verdict
            at = execute.find(needle, at + 1)
    return None


def _conjuncts(guard: str) -> list[str]:
    """A guard's top-level conjuncts, each decided on its own.

    Split rather than evaluated whole, because a conjunct that is a constraint on an
    operand is not a truth value at all: it is a condition the encoder carries to the
    site, and only a per-conjunct reading can tell it apart from a conjunct that is
    simply false.
    """
    if not guard.strip():
        return []
    node = sailexpr.parse(guard)
    out: list[str] = []
    _flatten(node, guard, out)
    return out


def _flatten(node: sailexpr.Node, text: str, out: list[str]) -> None:
    if node.kind == "binary" and node.text == "&":
        _flatten(node.parts[0], text, out)
        _flatten(node.parts[1], text, out)
        return
    out.append(_render(node))


def _render(node: sailexpr.Node) -> str:
    """One conjunct back as text, for the residual reading and for a finding's wording.

    A re-rendering rather than a slice of the source, because the parse has already
    dropped the parentheses a slice would have to balance.
    """
    if node.kind in ("number", "bits", "boolean", "name"):
        return node.text
    if node.kind == "config":
        return f"config {node.text}"
    if node.kind == "sizeof":
        return f"sizeof({node.text})"
    if node.kind == "not":
        return f"not({_render(node.parts[0])})"
    if node.kind == "negate":
        return f"-{_render(node.parts[0])}"
    if node.kind == "binary":
        return f"({_render(node.parts[0])} {node.text} {_render(node.parts[1])})"
    if node.kind == "apply":
        return f"{node.text}({', '.join(_render(p) for p in node.parts)})"
    if node.kind == "if":
        return (f"if {_render(node.parts[0])} then {_render(node.parts[1])} "
                f"else {_render(node.parts[2])}")
    if node.kind == "match":
        arms = ", ".join(f"{p.text} => {_render(p.parts[0])}" for p in node.parts[1:])
        return f"match {_render(node.parts[0])} {{{arms}}}"
    return node.kind


def _decide(text: str, env: _Model, form: encdec.Form,
            requires: list[tuple[str, str, tuple[int, ...]]]) -> None:
    """One conjunct: admitted, refused, or carried to the site as a requirement."""
    node = sailexpr.parse(text)
    try:
        verdict = sailexpr.evaluate(node, env)
    except UnresolvedError as exc:
        found = _residual(node, env, form)
        if found is None:
            raise RefusedError(f"the guard `{text}` does not resolve: {exc}") from None
        requires.append(found)
        return
    if verdict is False:
        raise RefusedError(f"the guard `{text}` is false at the shipped configurations")


def _residual(node: sailexpr.Node, env: _Model, form: encdec.Form
              ) -> tuple[str, str, tuple[int, ...]] | None:
    """A conjunct that is a condition on one *operand*, as a requirement the encoder can
    check at the site.

    Two shapes and no more, each fail-closed. `cd != zreg` is a value the operand may not
    take, and `keccak_valid_rounds(rnd)` is a disjunction of the values it may. Both are
    conditions the hand-written table carried as one-off rules with the clause quoted
    beside them; here they are the clause.
    """
    names = {operand.name for operand in form.operands}
    if node.kind == "binary" and node.text in ("!=", "=="):
        found = _against(node, env, names)
        if found is not None:
            name, value = found
            return ("ne" if node.text == "!=" else "in", name, (value,))
    if node.kind == "binary" and node.text == "|":
        left = _residual(node.parts[0], env, form)
        right = _residual(node.parts[1], env, form)
        if left is not None and right is not None and left[0] == right[0] == "in" \
                and left[1] == right[1]:
            return ("in", left[1], tuple(sorted(set(left[2]) | set(right[2]))))
        return None
    if node.kind == "apply" and len(node.parts) == 1 \
            and node.parts[0].kind == "name" and node.parts[0].text in names:
        return _through(node, env, form)
    return None


def _against(node: sailexpr.Node, env: _Model,
             names: set[str]) -> tuple[str, int] | None:
    """A comparison between one named operand and one value this lane can compute."""
    for free, other in ((node.parts[0], node.parts[1]), (node.parts[1], node.parts[0])):
        if free.kind != "name" or free.text not in names:
            continue
        try:
            value = _as_int(sailexpr.evaluate(other, env))
        except UnresolvedError:
            return None
        if value is not None:
            return free.text, value
    return None


def _through(node: sailexpr.Node, env: _Model,
             form: encdec.Form) -> tuple[str, str, tuple[int, ...]] | None:
    """One predicate over an operand, read through the model's own definition of it."""
    operand = node.parts[0].text
    clauses = env.bundle.function_bodies(node.text) \
        if env.bundle.has("functions", node.text) else []
    if len(clauses) != 1 or len(clauses[0][0]) != 1:
        return None
    (parameter,), body, _site = clauses[0]
    try:
        inner = sailexpr.parse(body.replace(parameter, operand))
    except UnresolvedError:
        return None
    return _residual(inner, env, form)


# --- the artifact --------------------------------------------------------------------


def generate(bundle: Bundle, root: Path) -> tuple[dict[str, Row], list[str], list[str]]:
    """Every admitted row, the clauses this lane could not read, and every refusal.

    A mnemonic two admitted rows spell is refused outright and named: an assembler with
    an ambiguous mnemonic is worse than one without it, because the ambiguity is
    resolved silently by whichever row was walked last.
    """
    surface = encdec.Surface(bundle)
    forms, residue = surface.forms()
    facts = Facts(bundle, root)
    admitted: dict[str, list[Row]] = {}
    refused: dict[str, list[str]] = {}
    for form in forms:
        try:
            row = admit(form, facts)
        except (RefusedError, UnresolvedError, encdec.UnreadableError) as exc:
            refused.setdefault(form.mnemonic, []).append(str(exc))
            continue
        admitted.setdefault(form.mnemonic, []).append(row)
    rows: dict[str, Row] = {}
    notes: list[str] = []
    for mnemonic, found in sorted(admitted.items()):
        distinct = {(row.form.word, row.form.mask) for row in found}
        if len(distinct) > 1:
            notes.append(f"{mnemonic}: {len(distinct)} admitted encodings, so the "
                         f"mnemonic is ambiguous and carries none")
            continue
        rows[mnemonic] = found[0]
    for mnemonic, reasons in sorted(refused.items()):
        if mnemonic not in rows:
            notes.append(f"{mnemonic}: {reasons[0]}")
    return rows, residue, notes


def render(rows: dict[str, Row], residue: list[str], notes: list[str]) -> str:
    """The generated artifact, one admitted row per line.

    Line-oriented on purpose: the rule that holds this file reports a byte difference by
    the line it falls on, and a pretty-printed object would report every difference at
    line 3 of a file nobody can diff.
    """
    head = json.dumps({
        "version": VERSION,
        "generator": "vos.dialectgen",
        "configurations": list(CONFIGURATIONS),
        "admitted": len(rows),
        "unread": len(residue),
        "refused": len(notes),
    }, sort_keys=True)
    out = [f'{{"header": {head},', '"rows": {']
    lines = [f"{json.dumps(name)}: {json.dumps(_row(row), sort_keys=True)}"
             for name, row in sorted(rows.items())]
    out += [line + "," for line in lines[:-1]] + lines[-1:]
    out += ["},", f'"unread": {json.dumps(sorted(residue), indent=0)},',
            f'"refused": {json.dumps(sorted(notes), indent=0)}}}']
    return "\n".join(out) + "\n"


def _row(row: Row) -> dict[str, Json]:
    form = row.form
    return {
        "ctor": form.ctor,
        "site": str(form.site),
        "word": form.word,
        "mask": form.mask,
        "guard": form.guard,
        "syntax": list(form.syntax),
        "signature": list(row.signature),
        "slots": [{"kind": slot.kind, "name": slot.name, "width": slot.width,
                   "signed": slot.signed, "align": slot.align,
                   "pieces": [list(piece) for piece in slot.pieces]}
                  for slot in row.slots],
        "requires": [[kind, name, list(values)] for kind, name, values in row.requires],
    }


def emit(bundle: Bundle, root: Path) -> str:
    """The whole artifact, for a caller that only wants the bytes."""
    rows, residue, notes = generate(bundle, root)
    return render(rows, residue, notes)
