# SPDX-License-Identifier: Apache-2.0
"""Failure retention and exact-subject controls for native Vela term replay."""

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela_elaboration_check as replay
from vos.vela import VelaError


def _process_controls() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        steps: list[dict[str, object]] = []
        log = directory / "command.log"
        done = subprocess.CompletedProcess(["rocq"], 1, b"partial", b"refused")
        with patch.object(replay.subprocess, "run", return_value=done):
            try:
                replay._run(["rocq"], directory, log, steps)
            except RuntimeError as error:
                ensure("exited 1" in str(error), "compiler failure lost its verdict")
            else:
                raise AssertionError("failed compiler counted as a kernel verdict")
        ensure(log.read_bytes() == b"partialrefused", "compiler failure transcript was lost")
        ensure(steps[0]["status"] == "failed", "compiler failure was not retained")
        with patch.object(replay.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                "rocq", replay.TIMEOUT, output=b"before", stderr=b"timeout")):
            try:
                replay._run(["rocq"], directory, log, steps)
            except RuntimeError as error:
                ensure("exceeded" in str(error), "timeout lost its bounded diagnostic")
            else:
                raise AssertionError("timeout counted as acceptance")
        ensure(steps[-1]["status"] == "timeout", "timeout verdict was not journalled")
        ensure(log.read_bytes() == b"partialrefused", "a later process overwrote earlier evidence")
        ensure(Path(str(steps[-1]["log"])).read_bytes() == b"beforetimeout", "partial timeout output lost")
        with patch.object(replay.subprocess, "run", side_effect=FileNotFoundError("rocq missing")):
            try:
                replay._run(["rocq"], directory, directory / "missing.log", steps)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("missing compiler counted as acceptance")
        ensure(steps[-1]["status"] == "unavailable", "unavailable tooling was not distinguished")


def _semantic_controls() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        compiled = replay.vela_parser.Build(directory, directory / "parser", {})
        fixture = replay.Fixture("wrong-index", b"module M;", "type")
        with patch.object(replay.vela_parser, "parse_source", side_effect=VelaError(
                "syntax", 1, 1, "malformed fixture")):
            try:
                replay._case(compiled, fixture, directory, 0, [])
            except VelaError as error:
                ensure(error.kind == "syntax", "parser failure changed category")
            else:
                raise AssertionError("parse failure satisfied a semantic negative")
        with patch.object(replay.vela_parser, "parse_source", return_value={}), \
                patch.object(replay.vela_elaborate, "elaborate", side_effect=VelaError(
                    "type", 1, 5, "index mismatch")):
            row = replay._case(compiled, fixture, directory, 0, [])
        ensure(row["category"] == "type" and row["column"] == 5, "intended semantic refusal lost")
        for outcome in (VelaError("unsupported", 1, 1, "missing implementation"), None):
            proposed = SimpleNamespace(module="M", gallina="Definition value := 0.\n")
            with patch.object(replay.vela_parser, "parse_source", return_value={}), \
                    patch.object(replay.vela_elaborate, "elaborate", side_effect=outcome,
                                 return_value=proposed):
                try:
                    replay._case(compiled, fixture, directory, 0, [])
                except ValueError as error:
                    ensure("expected type" in str(error), "wrong semantic rejection lost its cause")
                else:
                    raise AssertionError("unrelated refusal or acceptance satisfied a negative")


def _refused_attempts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        latest = directory / "qualification.json"
        latest.write_text('{"status":"passed","stale":true}', encoding="utf-8")
        with patch.object(replay, "_work_root", return_value=directory), \
                patch.object(replay, "_inputs", return_value={}), \
                patch.object(replay, "_toolchain", side_effect=ValueError("wrong locked prover")):
            try:
                replay.qualify(directory)
            except ValueError as error:
                ensure("wrong locked prover" in str(error), "qualification failure was swallowed")
            else:
                raise AssertionError("unsupported prover qualified")
        ensure(not latest.exists(), "stale passing receipt survived a new failed attempt")
        attempts = list(directory.glob("replay-*/attempt.json"))
        ensure(len(attempts) == 1, "failed attempt journal was not retained")
        row = json.loads(attempts[0].read_text(encoding="utf-8"))
        ensure(row["status"] == "failed" and not row["kernel_checked"], "failed replay acquired acceptance")
        ensure("wrong locked prover" in row["error"], "attempt omitted its refusal cause")


