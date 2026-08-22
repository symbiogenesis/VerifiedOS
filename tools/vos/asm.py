# SPDX-License-Identifier: Apache-2.0
"""The corpus assembler: dialect source in, position-fixed ELF out.

Sized to hand-written test programs and to nothing else. The frozen dialect has
no assembler, because no toolchain has one: LLVM's MC layer and `lld` are
re-homed to it at M1.4, which is downstream of every milestone the differential
corpus gates, so the corpus would otherwise have to wait on the toolchain that
waits on it (M0.12). What lands here instead is small enough to read: the
encoder is [dialect.py](dialect.py), the container is [image.py](image.py), and
this module is the parser, the layout, and the seven pseudo-instructions between
them.

**Three things it deliberately does not do**, each because the program that
needs it is not a hand-written test. There is no relocation output and no object
file: layout is absolute at assembly time, which is the position-fixed image the
profile already assumes (R-15-002b, R-15-036l). There is no linker script: two
sections at two composed addresses is the whole model. And there is no macro
processor, no `.if`, and no expression over a forward-declared external, because
a program that wants those is M1.4's rather than this corpus's.

**Purecap is the shape of the source, not a mode of it.** A load or store takes
its authority from the base register it names (core/addr_checks.sail), so a test
that touches memory derives a capability first, and the two idioms for that are
in every corpus program: `la` off PCC for code and read-only data, and `li` plus
`csetaddr` off the root data capability in `c1` for anything written. There is
no default data capability to fall back to and no integer-addressed access to
write by accident (R-15-001c).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol

from . import dialect, image
from .dialect import AsmError

# One instruction after expansion and before encoding: a mnemonic the dialect
# table knows, and its operands already resolved to integers in source order. A
# pseudo-instruction yields a list of these, which is the only reason it is a list
# rather than a single instruction.
Instr = tuple[str, list[int]]

# A lexed token: the name of the group in `_TOKEN` that matched, and its text.
Token = tuple[str, str]

# Where the two sections are composed. Both are 16-aligned so that a section's
# file offset and its address agree modulo the segment alignment, and both sit
# in the RAM region the profile configuration declares (model/config).
TEXT_BASE = 0x8000_0000
DATA_BASE = 0x8000_8000

MASK64 = (1 << 64) - 1

_TOKEN = re.compile(r"""
    (?P<hex>0[xX][0-9a-fA-F_]+)
  | (?P<bin>0[bB][01_]+)
  | (?P<dec>\d[\d_]*)
  | (?P<char>'(?:\\.|[^'])')
  | (?P<name>[A-Za-z_.$][A-Za-z_.$0-9]*)
  | (?P<op><<|>>|[-+*/%&|^~()])
  | (?P<space>\s+)
