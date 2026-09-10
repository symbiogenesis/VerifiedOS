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


def _corpus_fixture(e: env.Environment) -> Path:
    declaration = e.model / "test/CMakeLists.txt"
    declaration.parent.mkdir(parents=True, exist_ok=True)
    declaration.write_text('set(TEST_DOWNLOAD_VERSION "2031-02-03" CACHE STRING "tests")\n',
                           encoding="utf-8")
    suite = e.build_dir / "test/2031-02-03/riscv-tests"
    suite.mkdir(parents=True, exist_ok=True)
    return suite


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
        elf = _corpus_fixture(e) / "rv64ui-p-add"
        elf.write_bytes(b"test program")
        identity = {"inputs": {"source": "hash"}}
        receipts.write(log.with_suffix(".json"), {
            "schema": 1, "exit_code": 0,
            "stages": {"configure": 0, "build": 0, "ctest": 0},
            "identity": identity, "artifacts": model.build_artifacts(e.build_dir, e.model),
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
        suite = _corpus_fixture(e)
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


def _warm_test_corpus() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        e = _environment(Path(td))
        current = _corpus_fixture(e) / "rv64ui-p-add"
        current.write_bytes(b"current")
        for version in ("2020-01-01", "2040-01-01"):
            stale = e.build_dir / "test" / version / "riscv-tests/rv64ui-p-add"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"different release")
        ensure(model.sweep_inputs(e.build_dir, e.model) == [current],
               "sweep must select the declaration, regardless of donor cache sort order")
        e.oracle.parent.mkdir(parents=True, exist_ok=True)
        e.oracle.write_bytes(b"unused oracle")
        args = argparse.Namespace(elf=[], corpus=True, limit=1, timeout=1)
        with (patch.object(model, "_missing_simulator", return_value=None),
              patch.object(model, "_run_trace", return_value=[]) as runner,
              redirect_stdout(io.StringIO())):
            ensure(model.cmd_trace_diff(e, args) == 0, "empty traces are skipped")
            ensure(runner.call_count == 1 and runner.call_args.args[0][-1] == str(current),
                   "trace-diff must use the same declared release as sweep")
        current.unlink()
        current.parent.rmdir()
        try:
            model.sweep_inputs(e.build_dir, e.model)
        except ValueError as err:
            ensure("2031-02-03" in str(err), "missing corpus must name its required release")
        else:
            raise AssertionError("missing current corpus must never fall back to donor data")
        with (patch.object(model, "_missing_simulator", return_value=None),
              patch.object(model, "_run_trace") as runner, redirect_stderr(io.StringIO())):
            ensure(model.cmd_trace_diff(e, args) == 1 and not runner.called,
                   "trace-diff must refuse a missing current corpus before execution")


def _invalid_test_corpus_pin() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        e = _environment(Path(td))
        _corpus_fixture(e)
        declaration = e.model / "test/CMakeLists.txt"
        valid = declaration.read_text(encoding="utf-8")
        malformed = valid.replace("2031-02-03", "../old")
        for text in ("", valid + valid, malformed, valid + malformed):
            declaration.write_text(text, encoding="utf-8")
            try:
                model.test_corpus_version(e.model)
            except ValueError:
                pass
            else:
                raise AssertionError("a missing, duplicate or malformed corpus pin must fail")


def cases() -> list[Case]:
    return [Case("solver-failure", _solver_failure), Case("detach-race", _detach_race),
            Case("reference-failure", _reference_failure), Case("stale-build", _stale_build),
            Case("empty-sweep-refused", _empty_sweep_is_refused),
            Case("warm-test-corpus", _warm_test_corpus),
            Case("invalid-test-corpus-pin", _invalid_test_corpus_pin),
            Case("empty-corpus-refused", _empty_corpus_is_refused)]
