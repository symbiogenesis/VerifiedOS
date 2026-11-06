# SPDX-License-Identifier: Apache-2.0
"""Independent located-AST consumers and malformed native protocol controls."""

import copy
import hashlib
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela
from vos.vela import ast as vela_ast


def _node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
    return {"kind": kind, "span": [start, end], **fields}


def _name(text: str, start: int) -> dict[str, object]:
    return {"text": text, "span": [start, start + len(text)]}


def _fixture(source: bytes, expression: dict[str, object], *, value_type: str = "Nat") -> dict[str, object]:
    """One independently selected nullary function, located in its original bytes."""
    start = source.index(b"module")
    declaration = source.index(b"public")
    result = source.index(value_type.encode(), declaration)
    name = source.index(b"F(", declaration)
    brace = source.index(b"{", declaration)
    terminal = source.index(b"return", brace)
    end = source.index(b"}", terminal) + 1
    function = _node("function", declaration, end, name=_name("F", name),
                     result=_node("type", result, result + len(value_type), name=value_type), parameters=[],
                     body=_node("block", brace, end, bindings=[],
                                exit=_node("return", terminal, source.index(b";", terminal) + 1,
                                           value=expression)))
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": _node("file", start, end, name=_name("M", start + 7), declarations=[function])}


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
            "ast": _node("file", module, end, name=_name("M", module + 7), declarations=[function])}


def _typed_local_protocol() -> None:
    for explicit in (False, True):
        for newline in (b"\n", b"\r\n", b"\r"):
            prefix = b"let Nat" if explicit else b"Nat"
            source = (b"module M; public Nat F() {" + newline + b"  " + prefix
                      + b" value = 1;" + newline + b"  return value;" + newline + b"}")
            returned = source.index(b"value", source.index(b"return"))
            tree = _fixture(source, _node("name", returned, returned + 5, name=_name("value", returned)))
            local = source.index(prefix, source.index(b"{"))
            annotation = source.index(b"Nat", local)
            name = source.index(b"value", annotation)
            literal = source.index(b"1", name)
            binding = _node("let" if explicit else "typed_local", local, source.index(b";", local) + 1,
                            name=_name("value", name), type=_node("type", annotation, annotation + 3, name="Nat"),
                            value=_node("nat", literal, literal + 1, value="1"))
            root = cast("dict[str, object]", tree["ast"])
            function = cast("list[dict[str, object]]", root["declarations"])[0]
            body = cast("dict[str, object]", function["body"])
            body["bindings"] = [binding]
            decoded = vela_ast.decode(source, tree)
            declaration = decoded.declarations[0]
            if not isinstance(declaration, vela_ast.Function):
                raise TypeError("typed-local fixture lost its function")
            selected = declaration.body.bindings[0]
            ensure(isinstance(selected, vela_ast.Binding) and selected.annotation == "Nat"
                   and selected.explicit_binding is explicit,
                   "native decoder lost the local annotation or source binding keyword")
            with patch.object(vela, "_tokens", side_effect=AssertionError("Python parser fallback")):
                ensure("Definition f_F" in vela.translate_ast(source, tree).gallina,
                       "a typed native binding failed its separate AST consumer")
            for mutation in ("missing-type", "wrong-type-span", "wrong-kind", "null-type"):
                changed = copy.deepcopy(tree)
                changed_root = cast("dict[str, object]", changed["ast"])
                changed_function = cast("list[dict[str, object]]", changed_root["declarations"])[0]
                changed_body = cast("dict[str, object]", changed_function["body"])
                changed_binding = cast("list[dict[str, object]]", changed_body["bindings"])[0]
                if mutation == "missing-type":
                    del changed_binding["type"]
                elif mutation == "wrong-type-span":
                    cast("dict[str, object]", changed_binding["type"])["span"] = [name, name + 3]
                elif mutation == "wrong-kind":
                    changed_binding["kind"] = "typed_local" if explicit else "let"
                else:
                    changed_binding["type"] = None
                try:
                    vela_ast.decode(source, changed)
                except (TypeError, ValueError):
                    pass
                else:
                    raise AssertionError(f"native decoder accepted a {mutation} annotation forgery")


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
            function = cast("list[dict[str, object]]", ast["declarations"])[0]
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