""", re.VERBOSE)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\",
            '"': '"', "'": "'"}


@dataclass
class Item:
    """One assembled thing: an instruction, some bytes, or a gap."""

    kind: str                       # insn | data | align | space | label
    line: int
    section: str
    text: str = ""
    args: list[str] = field(default_factory=list)
    address: int = 0
    size: int = 0


class Assembler:
    def __init__(self, source: str, name: str = "<source>") -> None:
        self.name = name
        self.items: list[Item] = []
        self.symbols: dict[str, int] = {}
        self.symbol_section: dict[str, str] = {}
        self.constants: dict[str, tuple[int, str]] = {}   # .equ, with its section
        self.section = ".text"
        # An unplaced symbol reads as zero while the layout settles and is an
        # error once it has, which is what keeps a typo from assembling to a
        # branch to the start of the image.
        self.strict = False
        self._parse(source)

    # -- parsing ------------------------------------------------------------

    def _parse(self, source: str) -> None:
        for lineno, raw in enumerate(source.splitlines(), 1):
            text = raw.split("#", 1)[0].split("//", 1)[0].strip()
            while text:
                label = re.match(r"([A-Za-z_.$][A-Za-z_.$0-9]*)\s*:", text)
                if not label:
                    break
                self.items.append(Item("label", lineno, self.section,
                                       text=label.group(1)))
                text = text[label.end():].strip()
            if not text:
                continue
            head, _, rest = text.partition(" ")
            head, rest = head.lower(), rest.strip()
            if head.startswith("."):
                self._directive(head, rest, lineno)
            else:
                self.items.append(Item("insn", lineno, self.section,
                                       text=head, args=_split_operands(rest)))

    def _directive(self, name: str, rest: str, lineno: int) -> None:
        args = _split_operands(rest)
        if name in (".text", ".data"):
            self.section = name
        elif name == ".section":
            if args[0] not in (".text", ".data"):
                raise self._error(lineno, f"no section {args[0]}: the image has "
                                          f".text and .data")
            self.section = args[0]
        elif name in (".globl", ".global", ".type", ".size"):
            pass                                   # every label is exported
        elif name in (".equ", ".set"):
            self.items.append(Item("equ", lineno, self.section, text=args[0],
                                   args=args[1:]))
        elif name in (".byte", ".half", ".word", ".dword"):
            width = {".byte": 1, ".half": 2, ".word": 4, ".dword": 8}[name]
            self.items.append(Item("data", lineno, self.section, text=name,
                                   args=args, size=width * len(args)))
        elif name in (".ascii", ".asciz", ".string"):
            blob = b"".join(_string(a, lineno, self) for a in args)
            if name != ".ascii":
                blob += b"\0" * len(args)
            self.items.append(Item("data", lineno, self.section, text=".bytes",
                                   args=[str(b) for b in blob], size=len(blob)))
        elif name in (".space", ".zero"):
            self.items.append(Item("space", lineno, self.section, args=args))
        elif name in (".align", ".p2align", ".balign"):
            self.items.append(Item("align", lineno, self.section, text=name,
                                   args=args))
        else:
            raise self._error(lineno, f"no directive {name}")

    def _error(self, lineno: int, message: str) -> AsmError:
        return AsmError(f"{self.name}:{lineno}: {message}")

    # -- layout -------------------------------------------------------------

    def assemble(self) -> tuple[list[image.Section], dict[str, tuple[str, int]], int]:
        """Lay the program out, then encode it.

        Layout is iterated to a fixed point rather than done in two passes,
        because `li` is as long as its value needs and a value can be a symbol:
        one pass would have to guess the length of an instruction whose operand
        it has not placed yet. Every other item's size is a property of the
        source alone, so the iteration moves only where a `li` crosses a
        materialization boundary and it settles in two rounds.
        """
        previous: dict[str, int] = {}
        for _ in range(8):
            self._layout()
            if self.symbols == previous:
                break
            previous = dict(self.symbols)
        else:
            raise AsmError(f"{self.name}: layout did not settle in eight rounds")

        self.strict = True
        text = image.Section(".text", TEXT_BASE, executable=True)
        data = image.Section(".data", DATA_BASE, writable=True)
        sections = {".text": text, ".data": data}

        for item in self.items:
            section = sections[item.section]
            blob = self._bytes(item)
            if blob is None:
                continue
            gap = item.address - (section.addr + len(section.data))
            # Raised rather than asserted, and this is the one in this module that
            # most needs to survive `python -O`: a negative gap multiplies to an
            # empty padding, so the item would be written at the wrong offset and
            # the image would assemble, load, and run as a different program.
            if gap < 0:
                raise self._error(item.line, f"layout moved backwards by {-gap} bytes "
                                             f"placing {item.text or item.kind}")
            section.data += b"\0" * gap + blob

        symbols = {name: (self.symbol_section[name], value)
                   for name, value in self.symbols.items()}
        entry = self.symbols.get("_start", TEXT_BASE)
        return [text, data], symbols, entry

    def _layout(self) -> None:
        cursor = {".text": TEXT_BASE, ".data": DATA_BASE}
        self.constants = {}
        for item in self.items:
            here = cursor[item.section]
            item.address = here
            if item.kind == "label":
                self.symbols[item.text] = here
                self.symbol_section[item.text] = item.section
            elif item.kind == "equ":
                self.constants[item.text] = (self._eval(item.args[0], item, here),
                                             item.section)
            elif item.kind == "insn":
                item.size = 4 * len(self._expand(item, here))
            elif item.kind == "space":
                item.size = self._eval(item.args[0], item, here)
            elif item.kind == "align":
                boundary = self._eval(item.args[0], item, here)
                if item.text != ".balign":
                    boundary = 1 << boundary
                item.size = (-here) % boundary
            cursor[item.section] = here + item.size

    def _bytes(self, item: Item) -> bytes | None:
        if item.kind in ("label", "equ"):
            return None
        if item.kind in ("space", "align"):
            return b"\0" * item.size
        if item.kind == "data":
            if item.text == ".bytes":
                return bytes(int(a) for a in item.args)
            width = {".byte": 1, ".half": 2, ".word": 4, ".dword": 8}[item.text]
            out = bytearray()
            for i, arg in enumerate(item.args):
                value = self._eval(arg, item, item.address + i * width)
                out += (value & ((1 << (8 * width)) - 1)).to_bytes(width, "little")
            return bytes(out)
        out = bytearray()
        pc = item.address
        for mnemonic, operands in self._expand(item, pc):
            try:
                out += dialect.encode(mnemonic, operands, pc).to_bytes(4, "little")
            except AsmError as exc:
                raise self._error(item.line, f"{item.text}: {exc}") from None
            pc += 4
        return bytes(out)

    # -- instructions -------------------------------------------------------

    def _expand(self, item: Item, pc: int) -> list[tuple[str, list[int]]]:
        """One source instruction as the sequence of encodable ones it is."""
        name = item.text
        if name in PSEUDOS:
            return PSEUDOS[name](self, item, pc)
        if name not in dialect.TABLE:
            raise self._error(item.line, f"no instruction {name}")
        return [(name, self._operands(name, item, pc))]

    def _operands(self, name: str, item: Item, pc: int) -> list[int]:
        wanted = dialect.signature(name)
        given = item.args
        # The vector mask is the one operand a program leaves out rather than
        # spells. `v0.t` is written where the operation is masked and nothing at
        # all where it is not, which is how every RISC-V assembler spells it and
        # how the model's own `maybe_vmask` mapping reads it back
        # (extensions/V/vext_utils_insts.sail). It is the last operand of every
        # form that has one, so the absence is unambiguous.
        if wanted and wanted[-1] == "vm" and len(given) == len(wanted) - 1:
            given = [*given, ""]
        if len(given) != len(wanted):
            raise self._error(item.line,
                              f"{name} takes {len(wanted)} operands, given {len(given)}")
        out: list[int] = []
        # `strict` even though the lengths were just compared: the guard above
        # reports the operand count a person got wrong, and this one refuses to
        # encode a truncated instruction if the two ever stop agreeing.
        for spec, text in zip(wanted, given, strict=True):
            out += self._operand(spec, text, item, pc)
        return out

    def _operand(self, spec: str, text: str, item: Item, pc: int) -> list[int]:
        text = text.strip()
        if spec == "reg":
            return [self._register(text, item)]
        if spec == "vreg":
            key = text.lower()
            if key not in dialect.VREGISTERS:
                raise self._error(item.line, f"no vector register {text}")
            return [dialect.VREGISTERS[key]]
        if spec == "vm":
            # Absent is unmasked, which is the `vm` bit set; `v0.t` is masked,
            # which is the bit clear. There is no third spelling: the mask
            # register is always `v0`, so naming another one is an error rather
            # than a mask.
            if not text:
                return [1]
            if text.lower() != "v0.t":
                raise self._error(item.line, f"the vector mask is spelled v0.t, "
                                             f"given {text!r}")
            return [0]
        if spec in ("imm", "sym"):
            return [self._eval(text, item, pc)]
        if spec == "csr":
            key = text.lower()
            return [dialect.CSRS[key]] if key in dialect.CSRS \
                else [self._eval(text, item, pc)]
        if spec == "scr":
            key = text.lower()
            if key not in dialect.SCRS:
                raise self._error(item.line, f"no special capability register {text}")
            return [dialect.SCRS[key]]
        if spec == "index":
            # `cs1[rs2 << scale]`, the profile's own spelling of the indexed
            # access. The scale is optional and defaults to zero, which is the
            # unscaled case rather than a missing operand.
            match = re.fullmatch(r"([A-Za-z_.$0-9]+)\s*\[\s*([A-Za-z_.$0-9]+)\s*"
                                 r"(?:<<\s*(.+?)\s*)?\]", text)
            if not match:
                raise self._error(item.line,
                                  f"{item.text} takes cs1[rs2 << scale], given {text!r}")
            scale = match.group(3)
            return [self._register(match.group(1), item),
                    self._register(match.group(2), item),
                    self._eval(scale, item, pc) if scale else 0]
        if spec in ("mem", "mem0"):
            match = re.fullmatch(r"(.*?)\(\s*([A-Za-z_.$0-9]+)\s*\)", text)
            if match:
                offset = match.group(1).strip()
                base = self._register(match.group(2), item)
            else:
                offset, base = "", self._register(text, item)
            if spec == "mem0":
                if offset:
                    raise self._error(item.line, f"{item.text} takes no displacement")
                return [base]
            return [self._eval(offset, item, pc) if offset else 0, base]
        raise AssertionError(f"no operand kind {spec}")

    def _register(self, text: str, item: Item) -> int:
        key = text.strip().lower()
        if key not in dialect.REGISTERS:
            raise self._error(item.line, f"no register {text}")
        return dialect.REGISTERS[key]

    # -- expressions --------------------------------------------------------

    def _eval(self, text: str, item: Item, here: int) -> int:
        tokens = _tokenize(text, self, item.line)
        value, rest = _expr(tokens, 0, self, item, here)
        if rest != len(tokens):
            raise self._error(item.line, f"trailing input in {text!r}")
        return value

    def value_of(self, name: str, item: Item, here: int) -> int:
        if name == ".":
            return here
        if name in self.symbols:
            return self.symbols[name]
        if name in self.constants:
            return self.constants[name][0]
        if self.strict:
            raise self._error(item.line, f"no symbol {name}")
        return 0


# ---------------------------------------------------------------------------
# Expressions: a precedence climber over the token list, with no assignment, no
# call, and no comparison, because an operand is an address or a constant.

_PRECEDENCE = {"|": 1, "^": 2, "&": 3, "<<": 4, ">>": 4,
               "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


def _tokenize(text: str, asm: Assembler, line: int) -> list[Token]:
    tokens: list[Token] = []
    at = 0
    while at < len(text):
        match = _TOKEN.match(text, at)
        if not match:
            raise asm._error(line, f"cannot read {text[at:]!r}")
        at = match.end()
        kind = match.lastgroup
        if kind is None:
            # Every branch of `_TOKEN` is a named group, so this is unreachable
            # unless one is added without a name; said here rather than left for a
            # `None` to travel into the token list and fail as a bad token kind.
            raise asm._error(line, f"the lexer matched {match.group()!r} in no named group")
        if kind != "space":
            tokens.append((kind, match.group()))
    return tokens


def _atom(tokens: list[Token], at: int, asm: Assembler, item: Item,
          here: int) -> tuple[int, int]:
    if at >= len(tokens):
        raise asm._error(item.line, "expression ended early")
    kind, text = tokens[at]
    if kind == "hex":
        return int(text.replace("_", ""), 16), at + 1
    if kind == "bin":
        return int(text.replace("_", ""), 2), at + 1
    if kind == "dec":
        return int(text.replace("_", "")), at + 1
    if kind == "char":
        return ord(_unescape(text[1:-1])), at + 1
    if kind == "name":
        return asm.value_of(text, item, here), at + 1
    if text == "(":
        value, at = _expr(tokens, at + 1, asm, item, here)
        if at >= len(tokens) or tokens[at][1] != ")":
            raise asm._error(item.line, "unbalanced parenthesis")
        return value, at + 1
    if text == "-":
        value, at = _atom(tokens, at + 1, asm, item, here)
        return -value, at
    if text == "~":
        value, at = _atom(tokens, at + 1, asm, item, here)
        return ~value, at
    if text == "+":
        return _atom(tokens, at + 1, asm, item, here)
    raise asm._error(item.line, f"cannot read {text!r} here")


def _expr(tokens: list[Token], at: int, asm: Assembler, item: Item, here: int,
          min_precedence: int = 1) -> tuple[int, int]:
    left, at = _atom(tokens, at, asm, item, here)
    while at < len(tokens):
        op = tokens[at][1]
        precedence = _PRECEDENCE.get(op, 0)
        if precedence < min_precedence:
            break
        right, at = _expr(tokens, at + 1, asm, item, here, precedence + 1)
        left = _apply(op, left, right)
    return left, at


def _apply(op: str, left: int, right: int) -> int:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left // right
    if op == "%":
        return left % right
    if op == "<<":
        return left << right
    if op == ">>":
        return left >> right
    if op == "&":
        return left & right
    if op == "|":
        return left | right
    if op == "^":
        return left ^ right
    raise AsmError(f"no operator {op}")


def _split_operands(text: str) -> list[str]:
    """Split on commas outside parentheses and outside quotes."""
    out: list[str] = []
    depth, quote, current = 0, "", ""
    for char in text:
        if quote:
            current += char
            if char == quote and not current.endswith("\\" + quote):
                quote = ""
            continue
        if char in "\"'":
            quote, current = char, current + char
        elif char == "(":
            depth, current = depth + 1, current + char
        elif char == ")":
            depth, current = depth - 1, current + char
        elif char == "," and depth == 0:
            out.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        out.append(current.strip())
    return out


def _unescape(text: str) -> str:
    out, at = "", 0
    while at < len(text):
        if text[at] == "\\" and at + 1 < len(text):
            out += _ESCAPES.get(text[at + 1], text[at + 1])
            at += 2
        else:
            out += text[at]
            at += 1
    return out


def _string(text: str, line: int, asm: Assembler) -> bytes:
    text = text.strip()
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        raise asm._error(line, f"expected a quoted string, got {text!r}")
    return _unescape(text[1:-1]).encode()


# ---------------------------------------------------------------------------
# Pseudo-instructions. Seven of them, and the two that matter are the purecap
# ones: `la` materializes a capability off PCC, and `li` materializes an
# integer, which is how a program names a *data* address before deriving the
# capability for it off `c1`.


class Pseudo(Protocol):
    """What every pseudo-instruction expander is, stated once for `PSEUDOS`.

    The table at the bottom of this module maps a name to one of these, and two of
    its entries are closures built by a factory rather than functions written out.
    Without a declared shape the table is `dict[str, object]` and nothing checks
    that a member takes the arguments the expander is called with, which is exactly
    the position `dialect.KINDS` was in.
    """

    def __call__(self, asm: Assembler, item: Item, pc: int) -> list[Instr]: ...


def _sign12(value: int) -> int:
    return ((value & 0xFFF) ^ 0x800) - 0x800


def _materialize(rd: int, value: int, out: list[Instr]) -> None:
    """The shortest `lui`/`addiw`/`slli`/`addi` sequence for a 64-bit constant.

    This is the RISC-V materialization every backend implements; it is here
    because the corpus has no backend. `addiw` rather than `addi` in the 32-bit
    case is not a stylistic choice: `lui` sign-extends its result to XLEN, so
    the low half has to be added at 32 bits and re-extended or a constant just
    below 2^31 comes out with its high half set.
    """
    value = ((value & MASK64) ^ (1 << 63)) - (1 << 63)     # to signed 64
    if -(1 << 31) <= value < (1 << 31):
        hi20 = ((value + 0x800) >> 12) & 0xFFFFF
        lo12 = _sign12(value)
        if hi20:
            out.append(("lui", [rd, hi20]))
        if lo12 or not hi20:
            out.append(("addiw", [rd, rd if hi20 else 0, lo12]))
        return
    lo12 = _sign12(value)
    high = ((value + 0x800) & MASK64) >> 12
    trailing = (high & -high).bit_length() - 1
    shift = 12 + trailing
    high >>= trailing
    high = (high ^ (1 << (63 - shift))) - (1 << (63 - shift))   # sign-extend
    _materialize(rd, high, out)
    out.append(("slli", [rd, rd, shift]))
    if lo12:
        out.append(("addi", [rd, rd, lo12]))


def _p_li(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    if len(item.args) != 2:
        raise asm._error(item.line, "li takes a register and a value")
    rd = asm._register(item.args[0], item)
    out: list[Instr] = []
    _materialize(rd, asm._eval(item.args[1], item, pc), out)
    return out


def _p_la(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    """`la cd, symbol`: a capability for `symbol` derived from PCC.

    The pair is the profile's own PC-relative materialization (§1.1,
    R-15-036k), and what it yields carries PCC's authority: read and execute,
    never store, W+X being unrepresentable (R-15-007l). A program that writes
    through the result would fault at the store, which is the intended answer.
    """
    if len(item.args) != 2:
        raise asm._error(item.line, "la takes a register and a symbol")
    cd = asm._register(item.args[0], item)
    delta = asm._eval(item.args[1], item, pc) - pc
    return [("auipcc", [cd, ((delta + 0x800) >> 12) & 0xFFFFF]),
            ("cincoffsetimm", [cd, cd, _sign12(delta)])]


def _arity(asm: Assembler, item: Item, count: int) -> None:
    if len(item.args) != count:
        raise asm._error(item.line,
                         f"{item.text} takes {count} operands, given {len(item.args)}")


def _p_nop(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 0)
    return [("addi", [0, 0, 0])]


def _p_mv(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("addi", [asm._register(item.args[0], item),
                      asm._register(item.args[1], item), 0])]


def _p_not(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("xori", [asm._register(item.args[0], item),
                      asm._register(item.args[1], item), -1])]


def _p_neg(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("sub", [asm._register(item.args[0], item), 0,
                     asm._register(item.args[1], item)])]


def _p_seqz(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("sltiu", [asm._register(item.args[0], item),
                       asm._register(item.args[1], item), 1])]


def _p_snez(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("sltu", [asm._register(item.args[0], item), 0,
                      asm._register(item.args[1], item)])]


# `fence` takes its two ordering sets as letters, which is how every RISC-V
# assembler spells them and how the model's own tests are written; a bare
# `fence` is the conservative `iorw, iorw` the base ISA defines it as.
_FENCE_BITS = {"i": 8, "o": 4, "r": 2, "w": 1}


def _fence_set(asm: Assembler, item: Item, text: str) -> int:
    text = text.strip().lower()
    if not text:
        return 0b1111
    if all(c in _FENCE_BITS for c in text):
        return sum(_FENCE_BITS[c] for c in dict.fromkeys(text))
    return asm._eval(text, item, item.address)


def _p_fence(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    if len(item.args) not in (0, 2):
        raise asm._error(item.line, "fence takes two ordering sets, or none")
    pred, succ = [*item.args, "", ""][:2]
    return [("fence", [_fence_set(asm, item, pred), _fence_set(asm, item, succ)])]


def _branch_zero(mnemonic: str, *, swap: bool) -> Pseudo:
    def build(asm: Assembler, item: Item, pc: int) -> list[Instr]:
        _arity(asm, item, 2)
        reg = asm._register(item.args[0], item)
        target = asm._eval(item.args[1], item, pc)
        operands = [0, reg, target] if swap else [reg, 0, target]
        return [(mnemonic, operands)]
    return build


def _branch_swapped(mnemonic: str) -> Pseudo:
    def build(asm: Assembler, item: Item, pc: int) -> list[Instr]:
        _arity(asm, item, 3)
        return [(mnemonic, [asm._register(item.args[1], item),
                            asm._register(item.args[0], item),
                            asm._eval(item.args[2], item, pc)])]
    return build


def _p_csrr(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("csrrs", [asm._register(item.args[0], item),
                       *asm._operand("csr", item.args[1], item, pc), 0])]


def _p_csrw(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 2)
    return [("csrrw", [0, *asm._operand("csr", item.args[0], item, pc),
                       asm._register(item.args[1], item)])]


def _p_j(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 1)
    return [("cjal", [0, asm._eval(item.args[0], item, pc)])]


def _p_call(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    _arity(asm, item, 1)
    return [("cjal", [1, asm._eval(item.args[0], item, pc)])]


def _p_ret(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    """`ret` is a jump that writes no link, which is the only role a
    backward-edge sentry is reachable in (R-15-071, extensions/CHERI)."""
    _arity(asm, item, 0)
    return [("cjalr", [0, 1, 0])]


def _p_cjr(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    """`cjr` rather than `jr`, beside `cjal` and `cjalr`: the jump is the
    capability form, there being no integer one to distinguish it from."""
    _arity(asm, item, 1)
    return [("cjalr", [0, asm._register(item.args[0], item), 0])]


PSEUDOS: Final[dict[str, Pseudo]] = {
    "nop": _p_nop, "mv": _p_mv, "not": _p_not, "neg": _p_neg,
    "seqz": _p_seqz, "snez": _p_snez,
    "li": _p_li, "la": _p_la, "fence": _p_fence,
    "csrr": _p_csrr, "csrw": _p_csrw,
    "j": _p_j, "call": _p_call, "ret": _p_ret, "cjr": _p_cjr,
    "beqz": _branch_zero("beq", swap=False), "bnez": _branch_zero("bne", swap=False),
    "blez": _branch_zero("bge", swap=True), "bgez": _branch_zero("bge", swap=False),
    "bltz": _branch_zero("blt", swap=False), "bgtz": _branch_zero("blt", swap=True),
    "bgt": _branch_swapped("blt"), "ble": _branch_swapped("bge"),
    "bgtu": _branch_swapped("bltu"), "bleu": _branch_swapped("bgeu"),
}


def assemble_file(source: Path, elf: Path) -> int:
    """Assemble one program and write its image. Returns the byte count."""
    asm = Assembler(source.read_text(encoding="utf-8"), source.name)
    sections, symbols, entry = asm.assemble()
    image.write_elf(elf, sections, symbols, entry)
    return sum(len(s.data) for s in sections)
