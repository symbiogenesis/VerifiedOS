# SPDX-License-Identifier: Apache-2.0
"""Independent located-AST consumers and malformed native protocol controls."""

import copy
import hashlib
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela


def _node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
    return {"kind": kind, "span": [start, end], **fields}


def _name(text: str, start: int) -> dict[str, object]:
    return {"text": text, "span": [start, start + len(text)]}


def _fixture(source: bytes, expression: dict[str, object]) -> dict[str, object]:
    """One independently selected nullary function, located in its original bytes."""
    start = source.index(b"module")
    declaration = source.index(b"public")
    result = source.index(b"Nat", declaration)
    name = source.index(b"F(", declaration)
    brace = source.index(b"{", declaration)
    terminal = source.index(b"return", brace)
    end = source.index(b"}", terminal) + 1
    function = _node("function", declaration, end, name=_name("F", name),
                     result=_node("type", result, result + 3, name="Nat"), parameters=[],
                     body=_node("block", brace, end, bindings=[],
                                exit=_node("return", terminal, source.index(b";", terminal) + 1,
                                           value=expression)))
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": _node("file", start, end, name=_name("M", start + 7), functions=[function])}


def _literal(source: bytes, spelling: bytes = b"1") -> dict[str, object]:
    start = source.index(spelling, source.index(b"return"))
    return _node("nat", start, start + len(spelling), value=spelling.decode())


def _arrow_fixture(source: bytes, expression: dict[str, object]) -> dict[str, object]:
    declaration = source.index(b"public")
    result = source.index(b"Nat", declaration)
    name = source.index(b"F(", declaration)
    arrow = source.index(b"=>", name)
    end = source.index(b";", arrow) + 1
    function = _node("function", declaration, end, name=_name("F", name),
                     result=_node("type", result, result + 3, name="Nat"), parameters=[],
                     body=_node("expression_body", arrow, end, value=expression))
    module = source.index(b"module")
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": _node("file", module, end, name=_name("M", module + 7), functions=[function])}


def _expression_body_protocol() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        source = ("// caf\u00e9".encode() + newline + b"module M; public Nat F() => // body"
                  + newline + b"  0001 // terminator" + newline + b";")
        literal = source.index(b"0001")
        tree = _arrow_fixture(source, _node("nat", literal, literal + 4, value="0001"))
        with patch.object(vela, "_tokens", side_effect=AssertionError("Python parser fallback")):
            actual = vela.translate_ast(source, tree)
        ensure(actual == vela.translate(source), "arrow body changed native/Python term agreement")
        for label in ("arrow", "terminator", "value", "field"):
            changed = copy.deepcopy(tree)
            ast = cast("dict[str, object]", changed["ast"])
            function = cast("list[dict[str, object]]", ast["functions"])[0]
            body = cast("dict[str, object]", function["body"])
            start, end = cast("list[int]", body["span"])
            if label == "arrow":
                body["span"] = [start + 1, end]
            elif label == "terminator":
                body["span"] = [start, end - 1]
            elif label == "value":
                body["value"] = _node("nat", start, start + 1, value="0")
            else:
                body["ignored"] = True
            try:
                vela.translate_ast(source, changed)
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError(f"accepted expression-body {label} corruption")
    for spelling, kind in ((b"true", "type"), (b"missing", "name")):
        source = b"module M; public Nat F() => " + spelling + b";"
        literal = source.index(spelling)
        expression = (_node("bool", literal, literal + 4, value=True) if spelling == b"true"
                      else _node("name", literal, literal + len(spelling), name=_name("missing", literal)))
        response = _arrow_fixture(source, expression)
        errors: list[tuple[str, int, int, str]] = []
        for operation in (lambda source=source: vela.translate(source),
                          lambda source=source, response=response: vela.translate_ast(source, response)):
            try:
                operation()
            except vela.VelaError as error:
                errors.append((error.kind, error.line, error.column, error.message))
        ensure(len(errors) == 2 and errors[0] == errors[1] and errors[0][0] == kind,
               "expression body changed the semantic diagnostic or its location")


def _expression_body_uncovered_tokens() -> None:
    sources = (
        (b"module M; public Nat F() => 0 + 1;", b"0"),
        (b"module M; public Nat F() => 0 + 1;", b"1"),
        (b"module M; public Nat F() => // hidden 0\n 1;", b"0"),
        (b"module M; public Nat F() => /* unsupported trivia */ 1;", b"1"),
        (b"module M; public Nat F() => \v 1;", b"1"),
    )
    for source, spelling in sources:
        start = source.index(spelling, source.index(b"=>"))
        tree = _arrow_fixture(source, _node("nat", start, start + len(spelling), value=spelling.decode()))
        try:
            vela.translate_ast(source, tree)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expression body accepted uncovered non-trivia or comment payload: {source!r}")


