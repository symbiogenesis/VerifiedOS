# SPDX-License-Identifier: Apache-2.0
"""Independent comment-attachment, source-binding and live-hover controls."""

import copy
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos.vela import VelaError, inspect_source, translate
from vos.vela_authoring import format_source
from vos.vela_documentation import MAX_DOCUMENTATION_BYTES
from vos.vela_lsp import Server
from vos.vela_lsp_services import InspectionError, project
from vos.vela_source import SourceSnapshot

INDEPENDENT_CASES = True
_URI = "untitled:documentation.vela"
_SOURCE = ("/// Module comment is not an API declaration.\nmodule Docs;\n"
           "/// Configured capacity.\n///  Keep one leading space 😀.\n"
           "public const Nat Base = 2;\n"
           "/// <summary>Returns &amp; preserves the count.</summary>\n"
           "public\nconst Nat Echo(\n    Nat arg)\n{\n    return arg + Base;\n}\n"
           "public Nat Use() => Echo(arg: Base);\n")


def _symbols(raw: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", raw["symbols"])


def _find(raw: dict[str, object], name: str) -> dict[str, object]:
    return next(symbol for symbol in _symbols(raw) if symbol["name"] == name)


def _hover(source: str, line: int, column: int,
           raw: dict[str, object] | None = None) -> dict[str, object]:
    snapshot = SourceSnapshot(_URI, 1, source, 1)
    result = project(snapshot, inspect_source(snapshot.source) if raw is None else raw,
                     "textDocument/hover", (line, column))
    ensure(isinstance(result, dict), f"expected hover at {(line, column)}: {result!r}")
    return cast("dict[str, object]", result)


def _contents(hover: dict[str, object]) -> str:
    contents = cast("dict[str, object]", hover["contents"])
    ensure(contents["kind"] == "plaintext", "documentation became active markup")
    return cast("str", contents["value"])


def _attachment_and_original_bytes() -> None:
    raw = inspect_source(_SOURCE.encode())
    base = _find(raw, "Base")
    expected = {"text": "Configured capacity.\n Keep one leading space 😀.",
                "span": [len(_SOURCE[:_SOURCE.index("/// Configured")].encode()),
                         len(_SOURCE[:_SOURCE.index("\npublic const")].encode())],
                "declaration": len(_SOURCE[:_SOURCE.index("public const")].encode())}
    ensure(base.get("documentation") == expected,
           f"capacity documentation lost content or original-byte spans: {base!r}")
    echo = _find(raw, "Echo")
    ensure(cast("dict[str, object]", echo.get("documentation"))["text"]
           == "<summary>Returns &amp; preserves the count.</summary>",
           "XML-looking text was decoded, expanded or discarded")
    ensure("documentation" not in _find(raw, "arg")
           and "documentation" not in _find(raw, "Use"),
           "declaration documentation leaked to a parameter or later declaration")
    ensure("Module comment" not in str(raw), "orphan module documentation became API facts")
    # Comments change exact provenance, while generated definitions remain equal.
    without = "\n".join(line for line in _SOURCE.split("\n") if not line.startswith("///"))
    def definitions(source: str) -> str:
        return translate(source.encode()).gallina.split("\n", 2)[2]

    ensure(definitions(_SOURCE) == definitions(without), "documentation changed emitted definitions")


def _breaks_and_multiline_declarations() -> None:
    for interruption in ("\n", "// ordinary comment\n", "// /// ordinary comment\n"):
        source = "module M;\n/// Orphan.\n" + interruption + "public Nat F() => 1;\n"
        ensure("documentation" not in _find(inspect_source(source.encode()), "F"),
               f"documentation crossed an attachment break: {interruption!r}")
    same_line = "module M; /// Not standalone.\npublic Nat F() => 1;\n"
    ensure("documentation" not in _find(inspect_source(same_line.encode()), "F"),
           "a trailing line comment attached as declaration documentation")
    for newline in ("\n", "\r\n", "\r"):
        source = newline.join(("module M;", "  /// 😀 One.", "\t/// Two\u2028still one line.",
                               "public", "// inside the declaration", "Nat", "F() => 1;"))
        raw = inspect_source(source.encode())
        doc = cast("dict[str, object]", _find(raw, "F")["documentation"])
        ensure(doc["text"] == "😀 One.\nTwo\u2028still one line.",
               f"comment normalization changed UTF-8 text for {newline!r}")
        ensure("😀 One." in _contents(_hover(source, 6, 0, raw)),
               "multiline declaration lost its parser-owned start site")


def _declaration_and_reference_hovers() -> None:
    expected = "Configured capacity.\n Keep one leading space 😀."
    declaration = _hover(_SOURCE, 4, 17)
    reference = _hover(_SOURCE, 10, 17)
    ensure(_contents(declaration) == _contents(reference)
           and expected in _contents(reference) and "unqualified" in _contents(reference),
           "reference hover did not use the declaration's documentation")
    ensure(declaration["range"] != reference["range"], "documentation replaced selected occurrence ranges")
    ensure("Returns &amp; preserves" in _contents(_hover(_SOURCE, 12, 20)),
           "function reference omitted authored documentation text")


def _forged_and_stale_documentation() -> None:
    source = "module M;\n/// First.\npublic Nat One() => 1;\npublic Nat Two() => One();\n"
    original = inspect_source(source.encode())
    variants: list[dict[str, object]] = []
    for field, value in (("text", "Forged."), ("span", [0, 3]), ("span", [True, 3]),
                         ("declaration", -1), ("declaration", True)):
        raw = copy.deepcopy(original)
        cast("dict[str, object]", _find(raw, "One")["documentation"])[field] = value
        variants.append(raw)
    raw = copy.deepcopy(original)
    _find(raw, "Two")["documentation"] = copy.deepcopy(_find(raw, "One")["documentation"])
    variants.append(raw)
    raw = copy.deepcopy(original)
    cast("dict[str, object]", _find(raw, "One")["documentation"])["extra"] = 0
    variants.append(raw)
    for raw in variants:
        try:
            _hover(source, 2, 11, raw)
        except InspectionError:
            continue
        raise AssertionError(f"forged documentation reached hover: {raw!r}")
    try:
        _hover(source.replace("First.", "Other."), 2, 11, original)
    except InspectionError:
        pass
    else:
        raise AssertionError("old comment facts survived changed source bytes")


def _documentation_bounds_and_invalid_sources() -> None:
    source = "module M;\n/// " + "x" * MAX_DOCUMENTATION_BYTES + "\npublic Nat F() => 1;"
    doc = cast("dict[str, object]", _find(inspect_source(source.encode()), "F")["documentation"])
    ensure(len(cast("str", doc["text"]))
           == MAX_DOCUMENTATION_BYTES, "exact documentation bound was refused or truncated")
    translate(source.replace("/// x", "/// xx").encode())
    try:
        inspect_source(source.replace("/// x", "/// xx").encode())
    except VelaError as error:
        ensure(error.kind == "inspection-limit", "oversized documentation got a semantic verdict")
    else:
        raise AssertionError("oversized documentation inspection succeeded")
    for body in ("public Nat F() => missing;", "public Nat F() => true;",
                 "public owned Nat F() => 1;"):
        try:
            inspect_source(("module M;\n/// No accepted facts.\n" + body).encode())
        except VelaError:
            continue
        raise AssertionError("invalid source published documentation facts")


def _declaration_kind_source_binding() -> None:
    source = ("module K;\r\n/// Stored.\npublic const Nat Value // before initializer\r\n = 7;\r"
              "/// Callable.\npublic const Nat Get // before parameters\n () => Value;")
    original = inspect_source(source.encode())
    ensure("Stored." in _contents(_hover(source, 2, 17, original))
           and "Callable." in _contents(_hover(source, 5, 17, original)),
           "legitimate constant and const function documentation lost its declaration kind")
    for name, kind, detail, position in (
            ("Value", "function", "public const Nat Value()", (2, 17)),
            ("Get", "constant", "const Nat Get", (5, 17))):
        raw = copy.deepcopy(original)
        symbol = _find(raw, name)
        symbol.update(kind=kind, detail=detail)
        try:
            _hover(source, *position, raw)
        except InspectionError:
            continue
        raise AssertionError(f"forged declaration kind reused documentation for {name}")


def _unicode_documentation_byte_bound() -> None:
    text = "😀" * (MAX_DOCUMENTATION_BYTES // 4 - 1) + "\nabc"
    ensure(len(text.encode()) == MAX_DOCUMENTATION_BYTES,
           "independent Unicode fixture does not reach the UTF-8 byte boundary")
    source = "module M;\r\n" + "\r\n".join("/// " + line for line in text.split("\n"))
    source += "\r\npublic Nat F() => 1;"
    raw = inspect_source(source.encode())
    ensure(cast("dict[str, object]", _find(raw, "F")["documentation"])["text"] == text
           and text in _contents(_hover(source, 3, 11, raw)),
           "exact UTF-8 bound changed Unicode text or counted authored CRLF bytes")
    oversized = source.replace("/// abc", "/// abcd")
    translate(oversized.encode())
    try:
        inspect_source(oversized.encode())
    except VelaError as error:
        ensure(error.kind == "inspection-limit", "Unicode overflow received a semantic verdict")
    else:
        raise AssertionError("Unicode documentation was bounded by characters instead of UTF-8 bytes")


def _use_site_comments_and_formatting_attachment() -> None:
    source = ("/// Orphan module text.\r\nmodule Preserve;\r"
              "/// Configured 😀.\npublic const Nat Size=2;\r\n"
              "/// Callable description.\rpublic Nat Echo(Nat arg){\n"
              "/// Local documentation stays a comment.\nlet local=arg;return local;}\n"
              "/// Broken by a blank line.\n\npublic Nat Use(Nat input){\n"
              "/// Use-site text does not document Echo.\nreturn Echo(input)+Size;}")
    expected = {"Size": "Configured 😀.", "Echo": "Callable description."}
    for current in (source, format_source(source.encode()).decode()):
        raw = inspect_source(current.encode())
        actual = {cast("str", symbol["name"]): cast("dict[str, object]", symbol["documentation"])["text"]
                  for symbol in _symbols(raw) if "documentation" in symbol}
        ensure(actual == expected,
               f"formatting changed attachment or promoted orphan/local/use-site comments: {actual!r}")
        normalized = current.replace("\r\n", "\n").replace("\r", "\n")
        prefix = normalized[:normalized.index("Echo(input)")]
        line, column = prefix.count("\n"), len(prefix.rsplit("\n", 1)[-1])
        contents = _contents(_hover(current, line, column, raw))
        ensure("Callable description." in contents and "Use-site text" not in contents,
               "reference hover selected nearby comments instead of declaration documentation")


def _orphan_documentation_budget() -> None:
    oversized = "/// " + "x" * (MAX_DOCUMENTATION_BYTES + 1)
    for source in (oversized + "\nmodule M;\npublic Nat F() => 1;",
                   "module M;\n" + oversized + "\n\npublic Nat F() => 1;",
                   "module M;\n" + oversized + "\n// break\npublic Nat F() => 1;"):
        raw = inspect_source(source.encode())
        ensure("documentation" not in _find(raw, "F"),
               "an orphan comment consumed or bypassed the attached-documentation budget")


def _message(method: str, params: object = None, identity: int | None = None) -> dict[str, object]:
    result = {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}
    if identity is not None:
        result["id"] = identity
    return result


def _position() -> dict[str, object]:
    return {"textDocument": {"uri": _URI}, "position": {"line": 3, "character": 22}}


def _edited_overlay() -> None:
    source = "module Live;\n/// Old 😀.\npublic Nat Echo(Nat arg) => arg;\npublic Nat Use() => Echo(1);"
    server = Server(checker=lambda _: None, inspector=inspect_source)
    server.handle(_message("initialize", identity=1))
    server.handle(_message("initialized"))
    server.handle(_message("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": source}}))
    before = server.handle(_message("textDocument/hover", _position(), 2))[0]
    ensure("Old 😀." in _contents(cast("dict[str, object]", before["result"])),
           "initial overlay documentation was absent")
    server.handle(_message("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
        "contentChanges": [{"range": {"start": {"line": 1, "character": 4},
                                      "end": {"line": 1, "character": 7}}, "text": "New"}]}))
    changed = server.handle(_message("textDocument/hover", _position(), 3))[0]
    ensure("New 😀." in _contents(cast("dict[str, object]", changed["result"]))
           and "Old" not in str(changed), "incremental edit reused old documentation")
    server.handle(_message("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 3},
        "contentChanges": [{"range": {"start": {"line": 1, "character": 0},
                                      "end": {"line": 1, "character": 3}}, "text": "//"}]}))
    removed = server.handle(_message("textDocument/hover", _position(), 4))[0]
    ensure("New" not in str(removed), "ordinary comment retained cached declaration documentation")


