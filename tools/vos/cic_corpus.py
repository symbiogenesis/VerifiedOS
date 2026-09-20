# SPDX-License-Identifier: Apache-2.0
"""What the shipped proof corpus actually asks a CIC checker to decide.

M6.2b-0's [corpus and source qualification](../../docs/assurance/cic-checker-qualification.md#corpus-and-source-qualification)
step wants a feature and dependency report over the real proofs rather than a
handwritten count of surface `Fixpoint` declarations. This module is the parse half of
that report: every reading below is a stated predicate over text Rocq itself printed,
and nothing here guesses a feature a query did not show.

**Three readings, and they decide different things.** The *kernel* reading is
`Print All Dependencies`, which walks the compiled proof term, including the bodies of
`Qed` constants, and names each dependency under one of four headings. The *declaration*
reading is `About`, which says whether a constant is universe polymorphic, whether it is
opaque, and what kind of object it is. The *term* reading is `Print` under
`Set Printing All`, whose notation-free output is where a `fix` binder, a mutual block
and a dependent `match` become visible at all. A source-text reading stands beside
them, counting the vernaculars a file spells, and it is kept separate on purpose: a
`Fixpoint` a proof never uses is a line in a file and not an obligation on a checker.

**Each term-level predicate over-approximates in a declared direction**, because a
printer is not a parser and this module refuses to pretend otherwise:

- `fix-binder` and `cofix-binder` are the tokens `fix` and `cofix` printed outside an
  identifier. Under `Set Printing All` there is no notation that can spell either.
- `fix-binders-multiple` is two or more such binders in one printed declaration. That
  is nesting wherever the second sits inside the first's body, and it is two siblings
  wherever it does not; the report does not separate them, and a reader who needs the
  distinction opens the constant.
- `fix-binder-mutual` is the `for <name>` selector Rocq prints at the end of a mutual
  block and nowhere else. A mutual block prints one `fix` token, so this reading and
  the preceding one are independent.
- `match-dependent-return` is a `match` head carrying an `as` or `in` token before its
  `return` or `with`. Those clauses are printed exactly when the elimination's return
  predicate is annotated, which is the shape a checker has to typecheck; a `let ... in`
  inside an unparenthesized scrutinee would also satisfy it, which is the direction
  this errs in.
- The primitive readings are name membership, over both the printed declaration and the
  dependency closure, so a primitive reached only through a library constant still
  counts.

**What no reading here decides is whether conversion is required.** A constant whose
closure holds no transparent constant cannot need delta reduction of one, and that is
the only conversion statement this module makes. The converse does not follow: a
transparent dependency may be used at its name alone. Deciding the positive case means
rechecking the corpus with those constants sealed, which is M6.2b-0's own experiment
and not a figure this report may quote.
"""

import re
from dataclasses import dataclass, field

from vos.proofs import sentences

# The four headings `Print All Dependencies` prints, and the key each one lands under.
# The command prints nothing else, and a fifth heading is a Rocq change this parse has
# to see rather than skip, which is why an unknown heading refuses.
SECTIONS: dict[str, str] = {
    "Axioms:": "axioms",
    "Variables:": "variables",
    "Opaque constants:": "opaque",
    "Transparent constants:": "transparent",
}
CLOSED = "Closed under the global context"

# The marker a query writes before each answer, so a block belongs to the constant it
# was asked about rather than to whichever answer happened to precede it.
MARKER = "VOS_CIC_CORPUS|"

# Notations off, elision off, wrapping off. `Set Printing Universes` is deliberately
# absent: it decorates every sort in every printed term, and the universe fact this
# report needs is per constant and comes from `About` instead.
QUERY_SETTINGS = """\
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
"""

QUALIFIED = re.compile(r"[\w'][\w']*(?:\.[\w'][\w']*)*")
# A heading and an entry are told apart by the space before the colon, which the
# printer is consistent about: `Opaque constants:` carries none and `usesax :` does.
# Without that, a heading Rocq gained would read as a dependency named after it.
_HEADING = re.compile(r"^([^\s:](?:[^:]*[^\s:])?):$")
_ENTRY = re.compile(r"^([\w'][\w']*(?:\.[\w'][\w']*)*)\s+:")
_EXPANDS = re.compile(r"^Expands to:\s+(\w+)\s+(\S+)")
_WORD = re.compile(r"[\w']+")
_FIX = re.compile(r"(?<![\w'])fix(?![\w'])")
_COFIX = re.compile(r"(?<![\w'])cofix(?![\w'])")
_FOR = re.compile(r"(?<![\w'])for\s+[\w']+")
_MATCH = re.compile(r"(?<![\w'])match(?![\w'])")

