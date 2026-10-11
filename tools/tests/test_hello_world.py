# SPDX-License-Identifier: Apache-2.0
"""M1.7 client evidence controls, especially frame-save false positives, and the
lowering's opam reads, which answer no question."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

from tests import compiler_fixture, test_simulator_build
from tests.harness import Case, ensure
from vos import compiler_provenance, env, receipts


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


def _opam_reads_decline() -> None:
    """Every opam command of the lowering runs through `regenerate._run`, with no
    standard input and no answer from the caller's environment, keeping the root it
    reads: the installed prover's prefix the recipe binds, the switch's prover and
    listing, its library, and a derivation compiled in the switch."""
    recipe = _module()
    lowering = recipe.regenerate
    answers = {"OPAMYES": "1", "OPAMCONFIRMLEVEL": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        prefix = Path(td)
        for name in ("bin/coqc", "bin/coqchk", "bin/rocq", "lib/coq/A.vo",
                     "lib/coq-core/b.cmxs"):
            (prefix / name).parent.mkdir(parents=True, exist_ok=True)
            (prefix / name).write_bytes(name.encode())
        answer = subprocess.CompletedProcess([], 0, stdout=f"{prefix}\n", stderr="")
        with (patch.dict(os.environ, answers),
              patch.object(subprocess, "run", return_value=answer) as launched):
            identity = recipe.lowering_identity()
            lowering.environment()
            lowering.shipped_source()
            lowering.coqc(prefix, "Derived.v")
    commands = [list(call.args[0]) for call in launched.call_args_list]
    ensure(len(identity) == 5 and len(commands) == 5
           and all("opam" in argv for argv in commands)
           and commands[0] == ["opam", "var", f"--switch={lowering.SWITCH}", "prefix"]
           and launched.call_args_list[0].kwargs.get("timeout") == 30,
           f"the recipe and the lowering ran their opam commands: {commands}")
    for call in launched.call_args_list:
        passed = call.kwargs.get("env") or {}
        ensure(call.kwargs.get("stdin") is subprocess.DEVNULL
               and not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
               and passed.get("OPAMROOT") == "/elsewhere",
               f"{call.args[0]} answers no question and keeps the root: {sorted(passed)}")


def _producer_receipts() -> None:
    recipe = _module()
    with tempfile.TemporaryDirectory(prefix="vos-hello-identities-") as name:
        root = Path(name)
        simulator, path, focused = test_simulator_build.fixture(root)
        compiler = compiler_fixture.create(root)
        with (patch.object(recipe, "ROOT", root),
              patch.object(recipe, "COMPILER_SHA256", receipts.digest(compiler))):
            ensure(recipe.accepted_compiler(compiler)[0]["build_receipt"] == "present",
                   "HELLO refused its complete locked compiler")
            result_path = compiler.parent / "build-result.json"
            original = json.loads(result_path.read_text(encoding="utf-8"))
            for role in compiler_provenance.TOOLS:
                for missing in (True, False):
                    record = copy.deepcopy(original)
                    if missing:
                        del record["toolchain"][role]
                    else:
                        record["toolchain"][role]["version"] = "0"
                    receipts.write(result_path, record)
                    try:
                        recipe.accepted_compiler(compiler)
                    except ValueError:
                        continue
                    raise AssertionError("HELLO accepted missing/mismatched compiler identity")
            receipts.write(result_path, original)
        wrong = root / "wrong-ccomp"
        wrong.write_bytes(b"another compiler")
        try:
            recipe.accepted_compiler(wrong)
        except ValueError as err:
            ensure("Q39's locked rebuilt executable" in str(err),
                   "HELLO's wrong-compiler diagnostic does not name the Q39 rebuild")
        else:
            raise AssertionError("HELLO accepted another compiler")
        with patch.object(receipts, "inputs", side_effect=test_simulator_build._inputs):
            receipts.write(path, focused)
            record, selected = recipe.model_receipt(root, simulator, path)
            ensure(record["bundled_model_tests"] == "not-run" and len(selected) == 2,
                   "HELLO's focused route claims complete model acceptance")
            complete: dict[str, Any] = {"schema": 1, "exit_code": 0,
                        "stages": {"configure": 0, "build": 0, "ctest": 0},
                        "identity": {"inputs": selected, "tools": {"/sail": "1" * 64}},
                        "artifacts": {"c_emulator/sail_riscv_sim": receipts.digest(simulator)}}
            receipts.write(path, complete)
            ensure(recipe.model_receipt(root, simulator, path)[0]["stages"] == complete["stages"],
                   "HELLO refused the separate complete receipt route")
            for change in ("ctest-failed", "stages-missing", "tools-missing", "artifact-changed"):
                damaged = copy.deepcopy(complete)
                if change == "ctest-failed":
                    damaged["stages"]["ctest"] = 1
                elif change == "stages-missing":
                    del damaged["stages"]
                elif change == "tools-missing":
                    damaged["identity"]["tools"] = {}
                else:
                    damaged["artifacts"]["c_emulator/sail_riscv_sim"] = "0" * 64
                receipts.write(path, damaged)
                try:
                    recipe.model_receipt(root, simulator, path)
                except ValueError:
                    continue
                raise AssertionError("HELLO confused a partial receipt with complete acceptance")


def cases() -> list[Case]:
    return [Case("client slots exclude frame saves and invalidated values", _client_slots),
            Case("client extraction excludes the external preamble", _preamble_exclusion),
            Case("the lowering's opam reads decline the client's questions",
                 _opam_reads_decline),
            Case("HELLO binds locked compiler and distinguishes model acceptance", _producer_receipts)]
