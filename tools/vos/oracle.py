# SPDX-License-Identifier: Apache-2.0
"""The model-as-oracle vector generator: a domain description in, a Sail harness out.

This repository has proved the model-as-oracle technique twice and thrown the rig
away both times. M2.1 emitted 21,546 vectors from the model itself and held a C
instantiation to every line; R1a emitted 658,659 over thirteen kinds and held the
authored SystemVerilog to every line. Both rigs were the same three parts: a list of
model sources, a hand-written Sail file that picks inputs and prints answers, and a
text comparison. Only the middle part was ever specific to the question being asked,
and only a small fraction of *it* was: [tools/cheri-equiv/gen_vectors.sail](
../cheri-equiv/gen_vectors.sail) is 522 lines of which the per-function part is a
dozen, the rest being formatters, an LFSR, loop nests and a line discipline that any
second rig would have written again.

So this module owns those, and a **spec** owns the dozen. A spec is a JSON file under
[tools/oracle-specs/](../oracle-specs/) naming the model sources to compile, and one
or more *probes*: a line kind, the parameters a probe takes and how the domain walks
them, the Sail that calls the model with them, and the expressions to print. What
comes out is a Sail harness that prints one line per vector, which
[run.py oracle](cli/oracle.py) compiles against those sources and runs. **The vectors
cross as text**, which is M2.1's discipline and R1a's: no adapter sits between the two
implementations, neither is compiled against the other's types, and a disagreement
names a line a person reads on both sides.

**Which of the tree's two findings this answers.** M0.12's, that its corpus found an
encoding defect the `$[test]` harness structurally cannot, a `$[test]` calling
`execute` on an already-decoded instruction and so never seeing a mis-encoded word. A
probe here calls a Sail function at a domain this file walks, so what it reaches is
decided by the domain and not by what a property happens to be written about. The
other finding, M0.8d's, belongs to [run.py seed](cli/seed.py) and is answered there.

**Nothing here decides anything.** It picks inputs and formats answers; every value
right of an arrow is the model's, and a line the spec cannot print is a line the
oracle does not reach.

## The domain, which is the half worth declaring

Each parameter says how the sweep walks it, and the three answers are the three R1a
needed:

* `all` walks every value of the parameter's own width, which is what makes a sweep
  **exhaustive over its own domain**. R1a had two: decode over the whole 19-bit bounds
  encoding, and `perms_narrow` over all 4,096 masks `candperm` can hand it.
* `draw` takes the parameter from a maximal-length 36-bit shift register, which is the
  sampled sweep. The register is per probe and its seed is in the spec, so a run is
  reproducible and two runs of one spec produce the same bytes.
* `table` walks an explicit list of Sail literals, which is how the edges a sweep off
  entropy alone does not reach are named rather than hoped for. R1a's own measurement
  is why the shape exists: a defect inside `setCapBounds`'s exponent-increment branch
  reproduced 647,179 sampled vectors and was killed only by the 840 lines of a
  deliberate corner.

A probe may mix them: R1a's decode sweep is exhaustive over three fields with the
address riding the shift register, which is `all`, `all`, `all`, `draw`.

## The line format

One vector per line, `<kind> <inputs> -> <outputs>`, every field lowercase hex with no
prefix at a width fixed by the field rather than by the value in it, so a reproducing
implementation holding each field in a variable of that width prints the same digits
with a bare `%x`. Lines opening with `#` are commentary. It is R1a's format unchanged,
which is deliberate: the RTL lane's census and comparison read it already.
"""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from vos import sailrig

# Where the specs live, relative to the repository root. One file per spec, named for
# the spec, so `run.py oracle vectors --spec keccak` and `tools/oracle-specs/keccak.json`
# are the same word twice and never two.
SPECS = "tools/oracle-specs"

# The tool a reader runs to regenerate a harness, written into every emitted file, and
# this lane's working directory and vector file under the lane root. Named here rather
# than in the CLI because two tools drive this rig and neither may have its own name
# for where the other one's output went.
TOOL = "tools/run.py oracle"
WORK = "oracle"
VECTORS = "vectors.txt"

# What a `show` token may be: `h<n>` prints n hex nibbles, `b1` prints a bool as one
# digit. Held to a closed vocabulary rather than passed through, because a token this
# module cannot read would otherwise reach the generated Sail as a call to a function
# nothing defines, and fail several hundred lines from the spec that wrote it.
SHOW = re.compile(r"^(?:h(\d{1,2})|b1)$")

# A kind is the first token of every line the probe writes, and the RTL lane's census
# reads it back with `^([a-z]+) `. Held to that shape here so a spec cannot emit a line
# that census counts as commentary.
KIND = re.compile(r"^[a-z]+$")

