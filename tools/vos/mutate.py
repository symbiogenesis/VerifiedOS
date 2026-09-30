# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator: mutants produced from a source, not written by hand.

[run.py selftest](cli/selftest.py) proved the method on the checker's own rules and
proved it the expensive way: at least one mutant per rule, each authored, each stating
in prose the defect it seeds. That is the right shape for a *registry*, where a rule and
its mutant are two halves of one claim, and it is the wrong shape for an artifact with
no registry behind it. A Sail function and a Gallina definition have hundreds of sites
each and nobody is going to write hundreds of cases; what they need is an engine that
walks the source and produces the population.

So this module holds mutation **operators** rather than mutants: a named rewrite of a
token, applied at every site of a source where the token occurs and the site is one a
mutation may land on. What comes out is deterministic, ordered, and countable before
anything is compiled, which is what makes a run of it a measurement.

**Three verdicts and not two.** A mutant that does not compile is *stillborn*: nothing
was decided about the oracle, because the oracle never ran. A mutant that compiles and
moves the oracle's answer is *killed*. A mutant that compiles and does not move it
*survived*, and a survivor is the finding: the oracle does not reach that site, which
is R1a's own measurement ("a vector population off entropy alone cannot tell one
clause of `setCapBounds` from its absence") stated as a loop instead of as a paragraph.
Reporting stillborn mutants as kills is the standard way a mutation score is inflated,
so the three are counted apart. What a verdict is and how a run is scored over them is
[seeded.py](seeded.py)'s, shared with every oracle that runs one; what is here is the
population.

**Which finding this answers.** M0.8d's: the property that named the *pi* defect was
written before the vectors and never ran, the harness running alphabetically so the
symptom aborted the executable ahead of the cause. A written property is a person's
choice about what to check next and inherits every blind spot that choice has. A
generated mutant is not chosen at all: the site is walked, and what is left standing
after the walk is what the oracle does not decide about.

## Where a mutation may land

Two masks, and both matter. A mutation inside a comment or a string literal changes
the bytes and nothing else, so the mutant compiles to the same program, the oracle
agrees, and it reports as a survivor about nothing; comments and strings are therefore
cut out before any operator runs. And a mutation inside a Coq *proof script* breaks the
proof and kills itself, which says nothing about whether the statement constrains the
definition; so the Coq lane's default region is the definitional commands alone, and
`Proof`-to-`Qed` is outside it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from vos.proofs import DECLARATIONS, VOID, decorations, strip_comments

# The lanes this engine carries. Named rather than passed as free strings, because the
# comment syntax, the region keywords and the operator table are three facts that have
# to agree about which language is being mutated.
SAIL = "sail"
COQ = "coq"
LANES = (SAIL, COQ)

# Sail's top-level declaration keywords, which is how a region is found: a block runs
# from one of these at the start of a line to the line before the next.
SAIL_TOP = re.compile(
    r"^(function|val|let|type|mapping|register|struct|enum|union|infix|overload|"
    r"scattered|end|default|\$\[|\$)")

# The ones a mutation may land in by default. A `val` is a signature and a `type` is an
# abbreviation, so mutating either is a stillborn mutant with high probability and no
# information; what carries behaviour is a function body and a table written as a `let`.
SAIL_MUTABLE = ("function", "let", "mapping")

# Rocq's command keywords, same reading. Every vernacular whose sentence binds a
# top-level name is the shared lexer's `DECLARATIONS`, Rocq 9.3's theorem keywords,
# recursive definitions and inductive types among them, and `Let` binds one inside a
# section; beside them, the commands this repository's own proofs use plus the
# neighbours a proof file reaches for. A command outside the list opens no region, which
# leaves its lines attached to the region above: that is why `Proof` and `Qed` are both
# here even though neither is mutable, and why a `Variant` or a `CoFixpoint` missing
# from it joined the definition above it.
COQ_TOP = re.compile("^(" + "|".join((
    *DECLARATIONS, "Let", "Proof", "Qed", "Defined", "Admitted", "Require", "Import",
    "Export", "Arguments", "Print", "Section", "End", "Notation", "Local", "Global", "Set",
    "Unset", "Open", "Close", "Hint", "Class", "Variable", "Parameter", "Axiom", "Context",
    "Ltac", "From")) + ")")

# And the ones a mutation may land in: the definitional commands, and deliberately not
# a `Lemma` or a `Theorem`. A mutation inside a proof script breaks the proof and kills
# itself, which decides nothing about whether the statement constrains the definition;
# a mutation inside a *definition* is the question this engine is asking.
COQ_MUTABLE = ("Definition", "Fixpoint", "Inductive", "Record")

