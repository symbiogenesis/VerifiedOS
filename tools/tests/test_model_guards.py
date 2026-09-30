# SPDX-License-Identifier: Apache-2.0
"""Failed executions and stale build evidence cannot report model success."""

import argparse
import io
import subprocess
import tempfile
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

from tests.harness import Case, ensure, sandbox_tree
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
            for target in (*(e.build_dir / rel for rel in model.BUILD_ARTIFACTS), elf):
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


def _git(root: Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", *argv],
                   check=True, capture_output=True, timeout=60)


def _pin(root: Path, path: str, commit: str) -> None:
    """Record `path` as a submodule pinned at `commit`, as a gitlink bump leaves it."""
    _git(root, "update-index", "--add", "--cacheinfo", f"160000,{commit},{path}")


_ORACLE_PIN = "1" * 40


def _proof_publication_keeps_build_identity() -> None:
    with sandbox_tree({"model/source.sail": "model bytes\n",
                       "proofs/proof-evidence.json": "old receipt\n"}) as root:
        _pin(root, model.ORACLE_SRC, _ORACLE_PIN)
        _git(root, "commit", "-qm", "fixture")
        e = _environment(root)
        with patch.object(receipts, "executables", return_value={"sail": "compiler bytes"}):
            before = model.build_identity(e)
            receipt = root / "proofs/proof-evidence.json"
            receipt.write_text("new receipt\n", encoding="utf-8")
            ensure(model.build_identity(e) == before,
                   "publishing proof evidence must not stale the completed model build")
            receipt.unlink()
            ensure(model.build_identity(e) == before,
                   "removing a proof output must not change model inputs")
            source = root / "model/source.sail"
            source.write_text("changed model bytes\n", encoding="utf-8")
            ensure(model.build_identity(e) != before,
                   "model source edits must still invalidate the build")
            source.write_text("model bytes\n", encoding="utf-8")
            (root / "model/new.sail").write_text("new model input\n", encoding="utf-8")
            ensure(model.build_identity(e) != before,
                   "new model inputs must still invalidate the build")


def _identity_binds_only_opened_gitlinks() -> None:
    """A pin recorded to be read later is not a model input; the oracle's pin is.

    Tip-tracking an unread reference advances its gitlink without changing anything a
    model command opens, so the build receipt and the evidence inputs must stay current
    across it, while the oracle's own pin, the one submodule a model command reads,
    still moves the identity. The binding stays fail-closed: an index that no longer
    records the oracle as a gitlink is refused rather than dropped from the manifest.
    """
    with sandbox_tree({"model/source.sail": "model bytes\n",
                       ".gitmodules": "[submodule \"upstream/sail-cheri-riscv\"]\n"}) as root:
        _pin(root, model.ORACLE_SRC, _ORACLE_PIN)
        _pin(root, "upstream/llvm-project", "2" * 40)
        _git(root, "commit", "-qm", "fixture")
        e = _environment(root)
        with patch.object(receipts, "executables", return_value={"sail": "compiler bytes"}):
            before = model.build_identity(e)
            inputs = cast("dict[str, str]", before["inputs"])
            ensure(inputs.get(model.ORACLE_SRC) == f"gitlink:{_ORACLE_PIN}"
                   and "upstream/llvm-project" not in inputs and ".gitmodules" in inputs,
                   f"the identity binds the oracle's pin and .gitmodules alone, got {inputs}")
            _pin(root, "upstream/llvm-project", "3" * 40)
            ensure(model.build_identity(e) == before,
                   "advancing a read-later gitlink must leave the build identity unchanged")
            _pin(root, model.ORACLE_SRC, "4" * 40)
            ensure(model.build_identity(e) != before,
                   "advancing the oracle's gitlink must change the build identity")
            _pin(root, model.ORACLE_SRC, _ORACLE_PIN)
            ensure(model.build_identity(e) == before, "restoring the pin restores the identity")
            (root / ".gitmodules").write_text("[submodule \"moved\"]\n", encoding="utf-8")
            ensure(model.build_identity(e) != before, ".gitmodules stays bound")
            _git(root, "update-index", "--force-remove", model.ORACLE_SRC)
            try:
                model.build_identity(e)
            except ValueError as err:
                ensure(model.ORACLE_SRC in str(err), f"the refusal names the gitlink: {err}")
            else:
                raise AssertionError("an identity without the oracle's gitlink was accepted")


def _oracle_fixture(root: Path) -> Path:
    """An oracle source with the two paths `cmd_oracle` requires before it builds."""
    src = root / model.ORACLE_SRC
    (src / "sail-riscv" / "model").mkdir(parents=True)
    (src / "Makefile").write_text("all:\n", encoding="utf-8")
    return src


