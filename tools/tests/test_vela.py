# SPDX-License-Identifier: Apache-2.0
"""Independent translation oracles and rejection/publication cases for pure Vela."""

import hashlib
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos.cli import vela as cli
from vos.vela import MAX_SOURCE_BYTES, VelaError, translate

_NAT = "Corelib.Init.Datatypes.nat"
_BOOL = "Corelib.Init.Datatypes.bool"
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"
_ORACLE = b"""module Oracle;
public Nat Cube(Nat x) { return x * x * x; }
public bool Choose(bool flag, Nat x) {
  let y = Cube(x + 1);
  if (flag == true) {
    let limit = 9;
    return y <= limit;
  } else {
    let limit = 0;
    if (y == limit) { return true; } else { return false; }
  }
}
"""


def _nat(value: int) -> str:
    return f"({value} : {_NAT})"


def _header(source: bytes) -> str:
    return ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
            "(* Vela pure prototype: unqualified. Source SHA256: "
            f"{hashlib.sha256(source).hexdigest()} *)\n"
            "From Corelib Require Import Init.Datatypes Init.Nat.\n\n")


def _refuses(source: bytes | str, kind: str, fragment: str = "") -> VelaError:
    try:
        translate(source.encode("utf-8") if isinstance(source, str) else source)
    except VelaError as error:
        ensure(error.kind == kind, f"expected {kind}, got {error.kind}: {error.message}")
        ensure(fragment in error.message, f"missing {fragment!r} in {error.message!r}")
        ensure(error.line >= 1 and error.column >= 1, "diagnostic has no source location")
        return error
    raise AssertionError(f"unexpected acceptance: {source!r}")


def _oracle() -> None:
    # Chosen independently of the emitter by the separate contract reviewer.
    # Cube is left associated; Choose has separate branch locals and a nested exit.
    expected = (_header(_ORACLE) + "Module Vela_Oracle.\n\n"
                f"Definition f_Cube (v_x : {_NAT}) : {_NAT} :=\n"
                "  (Corelib.Init.Nat.mul (Corelib.Init.Nat.mul v_x v_x) v_x).\n\n"
                f"Definition f_Choose (v_flag : {_BOOL}) (v_x : {_NAT}) : {_BOOL} :=\n"
                f"  (let v_y := (f_Cube (Corelib.Init.Nat.add v_x {_nat(1)})) in "
                f"(if (let vela_eq_left := v_flag in let vela_eq_right := {_TRUE} in "
                f"if vela_eq_left then vela_eq_right else "
                f"(if vela_eq_right then {_FALSE} else {_TRUE})) "
                f"then (let v_limit := {_nat(9)} in (Corelib.Init.Nat.leb v_y v_limit)) "
                f"else (let v_limit := {_nat(0)} in "
                f"(if (Corelib.Init.Nat.eqb v_y v_limit) then {_TRUE} else {_FALSE})))).\n\n"
                "End Vela_Oracle.\n")
    translation = translate(_ORACLE)
    ensure(translation.module == "Oracle", "module identity lost")
    ensure(translation.gallina == expected,
           f"translation differs from independently selected terms:\n{translation.gallina}")
    ensure(translate(_ORACLE).gallina == expected, "translation is nondeterministic")
    example = (TOOLS / "vela/examples/pure.vela").read_bytes()
    emitted = translate(example).gallina
    ensure(emitted[len(_header(example)):] == expected[len(_header(_ORACLE)):],
           "authored example diverges from independent oracle")


def _precedence_and_literals() -> None:
    source = b"module Math; public bool Test() { return 0001 + 2 * 3 == 7; }"
    body = (f"(Corelib.Init.Nat.eqb (Corelib.Init.Nat.add {_nat(1)} "
            f"(Corelib.Init.Nat.mul {_nat(2)} {_nat(3)})) {_nat(7)})")
    ensure(f"  {body}.\n" in translate(source).gallina,
           "arithmetic/equality precedence or decimal normalization changed")
    source = b"module Math; public Nat Test() { return (1 + 2) * 3; }"
    body = f"(Corelib.Init.Nat.mul (Corelib.Init.Nat.add {_nat(1)} {_nat(2)}) {_nat(3)})"
    ensure(f"  {body}.\n" in translate(source).gallina, "parentheses lost grouping")
    wide = 2 ** 100 + 1
    ensure(_nat(wide) in translate(f"module N; public Nat N() {{ return {wide}; }}".encode()).gallina,
           "mathematical natural truncated to a machine word")
    source = b"module B; public bool B() { return false; } public bool C() { return B(); }"
    ensure(f"  {_FALSE}.\n" in translate(source).gallina, "false not emitted")
    ensure("  f_B.\n" in translate(source).gallina, "nullary call malformed")