def _real_stdio_documentation() -> None:
    source = "module Wire;\r\n/// Documented 😀.\r\npublic Nat Echo(Nat arg) => arg;\r\npublic Nat Use() => Echo(1);"
    messages = [_message("initialize", identity=1), _message("initialized"),
                _message("textDocument/didOpen", {"textDocument": {
                    "uri": _URI, "languageId": "vela", "version": 1, "text": source}}),
                _message("textDocument/hover", _position(), 2),
                _message("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
                    "contentChanges": [{"text": source.replace("Documented 😀.", "Changed 😀.")}]}),
                _message("textDocument/hover", _position(), 3),
                _message("shutdown", identity=4), _message("exit")]
    wire = bytearray()
    for message in messages:
        body = json.dumps(message, ensure_ascii=False).encode()
        wire.extend(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.cli.vela_lsp import main; raise SystemExit(main())")
    done = subprocess.run([sys.executable, "-I", "-c", script], input=bytes(wire),
                          capture_output=True, timeout=30, check=False)
    ensure(done.returncode == 0 and done.stderr == b"", f"documentation stdio failed: {done.stderr!r}")
    replies: dict[int, dict[str, object]] = {}
    versions: list[object] = []
    stream = BytesIO(done.stdout)
    while header := stream.readline():
        ensure(header.startswith(b"Content-Length: ") and stream.readline() == b"\r\n",
               "documentation reply lost length framing")
        body = stream.read(int(header[len(b"Content-Length: "):].strip()))
        reply = cast("dict[str, object]", json.loads(body))
        if "id" in reply:
            replies[cast("int", reply["id"])] = reply
        else:
            publication = cast("dict[str, object]", reply["params"])
            ensure(publication["diagnostics"] == [], "comment edit changed checking result")
            versions.append(publication["version"])
    ensure(set(replies) == {1, 2, 3, 4} and versions == [1, 2],
           "documentation wire session lost requests or overlay versions")
    ensure("Documented 😀." in _contents(cast("dict[str, object]", replies[2]["result"]))
           and "Changed 😀." in _contents(cast("dict[str, object]", replies[3]["result"]))
           and "Documented" not in str(replies[3]), "wire hover reused stale documentation")


def cases() -> list[Case]:
    return [Case("attachment-and-original-byte-witnesses", _attachment_and_original_bytes),
            Case("attachment-breaks-multiline-and-newlines", _breaks_and_multiline_declarations),
            Case("declaration-reference-documentation-hovers", _declaration_and_reference_hovers),
            Case("forged-and-stale-documentation-refusal", _forged_and_stale_documentation),
            Case("bounded-documentation-and-invalid-programs", _documentation_bounds_and_invalid_sources),
            Case("documentation-declaration-kind-source-binding", _declaration_kind_source_binding),
            Case("unicode-documentation-byte-boundary", _unicode_documentation_byte_bound),
            Case("use-site-comments-and-formatting-attachment", _use_site_comments_and_formatting_attachment),
            Case("orphan-documentation-does-not-consume-presentation-budget", _orphan_documentation_budget),
            Case("incremental-documentation-invalidation", _edited_overlay),
            Case("real-stdio-documentation-and-edit", _real_stdio_documentation)]
