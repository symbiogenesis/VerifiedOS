# SPDX-License-Identifier: Apache-2.0
"""Lower the Clight `switch` statements Vélus prints into `if` chains, after normalization.

The accepted typed purecap route refuses every Clight `switch` (F-472), and Vélus prints
each Obc conditional as one. This is the exchange's second rewrite: it reads the
normalizer's output and lowers to `if` chains only the `switch` shapes that Vélus's one
Obc `Switch` translation site prints, refusing every other `switch`. Input with no
`switch` token is returned byte-identically. Nothing here reads or changes Vélus, its
printer, the normalizer or the accepted compiler.

**The site.** `translate_stmt` in Vélus's `src/ObcToClight/Generation.v` (`SITE` below,
bound by hash at Vélus `27ba860c2624ba232816591290c6c119b9ead88a`) is the only place an
Obc `Switch e branches default` becomes a Clight `Sswitch`. Its labelled statements put
one `case i` for each present branch `i`, in increasing order, each body followed by a
`break`, and then the default last, with no `break`. The Clight printer (`PRINTER`)
writes that as

    switch (E) {
      case K1:
        B1
        break;
      ...
      default:
        D
    }

where an empty body prints nothing: `case K: break;` for a branch whose statement is a
skip, and `default:` directly before the closing brace for a skip default. The site
emits no other labels, no `goto`, no loop and no `if`, so a body's statements are
assignments, calls, skips and nested switches.

**The declared shapes** are the ones this layout takes in the printed output of Vélus's
passes ahead of the site (Obc switch normalization, its two-way default insertion and
fusion). Every case label is a decimal integer and the labels strictly increase:

    if-else      one case with a non-empty body, a non-empty default
    if-only      one case with a non-empty body, an empty default (a clock guard)
    else-only    one case labelled 0 with an empty body, a non-empty default
    chain-else   two or more cases with non-empty bodies, a non-empty default
    chain-only   two or more cases with non-empty bodies, an empty default

A body may hold further switches, each of which must itself be a declared shape. Every
other `switch` is refused: no case, an empty case body outside `else-only`, a label out
of order or not in decimal, a `break` anywhere but ending a case, a `case` or `default`
after the default, and any brace, label, `if`, loop, `goto`, `continue` or `return`
inside a body. A `case`, `default` or `break` outside a switch is refused too.

**The lowering** keeps every byte outside a switch and every body's bytes, and replaces
only the label and `break` text between them:

    if ((E) == K1) {B1} else if ((E) == K2) {B2} ... else {D}

E's bytes are repeated before each comparison. A Clight expression has no side effect
and no body runs between comparisons, so each evaluation reads the same value; Vélus's
layout has no fall-through, so exactly the body whose label equals that value runs, or
the default. A record lists every group by position, with its shape and labels.

    python3 switch_rewrite.py INPUT --out OUTPUT [--record RECORD.json]

Exit 0 having written OUTPUT and RECORD; exit 2 on a refusal, writing neither.
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# The one translation site, and the printer that writes its labelled statements.
SITE = {"velus_revision": "27ba860c2624ba232816591290c6c119b9ead88a",
        "file": "src/ObcToClight/Generation.v",
        "sha256": "0edb3ffad07e250fb84319d95666277a9eaa4033dca2c862f06a83bbd8dfce8d",
        "construct": "translate_stmt's Switch arm, through make_labeled_statements"}
PRINTER = {"file": "CompCert/cfrontend/PrintClight.ml",
           "sha256": "25a3f8489ae6444356262f3f4fc6f3bb1e3b3303f5fbf22ce0228c1cb25305db",
           "construct": "print_stmt's Sswitch arm and print_cases"}
SHAPES = {
    "if-else": "one case with a non-empty body, a non-empty default",
    "if-only": "one case with a non-empty body, an empty default",
    "else-only": "one case labelled 0 with an empty body, a non-empty default",
    "chain-else": "two or more cases with non-empty bodies, a non-empty default",
    "chain-only": "two or more cases with non-empty bodies, an empty default",
}
# Statement words the site never prints inside a switch body.
FORBIDDEN = frozenset({"if", "else", "while", "for", "do", "goto", "continue", "return"})
# Tokens a scrutinee, which is one printed expression, never holds.
NOT_EXPRESSION = FORBIDDEN | {"switch", "case", "default", "break", "{", "}", ";", ":", "?"}
LABEL = re.compile(r"0|[1-9][0-9]*")
LABEL_LIMIT = (1 << 32) - 1

_LEX = re.compile(r"""
    (?P<space>[ \t\n]+)
  | (?P<comment>/\*.*?\*/)
  | (?P<line>//)
  | (?P<open>/\*)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<num>\.?[0-9](?:[eEpP][+-]|[0-9A-Za-z_.])*)
  | (?P<punct><<=|>>=|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%&|^!~<>=?:;,.(){}\[\]])
