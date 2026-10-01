# SPDX-License-Identifier: Apache-2.0
"""instruments: what a Rocq older than 9.3.0 compiles, against the syntax 9.3 adds.

Rocq 9.3.0 reads four forms no earlier release parses: `if … is` (rocq#21609), a record
value completed from a base with `with` (rocq#22207), and the `&` and `of` binders
(rocq#21611). The proof gate compiles at 9.3.0, so it accepts each of them, and the
gate is not the only compiler of these sources. The QuickChick harness and its seeded
mutants, the CertiRocq Wasm oracle and the Rupicola lowering each compile a proof source
or a harness with an older release, held there by the libraries they load. **A form
the gate accepts breaks those instruments without any gate saying so**: no hosted lane
runs them, and the first reader to learn of it is whoever runs one next. This rule is
what says so, on every checker run.

**The set is derived and never listed.** `INSTRUMENTS` below is the one table of every
instrument that compiles a proof source or a harness outside the gate: its switch, its
Rocq release, the harnesses it compiles, whether it also compiles the rig's support
harnesses or a directory of its own, whether it compiles every proof source, as
`seed coq`'s enumerative mode does for the `--file` its caller names and as
`gallina.emit` does for the vector harnesses, and the proof sources it names itself, as
the Rupicola lowering names its default owner. `seed coq --quickchick` compiles its
harness's closure alone and refuses a subject outside it, so its row holds that harness
and the rig's support harnesses, each with its closure, which today lie inside the
harness's. Each switch and release is the instrument's own constant,
imported, or, where it has none to import, the literal in its own file or the rig's
constant that file binds under a name of its own, read by name out of that file's syntax
tree, and so is a proof source the instrument names. The rows older than 9.3.0 decide
the set, and each harness or named source brings its `Require` closure, read by
[vos/proofs.py](../proofs.py)'s own reader over the proofs directory and the harness's
directory as one namespace, because that is how every row stages them: the rig roots
both at the empty logical path, and the recipes copy the proof beside the harness. The
dated campaigns under `proofs/campaigns/` are not rows. A row that states no release is
held older than 9.3.0, since a release nobody states is one nobody can say admits the
forms.

**The table's own membership is held too.** Every module under `tools/vos/` that resolves
a prover through `gallina.prover` has to be some row's `selects`, so an instrument added
to the rig is inside the rule the day it chooses a switch. And the switches its calls can
ask for have to be the switches its rows state, so a row cannot keep a release its module
has moved away from. A call's argument is read out of the module's syntax tree: a literal,
or every `_SWITCH` constant of the rig or of `vos.env` it names, following each local name
back through the statements that bind it; an argument that reaches none is a finding. The
instruments outside the rig are rows by name and have no such check, and the compilers
that resolve the gate's own prover through `env.rocq_command` are outside the table by
construction: they compile at the gate's release.

**The reading is lexical, over the shared lexer's text.** `proofs.strip_comments` blanks
the comments and each string literal is blanked here, so neither can trigger a form.
`is` is refused where an `if` of its sentence has not yet met its `then`; `with` where
it is the first of `:=`, `with` and `|}` at a `{|`'s own depth; a lone `&` unless it is
a separator an older Rocq reads, a sigma type's directly inside a plain brace holding a
term or `exists2`'s after its binders, and even then where a `forall`, `fun`, `exists`,
`exists2`, `let`, `fix` or `cofix` binder list is open at its depth; and any `of`, which
9.3 reserves as a keyword, so a name spelled `of` is refused with the binder. So
`{x : A & P}` and `exists2 x, P & Q` pass, and a field's binder written directly inside
a record's, a class's or an instance's braces is refused, as are the intro pattern
`(p & q)` and a notation token such as `&=`, which the reading cannot tell from the
binder. What the reading cannot see is stated rather than left to be met: a form a
notation or a loaded library supplies, text a source reaches otherwise than by a
`Require` it spells, a subject a caller names beyond a row's defaults, and an instrument
that compiles Gallina outside the table, or reaches the rig's prover otherwise than by
calling `gallina.prover` under some name.

Fail-closed at every reading. An empty table, a switch or release that cannot be read or
is not a release, a harness or named source the index does not carry, a named path that
leaves the checkout, a directory of harnesses holding none, a row older than 9.3.0 that
derives no file, a stem one namespace holds twice, a `Require` cycle, a prover call whose
argument names no switch and a file that cannot be read are each a finding, so the rule
owes the floors group no member.
"""

import ast
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vos import env, gallina, proofs

# `Context` lives in this package's __init__, which imports this module in turn.
if TYPE_CHECKING:
    from . import Context

HEADING = ("=== instruments: what an older Rocq compiles, against the syntax Rocq 9.3 "
           "adds ===")