def _expression_bodies_and_commas() -> None:
    concise = (b"module M; public Nat F(Nat x, bool flag,) => x * (x + 1); "
               b"public Nat G() => F(3, true,); public bool H() => false;")
    expanded = (b"module M; public Nat F(Nat x, bool flag) { return x * (x + 1); } "
                b"public Nat G() { return F(3, true); } public bool H() { return false; }")
    actual = translate(concise).gallina[len(_header(concise)):]
    ensure(actual == translate(expanded).gallina[len(_header(expanded)):],
           "expression-body or trailing-comma sugar changed the checked definitions")
    for source in ("public Nat F() => ;", "public Nat F() => 1",
                   "public Nat F(,) => 0;", "public Nat F(Nat x,,) => x;",
                   "public Nat F() => 0; public Nat G() => F(,);",
                   "public Nat F(Nat x) => x; public Nat G() => F(1,,);",
                   "public Nat F() => (1,);", "public Nat F() => 1; return 2;"):
        _refuses("module M; " + source, "syntax")
    _refuses("module M; public Nat F() => true;", "type")
    _refuses("module M; public Nat F() => missing;", "name")
    _refuses("module M; public Nat F() => " + "(" * 64 + "0" + ")" * 64 + ";", "limit")


def _ownership_explanations() -> None:
    for spelling, meaning in (("in", "shared read loan"), ("ref", "initialized exclusive loan"),
                              ("out", "exclusive initialization loan"),
                              ("owned", "consuming ownership"), ("move", "ownership transfer")):
        error = _refuses(f"module M; public Nat F() => {spelling} value;", "unsupported", meaning)
        ensure("cannot check ownership, borrowing or resource lifetimes" in error.message,
               "ownership diagnostic claimed a borrow-checking verdict")


def _scope_and_hygiene() -> None:
    source = b"""module Module;
public Nat Definition(Nat end, bool Type) {
  let nat = end;
  if (Type) { let Set = nat; return Set; } else { let Set = 0; return Set; }
}
public Nat Invoke(Nat Definition) { return Definition(Definition, true); }
"""
    emitted = translate(source).gallina
    for fragment in ("Module Vela_Module.", "Definition f_Definition",
                     f"(v_end : {_NAT})", f"(v_Type : {_BOOL})",
                     "(let v_nat := v_end in", "(let v_Set := v_nat in v_Set)",
                     "(f_Definition v_Definition", "End Vela_Module."):
        ensure(fragment in emitted, f"identifier hygiene lost: {fragment}")
    # A branch-local binder is gone after that branch; a fresh branch may reuse it.
    _refuses("module M; public Nat F() { if (true) { let b = 1; return b; } "
             "else { return b; } }", "name")
    # Comments cannot enter generated code, even if they contain Gallina commands.
    commented = ("// café *) Axiom bad : False. (*\n"
                 "module M; public Nat F() { return 1; }// tail\n")
    emitted = translate(commented.encode()).gallina
    ensure("Axiom" not in emitted and "café" not in emitted, "comment injected Gallina")