""", re.VERBOSE | re.DOTALL)


class RefusalError(ValueError):
    """The input carries a `switch` outside the declared shapes, or is not printed Clight."""


@dataclass(frozen=True)
class Token:
    text: str
    kind: str
    start: int
    end: int


@dataclass
class Case:
    label: int
    keyword: int    # index of `case`
    colon: int      # index of its `:`
    stop: int       # index of the `break` that ends it
    nested: list[Group] = field(default_factory=list)


@dataclass
class Group:
    keyword: int    # index of `switch`
    close_paren: int
    cases: list[Case]
    default_colon: int
    close_brace: int
    depth: int
    owner: str
    nested: list[Group] = field(default_factory=list)   # those in the default body
    shape: str = ""


def lex(text: str) -> list[Token]:
    """The printer's tokens, refusing any byte its vocabulary does not contain."""
    if not text.isascii():
        raise RefusalError("non-ASCII input: the Clight printer writes ASCII")
    tokens: list[Token] = []
    at = 0
    while at < len(text):
        match = _LEX.match(text, at)
        if match is None:
            raise RefusalError(f"unexpected character {text[at]!r} at offset {at}")
        kind = match.lastgroup or ""
        if kind == "line":
            raise RefusalError(f"line comment at offset {at}: the printer writes none")
        if kind == "open":
            raise RefusalError(f"unterminated comment at offset {at}")
        if kind in ("id", "num", "punct"):
            tokens.append(Token(match.group(), kind, match.start(), match.end()))
        at = match.end()
    return tokens