def _run_oracle(e: env.Environment, sail: str | None, **stubs: object) -> tuple[int, list[list[str]]]:
    """`cmd_oracle` with its lock, stages, copy and suite standing in, so what is held
    is the command line and the tree it builds in rather than an upstream build."""
    staged: list[list[str]] = []

    def stage(name: str, argv: list[str], report_to: object = None, **kwargs: object) -> int:
        staged.append(argv)
        return 0

    fake_env = SimpleNamespace(stage=stage, hold_lock=lambda target, what: io.StringIO(),
                               git_env=env.git_env)
    version = subprocess.CompletedProcess([], 0, "Sail 9.9.9 (fixture)\n", "")
    fake_shutil = SimpleNamespace(which=lambda name: sail if name == "sail" else None)
    with ExitStack() as stack:
        stack.enter_context(patch.object(model, "env", fake_env))
        stack.enter_context(patch.object(model, "shutil", fake_shutil))
        stack.enter_context(patch.object(
            model, "subprocess", SimpleNamespace(run=Mock(return_value=version))))
        stack.enter_context(patch.object(model, "_oracle_suite", return_value=0))
        for name, value in stubs.items():
            stack.enter_context(patch.object(model, name, value))
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(redirect_stderr(io.StringIO()))
        try:
            code = model.cmd_oracle(e, argparse.Namespace(resync=False, timeout=1))
        except SystemExit:
            code = 1
    return code, staged


def _oracle_binds_the_environments_sail() -> None:
    """The oracle is built by the compiler the environment selects, into a tree filed
    under that compiler's edition, and the log says which binary it was."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        e = _environment(root)
        _oracle_fixture(root)
        sail = "/root/.opam/verifiedos-sail-9.9.9-ocaml-5.4.1/bin/sail"
        synced = Mock()
        code, staged = _run_oracle(e, sail, _sync_oracle_tree=synced)
        ensure(code == 0 and len(staged) == 1, f"the fixture build is green, got {code}")
        ensure(f"SAIL={sail}" in staged[0],
               f"make must be handed the environment's sail, got {staged[0]}")
        ensure(synced.call_args.args[1] == e.oracle_root
               and e.oracle_root.parent.name == f"sail-{env.SAIL_VERSION}",
               f"the tree is the edition-keyed one, got {synced.call_args.args[1]}")
        log = e.log("oracle-build").read_text(encoding="utf-8")
        ensure(f"== sail: Sail 9.9.9 (fixture) at {sail}" in log,
               f"the log names the version and the binary that built it, got {log!r}")
        code, staged = _run_oracle(e, None, _sync_oracle_tree=synced)
        ensure(code == 1 and not staged, "with no sail on PATH nothing is built")


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


def _member_terminal_isolation() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        elf = root / "hello.elf"
        terminal = elf.with_suffix(".terminal.log")
        terminal.write_text("stale output", encoding="utf-8")

        def run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
            ensure(not terminal.exists(), "member must remove stale terminal output")
            ensure(argv[argv.index("--terminal-log") + 1] == str(terminal),
                   "member console must be redirected away from the commit trace")
            terminal.write_text("Hello, world!\n", encoding="utf-8")
            return SimpleNamespace(stdout="I 0 0000000080000000 00000013\nSUCCESS\n",
                                   stderr="", returncode=0)

        fake = SimpleNamespace(run=run, TimeoutExpired=subprocess.TimeoutExpired)
        with (patch.object(model, "_missing_simulator", return_value=None),
              patch.object(model, "subprocess", fake)):
            status, _, records = model._run_member(_environment(root), root / "profile", elf, 1)
        ensure(status == "PASS" and records is not None and len(records) == 1,
               "console-producing members must retain every commit record")
        fake.run = Mock(return_value=SimpleNamespace(stdout="SUCCESS\n", stderr="", returncode=1))
        with (patch.object(model, "_missing_simulator", return_value=None),
              patch.object(model, "subprocess", fake)):
            status, _, _ = model._run_member(_environment(root), root / "profile", elf, 1)
        ensure(status == "FAIL", "success text cannot override an abnormal simulator exit")


def cases() -> list[Case]:
    return [Case("solver-failure", _solver_failure), Case("detach-race", _detach_race),
            Case("reference-failure", _reference_failure), Case("stale-build", _stale_build),
            Case("proof-publication-keeps-build-identity", _proof_publication_keeps_build_identity),
            Case("identity-binds-only-opened-gitlinks", _identity_binds_only_opened_gitlinks),
            Case("oracle-binds-the-environments-sail", _oracle_binds_the_environments_sail),
            Case("empty-sweep-refused", _empty_sweep_is_refused),
            Case("warm-test-corpus", _warm_test_corpus),
            Case("invalid-test-corpus-pin", _invalid_test_corpus_pin),
            Case("empty-corpus-refused", _empty_corpus_is_refused),
            Case("member-terminal-isolation", _member_terminal_isolation)]