# A Sail identifier, for a parameter name that has to survive into generated code.
IDENT = re.compile(r"^[a-z][a-z0-9_]*$")

# Names a parameter may not take, and the reason the list exists rather than the reason
# each member is on it: a parameter's name reaches the generated Sail as a binder, so a
# collision is a syntax error several hundred lines from the spec that caused it, and it
# reads as a defect in the emitter. `inc` and `dec` are the pair that found this, being
# Sail's bitvector order keywords and an entirely natural name for a step. The rest are
# the keywords a parameter name might plausibly want and the names this module emits
# for itself.
RESERVED = frozenset({
    "and", "as", "assert", "bitfield", "bitone", "bitzero", "bool", "by", "cast",
    "catch", "constraint", "dec", "default", "do", "effect", "else", "end", "enum",
    "exit", "false", "forall", "foreach", "from", "function", "if", "impl", "implicit",
    "in", "inc", "infix", "infixl", "infixr", "instantiation", "int", "let", "mapping",
    "match", "monadic", "nat", "operator", "overload", "private", "pure", "ref",
    "register", "repeat", "return", "scattered", "sizeof", "struct", "then", "throw",
    "to", "true", "try", "type", "undefined", "union", "unit", "until", "val", "var",
    "where", "while",
    # and this module's own, which the emitted sweep binds beside the parameters
    "b1", "hex", "lfsr36", "main", "nib", "rep", "seed",
})

# The shift register's width, and the polynomial x^36 + x^25 + 1. Maximal length, so a
# `draw` parameter walks 2^36 - 1 distinct values before it repeats. The width is 36
# because that is the address width the format this technique was first used on
# carries; a parameter wider than one draw takes two, which `_draw` composes.
LFSR_BITS = 36

# The widest parameter a `draw` can fill, being two draws concatenated. A wider one is
# refused at parse rather than emitted as Sail that does not typecheck.
DRAW_MAX = 2 * LFSR_BITS

# The widest field the hex formatters are emitted for. 32 nibbles is 128 bits, which is
# twice the frozen capability and wider than anything the model returns whole.
HEX_MAX = 32


class ParamRow(TypedDict, total=False):
    """One parameter of a probe, as the spec file writes it."""

    name: str
    width: int
    over: str
    rows: list[str]
    show: str


class ShowRow(TypedDict, total=False):
    """One printed answer: the Sail expression, and how wide a field it fills."""

    expr: str
    show: str


class ProbeRow(TypedDict, total=False):
    """One probe of a spec, as the spec file writes it."""

    kind: str
    what: str
    params: list[ParamRow]
    repeat: int
    seed: str
    body: list[str]
    shows: list[ShowRow]


class SpecRow(TypedDict, total=False):
    """One spec file, whole."""

    name: str
    what: str
    answers: str
    sources: list[str]
    probes: list[ProbeRow]


@dataclass(frozen=True)
class Param:
    """One parameter, parsed: its Sail name, its width, and how the sweep walks it."""

    name: str
    width: int
    over: str
    rows: tuple[str, ...]
    show: str

    @property
    def size(self) -> int:
        """How many values this parameter contributes to the nest, which is only
        meaningful for the two that are loops."""
        return len(self.rows) if self.over == "table" else 1 << self.width


@dataclass(frozen=True)
class Show:
    """One printed answer."""

    expr: str
    show: str


@dataclass(frozen=True)
class Probe:
    """One line kind: what it calls, over what domain, and what it prints."""

    kind: str
    what: str
    params: tuple[Param, ...]
    repeat: int
    seed: str
    body: tuple[str, ...]
    shows: tuple[Show, ...]

    @property
    def vectors(self) -> int:
        """How many lines this probe writes, which is arithmetic over its own domain
        and is what lets a spec state its size without running the model."""
        total = self.repeat
        for param in self.params:
            if param.over in ("all", "table"):
                total *= param.size
        return total


@dataclass(frozen=True)
class Spec:
    """One oracle: the model sources to compile against, and the probes to run."""

    name: str
    what: str
    answers: str
    sources: tuple[str, ...]
    probes: tuple[Probe, ...]

    @property
    def vectors(self) -> int:
        return sum(probe.vectors for probe in self.probes)


class SpecError(ValueError):
    """A spec this module refuses, named at the spec rather than at the Sail error its
    emission would have produced."""


def spec_path(root: Path, name: str) -> Path:
    return root / SPECS / f"{name}.json"