# The release the four forms arrive in. A fact about the language rather than the proof
# switch's pin, so it is not read from `env.ROCQ_VERSION`: a row at 9.3.0 reads every
# form whatever release the gate moves to.
SINCE = (9, 3, 0)

PROOFS = gallina.PROOFS
SUFFIX = ".v"
RIG = gallina.HARNESS_DIR


@dataclass(frozen=True)
class Literal:
    """A value an instrument states only in its own file: the value assigned to the
    module-level `name`, or, where `name` opens with `--`, the default of that
    command-line option. `within` is a pattern whose first group is the value where the
    string carries it inside a longer one.

    The value is a string literal, a string constant of the rig or of `vos.env` that the
    file imports and names, or a path built from `Path(__file__)` by `.resolve()`,
    `.parent` and `/`, read as the checkout-relative path it names, through `str(...)`
    and the module's own names."""

    path: str
    name: str
    within: str = ""


@dataclass(frozen=True)
class Instrument:
    """One instrument that compiles a proof source or a harness outside the gate.

    `selects` is the module that chooses its switch. `release` is None where the
    instrument states none. `harnesses` are the files it runs, `support` whether it
    also compiles the rig's non-entry harnesses as `gallina.compile_support` does,
    `beside` a directory whose every tracked Gallina file it compiles, `whole`
    whether it compiles every proof source, and `subjects` the proof sources it names
    itself and compiles, each with its `Require` closure.
    """

    name: str
    selects: str
    switch: str | Literal
    release: str | Literal | None
    harnesses: tuple[str, ...] = ()
    support: bool = False
    beside: str = ""
    whole: bool = False
    subjects: tuple[str | Literal, ...] = ()


_REGENERATE = "tools/bedrock2-lowering/regenerate.py"
_COMPARE = "tools/wasm-oracle/compare_component.py"

INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("quickchick vectors", "tools/vos/gallina.py", gallina.VECTOR_SWITCH,
               gallina.VECTOR_ROCQ_VERSION, (f"{RIG}/{gallina.ENUMERATIVE}",),
               support=True, whole=True),
    Instrument("quickchick freeze", "tools/vos/gallina.py", gallina.VECTOR_SWITCH,
               gallina.VECTOR_ROCQ_VERSION, (f"{RIG}/{gallina.FREEZE}",),
               support=True, whole=True),
    Instrument("kernel vectors, check and mutants", "tools/vos/cli/kernel.py",
               gallina.VECTOR_SWITCH, gallina.VECTOR_ROCQ_VERSION,
               (f"{RIG}/{gallina.KERNEL}",)),
    Instrument("seed coq", "tools/vos/cli/seed.py", gallina.VECTOR_SWITCH,
               gallina.VECTOR_ROCQ_VERSION, (f"{RIG}/{gallina.ENUMERATIVE}",),
               support=True, whole=True),
    Instrument("quickchick properties", "tools/vos/cli/quickchick.py",
               gallina.QUICKCHICK_SWITCH, gallina.QUICKCHICK_ROCQ_VERSION,
               (f"{RIG}/{gallina.RANDOMIZED}",)),
    # The same run where QuickChick is installed in the CertiRocq switch instead.
    Instrument("quickchick properties in the oracle's switch", "tools/vos/cli/quickchick.py",
               gallina.ORACLE_SWITCH, gallina.ORACLE_ROCQ_VERSION,
               (f"{RIG}/{gallina.RANDOMIZED}",)),
    # Properties.v's closure alone, a subject outside it refused, beside the rig's support.
    Instrument("seed coq --quickchick", "tools/vos/cli/seed.py", gallina.QUICKCHICK_SWITCH,
               gallina.QUICKCHICK_ROCQ_VERSION, (f"{RIG}/{gallina.RANDOMIZED}",),
               support=True),
    # Each writes its harness at run time, over proofs its own module names; at the
    # gate's release they add nothing, and older they would derive no file and fail.
    Instrument("the copy-service comparison", "tools/vos/copy_service.py",
               env.ROCQ_SWITCH, env.ROCQ_VERSION),
    Instrument("the supervisor comparison", "tools/vos/supervisor.py",
               env.ROCQ_SWITCH, env.ROCQ_VERSION),
    # The recipes compile in the switch they import from tools/opam/certirocq.lock, the
    # one ORACLE_SWITCH names: K-118 holds the rig's Rocq and OCaml releases to that
    # snapshot and `run.py provision` its CertiRocq to the rig's pin, and the Docker
    # image's own Rocq 9.1 only bootstraps opam. The row reads the rig's constants by
    # decision, the recipes importing none.
    Instrument("the Wasm oracle's recipes", "tools/wasm-oracle/README.md",
               gallina.ORACLE_SWITCH, gallina.ORACLE_ROCQ_VERSION,
               beside="tools/wasm-oracle"),
    # Its default switch and the release its prover must report are the rig's, bound
    # under its own names and read through them.
    Instrument("compare_component.py", _COMPARE, Literal(_COMPARE, "--switch"),
               Literal(_COMPARE, "ROCQ_VERSION"), beside="tools/wasm-oracle"),
    # The lowering compiles its `--owner` before the source; a caller may name another.
    Instrument("the Rupicola lowering", _REGENERATE, Literal(_REGENERATE, "SWITCH"),
               Literal(_REGENERATE, "SWITCH", r"-rupicola-(\d+\.\d+\.\d+)-ocaml-"),
               beside="tools/bedrock2-lowering",
               subjects=(Literal(_REGENERATE, "--owner"),)),
)

