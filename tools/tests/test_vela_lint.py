# SPDX-License-Identifier: Apache-2.0
"""Independent finding identities, locations and supported-syntax lint controls."""

from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela
from vos.vela import VelaError
from vos.vela.authoring import LINT_CODES, lint_source
from vos.vela.facts import MAX_SYMBOLS

INDEPENDENT_CASES = True


def _findings_and_sites() -> None:
    source = (b"module M;\npublic bool bad(bool Flag)\n{\n"
              b"    let Value = Flag == true;\n    return Value;\n}\n")
    values = lint_source(source)
    expected = (("VELA100", 2, 13), ("VELA102", 2, 13),
                ("VELA101", 2, 22), ("VELA101", 4, 9), ("VELA103", 4, 22))
    ensure(tuple((value.code, value.line, value.column) for value in values) == expected,
           f"findings differ from independent code/site expectations: {values!r}")
    ensure(all(value.message for value in values), "a finding has no actionable message")
    ensure(set(LINT_CODES) == {"VELA100", "VELA101", "VELA102", "VELA103", "VELA104", "VELA105", "VELA106"},
           "stable lint IDs drifted")


def _uses_compiler_doc_facts() -> None:
    source = b"module M; public Nat Good(Nat value) => value;"
    facts = vela.inspect_source(source)
    symbols = cast("list[dict[str, object]]", facts["symbols"])
    symbols[0]["documentation"] = {"text": "A compiler-owned summary."}
    with patch.object(vela, "inspect_source", return_value=facts):
        ensure(lint_source(source) == (), "missing-documentation lint ignored the compiler declaration fact")
    ensure(tuple(item.code for item in lint_source(source)) == ("VELA102",),
           "undocumented public member did not receive its advisory finding")


def _nested_literals_and_local_constants() -> None:
    source = (b"module M;public const Nat limit=1;public bool Choose(bool flag){"
              b"const Nat localLimit=2;if((true)==flag){return false==flag;}else{return flag;}}")
    values = lint_source(source)
    ensure(sum(item.code == "VELA100" for item in values) == 1,
           "public constant naming did not use the member convention")
    ensure(not any(item.code == "VELA101" for item in values),
           "camelCase parameter or local constant was incorrectly warned")
    ensure(sum(item.code == "VELA103" for item in values) == 2,
           "grouped/left/right Boolean literal comparisons were not inspected structurally")


def _comments_are_not_expressions() -> None:
    source = ("// Bad_Name == true 😀\r\nmodule M;\r\n"
              "public bool Good(bool flag) { // flag == false\r\nreturn flag; }").encode()
    values = lint_source(source)
    ensure(tuple(item.code for item in values) == ("VELA102",),
           "a comment or source spelling produced a semantic lint")
    ensure((values[0].line, values[0].column) == (3, 13), "Unicode/CRLF shifted the lint location")
    ignored = lint_source(b"module M;public Nat Ignore(Nat _) => 0;")
    ensure(not any(value.code == "VELA101" for value in ignored),
           "the conventional ignored-binding spelling received a naming warning")


def _invalid_programs_never_get_partial_findings() -> None:
    for source in (b"module M;public Nat bad(Nat Bad)=>missing;",
                   b"module M;public bool bad(ref bool Bad)=>Bad;",
                   b"module M;public Nat bad()=>true;"):
        try:
            lint_source(source)
        except VelaError:
            continue
        raise AssertionError("lints returned findings for an invalid or unsupported program")


def _unavailable_inspection_is_not_clean() -> None:
    parameters = ",".join(f"Nat p{index}" for index in range(MAX_SYMBOLS))
    source = ("module M;public Nat Good(" + parameters + ") => 0;").encode()
    vela.translate(source)
    try:
        lint_source(source)
    except VelaError as error:
        ensure(error.kind == "inspection-limit", "bounded lint facts lost their unavailable status")
        return
    raise AssertionError("bounded unavailable lint inspection was reported as a clean pass")


def cases() -> list[Case]:
    return [Case("vela-lints-independent-codes-and-sites", _findings_and_sites),
            Case("vela-lints-use-compiler-documentation", _uses_compiler_doc_facts),
            Case("vela-lints-nested-boolean-and-constant-conventions", _nested_literals_and_local_constants),
            Case("vela-lints-comments-and-unicode-locations", _comments_are_not_expressions),
            Case("vela-lints-complete-check-required", _invalid_programs_never_get_partial_findings),
            Case("vela-lints-unavailable-inspection-not-clean", _unavailable_inspection_is_not_clean)]
