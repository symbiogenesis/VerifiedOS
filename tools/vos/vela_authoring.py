# SPDX-License-Identifier: Apache-2.0
"""Source-preserving pure Vela formatting and optional compiler-owned lints.

The existing compiler owns syntax and semantic acceptance. This module only
renders its token stream and inspects its syntax and resolved declaration facts.
It performs no filesystem writes; the compiler command owns publication.
"""

import re
from dataclasses import dataclass, fields, is_dataclass
from typing import cast

from vos import vela
from vos import vela_ast as syntax
from vos.vela_source import SourceSnapshot

STYLE_VERSION = 1
LINT_CODES = frozenset({"VELA100", "VELA101", "VELA102", "VELA103", "VELA104"})
_MEMBER = re.compile(r"[A-Z][A-Za-z0-9]*")
_BINDING = re.compile(r"[a-z][A-Za-z0-9]*")


@dataclass(frozen=True)
class Finding:
    """An advisory finding at an original compiler source position."""

    code: str
    message: str
    line: int
    column: int


@dataclass(frozen=True)
class _Part:
    text: str
    kind: str
    line: int
    column: int
    blank_before: bool = False
    inline: bool = False


def _parts(source: bytes) -> list[_Part]:
    """Interleave the compiler's tokens with complete original line comments."""
    text = syntax.source_text(source).replace("\r\n", "\n").replace("\r", "\n")
    starts = [0, *(index + 1 for index, value in enumerate(text) if value == "\n")]
    result: list[_Part] = []
    cursor = 0
    for token in vela._tokens(source):
        start = len(text) if token.kind == "eof" else starts[token.line - 1] + token.column - 1
        token_blank = False
        while cursor < start:
            end = cursor
            while end < start and text[end] in " \t\n":
                end += 1
            blank = text[cursor:end].count("\n") > 1
            if end == start:
                token_blank = blank
                cursor = end
                break
            if not text.startswith("//", end):
                raise syntax.VelaError("format", token.line, token.column,
                                       "compiler trivia contains an uncovered source token")
            comment_end = text.find("\n", end)
            comment_end = len(text) if comment_end == -1 else comment_end
            site = syntax.position(text[:end])
            line_start = starts[site.line - 1]
            inline = bool(text[line_start:end].strip(" \t"))
            result.append(_Part(text[end:comment_end], "comment", site.line, site.column,
                                blank, inline))
            cursor = comment_end
        if token.kind == "eof":
            break
        result.append(_Part(token.text, token.kind, token.line, token.column,
                            token_blank))
        cursor = start + len(token.text)
    return result


def _fingerprint(parts: list[_Part]) -> tuple[object, ...]:
    """Bind token spelling, comment order/content and doc attachment boundaries."""
    result: list[object] = []
    for index, part in enumerate(parts):
        if part.kind != "comment":
            result.append((part.kind, part.text))
            continue
        following = parts[index + 1] if index + 1 < len(parts) else None
        doc_break = (following is not None and following.blank_before
                     if part.text.startswith("///") and not part.inline else False)
        result.append(("comment", part.text, part.inline, doc_break))
    return tuple(result)


def _shape(value: object) -> object:
    """Erase source positions from the existing compiler's located syntax."""
    if is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, tuple((field.name, _shape(getattr(value, field.name)))
                                            for field in fields(value) if field.name != "site"))
    if isinstance(value, tuple):
        return tuple(_shape(child) for child in value)
    return value