_RELEASE_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# A string literal as Rocq's lexer reads one: a doubled quote inside it is a quote, and
# one left open runs to the end of the text.
_STRING_RE = re.compile(r'"(?:[^"]|"")*"?')

# The tokens the forms are located by, in one pass and without a leading lookbehind,
# which the engine would re-decide at every position of every source: a prime beside a
# word is checked on the hits, and a run of more than one ampersand is `&&` or longer.
_CANDIDATE_RE = re.compile(r"\b(?:is|of)\b|&+|\{\|")

# The brackets and keywords a hit's context is read through, only ever over a hit's own
# sentence, so the lookbehind that keeps a primed name out costs nothing per source.
_WORD = r"(?<![\w']){}(?![\w'])"
_IF_THEN_RE = re.compile(_WORD.format("(?:if|then)"))
_BRACKET_RE = re.compile(r"\{\||\|\}|[()\[\]{}]")
_RECORD_SCAN_RE = re.compile(r"\{\||\|\}|[()\[\]{}]|:=|" + _WORD.format("with"))
_OPENERS = {"(": ")", "[": "]", "{": "}", "{|": "|}"}
# What may stand before a focusing brace at a sentence's opening: bullets, a goal
# selector, and the braces already read past.
_LEAD_RE = re.compile(r"[\s\-+*{}]*(?:(?:\d+|all)\s*:)?[\s{}]*")
# The declarations whose plain braces after `:=` hold fields rather than a term, behind
# any attribute or modifier, and what stands before such a brace: the `:=` or a
# constructor's name after it.
_FIELDS_RE = re.compile(r"(?:#\[[^\]]*\]\s*|(?:Local|Global|Polymorphic|Monomorphic|"
                        r"Cumulative|NonCumulative|Private|Program)\s+)*"
                        r"(?:Record|Structure|Class|Inductive|CoInductive|Variant|"
                        r"Instance)(?![\w'])")
_FIELD_LIST_RE = re.compile(r"(?::=|\|)\s*(?:[^\W\d][\w']*\s*)?\Z")
# What a lone `&` is read through: the brackets, the keywords opening a binder list and
# the tokens closing one at its own depth, and each `&` before it.
_SCOPE_RE = re.compile(r"\{\||\|\}|[()\[\]{}]|,|=>|:=|(?<!&)&(?!&)|"
                       + _WORD.format("(?:forall|fun|exists2?|let|fix|cofix)"))

# The rig's prover lookup, the modules whose `_SWITCH` constants a call's argument is read
# back to, and where the scan for its callers runs.
_PROVER = "prover"
_MODULES = {"gallina": gallina, "env": env}
_SWITCH_SUFFIX = "_SWITCH"
_SCANNED = "tools/vos/"
_RIG_FILE = f"{_SCANNED}gallina.py"

FORM_IF = "`if … is`"
FORM_WITH = "a record value completed with `with`"
FORM_AMP = "an `&` binder"
FORM_OF = "an `of` binder"


def code(text: str) -> str:
    """A source with its comments and string literals blanked, line breaks kept, so a
    form a comment or a string spells is not read and every offset stays a line's."""
    stripped = proofs.strip_comments(text)
    pieces: list[str] = []
    at = 0
    for quoted in _STRING_RE.finditer(stripped):
        pieces.append(stripped[at:quoted.start()])
        pieces.append("".join("\n" if c == "\n" else " " for c in quoted.group()))
        at = quoted.end()
    pieces.append(stripped[at:])
    return "".join(pieces)