def names(root: Path) -> list[str]:
    """Every spec in the repository, sorted, so a listing is stable."""
    directory = root / SPECS
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def load(root: Path, name: str) -> Spec:
    """One spec, parsed and refused by name where it is malformed."""
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
    """A decoded spec file, held to the shape this module emits from.

    Every refusal names the spec's own field. The alternative is a Sail file that does
    not typecheck for a reason a reader has to work back from the emitted code to the
    line of JSON that produced it, which is the seam this whole module exists to close
    for the two implementations it puts either side of a text file.
    """
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
    """One body statement, held to being one.

    The generator joins statements with its own separator, so a line that carries a
    trailing `;` would emit a double separator and a Sail parse error in generated
    code. Refused here, where the spec's own line is what the message names.
    """
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
    """How many hex digits a show token spends, 0 for the bool. Refuses the token this
    module cannot emit a formatter for."""
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


# =====================================================================================
# the emission
# =====================================================================================


def harness(spec: Spec, tool: str) -> str:
    """The Sail harness for one spec, whole and deterministic.

    Deterministic to the byte, because a caller compares two runs of it: a seeded
    defect is killed by the vectors moving, and a harness that varied between two
    emissions would make every line move for a reason that is not the defect.
    """
    widest = max(_widths(spec), default=1)
    parts = [_preamble(spec, tool), _formatters(widest)]
    parts.extend(_probe_sail(probe) for probe in spec.probes)
    parts.append(_main(spec))
    return "\n".join(parts)


def _widths(spec: Spec) -> list[int]:
    """Every hex field width the harness prints, so the formatters emitted are the ones
    used and no more."""
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
    """The hex ladder and the bool, emitted to the width the spec actually spends.

    Stated per width rather than derived at run time, so the digits a field occupies
    are a property of the field and not of the value in it, which is what lets the
    other implementation print the same digits with a bare `%x`.
    """
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
    """One field, as the Sail that prints it.

    The hex formatters are emitted at whole nibbles and a great many of the model's own
    types are not, `CapLenBits` being 37 bits printed in ten digits, so every hex field
    is zero-extended into its formatter here rather than in the spec. The widening is
    arithmetic about two widths and not a decision somebody makes, and a spec writing
    it by hand would then be a spec that could get it wrong; a field *wider* than its
    formatter is still a Sail constraint failure, which is the loud answer wanted.
    """
    if show == "b1":
        return f"b1({expr})"
    return f"hex_{int(show[1:])}(zero_extend({expr}))"


def _probe_sail(probe: Probe) -> str:
    """One probe: the call that prints a line, and the nest that walks its domain."""
    return "\n".join([_probe_fn(probe), "", *_tables(probe), _sweep(probe), ""])


def _probe_fn(probe: Probe) -> str:
    args = ", ".join(f"{p.name} : bits({p.width})" for p in probe.params)
    pieces = [f'"{probe.kind}"']
    for param in probe.params:
        pieces.append('" "')
        pieces.append(_fmt(param.show, param.name))
    pieces.append('" ->"')
    for show in probe.shows:
        pieces.append('" "')
        pieces.append(_fmt(show.show, show.expr))
    printed = "\n    ^ ".join(pieces)
    statements = [*probe.body, f"print_endline(\n    {printed}\n  )"]
    joined = ";\n  ".join(statements)
    head = f"// {probe.what}" if probe.what else f"// the `{probe.kind}` vectors"
    return f"{head}\nfunction probe_{probe.kind}({args}) -> unit = {{\n  {joined}\n}}"


def _tables(probe: Probe) -> list[str]:
    """The literal tables a `table` parameter walks, one function each.

    A `match` over the index with the last row as the wildcard, which is the shape the
    Sail typechecker wants: an index this cannot place is the last row rather than an
    incomplete match, and the loop that drives it never hands one.
    """
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
    """The statements that fill one drawn parameter, one draw or two.

    Two where the parameter is wider than the register, taking the high bits from the
    first draw and the whole of the second below them, which is the composition the
    hand-written rig made at the one width it needed and this makes at every width.
    """
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
    """The loop nest for one probe: every `all` and `table` parameter a loop, the drawn
    ones taken inside it, and the repeat innermost."""
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


# =====================================================================================
# the run
# =====================================================================================


def work_dir(lane_root: Path, spec: str) -> Path:
    """Where one spec builds and runs in this lane.

    Under the lane root and never in the checkout: the file a run produces is derived
    from the checkout rather than part of it, and two worktrees running at once must
    not write one path.
    """
    path = lane_root / WORK / spec
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate(root: Path, spec: Spec, work: Path, out: list[str], *,
             model_root: Path | None = None) -> Path | None:
    """Emit the harness for one spec, compile it against the spec's sources, run it,
    and hand back the vector file.

    `model_root` is where the spec's sources are read from, defaulting to the checkout.
    A caller holding a mutated copy of the model passes its own tree, which is what
    lets [run.py seed](cli/seed.py) point this at a defect without writing into `model/`.
    """
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