# Where a primitive shows itself: in a printed declaration, or in a closure name. The
# spellings are the ones Rocq's own libraries carry for the four primitive families.
PRIMITIVES: dict[str, tuple[str, ...]] = {
    "primitive-int63": ("Uint63", "Int63", "PrimInt63"),
    "primitive-float64": ("PrimFloat", "Float64", "SpecFloat"),
    "primitive-array": ("PArray", "PrimArray"),
    "primitive-string": ("PString", "PrimString"),
}

# The vernaculars the source reading counts. Kept flat and named, because a count over
# a file is a count over a file: it says what an author wrote, never what a proof uses.
SOURCE_VERNACULARS: tuple[str, ...] = (
    "Section", "End", "Module", "Fixpoint", "CoFixpoint", "Inductive", "CoInductive",
    "Record", "Variant", "Axiom", "Parameter", "Primitive", "Polymorphic",
    "Monomorphic", "Cumulative", "NonCumulative", "Equations", "Program",
)


class ParseError(ValueError):
    """A native response cannot support this reading."""


# One constant's transitive closure, split the way Rocq splits it: one list per key of
# `SECTIONS`. A mapping rather than a record because the headings are data here, the
# parse placing an entry under whichever heading opened it.
type Dependencies = dict[str, list[str]]

# The headings whose members are constants rather than declared assumptions, which is
# the split the conversion reading and the primitive reading both walk.
CLOSURE_KEYS: tuple[str, ...] = ("axioms", "opaque", "transparent")


def empty_dependencies() -> Dependencies:
    """A closure with every heading present and none of them populated."""
    return {key: [] for key in SECTIONS.values()}


# The three universe sentences `About` writes, longest first so that the template form
# is read as itself rather than as the plain one it ends with. Template polymorphism is
# its own answer here because it is its own rule in the kernel: an inductive's sort is
# computed from its arguments' rather than quantified, which a profile decision has to
# admit or exclude by name and cannot fold into either of the other two.
UNIVERSE_SENTENCES: tuple[tuple[str, str], ...] = (
    ("is not universe polymorphic", "monomorphic"),
    ("is template universe polymorphic", "template"),
    ("is universe polymorphic", "polymorphic"),
)


@dataclass(frozen=True)
class About:
    """What `About` says a symbol is: its kind, its opacity and its universes."""

    kind: str
    expands_to: str
    universes: str
    opacity: str

    @property
    def universe_polymorphic(self) -> bool:
        """Whether the symbol's universes are quantified or computed rather than fixed."""
        return self.universes != "monomorphic"


@dataclass
class Constant:
    """One enumerated symbol and every reading this module makes of it."""

    name: str
    type: str = ""
    kind: str = ""
    opacity: str = "n/a"
    universes: str = "monomorphic"
    features: list[str] = field(default_factory=list)
    dependencies: Dependencies = field(default_factory=empty_dependencies)
    body_printed: bool = False


def blocks(stdout: str, keys: list[str]) -> dict[str, str]:
    """Split one query's output into the answer each marker introduced.

    The keys are supplied rather than discovered, so a missing answer is a refusal
    here and not a shorter dictionary a caller reads as an empty result.
    """
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in stdout.splitlines():
        if line.startswith(MARKER):
            current = line[len(MARKER):].strip()
            if current in found:
                raise ParseError(f"the query answered {current} twice")
            found[current] = []
        elif current is None:
            if line.strip():
                raise ParseError(f"unframed query output: {line}")
        else:
            found[current].append(line)
    missing = [key for key in keys if key not in found]
    if missing:
        raise ParseError(f"the query left {len(missing)} answer(s) unwritten, "
                         f"first {missing[0]}")
    extra = [key for key in found if key not in keys]
    if extra:
        raise ParseError(f"the query answered {extra[0]}, which was not asked")
    return {key: "\n".join(found[key]).strip("\n") for key in keys}