def forms(text: str) -> list[tuple[int, str]]:
    """Every refused form a source writes, as its line and its name, in source order.

    Each form is located by its own lexeme first, in one scan in the regex engine, and
    only a hit pays for the sentence and bracket reading that decides it, so a source
    writing none of the four tokens costs that scan and nothing more."""
    body = code(text)
    found: list[tuple[int, str]] = []
    for hit in _CANDIDATE_RE.finditer(body):
        if not _whole(body, hit):
            continue
        lexeme, start = hit.group(), hit.start()
        opens, closes = _sentence(body, start)
        if lexeme == "is":
            pending = 0
            for word in _IF_THEN_RE.finditer(body, opens, start):
                pending = pending + 1 if word.group() == "if" else max(0, pending - 1)
            if pending:
                found.append((start, FORM_IF))
        elif lexeme == "of":
            found.append((start, FORM_OF))
        elif lexeme == "&":
            if not _separates(body, opens, start):
                found.append((start, FORM_AMP))
        elif _completed(body, hit.end(), closes):
            found.append((start, FORM_WITH))
    return [(body.count("\n", 0, at) + 1, form) for at, form in sorted(found)]


def _sentence(body: str, at: int) -> tuple[int, int]:
    """Where the sentence holding an offset opens and where it ends, by the shared
    lexer's own full stop: one followed by whitespace or the end of the text, and not
    the second of exactly two, which Rocq reads as the token `..`."""
    opens = at
    while (dot := body.rfind(".", 0, opens)) >= 0:
        if proofs.SENTENCE_END.match(body, dot):
            break
        opens = dot
    closes = proofs.SENTENCE_END.search(body, at)
    return dot + 1, closes.end() if closes else len(body)


def _whole(body: str, hit: re.Match[str]) -> bool:
    """Whether a candidate is the lexeme it spells: a word not continued by a prime,
    which `\\b` does not count as part of a name and Rocq does, or a lone `&`."""
    lexeme = hit.group()
    if lexeme in ("is", "of"):
        return (body[hit.start() - 1:hit.start()] != "'"
                and body[hit.end():hit.end() + 1] != "'")
    return len(lexeme) == 1 if lexeme.startswith("&") else True


def _separates(body: str, start: int, at: int) -> bool:
    """Whether the lone `&` at `at` is a separator an older Rocq reads: a sigma type's,
    directly inside a plain brace holding a term, or `exists2`'s, after its binders.

    Either way no binder list may be open at its depth, since 9.3 reads an `&` there as
    a binder: after `forall`, `fun`, `exists`, `exists2`, `let`, `fix` or `cofix` and
    before the `,`, `=>` or `:=` closing their binders. An `&` a field list holds
    directly, a record's, a class's or an instance's, is a field's binder and never a
    sigma type's."""
    bracket, inside, fields = _context(body, start, at)
    depth, keyword, pending = 0, "", 0
    for mark in _SCOPE_RE.finditer(body, inside, at):
        lexeme = mark.group()
        if lexeme in _OPENERS:
            depth += 1
        elif lexeme in _OPENERS.values():
            depth = max(0, depth - 1)
        elif depth:
            continue
        elif lexeme in (",", "=>", ":="):
            pending += keyword == "exists2" and lexeme == ","
            keyword = ""
        elif lexeme == "&":
            pending = max(0, pending - 1)
        else:
            keyword = lexeme
    if keyword:
        return False
    return (bracket == "{" and not fields) or pending > 0


def _context(body: str, start: int, end: int) -> tuple[str, int, bool]:
    """The bracket innermost around an offset within its sentence, "" where none is,
    where its contents open, and whether it is a field list: a plain brace at the
    sentence's own depth, after its `:=` and any constructor name, in a declaration
    that takes fields.

    A brace opening the sentence, after any bullet or goal selector, is a focusing brace
    around a proof step and not a bracket around its text, so a leading run of them is
    read past."""
    stack: list[tuple[str, int, bool]] = []
    leading = True
    declares = False
    for mark in _BRACKET_RE.finditer(body, start, end):
        lexeme = mark.group()
        if leading and lexeme in ("{", "}") and _LEAD_RE.fullmatch(body, start, mark.start()):
            start = mark.end()
            continue
        if leading:
            lead = _LEAD_RE.match(body, start)
            declares = bool(_FIELDS_RE.match(body, lead.end() if lead else start))
        leading = False
        if lexeme in _OPENERS:
            listed = (declares and lexeme == "{" and not stack
                      and _FIELD_LIST_RE.search(body[start:mark.start()]) is not None)
            stack.append((lexeme, mark.end(), listed))
        elif stack:
            stack.pop()
    return stack[-1] if stack else ("", start, False)


def _completed(body: str, start: int, end: int) -> bool:
    """Whether the `{|` ending at `start` is completed from a base: a `with` at its own
    depth before its first `:=` and before its `|}`, within its sentence."""
    depth = 0
    for mark in _RECORD_SCAN_RE.finditer(body, start, end):
        lexeme = mark.group()
        if lexeme in _OPENERS:
            depth += 1
        elif lexeme in _OPENERS.values():
            if not depth:
                return False
            depth -= 1
        elif not depth:
            return lexeme == "with"
    return False


