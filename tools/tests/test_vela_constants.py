# SPDX-License-Identifier: Apache-2.0
"""Required-static values, dependency refusals and independent source bindings."""

import copy
import hashlib
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela


def _refuses(source: str, kind: str, fragment: str = "") -> vela.VelaError:
    try:
        vela.translate(source.encode())
    except vela.VelaError as error:
        ensure(error.kind == kind and fragment in error.message,
               f"constant refusal differs: {error.kind}: {error.message}")
        return error
    raise AssertionError(f"accepted forbidden constant: {source}")


def _evaluated_values() -> None:
    source = b"""module Static;
public const Nat Base = 0002;
public Nat Calculate(Nat value) {
    let square = value * value;
    if (square <= 4) { let nextValue = square + 1; return nextValue; }
    else { return square; }
}
public const Nat Limit = Calculate(value: Base) + 11;
public const bool Ready = Limit == 16;
public Nat Read() { const Nat Local = Limit + 1; return Local; }
"""
    result = vela.translate(source).gallina
    for expected in ("Definition c_Base : Corelib.Init.Datatypes.nat :=\n  (2 :",
                     "Definition c_Limit : Corelib.Init.Datatypes.nat :=\n  (16 :",
                     "Definition c_Ready : Corelib.Init.Datatypes.bool :=\n  Corelib.Init.Datatypes.true.",
                     "(let v_Local := (17 : Corelib.Init.Datatypes.nat) in v_Local)"):
        ensure(expected in result, f"constant did not emit its independently expected value: {expected}")
    ensure("f_Calculate" not in result.split("Definition c_Limit", 1)[1].split(".", 1)[0],
           "constant initializer was emitted as a runtime function call")
    ensure(result.index("Definition c_Base") < result.index("Definition f_Calculate")
           < result.index("Definition c_Limit"), "constant/function declaration order changed")
    only = vela.translate(b"module M; public const bool Ready = false;").gallina
    ensure("Definition c_Ready" in only and "Datatypes.false" in only,
           "const-only module was refused or its false value lost")


def _static_dependencies() -> None:
    prefix = "module M; public Nat Ignore(Nat value) => 0; "
    for body in ("const Nat Limit = runtime; return Limit;",
                 "const Nat Limit = Ignore(value: runtime); return Limit;",
                 "let saved = 1; const Nat Limit = saved; return Limit;",
                 "if (false) { const Nat Limit = runtime; return Limit; } else { return 0; }"):
        error = _refuses(prefix + "public Nat Use(Nat runtime) { " + body + " }", "unsupported", "runtime binding")
        ensure(error.column > 1, "runtime constant dependency has no identifier location")
    _refuses("module M; public const Nat Limit = 1; public Nat Use(Nat Limit) { "
             "const Nat Copy = Limit; return Copy; }", "unsupported", "runtime binding 'Limit'")
    for source in ("public const Nat A = B; public const Nat B = 1;",
                   "public const Nat A = A;", "public const Nat A = Missing(value: 1);",
                   "public const Nat A = Later(); public Nat Later() => 1;"):
        _refuses("module M; " + source, "name")
    _refuses("module M; public Nat Use(ghost Nat erased) { const Nat N = erased; return N; }",
             "unsupported", "ghost")


def _types_arity_and_immutability() -> None:
    _refuses("module M; public const bool Ready = 1;", "type", "must be bool")
    _refuses("module M; public const Nat Limit = true;", "type", "must be Nat")
    _refuses("module M; public const Nat Limit = 1; public Nat Read() => Limit();",
             "type", "cannot be called")
    _refuses("module M; public Nat Read() { const Nat Limit = 1; Limit = 2; return Limit; }",
             "unsupported", "const 'Limit'")
    _refuses("module M; public const Nat Limit = 1; public Nat Read() { Limit = 2; return Limit; }",
             "unsupported", "const 'Limit'")
    for source in ("public const Limit = 1;", "public const Nat Limit;", "public const Nat Limit = ;"):
        _refuses("module M; " + source, "syntax")
    _refuses("module M; public const Nat Limit = 1; public const Nat Limit = 2;", "name", "duplicate")


