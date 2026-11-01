# SPDX-License-Identifier: Apache-2.0
"""Compare development-parser consumers without promoting either frontend.

Agreement is a migration prerequisite, not checked parsing or source
correspondence. Every difference remains visible in the native-lane report.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos import vela, vela_parser
from vos.atomic import atomic_path


@dataclass(frozen=True)
class Fixture:
    name: str
    source: bytes
    expected: str


def fixtures(example: bytes) -> tuple[Fixture, ...]:
    """Source edits selected separately from the grammar and AST decoder."""
    positive = (
        ("authored-example", example),
        ("precedence-edit", b"module M; public bool F() { return 0001 + 2 * 3 == 7; }"),
        ("grouping-edit", b"module M; public Nat F() { return (1 + 2) * 3; }"),
        ("earlier-function", b"module M; public Nat A(Nat x) { return x * x; } "
         b"public Nat B() { return A(3 + 1); }"),
        ("branch-scopes", b"module M; public Nat F(bool b) { if (b) { let x = 1; return x; } "
         b"else { let x = 2; return x; } }"),
        ("hygienic-names", b"module Module; public Nat Definition(Nat end) { "
         b"let Type = end; return Type; }"),
        ("wide-decimal", b"module M; public Nat F() { return " + b"9" * 256 + b"; }"),
        ("boolean-equality", b"module M; public bool F(bool x) { return x == (false == true); }"),
    )
    result = [Fixture(name, source, "accepted") for name, source in positive]
    for name, source in positive[:6]:
        for suffix, newline in (("lf", b"\n"), ("crlf", b"\r\n"), ("cr", b"\r")):
            edited = b"// caf\xc3\xa9" + newline + source.replace(b"\n", newline) + newline + b"// tail"
            result.append(Fixture(f"{name}-{suffix}-trivia", edited, "accepted"))
    negative = (
        ("return-type", "public Nat F() { return true; }", "type"),
        ("boolean-return", "public bool F() { return 1; }", "type"),
        ("condition-type", "public Nat F() { if (1) { return 0; } else { return 1; } }", "type"),
        ("branch-type", "public Nat F() { if (true) { return 0; } else { return false; } }", "type"),
        ("addition-type", "public Nat F() { return true + 1; }", "type"),
        ("multiply-type", "public Nat F() { return 1 * false; }", "type"),
        ("comparison-type", "public bool F() { return true <= false; }", "type"),
        ("equality-type", "public bool F() { return 0 == false; }", "type"),
        ("argument-type", "public Nat F(Nat x) { return x; } public Nat G() { return F(true); }", "type"),
        ("missing-argument", "public Nat F(Nat x) { return x; } public Nat G() { return F(); }", "type"),
        ("extra-argument", "public Nat F(Nat x) { return x; } public Nat G() { return F(1, 2); }", "type"),
        ("unbound-value", "public Nat F() { return missing; }", "name"),
        ("unbound-call", "public Nat F() { return Missing(); }", "name"),
        ("recursion", "public Nat F(Nat x) { return F(x); }", "name"),
        ("forward-call", "public Nat F() { return G(); } public Nat G() { return 0; }", "name"),
        ("duplicate-function", "public Nat F() { return 0; } public Nat F() { return 1; }", "name"),
        ("duplicate-parameter", "public Nat F(Nat x, Nat x) { return x; }", "name"),
        ("parameter-shadow", "public Nat F(Nat x) { let x = 1; return x; }", "name"),
        ("duplicate-local", "public Nat F() { let x = 1; let x = 2; return x; }", "name"),
        ("self-binding", "public Nat F() { let x = x; return x; }", "name"),
        ("branch-escape", "public Nat F() { if (true) { let x = 1; return x; } else { return x; } }", "name"),
        ("empty-block", "public Nat F() {}", "syntax"),
        ("missing-return", "public Nat F() { let x = 1; }", "syntax"),
        ("missing-semicolon", "public Nat F() { return 1 }", "syntax"),
        ("extra-return", "public Nat F() { return 1; return 2; }", "syntax"),
        ("missing-else", "public Nat F() { if (true) { return 0; } }", "syntax"),
        ("chained-comparison", "public bool F() { return 1 <= 2 <= 3; }", "syntax"),
        ("trailing-token", "public Nat F() { return 1; } garbage", "syntax"),
        ("incomplete-editor-input", "public Nat F() { return (1 +", "syntax"),
        ("unsupported-await", "public Nat F() { return await 1; }", "unsupported"),
        ("unsupported-contract", "public Nat F() requires true { return 1; }", "unsupported"),
    )
    result.extend(Fixture(name, ("module M; " + source).encode(), kind)
                  for name, source, kind in negative)
    prefix = b"module M; public Nat F() { return "
    result.extend((
        Fixture("empty-file", b"", "syntax"),
        Fixture("empty-module", b"module M;", "syntax"),
        Fixture("invalid-utf8", b"// bad \xff\nmodule M;", "encoding"),
        Fixture("oversized-source", b" " * (vela.MAX_SOURCE_BYTES + 1), "limit"),
        Fixture("oversized-literal", prefix + b"9" * 257 + b"; }", "limit"),
        Fixture("deep-group", prefix + b"(" * 2000 + b"0" + b")" * 2000 + b"; }", "limit"),
        Fixture("deep-expression", prefix + b" + ".join([b"1"] * 2000) + b"; }", "limit"),
        Fixture("many-bindings", b"module M; public Nat F() { "
                + b"".join(f"let x{i} = {i}; ".encode() for i in range(1000)) + b"return 0; }", "limit"),
        # Keep the known differing depth conventions observable until disposition.
        Fixture("group-boundary", prefix + b"(" * 62 + b"0" + b")" * 62 + b"; }", "accepted"),
    ))
    # Boundary outcomes independently read by the migration reviewer. Raw syntax
    # budgets must allow these before the consumer applies semantic limits.
    for groups, expected in ((63, "accepted"), (64, "limit")):
        result.append(Fixture(f"group-boundary-{groups}",
                              prefix + b"(" * groups + b"0" + b")" * groups + b"; }", expected))
    for operator in (b"+", b"*"):
        for terms, expected in ((64, "accepted"), (65, "limit")):
            result.append(Fixture(f"operator-boundary-{operator.decode()}-{terms}",
                                  prefix + (b" " + operator + b" ").join([b"1"] * terms) + b"; }", expected))
    for bindings, expected in ((63, "accepted"), (64, "limit")):
        source = (b"module M; public Nat F() { "
                  + b"".join(f"let x{i} = 0; ".encode() for i in range(bindings)) + b"return 0; }")
        result.append(Fixture(f"binding-boundary-{bindings}", source, expected))
    for nesting, expected in ((63, "accepted"), (64, "limit")):
        terminal = b"return 0;"
        for _ in range(nesting):
            terminal = b"if (true) { " + terminal + b" } else { return 1; }"
        result.append(Fixture(f"branch-boundary-{nesting}",
                              b"module M; public Nat F() { " + terminal + b" }", expected))
    for bindings, expected in ((62, "accepted"), (63, "limit")):
        source = (b"module M; public Nat F() { "
                  + b"".join(f"let x{i} = 0; ".encode() for i in range(bindings))
                  + b"if (true) { return 0; } else { return 1; } }")
        result.append(Fixture(f"combined-binding-branch-{bindings}", source, expected))
    terminal = b"return " + b"(" * 63 + b"0" + b")" * 63 + b";"
    for _ in range(63):
        terminal = b"if (true) { " + terminal + b" } else { return 0; }"
    result.append(Fixture("combined-branch-group-boundary",
                          b"module M; public Nat F() { " + terminal + b" }", "accepted"))
    return tuple(result)


def _observe(operation: Callable[[], vela.Translation]) -> dict[str, object]:
    try:
        translation = operation()
    except vela.VelaError as error:
        return {"category": error.kind, "line": error.line, "column": error.column}
    return {"category": "accepted", "module": translation.module,
            "gallina_sha256": hashlib.sha256(translation.gallina.encode()).hexdigest()}


def compare(compiled: vela_parser.Build, cases: tuple[Fixture, ...]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    differences: list[str] = []
    for case in cases:
        baseline = _observe(lambda source=case.source: vela.translate(source))
        native = _observe(lambda source=case.source: vela.translate_ast(source, vela_parser.parse_source(compiled, source)))
        reasons: list[str] = []
        if baseline["category"] != case.expected:
            reasons.append("baseline differs from independent expected category")
        if native["category"] != case.expected:
            reasons.append("generated route differs from independent expected category")
        if baseline["category"] == native["category"] == "accepted" and baseline != native:
            reasons.append("accepted translations differ")
        if case.expected in {"name", "type"} and baseline != native:
            reasons.append("semantic diagnostic location differs")
        if reasons:
            differences.append(case.name)
        rows.append({"name": case.name, "source_sha256": hashlib.sha256(case.source).hexdigest(),
                     "source_bytes": len(case.source), "expected_category": case.expected,
                     "baseline": baseline, "generated": native, "differences": reasons})
    return {"schema": 1, "scope": "vela-development-parser-migration-comparison",
            "status": "differences" if differences else "agreed",
            "checked_parser": False, "python_retired": False,
            "differences": differences, "fixtures": rows}


def _inputs(root: Path) -> dict[str, str]:
    paths = ("tools/vos/vela.py", "tools/vos/vela_ast.py", "tools/vos/vela_migration.py",
             "tools/vela/examples/pure.vela")
    return {**vela_parser._inputs(root),
            **{path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}}


def qualify(root: Path) -> dict[str, object]:
    """Retain all differences; never replace the active prototype parser."""
    latest = vela_parser._work_root(root) / "migration.json"
    latest.unlink(missing_ok=True)
    inputs = _inputs(root)
    syntax = vela_parser.qualify(root)
    receipt = cast("dict[str, object]", syntax["build"])
    directory = Path(cast("str", receipt["directory"]))
    compiled = vela_parser.Build(directory, directory / "vela-parser", receipt)
    report = compare(compiled, fixtures(vela_parser.read_source(root / "tools/vela/examples/pure.vela")))
    if _inputs(root) != inputs or vela_parser._toolchain(root) != receipt["toolchain"]:
        raise ValueError("migration inputs or toolchain changed during comparison")
    outputs = cast("dict[str, str]", receipt["generated_sha256"])
    if any(vela_parser._digest(directory / name) != outputs[name]
           for name in (*vela_parser.GENERATED, "vela-parser")):
        raise ValueError("migration parser output changed during comparison")
    report.update({"inputs": inputs, "build": receipt,
                   "syntax_qualification": str(directory / "qualification.json")})
    with atomic_path(directory / "migration.json") as pending:
        pending.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    with atomic_path(latest) as pending:
        pending.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    return report