def release_of(text: str) -> tuple[int, int, int] | None:
    """A release as the three numbers it compares by, or None where it is not one."""
    m = _RELEASE_RE.fullmatch(text)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def literal(root: Path, spec: Literal) -> tuple[str | None, str]:
    """The value one instrument's own file states, or why it could not be read."""
    path = root / spec.path
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=spec.path)
    except (OSError, UnicodeDecodeError, SyntaxError) as err:
        return None, f"{spec.path} cannot be read as Python, so its {spec.name} is unread ({err})"
    option = spec.name.startswith("--")
    if option:
        stated = [k.value for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and node.args
                  and isinstance(node.args[0], ast.Constant)
                  and node.args[0].value == spec.name
                  for k in node.keywords if k.arg == "default"]
    else:
        stated = _assigned(tree, spec.name)
    values = [value if isinstance(value, str) else "/".join(value) for expr in stated
              if (value := _evaluate(tree, expr, spec.path)) is not None]
    if len(values) != 1:
        what = (f"string default of its {spec.name} option" if option
                else f"module-level string {spec.name}")
        return None, (f"{spec.path} states {len(values)} {what} where the instrument "
                      "table reads exactly one")
    if not spec.within:
        return values[0], ""
    inner = re.search(spec.within, values[0])
    if inner is None:
        return None, (f"{spec.path}'s {spec.name} is {values[0]!r}, which carries no value "
                      f"the pattern {spec.within!r} reads")
    return str(inner.group(1)), ""


def _assigned(tree: ast.Module, name: str) -> list[ast.expr]:
    """Every value a module's own top level assigns to one name."""
    out: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                out.append(node.value)
    return out


def _evaluate(tree: ast.Module, expr: ast.expr, here: str,
              depth: int = 0) -> str | tuple[str, ...] | None:
    """A value one instrument states, as a string, or as the parts of a path under the
    checkout while it is still being built; None for anything else, a path leaving the
    checkout or a name bound other than once among them. A constant of the rig or of
    `vos.env` that the file names through its own import is the value that constant
    holds, the instrument stating it by taking it."""
    if depth > 16:
        return None
    step = depth + 1
    if isinstance(expr, ast.Constant):
        return expr.value if isinstance(expr.value, str) else None
    if isinstance(expr, ast.Name):
        bound = _assigned(tree, expr.id)
        return _evaluate(tree, bound[0], here, step) if len(bound) == 1 else None
    if (isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name)
            and (module := _modules(tree).get(expr.value.id)) is not None):
        value = getattr(module, expr.attr, None)
        return value if isinstance(value, str) else None
    if isinstance(expr, ast.Attribute) and expr.attr == "parent":
        inner = _evaluate(tree, expr.value, here, step)
        return inner[:-1] if isinstance(inner, tuple) and inner else None
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        left, right = (_evaluate(tree, side, here, step) for side in (expr.left, expr.right))
        parts = tuple(right.split("/")) if isinstance(right, str) else ()
        if isinstance(left, tuple) and parts and not {"", ".", ".."} & set(parts):
            return left + parts
        return None
    if not isinstance(expr, ast.Call) or expr.keywords:
        return None
    func, args = expr.func, expr.args
    if isinstance(func, ast.Name) and len(args) == 1:
        if func.id == "Path" and isinstance(args[0], ast.Name) and args[0].id == "__file__":
            return tuple(here.split("/"))
        if func.id == "str":
            inner = _evaluate(tree, args[0], here, step)
            return "/".join(inner) if isinstance(inner, tuple) else inner
    if isinstance(func, ast.Attribute) and func.attr == "resolve" and not args:
        inner = _evaluate(tree, func.value, here, step)
        return inner if isinstance(inner, tuple) else None
    return None


def _entry(root: Path, value: str | Literal | None) -> tuple[str | None, str]:
    if value is None or isinstance(value, str):
        return value, ""
    return literal(root, value)


def decide(root: Path, index: Iterable[str],
           rows: Sequence[Instrument]) -> tuple[list[str], str]:
    """The rule over one tree and one table: its findings and its clean line."""
    reached, labels, findings = reach(root, index, rows)
    decided = 0
    for rel in sorted(reached):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            findings.append(f"{rel} cannot be read, so the forms it writes are undecided "
                            f"({err})")
            continue
        decided += 1
        compiled = "; ".join(dict.fromkeys(reached[rel]))
        findings += [f"{rel}:{line} writes {form}, which only Rocq 9.3.0 and later parse, "
                     f"and is compiled by {compiled}" for line, form in forms(text)]

    names = ", ".join(labels) or "none"
    ok = (f"no {FORM_IF}, record value completed with `with`, `&` or `of` binder in the "
          f"{decided} file(s) compiled by the {len(labels)} of the table's {len(rows)} "
          f"instruments older than Rocq 9.3.0, each switch and release read from the "
          f"constant or literal stating it and each rig module held to the switches its "
          f"calls ask for: {names}")
    return findings, ok


