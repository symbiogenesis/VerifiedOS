# SPDX-License-Identifier: Apache-2.0
"""Generate the frozen dialect's encoder table ([tools/generated/dialect-table.json](../generated/dialect-table.json))
for [dialect.py](dialect.py) from the Sail model bundle.

Reads instruction forms via [encdec.py](encdec.py) and evaluates each `encdec` guard
via [sailexpr.py](sailexpr.py) against the union of `CONFIGURATIONS`:
- **Extension presence**: resolves against `CONFIGURATIONS` (`True` admits, `False` refuses).
- **Machine state**: guards that read registers evaluate to `UNKNOWN` and admit the form
  (runtime state enablement is decided by hardware, not the assembler).
- **Field constraints**: fixed mnemonic/encoding bindings are substituted before guard
  evaluation so invalid field combinations (such as `ldu`) evaluate to `False`.
  Per-operand conditions (`!=`, `==`, or unary predicates) become site-checked `requires`.
- **Fail-closed default**: any guard that cannot be resolved or converted into an operand
  requirement raises `RefusedError`.
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

TABLE = "tools/generated/dialect-table.json"

VERSION = 1

# Shipped model configurations whose union defines the admitted assembler surface.
CONFIGURATIONS: Final[tuple[str, ...]] = (
    "model/config/verifiedos.json",
    "model/config/verifiedos-v.json",
    "model/config/verifiedos-rot.json",
)

# Width/conversion helpers and index wrappers treated as identity functions during guard evaluation.
_TRANSPARENT: Final[frozenset[str]] = frozenset(
    {"zero_extend", "sign_extend", "unsigned", "signed", "truncate", "Regidx",
     "Vregidx", "bits_of", "regidx_bits", "vregidx_bits"})


class RefusedError(RuntimeError):
    """Raised when an instruction form is rejected by the admission policy."""


# Mapping from Sail operand printers to [dialect.py](dialect.py) operand kinds.
SPELLINGS: Final[dict[str, str]] = {
    "reg_name": "reg", "cap_reg_name": "reg", "vreg_name": "vreg",
    "maybe_vmask": "vm", "csr_name_map": "csr", "scr_name_map": "scr",
    "vtype_assembly": "imm",
}

# Constructors whose immediate operand is a signed PC-relative branch/jump displacement.
PC_RELATIVE: Final[frozenset[str]] = frozenset({"BTYPE", "CJAL"})

# Bracketed token sequences that collapse into a single composite source operand kind.
_SHAPES: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("imm", "(", "reg", ")"), "mem"),
    (("(", "reg", ")"), "mem0"),
    (("reg", "[", "reg", "<<", "imm", "]"), "index"),
)

_IMMEDIATE = re.compile(r"^(hex_bits|hex_bits_signed|dec_bits)_(\d+)$")

# Extension calls in `execute` bodies that determine whether an immediate is signed.
_READING: Final[tuple[tuple[str, bool], ...]] = (
    ("sign_extend", True), ("signed", True),
    ("zero_extend", False), ("unsigned", False),
)


@dataclass(frozen=True)
class Slot:
    """Encoded operand descriptor: kind, field name, bit width, signedness, alignment, and bit pieces."""

    kind: str
    name: str
    width: int
    signed: bool
    align: int
    pieces: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True)
class Row:
    """Admitted mnemonic row for the generated encoder table."""

    form: encdec.Form
    requires: tuple[tuple[str, str, tuple[int, ...]], ...]
    signature: tuple[str, ...]
    slots: tuple[Slot, ...]


class Facts:
    """Model-wide definitions and memoized guard verdicts shared across all forms in a run."""

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
    """Sail evaluation environment backed by `Facts` and per-form field `bindings`."""

    def __init__(self, facts: Facts, bindings: dict[str, Value] | None = None) -> None:
        self.facts = facts
        self.bundle = facts.bundle
        self.bindings = bindings or {}
        self.registers = facts.registers
        self.enums = facts.enums
        self.scattered = facts.scattered
        self._open: set[str] = set()
        self._configs = facts.configs

    # -- Environment protocol --------------------------------------------------------

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
        """Resolve `config <path>` across `CONFIGURATIONS` by taking the widest value (`any` for bool, `max` for int/enum ordinal)."""
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
        """Return the highest-ordinal `Sym` among enum member names in `seen`."""
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
        """Evaluate a 1-argument mapping call by matching `args[0]` against either side of its clauses."""
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
        """Evaluate a function call by selecting a matching enum-pattern clause or binding positional parameters."""
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
        """Return whether `text` transitively references any register in `self.registers`."""
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
        """Evaluate function body `text`, returning `UNKNOWN` immediately if `_state_bound(text)` holds."""
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
    """Return the set of identifier tokens in `text`."""
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
    """Empty `Environment` for evaluating standalone literals in mapping arm keys."""

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


# --- admission policy ---------------------------------------------------------------


def admit(form: encdec.Form, facts: Facts) -> Row:
    """Admit `form` as a `Row`, or raise `RefusedError` if its spelling or guard is rejected."""
    signature, slots = _spelling(form, facts.executes.get(form.ctor, ""))
    return Row(form=form, requires=_guarded(form, facts), signature=signature,
               slots=slots)


def _guarded(form: encdec.Form, facts: Facts
             ) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    """Evaluate `form.guard` (memoized by referenced bindings) and return any residual operand requirements."""
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
    """Derive the source operand `signature` and encoded `Slot` tuple for `form`."""
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
    """Split `syntax` tokens on `","` into per-source-operand groups."""
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
    """Map a single comma-delimited token `group` to its source operand kind."""
    if len(group) == 1:
        printer = group[0]
        if printer in SPELLINGS:
            return SPELLINGS[printer]
        if _IMMEDIATE.match(printer):
            return "sym" if form.ctor in PC_RELATIVE else "imm"
        if printer == "v0":
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
    """Build the encoded `Slot` for `operand`, deriving immediate signedness from `execute` or its printer."""
    found = _IMMEDIATE.match(operand.printer)
    kind = SPELLINGS.get(operand.printer, "imm" if found else "")
    if not kind:
        raise RefusedError(f"the operand printer {operand.printer} is not in this "
                      f"assembler's vocabulary")
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
    """Return whether `execute` widens `name` via `sign_extend`/`signed` (`True`) or `zero_extend`/`unsigned` (`False`)."""
    for call, verdict in _READING:
        needle = f"{call}({name}"
        at = execute.find(needle)
        while at >= 0:
            before = execute[at - 1] if at else " "
            after = execute[at + len(needle)] if at + len(needle) < len(execute) else " "
            if not (before.isalnum() or before == "_") and not after.isalnum() \
                    and after != "_":
                return verdict
            at = execute.find(needle, at + 1)
    return None


def _conjuncts(guard: str) -> list[str]:
    """Split `guard` on top-level `&` operators into rendered conjunct strings."""
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
    """Render a parsed `sailexpr.Node` back to canonical expression text."""
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
    """Evaluate conjunct `text`, appending operand constraints to `requires` or raising `RefusedError`."""
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
    """Convert an unresolved operand guard `node` into a `("ne" | "in", operand_name, values)` requirement."""
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
    """Extract `(operand_name, int_value)` from a binary comparison between an operand in `names` and a constant."""
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
    """Inline a single-clause unary function call over an operand and extract its `_residual` requirement."""
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


# --- table generation and rendering -------------------------------------------------


def generate(bundle: Bundle, root: Path) -> tuple[dict[str, Row], list[str], list[str]]:
    """Return `(admitted_rows, unread_clauses, refusal_notes)` for `bundle`, rejecting ambiguous mnemonics."""
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
    """Serialize `rows`, `residue`, and `notes` as line-oriented JSON for [tools/generated/dialect-table.json](../generated/dialect-table.json)."""
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
    """Generate and render the dialect table JSON for `bundle`."""
    rows, residue, notes = generate(bundle, root)
    return render(rows, residue, notes)
