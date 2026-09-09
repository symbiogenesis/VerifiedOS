# SPDX-License-Identifier: Apache-2.0
"""Failed executions and stale build evidence cannot report model success."""

import argparse
import io
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.harness import Case, ensure
from vos import env, receipts
from vos.cli import model


def _environment(root: Path) -> env.Environment:
    return env.Environment(root, root / "model", root / "build", root / "logs",
                           "", 4, 4096, 2, 2)


def _solver_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / f"{model.SMT_PREFIX}_probe.smt2").write_text("(check-sat)\n", encoding="utf-8")
        for code, stdout, stderr in ((1, "unsat\n", "failure"),
                                     (0, "unsat\n(error bad)\n", ""),
                                     (0, "unsat\n", "unexpected diagnostic")):
            fake = SimpleNamespace(run=Mock(return_value=subprocess.CompletedProcess(
                [], code, stdout, stderr)), TimeoutExpired=subprocess.TimeoutExpired)
            with patch.object(model, "subprocess", fake), redirect_stdout(io.StringIO()):
                result = model._solve_each(root, ["probe"], 1, _environment(root))
            ensure(result == 1, "an unsuccessful or malformed solver execution cannot prove")


def _detach_race() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        log = Path(td) / "build.log"
        log.write_text("previous", encoding="utf-8")

        def started(*args: object, **kwargs: object) -> SimpleNamespace:
            log.write_text("child completed", encoding="utf-8")
            return SimpleNamespace(pid=123)

        fake = SimpleNamespace(Popen=started, DEVNULL=subprocess.DEVNULL)
        with patch.object(model, "subprocess", fake), redirect_stdout(io.StringIO()):
            code = model._detach(argparse.Namespace(fast=False), log, None)
        ensure(code == 0 and log.read_text(encoding="utf-8") == "child completed",
               "a child that writes before Popen returns must retain its log")
        fake.Popen = Mock(side_effect=OSError("launch failed"))
        with patch.object(model, "subprocess", fake), redirect_stderr(io.StringIO()):
            code = model._detach(argparse.Namespace(fast=False), log, None)
        ensure(code == 1 and log.read_text(encoding="utf-8") == "child completed",
               "failed launch must preserve previous evidence")


def _reference_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        e = _environment(root)
        e.simulator.parent.mkdir(parents=True)
        e.simulator.write_bytes(b"simulator")
        harness = e.build_dir / "test/unit_tests/unit_tests"
        harness.parent.mkdir(parents=True)
        harness.write_bytes(b"harness")
        info = subprocess.CompletedProcess([], 0, "Sail RISC-V git: pinned\n", "")
        failed = subprocess.CompletedProcess([], 1, "Testing broken\n", "failed")
        fake = SimpleNamespace(run=Mock(side_effect=[info, failed]),
                               TimeoutExpired=subprocess.TimeoutExpired)
        corpus = SimpleNamespace(members=[], version=1)
        with (patch.object(model, "subprocess", fake),
              patch.object(model, "differential", SimpleNamespace(load=lambda root: corpus)),
              redirect_stderr(io.StringIO())):
            ensure(model.cmd_reference(e, argparse.Namespace()) == 1,
                   "attempted properties from a failed harness must not become evidence")


def _stale_build() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        e = _environment(root)
        e.log_dir.mkdir()
        log = e.log("model-build")
        log.write_text("ALL_DONE\n", encoding="utf-8")
        for rel in model.BUILD_ARTIFACTS:
            path = e.build_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"artifact")
        elf = e.build_dir / "test/version/riscv-tests/rv64ui-p-add"
        elf.parent.mkdir(parents=True)
        elf.write_bytes(b"test program")
        identity = {"inputs": {"source": "hash"}}
        receipts.write(log.with_suffix(".json"), {
            "schema": 1, "exit_code": 0,
            "stages": {"configure": 0, "build": 0, "ctest": 0},
            "identity": identity, "artifacts": model.build_artifacts(e.build_dir),
            "log_sha256": receipts.digest(log),
        })
        with patch.object(model, "build_identity", return_value=identity):
            model.verified_build(e)
            for target in (e.simulator, elf):
                original = target.read_bytes()
                target.write_bytes(b"replaced")
                try:
                    model.verified_build(e)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"replacing {target.name} did not invalidate its receipt")
                target.write_bytes(original)
            extra = elf.with_name("rv64ui-p-new")
            extra.write_bytes(b"new test program")
            try:
                model.verified_build(e)
            except ValueError:
                pass
            else:
                raise AssertionError("adding a sweep input did not invalidate its receipt")
            extra.unlink()
            elf.unlink()
            try:
                model.verified_build(e)
            except ValueError:
                return
        raise AssertionError("removing every sweep input must invalidate its receipt")


def _empty_sweep_is_refused() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        e = _environment(Path(td))
        e.simulator.parent.mkdir(parents=True)
        e.simulator.write_bytes(b"unused simulator")
        suite = e.build_dir / "test/version/riscv-tests"
        suite.mkdir(parents=True)
        # A dump and another width's program are not runnable members of this selection.
        (suite / "rv64ui-p-add.dump").write_bytes(b"dump")
        (suite / "rv32ui-p-add").write_bytes(b"other width")
        fake = SimpleNamespace(run=Mock(side_effect=AssertionError("executed an empty suite")))
        with (patch.object(model, "subprocess", fake), redirect_stderr(io.StringIO()),
              redirect_stdout(io.StringIO()) as output):
            code = model.cmd_sweep(e, argparse.Namespace(xlen="64", timeout=1))
        ensure(code == 1 and "TOTAL" not in output.getvalue(),
               "an empty selected sweep cannot report successful execution evidence")


def _empty_corpus_is_refused() -> None:
    fake = SimpleNamespace(load=Mock(return_value=SimpleNamespace(members=[])))
    with (patch.object(model, "differential", fake), redirect_stderr(io.StringIO()),
          redirect_stdout(io.StringIO()) as output):
        code = model.cmd_corpus(_environment(Path("unused")), argparse.Namespace())
    ensure(code == 1 and "TOTAL" not in output.getvalue(),
           "an empty differential corpus cannot report successful execution evidence")


def cases() -> list[Case]:
    return [Case("solver-failure", _solver_failure), Case("detach-race", _detach_race),
            Case("reference-failure", _reference_failure), Case("stale-build", _stale_build),
            Case("empty-sweep-refused", _empty_sweep_is_refused),
            Case("empty-corpus-refused", _empty_corpus_is_refused)]