def _independent_translation() -> None:
    source = b"module M; public Nat F() { return 1 + 2 * 3; }"
    # These terms, source offsets and precedence are selected without invoking
    # either parser or the native decoder to construct an expected tree.
    tree = _fixture(source, _node("binary", 34, 43, operator=_name("+", 36),
                                left=_node("nat", 34, 35, value="1"),
                                right=_node("binary", 38, 43, operator=_name("*", 40),
                                            left=_node("nat", 38, 39, value="2"),
                                            right=_node("nat", 42, 43, value="3"))))
    with patch.object(vela, "_tokens", side_effect=AssertionError("Python parser fallback")):
        actual = vela.translate_ast(source, tree)
    expected_body = ("(Corelib.Init.Nat.add (1 : Corelib.Init.Datatypes.nat) "
                     "(Corelib.Init.Nat.mul (2 : Corelib.Init.Datatypes.nat) "
                     "(3 : Corelib.Init.Datatypes.nat)))")
    ensure(actual.module == "M" and f"  {expected_body}.\n" in actual.gallina,
           "native AST consumer lost precedence or changed expected pure terms")
    ensure(actual == vela.translate(source), "native and legacy syntax consumers disagree")


def _held_out_edits() -> None:
    for prefix in (b"", "// caf\u00e9\r\n".encode(), b"// comment\r"):
        for operator, operation in ((b"+", "add"), (b"*", "mul")):
            source = prefix + b"module M; public Nat F() { return 0001 " + operator + b" 2; }"
            left = source.index(b"0001")
            right = source.index(b"2;", left)
            tree = _fixture(source, _node("binary", left, right + 1,
                                        operator=_name(operator.decode(), right - 2),
                                        left=_node("nat", left, left + 4, value="0001"),
                                        right=_node("nat", right, right + 1, value="2")))
            actual = vela.translate_ast(source, tree)
            ensure(actual == vela.translate(source), "held-out edit changed consumer agreement")
            ensure(f"Corelib.Init.Nat.{operation} (1 :" in actual.gallina,
                   "held-out edit reused stale operation or decimal spelling")
            ensure(hashlib.sha256(source).hexdigest() in actual.gallina, "source binding was normalized")


def _protocol_controls() -> None:
    source = b"module M; public Nat F() { return 1; }"
    expected = _fixture(source, _literal(source))
    mutations: tuple[tuple[str, object], ...] = (
        ("unknown response field", {**expected, "extra": True}),
        ("Boolean schema", {**expected, "schema": True}),
        ("stale source binding", {**expected, "source_sha256": "0" * 64}),
        ("unsupported schema", {**expected, "schema": 2}),
        ("missing AST", {key: value for key, value in expected.items() if key != "ast"}),
    )
    for label, response in mutations:
        try:
            vela.translate_ast(source, response)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {label}")
    for label in ("field", "span", "Boolean span", "name", "literal", "kind", "empty", "child"):
        response = copy.deepcopy(expected)
        # Mutations use the fixture's known shape rather than production decoding.
        ast = cast("dict[str, object]", response["ast"])
        function = cast("dict[str, object]", cast("list[object]", ast["functions"])[0])
        terminal = cast("dict[str, object]", cast("dict[str, object]", function["body"])["exit"])
        expression = cast("dict[str, object]", terminal["value"])
        if label == "field":
            expression["ignored"] = "payload"
        elif label == "span":
            expression["span"] = [0, len(source)]
        elif label == "Boolean span":
            expression["span"] = [True, 35]
        elif label == "name":
            cast("dict[str, object]", function["name"])["text"] = "Injected."
        elif label == "literal":
            expression["value"] = "2"
        elif label == "kind":
            expression["kind"] = "effect"
        elif label == "empty":
            ast["functions"] = []
        else:
            terminal["value"] = []
        try:
            vela.translate_ast(source, response)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"accepted native {label} mutation")


def _semantic_refusals() -> None:
    for spelling, kind in ((b"true", "type"), (b"absent", "name")):
        for newline in (b"\n", b"\r\n", b"\r"):
            source = "// caf\u00e9".encode() + newline + b"module M;" + newline + b"public Nat F() { return " + spelling + b"; }"
            offset = source.index(spelling)
            expression = (_node("bool", offset, offset + len(spelling), value=True)
                          if spelling == b"true" else
                          _node("name", offset, offset + len(spelling), name=_name("absent", offset)))
            response = _fixture(source, expression)
            errors: list[tuple[str, int, int, str]] = []
            for native in (False, True):
                try:
                    if native:
                        vela.translate_ast(source, response)
                    else:
                        vela.translate(source)
                except vela.VelaError as error:
                    errors.append((error.kind, error.line, error.column, error.message))
                else:
                    raise AssertionError("native syntax bypassed semantic rejection")
            ensure(errors[0] == errors[1] and errors[0][0] == kind,
                   f"native semantic diagnostic changed: {errors}")