def _freshness_controls() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        for name in (*replay.vela_parser.GENERATED, "vela-parser"):
            (directory / name).write_bytes(name.encode())
        outputs = {name: replay._sha256((directory / name).read_bytes())
                   for name in (*replay.vela_parser.GENERATED, "vela-parser")}
        compiled = replay.vela_parser.Build(directory, directory / "vela-parser",
                                            {"generated_sha256": outputs})
        ensure(replay._parser_outputs(compiled) == outputs, "unchanged parser output was refused")
        (directory / "parser.ml").write_bytes(b"changed parser")
        try:
            replay._parser_outputs(compiled)
        except ValueError as error:
            ensure("changed" in str(error), "changed parser lost its refusal")
        else:
            raise AssertionError("stale generated parser was accepted")
        artifact = directory / "Case000.vo"
        artifact.write_bytes(b"checked library")
        rows: list[dict[str, object]] = [{"vo": str(artifact), "vo_sha256": replay._sha256(artifact.read_bytes())}]
        ensure(str(artifact) in replay._observations(rows, []), "checked library not bound in receipt")
        artifact.write_bytes(b"replacement library")
        try:
            replay._observations(rows, [])
        except ValueError as error:
            ensure("changed" in str(error), "changed library lost its refusal")
        else:
            raise AssertionError("replaced checked library was accepted")


def _changed_input_completion() -> None:
    """A late edit refuses final publication even after successful kernel commands."""
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        compiled = replay.vela_parser.Build(directory, directory / "parser", {"toolchain": {}})
        example = replay.Fixture("example", b"module M;")
        row: dict[str, object] = {"category": "accepted", "library": "VelaElaboration.Case000"}
        with patch.object(replay, "_work_root", return_value=directory), \
                patch.object(replay, "_inputs", side_effect=[{"source": "old"}, {"source": "new"}]), \
                patch.object(replay, "_toolchain", return_value={}), \
                patch.object(replay, "_runtime", return_value={}), \
                patch.object(replay, "_parser_outputs", return_value={}), \
                patch.object(replay.vela_parser, "build", return_value=compiled), \
                patch.object(replay.vela_parser, "read_source", return_value=b"module M;"), \
                patch.object(replay, "fixtures", return_value=(example,)), \
                patch.object(replay, "_case", return_value=row), \
                patch.object(replay, "_run", return_value=""):
            try:
                replay.qualify(directory)
            except ValueError as error:
                ensure("changed during" in str(error), "late edit lost its freshness diagnostic")
            else:
                raise AssertionError("changed source acquired a passing replay receipt")
        ensure(not (directory / "qualification.json").exists(), "late edit published acceptance")
        attempts = list(directory.glob("replay-*/attempt.json"))
        ensure(len(attempts) == 1, "late edit attempt journal missing")
        ensure(json.loads(attempts[0].read_text(encoding="utf-8"))["status"] == "failed",
               "late edit retained passing attempt status")


def _native_output_placement() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        for kind in ("", *replay.env.CROSS_OS_FILESYSTEMS, *replay.env.VOLATILE_FILESYSTEMS):
            with patch.object(replay.env, "lane_of", return_value="fixture"), \
                    patch.object(replay.env, "lane_root", return_value=directory), \
                    patch.object(replay.env, "filesystem", return_value=kind):
                try:
                    replay._work_root(directory)
                except ValueError as error:
                    ensure("persistent native" in str(error), "placement refusal lost its purpose")
                else:
                    raise AssertionError(f"unsupported output filesystem accepted: {kind}")