class _Parser:
    def __init__(self, text: str, tokens: list[Token]) -> None:
        self.text = text
        self.toks = tokens
        self.owners = self._owners()

    def _owners(self) -> list[str]:
        """The function each token sits in, or "" at file scope."""
        owners: list[str] = []
        depth, candidate, current = 0, "", ""
        for index, token in enumerate(self.toks):
            if depth == 0 and token.kind == "id" and self.peek(index + 1) == "(":
                candidate = token.text
            if token.text == "{":
                if depth == 0:
                    current = candidate
                depth += 1
            owners.append(current)
            if token.text == "}":
                depth -= 1
                if depth == 0:
                    current = ""
        return owners

    def peek(self, index: int) -> str:
        return self.toks[index].text if 0 <= index < len(self.toks) else ""

    def where(self, index: int) -> tuple[int, int]:
        start = self.toks[index].start
        return (self.text.count("\n", 0, start) + 1,
                start - self.text.rfind("\n", 0, start))

    def fail(self, message: str, index: int) -> RefusalError:
        index = max(0, min(index, len(self.toks) - 1))
        line, column = self.where(index)
        return RefusalError(f"line {line} column {column}: {message}")

    def expect(self, index: int, text: str, what: str) -> None:
        if self.peek(index) != text:
            raise self.fail(f"{what}: expected `{text}`, found "
                            f"`{self.peek(index) or 'end of input'}`", index)

    def matching_paren(self, index: int) -> int:
        depth = 0
        for at in range(index, len(self.toks)):
            text = self.toks[at].text
            depth += (text == "(") - (text == ")")
            if depth == 0:
                return at
        raise self.fail("unbalanced parenthesis", index)

    def group(self, index: int, depth: int) -> Group:
        """The switch at `index`, refused unless it has the site's layout."""
        self.expect(index + 1, "(", "a switch")
        close = self.matching_paren(index + 1)
        if close == index + 2:
            raise self.fail("a switch with no scrutinee", index)
        for at in range(index + 2, close):
            if self.toks[at].text in NOT_EXPRESSION:
                raise self.fail(f"`{self.toks[at].text}` in a switch's scrutinee", at)
        self.expect(close + 1, "{", "a switch body")
        at = close + 2
        cases: list[Case] = []
        while self.peek(at) == "case":
            label = self.peek(at + 1)
            if self.toks[at + 1].kind != "num" or LABEL.fullmatch(label) is None:
                raise self.fail(f"case label `{label}` is not the printer's decimal", at + 1)
            value = int(label)
            if value > LABEL_LIMIT:
                raise self.fail(f"case label {value} exceeds an enumeration tag", at + 1)
            if cases and value <= cases[-1].label:
                raise self.fail(f"case label {value} does not increase on "
                                f"{cases[-1].label}", at + 1)
            self.expect(at + 2, ":", "a case label")
            case = Case(value, at, at + 2, 0)
            case.stop = self.body(at + 3, depth, case.nested, in_case=True)
            self.expect(case.stop + 1, ";", "a case's break")
            cases.append(case)
            at = case.stop + 2
        if not cases:
            raise self.fail("a switch with no case: not a declared shape", index)
        self.expect(at, "default", "the switch after its cases")
        self.expect(at + 1, ":", "the default label")
        default_colon = at + 1
        nested: list[Group] = []
        close_brace = self.body(at + 2, depth, nested, in_case=False)
        group = Group(index, close, cases, default_colon, close_brace, depth,
                      self.owners[index], nested)
        group.shape = self.shape(group)
        return group

    def body(self, at: int, depth: int, nested: list[Group], in_case: bool) -> int:
        """Scan a body from `at`: the index of the `break` ending a case body, or of the
        `}` closing the switch after its default body."""
        while True:
            if at >= len(self.toks):
                raise self.fail("unterminated switch", len(self.toks) - 1)
            text = self.toks[at].text
            if text == "switch":
                inner = self.group(at, depth + 1)
                nested.append(inner)
                at = inner.close_brace + 1
                continue
            if text == "break":
                if not in_case:
                    raise self.fail("a `break` in the default body: the site ends only "
                                    "cases with one", at)
                after = self.peek(at + 2)
                if self.peek(at + 1) != ";" or after not in ("case", "default"):
                    raise self.fail("a `break` that does not end a case before the next "
                                    "label", at)
                return at
            if text == "}":
                if in_case:
                    raise self.fail("a case body that does not end in `break`", at)
                return at
            if text in ("case", "default"):
                raise self.fail(f"`{text}` " + ("inside a case body: a fall-through"
                                                if in_case else "after the default"), at)
            if text == "{":
                raise self.fail("a brace in a switch body that opens no switch", at)
            if text in FORBIDDEN:
                raise self.fail(f"`{text}` in a switch body: the site prints none", at)
            if text in (":", "?"):
                raise self.fail(f"`{text}` in a switch body: the site prints no label "
                                "or conditional", at)
            at += 1

    def shape(self, group: Group) -> str:
        empty = [case for case in group.cases if case.stop == case.colon + 1]
        default_empty = group.close_brace == group.default_colon + 1
        if empty:
            if len(group.cases) == 1 and group.cases[0].label == 0 and not default_empty:
                return "else-only"
            raise self.fail("an empty case body outside the declared else-only shape",
                            empty[0].keyword)
        if len(group.cases) == 1:
            return "if-only" if default_empty else "if-else"
        return "chain-only" if default_empty else "chain-else"

    def unit(self) -> list[Group]:
        groups: list[Group] = []
        at = 0
        while at < len(self.toks):
            text = self.toks[at].text
            if text == "switch":
                group = self.group(at, 0)
                groups.append(group)
                at = group.close_brace + 1
                continue
            if text in ("case", "default", "break"):
                raise self.fail(f"`{text}` outside a switch", at)
            at += 1
        return groups


