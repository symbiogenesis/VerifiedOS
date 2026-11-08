# SPDX-License-Identifier: Apache-2.0
"""Deterministic source-mutation generator for Sail (`.sail`) and Rocq (`.v`) files.

Applies `OPERATORS` across mutable declaration regions (`SAIL_MUTABLE` / `COQ_MUTABLE`)
outside comments and string literals, producing ordered `Mutant` instances evaluated by
[seeded.py](seeded.py) oracles.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from vos.proofs import DECLARATIONS, VOID, decorations, strip_comments

SAIL = "sail"
COQ = "coq"
LANES = (SAIL, COQ)

# Top-level Sail declaration keywords that open a source region.
SAIL_TOP = re.compile(
    r"^(function|val|let|type|mapping|register|struct|enum|union|infix|overload|"
    r"scattered|end|default|\$\[|\$)")

# Sail region kinds mutated by default (`val` and `type` mostly yield stillborn mutants).
SAIL_MUTABLE = ("function", "let", "mapping")

# Top-level Rocq vernacular keywords that open a source region.
COQ_TOP = re.compile("(" + "|".join((
    *DECLARATIONS, "Let", "Proof", "Qed", "Defined", "Admitted", "Require", "Import",
    "Export", "Arguments", "Print", "Section", "End", "Notation", "Local", "Global", "Set",
    "Unset", "Open", "Close", "Hint", "Class", "Variable", "Variables", "Parameter",
    "Parameters", "Axiom", "Axioms", "Context", "Ltac", "Ltac2", "From")) + r")(?![\w'])")

# Rocq definitional region kinds mutated by default (proof scripts are excluded).
COQ_MUTABLE = ("Definition", "Fixpoint", "Inductive", "Record")

_COMMAND_WORD = re.compile(r"([A-Z]\w*)")


@dataclass(frozen=True)
class Region:
    """Top-level source declaration block (`[start, end)`)."""

    keyword: str
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class Mutant:
    """Single token-rewrite mutant at `[start, end)` on `line` of `path`."""

    ident: str
    operator: str
    path: str
    line: int
    start: int
    end: int
    before: str
    after: str

    def apply(self, text: str) -> str:
        """Return `text` with this mutation applied."""
        return text[:self.start] + self.after + text[self.end:]

    @property
    def what(self) -> str:
        return f"{self.path}:{self.line} `{self.before}` -> `{self.after}`"


@dataclass(frozen=True)
class Operator:
    """Named token-rewrite mutation operator and the lanes (`SAIL`, `COQ`) it targets."""

    name: str
    lanes: tuple[str, ...]
    pattern: re.Pattern[str]
    rewrite: Callable[[re.Match[str]], str]
    what: str


def _const_inc(m: re.Match[str]) -> str:
    return str(int(m.group(0)) + 1)


def _slice_down(m: re.Match[str]) -> str:
    return f"[{int(m.group(1)) - 1} .. {int(m.group(2)) - 1}]"


def _fixed(repl: str) -> Callable[[re.Match[str]], str]:
    def rewrite(_m: re.Match[str]) -> str:
        return repl
    return rewrite


def _lit(name: str, lanes: tuple[str, ...], find: str, repl: str,
         what: str) -> Operator:
    return Operator(name=name, lanes=lanes, pattern=re.compile(find),
                    rewrite=_fixed(repl), what=what)


OPERATORS: tuple[Operator, ...] = (
    _lit("le-to-lt", LANES, r"<=(?!>)", "<", "a bound made strict"),
    _lit("lt-to-le", LANES, r"(?<![<>=])<(?![<=>])", "<=", "a bound made inclusive"),
    _lit("ge-to-gt", LANES, r">=", ">", "a bound made strict"),
    _lit("gt-to-ge", LANES, r"(?<![<>=-])>(?![<=>])", ">=", "a bound made inclusive"),
    _lit("eq-to-ne", (SAIL,), r"==", "!=", "an equality inverted"),
    _lit("ne-to-eq", (SAIL,), r"!=", "==", "an inequality inverted"),
    _lit("plus-to-minus", LANES, r" \+ ", " - ", "an addition made a subtraction"),
    _lit("minus-to-plus", LANES, r" - ", " + ", "a subtraction made an addition"),
    _lit("and-to-or", (SAIL,), r"(?<![&])&(?![&])", "|", "a conjunction made a union"),
    _lit("or-to-and", (SAIL,), r"(?<![|])\|(?![|])", "&", "a union made a conjunction"),
    _lit("shl-to-shr", (SAIL,), r"<<", ">>", "a shift reversed"),
    _lit("shr-to-shl", (SAIL,), r">>", "<<", "a shift reversed"),
    _lit("not-dropped", (SAIL,), r"\bnot\(", "(", "a negation removed"),
    _lit("zext-to-sext", (SAIL,), r"\bzero_extend\b", "sign_extend",
         "a widening made signed"),
    _lit("sext-to-zext", (SAIL,), r"\bsign_extend\b", "zero_extend",
         "a widening made unsigned"),
    _lit("andb-to-orb", (COQ,), r"\bandb\b", "orb", "a conjunction made a disjunction"),
    _lit("orb-to-andb", (COQ,), r"\borb\b", "andb", "a disjunction made a conjunction"),
    _lit("leb-to-ltb", (COQ,), r"\bNat\.leb\b", "Nat.ltb", "a bound made strict"),
    _lit("ltb-to-leb", (COQ,), r"\bNat\.ltb\b", "Nat.leb", "a bound made inclusive"),
    _lit("andalso-to-orelse", (COQ,), r"&&", "||", "a conjunction made a disjunction"),
    _lit("negb-dropped", (COQ,), r"\bnegb\s+", "", "a negation removed"),
    _lit("true-to-false", LANES, r"\btrue\b", "false", "a constant inverted"),
    _lit("false-to-true", LANES, r"\bfalse\b", "true", "a constant inverted"),
    # Lookbehind preserves hex/bit literals (`0x1f`, `0b0101`); lookahead allows `.` at sentence end.
    Operator("const-inc", LANES, re.compile(r"(?<![\w.])\d+(?!\w)"), _const_inc,
             "a numeric literal off by one"),
    Operator("slice-down", (SAIL,), re.compile(r"\[(\d+) \.\. (\d+)\]"), _slice_down,
             "a bit slice moved down one position"),
)


_OPENERS = {COQ: re.compile(r'\(\*|"'), SAIL: re.compile(r'/[/*]|"')}
_BLOCK_OR_STRING = re.compile(r'/\*|"')
_COQ_COMMENT = re.compile(r"\(\*|\*\)")
_STRING_TOKEN = re.compile(r'\\[\s\S]?|"')


def mask(text: str, lane: str) -> list[bool]:
    """Return a per-character boolean mask that is True outside comments and string literals."""
    size = len(text)
    ok = [True] * size
    opener = _OPENERS.get(lane, _BLOCK_OR_STRING)
    cursor = 0
    while found := opener.search(text, cursor):
        start = found.start()
        opening = found.group()
        cursor = size
        if opening == '"':
            for boundary in _STRING_TOKEN.finditer(text, found.end()):
                if boundary.group() == '"':
                    cursor = boundary.end()
                    break
        elif opening == "//":
            end = text.find("\n", found.end())
            if end >= 0:
                cursor = end + 1
        elif lane == COQ:
            depth = 1
            for boundary in _COQ_COMMENT.finditer(text, found.end()):
                depth += 1 if boundary.group() == "(*" else -1
                if depth == 0:
                    cursor = boundary.end()
                    break
        else:
            end = text.find("*/", found.end())
            if end >= 0:
                cursor = end + 2
        ok[start:cursor] = [False] * (cursor - start)
    return ok


def _coq_head(code: str, at: int) -> tuple[str, str | None, int, int] | None:
    """Parse a Rocq command head at line offset `at` in comment-blanked `code`.

    Returns `(keyword, void_flag_or_None, region_start, keyword_end)`, or `None` if `at`
    does not open a top-level command.
    """
    found, opened = decorations(code, at)
    command = COQ_TOP.match(code, opened)
    if command is None and found:
        if any(decoration.group("bullet") is not None or decoration.group("word") == "Export"
               for decoration in found):
            found.clear()
            command = COQ_TOP.match(code, at)
        else:
            command = _COMMAND_WORD.match(code, opened)
    if command is None:
        return None
    start = at
    if found and found[0].group("bullet") is not None:
        found = found[1:]
        start = found[0].start() if found else command.start()
    void = next((str(decoration.group("word")) for decoration in found
                 if decoration.group("word") in VOID), None)
    return str(command.group(1)), void, start, command.end()


def regions(text: str, lane: str, lexical: list[bool] | None = None) -> list[Region]:
    """Partition `text` into top-level declaration `Region`s for `lane`."""
    starts: list[tuple[int, str, str]] = []
    read_to = 0
    offset = 0
    code = strip_comments(text, keep_offsets=True) if lane == COQ else text
    for line in text.splitlines(keepends=True):
        head: tuple[str, str] | None = None
        start = offset
        if lane == COQ:
            found = (_coq_head(code, offset)
                     if offset >= read_to and not code[offset].isspace() else None)
            if found is not None and lexical is None:
                lexical = mask(text, lane)
            if found is not None and lexical is not None and lexical[offset]:
                keyword, void, start, read_to = found
                stop = code.find("\n", read_to)
                head = (keyword if void is None else void,
                        code[read_to:stop + 1 if stop >= 0 else len(code)])
        else:
            sail = SAIL_TOP.match(line)
            head = (str(sail.group(1)), line[sail.end():]) if sail else None
        if head is not None:
            keyword, after = head
            name = re.match(r"[\w'.{}]+", after.strip())
            starts.append((start, keyword, name.group() if name else ""))
        offset += len(line)
    out: list[Region] = []
    for n, (start, keyword, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(text)
        out.append(Region(keyword=keyword, name=name, start=start, end=end))
    return out


def mutable_mask(text: str, lane: str, only: tuple[str, ...] | None = None,
                 named: tuple[str, ...] = ()) -> list[bool]:
    """Return a per-character admissibility mask (inside mutable regions and outside comments/strings)."""
    admitted = only if only is not None else (
        COQ_MUTABLE if lane == COQ else SAIL_MUTABLE)
    ok = mask(text, lane)
    inside = [False] * len(text)
    for region in regions(text, lane, ok):
        if region.keyword not in admitted:
            continue
        if named and region.name not in named:
            continue
        inside[region.start:region.end] = ok[region.start:region.end]
    return inside


def mutants(text: str, lane: str, path: str, *, only: tuple[str, ...] | None = None,
            named: tuple[str, ...] = (),
            operators: tuple[Operator, ...] = OPERATORS) -> list[Mutant]:
    """Generate all `Mutant`s for `text` in `lane`, ordered by operator then source offset."""
    if lane not in LANES:
        raise ValueError(f"{lane!r} is not a lane this engine carries")
    admissible = mutable_mask(text, lane, only, named)
    out: list[Mutant] = []
    for operator in operators:
        if lane not in operator.lanes:
            continue
        seen = 0
        line, cursor = 1, 0
        for found in operator.pattern.finditer(text):
            if not all(admissible[found.start():found.end()]):
                continue
            after = operator.rewrite(found)
            if after == found.group(0):
                continue
            line += text.count("\n", cursor, found.start())
            cursor = found.start()
            out.append(Mutant(
                ident=f"{operator.name}/{seen}", operator=operator.name, path=path,
                line=line,
                start=found.start(), end=found.end(),
                before=found.group(0), after=after))
            seen += 1
    return out


def lane_of(path: str) -> str:
    """Return `SAIL` for `.sail` paths or `COQ` for `.v` paths."""
    if path.endswith(".sail"):
        return SAIL
    if path.endswith(".v"):
        return COQ
    raise ValueError(f"{path} is neither a .sail nor a .v source, and those are the "
                     "two lanes this engine carries")
