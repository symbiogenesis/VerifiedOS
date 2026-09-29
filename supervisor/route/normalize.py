# SPDX-License-Identifier: Apache-2.0
"""Erase Vélus's forbidden 64-bit alignment specifiers from its printed library Clight.

Vélus types every 64-bit integer as a CompCert `Tlong` carrying an explicit 8-byte
alignment attribute, and the Clight printer writes it as ` _Alignas(8)` after
`long long` or `unsigned long long` wherever that type is printed. The accepted purecap
frontend refuses the exchange because some of those positions are ones where C11
forbids an alignment specifier. The RV64 natural alignment of both types is already 8.

This removes those groups, byte for byte, only where C11 forbids the specifier and
Vélus's generation places one: parameter declarators in prototypes, definitions and
extern prototypes, `register` temporaries, function return types and cast type names.
Structure members stay byte-identical. Every other alignment specifier is refused, as
is any value other than 8, any other type, a group before a pointer declarator, whose
declared object is a pointer, and a group not in the printer's exact ` _Alignas(8)`
byte form. Input is accepted only in the form `-nomain -lib` printing takes: a
file-scope object, a `main` function or a `volatile` qualifier, which only main-node
compilation prints, is refused, as is any construct outside the printer's declaration
vocabulary. Under `-nomain`, Vélus ignores `-lib`: the no-main arm of its ObcToClight
`Generation.translate` makes every generated function public either way, so no byte
distinguishes `-nomain -lib` output and acceptance rests on those markers. Input
without an alignment specifier is returned byte-identically.

Nothing here reads or changes Vélus, its printer or the accepted compiler, and no
alignment is inferred: the record lists every group removed or kept, by position.

    python3 normalize.py INPUT --out OUTPUT [--record RECORD.json]

Exit 0 having written OUTPUT and RECORD; exit 2 on a refusal, writing neither.
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

GROUP = " _Alignas(8)"
LONG_TYPES = ("long long", "unsigned long long")
# The printer's base type names, longest spelling first so a prefix never wins.
BASES = (("unsigned", "long", "long"), ("long", "long"), ("signed", "char"),
         ("unsigned", "char"), ("unsigned", "short"), ("unsigned", "int"), ("void",),
         ("short",), ("int",), ("_Bool",), ("float",), ("double",))
# Words no `-nomain` Clight dump carries; `volatile` is main-node compilation's.
FOREIGN = frozenset({"volatile", "static", "typedef", "alignas", "__attribute__",
                     "__attribute", "__declspec", "_Thread_local", "auto", "const"})
# A parenthesized type after one of these is an operand, not a cast.
NOT_CAST = frozenset({")", "]"})
# The only words a cast may follow; every other identifier makes `(` a call.
OPERAND_KEYWORDS = frozenset({"return", "case"})

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
    """The input is not printed `-nomain -lib` Clight this normalizer may change."""


@dataclass(frozen=True)
class Token:
    text: str
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Site:
    """One `_Alignas(8)` group: where it is, what it qualifies, and what was done."""

    line: int
    column: int
    kind: str          # parameter, return, register, cast or member
    declaration: str   # prototype, definition, extern, body or struct
    owner: str         # the function or structure it sits in
    type: str
    action: str        # removed or kept


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
    for token in tokens:
        if token.text in FOREIGN:
            raise RefusalError(f"`{token.text}` at offset {token.start}: "
                               + ("only main-node compilation prints it"
                                  if token.text == "volatile"
                                  else "the -nomain Clight printer writes none"))
    return tokens


class _Parser:
    def __init__(self, text: str, tokens: list[Token]) -> None:
        self.text = text
        self.toks = tokens
        self.at = 0
        self.sites: dict[int, Site] = {}
        self.functions = 0

    def peek(self, ahead: int = 0) -> str:
        index = self.at + ahead
        return self.toks[index].text if index < len(self.toks) else ""

    def where(self, index: int) -> tuple[int, int]:
        start = self.toks[index].start
        return (self.text.count("\n", 0, start) + 1,
                start - self.text.rfind("\n", 0, start))

    def fail(self, message: str, index: int | None = None) -> RefusalError:
        index = min(self.at if index is None else index, len(self.toks) - 1)
        line, column = self.where(index) if self.toks else (1, 1)
        return RefusalError(f"line {line} column {column}: {message}")

    def expect(self, text: str) -> None:
        if self.peek() != text:
            raise self.fail(f"expected `{text}`, found `{self.peek() or 'end of input'}`")
        self.at += 1

    def identifier(self, what: str) -> str:
        token = self.toks[self.at] if self.at < len(self.toks) else None
        if token is None or token.kind != "id" or token.text in FOREIGN:
            raise self.fail(f"expected {what}")
        self.at += 1
        return token.text

    def base(self) -> str:
        """One printed base type: a scalar name or `struct`/`union` and its tag."""
        if self.peek() in ("struct", "union"):
            keyword = self.peek()
            self.at += 1
            return f"{keyword} {self.identifier('a structure tag')}"
        for words in BASES:
            if all(self.peek(k) == word for k, word in enumerate(words)):
                self.at += len(words)
                return " ".join(words)
        raise self.fail(f"`{self.peek() or 'end of input'}` is not a printed type")

    def specifiers(self) -> tuple[str, int | None]:
        """A base type and the index of the one alignment group after it, if any."""
        typename = self.base()
        group = None
        if self.peek() == "_Alignas":
            group = self.at
            self.group_tokens(group)
            self.at += 4
            if self.peek() == "*":
                raise self.fail(f"alignment specifier on `{typename}` before a pointer "
                                "declarator: the declared object is a pointer, not an "
                                "erased position", group)
        return typename, group

    def group_tokens(self, index: int) -> str:
        """The value of the well-formed `_Alignas ( N )` group at `index`."""
        texts = [t.text for t in self.toks[index:index + 4]]
        if len(texts) < 4 or texts[1] != "(" or texts[3] != ")" \
                or self.toks[index + 2].kind != "num":
            raise self.fail("malformed alignment specifier", index)
        return texts[2]

    def pointers(self) -> int:
        count = 0
        while self.peek() == "*":
            self.at += 1
            count += 1
            if self.peek() == "_Alignas":
                raise self.fail("alignment specifier on a pointer: not an erased position")
        return count

    def record(self, index: int, typename: str, kind: str, declaration: str,
               owner: str) -> None:
        """Decide one group at an enumerated position, refusing all but the erased form."""
        value = self.group_tokens(index)
        if typename not in LONG_TYPES:
            raise self.fail(f"alignment specifier on `{typename}` ({kind} of {owner}): only "
                            "`long long` and `unsigned long long` carry Vélus's alignment",
                            index)
        if value != "8":
            raise self.fail(f"alignment {value} on `{typename}` ({kind} of {owner}): only "
                            "the 8 of Vélus's `Tlong` is erased", index)
        token = self.toks[index]
        if self.text[token.start - 1:self.toks[index + 3].end] != GROUP:
            raise self.fail("alignment group not in the printer's ` _Alignas(8)` form", index)
        line, column = self.where(index)
        self.sites[index] = Site(line, column, kind, declaration, owner, typename,
                                 "kept" if kind == "member" else "removed")

    def composite(self) -> None:
        """`struct T;` or `struct T { members };`, members left as printed."""
        keyword = self.peek()
        self.at += 1
        tag = self.identifier("a structure tag")
        if self.peek() == ";":
            self.at += 1
            return
        if self.peek() == "_Alignas":
            raise self.fail(f"file-scope alignment on `{keyword} {tag}`")
        self.expect("{")
        while self.peek() != "}":
            typename, group = self.specifiers()
            self.pointers()
            member = self.identifier("a member name")
            if self.peek() == ":":
                raise self.fail(f"bit-field `{member}`: Vélus prints none")
            self.expect(";")
            if group is not None:
                self.record(group, typename, "member", "struct", f"{keyword} {tag}")
        self.expect("}")
        self.expect(";")

    def parameters(self, declaration: str, owner: str) -> None:
        self.expect("(")
        if self.peek() == "void" and self.peek(1) == ")":
            self.at += 2
            return
        while True:
            typename, group = self.specifiers()
            self.pointers()
            if self.at < len(self.toks) and self.toks[self.at].kind == "id":
                self.identifier("a parameter name")
            if group is not None:
                self.record(group, typename, "parameter", declaration, owner)
            if self.peek() == ",":
                self.at += 1
                continue
            self.expect(")")
            return

    def body(self, owner: str) -> None:
        """Scan one definition's body; only register temporaries and casts may carry a group."""
        opened = self.at
        self.expect("{")
        depth = 1
        while depth:
            if self.at >= len(self.toks):
                raise self.fail(f"unterminated body of `{owner}`", opened)
            text = self.toks[self.at].text
            if text in ("{", "}"):
                depth += 1 if text == "{" else -1
            elif text == "_Alignas":
                self.body_group(self.at, owner)
            self.at += 1

    def body_group(self, index: int, owner: str) -> None:
        self.group_tokens(index)
        texts = [t.text for t in self.toks]
        if texts[index - 2:index] != ["long", "long"]:
            previous = texts[index - 1]
            raise self.fail(f"alignment specifier after `{previous}` in `{owner}`: only "
                            "`long long` and `unsigned long long` carry Vélus's alignment",
                            index)
        signed = texts[index - 3] != "unsigned"
        start = index - 2 if signed else index - 3
        typename = "long long" if signed else "unsigned long long"
        after = index + 4
        if after + 1 >= len(texts):
            raise self.fail(f"unterminated body of `{owner}`", index)
        before = self.toks[start - 2]
        if texts[start - 1] == "register" and before.text in ("{", ";") \
                and self.toks[after].kind == "id" and texts[after + 1] == ";":
            self.record(index, typename, "register", "body", owner)
        elif texts[start - 1] == "(" and texts[after] == ")" \
                and (before.kind == "punct" or before.text in OPERAND_KEYWORDS) \
                and before.text not in NOT_CAST:
            self.record(index, typename, "cast", "body", owner)
        else:
            raise self.fail(f"alignment specifier at a position in `{owner}` that is "
                            "neither a register temporary nor a cast", index)

    def declaration(self) -> None:
        """A prototype, extern prototype or definition; a file-scope object is refused."""
        first = self.at
        extern = self.peek() == "extern"
        if extern:
            self.at += 1
        typename, group = self.specifiers()
        self.pointers()
        name = self.identifier("a declarator name")
        if self.peek() != "(":
            what = "file-scope alignment on" if group is not None else "file-scope object"
            raise self.fail(f"{what} `{name}`: only main-node compilation prints one", first)
        if name == "main":
            raise self.fail("a `main` function: only main-node compilation prints one", first)
        close = self.matching(self.at)
        after = self.toks[close + 1].text if close + 1 < len(self.toks) else ""
        if after not in (";", "{"):
            raise self.fail(f"`{name}` is neither declared nor defined", close)
        if extern and after == "{":
            raise self.fail(f"extern definition of `{name}`", first)
        kind = "extern" if extern else "prototype" if after == ";" else "definition"
        self.parameters(kind, name)
        if group is not None:
            self.record(group, typename, "return", kind, name)
        if after == ";":
            self.expect(";")
        else:
            self.body(name)
            self.functions += 1

    def matching(self, index: int) -> int:
        depth = 0
        for at in range(index, len(self.toks)):
            text = self.toks[at].text
            depth += (text == "(") - (text == ")")
            if depth == 0:
                return at
        raise self.fail("unbalanced parenthesis", index)

    def unit(self) -> None:
        while self.at < len(self.toks):
            if self.peek() in ("struct", "union") and self.peek(2) in (";", "{", "_Alignas"):
                self.composite()
            else:
                self.declaration()
        if not self.functions:
            raise RefusalError("no function definition: not a printed Vélus library")
        unhandled = [i for i, t in enumerate(self.toks)
                     if t.text == "_Alignas" and i not in self.sites]
        if unhandled:
            raise self.fail("alignment specifier at no enumerated position", unhandled[0])