@dataclass(frozen=True)
class Site:
    """One lowered switch: where it was, what it held, and the shape it had."""

    line: int
    column: int
    depth: int
    owner: str
    shape: str
    labels: list[int]
    scrutinee: str
    empty_cases: int
    default_empty: bool


class _Renderer:
    def __init__(self, parser: _Parser) -> None:
        self.parser = parser
        self.text = parser.text
        self.toks = parser.toks
        self.sites: list[Site] = []

    def span(self, start: int, stop: int, nested: list[Group]) -> str:
        """The bytes from offset `start` to `stop`, each nested switch lowered."""
        out: list[str] = []
        at = start
        for group in nested:
            out.append(self.text[at:self.toks[group.keyword].start])
            out.append(self.group(group))
            at = self.toks[group.close_brace].end
        out.append(self.text[at:stop])
        return "".join(out)

    def group(self, group: Group) -> str:
        toks = self.toks
        scrutinee = self.text[toks[group.keyword + 2].start:toks[group.close_paren - 1].end]
        line, column = self.parser.where(group.keyword)
        self.sites.append(Site(line, column, group.depth, group.owner, group.shape,
                               [case.label for case in group.cases], scrutinee,
                               sum(case.stop == case.colon + 1 for case in group.cases),
                               group.close_brace == group.default_colon + 1))
        out: list[str] = []
        for index, case in enumerate(group.cases):
            out.append(("if" if index == 0 else "} else if")
                       + f" (({scrutinee}) == {case.label}) {{")
            out.append(self.span(toks[case.colon].end, toks[case.stop].start, case.nested))
        out.append("} else {")
        out.append(self.span(toks[group.default_colon].end, toks[group.close_brace].start,
                             group.nested))
        out.append("}")
        return "".join(out)


def rewrite(text: str) -> tuple[str, list[Site]]:
    """The input with every declared switch lowered, and each group in source order."""
    tokens = lex(text)
    if not any(token.text == "switch" for token in tokens):
        return text, []
    parser = _Parser(text, tokens)
    groups = parser.unit()
    renderer = _Renderer(parser)
    out = renderer.span(0, len(text), groups)
    order = sorted(renderer.sites, key=lambda site: (site.line, site.column))
    return out, order


def _identity(data: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    try:
        text = raw.decode("ascii")
        rewritten, sites = rewrite(text)
    except (UnicodeDecodeError, RefusalError) as err:
        print(f"refused: {args.input}: {err}", file=sys.stderr)
        return 2
    data = rewritten.encode("ascii")
    args.out.write_bytes(data)
    shapes = {name: sum(site.shape == name for site in sites) for name in SHAPES}
    record = {
        "rewrite": "supervisor/route/switch_rewrite.py",
        "site": SITE,
        "printer": PRINTER,
        "shapes": SHAPES,
        "input": {"path": str(args.input), **_identity(raw)},
        "output": {"path": str(args.out), **_identity(data)},
        "identical": data == raw,
        "lowered": len(sites),
        "by_shape": shapes,
        "groups": [asdict(site) for site in sites],
    }
    if args.record is not None:
        args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8",
                               newline="\n")
    print(f"lowered {len(sites)} switch group(s): "
          + ", ".join(f"{name} {count}" for name, count in shapes.items() if count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
