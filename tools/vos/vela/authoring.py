# SPDX-License-Identifier: Apache-2.0
"""Source-preserving Vela formatting and optional compiler-owned lints.

The existing compiler owns syntax and semantic acceptance. This module only
renders its token stream and inspects its syntax and resolved declaration facts.
It performs no filesystem writes; the compiler command owns publication.
"""

import re
from dataclasses import dataclass, fields, is_dataclass
from typing import cast

from vos import vela
from vos.vela import ast as syntax
from vos.vela.source import SourceSnapshot

STYLE_VERSION = 1
LINT_CODES = frozenset({"VELA100", "VELA101", "VELA102", "VELA103", "VELA105"})
RETIRED_LINT_CODES = frozenset({"VELA104", "VELA106"})
_MEMBER = re.compile(r"[A-Z][A-Za-z0-9]*")
_BINDING = re.compile(r"[a-z][A-Za-z0-9]*")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_EFFECT_ITEM = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:\([A-Za-z0-9_., ']+\))?")
_NUMERIC_TYPES: dict[str, tuple[bool, int | str]] = {
    "u8": (False, 8), "byte": (False, 8),
    "u16": (False, 16),
    "u32": (False, 32), "uint": (False, 32),
    "u64": (False, 64), "ulong": (False, 64),
    "usize": (False, "usize"),
    "i8": (True, 8),
    "i16": (True, 16),
    "i32": (True, 32), "int": (True, 32),
    "i64": (True, 64), "long": (True, 64),
}


@dataclass(frozen=True)
class Finding:
    """An advisory finding at an original compiler source position."""

    code: str
    message: str
    line: int
    column: int


def is_pascal_case(name: str) -> bool:
    return _MEMBER.fullmatch(name) is not None


def generic_type_findings(names: tuple[syntax.Name, ...]) -> tuple[Finding, ...]:
    """Apply type naming to compiler-recorded generic type identifiers only."""
    return tuple(Finding("VELA105", f"generic type parameter '{name.text}' should use PascalCase "
                         "(for example T or TValue); value indices remain camelCase",
                         name.site.line, name.site.column)
                 for name in names if not is_pascal_case(name.text))


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


def _bare_binding_sites(source: bytes) -> tuple[syntax.Site, ...]:
    tokens = vela._tokens(source)
    sites: list[syntax.Site] = []
    for index, token in enumerate(tokens):
        if (token.text in {"Nat", "bool"}
                and index > 0 and tokens[index - 1].text in {"{", ";"}
                and index + 2 < len(tokens)
                and tokens[index + 1].kind == "name"
                and tokens[index + 2].text == "="):
            sites.append(token.site)
    return tuple(sites)


def preview_bindings(source: bytes) -> bytes:
    """Check a candidate containing only explicit immutable-binding insertions."""
    snapshot = SourceSnapshot("vela:binding-preview", 0, syntax.source_text(source), 1)
    types = {token.site: token.text.encode("ascii") for token in vela._tokens(source)
             if token.text in {"Nat", "bool"}}
    offsets: list[int] = []
    for site in _bare_binding_sites(source):
        try:
            position = snapshot.diagnostic_position(site.line, site.column)
            offset = snapshot.position_byte_offset(position["line"], position["character"])
        except ValueError as error:
            raise syntax.VelaError("lint-preview", 1, 1,
                                   "binding insertion site is outside the checked source") from error
        spelling = types.get(site)
        if spelling is None or not source.startswith(spelling, offset):
            raise syntax.VelaError("lint-preview", site.line, site.column,
                                   "binding insertion differs from the checked source type token")
        offsets.append(offset)
    if offsets != sorted(set(offsets)):
        raise syntax.VelaError("lint-preview", 1, 1, "binding insertion sites are not distinct and ordered")
    candidate = source
    for offset in reversed(offsets):
        candidate = candidate[:offset] + b"let " + candidate[offset:]
    first = vela.translate(candidate)
    checked = vela.translate(candidate)
    if first.gallina.splitlines()[2:] != checked.gallina.splitlines()[2:]:
        raise syntax.VelaError("lint-preview", 1, 1,
                               "binding preview changed the interpreted terms")
    return candidate


def assist_loan_argument(source: bytes, line: int, column: int, mode: str) -> bytes:
    """Insert an explicit in/ref/out loan modifier at a checked argument site."""
    if mode not in {"in", "ref", "out"}:
        raise syntax.VelaError("lint-preview", line, column, f"unsupported loan mode '{mode}'")
    text = syntax.source_text(source)
    snapshot = SourceSnapshot("vela:loan-assist", 0, text, 1)
    try:
        position = snapshot.diagnostic_position(line, column)
        offset = snapshot.position_byte_offset(position["line"], position["character"])
    except ValueError as error:
        raise syntax.VelaError("lint-preview", line, column, "loan argument site is outside source") from error
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    line_text = lines[line - 1]
    col0 = column - 1
    if (col0 < 0 or col0 >= len(line_text)
            or _IDENT.match(line_text, col0) is None
            or (col0 > 0 and (line_text[col0 - 1].isalnum() or line_text[col0 - 1] == "_"))):
        raise syntax.VelaError("lint-preview", line, column, "loan argument site does not start at an identifier")
    prefix = f"{mode} ".encode("ascii")
    if source.startswith(prefix, offset):
        return source
    return source[:offset] + prefix + source[offset:]


def assist_null_conditional(receiver: str, member: str) -> tuple[str, str]:
    """Return the propagation and local-match replacements for a refused ?. access."""
    rec = receiver.strip()
    mem = member.strip()
    if not rec or not _IDENT.fullmatch(mem):
        raise syntax.VelaError("lint-preview", 1, 1, "null-conditional assist requires a receiver and member")
    propagate = f"({rec}?).{mem}"
    local_match = f"match ({rec}) {{ Some(value) => value.{mem}, None => todo }}"
    return propagate, local_match


def assist_effects_clause(source: bytes, line: int, column: int, effects: tuple[str, ...]) -> bytes:
    """Insert an explicit closed effects(...) clause at a checked signature boundary."""
    cleaned: list[str] = []
    for eff in effects:
        item = eff.strip()
        if not _EFFECT_ITEM.fullmatch(item):
            raise syntax.VelaError("lint-preview", line, column, "effects assist requires valid effect items")
        cleaned.append(item)
    snapshot = SourceSnapshot("vela:effects-assist", 0, syntax.source_text(source), 1)
    try:
        position = snapshot.diagnostic_position(line, column)
        offset = snapshot.position_byte_offset(position["line"], position["character"])
    except ValueError as error:
        raise syntax.VelaError("lint-preview", line, column, "effects insertion site is outside source") from error
    ordered = tuple(sorted(set(cleaned)))
    clause = f"effects({', '.join(ordered)}) ".encode("ascii")
    return source[:offset] + clause + source[offset:]


def suggest_numeric_conversion(source_type: str, target_type: str, expression: str) -> str:
    """Suggest T.From(x) when infallibly wider or T.TryFrom(x) when range-checked."""
    expr = expression.strip()
    if (source_type not in _NUMERIC_TYPES or target_type not in _NUMERIC_TYPES
            or not expr or source_type == target_type):
        raise syntax.VelaError("lint-preview", 1, 1, "numeric conversion assist requires distinct scalar types")
    src_signed, src_width = _NUMERIC_TYPES[source_type]
    dst_signed, dst_width = _NUMERIC_TYPES[target_type]
    infallible = False
    if not src_signed and not dst_signed:
        if isinstance(src_width, int) and isinstance(dst_width, int):
            infallible = src_width <= dst_width
        elif dst_width == "usize" and isinstance(src_width, int):
            infallible = src_width <= 16
    elif src_signed and dst_signed and isinstance(src_width, int) and isinstance(dst_width, int):
        infallible = src_width <= dst_width
    elif not src_signed and dst_signed and isinstance(src_width, int) and isinstance(dst_width, int):
        infallible = src_width < dst_width
    method = "From" if infallible else "TryFrom"
    return f"{target_type}.{method}({expr})"


def assist_refusal(source: bytes, error: syntax.VelaError) -> tuple[str, ...]:
    """Produce source-bound 'assist, don't coerce' repairs for a compiler refusal."""
    text = syntax.source_text(source)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    line_text = lines[error.line - 1] if 1 <= error.line <= len(lines) else ""
    col0 = max(0, error.column - 1)
    if "null-conditional '?.'" in error.message and line_text[col0:col0 + 2] == "?.":
        before = line_text[:col0].rstrip()
        after = line_text[col0 + 2:].lstrip()
        rec_start = len(before)
        while rec_start > 0 and (before[rec_start - 1].isalnum() or before[rec_start - 1] in "_.)"):
            rec_start -= 1
        receiver = before[rec_start:].strip()
        mem_match = _IDENT.match(after)
        if receiver and mem_match is not None:
            return assist_null_conditional(receiver, mem_match.group(0))
    if "Format.Write requires an explicit ref" in error.message:
        target_col = error.column
        colon_pos = line_text.find(":", col0)
        if colon_pos != -1 and colon_pos < line_text.find(",", col0 if "," in line_text[col0:] else len(line_text)):
            after_colon = line_text[colon_pos + 1:]
            stripped = after_colon.lstrip()
            target_col = colon_pos + 2 + (len(after_colon) - len(stripped))
        try:
            repaired = assist_loan_argument(source, error.line, target_col, "ref")
        except syntax.VelaError:
            return ()
        return (repaired.decode("utf-8"),)
    return ()
