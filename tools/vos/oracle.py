# SPDX-License-Identifier: Apache-2.0
"""Model-as-oracle Sail harness generator for [tools/oracle-specs/](../oracle-specs/)
and [cli/oracle.py](cli/oracle.py).

Parses JSON oracle specifications (`sources` and `probes`), emits deterministic Sail
harnesses with fixed-width lowercase hex formatters (`hex_<n>`), a 36-bit maximal-length
LFSR (`x^36 + x^25 + 1`), and parameter sweeps (`all`, `draw`, `table`), and compiles
and runs them via [sailrig.py](sailrig.py) to produce `<kind> <inputs> -> <outputs>`
vector files.
"""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from vos import sailrig

SPECS = "tools/oracle-specs"
TOOL = "tools/run.py oracle"
WORK = "oracle"
VECTORS = "vectors.txt"

# Format token pattern: `h<n>` (1..32 hex digits) or `b1` (boolean digit).
SHOW = re.compile(r"^(?:h(\d{1,2})|b1)$")

# Probe line-prefix identifier pattern.
KIND = re.compile(r"^[a-z]+$")

# Sail identifier pattern for probe parameter names.
IDENT = re.compile(r"^[a-z][a-z0-9_]*$")

# Sail keywords and harness-internal identifiers disallowed as probe parameter names.
RESERVED = frozenset({
    "and", "as", "assert", "bitfield", "bitone", "bitzero", "bool", "by", "cast",
    "catch", "constraint", "dec", "default", "do", "effect", "else", "end", "enum",
    "exit", "false", "forall", "foreach", "from", "function", "if", "impl", "implicit",
    "in", "inc", "infix", "infixl", "infixr", "instantiation", "int", "let", "mapping",
    "match", "monadic", "nat", "operator", "overload", "private", "pure", "ref",
    "register", "repeat", "return", "scattered", "sizeof", "struct", "then", "throw",
    "to", "true", "try", "type", "undefined", "union", "unit", "until", "val", "var",
    "where", "while",
    "b1", "hex", "lfsr36", "main", "nib", "rep", "seed",
})

# Width of the `x^36 + x^25 + 1` maximal-length shift register (`lfsr36`).
LFSR_BITS = 36

# Maximum bit width of a `draw` parameter (two `lfsr36` draws concatenated).
DRAW_MAX = 2 * LFSR_BITS

# Maximum nibble width supported by `hex_<n>` formatters (128 bits).
HEX_MAX = 32


class ParamRow(TypedDict, total=False):
    """JSON schema for a probe parameter entry."""

    name: str
    width: int
    over: str
    rows: list[str]
    show: str


class ShowRow(TypedDict, total=False):
    """JSON schema for a printed output expression entry."""

    expr: str
    show: str


class ProbeRow(TypedDict, total=False):
    """JSON schema for a single probe in an oracle spec."""

    kind: str
    what: str
    params: list[ParamRow]
    repeat: int
    seed: str
    body: list[str]
    shows: list[ShowRow]


class SpecRow(TypedDict, total=False):
    """JSON schema for an oracle spec file."""

    name: str
    what: str
    answers: str
    sources: list[str]
    probes: list[ProbeRow]


@dataclass(frozen=True)
class Param:
    """Validated probe parameter descriptor."""

    name: str
    width: int
    over: str
    rows: tuple[str, ...]
    show: str

    @property
    def size(self) -> int:
        """Return the loop iteration count for an `all` or `table` parameter."""
        return len(self.rows) if self.over == "table" else 1 << self.width


@dataclass(frozen=True)
class Show:
    """Printed Sail expression and its `SHOW` format token."""

    expr: str
    show: str


@dataclass(frozen=True)
class Printer:
    """Typed Sail probe printer specification (`probe_<kind>`)."""

    kind: str
    arguments: tuple[tuple[str, str], ...]
    inputs: tuple[Show, ...]
    body: tuple[str, ...]
    shows: tuple[Show, ...]
    what: str = ""


@dataclass(frozen=True)
class Probe:
    """Validated probe specification."""

    kind: str
    what: str
    params: tuple[Param, ...]
    repeat: int
    seed: str
    body: tuple[str, ...]
    shows: tuple[Show, ...]

    @property
    def vectors(self) -> int:
        """Return the total number of vector lines emitted by this probe."""
        total = self.repeat
        for param in self.params:
            if param.over in ("all", "table"):
                total *= param.size
        return total