def _resource_boundaries() -> None:
    for count in (63, 64, 300):
        prefix = b"module M; public Nat F() { return "
        source = prefix + b"(" * count + b"0" + b")" * count + b"; }"
        start = len(prefix) + count
        expression = _node("nat", start, start + 1, value="0")
        for index in range(count):
            expression = _node("group", start - index - 1, start + index + 2, value=expression)
        response = _fixture(source, expression)
        try:
            actual = vela.translate_ast(source, response)
        except vela.VelaError as error:
            ensure(count >= 64 and error.kind == "limit", "wrong native group-depth refusal")
        else:
            ensure(count == 63 and actual == vela.translate(source), "native grouping boundary changed")
    # Source bytes are bounded before a forged AST can reach a recursive reader.
    try:
        vela.translate_ast(b" " * (vela.MAX_SOURCE_BYTES + 1), {})
    except vela.VelaError as error:
        ensure(error.kind == "limit", "oversized AST source has wrong refusal")
    else:
        raise AssertionError("oversized source accepted through native consumer")


def _named_call_tree(source: bytes) -> dict[str, object]:
    first = source.index(b"public")
    first_name = source.index(b"A(", first)
    parameter = source.index(b"Nat value", first_name)
    first_arrow = source.index(b"=>", parameter)
    first_end = source.index(b";", first_arrow) + 1
    first_value = source.index(b"value", first_arrow)
    declaration = _node("function", first, first_end, name=_name("A", first_name),
                        result=_node("type", first + 7, first + 10, name="Nat"),
                        parameters=[_node("parameter", parameter, parameter + 9,
                                          name=_name("value", parameter + 4),
                                          type=_node("type", parameter, parameter + 3, name="Nat"))],
                        body=_node("expression_body", first_arrow, first_end,
                                   value=_node("name", first_value, first_value + 5,
                                               name=_name("value", first_value))))
    second = source.index(b"public", first_end)
    second_name = source.index(b"F(", second)
    second_arrow = source.index(b"=>", second_name)
    call = source.index(b"A(", second_arrow)
    label = source.index(b"value", call)
    literal = source.index(b"1", label)
    argument = _node("argument", label, literal + 1, label=_name("value", label),
                     value=_node("nat", literal, literal + 1, value="1"))
    function = _node("function", second, len(source), name=_name("F", second_name),
                     result=_node("type", second + 7, second + 10, name="Nat"), parameters=[],
                     body=_node("expression_body", second_arrow, len(source),
                                value=_node("call", call, source.index(b")", literal) + 1,
                                            callee=_name("A", call), arguments=[argument])))
    module = source.index(b"module")
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": _node("file", module, len(source), name=_name("M", module + 7),
                         functions=[declaration, function])}


def _located_named_arguments() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        source = ("// café".encode() + newline
                  + b"module M; public Nat A(Nat value) => value; public Nat F() => A(value: 1);")
        tree = _named_call_tree(source)
        with patch.object(vela, "_tokens", side_effect=AssertionError("Python parsing fallback")):
            actual = vela.translate_ast(source, tree)
        ensure(actual == vela.translate(source), "native label changed the independently parsed application")
        for corruption in ("name", "erased-label", "narrowed-wrapper", "separator", "stale-source"):
            response = copy.deepcopy(tree)
            ast = cast("dict[str, object]", response["ast"])
            functions = cast("list[dict[str, object]]", ast["functions"])
            body = cast("dict[str, object]", functions[1]["body"])
            call = cast("dict[str, object]", body["value"])
            argument = cast("list[dict[str, object]]", call["arguments"])[0]
            if corruption == "name":
                cast("dict[str, object]", argument["label"])["text"] = "other"
            elif corruption in {"erased-label", "narrowed-wrapper"}:
                argument["label"] = None
                if corruption == "narrowed-wrapper":
                    argument["span"] = cast("dict[str, object]", argument["value"])["span"]
            elif corruption == "separator":
                call["arguments"] = []
            else:
                response["source_sha256"] = "0" * 64
            try:
                vela.translate_ast(source, response)
            except (ValueError, TypeError):
                pass
            else:
                raise AssertionError(f"accepted named-argument {corruption} corruption")


def cases() -> list[Case]:
    return [Case("independent-located-ast-to-terms", _independent_translation),
            Case("expression-body-source-binding-and-terms", _expression_body_protocol),
            Case("expression-body-complete-token-coverage", _expression_body_uncovered_tokens),
            Case("located-labels-and-complete-call-token-coverage", _located_named_arguments),
            Case("held-out-source-edits", _held_out_edits),
            Case("strict-native-schema-and-provenance", _protocol_controls),
            Case("native-semantic-diagnostics", _semantic_refusals),
            Case("native-resource-boundaries", _resource_boundaries)]
