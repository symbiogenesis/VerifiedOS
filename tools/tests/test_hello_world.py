# SPDX-License-Identifier: Apache-2.0
"""M1.7 client evidence controls, especially frame-save false positives."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from tests.harness import Case, ensure


def _module() -> ModuleType:
    directory = Path(__file__).resolve().parents[1] / "bedrock2-lowering"
    spec = importlib.util.spec_from_file_location("hello_world_recipe", directory / "hello.py")
    if spec is None or spec.loader is None:
        raise ValueError("cannot load hello-world recipe")
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    old = sys.modules.get("regenerate")
    try:
        sys.path.insert(0, str(directory))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
        if old is None:
            sys.modules.pop("regenerate", None)
        else:
            sys.modules["regenerate"] = old
    return module


def _client_slots() -> None:
    recipe = _module()
    value = "0123456789ABCDEF"
    write = f"W 0000000080001000 8 1 {value}"
    read = f"R 0000000080001000 8 1 {value}"
    base = 0x80001000
    ensure(recipe.slot_roundtrips([write, read], base, 2) == [base],
           "one client slot is an intact round-trip, not an entire two-slot campaign")
    for records in ([read, write],
                    [write, read.replace(value, "1123456789ABCDEF")],
                    [write, "W 0000000080001007 1 0 00", read],
                    [write, "W 0000000080000FF0 32 0 " + "00" * 32, read],
                    [write.replace("8 1", "8 0"), read],
                    [write, read.replace("8 1", "8 0")]):
        ensure(recipe.slot_roundtrips(records, base, 2) == [],
               "stale, damaged or untagged slots cannot pass")
    ensure(recipe.slot_roundtrips([write, read], base + 0x100, 2) == [],
           "tagged frame saves outside the declared data slots cannot pass")
    ensure(recipe.slot_roundtrips([write, "W 0000000080001008 8 0 " + "00" * 8, read],
                                 base, 2) == [base], "an adjacent slot is disjoint")
    for bad in ("W malformed", "R 0000000080001000 8 1 00"):
        try:
            recipe.slot_roundtrips([write, read, bad], base, 2)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed trailing memory evidence was accepted")


def _preamble_exclusion() -> None:
    recipe = _module()
    body = "uintptr_t hello_char(uintptr_t index) { return index; }\n"
    output = recipe.client_c("#include <string.h>\n/* external preamble */\n" + body,
                             "int main(void) { return 0; }\n")
    ensure(body in output and "external preamble" not in output and "#include" not in output,
           "the printed client body stays verbatim and the upstream preamble stays external")
    for bad in (body + body, body.replace("return index", "return _br2_load(index, 1)"),
                body.replace("hello_char", "renamed")):
        try:
            recipe.client_c(bad, "")
        except ValueError:
            pass
        else:
            raise AssertionError("unqualified client extraction accepted")


def cases() -> list[Case]:
    return [Case("client slots exclude frame saves and invalidated values", _client_slots),
            Case("client extraction excludes the external preamble", _preamble_exclusion)]