def _render(parts: list[_Part]) -> bytes:
    lines: list[str] = []
    current = ""
    indent = 0
    previous: _Part | None = None
    complete = False

    def flush() -> None:
        nonlocal current
        if current:
            lines.append("    " * indent + current)
            current = ""

    def blank() -> None:
        flush()
        if lines and lines[-1]:
            lines.append("")

    for part in parts:
        spelling = part.text
        if previous is not None and previous.kind == "comment" and part.blank_before:
            blank()
        if part.kind == "comment":
            if part.inline:
                if current:
                    current = current.rstrip(" ") + " " + spelling
                    flush()
                elif lines:
                    # A semicolon or brace has already ended this code line.
                    while lines and not lines[-1]:
                        lines.pop()
                    lines[-1] += " " + spelling
                else:
                    lines.append(spelling)
            else:
                flush()
                if indent == 0 and complete:
                    blank()
                    complete = False
                lines.append("    " * indent + spelling)
            previous = part
            continue
        if indent == 0 and complete:
            blank()
            complete = False
        if spelling == "{":
            flush()
            lines.append("    " * indent + "{")
            indent += 1
        elif spelling == "}":
            flush()
            indent -= 1
            lines.append("    " * indent + "}")
            complete = indent == 0
        elif spelling == ";":
            current = current.rstrip(" ") + ";"
            flush()
            complete = indent == 0
        elif spelling in {",", ":"}:
            current = current.rstrip(" ") + spelling + " "
        elif spelling == ")":
            current = current.rstrip(" ") + ")"
        elif spelling == "(":
            if previous is not None and previous.text in {"if", "return"}:
                current += " "
            current += "("
        elif spelling == "!":
            if current and not current.endswith((" ", "(", "!")):
                current += " "
            current += "!"
        elif spelling in {"=", "=>", "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}:
            current = current.rstrip(" ") + " " + spelling + " "
        else:
            if current and not current.endswith((" ", "(", "!")):
                current += " "
            current += spelling
        previous = part
    flush()
    while lines and not lines[-1]:
        lines.pop()
    return ("\n".join(lines) + "\n").encode("utf-8")


def format_source(source: bytes) -> bytes:
    """Return checked canonical bytes without mutating source or filesystem state."""
    vela.translate(source)
    tokens = vela._tokens(source)
    original = vela._Parser(tokens).parse()
    parts = _parts(source)
    result = _render(parts)
    # Checking the candidate also enforces its expanded byte and syntax bounds.
    vela.translate(result)
    candidate = vela._Parser(vela._tokens(result)).parse()
    rendered = _parts(result)
    if _fingerprint(parts) != _fingerprint(rendered) or _shape(original) != _shape(candidate):
        raise syntax.VelaError("format", 1, 1, "formatting changed tokens, comments or syntax")
    if _render(rendered) != result:
        raise syntax.VelaError("format", 1, 1, "formatting did not reach a stable layout")
    return result


def _unwrapped(value: syntax.Expression) -> syntax.Expression:
    while value.kind == "group":
        value = value.children[0]
    return value


def lint_source(source: bytes) -> tuple[Finding, ...]:
    """Report optional findings only after complete compiler acceptance."""
    facts = vela.inspect_source(source)
    module = vela._Parser(vela._tokens(source)).parse()
    findings: list[Finding] = []

    def report(code: str, message: str, site: syntax.Site) -> None:
        findings.append(Finding(code, message, site.line, site.column))

    def binding(name: syntax.Name) -> None:
        if name.text != "_" and not _BINDING.fullmatch(name.text):
            report("VELA101", f"binding '{name.text}' should use camelCase", name.site)

    def expression(value: syntax.Expression) -> None:
        if (value.kind == "binary" and value.value == "=="
                and any(_unwrapped(child).kind == "bool" for child in value.children)):
            report("VELA103", "Boolean literal comparison is redundant; prefer direct Boolean logic",
                   value.site)
        for child in value.children:
            expression(child)

    def block(value: syntax.Block) -> None:
        for local in value.bindings:
            binding(local.name)
            if isinstance(local, syntax.Binding) and not local.explicit_binding:
                report("VELA104", f"typed local '{local.name.text}' is immutable; "
                       "prefer an explicit let binding keyword", local.site)
            expression(local.value)
        terminal = value.terminal
        if isinstance(terminal, syntax.Return):
            expression(terminal.value)
        else:
            expression(terminal.condition)
            block(terminal.yes)
            block(terminal.no)

    symbols = cast("list[dict[str, object]]", facts["symbols"])
    documented = {(symbol["line"], symbol["column"]) for symbol in symbols
                  if symbol.get("documentation") is not None}
    for declaration in module.declarations:
        name = declaration.name
        if not _MEMBER.fullmatch(name.text):
            report("VELA100", f"public member '{name.text}' should use PascalCase", name.site)
        if (name.site.line, name.site.column) not in documented:
            report("VELA102", f"public member '{name.text}' should have a /// documentation comment", name.site)
        if isinstance(declaration, syntax.Function):
            for parameter, _ in declaration.parameters:
                binding(parameter)
            block(declaration.body)
        else:
            expression(declaration.value)
    return tuple(sorted(findings, key=lambda item: (item.line, item.column, item.code)))


def preview_bindings(source: bytes) -> bytes:
    """Check a candidate containing only explicit immutable-binding insertions."""
    original = vela.translate(source)
    findings = lint_source(source)
    snapshot = SourceSnapshot("vela:binding-preview", 0, syntax.source_text(source), 1)
    types = {token.site: token.text.encode("ascii") for token in vela._tokens(source)
             if token.text in {"Nat", "bool"}}
    offsets: list[int] = []
    for finding in findings:
        if finding.code != "VELA104":
            continue
        try:
            position = snapshot.diagnostic_position(finding.line, finding.column)
            offset = snapshot.position_byte_offset(position["line"], position["character"])
        except ValueError as error:
            raise syntax.VelaError("lint-preview", 1, 1,
                                   "binding insertion site is outside the checked source") from error
        spelling = types.get(syntax.Site(finding.line, finding.column))
        if spelling is None or not source.startswith(spelling, offset):
            raise syntax.VelaError("lint-preview", finding.line, finding.column,
                                   "binding insertion differs from the checked source type token")
        offsets.append(offset)
    if offsets != sorted(set(offsets)):
        raise syntax.VelaError("lint-preview", 1, 1, "binding insertion sites are not distinct and ordered")
    candidate = source
    for offset in reversed(offsets):
        candidate = candidate[:offset] + b"let " + candidate[offset:]
    checked = vela.translate(candidate)
    if original.gallina.splitlines()[2:] != checked.gallina.splitlines()[2:]:
        raise syntax.VelaError("lint-preview", 1, 1,
                               "binding preview changed the interpreted terms")
    return candidate
