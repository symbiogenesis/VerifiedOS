# SPDX-License-Identifier: Apache-2.0
"""CIC feature and dependency parser for the proof corpus; see
[docs/assurance/cic-checker-qualification.md](../../docs/assurance/cic-checker-qualification.md#corpus-and-source-qualification).

Combines three Rocq query readings with a source-vernacular count:
- **Kernel dependencies (`Print All Dependencies`)**: partitions each global's transitive
  dependencies into `axioms`, `variables`, `opaque`, and `transparent`.
- **Declaration metadata (`About`)**: extracts symbol kind, opacity, and universe mode
  (`monomorphic`, `template`, or `polymorphic`).
- **Term features (`Print` under `Set Printing All`)**: conservative token predicates over
  notation-free printed declarations (`fix-binder`, `cofix-binder`, `fix-binders-multiple`,
  `fix-binder-mutual`, `match`, `match-dependent-return`, and `PRIMITIVES`).
- **Source vernaculars**: sentence-level counts of `SOURCE_VERNACULARS` and attribute
  modifiers in `.v` files (ignoring `Fail` and `Succeed`).
"""

import re
from dataclasses import dataclass, field

from vos.proofs import VOID, decorations, sentences

# Headings printed by `Print All Dependencies` mapped to `Dependencies` keys.
SECTIONS: dict[str, str] = {
    "Axioms:": "axioms",
    "Variables:": "variables",
    "Opaque constants:": "opaque",
    "Transparent constants:": "transparent",
}
CLOSED = "Closed under the global context"

# Delimiter prefix emitted before each query response block.
MARKER = "VOS_CIC_CORPUS|"

# Rocq display settings for notation-free, unwrapped `Print` queries.
QUERY_SETTINGS = """\
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
"""

QUALIFIED = re.compile(r"[\w'][\w']*(?:\.[\w'][\w']*)*")
# Headings have no space before `:`, whereas dependency entries have `ident :`.
_HEADING = re.compile(r"^([^\s:](?:[^:]*[^\s:])?):$")
_ENTRY = re.compile(r"^([\w'][\w']*(?:\.[\w'][\w']*)*)\s+:")
_EXPANDS = re.compile(r"^Expands to:\s+(\w+)\s+(\S+)")
_WORD = re.compile(r"[\w']+")
_FIX = re.compile(r"(?<![\w'])fix(?![\w'])")
_COFIX = re.compile(r"(?<![\w'])cofix(?![\w'])")
_FOR = re.compile(r"(?<![\w'])for\s+[\w']+")
_MATCH = re.compile(r"(?<![\w'])match(?![\w'])")

# Rocq standard-library module prefixes for the four primitive type families.
PRIMITIVES: dict[str, tuple[str, ...]] = {
    "primitive-int63": ("Uint63", "Int63", "PrimInt63"),
    "primitive-float64": ("PrimFloat", "Float64", "SpecFloat"),
    "primitive-array": ("PArray", "PrimArray"),
    "primitive-string": ("PString", "PrimString"),
}

# Vernaculars counted in the source-text reading.
SOURCE_VERNACULARS: tuple[str, ...] = (
    "Section", "End", "Module", "Fixpoint", "CoFixpoint", "Inductive", "CoInductive",
    "Record", "Variant", "Axiom", "Parameter", "Primitive", "Polymorphic",
    "Monomorphic", "Cumulative", "NonCumulative", "Equations", "Program",
)
_VERNACULAR = re.compile("(?:" + "|".join(SOURCE_VERNACULARS) + r")\b")

# Attribute patterns for extracting counted modifiers from [proofs.py](proofs.py) sentence decorations.
_QUOTED = re.compile(r'"[^"]*"')
_UNIVERSES = re.compile(r"\buniverses\s*\(([^()]*)\)")
_SETTING = re.compile(r"\b(program|polymorphic|cumulative)\b(?:\s*=\s*(yes|no)\b)?")


def _attribute_modifiers(attributes: str) -> list[str]:
    """Extract counted vernacular modifiers (`Program`, `Polymorphic`/`Monomorphic`, `Cumulative`/`NonCumulative`) from `#[...]` attributes."""
    bare = _QUOTED.sub('""', attributes)
    found = ["Program" for setting in _SETTING.finditer(_UNIVERSES.sub("", bare))
             if setting.group(1) == "program" and setting.group(2) != "no"]
    for universes in _UNIVERSES.finditer(bare):
        for setting in _SETTING.finditer(universes.group(1)):
            if setting.group(1) == "polymorphic":
                found.append("Monomorphic" if setting.group(2) == "no" else "Polymorphic")
            elif setting.group(1) == "cumulative":
                found.append("NonCumulative" if setting.group(2) == "no" else "Cumulative")
    return found


