# SPDX-License-Identifier: Apache-2.0
"""The model's own expressions, read as expressions rather than matched as text.

An `encdec` clause's `when` guard is the one part of the decode surface the bundle
carries as **text**: there is no structured guard node, so a reader that wants to know
whether the model can decode a form has the guard's source and nothing else. Matching
that text against a list of known spellings is the transcription this repository exists
to refuse, so what is here is a parse instead: a tokenizer, a precedence climber, and an
evaluator that resolves every name against the bundle's own definitions.

**This module is a parse and never a decision.** What an `UNKNOWN` means for admission,
which configuration the resolution is taken at, and what to do with a name the model does
not define are all [dialectgen.py](dialectgen.py)'s, which is where the one decision in
this pair is written down.

## Three-valued, because two values would be a lie in both directions

A guard is a predicate over the machine as well as over the encoding, and the two are not
separable in the text: `currentlyEnabled(Ext_M)` is `hartSupports(Ext_M) & misa[M] == 0b1`,
so whether the model decodes a `mul` today is a function of a CSR. An evaluator with two
values has to answer that either `true`, which claims a machine state it cannot see, or
`false`, which deletes the whole M extension from an assembler. So the third value is
`UNKNOWN` and it means exactly *this is machine state*, reached the one way it can be
reached soundly: a name that is a **register**, or a function whose body reads one.

`UNKNOWN` is not an error value. A name this module cannot resolve at all raises
`UnresolvedError`, and the two are kept apart deliberately, because a caller that read them
as one would admit an encoding on the strength of a typo.

## What the grammar covers, and why it stops where it does

Everything reached from an `encdec` guard and from the definitions those guards call
into: `&`, `|`, `not`, comparison, arithmetic, `if`/`then`/`else`, `match`, application,
`config` paths, `sizeof`, and the bit and integer literals. It does **not** cover
statements, assignment, subscripting or a `let` sequence, and that is the boundary the
`UNKNOWN` rule above sits on rather than a gap: a body needing any of them in this
corpus is a body that reads machine state, so it is answered before it is parsed.
"""

import re
from dataclasses import dataclass
from typing import Final, Protocol, override

# --- values -------------------------------------------------------------------------
# Four value shapes and one absence. `Bits` carries its width because the model compares
# a field against a bit literal of the same width and a bare integer would lose it;
# `Sym` carries its enum and its ordinal because the model orders an enum with `>=`
# (`vector_support_level >= Full`) and a bare name could not answer that.


@dataclass(frozen=True)
class Bits:
    value: int
    width: int


@dataclass(frozen=True)
class Sym:
    """One enum member: its name, the enum that declares it, and its position in it.

    `ordinal` is `UNORDERED` where the member's position is not recoverable, which is
    every member of a `scattered enum`. Equality still decides there and ordering does
    not, and the difference is refused rather than papered over: two members handed the
    same position would make `<` answer `false` about every pair of them.
    """

    name: str
    enum: str
    ordinal: int


UNORDERED: Final[int] = -1


class _Unknown:
    """Machine state: a value this lane cannot see and must not guess at."""

    @override
    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN: Final[_Unknown] = _Unknown()

Value = bool | int | Bits | Sym | _Unknown


class UnresolvedError(RuntimeError):
    """A name or a form this evaluator does not resolve.

    Raised rather than answered `UNKNOWN`, because the two mean opposite things to a
    caller deciding admission: `UNKNOWN` is a fact about the machine and this is a fact
    about the reader.
    """


# --- the environment a caller supplies ----------------------------------------------


class Environment(Protocol):
    """What an evaluator needs from outside the expression.

    Every member may raise `UnresolvedError`, and `is_state` is the one that decides the
    `UNKNOWN` rule: it answers whether a bare name is machine state, which is how a
    register reaches this evaluator without this module knowing what a register is.
    """

    def is_state(self, name: str) -> bool: ...

    def value_of(self, name: str) -> Value: ...

    def call(self, name: str, args: list[Value]) -> Value: ...

    def config(self, path: str) -> Value: ...

    def size_of(self, name: str) -> Value: ...


# --- tokens -------------------------------------------------------------------------

