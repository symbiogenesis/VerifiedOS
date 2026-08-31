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

# Rocq's command keywords, same reading. The list is what this repository's own proofs
# use plus the neighbours a proof file reaches for, and a command outside it opens no
# region, which leaves its lines attached to the region above: that is why `Proof` and
# `Qed` are both here even though neither is mutable.
COQ_TOP = re.compile(
    r"^(Definition|Fixpoint|Inductive|Record|Lemma|Theorem|Example|Corollary|"
    r"Proposition|Remark|Fact|Proof|Qed|Defined|Admitted|Require|Import|Export|"
    r"Arguments|Print|Section|End|Notation|Local|Global|Set|Unset|Open|Close|"
    r"Hint|Instance|Class|Variable|Parameter|Axiom|Context|Ltac|From)")

# And the ones a mutation may land in: the definitional commands, and deliberately not
# a `Lemma` or a `Theorem`. A mutation inside a proof script breaks the proof and kills
# itself, which decides nothing about whether the statement constrains the definition;
# a mutation inside a *definition* is the question this engine is asking.
COQ_MUTABLE = ("Definition", "Fixpoint", "Inductive", "Record")


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


def mask(text: str, lane: str) -> list[bool]:
    """Which characters a mutation may land on: everything but comments and strings.

    Rocq comments **nest**, which is why this is a scanner and not a regular
    expression: `(* a (* b *) c *)` closes once, and a pattern that stopped at the
    first `*)` would leave ` c *)` mutable and produce mutants that are pure noise.
    Sail's `/* */` do not nest, and it costs nothing to run the same scanner over both
    with the depth capped at one.
    """
    size = len(text)
    ok = [True] * size
    opener, closer = ("(*", "*)") if lane == COQ else ("/*", "*/")

    def blank(at: int, run: int) -> None:
        """Mark a run of characters unmutable, clipped to the text: an opener at the
        very last character is not a reason for an index error."""
        for n in range(at, min(at + run, size)):
            ok[n] = False

    i = 0
    depth = 0
    line_comment = False
    in_string = False
    while i < size:
        if line_comment:
            ok[i] = False
            line_comment = text[i] != "\n"
            i += 1
            continue
        if depth:
            if lane == COQ and text.startswith(opener, i):
                depth += 1
                blank(i, 2)
                i += 2
                continue
            if text.startswith(closer, i):
                depth -= 1
                blank(i, 2)
                i += 2
                continue
            ok[i] = False
            i += 1
            continue
        if in_string:
            ok[i] = False
            if text[i] == "\\":
                blank(i, 2)
                i += 2
                continue
            in_string = text[i] != '"'
            i += 1
            continue
        if text.startswith(opener, i):
            depth = 1
            blank(i, 2)
            i += 2
            continue
        if lane == SAIL and text.startswith("//", i):
            line_comment = True
            continue
        if text[i] == '"':
            in_string = True
            ok[i] = False
            i += 1
            continue
        i += 1
    return ok


def regions(text: str, lane: str) -> list[Region]:
    """The source's top-level blocks, each from its own keyword to the next one.

    A line-based reading rather than a parse, and it is enough for what it decides: a
    block's *extent* only has to be right about which command a character belongs to,
    and both languages here put every top-level command at the start of a line.
    """
    top = COQ_TOP if lane == COQ else SAIL_TOP
    starts: list[tuple[int, str, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        found = top.match(line)
        if found:
            rest = line[found.end():].strip()
            name = re.match(r"[\w'.{}]+", rest)
            starts.append((offset, found.group(1), name.group() if name else ""))
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
    for region in regions(text, lane):
        if region.keyword not in admitted:
            continue
        if named and region.name not in named:
            continue
        for i in range(region.start, region.end):
            inside[i] = True
    return [a and b for a, b in zip(ok, inside, strict=True)]


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
        for found in operator.pattern.finditer(text):
            if not all(admissible[found.start():found.end()]):
                continue
            after = operator.rewrite(found)
            if after == found.group(0):
                continue
            out.append(Mutant(
                ident=f"{operator.name}/{seen}", operator=operator.name, path=path,
                line=text.count("\n", 0, found.start()) + 1,
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
