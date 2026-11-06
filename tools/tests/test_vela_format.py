# SPDX-License-Identifier: Apache-2.0
"""Independent canonical-layout and source-preservation controls for pure Vela."""

from tests.harness import Case, ensure
from vos.vela import VelaError, translate
from vos.vela.authoring import STYLE_VERSION, format_source

INDEPENDENT_CASES = True


def _allman_and_spacing() -> None:
    source = b"module Example;public Nat Scale(Nat count){let total=count*2;return total;}"
    expected = (b"module Example;\n\npublic Nat Scale(Nat count)\n{\n"
                b"    let total = count * 2;\n    return total;\n}\n")
    ensure(STYLE_VERSION == 1, "format controls require style version 1")
    ensure(format_source(source) == expected, "canonical Allman layout differs from independent expected bytes")
    ensure(format_source(expected) == expected, "canonical source changed on a second pass")
    grouped = b"module M;public Nat F(){return((1+2));}"
    ensure(b"    return ((1 + 2));\n" in format_source(grouped),
           "return grouping was formatted like a function call")


def _nested_control_and_expression_bodies() -> None:
    source = (b"module M; public Nat Echo(Nat value,)=>((value));"
              b"public Nat Pick(bool yes,Nat count){if(yes){return Echo(value:count,);}"
              b"else {return 0;}}")
    expected = (b"module M;\n\npublic Nat Echo(Nat value,) => ((value));\n\n"
                b"public Nat Pick(bool yes, Nat count)\n{\n    if (yes)\n    {\n"
                b"        return Echo(value: count,);\n    }\n    else\n    {\n"
                b"        return 0;\n    }\n}\n")
    ensure(format_source(source) == expected,
           "nesting, expression bodies, labels, parentheses or trailing commas changed")
    ensure(translate(source).gallina.splitlines()[2:] == translate(expected).gallina.splitlines()[2:],
           "canonical layout changed generated pure definitions")


def _comments_and_documentation_boundaries() -> None:
    source = ("// header 😀  \r\nmodule M; // module  \r"
              "/// orphan  \n\npublic Nat Echo(Nat value){\n"
              " // body café \t\nreturn value; // end  \n}\r\n"
              "/// attached\r\n/// second  \r\npublic const Nat Limit=002;\r\n"
              "// tail ").encode()
    expected = ("// header 😀  \nmodule M; // module  \n\n"
                "/// orphan  \n\npublic Nat Echo(Nat value)\n{\n"
                "    // body café \t\n    return value; // end  \n}\n\n"
                "/// attached\n/// second  \npublic const Nat Limit = 002;\n\n// tail \n").encode()
    ensure(format_source(source) == expected,
           "comment contents, Unicode, attachment breaks or normalized newlines changed")
    ensure(format_source(expected) == expected, "comments are not idempotent")


def _composed_authoring_features() -> None:
    source = (b"module M;\n/// Defines the limit.\npublic const Nat Limit=1_024;\n"
              b"/// Returns the selected value.\npublic Nat Echo(Nat value,)=>value;"
              b"public Nat Pick(bool yes,Nat count){const Nat localLimit=2_048;"
              b"if(yes){return Echo(value:count+Limit,);}"
              b"else{// fallback\nreturn localLimit;}}")
    expected = (b"module M;\n\n/// Defines the limit.\npublic const Nat Limit = 1_024;\n\n"
                b"/// Returns the selected value.\npublic Nat Echo(Nat value,) => value;\n\n"
                b"public Nat Pick(bool yes, Nat count)\n{\n    const Nat localLimit = 2_048;\n"
                b"    if (yes)\n    {\n        return Echo(value: count + Limit,);\n    }\n"
                b"    else\n    { // fallback\n        return localLimit;\n    }\n}\n")
    ensure(format_source(source) == expected,
           "composed constants, separators, calls, comments and nesting changed canonical bytes")
    ensure(format_source(expected) == expected, "composed authoring features are not idempotent")
    ensure(translate(source).gallina.splitlines()[2:] == translate(expected).gallina.splitlines()[2:],
           "composed authoring formatting changed emitted definitions")