def reach(root: Path, index: Iterable[str],
          rows: Sequence[Instrument]) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """What the table's rows older than Rocq 9.3.0 compile in one tree: each file with
    the label of every such row compiling it, those rows' labels in table order, and the
    findings of the reading. The forms each file writes are `decide`'s to read."""
    tracked = set(index)
    findings: list[str] = []
    if not rows:
        findings.append("the instrument table is empty, so nothing an older Rocq compiles "
                        "is decided about")

    older: list[tuple[Instrument, str, str]] = []
    switches: dict[str, set[str] | None] = {row.selects: set() for row in rows}
    for row in rows:
        switch, why = _entry(root, row.switch)
        if switch is None or not switch.strip():
            findings.append(why or f"the row for {row.name} names no switch")
            switches[row.selects] = None
            continue
        if (chosen := switches[row.selects]) is not None:
            chosen.add(switch)
        stated, why = _entry(root, row.release)
        if why:
            findings.append(why)
            continue
        if stated is None:
            older.append((row, switch, "no stated release"))
            continue
        number = release_of(stated)
        if number is None:
            findings.append(f"the row for {row.name} reads the release {stated!r}, which is "
                            "not a release")
        elif number < SINCE:
            older.append((row, switch, f"Rocq {stated}"))
    findings += _selections(root, tracked, switches)

    proof_sources = sorted(rel for rel in tracked if rel.startswith(f"{PROOFS}/")
                           and rel.endswith(SUFFIX) and rel.count("/") == 1)
    namespaces: set[str] = set()
    starts: list[tuple[Instrument, str, set[str]]] = []
    for row, switch, release in older:
        files, own = _starts(root, row, tracked, findings)
        if row.whole:
            if not proof_sources:
                findings.append(f"{row.name} compiles every proof source and the index "
                                f"carries none under {PROOFS}/")
            files |= set(proof_sources)
        if not files:
            findings.append(f"{row.name} compiles with {release}, older than Rocq 9.3.0, "
                            "and the table derives no file it compiles")
        namespaces |= own
        starts.append((row, f"{row.name} ({release}, {switch})", files))

    closures = _closures(root, tracked, proof_sources, namespaces, findings)
    reached: dict[str, list[str]] = {}
    for _, label, files in starts:
        for rel in sorted(files):
            directory = rel.rsplit("/", 1)[0]
            for member in sorted(closures.get(directory, {}).get(rel, {rel})):
                reached.setdefault(member, []).append(label)
    return reached, [label for _, label, _ in starts], findings


def _starts(root: Path, row: Instrument, tracked: set[str],
            findings: list[str]) -> tuple[set[str], set[str]]:
    """The harness files one row compiles, and the directories they sit in."""
    files: set[str] = set()
    for rel in row.harnesses:
        if rel in tracked:
            files.add(rel)
        else:
            findings.append(f"{row.name} runs {rel}, which the git index does not carry")
    for spec in row.subjects:
        rel, why = _entry(root, spec)
        if rel is None:
            findings.append(why)
        elif rel in tracked:
            files.add(rel)
        else:
            findings.append(f"{row.name} compiles {rel!r}, which the git index does not "
                            "carry")
    if row.support:
        files |= {rel for rel in _gallina_in(tracked, RIG)
                  if rel.rsplit("/", 1)[1] not in gallina.ENTRY_POINTS}
    if row.beside:
        found = _gallina_in(tracked, row.beside)
        if not found:
            findings.append(f"{row.name} compiles the Gallina files in {row.beside}/, and "
                            "the git index carries none there")
        files |= found
    return files, {rel.rsplit("/", 1)[0] for rel in files}


def _gallina_in(tracked: set[str], directory: str) -> set[str]:
    return {rel for rel in tracked if rel.startswith(f"{directory}/")
            and rel.endswith(SUFFIX) and "/" not in rel[len(directory) + 1:]}


