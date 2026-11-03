# SPDX-License-Identifier: Apache-2.0
"""Build and exercise Vela's syntax-only Menhir development parser.

The parser is a native-lane build product. Its JSON syntax tree is no type,
elaboration, checked-parser or source-correspondence verdict.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from filelock import FileLock

from vos import env, vela_surface
from vos.atomic import atomic_path
from vos.jsonutil import finite_float, unique_object
from vos.vela import MAX_SOURCE_BYTES, VelaError
from vos.vela_ast import MAX_SYNTAX_DEPTH

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None

SOURCES = ("ast.ml", "parser.mly", "lexer.mll", "main.ml")
GENERATED = ("parser.ml", "parser.mli", "lexer.ml")
GENERATION_FLAGS = ("--strict", "--infer", "--explain")
BUILD_TIMEOUT = 120
PARSE_TIMEOUT = 15
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
# A syntax edge can add a node object and a child-list container. The response
# envelope, located names and span arrays require the remaining four levels.
MAX_RESPONSE_DEPTH = 2 * MAX_SYNTAX_DEPTH + 4


@dataclass(frozen=True)
class Build:
    directory: Path
    executable: Path
    receipt: dict[str, object]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locked_versions(root: Path) -> dict[str, str]:
    text = (root / "tools/opam/sail.lock").read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for package in ("menhir", "ocaml-base-compiler"):
        versions = set(re.findall(r'"' + re.escape(package) + r'\.([^"\s]+)"', text))
        if len(versions) != 1:
            raise ValueError(f"Sail snapshot must name one {package} version")
        result[package] = versions.pop()
    return result


def _run(arguments: list[str], directory: Path, *, timeout: int = BUILD_TIMEOUT) -> str:
    try:
        done = subprocess.run(arguments, cwd=directory, capture_output=True,
                              text=True, encoding="utf-8", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{arguments[0]} exceeded {timeout} seconds") from error
    if done.returncode:
        detail = (done.stderr or done.stdout).strip()
        raise RuntimeError(f"{arguments[0]} exited {done.returncode}: {detail}")
    return done.stdout.strip()


def _opam(arguments: list[str]) -> list[str]:
    return ["opam", "exec", "--switch", env.SAIL_SWITCH, "--", *arguments]


def _toolchain(root: Path) -> dict[str, object]:
    wanted = _locked_versions(root)
    menhir = _run(_opam(["menhir", "--version"]), root)
    ocaml = _run(_opam(["ocamlc", "-version"]), root)
    lexer = _run(_opam(["ocamllex", "-version"]), root)
    if menhir != f"menhir, version {wanted['menhir']}":
        raise ValueError(f"Menhir identity differs from Sail snapshot: {menhir}")
    if ocaml != wanted["ocaml-base-compiler"]:
        raise ValueError(f"OCaml identity differs from Sail snapshot: {ocaml}")
    if lexer != f"The OCaml lexer generator, version {ocaml}":
        raise ValueError(f"ocamllex identity differs from Sail snapshot: {lexer}")
    binary_dir = Path(_run(["opam", "var", "bin", "--switch", env.SAIL_SWITCH], root))
    if not binary_dir.is_absolute():
        raise ValueError("opam returned a relative tool directory")
    return {"switch": env.SAIL_SWITCH, "menhir": menhir, "ocamlc": ocaml,
            "ocamllex": lexer,
            "binary_sha256": {name: _digest(binary_dir / name)
                              for name in ("menhir", "ocamlc", "ocamllex", "ocamlrun")}}


def _inputs(root: Path) -> dict[str, str]:
    paths = [f"tools/vela/parser/{name}" for name in SOURCES]
    paths.extend(("tools/opam/sail.lock", "tools/vos/vela_parser.py", "tools/vos/vela_surface.py",
                  "tools/vela/examples/pure.vela", "tools/vela/examples/surface.vela",
                  "tools/vela/examples/constants.vela"))
    return {name: _digest(root / name) for name in paths}


def _compile(root: Path, directory: Path, tools: dict[str, object]) -> Build:
    inputs = _inputs(root)
    for name in SOURCES:
        shutil.copyfile(root / "tools/vela/parser" / name, directory / name)
    commands = (["ocamlc", "-c", "ast.ml"],
                ["menhir", *GENERATION_FLAGS, "parser.mly"],
                ["ocamllex", "lexer.mll"],
                ["ocamlc", "-c", "parser.mli"],
                ["ocamlc", "-c", "parser.ml"],
                ["ocamlc", "-c", "lexer.ml"],
                ["ocamlc", "-c", "main.ml"],
                ["ocamlc", "-o", "vela-parser", "ast.cmo", "parser.cmo", "lexer.cmo", "main.cmo"])
    for arguments in commands:
        _run(_opam(arguments), directory)
    if _inputs(root) != inputs:
        raise ValueError("parser inputs changed during the build")
    if _toolchain(root) != tools:
        raise ValueError("parser toolchain changed during the build")
    executable = directory / "vela-parser"
    outputs = {name: _digest(directory / name) for name in (*GENERATED, "vela-parser")}
    receipt: dict[str, object] = {
        "schema": 1, "scope": "vela-syntax-only-development-parser", "status": "built",
        "inputs": inputs, "toolchain": tools, "commands": commands,
        "generated_sha256": outputs, "directory": str(directory),
    }
    with atomic_path(directory / "receipt.json") as pending:
        pending.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")
    return Build(directory, executable, receipt)


def _work_root(root: Path) -> Path:
    directory = env.lane_root(env.lane_of(root)) / "vela-parser"
    kind = env.filesystem(directory)
    if kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS or not kind:
        raise ValueError(f"parser build directory needs a persistent native filesystem: {directory} ({kind})")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build(root: Path) -> Build:
    """Make a fresh build; unsuccessful builds never acquire a passing receipt."""
    directory = _work_root(root)
    with FileLock(directory / "build.lock", timeout=1):
        tools = _toolchain(root)
        output = Path(tempfile.mkdtemp(prefix="build-", dir=directory))
        return _compile(root, output, tools)


def read_source(path: Path) -> bytes:
    with path.open("rb") as stream:
        source = stream.read(MAX_SOURCE_BYTES + 1)
    if len(source) > MAX_SOURCE_BYTES:
        raise VelaError("limit", 1, 1, f"source exceeds {MAX_SOURCE_BYTES} bytes")
    return source


def _object(value: Json, description: str) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError(f"native parser returned invalid {description}")
    return value


def _response(raw: bytes) -> dict[str, Json]:
    """Bound nesting before the JSON decoder, and reject ambiguous objects."""
    quoted, escaped, depth = False, False, 0
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > MAX_RESPONSE_DEPTH:
                raise ValueError("native parser response exceeds JSON nesting bound")
        elif byte in (93, 125):
            depth -= 1

    def reject_constant(value: str) -> Json:
        raise ValueError(f"non-finite native JSON value: {value}")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                           parse_float=finite_float, parse_constant=reject_constant)
        return _object(cast("Json", value), "JSON response")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("native parser returned malformed JSON") from error


def _validate_tree(value: Json, source: bytes) -> None:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("native parser accepted invalid UTF-8 source") from error
    boundaries = {0}
    offset = 0
    for character in text:
        offset += len(character.encode("utf-8"))
        boundaries.add(offset)
    pending = [(value, (0, len(source)), 0)]
    while pending:
        current, parent, depth = pending.pop()
        if isinstance(current, list):
            pending.extend((child, parent, depth) for child in current)
        elif isinstance(current, dict):
            for key in current:
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError as error:
                    raise ValueError("native parser returned a non-Unicode syntax key") from error
            if "kind" in current:
                depth += 1
                if depth > MAX_SYNTAX_DEPTH:
                    raise ValueError("native parser returned excessive syntax depth")
            if "kind" in current or "text" in current:
                span = current.get("span")
                if not isinstance(span, list) or len(span) != 2:
                    raise ValueError("native parser returned an invalid source span")
                start, end = span
                if type(start) is not int or type(end) is not int:
                    raise ValueError("native parser returned an invalid source span")
                if not 0 <= start <= end <= len(source):
                    raise ValueError("native parser returned a source span outside its input")
                if not parent[0] <= start <= end <= parent[1]:
                    raise ValueError("native parser returned a source span outside its parent")
                if start not in boundaries or end not in boundaries:
                    raise ValueError("native parser returned a span splitting a UTF-8 character")
                parent = (start, end)
            pending.extend((child, parent, depth) for child in current.values())
        elif isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("native parser returned a non-Unicode syntax string") from error


def parse_source(compiled: Build, source: bytes, *, surface: bool = False) -> dict[str, Json]:
    """Decode one complete native response, refusing any unsuccessful process."""
    if len(source) > MAX_SOURCE_BYTES:
        raise VelaError("limit", 1, 1, f"source exceeds {MAX_SOURCE_BYTES} bytes")
    outputs = cast("dict[str, str]", compiled.receipt["generated_sha256"])
    if _digest(compiled.executable) != outputs["vela-parser"]:
        raise ValueError("native parser executable changed after its build")
    try:
        arguments = [str(compiled.executable), *(["--surface"] if surface else [])]
        done = subprocess.run(arguments, input=source, capture_output=True,
                              timeout=PARSE_TIMEOUT, check=False)
    except subprocess.TimeoutExpired as error:
        raise VelaError("limit", 1, 1, f"parser exceeded {PARSE_TIMEOUT} seconds") from error
    if len(done.stdout) > MAX_RESPONSE_BYTES or done.stderr:
        raise ValueError("native parser returned excessive output or unexpected standard error")
    response = _response(done.stdout)
    if done.returncode == 1:
        kind, line, column, message = (response.get(key) for key in ("kind", "line", "column", "message"))
        if (set(response) != {"kind", "line", "column", "message"}
                or not isinstance(kind, str) or kind not in {"syntax", "unsupported", "encoding", "limit"}
                or type(line) is not int or type(column) is not int
                or line < 1 or column < 1 or not isinstance(message, str)):
            raise ValueError("native parser returned an invalid refusal")
        try:
            message.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("native parser returned an invalid refusal message") from error
        raise VelaError(cast("str", kind), line, column, message)
    if done.returncode:
        raise RuntimeError(f"native parser exited {done.returncode}")
    ast = _object(response.get("ast"), "syntax tree")
    schema, kind = (2, "surface_file") if surface else (1, "file")
    if (set(response) != {"schema", "ast"} or type(response.get("schema")) is not int
            or response["schema"] != schema or ast.get("kind") != kind):
        raise ValueError("native parser returned an unsupported syntax-tree schema")
    _validate_tree(ast, source)
    return {"schema": schema, "source_sha256": hashlib.sha256(source).hexdigest(), "ast": ast}


def _body(result: dict[str, Json]) -> dict[str, Json]:
    ast = _object(result["ast"], "file")
    functions = ast.get("declarations")
    if not isinstance(functions, list) or not functions:
        raise ValueError("fixture has no function")
    function = _object(functions[0], "function")
    body = _object(function.get("body"), "block")
    terminal = _object(body.get("exit"), "return")
    return _object(terminal.get("value"), "expression")


def _shape(value: dict[str, Json]) -> Json:
    kind = value.get("kind")
    if kind in {"nat", "bool"}:
        return [kind, value.get("value")]
    if kind == "binary":
        operator = _object(value.get("operator"), "operator")
        return [operator.get("text"), _shape(_object(value.get("left"), "left expression")),
                _shape(_object(value.get("right"), "right expression"))]
    if kind == "group":
        return ["group", _shape(_object(value.get("value"), "group expression"))]
    raise ValueError(f"unexpected fixture expression: {kind}")


def _precedence_oracle() -> dict[str, Json]:
    # Authored independently of grammar actions by the contract reviewer.
    return {"kind": "file", "span": [0, 46], "name": {"text": "M", "span": [7, 8]},
            "declarations": [{"kind": "function", "span": [10, 46],
                           "name": {"text": "F", "span": [21, 22]},
                           "result": {"kind": "type", "span": [17, 20], "name": "Nat"},
                           "parameters": [],
                           "body": {"kind": "block", "span": [25, 46], "bindings": [],
                                    "exit": {"kind": "return", "span": [27, 44],
                                             "value": {"kind": "binary", "span": [34, 43],
                                                       "operator": {"text": "+", "span": [36, 37]},
                                                       "left": {"kind": "nat", "span": [34, 35], "value": "1"},
                                                       "right": {"kind": "binary", "span": [38, 43],
                                                                 "operator": {"text": "*", "span": [40, 41]},
                                                                 "left": {"kind": "nat", "span": [38, 39], "value": "2"},
                                                                 "right": {"kind": "nat", "span": [42, 43], "value": "3"}}}}}}]}


def _concise_fixture(compiled: Build) -> str:
    source = (b"// caf\xc3\xa9\r\nmodule Concise;\r\n"
              b"public Nat Add(Nat left, Nat right,) => left + right;\r\n"
              b"public Nat Use() => Add(1, 2,);")
    result = parse_source(compiled, source)
    functions = _object(result["ast"], "concise pure file").get("declarations")
    if not isinstance(functions, list) or len(functions) != 2:
        raise ValueError("concise pure syntax changed declaration boundaries")
    add, use = [_object(value, "concise pure function") for value in functions]
    for function, spelling in ((add, b"=> left + right;"), (use, b"=> Add(1, 2,);")):
        body = _object(function.get("body"), "concise pure body")
        start = source.index(spelling)
        if set(body) != {"kind", "span", "value"} or body.get("kind") != "expression_body" or body.get("span") != [start, start + len(spelling)]:
            raise ValueError("concise pure body lost its value or exact arrow/semicolon span")
    parameters = add.get("parameters")
    if not isinstance(parameters, list) or len(parameters) != 2:
        raise ValueError("pure trailing comma fabricated a parameter")
    for raw, spelling in zip(parameters, (b"Nat left", b"Nat right"), strict=True):
        parameter = _object(raw, "concise pure parameter")
        start = source.index(spelling)
        if parameter.get("span") != [start, start + len(spelling)]:
            raise ValueError("pure trailing comma entered a parameter span")
    call = _object(_object(use.get("body"), "concise call body").get("value"), "concise pure call")
    arguments = call.get("arguments")
    if call.get("kind") != "call" or not isinstance(arguments, list) or len(arguments) != 2:
        raise ValueError("pure trailing comma fabricated an argument or changed call syntax")
    for spelling in (b"F(,)", b"F(Nat x,,)", b"F() => Add(1,,)"):
        invalid = b"module M; public Nat " + spelling
        invalid += b";" if b"=>" in spelling else b" => 0;"
        try:
            parse_source(compiled, invalid)
        except VelaError as error:
            if error.kind != "syntax":
                raise ValueError("malformed concise pure list has wrong refusal") from error
        else:
            raise ValueError("malformed concise pure list unexpectedly parsed")
    return "concise-expression-body-and-lists"


def _constant_callable_fixture(compiled: Build) -> str:
    source = (b"// caf\xc3\xa9\r\nmodule Static;\r\n"
              b"public const Nat Square(Nat value) => value * value;\r\n"
              b"public Nat Scale(const Nat factor, Nat value) { "
              b"const Nat multiplier = Square(factor); return multiplier * value; }\r\n"
              b"public const Nat Answer = Square(4);")
    result = parse_source(compiled, source)
    declarations = _object(result["ast"], "constant callable file").get("declarations")
    if not isinstance(declarations, list) or len(declarations) != 3:
        raise ValueError("constant function changed pure declaration boundaries")
    square, scale, answer = [_object(value, "constant callable declaration") for value in declarations]
    if (square.get("kind") != "function" or square.get("const") is not True
            or scale.get("kind") != "function" or "const" in scale
            or answer.get("kind") != "constant" or "const" in answer):
        raise ValueError("pure constant function/value roles differ from the independent oracle")
    parameters = scale.get("parameters")
    if not isinstance(parameters, list) or len(parameters) != 2:
        raise ValueError("static parameter changed pure callable arity")
    factor, value = [_object(parameter, "pure constant parameter") for parameter in parameters]
    start = source.index(b"const Nat factor")
    if (factor.get("const") is not True or "const" in value
            or factor.get("span") != [start, start + len(b"const Nat factor")]
            or _object(factor.get("type"), "static parameter type").get("span") != [start + 6, start + 9]):
        raise ValueError("pure required-static parameter qualifier or byte spans differ")
    square_parameters = square.get("parameters")
    if (not isinstance(square_parameters, list) or len(square_parameters) != 1
            or "const" in _object(square_parameters[0], "ordinary constant-function input")):
        raise ValueError("constant function incorrectly requires all inputs statically")
    return "compositional-constant-function-and-parameter-roles"


def _fixtures(compiled: Build) -> list[str]:
    """Expected trees selected by the independent grammar reviewer."""
    passed: list[str] = [_concise_fixture(compiled), _constant_callable_fixture(compiled)]
    prefix = b"module M; public Nat F() { return "
    expressions: tuple[tuple[bytes, Json], ...] = (
        (b"1 + 2 * 3", ["+", ["nat", "1"], ["*", ["nat", "2"], ["nat", "3"]]]),
        (b"1 * 2 * 3", ["*", ["*", ["nat", "1"], ["nat", "2"]], ["nat", "3"]]),
        (b"1 + 2 + 3", ["+", ["+", ["nat", "1"], ["nat", "2"]], ["nat", "3"]]),
        (b"(1 + 2) * 3", ["*", ["group", ["+", ["nat", "1"], ["nat", "2"]]], ["nat", "3"]]),
        (b"0001", ["nat", "0001"]),
        (b"0_001", ["nat", "0_001"]),
        (b"1_024 + 2_048", ["+", ["nat", "1_024"], ["nat", "2_048"]]),
        (b"_".join([b"9"] * 256), ["nat", "_".join(["9"] * 256)]),
    )
    for expression, expected in expressions:
        result = parse_source(compiled, prefix + expression + b"; }")
        if _shape(_body(result)) != expected:
            raise ValueError(f"independent AST oracle failed: {expression!r}")
        passed.append(f"expression:{expression.decode()}")
    source = prefix + b"1 + 2 * 3; }"
    baseline = parse_source(compiled, source)
    if baseline["ast"] != _precedence_oracle():
        raise ValueError("complete independent AST/span oracle differs")
    trailing = parse_source(compiled, source + b" \n//comment")
    if baseline["ast"] != trailing["ast"] or baseline["source_sha256"] == trailing["source_sha256"]:
        raise ValueError("trivia changed the AST or failed to change the source binding")
    passed.append("independent-spans-and-trivia")
    utf8 = b"// caf\xc3\xa9\r\nmodule M;\r\npublic Nat F() { return 0001; }\r\n"
    located = parse_source(compiled, utf8)
    if _object(located["ast"], "file").get("span") != [10, 52] or _body(located).get("span") != [45, 49]:
        raise ValueError("UTF-8/CRLF original-byte spans differ")
    passed.append("original-byte-spans")
    source = b"module M; public Nat as(Nat as) { return as; }"
    pure_identifier = parse_source(compiled, source)
    functions = _object(pure_identifier["ast"], "pure file").get("declarations")
    if not isinstance(functions, list) or len(functions) != 1:
        raise ValueError("pure surface-keyword regression lost its function")
    function = _object(functions[0], "pure function named as")
    parameters = function.get("parameters")
    if (_object(function.get("name"), "pure function name").get("text") != "as"
            or not isinstance(parameters, list) or len(parameters) != 1
            or _object(_object(parameters[0], "pure parameter").get("name"), "pure parameter name").get("text") != "as"
            or _object(_body(pure_identifier).get("name"), "pure returned identifier").get("text") != "as"):
        raise ValueError("surface match keyword changed a pure identifier")
    passed.append("pure-identifier-as")
    for word in (b"null",):
        source = b"module M; public Nat " + word + b"(Nat " + word + b") { return " + word + b"; }"
        pure_identifier = parse_source(compiled, source)
        functions = _object(pure_identifier["ast"], "pure file").get("declarations")
        if not isinstance(functions, list) or len(functions) != 1:
            raise ValueError("surface-only reserved word changed pure declaration syntax")
        function = _object(functions[0], "pure reserved-word identifier")
        parameters = function.get("parameters")
        if (_object(function.get("name"), "pure function name").get("text") != word.decode()
                or not isinstance(parameters, list) or len(parameters) != 1
                or _object(_object(parameters[0], "pure parameter").get("name"), "pure parameter name").get("text") != word.decode()
                or _object(_body(pure_identifier).get("name"), "pure returned identifier").get("text") != word.decode()):
            raise ValueError("surface-only reserved word changed pure identifier AST roles")
        passed.append("pure-identifier-" + word.decode())
    # These are deliberately invalid programs accepted as syntax.
    for source in (
            b"module M; public Nat F() { return true + 1; } public Nat F() { return missing; }",
            b"module M; public Nat F() { if (true) { let x = 1; return x; } else { let x = 2; return x; } }",
            b"module M; public Nat F(Nat x, bool b) { return F(x, b); }",
            b"module M; public Nat interface(Nat state) { let register = state; return register; }"):
        parse_source(compiled, source)
    passed.append("syntax-only-and-scoped-constructs")
    for newline in (b"\n", b"\r\n", b"\r"):
        source = b"// caf\xc3\xa9" + newline + b"module M;" + newline + b"public Nat F() { return @; }"
        try:
            parse_source(compiled, source)
        except VelaError as error:
            if (error.kind, error.line, error.column) != ("syntax", 3, 25):
                raise ValueError("newline/UTF-8 diagnostic position differs") from error
        else:
            raise ValueError("invalid character unexpectedly parsed")
    passed.append("newline-and-utf8-comment-positions")
    refusals = (
        (b"module M; public const const Nat F() => 1;", "syntax"),
        (b"module M; public Nat F(const const Nat value) => value;", "syntax"),
        (b"module M; public Nat F(const Nat) => 0;", "syntax"),
        (b"", "syntax"), (b"module M;", "syntax"),
        (prefix + b"1; } garbage", "syntax"),
        (prefix + b"1 == 2 <= 3; }", "syntax"),
        (prefix + b"1; return 2; }", "syntax"),
        (prefix + b"1", "syntax"),
        (prefix + b"await 1; }", "unsupported"),
        (b"module M; public Nat out() => 0;", "unsupported"),
        (b"// invalid \xff\n" + source, "encoding"),
        (prefix + b"9" * 257 + b"; }", "limit"),
        (prefix + b"_".join([b"9"] * 257) + b"; }", "limit"),
        (prefix + b"1__0; }", "syntax"),
        (prefix + b"1_; }", "syntax"),
        (prefix + b"1_Nat; }", "syntax"),
        (prefix + b"(" * 2000 + b"0" + b")" * 2000 + b"; }", "limit"),
        (prefix + b" + ".join([b"1"] * 2000) + b"; }", "limit"),
        (b"module M; public Nat F() { " + b"let x = 1; " * 1000 + b"return 0; }", "limit"),
        (b" " * (MAX_SOURCE_BYTES + 1), "limit"),
    )
    for number, (source, kind) in enumerate(refusals):
        try:
            parse_source(compiled, source)
        except VelaError as error:
            if error.kind != kind:
                raise ValueError(f"refusal fixture {number}: expected {kind}, got {error.kind}") from error
        else:
            raise ValueError(f"refusal fixture {number} unexpectedly parsed")
        passed.append(f"refusal:{number}:{kind}")
    return passed


def qualify(root: Path) -> dict[str, object]:
    latest = _work_root(root) / "qualification.json"
    latest.unlink(missing_ok=True)
    first = build(root)
    second = build(root)
    first_outputs = cast("dict[str, str]", first.receipt["generated_sha256"])
    second_outputs = cast("dict[str, str]", second.receipt["generated_sha256"])
    if first.receipt["inputs"] != second.receipt["inputs"] or first.receipt["toolchain"] != second.receipt["toolchain"]:
        raise ValueError("qualification inputs changed between fresh builds")
    if any(first_outputs[name] != second_outputs[name] for name in GENERATED):
        raise ValueError("fresh parser regeneration changed generated bytes")
    passed = _fixtures(first)
    surface_passed = vela_surface.qualify(lambda source: parse_source(first, source, surface=True))
    example_path = root / "tools/vela/examples/pure.vela"
    example = read_source(example_path)
    parse_source(first, example)
    surface_path = root / "tools/vela/examples/surface.vela"
    surface_example = read_source(surface_path)
    parse_source(first, surface_example, surface=True)
    constant_path = root / "tools/vela/examples/constants.vela"
    constant_example = read_source(constant_path)
    parse_source(first, constant_example)
    parse_source(first, constant_example, surface=True)
    if _inputs(root) != first.receipt["inputs"]:
        raise ValueError("qualification inputs changed after fixtures")
    if _toolchain(root) != first.receipt["toolchain"]:
        raise ValueError("qualification toolchain changed after fixtures")
    for compiled in (first, second):
        outputs = cast("dict[str, str]", compiled.receipt["generated_sha256"])
        if any(_digest(compiled.directory / name) != outputs[name]
               for name in (*GENERATED, "vela-parser")):
            raise ValueError("parser generated output changed after fixtures")
    if read_source(example_path) != example:
        raise ValueError("example changed during qualification")
    if read_source(surface_path) != surface_example:
        raise ValueError("surface example changed during qualification")
    if read_source(constant_path) != constant_example:
        raise ValueError("constant example changed during qualification")
    report: dict[str, object] = {
        "schema": 1, "scope": "vela-syntax-only-development-parser",
        "status": "passed", "checked_parser": False,
        "build": first.receipt, "regeneration": second.receipt,
        "example": {"path": "tools/vela/examples/pure.vela",
                    "source_sha256": hashlib.sha256(example).hexdigest()},
        "constant_example": {"path": "tools/vela/examples/constants.vela",
                             "source_sha256": hashlib.sha256(constant_example).hexdigest()},
        "fixtures": [*passed, "authored-example", "authored-compositional-constants"],
        "syntax_entries": {
            "pure": {"schema": 1, "status": "passed"},
            "surface": {"schema": 2, "status": "passed", "fixtures": surface_passed,
                        "example": {"path": "tools/vela/examples/surface.vela",
                                    "source_sha256": hashlib.sha256(surface_example).hexdigest()}},
        },
    }
    with atomic_path(first.directory / "qualification.json") as pending:
        pending.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")
    with atomic_path(latest) as pending:
        pending.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")
    return report
