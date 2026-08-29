# SPDX-License-Identifier: Apache-2.0
"""The model lane's host-testable seams.

`model.py` runs in the guest, but its verdict and seeding machinery is pure: the
build-log reading `wait` stands on (`_report_build` and the one `STAGE_EXIT`
spelling both ends share), the manifest check `corpus` decides per member
(`_check_trace`), the oracle tree's copy-and-normalize (`_sync_oracle_tree`), and
the two donor-seeding copies a lane stands up from. Held here with fixture logs and
throwaway directories, because a regression in any of them reports the wrong run's
verdict or configures a tree against state it did not produce.
"""

import importlib.util
import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos import differential


def _load_model() -> ModuleType:
    """model.py from its own path: the file is importable by name too, but loading it
    from the path pins exactly which file this module is testing."""
    spec = importlib.util.spec_from_file_location(
        "model", TOOLS / "vos" / "cli" / "model.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no import spec for {TOOLS / 'model.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODEL = _load_model()


def _stage_exit_spelling() -> None:
    # One regex serves both ends: cmd_build writes `<STAGE>_EXIT=<code>` and
    # _report_build reads the verdict back out of it.
    for line, code in (("CONFIGURE_EXIT=0", "0"), ("BUILD_EXIT=12", "12"),
                       ("CTEST_EXIT=2", "2")):
        found = _MODEL.STAGE_EXIT.match(line)
        ensure(found is not None and found.group(1) == code,
               f"{line!r} must carry exit {code}")
    for line in ("STAGE build wall=1.0s cpu=99% maxrss=1kB", " CONFIGURE_EXIT=0",
                 "CONFIGURE_EXIT=0 ", "ALL_DONE", "EXIT=1"):
        ensure(_MODEL.STAGE_EXIT.match(line) is None,
               f"{line!r} must not read as a stage exit")


def _report(text: str | None) -> tuple[int, str, str]:
    """_report_build over a fixture log, its prints captured off this run's stdout."""
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        log = Path(td) / "model-build.log"
        if text is not None:
            log.write_text(text, encoding="utf-8", newline="")
        with redirect_stdout(out), redirect_stderr(err):
            # cast because a module loaded from a path answers `Any` for every
            # attribute, and the tuple below states what the seam really returns
            code = cast("int", _MODEL._report_build(log))
    return code, out.getvalue(), err.getvalue()


_GREEN_LOG = (
    "== sail: Sail 0.20.2\n"
    "== lane: primary in /root/build/verifiedos-model\n"
    "ninja: some build noise the report must not echo\n"
    "STAGE configure wall=1.0s cpu=99% maxrss=1kB\n"
    "CONFIGURE_EXIT=0\n"
    "STAGE build wall=2.0s cpu=98% maxrss=2kB\n"
    "BUILD_EXIT=0\n"
    "STAGE ctest wall=3.0s cpu=97% maxrss=3kB\n"
    "CTEST_EXIT=0\n"
    "ALL_DONE\n"
)


def _report_build_verdict() -> None:
    code, out, _ = _report(_GREEN_LOG)
    ensure(code == 0, f"a green log's verdict is its last stage exit, got {code}")
    ensure("noise" not in out and "CONFIGURE_EXIT=0" in out and "STAGE build" in out
           and "== sail: Sail 0.20.2" in out,
           f"only the frame lines are echoed, got {out!r}")

    # the verdict is the LAST *_EXIT before ALL_DONE, because cmd_build stops at the
    # first stage that fails
    failed = _GREEN_LOG.replace("CTEST_EXIT=0", "CTEST_EXIT=2")
    code, _, _ = _report(failed)
    ensure(code == 2, f"the last stage exit is the verdict, got {code}")


def _report_build_unfinished() -> None:
    # No ALL_DONE means killed or still starting: a finding, not a silence, even
    # when every stage recorded so far exited 0.
    truncated = _GREEN_LOG.removesuffix("ALL_DONE\n")
    code, _, err = _report(truncated)
    ensure(code == 1 and "carries no ALL_DONE" in err,
           f"an unfinished log must report itself, got {code}, {err!r}")


def _report_build_no_log() -> None:
    code, _, err = _report(None)
    ensure(code == 1 and "nothing has built in this lane" in err,
           f"an absent log must say nothing has built, got {code}, {err!r}")


def _report_build_no_exits() -> None:
    # ALL_DONE with no stage exits at all cannot be read as success.
    code, _, _ = _report("== sail: Sail 0.20.2\nALL_DONE\n")
    ensure(code == 1, f"a log with no stage exits has no green to report, got {code}")


def _check_trace() -> None:
    member = differential.Member("m1", "m1.asm", checks=3, records=10, digest="abcd")
    verdict, detail = _MODEL._check_trace(member, (3, 10, "abcd"))
    ensure((verdict, detail) == ("PASS", " (3 checks, 10 records)"),
           f"a matching trace must pass, got {verdict}{detail}")

    verdict, detail = _MODEL._check_trace(member, (3, 10, "eeee"))
    ensure(verdict == "FAIL" and "eeee" in detail and "abcd" in detail,
           f"a digest mismatch must name both digests, got {verdict}{detail}")

    verdict, detail = _MODEL._check_trace(member, (4, 10, "abcd"))
    ensure(verdict == "FAIL" and "4 checks against the manifest's 3" in detail,
           f"a check-count drift must name both counts, got {verdict}{detail}")

    blank = differential.Member("m2", "m2.asm", checks=3, records=10, digest="")
    verdict, detail = _MODEL._check_trace(blank, (3, 10, "abcd"))
    ensure(verdict == "FAIL" and "no trace digest in the manifest" in detail,
           f"an unrecorded digest must fail rather than pass vacuously, got {verdict}{detail}")


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _sync_oracle_tree() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        src = Path(td) / "src"
        (src / "sub").mkdir(parents=True)
        (src / ".git").mkdir()
        (src / ".git" / "config").write_bytes(b"[core]\r\n")
        (src / "code.c").write_bytes(b"int f();\r\nint g();\r\n")
        (src / "Makefile").write_bytes(b"all:\r\n\ttrue\r\n")
        (src / "sub" / "x.sail").write_bytes(b"val x\r\n")
        (src / "blob.bin").write_bytes(b"\r\n\x00")

        tree = Path(td) / "tree"
        _MODEL._sync_oracle_tree(src, tree)
        ensure((tree / "code.c").read_bytes() == b"int f();\nint g();\n"
               and (tree / "Makefile").read_bytes() == b"all:\n\ttrue\n"
               and (tree / "sub" / "x.sail").read_bytes() == b"val x\n",
               "CRLF must be normalized out of every text kind the build reads")
        ensure((tree / "blob.bin").read_bytes() == b"\r\n\x00",
               "a file outside the text kinds is copied byte-verbatim")
        ensure(not (tree / ".git").exists(),
               ".git is dropped: a copy of it describes a repository it is not in")

        # a second sync over the standing tree lands on the same bytes
        first = _tree_bytes(tree)
        _MODEL._sync_oracle_tree(src, tree)
        ensure(_tree_bytes(tree) == first, "a re-sync must be byte-stable")


def _seed_smt_cache() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        bare, warm, target = root / "bare", root / "warm", root / "target"
        (warm / "model").mkdir(parents=True)
        (warm / "model" / "sail_smt_cache").write_bytes(b"warm-records")

        # the first donor that has a cache wins; a donor without one is passed over
        _MODEL._seed_smt_cache([bare, warm], target)
        ensure((target / "model" / "sail_smt_cache").read_bytes() == b"warm-records",
               "the cache is copied from the first donor holding one")

        # an existing cache is never overwritten: it is a copy, not a share
        (target / "model" / "sail_smt_cache").write_bytes(b"already-here")
        _MODEL._seed_smt_cache([warm], target)
        ensure((target / "model" / "sail_smt_cache").read_bytes() == b"already-here",
               "a tree that has a cache keeps it")


def _seed_test_data() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        donor, target = root / "donor", root / "target"
        suite = donor / "test" / "first_party" / "riscv-tests"
        suite.mkdir(parents=True)
        (suite / "rv64ui-p-add.elf").write_bytes(b"\x7fELF")

        _MODEL._seed_test_data([donor], target)
        ensure((target / "test" / "first_party" / "riscv-tests"
                / "rv64ui-p-add.elf").read_bytes() == b"\x7fELF",
               "the downloaded suite is copied into the cold tree")

        # an existing suite directory is left alone rather than merged into
        marker = target / "test" / "first_party" / "mine.txt"
        marker.write_text("mine\n", encoding="utf-8", newline="")
        _MODEL._seed_test_data([donor], target)
        ensure(marker.read_text(encoding="utf-8") == "mine\n"
               and (target / "test" / "first_party" / "riscv-tests").exists(),
               "a tree that already holds the suite's directory keeps it as it is")


def cases() -> list[Case]:
    return [
        Case("stage-exit-spelling", _stage_exit_spelling),
        Case("report-build-verdict", _report_build_verdict),
        Case("report-build-unfinished", _report_build_unfinished),
        Case("report-build-no-log", _report_build_no_log),
        Case("report-build-no-exits", _report_build_no_exits),
        Case("check-trace", _check_trace),
        Case("sync-oracle-tree", _sync_oracle_tree),
        Case("seed-smt-cache", _seed_smt_cache),
        Case("seed-test-data", _seed_test_data),
    ]