def _inline_comments_in_delimiters() -> None:
    source = (b"module M;public Nat Echo(Nat // parameter\nvalue)"
              b"{return ( // grouped\nvalue);}")
    result = format_source(source)
    ensure(b"// parameter\n" in result and b"// grouped\n" in result,
           "delimiter comments were dropped or joined with code")
    ensure(b"value" in result and format_source(result) == result,
           "delimiter comment formatting did not stabilize")
    ensure(translate(source).gallina.splitlines()[2:] == translate(result).gallina.splitlines()[2:],
           "delimiter comment formatting changed emitted terms")


def _generated_comment_boundaries() -> None:
    words = ("module", "M", ";", "public", "Nat", "Echo", "(", "Nat", "value", ")",
             "{", "let", "result", "=", "(", "value", "+", "1", ")", ";",
             "return", "result", ";", "}")
    for index in range(1, len(words)):
        for comment in (" // inline  \n", "\n// standalone \t\n", "\n/// orphan\n\n"):
            source = (" ".join(words[:index]) + comment + " ".join(words[index:])).encode()
            result = format_source(source)
            ensure(format_source(result) == result,
                   f"comment boundary {index} did not stabilize: {comment!r}")
            ensure(translate(source).gallina.splitlines()[2:] == translate(result).gallina.splitlines()[2:],
                   f"comment boundary {index} changed checked emitted terms")


def _refuses_invalid_and_unsupported() -> None:
    sources = (b"module M; public Nat Bad() => missing;",
               b"module M; public Nat Bad(ref Nat value) => value;",
               b"module M; public Nat Bad() => true;",
               b"module M; public Nat Bad() { return 0;",
               b"module M; public Nat Bad() => 0;\xff")
    for source in sources:
        try:
            format_source(source)
        except VelaError:
            continue
        raise AssertionError(f"formatter accepted invalid or unsupported source: {source!r}")


def _bounded_output() -> None:
    sources = (b"module M;public Nat F(){" + b" " * 65_536 + b"return 0;}",
               b"module M;public Nat F(){\n" + b"//\n" * 10_000 + b"return 0;}")
    for source in sources:
        try:
            format_source(source)
        except VelaError as error:
            ensure(error.kind == "limit", "oversized source or candidate lost its limit verdict")
            continue
        raise AssertionError("formatter accepted oversized input or output")


def _extended_expression_spacing() -> None:
    source = (b"module M;public bool Decide(bool flag,Nat value){"
              b"let ready=!!flag;return !(ready||value<2)&&value>=1&&value!=3||value>4;}"
              b"public Nat Remaining(Nat total,Nat used)=>total-used+2*3;")
    expected = (b"module M;\n\npublic bool Decide(bool flag, Nat value)\n{\n"
                b"    let ready = !!flag;\n"
                b"    return !(ready || value < 2) && value >= 1 && value != 3 || value > 4;\n}\n\n"
                b"public Nat Remaining(Nat total, Nat used) => total - used + 2 * 3;\n")
    ensure(format_source(source) == expected, "prefix or binary operator spacing changed")
    ensure(format_source(expected) == expected, "extended expressions are not idempotent")
    ensure(translate(source).gallina.splitlines()[2:] == translate(expected).gallina.splitlines()[2:],
           "operator formatting changed generated terms")
    for boundary in (b"! // prefix\n!flag", b"! // group\n(flag || false)", b"!\n// comment\nflag"):
        commented = b"module M;public bool Decide(bool flag)=>" + boundary + b";"
        formatted = format_source(commented)
        ensure(format_source(formatted) == formatted, "prefix comment layout failed to stabilize")
        ensure(translate(commented).gallina.splitlines()[2:] == translate(formatted).gallina.splitlines()[2:],
               "negation comment formatting changed meaning")


def cases() -> list[Case]:
    return [Case("vela-style-allman-and-spacing", _allman_and_spacing),
            Case("vela-style-nested-control-and-expression-body", _nested_control_and_expression_bodies),
            Case("vela-style-comments-and-doc-attachment", _comments_and_documentation_boundaries),
            Case("vela-style-composed-authoring-features", _composed_authoring_features),
            Case("vela-style-inline-comments-in-delimiters", _inline_comments_in_delimiters),
            Case("vela-style-generated-comment-token-boundaries", _generated_comment_boundaries),
            Case("vela-style-extended-expressions-and-prefix-comments", _extended_expression_spacing),
            Case("vela-style-invalid-and-unsupported-refusal", _refuses_invalid_and_unsupported),
            Case("vela-style-bounded-input", _bounded_output)]