def parse_dependencies(text: str) -> Dependencies:
    """`Print All Dependencies`, read for names and refusing a shape it cannot place.

    An entry is `name : type`, and the type is what the printer wraps: over several
    lines, indented or not, and the command marks no end. So an entry opens at an
    unindented line whose first token is a qualified identifier followed by whitespace
    and a colon, and every other line belongs to the type above it. That is safe in the
    one direction that matters, a printed type carrying no `ident :` in that position:
    a binder's colon follows the bound name inside the line, `forall x : nat`, where
    this reading wants the line's own first token.

    Three shapes refuse, because each would otherwise pass as a closure this saw all
    of: a silent query, a heading Rocq gained that this cannot place, and an entry or
    a continuation standing before any heading.
    """
    out = empty_dependencies()
    stripped = text.strip()
    if not stripped:
        raise ParseError("the dependency query printed nothing")
    if stripped == CLOSED:
        return out
    key: str | None = None
    for line in stripped.splitlines():
        body = line.rstrip()
        if not body.strip():
            continue
        if not body[:1].isspace():
            heading = _HEADING.match(body)
            if heading:
                if body not in SECTIONS:
                    raise ParseError(f"unplaceable dependency heading: {body}")
                key = SECTIONS[body]
                continue
            entry = _ENTRY.match(body)
            if entry:
                if key is None:
                    raise ParseError(f"a dependency entry precedes every heading: {body}")
                out[key].append(entry.group(1))
                continue
        if key is None:
            raise ParseError(f"dependency output precedes every heading: {body}")
    if not any(out.values()):
        raise ParseError("the dependency query printed headings and no entry")
    return out


def parse_about(text: str) -> About:
    """`About`, read for the three facts it states about a symbol.

    Opacity is `n/a` where the symbol carries none, an inductive type being the case
    this corpus supplies; a constant that states neither is a printer change and
    refuses here rather than defaulting to transparent.
    """
    universes: str | None = None
    opacity: str | None = None
    expands: tuple[str, str] | None = None
    for line in text.splitlines():
        trimmed = line.strip()
        sentence = next((answer for spelling, answer in UNIVERSE_SENTENCES
                         if trimmed.endswith(spelling)), None)
        if sentence is not None:
            universes = sentence
        elif trimmed.endswith(" is opaque"):
            opacity = "opaque"
        elif trimmed.endswith(" is transparent"):
            opacity = "transparent"
        else:
            found = _EXPANDS.match(trimmed)
            if found:
                expands = (str(found.group(1)), str(found.group(2)))
    if expands is None:
        raise ParseError("About named no expansion, so the symbol's kind is unknown")
    if universes is None:
        raise ParseError(f"About said nothing about {expands[1]}'s universes")
    kind = expands[0]
    if opacity is None and kind == "Constant":
        raise ParseError(f"About said nothing about constant {expands[1]}'s opacity")
    return About(kind=kind, expands_to=expands[1], universes=universes,
                 opacity=opacity or "n/a")


def dependent_matches(text: str) -> int:
    """Printed `match` heads carrying an `as` or an `in` clause.

    The scan starts after each `match` token and stops at the first `return` or `with`
    outside every bracket it has opened, which is where the head ends. The module
    docstring states the direction this errs in.
    """
    count = 0
    for hit in _MATCH.finditer(text):
        depth = 0
        index = hit.end()
        dependent = False
        while index < len(text):
            char = text[index]
            if char in "([{":
                depth += 1
                index += 1
                continue
            if char in ")]}":
                if depth == 0:
                    break
                depth -= 1
                index += 1
                continue
            word = _WORD.match(text, index)
            if word is None:
                index += 1
                continue
            token = word.group()
            if depth == 0:
                if token in ("return", "with"):
                    break
                if token in ("as", "in"):
                    dependent = True
            index = word.end()
        if dependent:
            count += 1
    return count