def _extended_operator_protocol() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        for operator in (b"-", b"!=", b"<", b">", b">=", b"&&", b"||"):
            boolean = operator in {b"&&", b"||"}
            left_text, right_text = (b"true", b"false") if boolean else (b"3", b"2")
            result_type = "Nat" if operator == b"-" else "bool"
            source = ("// café".encode() + newline + b"module M; public " + result_type.encode()
                      + b" F() { return " + left_text + b" " + operator + b" // operator trivia"
                      + newline + right_text + b"; }")
            left = source.index(left_text, source.index(b"return"))
            op = left + len(left_text) + 1
            right = source.index(right_text, op + len(operator))
            expression = _node("binary", left, right + len(right_text), operator=_name(operator.decode(), op),
                               left=_node("bool" if boolean else "nat", left, left + len(left_text),
                                          value=True if boolean else "3"),
                               right=_node("bool" if boolean else "nat", right, right + len(right_text),
                                           value=False if boolean else "2"))
            module = vela_ast.decode(source, _fixture(source, expression, value_type=result_type))
            function = module.declarations[0]
            ensure(isinstance(function, vela_ast.Function)
                   and isinstance(function.body.terminal, vela_ast.Return)
                   and function.body.terminal.value.value == operator.decode()
                   and function.body.terminal.value.site == vela_ast.position(source[:op].decode()),
                   "native extended binary operator lost its spelling or original source site")
    source = b"module M; public bool F() { return !true; }"
    first = source.index(b"!")
    expected = _node("unary", first, first + 5, operator=_name("!", first),
                     value=_node("bool", first + 1, first + 5, value=True))
    for mutation in ("operator", "extra-field", "missing-value", "operator-span", "operand-span"):
        changed = copy.deepcopy(expected)
        if mutation == "operator":
            cast("dict[str, object]", changed["operator"])["text"] = "-"
        elif mutation == "extra-field":
            changed["ignored"] = False
        elif mutation == "missing-value":
            del changed["value"]
        elif mutation == "operator-span":
            cast("dict[str, object]", changed["operator"])["span"] = [first, first + 2]
        else:
            cast("dict[str, object]", changed["value"])["span"] = [first, first + 5]
        try:
            vela_ast.decode(source, _fixture(source, changed, value_type="bool"))
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"native decoder accepted unary {mutation} forgery")


