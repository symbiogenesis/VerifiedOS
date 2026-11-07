# SPDX-License-Identifier: Apache-2.0
"""Independent typed-local semantics and source-bound explicit-binding previews."""

from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela
from vos.vela import (
    Translation,
    VelaError,
    translate,
)
from vos.vela import (
    authoring as vela_authoring,
)
from vos.vela.authoring import (
    RETIRED_LINT_CODES,
    assist_effects_clause,
    assist_loan_argument,
    assist_null_conditional,
    format_source,
    lint_source,
    preview_bindings,
    suggest_numeric_conversion,
)

INDEPENDENT_CASES = True


def _typed_local_semantics() -> None:
    sources = (b"module M;public Nat Count(){let count=1;return count;}",
               b"module M;public Nat Count(){let Nat count=1;return count;}")
    outputs = [translate(source).gallina.splitlines()[2:] for source in sources]
    ensure(outputs[0] == outputs[1],
           "equivalent inferred/explicit immutable bindings changed interpreted terms")
    for source, annotation, explicit in zip(sources, (None, "Nat"), (True, True), strict=True):
        module = vela._Parser(vela._tokens(source)).parse()
        declaration = module.declarations[0]
        if not isinstance(declaration, vela.syntax.Function):
            raise TypeError("test declaration is not callable")
        local = declaration.body.bindings[0]
        ensure(isinstance(local, vela.syntax.Binding)
               and local.annotation == annotation and local.explicit_binding is explicit,
               "typed-local annotation or explicit binding identity was lost")
    ensure(set(RETIRED_LINT_CODES) == {"VELA104"}, "VELA104 retirement set drifted")
    typed_bool = b"module M;public bool Flag(){let bool flag=true;return flag;}"
    ensure("Datatypes.true" in translate(typed_bool).gallina, "bool local annotation did not check")


def _typed_local_refusals() -> None:
    for declaration in (b"let Nat value=true;", b"let bool value=1;"):
        source = b"module M;public Nat Count(){" + declaration + b"return 0;}"
        try:
            translate(source)
        except VelaError as error:
            ensure(error.kind == "type" and "initializer" in error.message,
                   "local annotation mismatch was not a type refusal")
        else:
            raise AssertionError("a local annotation inserted a conversion")
    for declaration in (b"Nat value=1;", b"Nat value=true;", b"bool value=true;", b"bool value=1;"):
        source = b"module M;public Nat Count(){" + declaration + b"return 0;}"
        try:
            translate(source)
        except VelaError as error:
            ensure(error.kind == "syntax" and "let" in error.message,
                   "bare local declaration was not refused at parse time")
        else:
            raise AssertionError("bare local declaration without let/var was accepted")
    for declaration in (b"let usize count=0;", b"usize count=0;", b"var Nat count=0;"):
        try:
            translate(b"module M;public Nat Count(){" + declaration + b"return 0;}")
        except VelaError as error:
            ensure(error.kind == "unsupported", "wider binding syntax lost its unsupported boundary")
        else:
            raise AssertionError("the pure checker accepted represented types or mutation")
    try:
        translate(b"module M;public Nat Count(){let Nat count=0;count=1;return count;}")
    except VelaError as error:
        ensure(error.kind == "unsupported" and "immutable binding 'count'" in error.message,
               "explicit let typed local did not retain its immutable reassignment diagnostic")
    else:
        raise AssertionError("explicit let typed local became mutable")


def _lint_sites_and_formatter_preservation() -> None:
    legacy_source = ("// 😀\r\nmodule M;\rpublic Nat Count(bool flag) {\n"
                     "    Nat count = 1;\r\n    let bool selected = flag;\n"
                     "    if (selected) { Nat value = count; return value; }\r"
                     "    else { Nat value = 0; return value; }\n}").encode()
    sites = vela_authoring._bare_binding_sites(legacy_source)
    ensure(tuple((site.line, site.column) for site in sites) == ((4, 5), (6, 21), (7, 12)),
           f"migration site scanner lost original type-token sites: {sites!r}")
    source = ("// 😀\r\nmodule M;\rpublic Nat Count(bool flag) {\n"
              "    let Nat count = 1;\r\n    let bool selected = flag;\n"
              "    if (selected) { let Nat value = count; return value; }\r"
              "    else { let Nat value = 0; return value; }\n}").encode()
    formatted = format_source(source)
    ensure(b"let Nat count = 1;" in formatted and b"let bool selected = flag;" in formatted,
           "formatter changed authored typed binding forms")


def _preview_preserves_exact_bytes() -> None:
    source = ("// 😀\r\nmodule M;\rpublic Nat Count(bool flag) {\n"
              "    Nat// keeps the type comment\r\n    count = 1;\r\n"
              "    let bool selected = flag;\n"
              "    if (selected) { Nat value = count; return value; }\r"
              "    else { Nat value = 0; return value; }\n}").encode()
    expected = ("// 😀\r\nmodule M;\rpublic Nat Count(bool flag) {\n"
                "    let Nat// keeps the type comment\r\n    count = 1;\r\n"
                "    let bool selected = flag;\n"
                "    if (selected) { let Nat value = count; return value; }\r"
                "    else { let Nat value = 0; return value; }\n}").encode()
    candidate = preview_bindings(source)
    ensure(candidate == expected, "binding preview changed bytes beyond independently expected let insertions")
    ensure(preview_bindings(candidate) == candidate, "binding preview is not idempotent")
    ensure(translate(expected).gallina.splitlines()[2:] == translate(candidate).gallina.splitlines()[2:],
           "binding preview changed the interpreted source")
    ensure(not any(item.code == "VELA104" for item in lint_source(candidate)),
           "binding preview retained unmarked immutable bindings")