def _closures(root: Path, tracked: set[str], proof_sources: list[str],
              namespaces: set[str],
              findings: list[str]) -> dict[str, dict[str, set[str]]]:
    """Each harness directory's `Require` closures, read over the proofs and that
    directory as one namespace, keyed by directory and then by file; the proofs' own,
    for a proof source a row names, over the proofs alone.

    One snapshot of every namespace is read where no stem is held twice across them,
    which is the common case and reads each proof once; otherwise each namespace is read
    apart, so a stem two directories share is resolved as each instrument resolves it.
    """
    members = {directory: sorted(_gallina_in(tracked, directory) | set(proof_sources))
               for directory in namespaces}
    if not members:
        return {}
    for rels in members.values():
        stems: dict[str, str] = {}
        for rel in rels:
            stem = Path(rel).stem
            if stem in stems:
                findings.append(f"{stems[stem]} and {rel} share the stem {stem}, which one "
                                f"namespace resolves a Require of against both")
            stems[stem] = rel
    union = sorted(set().union(*members.values()))
    together = len({Path(rel).stem for rel in union}) == len(union)
    snapshots = dict.fromkeys(members, union) if together else members
    indexes: dict[tuple[str, ...], proofs.SourceIndex | None] = {}
    out: dict[str, dict[str, set[str]]] = {}
    for directory, rels in members.items():
        key = tuple(snapshots[directory])
        if key not in indexes:
            indexes[key] = _index(root, list(key), findings)
        index = indexes[key]
        if index is None:
            continue
        inside = {root / rel for rel in rels}
        closures: dict[str, set[str]] = {}
        for rel in rels:
            if not rel.startswith(f"{directory}/"):
                continue
            seen = {root / rel}
            todo = [root / rel]
            while todo:
                for need in index.needs.get(todo.pop(), frozenset()):
                    if need in inside and need not in seen:
                        seen.add(need)
                        todo.append(need)
            closures[rel] = {path.relative_to(root).as_posix() for path in seen}
        out[directory] = closures
    return out


def _index(root: Path, rels: list[str],
           findings: list[str]) -> proofs.SourceIndex | None:
    """One snapshot through the shared reader, or None with the reason it could not be
    read: a cycle is the reader's own refusal and an unreadable file is this rule's."""
    try:
        return proofs.SourceIndex.read([root / rel for rel in rels])
    except SystemExit as refusal:
        findings.append(f"the Require graph over {len(rels)} files cannot be ordered: "
                        f"{refusal}")
    except (OSError, UnicodeDecodeError) as err:
        findings.append(f"a Gallina file in the Require graph cannot be read ({err})")
    return None


def _selections(root: Path, tracked: set[str],
                switches: dict[str, set[str] | None]) -> list[str]:
    """Every module under tools/vos/ that resolves a prover through the rig, held to the
    rows naming it as their `selects`, whose switches are `switches[module]`, or None
    where one of them could not be read.

    A module no row names chose a switch the table does not know; one whose calls can
    ask for other switches than its rows state has moved away from them; and a row naming
    a module that asks for none states a choice nothing makes."""
    found: list[str] = []
    for rel in sorted(tracked):
        if (not rel.startswith(_SCANNED) or not rel.endswith(".py")
                or rel.startswith(f"{_SCANNED}checks/")):
            continue
        # Only a module spelling both the rig and its lookup can call it, so no other is
        # parsed; the rig itself spells its own name in its prose.
        try:
            text = (root / rel).read_text(encoding="utf-8")
            spelled = _PROVER in text and "gallina" in text
            tree = ast.parse(text, filename=rel) if spelled else None
        except (OSError, UnicodeDecodeError, SyntaxError) as err:
            found.append(f"{rel} cannot be read, so whether it resolves a prover through "
                         f"gallina.prover is undecided ({err})")
            continue
        asks, unread = _asks(tree, rel == _RIG_FILE) if tree else (None, [])
        stated = switches.get(rel, set())
        if asks is None:
            if stated:
                found.append(f"the table names {rel} as choosing {sorted(stated)}, and it "
                             "resolves no prover through gallina.prover")
        elif rel not in switches:
            found.append(f"{rel} resolves a prover through gallina.prover and no row of "
                         "the instrument table names it, so what it compiles and at which "
                         "release is undecided")
        elif unread:
            found += [f"{rel}:{line} passes gallina.prover an argument that names no "
                      "switch constant, so which switch it asks for is undecided"
                      for line in unread]
        elif stated is not None and asks != stated:
            found.append(f"{rel} can ask gallina.prover for {sorted(asks)} and the rows "
                         f"naming it state {sorted(stated)}, so what it compiles at which "
                         "release is undecided")
    return found