def normalize(text: str) -> tuple[str, list[Site]]:
    """The input with every erased group removed, and each group's decision in order."""
    tokens = lex(text)
    parser = _Parser(text, tokens)
    parser.unit()
    out: list[str] = []
    at = 0
    for index in sorted(parser.sites):
        if parser.sites[index].action == "removed":
            start = tokens[index].start - 1
            out.append(text[at:start])
            at = start + len(GROUP)
    out.append(text[at:])
    return "".join(out), [parser.sites[i] for i in sorted(parser.sites)]


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
        normalized, sites = normalize(text)
    except (UnicodeDecodeError, RefusalError) as err:
        print(f"refused: {args.input}: {err}", file=sys.stderr)
        return 2
    data = normalized.encode("ascii")
    args.out.write_bytes(data)
    record = {
        "normalizer": "supervisor/route/normalize.py",
        "input": {"path": str(args.input), **_identity(raw)},
        "output": {"path": str(args.out), **_identity(data)},
        "removed": sum(site.action == "removed" for site in sites),
        "kept": sum(site.action == "kept" for site in sites),
        "sites": [asdict(site) for site in sites],
    }
    if args.record is not None:
        args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8",
                               newline="\n")
    print(f"removed {record['removed']} and kept {record['kept']} alignment group(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
