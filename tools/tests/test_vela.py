# SPDX-License-Identifier: Apache-2.0
"""Independent translation oracles and rejection/publication cases for pure Vela."""

import hashlib
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from vos.vela import MAX_SOURCE_BYTES, VelaError, translate

from tests.harness import TOOLS, Case, ensure
from vos.cli import vela as cli

_NAT = "Corelib.Init.Datatypes.nat"
_BOOL = "Corelib.Init.Datatypes.bool"
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"
_ORACLE = b"""module Oracle;
fn cube(x: Nat) -> Nat { x * x * x }
fn choose(flag: Bool, x: Nat) -> Bool {
  let y = cube(x + 1);
  if flag == true { y <= 9 } else { y == 0 }
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
    # cube is left associated; choose uses natural comparison and both equalities.
    expected = (_header(_ORACLE) + "Module Vela_Oracle.\n\n"
                f"Definition f_cube (v_x : {_NAT}) : {_NAT} :=\n"
                "  (Corelib.Init.Nat.mul (Corelib.Init.Nat.mul v_x v_x) v_x).\n\n"
                f"Definition f_choose (v_flag : {_BOOL}) (v_x : {_NAT}) : {_BOOL} :=\n"
                f"  (let v_y := (f_cube (Corelib.Init.Nat.add v_x {_nat(1)})) in "
                f"(if (let vela_eq_left := v_flag in let vela_eq_right := {_TRUE} in "
                f"if vela_eq_left then vela_eq_right else "
                f"(if vela_eq_right then {_FALSE} else {_TRUE})) "
                f"then (Corelib.Init.Nat.leb v_y {_nat(9)}) "
                f"else (Corelib.Init.Nat.eqb v_y {_nat(0)}))).\n\n"
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
    source = b"module Math; fn test() -> Bool { 0001 + 2 * 3 == 7 }"
    body = (f"(Corelib.Init.Nat.eqb (Corelib.Init.Nat.add {_nat(1)} "
            f"(Corelib.Init.Nat.mul {_nat(2)} {_nat(3)})) {_nat(7)})")
    ensure(f"  {body}.\n" in translate(source).gallina,
           "arithmetic/equality precedence or decimal normalization changed")
    source = b"module Math; fn test() -> Nat { (1 + 2) * 3 }"
    body = f"(Corelib.Init.Nat.mul (Corelib.Init.Nat.add {_nat(1)} {_nat(2)}) {_nat(3)})"
    ensure(f"  {body}.\n" in translate(source).gallina, "parentheses lost grouping")
    wide = 2 ** 100 + 1
    ensure(_nat(wide) in translate(f"module N; fn n() -> Nat {{ {wide} }}".encode()).gallina,
           "mathematical natural truncated to a machine word")
    source = b"module B; fn b() -> Bool { false } fn c() -> Bool { b() }"
    ensure(f"  {_FALSE}.\n" in translate(source).gallina, "false not emitted")
    ensure("  f_b.\n" in translate(source).gallina, "nullary call malformed")


def _scope_and_hygiene() -> None:
    source = b"""module Module;