def term_features(declaration: str) -> list[str]:
    """Every term-level feature the printed declaration shows, as declared predicates."""
    found: list[str] = []
    fixes = len(_FIX.findall(declaration))
    cofixes = len(_COFIX.findall(declaration))
    if fixes:
        found.append("fix-binder")
    if cofixes:
        found.append("cofix-binder")
    if fixes + cofixes > 1:
        found.append("fix-binders-multiple")
    if (fixes or cofixes) and _FOR.search(declaration):
        found.append("fix-binder-mutual")
    if _MATCH.search(declaration):
        found.append("match")
    if dependent_matches(declaration):
        found.append("match-dependent-return")
    return found


def primitive_features(*texts: str) -> list[str]:
    """The primitive families named anywhere in the supplied texts."""
    joined = "\n".join(texts)
    return [name for name, spellings in PRIMITIVES.items()
            if any(spelling in joined for spelling in spellings)]


def source_declarations(text: str) -> dict[str, int]:
    """What one proof source spells, counted over sentences rather than over lines.

    A source reading, and it decides nothing about the compiled corpus: it is here so
    a profile decision can see the distance between what an author wrote and what the
    kernel reading above found a proof to use.

    It counts the vernacular a sentence opens with and nothing inside the sentence.
    Mutual recursion is deliberately absent from this reading and is left to the term
    reading's `for` selector: a `Fixpoint` block's own `with` and a `match`'s are the
    same token at this level, and a count that reads every `Fixpoint` as mutual is a
    figure with no predicate behind it.
    """
    counts = dict.fromkeys(SOURCE_VERNACULARS, 0)
    for sentence in sentences(text):
        for vernacular in SOURCE_VERNACULARS:
            if re.match(rf"^(?:#\[[^\]]*\]\s*)?(?:Local\s+|Global\s+)?{vernacular}\b",
                        sentence):
                counts[vernacular] += 1
    return counts


def classify(name: str, typ: str, about: About, dependencies: Dependencies,
             declaration: str | None) -> Constant:
    """One symbol's complete record, from the readings actually taken of it.

    `declaration` is None where the term reading was refused, which the module's
    bound on one query's output can do; the record then says so by carrying
    `term-reading-unavailable` rather than reporting the absence of a feature.
    """
    closure = [member for key in CLOSURE_KEYS for member in dependencies[key]]
    if declaration is None:
        features = ["term-reading-unavailable", *primitive_features(*closure)]
    else:
        features = [*term_features(declaration),
                    *primitive_features(declaration, *closure)]
    if about.universes != "monomorphic":
        features.append(f"universes-{about.universes}")
    if about.opacity == "opaque":
        features.append("opaque-body")
    if dependencies["axioms"]:
        features.append("axiom-dependency")
    if dependencies["variables"]:
        features.append("section-variable-dependency")
    if dependencies["transparent"]:
        features.append("transparent-constant-dependency")
    else:
        features.append("no-transparent-dependency")
    return Constant(name=name, type=typ, kind=about.kind, opacity=about.opacity,
                    universes=about.universes,
                    features=sorted(set(features)), dependencies=dependencies,
                    body_printed=bool(declaration and declaration.strip()))


def local_names(names: list[str], stems: set[str]) -> tuple[list[str], list[str]]:
    """A closure split into this corpus's own constants and everything else.

    `Print All Dependencies` prints the shortest unambiguous name, so a foreign member
    arrives as `andb` or `Nat.add` rather than under its library's full path. Ownership
    is therefore decided by the first component against the corpus's own module stems,
    which is exact in the direction that matters: a corpus constant is always printed
    under its module, that being the qualification this query is run without importing.
    """
    local = [name for name in names if name.split(".", 1)[0] in stems]
    return local, [name for name in names if name.split(".", 1)[0] not in stems]


def totals(constants: list[Constant]) -> dict[str, int]:
    """Every figure the report states about the corpus, each one a count of records."""
    counted: dict[str, int] = {"constants": len(constants)}
    for constant in constants:
        for feature in constant.features:
            counted[feature] = counted.get(feature, 0) + 1
        for label in (f"kind:{constant.kind}", f"opacity:{constant.opacity}",
                      f"universes:{constant.universes}"):
            counted[label] = counted.get(label, 0) + 1
    return dict(sorted(counted.items()))