class ParseError(ValueError):
    """Raised when Rocq query output does not match the expected grammar."""


type Dependencies = dict[str, list[str]]

# Dependency categories holding global constants rather than section variables.
CLOSURE_KEYS: tuple[str, ...] = ("axioms", "opaque", "transparent")


def empty_dependencies() -> Dependencies:
    """Return an empty `Dependencies` dictionary with all `SECTIONS` keys initialized."""
    return {key: [] for key in SECTIONS.values()}


# Universe polymorphism suffixes reported by `About` (longest match first).
UNIVERSE_SENTENCES: tuple[tuple[str, str], ...] = (
    ("is not universe polymorphic", "monomorphic"),
    ("is template universe polymorphic", "template"),
    ("is universe polymorphic", "polymorphic"),
)


@dataclass(frozen=True)
class About:
    """Symbol kind, expansion, universe mode, and opacity parsed from `About`."""

    kind: str
    expands_to: str
    universes: str
    opacity: str

    @property
    def universe_polymorphic(self) -> bool:
        """Return whether universes are `polymorphic` or `template` rather than `monomorphic`."""
        return self.universes != "monomorphic"


@dataclass
class Constant:
    """Classified CIC symbol record combining `About`, dependency closure, and term features."""

    name: str
    type: str = ""
    kind: str = ""
    opacity: str = "n/a"
    universes: str = "monomorphic"
    features: list[str] = field(default_factory=list)
    dependencies: Dependencies = field(default_factory=empty_dependencies)
    body_printed: bool = False


def blocks(stdout: str, keys: list[str]) -> dict[str, str]:
    """Split `MARKER`-delimited query output into blocks keyed by `keys`, rejecting missing or extra keys."""
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
    """Parse `Print All Dependencies` output into `Dependencies`, failing closed on unknown headings or unframed lines."""
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
    """Parse `About` output for symbol kind, expansion, universe mode, and opacity."""
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
    """Count printed `match` heads that carry a top-level `as` or `in` clause before `return` or `with`."""
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
    """Return term-level feature tags observed in a printed `declaration`."""
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
    """Return primitive family tags whose module prefixes appear in `texts`."""
    joined = "\n".join(texts)
    return [name for name, spellings in PRIMITIVES.items()
            if any(spelling in joined for spelling in spellings)]


def source_declarations(text: str) -> dict[str, int]:
    """Count `SOURCE_VERNACULARS` and attribute modifiers across non-`Fail`/`Succeed` sentences in `text`."""
    counts = dict.fromkeys(SOURCE_VERNACULARS, 0)
    for sentence in sentences(text):
        found, at = decorations(sentence)
        spelled: list[str] = []
        void = False
        for decoration in found:
            if decoration.group("attributes") is not None:
                spelled += _attribute_modifiers(decoration.group("attributes"))
            elif decoration.group("word") in counts:
                spelled.append(decoration.group("word"))
            void = void or decoration.group("word") in VOID
        head = _VERNACULAR.match(sentence, at)
        if head is not None:
            spelled.append(head.group())
        if not void:
            for counted in spelled:
                counts[counted] += 1
    return counts


def classify(name: str, typ: str, about: About, dependencies: Dependencies,
             declaration: str | None) -> Constant:
    """Build a `Constant` record from `about`, `dependencies`, and optional printed `declaration`."""
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
    """Partition `names` into corpus-local symbols (first component in `stems`) and external symbols."""
    local = [name for name in names if name.split(".", 1)[0] in stems]
    return local, [name for name in names if name.split(".", 1)[0] not in stems]


def totals(constants: list[Constant]) -> dict[str, int]:
    """Aggregate feature, kind, opacity, and universe counts across `constants`."""
    counted: dict[str, int] = {"constants": len(constants)}
    for constant in constants:
        for feature in constant.features:
            counted[feature] = counted.get(feature, 0) + 1
        for label in (f"kind:{constant.kind}", f"opacity:{constant.opacity}",
                      f"universes:{constant.universes}"):
            counted[label] = counted.get(label, 0) + 1
    return dict(sorted(counted.items()))