_TOKEN = re.compile(r"""
    (?P<space>\s+|//[^\n]*)
  | (?P<bits>0b[01_]+|0x[0-9a-fA-F_]+)
  | (?P<num>\d[\d_]*)
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op><=|>=|==|!=|=>|[-+*/%&|^<>(),{}=;.\[\]])
""", re.VERBOSE)

_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"if", "then", "else", "match", "config", "sizeof", "not", "true", "false"})

Token = tuple[str, str]


def tokens(text: str) -> list[Token]:
    """The expression's tokens, or `UnresolvedError` on a character the grammar has no rule
    for. Comments are dropped with whitespace: a `when` guard in this corpus never
    carries one, and a *body* reached through a call does."""
    out: list[Token] = []
    at = 0
    while at < len(text):
        found = _TOKEN.match(text, at)
        if found is None:
            raise UnresolvedError(f"cannot read {text[at:at + 24]!r}")
        at = found.end()
        kind = found.lastgroup
        if kind is None:
            raise UnresolvedError("the lexer matched in no named group")
        if kind != "space":
            out.append((kind, found.group()))
    return out


# --- the syntax tree ----------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    """One expression node, kept as one shape rather than a class per form.

    `kind` names the form and `parts` its children, with `text` carrying the one datum a
    child cannot: the operator, the literal's spelling, or the name applied. A tree of
    one dataclass is what lets the evaluator below be one walk with one `match`, which
    is the whole of what this tree is for.
    """

    kind: str
    text: str = ""
    parts: tuple[Node, ...] = ()


_BINARY: Final[tuple[tuple[str, ...], ...]] = (
    ("|",), ("&",), ("==", "!=", "<=", ">=", "<", ">"), ("+", "-"), ("*", "/", "%"),
    ("^",),
)


class _Parser:
    """A precedence climber over `_BINARY`, written as a class so the position is one
    field rather than a value threaded through every return."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = tokens(text)
        self.at = 0

    def peek(self) -> Token | None:
        return self.toks[self.at] if self.at < len(self.toks) else None

    def take(self, want: str) -> None:
        got = self.peek()
        if got is None or got[1] != want:
            raise UnresolvedError(f"expected {want!r} in {self.text!r}")
        self.at += 1

    def parse(self) -> Node:
        node = self.expr(0)
        if self.at != len(self.toks):
            raise UnresolvedError(f"trailing input in {self.text!r}")
        return node

    def expr(self, level: int) -> Node:
        if level >= len(_BINARY):
            return self.unary()
        left = self.expr(level + 1)
        while (got := self.peek()) is not None and got[1] in _BINARY[level]:
            self.at += 1
            right = self.expr(level + 1)
            left = Node("binary", got[1], (left, right))
        return left

    def unary(self) -> Node:
        got = self.peek()
        if got is not None and got[1] == "-":
            self.at += 1
            return Node("negate", parts=(self.unary(),))
        return self.atom()

    def atom(self) -> Node:
        got = self.peek()
        if got is None:
            raise UnresolvedError(f"{self.text!r} ends early")
        kind, text = got
        self.at += 1
        if kind == "bits":
            return Node("bits", text)
        if kind == "num":
            return Node("number", text)
        if text == "(":
            inner = self.expr(0)
            self.take(")")
            return inner
        if kind == "name":
            return self.named(text)
        raise UnresolvedError(f"cannot read {text!r} in {self.text!r}")

    def named(self, text: str) -> Node:
        if text in ("true", "false"):
            return Node("boolean", text)
        if text == "not":
            self.take("(")
            inner = self.expr(0)
            self.take(")")
            return Node("not", parts=(inner,))
        if text == "if":
            return self.conditional()
        if text == "match":
            return self.matched()
        if text == "config":
            return Node("config", self.dotted())
        if text == "sizeof":
            self.take("(")
            name = self.identifier()
            self.take(")")
            return Node("sizeof", name)
        if (got := self.peek()) is not None and got[1] == "(":
            return Node("apply", text, tuple(self.arguments()))
        return Node("name", text)

    def conditional(self) -> Node:
        test = self.expr(0)
        self.take("then")
        yes = self.expr(0)
        self.take("else")
        return Node("if", parts=(test, yes, self.expr(0)))

    def matched(self) -> Node:
        subject = self.expr(0)
        self.take("{")
        arms: list[Node] = [subject]
        while (got := self.peek()) is not None and got[1] != "}":
            key = self.pattern()
            self.take("=>")
            arms.append(Node("arm", key, (self.expr(0),)))
            if (nxt := self.peek()) is not None and nxt[1] == ",":
                self.at += 1
        self.take("}")
        return Node("match", parts=tuple(arms))

    def pattern(self) -> str:
        """One `match` arm's key, as the token that names it.

        Only the shapes this corpus's guards reach: a bare name, which is an enum member
        or the wildcard `_`, and a literal. A structured pattern raises, because reading
        one as a name would silently take the wrong arm.
        """
        got = self.peek()
        if got is None:
            raise UnresolvedError("a match arm with no pattern")
        kind, text = got
        self.at += 1
        if kind in ("name", "bits", "num"):
            if kind == "name" and (nxt := self.peek()) is not None and nxt[1] == "(":
                raise UnresolvedError(f"a structured match pattern {text}(...)")
            return text
        raise UnresolvedError(f"cannot read the match pattern {text!r}")

    def identifier(self) -> str:
        got = self.peek()
        if got is None or got[0] != "name":
            raise UnresolvedError(f"expected a name in {self.text!r}")
        self.at += 1
        return got[1]

    def dotted(self) -> str:
        out = [self.identifier()]
        while (got := self.peek()) is not None and got[1] == ".":
            self.at += 1
            out.append(self.identifier())
        return ".".join(out)

    def arguments(self) -> list[Node]:
        self.take("(")
        args: list[Node] = []
        if (got := self.peek()) is not None and got[1] == ")":
            self.at += 1
            return args
        args.append(self.expr(0))
        while (got := self.peek()) is not None and got[1] == ",":
            self.at += 1
            args.append(self.expr(0))
        self.take(")")
        return args


