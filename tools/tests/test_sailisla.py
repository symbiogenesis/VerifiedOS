# SPDX-License-Identifier: Apache-2.0
"""Strict witness/replay accounting and control classification without native tools."""

import io
import json
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import sailisla
from vos.cli import sail_isla


def _reject(call: Callable[[], object]) -> None:
    try:
        call()
    except sailisla.IslaError:
        return
    raise AssertionError("incomplete or ambiguous evidence must be refused")


def _witnesses() -> None:
    local = "\n".join(f"Result: #b{code << 12 | code:017b}" for code in reversed(range(16)))
    found = sailisla.parse_symbolic(local, 0)
    ensure(found == {code: code for code in range(16)}, "witness values and inputs must survive parsing")
    global_rows = "\n".join(f"Result: #b{code << 12 | code:017b}" for code in range(16, 32))
    ensure(len(sailisla.parse_symbolic(global_rows, 1)) == 16, "global half is a distinct domain")
    for malformed in (local.rsplit("\n", 1)[0], local + "\n" + local.splitlines()[0],
                      local.replace("Result: #b", "Result: #x", 1),
                      local + "\nError: assertion failed", global_rows):
        _reject(lambda text=malformed: sailisla.parse_symbolic(text, 0))


def _replay_roster() -> None:
    ensure(sailisla.parse_cases("case 2 6 2\ncase 1 2 1\n", {1, 2}) == [
        {"code": 1, "expanded": 2, "narrowed": 1}, {"code": 2, "expanded": 6, "narrowed": 2}],
        "replay must return deterministic numeric ordering")
    for invalid in ("case 1 2 1\n", "case 1 2 1\ncase 1 2 1",
                    "case 1 4096 1\ncase 2 6 2", "case 1 2 32\ncase 2 6 2",
                    "case 1 -1 1\ncase 2 6 2", "case 1 2 1\ncase 3 6 2",
                    "case 1 2 1\ncase 2 6 2\nhelper failed"):
        _reject(lambda text=invalid: sailisla.parse_cases(text, {1, 2}))


def _controls() -> None:
    baseline: list[sailisla.Case] = [{"code": 1, "expanded": 2, "narrowed": 1}]
    defect: list[sailisla.Case] = [{"code": 1, "expanded": 6, "narrowed": 1}]
    log = Path("control.log")
    killed = sailisla.control_result("semantic-defect", baseline, defect, log)
    ensure(killed["status"] == "killed" and killed["mismatches"] == [1],
           "compiled semantic differences are kills")
    survivor = sailisla.control_result("outside-scope", baseline, baseline, log)
    ensure(survivor["status"] == "survived" and not survivor["mismatches"],
           "an undetected compiled defect is a survivor")
    rejected = sailisla.control_result("rejected-build", baseline, None, log)
    ensure(rejected["status"] == "build_rejected" and not rejected["mismatches"],
           "a failed build must not improve the kill count")
    _reject(lambda: sailisla.control_result("partial", baseline, [], log))


def _mutation_anchors() -> None:
    ensure(sailisla._mutate("prefix OLD suffix", "OLD", "NEW") == "prefix NEW suffix",
           "control staging must preserve unrelated source text")
    _reject(lambda: sailisla._mutate("absent", "OLD", "NEW"))
    _reject(lambda: sailisla._mutate("OLD OLD", "OLD", "NEW"))


def _download_digest() -> None:
    with sandbox_tree({}) as root:
        destination = root / "tool.tar"
        with patch.object(sailisla.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
            _reject(lambda: sailisla._download("https://example.invalid/tool", "0" * 64, destination))
        ensure(not destination.exists() and not destination.with_suffix(".tar.part").exists(),
               "a mismatched download must not become an installable archive")


def _report() -> dict[str, Any]:
    return {
        "version": 1, "advisory_only": True, "notice": sailisla.NOTICE, "passed": True,
        "source_sha256": {"model.sail": "a" * 64}, "tool_sha256": {"sail": "b" * 64},
        "assets_sha256": "c" * 64, "ir_sha256": "d" * 64,
        "cases": [{"code": code, "expanded": code, "narrowed": code} for code in range(32)],
        "symbolic_paths": [16, 16], "baseline_matches": 32, "testgen_matches": 32,
        "controls": [
            {"name": "semantic-defect", "status": "killed", "mismatches": [1], "log": "kill.log"},
            {"name": "outside-scope", "status": "survived", "mismatches": [], "log": "survive.log"},
            {"name": "rejected-build", "status": "build_rejected", "mismatches": [], "log": "reject.log"}],
        "invocations": [], "directory": "/native/campaign",
    }


def _schema() -> None:
    schema = json.loads((TOOLS / "sail-isla/report.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    report = _report()
    validator.validate(report)
    report["advisory_only"] = False
    ensure(bool(list(validator.iter_errors(report))), "report must retain the advisory boundary")
    report = _report()
    report["cases"].pop()
    ensure(bool(list(validator.iter_errors(report))), "partial case reports must fail the schema")
    report = _report()
    report["controls"][2]["status"] = "killed-by-compilation"
    ensure(bool(list(validator.iter_errors(report))), "schema must distinguish rejected builds")


def _cli() -> None:
    for error in (sailisla.IslaError("missing witnesses"), OSError("missing tools")):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(sail_isla.env, "load"),
              patch.object(sail_isla.sailisla, "qualify", side_effect=error),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            code = sail_isla.main(["qualify", "--json"])
        ensure(code == 1 and not stdout.getvalue() and str(error) in stderr.getvalue(),
               "failed generation must not emit a partial JSON success")
    report = _report()
    report["passed"] = False
    stdout = io.StringIO()
    with (patch.object(sail_isla.env, "load"),
          patch.object(sail_isla.sailisla, "qualify", return_value=report),
          redirect_stdout(stdout)):
        code = sail_isla.main(["qualify", "--json"])
    ensure(code == 1 and json.loads(stdout.getvalue())["passed"] is False,
           "unexpected completed control outcomes need a nonzero status and explicit verdict")


def _harness_uses_model() -> None:
    text = sailisla.harness([3, 9])
    ensure("0b00011" in text and "0b01001" in text and "0b00000" not in text,
           "only generated witness inputs belong in the replay harness")
    ensure("perms_expand(code)" in text and "perms_narrow(expanded)" in text,
           "the harness must call curated functions rather than embed expected answers")


def cases() -> list[Case]:
    return [Case("symbolic-completeness-and-uniqueness", _witnesses),
            Case("replay-exact-roster", _replay_roster),
            Case("defect-control-classification", _controls),
            Case("mutation-unique-anchors", _mutation_anchors),
            Case("download-digest-refusal", _download_digest),
            Case("versioned-json-schema", _schema),
            Case("cli-refuses-partial-verdict", _cli),
            Case("oracle-replays-generated-inputs", _harness_uses_model)]