fn Definition(end: Nat, Type: Bool) -> Nat {
  let nat = end;
  if Type { let bool = nat; bool } else { let bool = 0; bool }
}
fn invoke(Definition: Nat) -> Nat { Definition(Definition, true) }
"""
    emitted = translate(source).gallina
    for fragment in ("Module Vela_Module.", "Definition f_Definition",
                     f"(v_end : {_NAT})", f"(v_Type : {_BOOL})",
                     "(let v_nat := v_end in", "(let v_bool := v_nat in v_bool)",
                     "(f_Definition v_Definition", "End Vela_Module."):
        ensure(fragment in emitted, f"identifier hygiene lost: {fragment}")
    # A branch-local binder is gone after that branch; a fresh branch may reuse it.
    _refuses("module M; fn f() -> Nat { let a = (let b = 1; b); b }", "name")
    # Comments cannot enter generated code, even if they contain Gallina commands.
    commented = "// café *) Axiom bad : False. (*\nmodule M; fn f() -> Nat { 1 }// tail\n"
    emitted = translate(commented.encode()).gallina
    ensure("Axiom" not in emitted and "café" not in emitted, "comment injected Gallina")


def _typed_neighbors() -> None:
    # Each neighbor stays syntactically valid and reaches its intended premise.
    neighbors: tuple[tuple[str, str], ...] = (
        ("fn f() -> Nat { true }", "type"),
        ("fn f() -> Bool { 1 }", "type"),
        ("fn f() -> Nat { if 1 { 0 } else { 1 } }", "type"),
        ("fn f() -> Nat { if true { 0 } else { false } }", "type"),
        ("fn f() -> Nat { true + 1 }", "type"),
        ("fn f() -> Nat { 1 * false }", "type"),
        ("fn f() -> Bool { true <= false }", "type"),
        ("fn f() -> Bool { 0 == false }", "type"),
        ("fn f(x: Nat) -> Nat { x } fn g() -> Nat { f(true) }", "type"),
        ("fn f(x: Nat) -> Nat { x } fn g() -> Nat { f() }", "type"),
        ("fn f(x: Nat) -> Nat { x } fn g() -> Nat { f(1, 2) }", "type"),
        ("fn f() -> Nat { missing }", "name"),
        ("fn f() -> Nat { missing() }", "name"),
        ("fn f(x: Nat) -> Nat { f(x) }", "name"),
        ("fn f() -> Nat { g() } fn g() -> Nat { 0 }", "name"),
        ("fn f() -> Nat { 0 } fn f() -> Nat { 1 }", "name"),
        ("fn f(x: Nat, x: Nat) -> Nat { x }", "name"),
        ("fn f(x: Nat) -> Nat { let x = 1; x }", "name"),
        ("fn f() -> Nat { let x = 1; let x = 2; x }", "name"),
        ("fn f() -> Nat { let x = x; x }", "name"),
        ("fn f(x: Nat) -> Nat { x() }", "name"),
    )
    for body, kind in neighbors:
        _refuses("module M; " + body, kind)


def _syntax_and_locations() -> None:
    for source in ("", "module M;", "module M; fn f() -> Nat { 1 } garbage",
                   "module M; fn f() -> Nat { 1 } module N;",
                   "module M; fn f() -> Nat { 1 <= 2 <= 3 }",
                   "module M; fn f() -> Nat { -1 }",
                   'module M; fn f() -> Nat { "Axiom injected" }',
                   "module M; fn f() -> Nat { 1 } (* arbitrary *)",
                   "module M; fn f() -> Nat { 1 / 2 }",
                   "module M; fn f() -> Nat { if true { 0 } }",
                   "module M; fn f(x) -> Nat { x }",
                   "module M; fn f() -> Nat { 1, 2 }"):
        _refuses(source, "syntax")
    _refuses("module M; async fn f() -> Nat { 1 }", "unsupported")
    _refuses("module M; fn f() -> Nat { await 1 }", "unsupported")
    _refuses(b"module M;\n// invalid \xff\n", "encoding")
    _refuses("module M; fn café() -> Nat { 0 }", "syntax")
    error = _refuses("module M;\r\nfn f() -> Nat {\r\n  missing\r\n}", "name")
    ensure((error.line, error.column) == (3, 3), "CRLF source location drifted")


def _limits() -> None:
    _refuses(b" " * (MAX_SOURCE_BYTES + 1), "limit")
    _refuses("module M; fn f() -> Nat { " + "9" * 257 + " }", "limit")
    _refuses("module M; fn f() -> Nat { " + "(" * 2000 + "0" + ")" * 2000 + " }",
             "limit")
    _refuses("module M; fn f() -> Nat { " + " + ".join(["1"] * 2000) + " }", "limit")
    bindings = " ".join(f"let x{i} = {i};" for i in range(1000))
    _refuses("module M; fn f() -> Nat { " + bindings + " 0 }", "limit")


def _source_binding() -> None:
    first = translate(_ORACLE).gallina
    changed = _ORACLE.replace(b"y <= 9", b"y <= 8")
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
        source.write_bytes(b"module Broken; fn f() -> Nat { true }")
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
            Case("scope-and-hygiene", _scope_and_hygiene),
            Case("typed-negative-neighbors", _typed_neighbors),
            Case("syntax-and-locations", _syntax_and_locations),
            Case("bounded-inputs", _limits), Case("exact-source-binding", _source_binding),
            Case("cli-publication", _cli_publication)]