# What may stand before a Rocq command's keyword is the shared lexer's decoration grammar
# ([proofs.py](proofs.py)): quoted and legacy attributes, control flags, and the bullets,
# braces and goal selectors of a proof, read over the line with its comments blanked, so
# a comment is the separator Rocq's lexer reads. A line opening with them opens a region
# keyed by the command they decorate, so `#[local] Definition` is a definition rather
# than the tail of the region above it and `Local Definition` is not a `Local` nobody
# mutates; written on lines of their own, they wait for the command under them and the
# region opens where they do. `Fail` and `Succeed` run the command and keep nothing it
# defines, so a region under either, on the command's line or above it, is keyed by the
# flag and no mutation lands in it.
#
# The command under a decoration where `COQ_TOP` does not name it, `Opaque` under
# `Local` being one this repository's proofs write. A command is capitalised, so a word
# under a flag that is not is a tactic's, `Time lia` in a proof script, and no command.
_COMMAND_WORD = re.compile(r"([A-Z]\w*)")


@dataclass(frozen=True)
class Region:
    """One block of a source: where it starts, where it ends, and what opened it."""

    keyword: str
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class Mutant:
    """One seeded defect: where it lands, what it replaces, and what with."""

    ident: str
    operator: str
    path: str
    line: int
    start: int
    end: int
    before: str
    after: str

    def apply(self, text: str) -> str:
        """The mutated source. Held rather than stored, a population of several hundred
        each carrying a copy of a fifty-kilobyte file being a megabyte of the same
        bytes."""
        return text[:self.start] + self.after + text[self.end:]

    @property
    def what(self) -> str:
        return f"{self.path}:{self.line} `{self.before}` -> `{self.after}`"


# One operator: a name, the lanes it applies to, the pattern that finds a site, and the
# rewrite. Typed rather than a bare tuple, because a table of callbacks nothing types
# is a table where a member with the wrong shape is found by running it.
@dataclass(frozen=True)
class Operator:
    """A named rewrite of one token, and where it is admitted."""

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
    """A rewrite that ignores what it matched, which is most of them."""
    def rewrite(_m: re.Match[str]) -> str:
        return repl
    return rewrite


def _lit(name: str, lanes: tuple[str, ...], find: str, repl: str,
         what: str) -> Operator:
    """The common shape: one fixed pattern for a fixed replacement."""
    return Operator(name=name, lanes=lanes, pattern=re.compile(find),
                    rewrite=_fixed(repl), what=what)


# The operators, both lanes. Each is a rewrite that keeps the source a plausible
# program: a relation for its neighbour, a connective for its dual, a constant off by
# one, a slice off by one bit. What is deliberately absent is any operator that deletes
# a statement or reorders one, because those are stillborn far more often than they are
# informative and a population dominated by stillborn mutants measures the compiler.
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
    # The lookbehind keeps a hex or bit literal whole, `0x1f` and `0b0101` each being
    # one token whose digits are not arithmetic. The lookahead deliberately admits a
    # following `.`, which is how a Rocq command ends: `Nat.leb n 3.` carries a literal
    # and a period, and a pattern excluding both would read every Gallina definition as
    # carrying no constant at all.
    Operator("const-inc", LANES, re.compile(r"(?<![\w.])\d+(?!\w)"), _const_inc,
             "a numeric literal off by one"),
    Operator("slice-down", (SAIL,), re.compile(r"\[(\d+) \.\. (\d+)\]"), _slice_down,
             "a bit slice moved down one position"),
)


# Search only for lexical boundaries; ordinary source bytes need no Python loop.
_OPENERS = {COQ: re.compile(r'\(\*|"'), SAIL: re.compile(r'/[/*]|"')}
_BLOCK_OR_STRING = re.compile(r'/\*|"')
_COQ_COMMENT = re.compile(r"\(\*|\*\)")
_STRING_TOKEN = re.compile(r'\\[\s\S]?|"')


def mask(text: str, lane: str) -> list[bool]:
    """Which characters a mutation may land on: everything but comments and strings.

    Searches advance from the previous boundary, so each source span is scanned
    once. Rocq comments nest; Sail comments do not. Unterminated constructs mask
    through EOF, and an escaped quote remains part of its string in either lane.
    """
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
                # A line comment excludes its terminating newline as well.
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