def _typed_neighbors() -> None:
    # Each neighbor stays syntactically valid and reaches its intended premise.
    neighbors: tuple[tuple[str, str], ...] = (
        ("public Nat F() { return true; }", "type"),
        ("public bool F() { return 1; }", "type"),
        ("public Nat F() { if (1) { return 0; } else { return 1; } }", "type"),
        ("public Nat F() { if (true) { return 0; } else { return false; } }", "type"),
        ("public Nat F() { if (true) { return false; } else { return true; } }", "type"),
        ("public Nat F() { return true + 1; }", "type"),
        ("public Nat F() { return 1 * false; }", "type"),
        ("public bool F() { return true <= false; }", "type"),
        ("public bool F() { return 0 == false; }", "type"),
        ("public Nat F(Nat x) { return x; } public Nat G() { return F(true); }", "type"),
        ("public Nat F(Nat x) { return x; } public Nat G() { return F(); }", "type"),
        ("public Nat F(Nat x) { return x; } public Nat G() { return F(1, 2); }", "type"),
        ("public Nat F() { return missing; }", "name"),
        ("public Nat F() { return Missing(); }", "name"),
        ("public Nat F(Nat x) { return F(x); }", "name"),
        ("public Nat F() { return G(); } public Nat G() { return 0; }", "name"),
        ("public Nat F() { return 0; } public Nat F() { return 1; }", "name"),
        ("public Nat F(Nat x, Nat x) { return x; }", "name"),
        ("public Nat F(Nat x) { let x = 1; return x; }", "name"),
        ("public Nat F() { let x = 1; let x = 2; return x; }", "name"),
        ("public Nat F() { let x = x; return x; }", "name"),
        ("public Nat F(Nat x) { return x(); }", "name"),
    )
    for body, kind in neighbors:
        _refuses("module M; " + body, kind)


def _syntax_and_locations() -> None:
    for source in ("", "module M;", "module M; public Nat F() { return 1; } garbage",
                   "module M; public Nat F() { return 1; } module N;",
                   "module M; public Nat F() { return 1 <= 2 <= 3; }",
                   "module M; public Nat F() { return -1; }",
                   'module M; public Nat F() { return "Axiom injected"; }',
                   "module M; public Nat F() { return 1; } (* arbitrary *)",
                   "module M; public Nat F() { return 1 / 2; }",
                   "module M; public Nat F() { if (true) { return 0; } }",
                   "module M; public Nat F() { return 1, 2; }"):
        _refuses(source, "syntax")
    _refuses("module M; public async Nat F() { return 1; }", "unsupported")
    _refuses("module M; public Nat F() { return await 1; }", "unsupported")
    _refuses("module M; public Nat F() requires true { return 1; }", "unsupported")
    _refuses(b"module M;\n// invalid \xff\n", "encoding")
    _refuses("module M; public Nat Café() { return 0; }", "syntax")
    error = _refuses("module M;\r\npublic Nat F() {\r\n  return missing;\r\n}", "name")
    ensure((error.line, error.column) == (3, 10), "CRLF source location drifted")


def _surface_and_exits() -> None:
    for source in ("public Nat F() {}", "public Nat F() { let x = 1; }",
                   "public Nat F() { return 1 }", "public Nat F() { 1 }",
                   "public Nat F() { return 1; return 2; }",
                   "public Nat F() { if (true) {} else { return 1; } }",
                   "public Nat F() { if true { return 0; } else { return 1; } }",
                   "public Nat F() { if (true) { return 0; } else { return 1; } return 2; }",
                   "public Nat F() { let x = if (true) { return 0; } else { return 1; }; return x; }",
                   "public Nat F() { return (let x = 1; x); }",
                   "public Nat F(Nat x) -> Nat { return x; }",
                   "public Nat F(x: Nat) { return x; }"):
        # A removed spelling may be an unsupported token or a syntax mismatch.
        try:
            translate(("module M; " + source).encode())
        except VelaError as error:
            ensure(error.kind in {"syntax", "unsupported"}, f"wrong surface failure: {error}")
        else:
            raise AssertionError(f"invalid surface accepted: {source}")
    _refuses("module M; fn F(x: Nat) -> Nat { x }", "unsupported")
    _refuses("module M; public Bool F() { return true; }", "unsupported")


def _limits() -> None:
    _refuses(b" " * (MAX_SOURCE_BYTES + 1), "limit")
    _refuses("module M; public Nat F() { return " + "9" * 257 + "; }", "limit")
    _refuses("module M; public Nat F() { return " + "(" * 2000 + "0" + ")" * 2000 + "; }",
             "limit")
    _refuses("module M; public Nat F() { return " + " + ".join(["1"] * 2000) + "; }", "limit")
    bindings = " ".join(f"let x{i} = {i};" for i in range(1000))
    _refuses("module M; public Nat F() { " + bindings + " return 0; }", "limit")
    nested = "return 0;"
    for _ in range(200):
        nested = f"if (true) {{ {nested} }} else {{ return 1; }}"
    _refuses("module M; public Nat F() { " + nested + " }", "limit")
    # Nested Boolean equality must not duplicate its right operand exponentially.
    expression = "false"
    for _ in range(30):
        expression = f"true == ({expression})"
    emitted = translate(f"module M; public bool F() {{ return {expression}; }}".encode()).gallina
    ensure(len(emitted) < 20_000, "small Boolean expression expanded exponentially")