def _bounded_evaluation() -> None:
    maximum = "9" * vela.MAX_LITERAL_DIGITS
    _refuses(f"module M; public const Nat Large = {maximum} * 2;", "limit", "decimal digits")
    source = "module M; public const Nat Value = 1 + 2;"
    with patch.object(vela, "MAX_STATIC_WORK", 2):
        _refuses(source, "limit", "budget")
    with patch.object(vela, "MAX_STATIC_DEPTH", 0):
        _refuses(source, "limit", "budget")
    with patch.object(vela, "MAX_OUTPUT_BYTES", 32):
        _refuses(source, "limit", "output")
    declarations = ["public Nat F0(Nat x) => x;"]
    declarations.extend(f"public Nat F{index}(Nat x) => F{index - 1}(x) + F{index - 1}(x);"
                        for index in range(1, 16))
    _refuses("module M; " + " ".join(declarations) + " public const Nat Limited = F15(0);", "limit", "budget")


def _constant_facts() -> None:
    source = b"module M; public const Nat Limit = 2 * 8; public const bool Ready = Limit == 16; " \
             b"public Nat Read() { const Nat Local = Limit + 1; return Local; }"
    facts = vela.inspect_source(source)
    symbols = cast("list[dict[str, object]]", facts["symbols"])
    expected = {"Limit": "const Nat Limit = 16", "Ready": "const bool Ready = true", "Local": "const Nat Local = 17"}
    for name, detail in expected.items():
        selected = next(item for item in symbols if item["name"] == name)
        ensure(selected["kind"] == "constant" and selected["detail"] == detail,
               "constant was flattened into an ordinary inferred variable fact")
    occurrences = cast("list[dict[str, object]]", facts["occurrences"])
    limit = next(index for index, item in enumerate(symbols) if item["name"] == "Limit")
    ensure(sum(item["symbol"] == limit for item in occurrences) == 3,
           "constant dependency references were omitted or repeated during evaluation")


def _constant_tree(source: bytes) -> dict[str, object]:
    def node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
        return {"kind": kind, "span": [start, end], **fields}
    def name(text: str, start: int) -> dict[str, object]:
        return {"text": text, "span": [start, start + len(text)]}
    module = source.index(b"module")
    declaration = source.index(b"public")
    annotation = source.index(b"Nat", declaration)
    binder = source.index(b"Limit", annotation)
    first = source.index(b"2", binder)
    second = source.index(b"3", first)
    third = source.index(b"4", second)
    expression = node("binary", first, third + 1, operator=name("+", source.index(b"+", first)),
                      left=node("nat", first, first + 1, value="2"),
                      right=node("binary", second, third + 1, operator=name("*", source.index(b"*", second)),
                                 left=node("nat", second, second + 1, value="3"),
                                 right=node("nat", third, third + 1, value="4")))
    constant = node("constant", declaration, len(source), name=name("Limit", binder),
                    type=node("type", annotation, annotation + 3, name="Nat"), value=expression)
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": node("file", module, len(source), name=name("M", module + 7), declarations=[constant])}


def _independent_constant_ast() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        source = "// café".encode() + newline + b"module M; public const Nat Limit = 2 + 3 * 4;"
        response = _constant_tree(source)
        with patch.object(vela, "_tokens", side_effect=AssertionError("Python parser fallback")):
            actual = vela.translate_ast(source, response)
        ensure(actual == vela.translate(source) and "(14 : Corelib.Init.Datatypes.nat)" in actual.gallina,
               "independent const AST did not evaluate to fourteen in both pure routes")
        for corruption in ("type", "value", "keyword", "truncated-initializer", "legacy-field", "source"):
            changed = copy.deepcopy(response)
            ast = cast("dict[str, object]", changed["ast"])
            constant = cast("list[dict[str, object]]", ast["declarations"])[0]
            if corruption == "type":
                cast("dict[str, object]", constant["type"])["name"] = "bool"
            elif corruption == "value":
                value = cast("dict[str, object]", constant["value"])
                cast("dict[str, object]", value["left"])["value"] = "9"
            elif corruption == "keyword":
                constant["span"] = [source.index(b"Nat"), len(source)]
            elif corruption == "truncated-initializer":
                constant["value"] = cast("dict[str, object]", constant["value"])["left"]
            elif corruption == "legacy-field":
                ast["functions"] = ast.pop("declarations")
            else:
                changed["source_sha256"] = "0" * 64
            try:
                vela.translate_ast(source, changed)
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError(f"accepted constant source/protocol {corruption} corruption")