def _coq_head(line: str) -> tuple[list[str], str, str] | None:
    """The decorations a Rocq line opens with, each as its word, `#[` for an attribute or
    a bullet as itself, the command keyword under them and the rest of the line after it,
    or None where the line opens with neither. `line` is the line with its comments
    blanked.

    A bare line names a command exactly when it starts with a `COQ_TOP` keyword. A
    decorated one names the `COQ_TOP` keyword under it, else the capitalised command
    word under it, else the empty keyword, which the caller reads as decorations whose
    command is on a later line where only comments follow them and as a tactic's flag
    otherwise. Whether the line is code at all is the caller's to decide too, a line
    inside a comment reading the same.

    A bullet, a brace or a goal selector, and `Export`, name a command only where a
    `COQ_TOP` keyword follows them, the line otherwise read bare. At a line's start `-`,
    `+`, `*` and `{` continue a term as often as they open a proof step, and a capitalised
    word after one is as often a constructor as a command. `Export` decorates an option
    command, `Set` or `Unset`, and is otherwise the command that exports a module.
    """
    found, at = decorations(line) if line[:1] and not line[:1].isspace() else ([], 0)
    rest = line[at:]
    command = COQ_TOP.match(rest)
    if command is None and found:
        if any(decoration.group("bullet") is not None or decoration.group("word") == "Export"
               for decoration in found):
            found, rest = [], line
            command = COQ_TOP.match(rest)
        else:
            command = _COMMAND_WORD.match(rest)
    flags = [str(decoration.group("word") or (decoration.group("bullet") or "#[").strip())
             for decoration in found]
    if command is not None:
        return flags, str(command.group(1)), rest[command.end():]
    return (flags, "", rest) if flags else None


def _prose(text: str, start: int, end: int, lexical: list[bool]) -> bool:
    """Whether `text[start:end]` carries nothing but blank space, comments and strings."""
    return all(not lexical[at] or text[at].isspace() for at in range(start, end))


def regions(text: str, lane: str, lexical: list[bool] | None = None) -> list[Region]:
    """The source's top-level blocks, each from its own keyword to the next one.

    A line-based reading rather than a parse, and it is enough for what it decides: a
    block's *extent* only has to be right about which command a character belongs to,
    and both languages here put every top-level command at the start of a line. A Rocq
    command's decorations are read past, so the region is keyed by what they decorate,
    and opens at the first of them where they stand on lines of their own above it,
    blank lines and comments between them. A Rocq line is read with its comments blanked
    at their own offsets, each the separator Rocq's lexer reads it as, and one whose first
    character lies inside a comment or a string is prose that opens nothing, whatever
    word it starts with, its lines staying in the region above. `lexical` is
    `mask(text, lane)` where the caller holds it already.
    """
    starts: list[tuple[int, str, str]] = []
    # a Rocq command's decorations on lines of their own, waiting for the command they
    # decorate: where the first of them stands, or -1 where none waits, and every flag
    waiting = -1
    waited: list[str] = []
    offset = 0
    code = strip_comments(text, keep_offsets=True) if lane == COQ else text
    for line in text.splitlines(keepends=True):
        head: tuple[str, str] | None = None
        start = offset
        if lane == COQ:
            end = offset + len(line)
            found = _coq_head(code[offset:end])
            if lexical is None and (found is not None or waiting >= 0):
                lexical = mask(text, lane)
            if found is not None and lexical is not None and lexical[offset]:
                flags, keyword, after = found
                waited.extend(flags)
                if keyword:
                    start = offset if waiting < 0 else waiting
                    void = next((flag for flag in waited if flag in VOID), None)
                    head = (keyword if void is None else void, after)
                    waiting = -1
                    waited.clear()
                elif _prose(text, end - len(after), end, lexical):
                    waiting = offset if waiting < 0 else waiting
                else:
                    waiting = -1
                    waited.clear()
            elif waiting >= 0 and lexical is not None \
                    and not _prose(text, offset, end, lexical):
                waiting = -1
                waited.clear()
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
    """The whole admissibility mask: inside a mutable region, outside a comment.

    `only` is the set of region keywords admitted, defaulting to the lane's own; the
    Coq default is what keeps a mutation out of a proof script, which is the difference
    between asking whether a statement constrains a definition and asking whether a
    tactic still applies.
    """
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
    """Every mutant of one source, ordered by operator and then by site.

    Deterministic, so a run is repeatable and a `--limit` takes the same prefix twice.
    Overlapping sites across operators are expected and are not deduplicated: two
    operators rewriting one token are two different defects, and the oracle may kill
    one and not the other.
    """
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
            # Matches advance within each operator: never recount the prefix.
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
    """Which lane a path belongs to, by its own suffix. Refused rather than guessed:
    an engine that mutated a file with the wrong comment syntax would cut the wrong
    spans out and report survivors about nothing."""
    if path.endswith(".sail"):
        return SAIL
    if path.endswith(".v"):
        return COQ
    raise ValueError(f"{path} is neither a .sail nor a .v source, and those are the "
                     "two lanes this engine carries")
