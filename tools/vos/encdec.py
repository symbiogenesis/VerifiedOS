# SPDX-License-Identifier: Apache-2.0
"""Extract instruction encodings and assembly spellings from the Sail model's `encdec`
and `assembly` mapping clauses.

Joins `encdec` and `assembly` clauses by shared AST constructor and positional
arguments to produce candidate `Form` records (mnemonic, fixed word/mask, operand bit
placements, syntax tokens, parameter bindings, and verbatim `when` guard text).
Admission and guard evaluation belong to [dialectgen.py](dialectgen.py).
"""

import re
from dataclasses import dataclass
from itertools import product
from typing import Any

from .sailbundle import SOURCE_ROOT, Bundle, Site

# Separator mapping calls in `assembly` clauses (`spc` ends the mnemonic, `sep` separates operands).
MNEMONIC_END = "spc"
OPERAND_SEP = "sep"
OPTIONAL_SPACE = "opt_spc"

_WHEN_RE = re.compile(r"\bwhen\b(.*)$", re.DOTALL)
_WAVE_RE = re.compile(r"\{\s*bits:\s*(\d+),\s*name:\s*(?:'([^']*)'|0[xX][0-9a-fA-F]+|\d+)")
_BITS_RE = re.compile(r"^0b([01_]+)$")


class UnreadableError(RuntimeError):
    """Raised when an `encdec` or `assembly` clause has an unsupported structure."""


@dataclass(frozen=True)
class Piece:
    """Contiguous bit slice mapping source operand bits `[src_hi:src_lo]` to instruction bits `[word_hi:word_lo]`."""

    word_hi: int
    word_lo: int
    src_hi: int
    src_lo: int


@dataclass(frozen=True)
class Operand:
    """Instruction operand descriptor: model variable name, printer mapping, value bit width, and bit `pieces`."""

    name: str
    printer: str
    width: int
    pieces: tuple[Piece, ...]

    @property
    def align(self) -> int:
        """Return the required byte/bit alignment factor (`1 << min(piece.src_lo)`)."""
        return 1 << min(piece.src_lo for piece in self.pieces)


@dataclass(frozen=True)
class Form:
    """Candidate instruction form joined from an `encdec` clause and an `assembly` clause."""

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
    """Parse a `0b...` literal into `(int_value, bit_width)`, or return `None`."""
    found = _BITS_RE.match(text)
    if not found:
        return None
    body = found.group(1).replace("_", "")
    return int(body, 2), len(body)


def _quoted(text: str) -> str | None:
    return text[1:-1] if len(text) >= 2 and text[0] == '"' and text[-1] == '"' else None


def _widths(wavedrom: str) -> dict[str, int]:
    """Extract `{field_name: bit_width}` from an `encdec` clause's `right_wavedrom` string."""
    out: dict[str, int] = {}
    for bits, name in _WAVE_RE.findall(wavedrom or ""):
        if name:
            out.setdefault(str(name), int(bits))
    return out


def _spans(pieces: list[tuple[str, object, int]]) -> dict[str, int]:
    """Infer `{field_name: bit_width}` for scattered fields from their highest referenced bit index."""
    out: dict[str, int] = {}
    for kind, payload, _ in pieces:
        if kind != "field":
            continue
        name, hi, _lo = _field(payload)
        out[name] = max(out.get(name, 0), hi + 1)
    return out


def arm_key(node: object) -> tuple[object, ...] | None:
    """Convert a mapping arm pattern (`id`, `literal`, `tuple`, `struct`, or `app`) into a hashable key."""
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


type Arms = dict[tuple[object, ...], object]


def _sided(clause: dict[str, Any], *, bits: bool
           ) -> tuple[tuple[object, ...], object, int] | None:
    """Extract `(pattern_key, literal_value, bit_width)` from whichever side of `clause` holds a literal."""
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
    """Join engine over a Sail `Bundle`'s `encdec`, `assembly`, and helper mappings."""

    def __init__(self, bundle: Bundle) -> None:
        self.bundle = bundle
        self._bit_arms: dict[str, Arms | None] = {}
        self._str_arms: dict[str, Arms | None] = {}

    # -- mapping arm lookups ---------------------------------------------------------

    def _arms(self, name: str) -> list[dict[str, Any]]:
        return self.bundle.clauses(name)

    def bit_arms(self, name: str) -> Arms | None:
        """Return `{arm_key: int_bits}` if every arm of mapping `name` yields a uniform-width bit literal."""
        if name not in self._bit_arms:
            self._bit_arms[name] = self._read_arms(name, bits=True)
        return self._bit_arms[name]

    def str_arms(self, name: str) -> Arms | None:
        """Return `{arm_key: str_value}` if every arm of mapping `name` yields a string literal."""
        if name not in self._str_arms:
            self._str_arms[name] = self._read_arms(name, bits=False)
        return self._str_arms[name]

    def _read_arms(self, name: str, *, bits: bool) -> Arms | None:
        """Read bidirectional mapping `name` into `{pattern_key: literal_value}`."""
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
        """Return the uniform bit width of bit-literal mapping `name`."""
        for clause in self._arms(name):
            found = _sided(clause, bits=True)
            if found is not None:
                return found[2]
        raise UnreadableError(f"{name} has no bit-literal arm after all")

    # -- right-hand-side encoding walk -----------------------------------------------

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
        # Non-literal single-argument mappings (`encdec_reg`, `encdec_vreg`, etc.) encode operand fields.
        if len(args) == 1 and args[0].get("type") == "id":
            field = str(args[0].get("id"))
            if field in widths:
                out.append(("field", (field, widths[field] - 1, 0), widths[field]))
                return
        raise UnreadableError(f"no reading for the application {name}")

    # -- `encdec` / `assembly` join --------------------------------------------------

    def forms(self) -> tuple[list[Form], list[str]]:
        """Join `encdec` and `assembly` clauses into `(forms, unread_residue)`."""
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
        """Collect encoding bit-selector and mnemonic string-selector constraints over argument positions."""
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
        """Build a `Form` for `assignment`, or return `None` if `assignment` conflicts with `bound.fixed`."""
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
        """Compute `(word, mask, placed_pieces)` for `assignment`, treating mnemonic-fixed fields as constants."""
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