def parse(text: str) -> Node:
    """One Sail expression, as a tree. `UnresolvedError` where the grammar has no rule."""
    stripped = text.strip()
    if not stripped:
        raise UnresolvedError("an empty expression")
    return _Parser(stripped).parse()


# --- evaluation ---------------------------------------------------------------------


def _literal(text: str) -> Value:
    body = text.replace("_", "")
    if body.startswith("0b"):
        return Bits(int(body, 0), len(body) - 2)
    if body.startswith("0x"):
        return Bits(int(body, 0), (len(body) - 2) * 4)
    return int(body)


def _numeric(value: Value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Bits):
        return value.value
    if isinstance(value, Sym):
        return value.ordinal
    return None


def _compare(op: str, left: Value, right: Value) -> Value:
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return UNKNOWN
    if op in ("==", "!=") and isinstance(left, bool) and isinstance(right, bool):
        return left == right if op == "==" else left != right
    if isinstance(left, Sym) and isinstance(right, Sym):
        if left.enum != right.enum:
            raise UnresolvedError(f"{left.name} and {right.name} are not one enum")
        if op in ("==", "!="):
            return left.name == right.name if op == "==" else left.name != right.name
        if UNORDERED in (left.ordinal, right.ordinal):
            raise UnresolvedError(
                f"{left.enum} is scattered, so `{op}` over its members is a question "
                f"its declaration does not answer")
    a, b = _numeric(left), _numeric(right)
    if a is None or b is None:
        raise UnresolvedError(f"cannot compare {left!r} {op} {right!r}")
    return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b,
            ">": a > b, ">=": a >= b}[op]