def _asks(tree: ast.Module, own: bool) -> tuple[set[str] | None, list[int]]:
    """The switches one module's calls of `gallina.prover` can ask for, None where it
    makes none, and the lines of the calls whose argument names no switch.

    A call is `gallina.prover` under whatever name the module binds the rig or the
    function to, or a bare `prover` in the rig itself. Its argument is a literal, or the
    `_SWITCH` constants of the rig and of `vos.env` it names, each local name followed
    back through the statements binding it in the call's function, then the module's."""
    modules: dict[str, object] = {}
    callees = {_PROVER} if own else set()
    candidates: list[ast.Call] = []
    for node in ast.walk(tree):
        modules |= _imported(node)
        if isinstance(node, ast.ImportFrom):
            source = node.module or ""
            if source == "vos.gallina" or (node.level and source == "gallina"):
                callees |= {a.asname or a.name for a in node.names if a.name == _PROVER}
        elif isinstance(node, ast.Call):
            candidates.append(node)
    calls = [node for node in candidates if _calls_prover(node.func, callees, modules)]
    if not calls:
        return None, []
    bare = gallina if own else None

    # Each node's innermost function, or the module, and the names each of those binds,
    # in one pass over the tree: a function's own statement lives in the scope around it.
    scopes: dict[ast.AST, ast.AST] = {}
    bindings: dict[ast.AST, dict[str, list[ast.expr]]] = {}
    stack: list[tuple[ast.AST, ast.AST]] = [(tree, tree)]
    while stack:
        node, scope = stack.pop()
        inner = node if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) else scope
        for child in ast.iter_child_nodes(node):
            scopes[child] = inner
            for name, value in _binds(child):
                bindings.setdefault(inner, {}).setdefault(name, []).append(value)
            stack.append((child, inner))

    def named(expr: ast.expr, scope: ast.AST, seen: set[str]) -> set[str]:
        out: set[str] = set()
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                out |= _constant(modules.get(sub.value.id), sub.attr)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                found = _constant(bare, sub.id)
                if not found and sub.id not in seen:
                    seen.add(sub.id)
                    for where in (scope, tree):
                        for value in bindings.get(where, {}).get(sub.id, []):
                            found |= named(value, where, seen)
                out |= found
        return out

    asked: set[str] = set()
    unread: list[int] = []
    for node in sorted(calls, key=lambda call: call.lineno):
        argument = (node.args[0] if node.args
                    else next((k.value for k in node.keywords), None))
        got: set[str] = set()
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            got.add(argument.value)
        elif argument is not None:
            got = named(argument, scopes.get(node, tree), set())
        asked |= got
        if not got:
            unread.append(node.lineno)
    return asked, unread


def _imported(node: ast.AST) -> dict[str, object]:
    """The names one import binds to the rig or to `vos.env`, each with its module:
    `from vos import gallina`, relatively or under another name, or `import vos.env as e`."""
    if isinstance(node, ast.ImportFrom):
        source = node.module or ""
        if source == "vos" or (node.level and not source):
            return {a.asname or a.name: _MODULES[a.name] for a in node.names
                    if a.name in _MODULES}
    elif isinstance(node, ast.Import):
        return {a.asname: _MODULES[a.name.removeprefix("vos.")] for a in node.names
                if a.asname and a.name.removeprefix("vos.") in _MODULES
                and a.name.startswith("vos.")}
    return {}


def _modules(tree: ast.Module) -> dict[str, object]:
    """Every name one module's imports bind to the rig or to `vos.env`."""
    return {name: module for node in ast.walk(tree)
            for name, module in _imported(node).items()}


def _calls_prover(func: ast.expr, callees: set[str], modules: dict[str, object]) -> bool:
    if isinstance(func, ast.Name):
        return func.id in callees
    return (isinstance(func, ast.Attribute) and func.attr == _PROVER
            and isinstance(func.value, ast.Name) and modules.get(func.value.id) is gallina)


def _constant(module: object, name: str) -> set[str]:
    """The switch one of the rig's or env's `_SWITCH` constants holds, or nothing."""
    value = getattr(module, name, None) if module and name.endswith(_SWITCH_SUFFIX) else None
    return {value} if isinstance(value, str) else set()


def _binds(node: ast.AST) -> list[tuple[str, ast.expr]]:
    """The names one statement or clause binds, each with the expression it binds from."""
    if isinstance(node, ast.Assign):
        pairs = [(target, node.value) for target in node.targets]
    elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None:
        pairs = [(node.target, node.value)]
    elif isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
        pairs = [(node.target, node.iter)]
    else:
        return []
    return [(name.id, value) for target, value in pairs for name in ast.walk(target)
            if isinstance(name, ast.Name)]


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    findings, ok = decide(ctx.root, ctx.corpus.tracked, INSTRUMENTS)
    rep.report("K-117", "form(s) Rocq 9.3 adds in a file an older Rocq compiles, or a "
               "reading of what compiles it that failed:", findings, ok)
    rep.line()