def _complete_source_order() -> None:
    def name(text: str, start: int) -> dict[str, object]:
        return {"text": text, "span": [start, start + len(text)]}
    def node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
        return {"kind": kind, "span": [start, end], **fields}
    base = b"module M; public const Nat Limit = 2 + 3 * 4;"
    source = base + b" public const Nat NextValue = Limit;"
    response = _constant_tree(base)
    response["source_sha256"] = hashlib.sha256(source).hexdigest()
    ast = cast("dict[str, object]", response["ast"])
    ast["span"] = [0, len(source)]
    start = source.index(b"public", len(base))
    annotation = source.index(b"Nat", start)
    binder = source.index(b"NextValue", annotation)
    value = source.index(b"Limit", binder)
    declarations = cast("list[dict[str, object]]", ast["declarations"])
    declarations.append(node("constant", start, len(source), name=name("NextValue", binder),
                             type=node("type", annotation, annotation + 3, name="Nat"),
                             value=node("name", value, value + 5, name=name("Limit", value))))
    ensure(vela.translate_ast(source, response) == vela.translate(source), "ordered constant fixture changed")
    for selection in (declarations[:1], declarations[1:], list(reversed(declarations))):
        changed = copy.deepcopy(response)
        cast("dict[str, object]", changed["ast"])["declarations"] = selection
        try:
            vela.translate_ast(source, changed)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted skipped or reordered module constants")
    source = b"module M; public Nat Read() { const Nat Limit = 2 + 3 * 4; const Nat Hidden = 0; return Limit; }"
    expression = cast("list[dict[str, object]]", cast("dict[str, object]", _constant_tree(source)["ast"])["declarations"])[0]["value"]
    bindings: list[dict[str, object]] = []
    for spelling, initializer in (("Limit", expression), ("Hidden", None)):
        start = source.index(b"const Nat " + spelling.encode())
        annotation, binder = start + 6, start + 10
        end = source.index(b";", binder) + 1
        zero = source.index(b"0", binder) if initializer is None else 0
        bindings.append(node("constant_local", start, end, name=name(spelling, binder),
                             type=node("type", annotation, annotation + 3, name="Nat"),
                             value=node("nat", zero, zero + 1, value="0") if initializer is None else initializer))
    terminal = source.index(b"return")
    result = source.index(b"Limit", terminal)
    body = node("block", source.index(b"{"), len(source), bindings=bindings,
                exit=node("return", terminal, source.index(b";", terminal) + 1,
                          value=node("name", result, result + 5, name=name("Limit", result))))
    declaration = source.index(b"public")
    function = node("function", declaration, len(source), name=name("Read", source.index(b"Read")),
                    result=node("type", declaration + 7, declaration + 10, name="Nat"), parameters=[], body=body)
    response = {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
                "ast": node("file", 0, len(source), name=name("M", 7), declarations=[function])}
    ensure(vela.translate_ast(source, response) == vela.translate(source), "local constant source fixture changed")
    for selection in (bindings[:1], bindings[1:], list(reversed(bindings))):
        changed = copy.deepcopy(response)
        changed_ast = cast("dict[str, object]", changed["ast"])
        changed_function = cast("list[dict[str, object]]", changed_ast["declarations"])[0]
        cast("dict[str, object]", changed_function["body"])["bindings"] = selection
        try:
            vela.translate_ast(source, changed)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted skipped or reordered local constants")