def _pure_routing_and_observations() -> None:
    source = b"module M; public Nat F(Nat value) => value; public const Nat C = 2;"
    translated = replay.vela.translate(source)
    fixture = replay.Fixture("pure-routing", source, pure=True,
                             observations=(("f_F 2", "2"), ("c_C", "2")))
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        compiled = replay.vela_parser.Build(directory, directory / "parser", {})
        commands: list[list[str]] = []

        def command(arguments: list[str], _directory: Path, _log: Path,
                    _steps: list[dict[str, object]]) -> str:
            commands.append(arguments)
            if arguments[-1] == "Case000.v":
                (directory / "Case000.vo").write_bytes(b"kernel fixture")
                return ""
            return "Closed under the global context\n" * 4

        with patch.object(replay.vela_parser, "parse_source", return_value={}) as parse, \
                patch.object(replay.vela, "translate_ast", return_value=translated) as consume, \
                patch.object(replay.vela_elaborate, "elaborate", side_effect=AssertionError("wrong consumer")), \
                patch.object(replay, "_run", side_effect=command):
            row = replay._case(compiled, fixture, directory, 0, [])
        parse.assert_called_once_with(compiled, source, surface=False)
        ensure(consume.call_count == 2, "pure consumer was not checked deterministically")
        ensure(row["consumer"] == "pure" and row["category"] == "accepted"
               and row["assumption_exports"] == ["f_F", "c_C"],
               "pure exports were omitted from the assumption audit")
        generated = (directory / "Case000.v").read_text(encoding="utf-8")
        ensure(generated.startswith(translated.gallina)
               and "Corelib.Init.Logic.eq (Vela_M.f_F 2) (2) := Corelib.Init.Logic.eq_refl (2)." in generated
               and "Corelib.Init.Logic.eq (Vela_M.c_C) (2)" in generated,
               "independent observations were not compiled in the kernel-checked library")
        audit = (directory / "Case000Assumptions.v").read_text(encoding="utf-8")
        ensure("Print Assumptions Case000.Vela_M.f_F." in audit
               and "Print Assumptions Case000.Vela_M.c_C." in audit
               and "Print Assumptions Case000.vela_replay_check_0." in audit
               and "Print Assumptions Case000.vela_replay_check_1." in audit,
               "generated exports or observation proofs escaped the assumption audit")
        ensure(len(commands) == 2 and commands[0][-1] == "Case000.v",
               "observation results used an extra host evaluator")
        with patch.object(replay.vela_parser, "parse_source", return_value={}), \
                patch.object(replay.vela, "translate_ast", return_value=translated), \
                patch.object(replay, "_run", side_effect=RuntimeError("kernel rejected observation")):
            try:
                replay._case(compiled, fixture, directory, 1, [])
            except RuntimeError as error:
                ensure("kernel rejected" in str(error), "observation failure lost its cause")
            else:
                raise AssertionError("a rejected observation acquired acceptance")


def _pure_semantic_negatives_and_inventory() -> None:
    fixture = replay.Fixture("pure-negative", b"module M; public bool F() => !1;", "type", pure=True)
    with tempfile.TemporaryDirectory(prefix="vos-vela-replay-") as temporary:
        directory = Path(temporary)
        compiled = replay.vela_parser.Build(directory, directory / "parser", {})
        with patch.object(replay.vela_parser, "parse_source", return_value={}), \
                patch.object(replay.vela, "translate_ast", side_effect=VelaError("type", 1, 35, "requires bool")), \
                patch.object(replay.vela_elaborate, "elaborate", side_effect=AssertionError("wrong consumer")):
            row = replay._case(compiled, fixture, directory, 0, [])
        ensure(row["category"] == "type" and row["consumer"] == "pure", "pure semantic refusal was lost")
        with patch.object(replay.vela_parser, "parse_source", side_effect=VelaError("syntax", 1, 1, "bad syntax")):
            try:
                replay._case(compiled, fixture, directory, 1, [])
            except VelaError as error:
                ensure(error.kind == "syntax", "parsing refusal changed kind")
            else:
                raise AssertionError("a parsing refusal satisfied a pure semantic negative")
    fixtures = replay.fixtures(b"module M;")
    operators = next(case for case in fixtures if case.name == "pure-expression-operators")
    ensure(operators.pure and ("f_Difference 2 5", "0") in operators.observations
           and ("f_Precedence", "true") in operators.observations
           and ("c_Static", "true") in operators.observations,
           "hosted fixtures lack runtime, static or precedence observations")
    ensure(any(case.name == "pure-skipped-runtime-dependency" and case.pure
               and case.expected == "unsupported" for case in fixtures),
           "hosted replay lost required-static checking of skipped operands")
    for case in fixtures:
        if not case.pure:
            continue
        try:
            replay.vela.translate(case.source)
        except VelaError as error:
            ensure(case.expected != "accepted" and error.kind == case.expected,
                   f"hosted pure fixture {case.name} reached {error.kind}, expected {case.expected}")
        else:
            ensure(case.expected == "accepted", f"hosted semantic negative {case.name} was accepted")


def cases() -> list[Case]:
    return [Case("vela-replay-process-controls", _process_controls),
            Case("vela-replay-semantic-negative-controls", _semantic_controls),
            Case("vela-replay-failed-attempt-retention", _refused_attempts),
            Case("vela-replay-artifact-freshness", _freshness_controls),
            Case("vela-replay-changed-input-completion", _changed_input_completion),
            Case("vela-replay-pure-routing-kernel-observations-and-exports", _pure_routing_and_observations),
            Case("vela-replay-pure-semantic-negatives-and-hosted-inventory", _pure_semantic_negatives_and_inventory),
            Case("vela-replay-native-output-placement", _native_output_placement)]