# --- positional constructor argument binding ----------------------------------------


class _Binding:
    """Positional correspondence between a constructor's `encdec` and `assembly` left-hand patterns."""

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
        """Bind argument position `at` from `encdec`'s left pattern as variable slices or a fixed constructor key."""
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
    """Mapping selector constraint over one or more constructor argument positions."""

    side: str
    name: str
    positions: tuple[int, ...]
    arms: Arms


def _assignments(constraints: list[_Constraint]
                 ) -> list[dict[int, tuple[object, ...]]]:
    """Return all position-to-arm-key assignments satisfying every constraint in `constraints`."""
    if not constraints:
        return [{}]
    # Intersect constraints over identical position tuples before taking the Cartesian product.
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
    """Unpack `key` across `width` argument positions, or return `None` if arity mismatches."""
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
    """Return the bit pattern selected by `(side, name, positions)` under `assignment`."""
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
    """Return `(field_name, literal_or_id_spelling)` pairs fixed by `bound` and `assignment`."""
    out: list[tuple[str, str]] = []
    for name, (at, _offset) in sorted(bound.parts.items()):
        key = assignment.get(at, bound.fixed.get(at))
        if key is not None and len(key) == 2 and key[0] in ("lit", "id"):
            out.append((name, str(key[1])))
    return tuple(out)


def _spell(bound: _Binding, run: list[dict[str, Any]], constraints: list[_Constraint],
           assignment: dict[int, tuple[object, ...]]) -> str:
    """Assemble the mnemonic string for `assignment` across `run`."""
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


# --- clause AST helpers -------------------------------------------------------------


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
    """Return `(ident, 0)` if `node` is a single `id` pattern, else `None`."""
    if node.get("type") == "id":
        return (str(node.get("id")), 0)
    return None


def _composite(node: dict[str, Any]) -> list[tuple[str, int]] | None:
    """Decompose an `id` or `vector_concat` left pattern into `(field_name, zero_pad_width)` slices, MSB first."""
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
    """Return all identifier names referenced anywhere in AST subtree `node`."""
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
    """Split an `assembly` clause's right-hand side at `spc()` into `(mnemonic_parts, operand_parts)`."""
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
        if seen and part.get("type") == "app" \
                and part.get("id") in (OPTIONAL_SPACE, MNEMONIC_END):
            continue
        (printed if seen else mnemonic).append(part)
    return mnemonic, printed


def _syntax(printed: list[dict[str, Any]]) -> tuple[str, ...]:
    """Extract the sequence of operand printer names, `","` separators, and punctuation literals from `printed`."""
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
    """Build `Operand` descriptors in print order, joining multi-field printers (such as `vtype_assembly`) in encoding order."""
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
    """Concatenate multiple field `Piece`s into a single source value ordered from highest word bit to lowest."""
    out: list[Piece] = []
    at = sum(piece.word_hi - piece.word_lo + 1 for piece in pieces)
    for piece in sorted(pieces, key=lambda p: p.word_hi, reverse=True):
        width = piece.word_hi - piece.word_lo + 1
        at -= width
        out.append(Piece(word_hi=piece.word_hi, word_lo=piece.word_lo,
                         src_hi=at + width - 1, src_lo=at))
    return out


def _covered(word: int, mask: int, operands: tuple[Operand, ...]) -> None:
    """Verify that `mask` and `operands` partition all 32 instruction bits without overlap or unmasked `word` bits."""
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
    """Extract variable names from application `args`, flattening a single tuple argument (`maybe_aqrl((aq, rl))`)."""
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


# --- payload narrowings -------------------------------------------------------------


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
    """Convert a `"lit"` arm key into an integer fitting within `width` bits."""
    if len(key) == 2 and key[0] == "lit":
        text = str(key[1])
        found = _bits(text)
        if found is not None and found[1] <= width:
            return found[0]
        if text.isdigit() and int(text) < (1 << width):
            return int(text)
    raise UnreadableError(f"the mnemonic fixes a field to {key!r}, which is not a literal")