def _lexical_token_boundaries() -> None:
    source = b"module M; public const Nat Limit = 2 + 3 * 4;"
    original = _constant_tree(source)
    for marker in (b"module M", b"public const", b"const Nat", b"Nat Limit"):
        removed = source.index(marker) + marker.index(b" ")
        edited = source[:removed] + source[removed + 1:]
        changed = copy.deepcopy(original)
        def relocate(value: object, boundary: int = removed) -> None:
            if isinstance(value, dict):
                if "span" in value:
                    value["span"] = [offset - (offset > boundary) for offset in value["span"]]
                for child in value.values():
                    relocate(child, boundary)
            elif isinstance(value, list):
                for child in value:
                    relocate(child, boundary)
        relocate(changed)
        changed["source_sha256"] = hashlib.sha256(edited).hexdigest()
        try:
            vela.translate_ast(edited, changed)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted lexical token split at {marker!r}")


def _inflated_neighbor_cannot_hide_runtime_shadow() -> None:
    def name(text: str, start: int) -> dict[str, object]:
        return {"text": text, "span": [start, start + len(text)]}
    def node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
        return {"kind": kind, "span": [start, end], **fields}
    base = b"module M; public const Nat Limit = 2 + 3 * 4;"
    source = base + b" public Nat Read() { let saved = 0; let Limit = 1; const Nat Copy = Limit; return Copy; }"
    response = _constant_tree(base)
    response["source_sha256"] = hashlib.sha256(source).hexdigest()
    ast = cast("dict[str, object]", response["ast"])
    ast["span"] = [0, len(source)]
    statement = source.index(b"let saved")
    zero = source.index(b"0", statement)
    hidden = source.index(b"let Limit", zero)
    hidden_end = source.index(b";", hidden) + 1
    local = source.index(b"const Nat Copy", hidden)
    local_name = source.index(b"Copy", local)
    local_value = source.index(b"Limit", local_name)
    terminal = source.index(b"return", local)
    returned = source.index(b"Copy", terminal)
    # The omitted ordinary binding would shadow the global constant at the next
    # initializer. Widening its neighbor must not make that input look static.
    saved = node("let", statement, hidden_end, name=name("saved", statement + 4),
                 value=node("nat", zero, zero + 1, value="0"))
    constant = node("constant_local", local, source.index(b";", local) + 1,
                    name=name("Copy", local_name), type=node("type", local + 6, local + 9, name="Nat"),
                    value=node("name", local_value, local_value + 5, name=name("Limit", local_value)))
    body = node("block", source.index(b"{", len(base)), len(source), bindings=[saved, constant],
                exit=node("return", terminal, source.index(b";", terminal) + 1,
                          value=node("name", returned, returned + 4, name=name("Copy", returned))))
    start = source.index(b"public", len(base))
    function = node("function", start, len(source), name=name("Read", source.index(b"Read", start)),
                    result=node("type", start + 7, start + 10, name="Nat"), parameters=[], body=body)
    cast("list[dict[str, object]]", ast["declarations"]).append(function)
    _refuses(source.decode(), "unsupported", "runtime binding 'Limit'")
    for inflate_value in (False, True):
        changed = copy.deepcopy(response)
        if inflate_value:
            changed_ast = cast("dict[str, object]", changed["ast"])
            changed_function = cast("list[dict[str, object]]", changed_ast["declarations"])[1]
            changed_body = cast("dict[str, object]", changed_function["body"])
            changed_saved = cast("list[dict[str, object]]", changed_body["bindings"])[0]
            cast("dict[str, object]", changed_saved["value"])["span"] = [zero, hidden_end - 1]
        try:
            vela.translate_ast(source, changed)
        except ValueError:
            pass
        else:
            raise AssertionError("inflated neighboring binding hid a runtime constant dependency")


def cases() -> list[Case]:
    return [Case("evaluated-scalars-and-pure-function-locals", _evaluated_values),
            Case("runtime-forward-cyclic-and-erased-dependencies", _static_dependencies),
            Case("constant-types-source-arity-and-immutability", _types_arity_and_immutability),
            Case("finite-static-evaluation-budgets", _bounded_evaluation),
            Case("constant-symbols-and-source-dependency-identities", _constant_facts),
            Case("complete-module-and-local-constant-source-order", _complete_source_order),
            Case("identifier-keyword-and-type-lexical-token-boundaries", _lexical_token_boundaries),
            Case("inflated-neighbor-cannot-hide-runtime-shadow", _inflated_neighbor_cannot_hide_runtime_shadow),
            Case("independent-constant-ast-values-and-source-binding", _independent_constant_ast)]
