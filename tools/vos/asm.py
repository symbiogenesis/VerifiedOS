# SPDX-License-Identifier: Apache-2.0
"""Position-fixed ELF assembler for the frozen dialect.

Instruction encodings come from [dialect.py](dialect.py) and ELF emission from
[image.py](image.py); this module parses assembly source, lays out `.text` and
`.data` at fixed addresses, and expands pseudo-instructions.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol

from . import dialect, image
from .dialect import AsmError

# Expanded instruction ready for encoding: `(mnemonic, resolved_integer_operands)`.
type Instr = tuple[str, list[int]]

# Lexed expression token: `(_TOKEN_group_name, raw_text)`.
type Token = tuple[str, str]

# Default section base addresses (16-byte aligned within RAM).
TEXT_BASE = 0x8000_0000
DATA_BASE = 0x8000_8000

MASK64 = (1 << 64) - 1
CANONICAL_BITS: Final[int] = 32

_DATA_WIDTHS: Final[dict[str, int]] = {".byte": 1, ".half": 2, ".word": 4, ".dword": 8}

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


@dataclass(frozen=True)
class Site:
    """Emitted 32-bit instruction site record for link-map and freeze-contract joins.

    `site_id` is `<unit_stem>#<ordinal:05d>` in emission order; `word` is the encoded
    32-bit instruction at `address` and `source` is the 1-based assembly line number.
    """

    site_id: str
    address: int
    opcode: str
    word: int
    source: int
    section: str

    def __post_init__(self) -> None:
        if type(self.word) is not int or not 0 <= self.word < 1 << CANONICAL_BITS:
            raise ValueError("instruction site word must be an unsigned 32-bit integer")


@dataclass
class Item:
    """One parsed assembly item (`insn`, `data`, `align`, `space`, `label`, or `equ`)."""

    kind: str                       # insn | data | align | space | label | equ
    line: int
    section: str
    text: str = ""
    args: list[str] = field(default_factory=list)
    address: int = 0
    size: int = 0


class Assembler:
    def __init__(self, source: str, name: str = "<source>", *,
                 text_base: int = TEXT_BASE, data_base: int = DATA_BASE,
                 externals: dict[str, int] | None = None) -> None:
        """Initialize an assembler for `source` with section bases and imported symbol addresses."""
        self.name = name
        self.text_base = text_base
        self.data_base = data_base
        self.externals = dict(externals or {})
        self.items: list[Item] = []
        self.sites: list[Site] = []
        self.symbols: dict[str, int] = {}
        self.symbol_section: dict[str, str] = {}
        self.constants: dict[str, tuple[int, str]] = {}   # .equ -> (value, section)
        self.section = ".text"
        # Unplaced symbols evaluate to 0 during layout relaxation and raise once `strict` is set.
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
            if not args:
                raise self._error(lineno, ".section takes a section name")
            if args[0] not in (".text", ".data"):
                raise self._error(lineno, f"no section {args[0]}: the image has "
                                          f".text and .data")
            self.section = args[0]
        elif name in (".globl", ".global", ".type", ".size"):
            pass                                   # every label is exported
        elif name in (".equ", ".set"):
            if len(args) < 2:
                raise self._error(lineno, f"{name} takes a name and a value")
            self.items.append(Item("equ", lineno, self.section, text=args[0],
                                   args=args[1:]))
        elif name in _DATA_WIDTHS:
            width = _DATA_WIDTHS[name]
            self.items.append(Item("data", lineno, self.section, text=name,
                                   args=args, size=width * len(args)))
        elif name in (".ascii", ".asciz", ".string"):
            tail = b"" if name == ".ascii" else b"\0"
            blob = b"".join(_string(a, lineno, self) + tail for a in args)
            self.items.append(Item("data", lineno, self.section, text=".bytes",
                                   args=[str(b) for b in blob], size=len(blob)))
        elif name in (".space", ".zero"):
            if not args:
                raise self._error(lineno, f"{name} takes a size")
            self.items.append(Item("space", lineno, self.section, args=args))
        elif name in (".align", ".p2align", ".balign"):
            if not args:
                raise self._error(lineno, f"{name} takes a boundary")
            if len(args) != 1:
                raise self._error(lineno, f"{name} takes only a boundary; explicit fill is unsupported")
            self.items.append(Item("align", lineno, self.section, text=name,
                                   args=args))
        else:
            raise self._error(lineno, f"no directive {name}")

    def _error(self, lineno: int, message: str) -> AsmError:
        return AsmError(f"{self.name}:{lineno}: {message}")

    # -- layout -------------------------------------------------------------

    def assemble(self) -> tuple[list[image.Section], dict[str, tuple[str, int]], int]:
        """Iterate section layout to a fixed point (for variable-length `li` expansions), then encode."""
        previous: dict[str, int] = {}
        for _ in range(8):
            self._layout()
            if self.symbols == previous:
                break
            previous = dict(self.symbols)
        else:
            raise AsmError(f"{self.name}: layout did not settle in eight rounds")

        self.strict = True
        self.sites = []
        text = image.Section(".text", self.text_base, executable=True)
        data = image.Section(".data", self.data_base, writable=True)
        sections = {".text": text, ".data": data}

        for item in self.items:
            section = sections[item.section]
            blob = self._bytes(item)
            if blob is None:
                continue
            gap = item.address - (section.addr + len(section.data))
            if gap < 0:
                raise self._error(item.line, f"layout moved backwards by {-gap} bytes "
                                             f"placing {item.text or item.kind}")
            section.data += b"\0" * gap + blob

        symbols = {name: (self.symbol_section[name], value)
                   for name, value in self.symbols.items()}
        entry = self.symbols.get("_start", self.text_base)
        return [text, data], symbols, entry

    def _layout(self) -> None:
        cursor = {".text": self.text_base, ".data": self.data_base}
        self.constants = {name: (value, "") for name, value in self.externals.items()}
        for item in self.items:
            here = cursor[item.section]
            item.address = here
            if item.kind in ("label", "equ") and item.text in self.externals:
                raise self._error(item.line, f"{item.text} is imported from another "
                                             f"unit and cannot be defined here")
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
        if item.kind == "align" and item.section == ".text" and item.size:
            if item.address % 4 or item.size % 4:
                raise self._error(item.line, "executable alignment needs whole 32-bit instructions")
            word = dialect.encode("addi", [0, 0, 0], item.address)
            for address in range(item.address, item.address + item.size, 4):
                self.sites.append(Site(
                    site_id=f"{Path(self.name).stem}#{len(self.sites):05d}",
                    address=address, opcode="addi", word=word,
                    source=item.line, section=item.section))
            return word.to_bytes(4, "little") * (item.size // 4)
        if item.kind in ("space", "align"):
            return b"\0" * item.size
        if item.kind == "data":
            if item.text == ".bytes":
                return bytes(int(a) for a in item.args)
            width = _DATA_WIDTHS[item.text]
            out = bytearray()
            for i, arg in enumerate(item.args):
                value = self._eval(arg, item, item.address + i * width)
                out += (value & ((1 << (8 * width)) - 1)).to_bytes(width, "little")
            return bytes(out)
        out = bytearray()
        pc = item.address
        for mnemonic, operands in self._expand(item, pc):
            try:
                word = dialect.encode(mnemonic, operands, pc)
                out += word.to_bytes(4, "little")
            except AsmError as exc:
                raise self._error(item.line, f"{item.text}: {exc}") from None
            self.sites.append(Site(
                site_id=f"{Path(self.name).stem}#{len(self.sites):05d}",
                address=pc, opcode=mnemonic, word=word, source=item.line,
                section=item.section))
            pc += 4
        return bytes(out)

    # -- instructions -------------------------------------------------------

    def _expand(self, item: Item, pc: int) -> list[tuple[str, list[int]]]:
        """Expand a source instruction or pseudo-instruction into encodable `(mnemonic, operands)` pairs."""
        name = item.text
        if name in PSEUDOS:
            return PSEUDOS[name](self, item, pc)
        if name not in dialect.TABLE:
            raise self._error(item.line, f"no instruction {name}")
        return [(name, self._operands(name, item, pc))]

    def _operands(self, name: str, item: Item, pc: int) -> list[int]:
        wanted = dialect.signature(name)
        given = item.args
        # Omitted trailing vector mask (`vm`) defaults to unmasked (`""`).
        if wanted and wanted[-1] == "vm" and len(given) == len(wanted) - 1:
            given = [*given, ""]
        if len(given) != len(wanted):
            raise self._error(item.line,
                              f"{name} takes {len(wanted)} operands, given {len(given)}")
        out: list[int] = []
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
            if not text:
                return [1]
            if text.lower() != "v0.t":
                raise self._error(item.line, f"the vector mask is spelled v0.t, "
                                             f"given {text!r}")
            return [0]
        if spec in ("imm", "sym"):
            return [self._eval(text, item, pc)]
        if spec == "v0":
            # Fixed `v0` mask operand carries no encoded slot bits.
            if text.lower() != "v0":
                raise self._error(item.line, f"{item.text} takes the mask register "
                                             f"spelled v0, given {text!r}")
            return []
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


class Pseudo(Protocol):
    """Callable signature for pseudo-instruction expanders in `PSEUDOS`."""

    def __call__(self, asm: Assembler, item: Item, pc: int) -> list[Instr]: ...


def _sign12(value: int) -> int:
    return ((value & 0xFFF) ^ 0x800) - 0x800


def _materialize(rd: int, value: int, out: list[Instr]) -> None:
    """Emit the shortest `lui`/`addiw`/`slli`/`addi` sequence to materialize 64-bit `value` in `rd`."""
    value = ((value & MASK64) ^ (1 << 63)) - (1 << 63)     # to signed 64
    if -(1 << 31) <= value < (1 << 31):
        hi20 = ((value + 0x800) >> 12) & 0xFFFFF
        lo12 = _sign12(value)
        if hi20:
            out.append(("lui", [rd, hi20 - (1 << 20) if hi20 >> 19 else hi20]))
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
    """Expand `la cd, symbol` to PC-relative `auipcc` + `cincoffsetimm` (R-15-036k)."""
    if len(item.args) != 2:
        raise asm._error(item.line, "la takes a register and a symbol")
    cd = asm._register(item.args[0], item)
    delta = asm._eval(item.args[1], item, pc) - pc
    hi20 = ((delta + 0x800) >> 12) & 0xFFFFF
    return [("auipcc", [cd, hi20 - (1 << 20) if hi20 >> 19 else hi20]),
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
    """Expand `ret` to `cjalr cnull, cra, 0` (R-15-071)."""
    _arity(asm, item, 0)
    return [("cjalr", [0, 1, 0])]


def _p_cjr(asm: Assembler, item: Item, pc: int) -> list[Instr]:
    """Expand `cjr cs1` to `cjalr cnull, cs1, 0`."""
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


def assemble_file(source: Path, elf: Path, sites: list[Site] | None = None) -> int:
    """Assemble `source` into `elf`, optionally appending emitted `Site` records to `sites`, and return the section byte count."""
    asm = Assembler(source.read_text(encoding="utf-8"), source.name)
    sections, symbols, entry = asm.assemble()
    image.write_elf(elf, sections, symbols, entry)
    if sites is not None:
        sites += asm.sites
    return sum(len(s.data) for s in sections)