@dataclass(frozen=True)
class Spec:
    """Validated oracle specification."""

    name: str
    what: str
    answers: str
    sources: tuple[str, ...]
    probes: tuple[Probe, ...]

    @property
    def vectors(self) -> int:
        return sum(probe.vectors for probe in self.probes)


class SpecError(ValueError):
    """Raised when an oracle spec or `Printer` declaration is invalid."""


def spec_path(root: Path, name: str) -> Path:
    return root / SPECS / f"{name}.json"


def names(root: Path) -> list[str]:
    """Return sorted oracle spec names under `root / SPECS`."""
    directory = root / SPECS
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def load(root: Path, name: str) -> Spec:
    """Load and validate `root / SPECS / f"{name}.json"`."""
    path = spec_path(root, name)
    if not path.is_file():
        raise SpecError(f"there is no spec at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise SpecError(f"{path} is not JSON: {err}") from err
    if not isinstance(raw, dict):
        raise SpecError(f"{path} is not a JSON object")
    return parse(name, raw)


def parse(name: str, raw: SpecRow) -> Spec:
    """Validate decoded JSON `raw` for spec `name` and return a `Spec`."""
    stated = raw.get("name", "")
    if stated != name:
        raise SpecError(f"the spec in {name}.json calls itself {stated!r}; the file "
                        "name and the declared name are one fact and must agree")
    sources = tuple(raw.get("sources", ()))
    if not sources:
        raise SpecError(f"{name}: no model sources, so there is nothing to be an "
                        "oracle about")
    probes = tuple(_probe(name, row) for row in raw.get("probes", ()))
    if not probes:
        raise SpecError(f"{name}: no probes, so the harness would print nothing")
    kinds = [probe.kind for probe in probes]
    if len(set(kinds)) != len(kinds):
        raise SpecError(f"{name}: two probes share a kind, so a census could not tell "
                        "their lines apart")
    return Spec(name=name, what=raw.get("what", ""), answers=raw.get("answers", ""),
                sources=sources, probes=probes)


def _probe(spec: str, row: ProbeRow) -> Probe:
    kind = row.get("kind", "")
    if not KIND.match(kind):
        raise SpecError(f"{spec}: {kind!r} is not a kind; a kind is lowercase letters, "
                        "because it is the token a census reads each line back by")
    params = tuple(_param(spec, kind, one) for one in row.get("params", ()))
    seen = [param.name for param in params]
    if len(set(seen)) != len(seen):
        raise SpecError(f"{spec}/{kind}: two parameters share a name")
    shows = tuple(_show(spec, kind, one) for one in row.get("shows", ()))
    if not shows:
        raise SpecError(f"{spec}/{kind}: a probe that prints no answer is a call whose "
                        "result nothing is held to")
    repeat = int(row.get("repeat", 1))
    loops = [param for param in params if param.over in ("all", "table")]
    if repeat < 1:
        raise SpecError(f"{spec}/{kind}: repeat is {repeat}, so the probe never runs")
    if repeat == 1 and not loops:
        raise SpecError(f"{spec}/{kind}: every parameter is drawn and repeat is 1, so "
                        "the probe writes one line; state a repeat")
    body = tuple(_statement(spec, kind, line) for line in row.get("body", ()))
    return Probe(kind=kind, what=row.get("what", ""), params=params, repeat=repeat,
                 seed=row.get("seed", "0x0a5c3f19d"), body=body, shows=shows)


def _statement(spec: str, kind: str, line: str) -> str:
    """Validate a single Sail body statement, rejecting trailing semicolons."""
    text = line.rstrip()
    if text.endswith(";"):
        raise SpecError(f"{spec}/{kind}: body statement {line!r} ends in `;`; the "
                        "generator supplies the separator, so a statement states "
                        "itself and no more")
    return text


def _param(spec: str, kind: str, row: ParamRow) -> Param:
    name = row.get("name", "")
    if not IDENT.match(name):
        raise SpecError(f"{spec}/{kind}: {name!r} is not a Sail identifier")
    if name in RESERVED:
        raise SpecError(f"{spec}/{kind}: `{name}` is a Sail keyword or a name the "
                        "generated harness binds for itself, so a parameter of that "
                        "name is a syntax error in emitted code rather than here")
    width = int(row.get("width", 0))
    if width < 1:
        raise SpecError(f"{spec}/{kind}/{name}: width {width} is not a bit width")
    over = row.get("over", "draw")
    if over not in ("all", "draw", "table"):
        raise SpecError(f"{spec}/{kind}/{name}: over is {over!r}, and the sweep knows "
                        "`all`, `draw` and `table`")
    rows = tuple(row.get("rows", ()))
    if over == "table" and not rows:
        raise SpecError(f"{spec}/{kind}/{name}: a table parameter with no rows walks "
                        "nothing")
    if over != "table" and rows:
        raise SpecError(f"{spec}/{kind}/{name}: rows are a table parameter's, and this "
                        f"one is `{over}`")
    if over == "draw" and width > DRAW_MAX:
        raise SpecError(f"{spec}/{kind}/{name}: {width} bits is wider than the "
                        f"{DRAW_MAX} two draws of the shift register fill")
    show = row.get("show", f"h{math.ceil(width / 4)}")
    _nibbles(spec, kind, show)
    if show != "b1" and _nibbles(spec, kind, show) * 4 < width:
        raise SpecError(f"{spec}/{kind}/{name}: `{show}` is narrower than the "
                        f"parameter's {width} bits, so the line would not carry the "
                        "input the answer was computed from")
    return Param(name=name, width=width, over=over, rows=rows, show=show)


def _show(spec: str, kind: str, row: ShowRow) -> Show:
    expr = row.get("expr", "").strip()
    if not expr:
        raise SpecError(f"{spec}/{kind}: a printed answer with no expression")
    show = row.get("show", "")
    _nibbles(spec, kind, show)
    return Show(expr=expr, show=show)


def _nibbles(spec: str, kind: str, show: str) -> int:
    """Return the hex digit count for `show` (`0` for `"b1"`), or raise `SpecError`."""
    found = SHOW.match(show)
    if not found:
        raise SpecError(f"{spec}/{kind}: `{show}` is not a show token; a token is "
                        "`h<n>` for n hex digits or `b1` for a bool")
    if found.group(1) is None:
        return 0
    width = int(found.group(1))
    if not 1 <= width <= HEX_MAX:
        raise SpecError(f"{spec}/{kind}: `{show}` asks for {width} hex digits and the "
                        f"formatters run to {HEX_MAX}")
    return width


# --- Sail harness emission --------------------------------------------------


def harness(spec: Spec, tool: str) -> str:
    """Render the deterministic Sail harness source for `spec`."""
    widest = max(_widths(spec), default=1)
    parts = [_preamble(spec, tool), _formatters(widest)]
    parts.extend(_probe_sail(probe) for probe in spec.probes)
    parts.append(_main(spec))
    return "\n".join(parts)


def _widths(spec: Spec) -> list[int]:
    """Return all hex nibble widths used across `spec.probes`."""
    found: list[int] = []
    for probe in spec.probes:
        found.extend(int(p.show[1:]) for p in probe.params if p.show != "b1")
        found.extend(int(s.show[1:]) for s in probe.shows if s.show != "b1")
    return found


def _preamble(spec: Spec, tool: str) -> str:
    lines = [
        "// SPDX-License-Identifier: Apache-2.0",
        "//",
        f"// Generated by {tool} from tools/oracle-specs/{spec.name}.json.",
        "// Do not edit: edit the spec and emit again.",
        "//",
        f"// {spec.what}",
        "//",
        "// One vector per line, `<kind> <inputs> -> <outputs>`, every field lowercase",
        "// hex at a width fixed by the field. Lines opening with `#` are commentary.",
        "// Nothing here decides anything: every value right of an arrow is the",
        "// model's own answer for the inputs left of it.",
        "",
    ]
    return "\n".join(lines)


def _formatters(widest: int) -> str:
    """Emit `nib`, `hex_1`..`hex_{widest}`, `b1`, and `lfsr36` Sail definitions."""
    out = ["// The formatters. Fixed width, lowercase, no prefix.",
           "",
           "function nib(n : bits(4)) -> string = match n {",
           '  0x0 => "0", 0x1 => "1", 0x2 => "2", 0x3 => "3",',
           '  0x4 => "4", 0x5 => "5", 0x6 => "6", 0x7 => "7",',
           '  0x8 => "8", 0x9 => "9", 0xa => "a", 0xb => "b",',
           '  0xc => "c", 0xd => "d", 0xe => "e", 0xf => "f",',
           "}",
           "",
           "function hex_1(x : bits(4)) -> string = nib(x)"]
    for n in range(2, widest + 1):
        top = 4 * n - 1
        out.append(f"function hex_{n}(x : bits({4 * n})) -> string = "
                   f"nib(x[{top} .. {top - 3}]) ^ hex_{n - 1}(x[{top - 4} .. 0])")
    out.extend(["",
                'function b1(b : bool) -> string = if b then "1" else "0"',
                "",
                "// A maximal-length shift register, x^36 + x^25 + 1, so a drawn",
                "// parameter varies without the sweep growing a loop and without this",
                "// file holding a table of values it would then be quantifying over.",
                "function lfsr36(s : bits(36)) -> bits(36) = {",
                "  let fb : bits(1) = s[35 .. 35] ^ s[24 .. 24];",
                "  (s << 1) | zero_extend(fb)",
                "}",
                ""])
    return "\n".join(out)


def _fmt(show: str, expr: str) -> str:
    """Return the Sail formatting call (`b1(...)` or `hex_<n>(zero_extend(...))`) for `expr`."""
    if show == "b1":
        return f"b1({expr})"
    return f"hex_{int(show[1:])}(zero_extend({expr}))"


def _probe_sail(probe: Probe) -> str:
    """Emit the printer function, lookup tables, and sweep function for `probe`."""
    return "\n".join([_probe_fn(probe), "", *_tables(probe), _sweep(probe), ""])


def _probe_fn(probe: Probe) -> str:
    return _printer_function(Printer(
        kind=probe.kind,
        arguments=tuple((p.name, f"bits({p.width})") for p in probe.params),
        inputs=tuple(Show(p.name, p.show) for p in probe.params),
        body=probe.body, shows=probe.shows, what=probe.what))


def printer_functions(printers: tuple[Printer, ...]) -> str:
    """Validate `printers` and emit the shared formatters, `lfsr36`, and `probe_<kind>` functions."""
    if not printers:
        raise SpecError("a campaign with no printers would print nothing")
    seen: set[str] = set()
    widths: list[int] = []
    for printer in printers:
        if not KIND.fullmatch(printer.kind) or printer.kind in seen:
            raise SpecError(f"invalid or repeated printer kind: {printer.kind!r}")
        seen.add(printer.kind)
        names = [name for name, _ in printer.arguments]
        if (len(set(names)) != len(names)
                or any(not IDENT.fullmatch(name) or name in RESERVED for name in names)
                or any(not typ.strip() for _, typ in printer.arguments)):
            raise SpecError(f"{printer.kind}: invalid printer arguments")
        if not printer.shows:
            raise SpecError(f"{printer.kind}: a printer must carry an answer")
        for field in (*printer.inputs, *printer.shows):
            if not field.expr.strip():
                raise SpecError(f"{printer.kind}: an empty printed expression")
            width = _nibbles("campaign", printer.kind, field.show)
            widths.append(width)
        for statement in printer.body:
            _statement("campaign", printer.kind, statement)
    return "\n".join([_formatters(max(widths, default=1)),
                      *(_printer_function(printer) for printer in printers)])


def _printer_function(printer: Printer) -> str:
    args = ", ".join(f"{name} : {typ}" for name, typ in printer.arguments)
    pieces = [f'"{printer.kind}"']
    for field in printer.inputs:
        pieces.append('" "')
        pieces.append(_fmt(field.show, field.expr))
    pieces.append('" ->"')
    for show in printer.shows:
        pieces.append('" "')
        pieces.append(_fmt(show.show, show.expr))
    printed = "\n    ^ ".join(pieces)
    statements = [*printer.body, f"print_endline(\n    {printed}\n  )"]
    joined = ";\n  ".join(statements)
    head = f"// {printer.what}" if printer.what else f"// the `{printer.kind}` vectors"
    return f"{head}\nfunction probe_{printer.kind}({args}) -> unit = {{\n  {joined}\n}}"


def _tables(probe: Probe) -> list[str]:
    """Emit `tbl_<kind>_<param>` index-match functions for `table` parameters in `probe`."""
    out: list[str] = []
    for param in probe.params:
        if param.over != "table":
            continue
        arms = ", ".join(f"{i} => {value}"
                         for i, value in enumerate(param.rows[:-1]))
        wildcard = f"_ => {param.rows[-1]}"
        body = f"{arms}, {wildcard}" if arms else wildcard
        out.append(f"function tbl_{probe.kind}_{param.name}(i : int) -> "
                   f"bits({param.width}) = match i {{ {body} }}")
        out.append("")
    return out


def _draw(param: Param) -> list[str]:
    """Emit `lfsr36` step statements to populate drawn parameter `param` (1 or 2 draws)."""
    if param.width <= LFSR_BITS:
        return ["seed = lfsr36(seed)",
                f"let {param.name} : bits({param.width}) = "
                f"seed[{param.width - 1} .. 0]"]
    high = param.width - LFSR_BITS - 1
    return ["seed = lfsr36(seed)",
            f"let {param.name}_hi : bits({high + 1}) = seed[{high} .. 0]",
            "seed = lfsr36(seed)",
            f"let {param.name} : bits({param.width}) = {param.name}_hi @ seed"]


def _sweep(probe: Probe) -> str:
    """Emit `sweep_<kind>()` nesting `all`/`table` loops around `repeat` and `draw` steps."""
    inner: list[str] = []
    for param in probe.params:
        if param.over == "all":
            inner.append(f"let {param.name} : bits({param.width}) = "
                         f"to_bits_truncate({param.width}, i_{param.name})")
        elif param.over == "table":
            inner.append(f"let {param.name} : bits({param.width}) = "
                         f"tbl_{probe.kind}_{param.name}(i_{param.name})")
    for param in probe.params:
        if param.over == "draw":
            inner.extend(_draw(param))
    inner.append(f"probe_{probe.kind}({', '.join(p.name for p in probe.params)})")

    body = ";\n".join(inner)
    loops = [(f"i_{p.name}", p.size) for p in probe.params
             if p.over in ("all", "table")]
    if probe.repeat > 1:
        loops.append(("rep", probe.repeat))
    for name, size in reversed(loops):
        body = (f"foreach ({name} from 0 to {size - 1}) {{\n"
                + _indent(body) + "\n}")

    drawn = any(p.over == "draw" for p in probe.params)
    opening = f"var seed : bits(36) = {probe.seed};\n" if drawn else ""
    return (f"function sweep_{probe.kind}() -> unit = {{\n"
            + _indent(opening + body) + "\n}")


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" if line else "" for line in text.split("\n"))


def _main(spec: Spec) -> str:
    calls = [f'print_endline("# vectors emitted by the generated harness for '
             f'{spec.name}")',
             'print_endline("# fields are lowercase hex, width fixed by the field")']
    calls.extend(f"sweep_{probe.kind}()" for probe in spec.probes)
    return "function main() -> unit = {\n  " + ";\n  ".join(calls) + "\n}\n"


# --- execution helpers ------------------------------------------------------


def work_dir(lane_root: Path, spec: str) -> Path:
    """Return (and create) the build/run directory `lane_root / WORK / spec`."""
    path = lane_root / WORK / spec
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate(root: Path, spec: Spec, work: Path, out: list[str], *,
             model_root: Path | None = None) -> Path | None:
    """Emit, compile, and run the Sail harness for `spec`, returning the generated `vectors.txt` path."""
    base = root if model_root is None else model_root
    work.mkdir(parents=True, exist_ok=True)
    harness_path = work / f"{spec.name}.sail"
    harness_path.write_text(harness(spec, TOOL), encoding="utf-8", newline="\n")
    sources = [base / source for source in spec.sources] + [harness_path]
    binary = sailrig.build(sources, work, out, stem=spec.name)
    if binary is None:
        return None
    vectors = work / VECTORS
    if not sailrig.emit(binary, vectors, out):
        return None
    return vectors