def _source_binding() -> None:
    first = translate(_ORACLE).gallina
    changed = _ORACLE.replace(b"y <= limit", b"y == limit")
    ensure(translate(changed).gallina != first, "semantic edit reused stale output")
    comment = _ORACLE + b"// comment\r\n"
    second = translate(comment).gallina
    ensure(second.startswith(_header(comment)) and not second.startswith(_header(_ORACLE)),
           "digest did not bind exact source bytes")
    ensure(second[len(_header(comment)):] == first[len(_header(_ORACLE)):],
           "comment changed generated definition")
    crlf = _ORACLE.replace(b"\n", b"\r\n")
    ensure(translate(crlf).gallina.startswith(_header(crlf)), "CRLF source bytes normalized")


def _invoke(arguments: list[str]) -> tuple[int, str, str]:
    with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()):
        result = cli.main(arguments)
    return result, out.getvalue(), err.getvalue()


def _cli_publication() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-") as directory:
        root = Path(directory)
        source, output = root / "input.vela", root / "output.v"
        source.write_bytes(_ORACLE)
        code, out, err = _invoke(["check", str(source)])
        ensure(code == 0 and "unqualified" in out and not err, "check hid prototype status")
        code, out, err = _invoke(["emit", str(source)])
        ensure(code == 0 and out == translate(_ORACLE).gallina and not err,
               "stdout emission differs from library")
        code, out, err = _invoke(["emit", str(source), "--output", str(output)])
        ensure(code == 0 and not out and not err, "file publication failed")
        original = output.read_bytes()
        ensure(original == translate(_ORACLE).gallina.encode(), "published bytes differ")
        source.write_bytes(b"module Broken; public Nat F() { return true; }")
        code, out, err = _invoke(["emit", str(source), "--output", str(output)])
        ensure(code == 1 and not out and ": type:" in err, "rejected source emitted output")
        ensure(output.read_bytes() == original, "rejected source clobbered previous output")
        source.write_bytes(_ORACLE)
        code, _, err = _invoke(["emit", str(source), "--output", str(source)])
        ensure(code == 1 and "aliases" in err and source.read_bytes() == _ORACLE,
               "input alias was overwritten")
        alias = root / "alias.vela"
        alias.hardlink_to(source)
        code, _, err = _invoke(["emit", str(source), "--output", str(alias)])
        ensure(code == 1 and "aliases" in err and source.read_bytes() == _ORACLE,
               "hard-linked input alias was overwritten")
        code, _, err = _invoke(["emit", str(source), "--output", str(root / "absent/out.v")])
        ensure(code == 1 and ": io:" in err and not (root / "absent").exists(),
               "missing output directory was created")
        with patch.object(Path, "replace", side_effect=OSError("publication refused")):
            code, _, err = _invoke(["emit", str(source), "--output", str(output)])
        ensure(code == 1 and "publication refused" in err, "write failure not diagnosed")
        ensure(output.read_bytes() == original, "failed write clobbered output")
        ensure(not list(root.glob(".output.v.*.tmp")), "atomic write leaked temporary file")
        code, _, err = _invoke(["check", str(root / "missing.vela")])
        ensure(code == 1 and ": io:" in err, "missing source was not diagnosed")
        source.write_bytes(b"\xff")
        code, _, err = _invoke(["check", str(source)])
        ensure(code == 1 and ": encoding:" in err, "invalid encoding escaped CLI")


def cases() -> list[Case]:
    return [Case("independent-translation-oracle", _oracle),
            Case("precedence-and-literals", _precedence_and_literals),
            Case("expression-bodies-and-trailing-commas", _expression_bodies_and_commas),
            Case("unsupported-ownership-explanations", _ownership_explanations),
            Case("scope-and-hygiene", _scope_and_hygiene),
            Case("typed-negative-neighbors", _typed_neighbors),
            Case("syntax-and-locations", _syntax_and_locations),
            Case("proposed-surface-and-terminal-returns", _surface_and_exits),
            Case("bounded-inputs", _limits), Case("exact-source-binding", _source_binding),
            Case("cli-publication", _cli_publication)]
