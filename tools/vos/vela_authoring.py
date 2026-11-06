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
from vos import vela_ast as syntax
from vos.vela_source import SourceSnapshot

STYLE_VERSION = 1
LINT_CODES = frozenset({"VELA100", "VELA101", "VELA102", "VELA103", "VELA104", "VELA105", "VELA106"})
_MEMBER = re.compile(r"[A-Z][A-Za-z0-9]*")
_BINDING = re.compile(r"[a-z][A-Za-z0-9]*")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_EFFECT_ITEM = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:\([A-Za-z0-9_., ']+\))?")
_NULLARY_CONSTRUCTORS = frozenset({"None", "EmptyBuilder", "VNil", "FZero"})
_ARITY_CONSTRUCTORS = frozenset({"Some", "Ok", "Err", "Succ", "VCons", "FSucc"})
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


@dataclass(frozen=True)
class _NormPat:
    kind: str
    value: bool | str = False
    args: tuple[_NormPat, ...] = ()


def _unwrap_pattern(node: dict[str, object]) -> dict[str, object]:
    while node.get("kind") == "group_pattern" and isinstance(node.get("pattern"), dict):
        node = cast("dict[str, object]", node["pattern"])
    if node.get("kind") == "labeled_pattern" and isinstance(node.get("pattern"), dict):
        return _unwrap_pattern(cast("dict[str, object]", node["pattern"]))
    return node


def _normalize_pattern(node: dict[str, object]) -> _NormPat:
    node = _unwrap_pattern(node)
    kind = node.get("kind")
    if kind in {"wildcard_pattern", "binding_pattern"}:
        return _NormPat("wild")
    if kind == "unit_pattern":
        return _NormPat("unit")
    if kind == "bool_pattern":
        return _NormPat("bool", bool(node.get("value")))
    if kind == "nat_pattern":
        amount = int(str(node.get("value", "0")).replace("_", ""))
        result = _NormPat("zero")
        for _ in range(min(amount, 65)):
            result = _NormPat("succ", args=(result,))
        return result
    if kind == "tuple_pattern":
        raw_items = node.get("patterns", [])
        items = [
            _normalize_pattern(cast("dict[str, object]", item))
            for item in (raw_items if isinstance(raw_items, list) else [])
            if isinstance(item, dict)
        ]
        if len(items) < 2:
            return _NormPat("wild")
        result = items[-1]
        for item in reversed(items[:-1]):
            result = _NormPat("pair", args=(item, result))
        return result
    if kind == "constructor_pattern":
        cname = cast("str", cast("dict[str, object]", node["name"])["text"])
        raw_args = node.get("arguments", [])
        args = tuple(
            _normalize_pattern(cast("dict[str, object]", arg))
            for arg in (raw_args if isinstance(raw_args, list) else [])
            if isinstance(arg, dict)
        )
        if cname == "Succ" and len(args) == 1:
            return _NormPat("succ", args=args)
        return _NormPat("ctor", cname, args)
    return _NormPat("wild")


def _specialize_norm(
    matrix: list[tuple[_NormPat, ...]], head_kind: str, head_val: bool | str, arity: int
) -> list[tuple[_NormPat, ...]]:
    specialized: list[tuple[_NormPat, ...]] = []
    for row in matrix:
        first, rest = row[0], row[1:]
        if first.kind == "wild":
            specialized.append((_NormPat("wild"),) * arity + rest)
        elif first.kind == head_kind and first.value == head_val and len(first.args) == arity:
            specialized.append(first.args + rest)
    return specialized


def _is_pattern_row_useful(
    matrix: list[tuple[_NormPat, ...]],
    row: tuple[_NormPat, ...],
    record_arities: dict[str, int],
) -> bool:
    if not row:
        return len(matrix) == 0
    first, rest = row[0], row[1:]
    if first.kind != "wild":
        return _is_pattern_row_useful(
            _specialize_norm(matrix, first.kind, first.value, len(first.args)),
            first.args + rest,
            record_arities,
        )
    heads = {(r[0].kind, r[0].value, len(r[0].args)) for r in matrix if r[0].kind != "wild"}
    complete_sig: list[tuple[str, bool | str, int]] | None = None
    if ("unit", False, 0) in heads:
        complete_sig = [("unit", False, 0)]
    elif {("bool", True, 0), ("bool", False, 0)} <= heads:
        complete_sig = [("bool", True, 0), ("bool", False, 0)]
    elif {("zero", False, 0), ("succ", False, 1)} <= heads:
        complete_sig = [("zero", False, 0), ("succ", False, 1)]
    elif ("pair", False, 2) in heads:
        complete_sig = [("pair", False, 2)]
    else:
        for hk, hv, harity in heads:
            if hk == "ctor" and isinstance(hv, str) and record_arities.get(hv) == harity:
                complete_sig = [(hk, hv, harity)]
                break
    if complete_sig is not None:
        return any(
            _is_pattern_row_useful(
                _specialize_norm(matrix, hk, hv, harity),
                (_NormPat("wild"),) * harity + rest,
                record_arities,
            )
            for hk, hv, harity in complete_sig
        )
    wild_matrix = [r[1:] for r in matrix if r[0].kind == "wild"]
    return _is_pattern_row_useful(wild_matrix, rest, record_arities)


def _in_scope_constructors(ast: dict[str, object]) -> tuple[set[str], set[str], dict[str, int]]:
    nullary = set(_NULLARY_CONSTRUCTORS)
    all_ctors = set(_NULLARY_CONSTRUCTORS | _ARITY_CONSTRUCTORS)
    record_arities: dict[str, int] = {}
    declarations = ast.get("declarations", [])
    if isinstance(declarations, list):
        for decl in declarations:
            if not isinstance(decl, dict):
                continue
            if decl.get("kind") == "record":
                name_node = decl.get("name")
                if isinstance(name_node, dict) and isinstance(name_node.get("text"), str):
                    rname = name_node["text"]
                    params = decl.get("parameters", [])
                    arity = len(params) if isinstance(params, list) else 0
                    record_arities[rname] = arity
                    all_ctors.add(rname)
                    if arity == 0:
                        nullary.add(rname)
            elif decl.get("kind") == "union":
                cases = decl.get("cases", [])
                if isinstance(cases, list):
                    for case_node in cases:
                        if not isinstance(case_node, dict):
                            continue
                        cname_node = case_node.get("name")
                        if isinstance(cname_node, dict) and isinstance(cname_node.get("text"), str):
                            cname = cname_node["text"]
                            cparams = case_node.get("parameters", [])
                            all_ctors.add(cname)
                            if isinstance(cparams, list) and not cparams:
                                nullary.add(cname)
    return nullary, all_ctors, record_arities


def pattern_constructor_findings(source: bytes, ast: dict[str, object]) -> tuple[Finding, ...]:
    """Warn on bare pattern binders shadowing constructors or unreachable match arms."""
    _, all_ctors, record_arities = _in_scope_constructors(ast)
    by_offset: dict[int, Finding] = {}
    pending: list[object] = [ast]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            kind = item.get("kind")
            if kind == "binding_pattern":
                identifier = cast("dict[str, object]", item["name"])
                spelling = cast("str", identifier["text"])
                if spelling in all_ctors:
                    offset = cast("list[int]", identifier["span"])[0]
                    site = syntax.position(source[:offset].decode("utf-8"))
                    by_offset[offset] = Finding(
                        "VELA106",
                        f"bare pattern binder '{spelling}' binds a variable and shadows constructor "
                        f"'{spelling}'; write '{spelling}()'",
                        site.line,
                        site.column,
                    )
            elif kind in {"match", "match_expression"}:
                cases = item.get("cases", [])
                if isinstance(cases, list):
                    prior_rows: list[tuple[_NormPat, ...]] = []
                    catchall_binder: str | None = None
                    for arm in cases:
                        if not isinstance(arm, dict) or not isinstance(arm.get("pattern"), dict):
                            continue
                        pat_node = cast("dict[str, object]", arm["pattern"])
                        norm = _normalize_pattern(pat_node)
                        if not _is_pattern_row_useful(prior_rows, (norm,), record_arities):
                            offset = cast("list[int]", pat_node["span"])[0]
                            if offset not in by_offset:
                                site = syntax.position(source[:offset].decode("utf-8"))
                                message = (
                                    f"unreachable match arm after bare pattern binder "
                                    f"'{catchall_binder}'; write '{catchall_binder}()' to match a constructor"
                                    if catchall_binder is not None
                                    else "unreachable match arm; earlier patterns already cover this case"
                                )
                                by_offset[offset] = Finding("VELA106", message, site.line, site.column)
                        prior_rows.append((norm,))
                        unwrapped = _unwrap_pattern(pat_node)
                        if unwrapped.get("kind") == "binding_pattern" and catchall_binder is None:
                            catchall_binder = cast(
                                "str", cast("dict[str, object]", unwrapped["name"])["text"]
                            )
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return tuple(sorted(by_offset.values(), key=lambda item: (item.line, item.column, item.code)))


def preview_pattern_constructors(source: bytes, parsed: object) -> bytes:
    """Return a source-preserving candidate inserting () on bare nullary constructor patterns."""
    syntax.source_text(source)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("ast"), dict):
        raise syntax.VelaError("lint-preview", 1, 1, "pattern preview requires a validated syntax tree")
    ast = cast("dict[str, object]", parsed["ast"])
    nullary, _, _ = _in_scope_constructors(ast)
    insertions: list[tuple[int, int, str]] = []
    pending: list[object] = [ast]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("kind") == "binding_pattern" and isinstance(item.get("name"), dict):
                identifier = cast("dict[str, object]", item["name"])
                spelling = identifier.get("text")
                span = identifier.get("span")
                if (isinstance(spelling, str) and spelling in nullary
                        and isinstance(span, list) and len(span) == 2
                        and type(span[0]) is int and type(span[1]) is int):
                    insertions.append((span[0], span[1], spelling))
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    insertions.sort(key=lambda entry: entry[0])
    for idx, (start, end, spelling) in enumerate(insertions):
        encoded = spelling.encode("utf-8")
        if start < 0 or end > len(source) or source[start:end] != encoded:
            site = syntax.position(source[:max(start, 0)].decode("utf-8", errors="ignore"))
            raise syntax.VelaError(
                "lint-preview", site.line, site.column,
                "pattern constructor preview span differs from source token",
            )
        if idx and start < insertions[idx - 1][1]:
            raise syntax.VelaError("lint-preview", 1, 1, "overlapping pattern constructor spans")
    candidate = source
    for _, end, _ in reversed(insertions):
        candidate = candidate[:end] + b"()" + candidate[end:]
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
    local_match = f"match ({rec}) {{ Some(value) => value.{mem}, None() => todo }}"
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