def _negation_source_coverage() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        source = ("// café".encode() + newline + b"module M; public bool F() { return ! // skipped !"
                  + newline + b" !true; }")
        first = source.index(b"!", source.index(b"return"))
        second = source.index(b"!true")
        literal = second + 1
        value = _node("bool", literal, literal + 4, value=True)
        nested = _node("unary", second, literal + 4, operator=_name("!", second), value=value)
        expression = _node("unary", first, literal + 4, operator=_name("!", first), value=nested)
        module = vela_ast.decode(source, _fixture(source, expression, value_type="bool"))
        declaration = module.declarations[0]
        ensure(isinstance(declaration, vela_ast.Function)
               and isinstance(declaration.body.terminal, vela_ast.Return)
               and declaration.body.terminal.value.children[0].value == "!",
               "nested unary source lost a negation across complete trivia")
        omitted = _node("unary", first, literal + 4, operator=_name("!", first), value=value)
        for changed in (omitted, nested, value):
            try:
                vela_ast.decode(source, _fixture(source, changed, value_type="bool"))
            except ValueError:
                pass
            else:
                raise AssertionError("native unary decoding omitted a source operator")
    for authored, operator, operand in ((b"-true", "-", b"true"),
                                        (b"!+true", "!", b"true"),
                                        (b"!true false", "!", b"true"),
                                        (b"! // true\n false", "!", b"true")):
        source = b"module M; public bool F() { return " + authored + b"; }"
        start = source.index(authored)
        literal = source.index(operand, start)
        value = _node("bool", literal, literal + len(operand), value=operand == b"true")
        expression = _node("unary", start, start + len(authored), operator=_name(operator, start), value=value)
        try:
            vela_ast.decode(source, _fixture(source, expression, value_type="bool"))
        except ValueError:
            pass
        else:
            raise AssertionError(f"native unary source coverage accepted {authored!r}")
    for count in (63, 64, 300):
        source = b"module M; public bool F() { return " + b"!" * count + b"true; }"
        literal = source.index(b"true")
        expression = _node("bool", literal, literal + 4, value=True)
        for index in range(count):
            first = literal - index - 1
            expression = _node("unary", first, literal + 4, operator=_name("!", first), value=expression)
        try:
            vela_ast.decode(source, _fixture(source, expression, value_type="bool"))
        except vela.VelaError as error:
            ensure(count >= 64 and error.kind == "limit", "wrong native unary depth refusal")
        else:
            ensure(count == 63, "native decoder accepted excessive unary depth")


def _combined_negation_and_group_limits() -> None:
    prefix = b"module M; public bool F() { return "
    for negations, expected in ((31, "accepted"), (32, "limit")):
        for outer in ("unary", "group"):
            wrappers = (("unary",) * negations + ("group",) * 32 if outer == "unary"
                        else ("group",) * 32 + ("unary",) * negations)
            opens = b"".join(b"!" if kind == "unary" else b"(" for kind in wrappers)
            source = prefix + opens + b"true" + b")" * 32 + b"; }"
            literal = len(prefix) + len(opens)
            end = literal + 4
            tree = _node("bool", literal, end, value=True)
            for index in reversed(range(len(wrappers))):
                start = len(prefix) + index
                if wrappers[index] == "group":
                    end += 1
                    tree = _node("group", start, end, value=tree)
                else:
                    tree = _node("unary", start, end, operator=_name("!", start), value=tree)
            native = _fixture(source, tree, value_type="bool")
            outputs = []
            for native_route in (False, True):
                try:
                    translated = vela.translate_ast(source, native) if native_route else vela.translate(source)
                except vela.VelaError as error:
                    ensure(expected == "limit" and error.kind == "limit", "mixed nesting reached wrong refusal")
                else:
                    ensure(expected == "accepted", f"{outer} mixed nesting bypassed the combined depth budget")
                    outputs.append(translated)
            if expected == "accepted":
                ensure(len(outputs) == 2 and outputs[0] == outputs[1], "mixed nesting changed translation")


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
        function = cast("dict[str, object]", cast("list[object]", ast["declarations"])[0])
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
            ast["declarations"] = []
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
                         declarations=[declaration, function])}


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
            functions = cast("list[dict[str, object]]", ast["declarations"])
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
            Case("typed-local-source-annotations-and-keyword-provenance", _typed_local_protocol),
            Case("expression-body-source-binding-and-terms", _expression_body_protocol),
            Case("expression-body-complete-token-coverage", _expression_body_uncovered_tokens),
            Case("located-labels-and-complete-call-token-coverage", _located_named_arguments),
            Case("held-out-source-edits", _held_out_edits),
            Case("extended-operator-schema-and-sites", _extended_operator_protocol),
            Case("negation-source-token-coverage-and-depth", _negation_source_coverage),
            Case("combined-negation-and-group-depth-boundaries", _combined_negation_and_group_limits),
            Case("strict-native-schema-and-provenance", _protocol_controls),
            Case("native-semantic-diagnostics", _semantic_refusals),
            Case("native-resource-boundaries", _resource_boundaries)]