def _arithmetic(op: str, left: Value, right: Value) -> Value:
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return UNKNOWN
    a, b = _numeric(left), _numeric(right)
    if a is None or b is None:
        raise UnresolvedError(f"cannot compute {left!r} {op} {right!r}")
    if op in ("/", "%") and b == 0:
        raise UnresolvedError(f"a division by zero in {op}")
    if op == "^":
        # Sail spells exponentiation `^` in an arithmetic context, which is the one this
        # evaluator is ever in: `get_sew()` is `2 ^ get_sew_pow()`. A negative exponent
        # is not a whole number and is refused rather than truncated.
        if b < 0 or b > 64:
            raise UnresolvedError(f"an exponent of {b}")
        return int(a ** b)
    return {"+": a + b, "-": a - b, "*": a * b,
            "/": a // b, "%": a % b}[op]


def _conjoin(left: Value, right: Value) -> Value:
    """Kleene's `and`: false wins over unknown, because a guard whose extension is
    absent is refused whatever the machine state beside it turns out to be."""
    if left is False or right is False:
        return False
    if left is True and right is True:
        return True
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return UNKNOWN
    raise UnresolvedError(f"cannot conjoin {left!r} and {right!r}")


def _disjoin(left: Value, right: Value) -> Value:
    if left is True or right is True:
        return True
    if left is False and right is False:
        return False
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return UNKNOWN
    raise UnresolvedError(f"cannot disjoin {left!r} and {right!r}")


def evaluate(node: Node, env: Environment) -> Value:
    """One tree's value against one environment.

    Every branch either answers a value, answers `UNKNOWN` where the machine decides, or
    raises `UnresolvedError`. Nothing here guesses: an operator this walk has no rule for is
    the third outcome and never the second.
    """
    if node.kind == "number":
        return _literal(node.text)
    if node.kind == "bits":
        return _literal(node.text)
    if node.kind == "boolean":
        return node.text == "true"
    if node.kind == "name":
        return UNKNOWN if env.is_state(node.text) else env.value_of(node.text)
    if node.kind == "config":
        return env.config(node.text)
    if node.kind == "sizeof":
        return env.size_of(node.text)
    if node.kind == "not":
        inner = evaluate(node.parts[0], env)
        if isinstance(inner, _Unknown):
            return UNKNOWN
        if isinstance(inner, bool):
            return not inner
        raise UnresolvedError(f"not() over {inner!r}")
    if node.kind == "negate":
        return _arithmetic("-", 0, evaluate(node.parts[0], env))
    if node.kind == "binary":
        return _binary(node, env)
    if node.kind == "if":
        return _conditional(node, env)
    if node.kind == "match":
        return _matched(node, env)
    if node.kind == "apply":
        if env.is_state(node.text):
            return UNKNOWN
        return env.call(node.text, [evaluate(part, env) for part in node.parts])
    raise UnresolvedError(f"no evaluation for a {node.kind} node")


def _binary(node: Node, env: Environment) -> Value:
    left = evaluate(node.parts[0], env)
    if node.text == "&":
        if left is False:
            return False
        return _conjoin(left, evaluate(node.parts[1], env))
    if node.text == "|":
        if left is True:
            return True
        return _disjoin(left, evaluate(node.parts[1], env))
    right = evaluate(node.parts[1], env)
    if node.text in ("==", "!=", "<", "<=", ">", ">="):
        return _compare(node.text, left, right)
    return _arithmetic(node.text, left, right)


def _conditional(node: Node, env: Environment) -> Value:
    test = evaluate(node.parts[0], env)
    if test is True:
        return evaluate(node.parts[1], env)
    if test is False:
        return evaluate(node.parts[2], env)
    # An unknown test does not make the whole conditional unknown where both arms agree,
    # and the arms here often do: `if width < 4 then currentlyEnabled(Ext_Zabha) else
    # width <= xlen_bytes` is decided by a bound width whatever the branch.
    yes, no = evaluate(node.parts[1], env), evaluate(node.parts[2], env)
    if yes == no and not isinstance(yes, _Unknown):
        return yes
    return UNKNOWN


def _matched(node: Node, env: Environment) -> Value:
    subject = evaluate(node.parts[0], env)
    arms = node.parts[1:]
    if isinstance(subject, _Unknown):
        return _fold_arms(arms, env)
    key = subject.name if isinstance(subject, Sym) else None
    for arm in arms:
        if arm.text == "_" or (key is not None and arm.text == key):
            return evaluate(arm.parts[0], env)
        if key is None and _matches_literal(arm.text, subject):
            return evaluate(arm.parts[0], env)
    raise UnresolvedError(f"no match arm for {subject!r}")


def _matches_literal(pattern: str, subject: Value) -> bool:
    try:
        want = _literal(pattern)
    except ValueError:
        return False
    got, wanted = _numeric(subject), _numeric(want)
    return got is not None and got == wanted


def _fold_arms(arms: tuple[Node, ...], env: Environment) -> Value:
    """A `match` on an unknown subject is its arms' join: unknown unless every arm
    agrees, in which case the subject never decided anything."""
    seen: list[Value] = [evaluate(arm.parts[0], env) for arm in arms]
    first = seen[0] if seen else UNKNOWN
    if seen and all(value == first for value in seen) and not isinstance(first, _Unknown):
        return first
    return UNKNOWN