def _preview_rejects_forged_sites_and_terms() -> None:
    source = b"module M;public Nat Count(){Nat count=1;return count;}"
    for sites in ((vela.syntax.Site(1, 1),),
                  (vela.syntax.Site(100, 1),),
                  (vela.syntax.Site(1, 29), vela.syntax.Site(1, 29))):
        with patch.object(vela_authoring, "_bare_binding_sites", return_value=sites):
            try:
                preview_bindings(source)
            except VelaError as error:
                ensure(error.kind == "lint-preview", "forged insertion lost its source-binding refusal")
            else:
                raise AssertionError("preview accepted a forged/duplicate source site")
    expected = b"module M;public Nat Count(){let Nat count=1;return count;}"
    original = translate(expected)
    changed = Translation(original.module, original.gallina + "changed term")
    with (
        patch.object(vela, "translate", side_effect=(original, changed)),
        patch.object(vela_authoring, "_bare_binding_sites", return_value=()),
    ):
        try:
            preview_bindings(expected)
        except VelaError as error:
            ensure(error.kind == "lint-preview" and "interpreted terms" in error.message,
                   "changed preview terms lost their semantic refusal")
        else:
            raise AssertionError("preview published changed interpreted terms")


def _assist_dont_coerce_bridges() -> None:
    loan_source = b"module M;\npublic unit Use(TextBuilder<8> b) => Format.Write(b, \"ok\");\n"
    rewritten_loan = assist_loan_argument(loan_source, 2, 51, "ref")
    ensure(rewritten_loan == b"module M;\npublic unit Use(TextBuilder<8> b) => Format.Write(ref b, \"ok\");\n",
           "loan assist did not insert explicit ref at the checked argument boundary")
    ensure(assist_loan_argument(rewritten_loan, 2, 51, "ref") == rewritten_loan,
           "loan assist was not idempotent on an already explicit ref argument")
    try:
        assist_loan_argument(loan_source, 2, 50, "ref")
    except VelaError as error:
        ensure(error.kind == "lint-preview", "non-token loan insertion lost its lint-preview refusal")
    else:
        raise AssertionError("loan assist accepted a non-identifier boundary")
    propagate, local_match = assist_null_conditional("Read()", "Value")
    ensure(propagate == "(Read()?).Value"
           and local_match == "match (Read()) { Some(value) => value.Value, None() => todo }",
           "null-conditional assist did not offer explicit propagation and local match forms")
    effects_source = b"module M;\npublic Nat ReadCount() { return 0; }\n"
    with_effects = assist_effects_clause(effects_source, 2, 24, ("Write(log)", "Read(counter)", "Read(counter)"))
    ensure(with_effects == b"module M;\npublic Nat ReadCount() effects(Read(counter), Write(log)) { return 0; }\n",
           "effects assist did not insert a closed, deduplicated effects(...) clause before the body")
    arrow_source = b"module M;\npublic Nat ReadCount() => 0;\n"
    ensure(assist_effects_clause(arrow_source, 2, 24, ())
           == b"module M;\npublic Nat ReadCount() effects() => 0;\n",
           "effects assist did not support empty effects() before =>")
    ensure(suggest_numeric_conversion("int", "long", "x") == "long.From(x)",
           "infallibly wider signed conversion did not suggest long.From(x)")
    ensure(suggest_numeric_conversion("byte", "uint", "b") == "uint.From(b)",
           "infallibly wider unsigned conversion did not suggest uint.From(b)")
    ensure(suggest_numeric_conversion("int", "usize", "x") == "usize.TryFrom(x)",
           "signed-to-unsigned conversion did not suggest range-checked usize.TryFrom(x)")
    ensure(suggest_numeric_conversion("long", "int", "wide") == "int.TryFrom(wide)",
           "narrowing conversion did not suggest range-checked int.TryFrom(wide)")
    ensure(suggest_numeric_conversion("uint", "usize", "count") == "usize.TryFrom(count)",
           "target-dependent usize conversion did not suggest range-checked usize.TryFrom(count)")


def cases() -> list[Case]:
    return [Case("vela-binding-typed-immutable-semantics", _typed_local_semantics),
            Case("vela-binding-type-and-mutation-refusals", _typed_local_refusals),
            Case("vela-binding-lint-sites-and-format-preservation", _lint_sites_and_formatter_preservation),
            Case("vela-binding-preview-exact-source-and-terms", _preview_preserves_exact_bytes),
            Case("vela-binding-preview-source-and-term-controls", _preview_rejects_forged_sites_and_terms),
            Case("vela-assist-dont-coerce-bridges", _assist_dont_coerce_bridges)]
