# SPDX-License-Identifier: Apache-2.0
"""The model lane's host-testable seams.

`model.py` runs in the guest, but its verdict and seeding machinery is pure: the
build-log reading `wait` stands on (`_report_build` and the one `STAGE_EXIT`
spelling both ends share), the manifest check `corpus` decides per member
(`_check_trace`), the oracle tree's byte-verbatim copy (`_sync_oracle_tree`), and
the two donor-seeding copies a lane stands up from. Held here with fixture logs and
throwaway directories, because a regression in any of them reports the wrong run's
verdict or configures a tree against state it did not produce.

`_configure` is held here too, and at the caller rather than at the composer it calls.
What that line hands its child is the whole of the repair `env.git_overlay` exists for,
and a case that decides the overlay decides nothing about whether the configure passes
it: the defect this repository met lived at this call and not one module over.
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout, suppress
from functools import partial
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast
from unittest.mock import patch

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
        ensure(_tree_bytes(tree) == {str(Path(name)): data for name, data in (
                   ("Makefile", b"all:\r\n\ttrue\r\n"), ("blob.bin", b"\r\n\x00"),
                   ("code.c", b"int f();\r\nint g();\r\n"), ("sub/x.sail", b"val x\r\n"))},
               "every file is copied byte-verbatim: line endings are restored to the "
               "pinned blobs' by _verify_oracle_copy, which knows what they are")
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


def _seed_cache_file() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        bare, warm = root / "bare-cache", root / "warm-cache"
        warm.write_bytes(b"warm-records")

        # the first donor holding one wins, and the lane directory is created for it
        target = root / "lane-x" / "cache"
        _MODEL._seed_cache_file([bare, warm], target)
        ensure(target.read_bytes() == b"warm-records",
               "the cache is copied from the first donor holding one")

        # an existing cache is never overwritten: it is a copy, not a share
        target.write_bytes(b"already-here")
        _MODEL._seed_cache_file([warm], target)
        ensure(target.read_bytes() == b"already-here",
               "a lane holding a cache keeps its own learning")

        # the primary worktree's case, where every donor is its own target, in both
        # states: this is what lets the callers name a donor without asking which
        # worktree they are in
        _MODEL._seed_cache_file([target], target)
        ensure(target.read_bytes() == b"already-here",
               "a donor that is the target leaves it as it is")
        absent = root / "lane-y" / "cache"
        _MODEL._seed_cache_file([absent], absent)
        ensure(not absent.exists(),
               "a donor that is the target and absent creates nothing")

        # no donor holding one is a machine with no warm state to give, not a failure
        cold = root / "lane-z" / "cache"
        _MODEL._seed_cache_file([bare], cold)
        ensure(not cold.exists(), "an absent donor leaves the target cold")


_CORPUS_DIGEST = "ab" * 32
_OTHER_DIGEST = "cd" * 32
_RELEASE = "2031-02-03"


def _corpus_model(root: Path) -> Path:
    """A model root declaring one release and the riscv-tests digest at it."""
    model_root = root / "model"
    declaration = model_root / "test/CMakeLists.txt"
    declaration.parent.mkdir(parents=True, exist_ok=True)
    declaration.write_text(
        f'set(TEST_DOWNLOAD_VERSION "{_RELEASE}" CACHE STRING "tests")\n'
        f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-tests "{_CORPUS_DIGEST}")\n',
        encoding="utf-8", newline="")
    return model_root


def _extracted(tree: Path, files: dict[str, bytes], digest: str = _CORPUS_DIGEST) -> Path:
    """A suite as configure leaves it: its files, and the manifest written beside them."""
    suite = tree / "test" / _RELEASE / "riscv-tests"
    for name, data in files.items():
        (suite / name).parent.mkdir(parents=True, exist_ok=True)
        (suite / name).write_bytes(data)
    _MODEL.corpus_manifest(suite).write_bytes(_MODEL.corpus_listing(suite, digest))
    return suite


def _corpus_listing_format() -> None:
    """The listing is one format with two renderers, `riscv_tests_listing` in
    model/test/CMakeLists.txt and `corpus_listing`, so its bytes are stated here
    rather than derived from either: the digest line, then `<sha256>  <path>` per file,
    ordered by the whole relative path's bytes. `a/b` sorts between `a.c` and `a0`
    because `/` lies between `.` and `0`, which a per-directory walk would not give."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = Path(td) / "riscv-tests"
        files = {"a0": b"zero", "a/b": b"nested", "a.c": b"dot", "a-b": b"dash"}
        for name, data in files.items():
            (suite / name).parent.mkdir(parents=True, exist_ok=True)
            (suite / name).write_bytes(data)

        def line(name: str) -> str:
            return f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n"

        want = (f"tarball riscv-tests.tar.gz sha256 {_CORPUS_DIGEST}\n"
                + line("a-b") + line("a.c") + line("a/b") + line("a0")).encode()
        got = _MODEL.corpus_listing(suite, _CORPUS_DIGEST)
        ensure(got == want, f"the listing's bytes are the stated format, got {got!r}")
        ensure(_MODEL.corpus_manifest(suite) == Path(td) / "riscv-tests.manifest",
               "the manifest sits beside the suite, where no suite glob reaches it")


def _corpus_digests() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        model_root = _corpus_model(Path(td))
        declaration = model_root / "test/CMakeLists.txt"
        valid = declaration.read_text(encoding="utf-8")
        vector = f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-vector-tests-v64x64 "{"0" * 64}")\n'
        other = f'set(TEST_DOWNLOAD_SHA256_2020-01-01_riscv-tests "{"1" * 64}")\n'
        declaration.write_text(valid + vector + other, encoding="utf-8", newline="")
        got = _MODEL.test_corpus_digests(model_root, _RELEASE)
        ensure(got == {"riscv-tests": _CORPUS_DIGEST, "riscv-vector-tests-v64x64": "0" * 64},
               f"every tarball of the release and no other release's, got {got}")
        repeated = valid + f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-tests "{"2" * 64}")\n'
        short = valid + f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-arch-tests "{"3" * 63}")\n'
        upper = valid + f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-arch-tests "{"A" * 64}")\n'
        for text in (repeated, short, upper):
            declaration.write_text(text, encoding="utf-8", newline="")
            try:
                _MODEL.test_corpus_digests(model_root, _RELEASE)
            except ValueError:
                continue
            raise AssertionError(f"a repeated or malformed digest must be refused: {text!r}")


def _verify_test_corpus() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF", "rv64ui-p-add.dump": b"d"})
        _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)

        def refused(why: str, digest: str = _CORPUS_DIGEST) -> None:
            try:
                _MODEL.verify_test_corpus(suite, digest)
            except ValueError as err:
                ensure(why in str(err), f"the refusal names {why!r}, got {err}")
            else:
                raise AssertionError(f"a suite that {why} must be refused")

        refused("disagrees", _OTHER_DIGEST)  # recorded for another tarball digest
        (suite / "rv64ui-p-add").write_bytes(b"\x7fELF tampered")
        refused("disagrees")
        (suite / "rv64ui-p-add").write_bytes(b"\x7fELF")
        (suite / "rv64ui-p-sub").write_bytes(b"not extracted")
        refused("disagrees")
        (suite / "rv64ui-p-sub").unlink()
        (suite / "rv64ui-p-add.dump").unlink()
        refused("disagrees")
        (suite / "rv64ui-p-add.dump").write_bytes(b"d")
        _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)
        _MODEL.corpus_manifest(suite).unlink()
        refused("has no riscv-tests.manifest")

        # a link is never hashed through, even under a manifest crafted to list it
        try:
            (suite / "rv64ui-p-link").symlink_to(suite / "rv64ui-p-add")
        except OSError:
            return  # a Windows host without the symlink privilege; Linux runs it
        _MODEL.corpus_manifest(suite).write_bytes(
            _MODEL.corpus_listing(suite, _CORPUS_DIGEST))
        refused("non-regular")


def _seed_test_data() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor, target = root / "donor", root / "target"
        _extracted(donor, {"rv64ui-p-add": b"\x7fELF"})
        # another release's cache beside it is not a suite of the declared release
        (donor / "test/2020-01-01/riscv-tests").mkdir(parents=True)
        (donor / "test/2020-01-01/riscv-tests/rv64ui-p-add").write_bytes(b"old")

        with redirect_stderr(io.StringIO()) as err:
            _MODEL._seed_test_data([donor], target, model_root)
        suite = target / "test" / _RELEASE / "riscv-tests"
        ensure((suite / "rv64ui-p-add").read_bytes() == b"\x7fELF",
               f"the verified suite is copied into the cold tree, got {err.getvalue()!r}")
        _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)
        ensure(not (target / "test/2020-01-01").exists(),
               "another release's suite is not seeded")
        ensure(sorted(p.name for p in suite.parent.iterdir())
               == ["riscv-tests", "riscv-tests.manifest"],
               "the suite and its manifest land, and no staging copy is left behind")

        # an existing suite directory is left to configure rather than merged into
        marker = suite / "mine.txt"
        marker.write_text("mine\n", encoding="utf-8", newline="")
        _MODEL._seed_test_data([donor], target, model_root)
        ensure(marker.read_text(encoding="utf-8") == "mine\n",
               "a tree that already holds the suite's directory keeps it as it is")


def _seed_test_data_refuses_unverified() -> None:
    """The primary's tree predates the manifest, so it is the case that matters most:
    a donor whose suite does not verify seeds nothing, and configure downloads."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        bare = root / "bare"
        (bare / "test" / _RELEASE / "riscv-tests").mkdir(parents=True)
        (bare / "test" / _RELEASE / "riscv-tests/rv64ui-p-add").write_bytes(b"\x7fELF")
        tampered = root / "tampered"
        (_extracted(tampered, {"rv64ui-p-add": b"\x7fELF"}) / "rv64ui-p-add").write_bytes(
            b"changed after extraction")
        extra = root / "extra"
        (_extracted(extra, {"rv64ui-p-add": b"\x7fELF"}) / "rv64ui-p-sub").write_bytes(
            b"never in the tarball")
        stale = root / "stale"
        _extracted(stale, {"rv64ui-p-add": b"\x7fELF"}, digest=_OTHER_DIGEST)

        for donor, why in ((bare, "has no riscv-tests.manifest"), (tampered, "disagrees"),
                           (extra, "disagrees"), (stale, "disagrees")):
            target = root / f"target-{donor.name}"
            with redirect_stderr(io.StringIO()) as err:
                _MODEL._seed_test_data([donor], target, model_root)
            release = target / "test" / _RELEASE
            ensure(not release.exists() or not any(release.iterdir()),
                   f"the {donor.name} donor must seed nothing and leave no staging copy")
            ensure(why in err.getvalue() and str(donor) in err.getvalue(),
                   f"the refusal names the donor and {why!r}, got {err.getvalue()!r}")

        # a refused donor is passed over for the next one, whose suite verifies
        good = root / "good"
        _extracted(good, {"rv64ui-p-add": b"\x7fELF good"})
        target = root / "target-fallback"
        with redirect_stderr(io.StringIO()):
            _MODEL._seed_test_data([tampered, good], target, model_root)
        suite = target / "test" / _RELEASE / "riscv-tests"
        ensure((suite / "rv64ui-p-add").read_bytes() == b"\x7fELF good",
               "the first donor that verifies seeds the suite")
        _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)


def _seeded_without_copying(donor: Path, model_root: Path) -> None:
    """Seed from `donor`, which holds an entry that is not a regular file under a
    manifest crafted to list it, and hold that nothing is copied or seeded; then seed
    from a clean donor, the positive control, whose suite `copytree` is called for."""
    ensure(_MODEL.corpus_manifest(donor / "test" / _RELEASE / "riscv-tests").is_file(),
           "precondition: the donor's manifest stands, so only the entry's kind decides "
           "the refusal")
    target = donor.parent / f"target-{donor.name}"
    with (patch.object(shutil, "copytree", wraps=shutil.copytree) as copied,
          redirect_stderr(io.StringIO()) as err):
        _MODEL._seed_test_data([donor], target, model_root)
    ensure(not copied.called,
           f"a donor holding a non-regular entry is refused before copytree reads it, "
           f"got {copied.call_args_list}")
    ensure("non-regular" in err.getvalue() and str(donor) in err.getvalue(),
           f"the refusal names the donor and the entry's kind, got {err.getvalue()!r}")
    release = target / "test" / _RELEASE
    ensure(not release.exists() or not any(release.iterdir()), "and nothing is seeded")
    clean = donor.parent / f"clean-{donor.name}"
    _extracted(clean, {"rv64ui-p-add": b"\x7fELF"})
    with patch.object(shutil, "copytree", wraps=shutil.copytree) as copied:
        _MODEL._seed_test_data([clean], donor.parent / f"target-clean-{donor.name}",
                               model_root)
    ensure(copied.call_count == 1,
           f"control: a clean donor's suite is copied, got {copied.call_args_list}")


_DEVICE = "rv64ui-p-device"


def _seed_refuses_a_device_donor() -> None:
    """`shutil.copyfile` refuses a FIFO but reads a character device such as a
    `/dev/zero` node without end, so a donor holding one would stall the lane's first
    build if it were copied before it was verified. A device node cannot be made
    unprivileged, so one is simulated: a regular stand-in that `Path.is_file`, the one
    question the listing asks of an entry that is not a link, answers as not a regular
    file."""
    real = Path.is_file

    def is_file(self: Path, *, follow_symlinks: bool = True) -> bool:
        return self.name != _DEVICE and real(self, follow_symlinks=follow_symlinks)

    with tempfile.TemporaryDirectory(prefix="vos-test-") as td, \
            patch.object(Path, "is_file", is_file):
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "device"
        _extracted(donor, {"rv64ui-p-add": b"\x7fELF", _DEVICE: b""})
        _seeded_without_copying(donor, model_root)


def _seed_refuses_a_fifo_donor() -> None:
    """A real FIFO in a donor is refused before the copy as well. POSIX-only, so the
    case is the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO donor case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "fifo"
        suite = _extracted(donor, {"rv64ui-p-add": b"\x7fELF"})
        os.mkfifo(suite / "rv64ui-p-fifo")
        _MODEL.corpus_manifest(suite).write_bytes(_MODEL.corpus_listing(suite, _CORPUS_DIGEST))
        _seeded_without_copying(donor, model_root)


def _returns(call: Callable[[], None], unblock: Callable[[], None] | None = None,
             within: float = 15.0) -> None:
    """Run `call` on a thread of its own and fail, rather than hang the suite, when it
    has not returned within `within` seconds; what it raises is raised here. `unblock`
    releases a call still waiting at the deadline, so that its thread ends as well."""
    raised: list[BaseException] = []

    def run() -> None:
        try:
            call()
        except BaseException as err:  # raised again on the case's own thread below
            raised.append(err)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(within)
    if worker.is_alive():
        if unblock is not None:
            unblock()
            worker.join(within)
        raise AssertionError(f"the call had not returned after {within:g} s")
    if raised:
        raise raised[0]


def _end_of_file(fifo: Path) -> None:
    """Open and close `fifo`'s write end, which releases a reader waiting to open it and
    hands that reader end of file. With no reader waiting the open is refused, and there
    is nothing to release."""
    with suppress(OSError):
        os.close(os.open(fifo, os.O_WRONLY | getattr(os, "O_NONBLOCK", 0)))


def _manifest_refused(donor: Path, model_root: Path,
                      unblock: Callable[[], None] | None = None) -> None:
    """Seed from `donor`, whose manifest is not a regular file, and hold that the seeding
    returns, names the donor and the manifest's kind, never calls `copytree`, and seeds
    nothing."""
    manifest = _MODEL.corpus_manifest(donor / "test" / _RELEASE / "riscv-tests")
    target = donor.parent / f"target-{donor.name}"
    with (patch.object(shutil, "copytree", wraps=shutil.copytree) as copied,
          redirect_stderr(io.StringIO()) as err):
        _returns(lambda: _MODEL._seed_test_data([donor], target, model_root), unblock)
    said = err.getvalue()
    ensure(f"{manifest} is not a regular file" in said and str(donor) in said,
           f"the refusal names the donor and the manifest's kind, got {said!r}")
    ensure(not copied.called,
           f"a donor whose manifest is not a regular file is refused before copytree, "
           f"got {copied.call_args_list}")
    release = target / "test" / _RELEASE
    ensure(not release.exists() or not any(release.iterdir()), "and nothing is seeded")


def _seed_refuses_a_device_manifest() -> None:
    """A donor whose manifest is a device node is refused by the kind its opened
    descriptor reports, which is the one question the reader asks of it before reading.
    A device node cannot be made unprivileged, so one is simulated: `os` as model.py
    sees it reports the manifest's descriptor as a character device. The positive
    control is the same donor read with the descriptor's own kind, which seeds."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "device-manifest"
        _extracted(donor, {"rv64ui-p-add": b"\x7fELF"})
        manifests: set[int] = set()

        def opened(path: str | Path, flags: int, mode: int = 0o777) -> int:
            fd = os.open(path, flags, mode)
            if str(path).endswith(_MODEL.CORPUS_MANIFEST_SUFFIX):
                manifests.add(fd)
            return fd

        def described(fd: int) -> os.stat_result:
            held = os.fstat(fd)
            if fd not in manifests:
                return held
            manifests.discard(fd)
            return os.stat_result((stat.S_IFCHR | 0o666, *tuple(held)[1:]))

        device = SimpleNamespace(**{**vars(os), "open": opened, "fstat": described})
        with patch.object(_MODEL, "os", device):
            _manifest_refused(donor, model_root)
        target = root / "target-control"
        with patch.object(shutil, "copytree", wraps=shutil.copytree) as copied:
            _returns(lambda: _MODEL._seed_test_data([donor], target, model_root))
        ensure(copied.call_count == 1
               and (target / "test" / _RELEASE / "riscv-tests/rv64ui-p-add").is_file(),
               f"control: the same donor read as it is seeds, got {copied.call_args_list}")


def _seed_refuses_a_fifo_manifest() -> None:
    """A donor whose manifest is a FIFO is refused rather than waited on: opening a FIFO
    for reading waits for a writer, and none comes. POSIX-only, so the case is the
    guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO manifest case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "fifo-manifest"
        manifest = _MODEL.corpus_manifest(_extracted(donor, {"rv64ui-p-add": b"\x7fELF"}))
        manifest.unlink()
        os.mkfifo(manifest)
        _manifest_refused(donor, model_root, partial(_end_of_file, manifest))


def _seed_refuses_a_manifest_linked_to_dev_zero() -> None:
    """A donor whose manifest is a symbolic link to `/dev/zero` is refused before a byte
    of it is read: followed, the link names a device read without end, until the
    `MemoryError` that ends the read, which no refusal of `_seed_test_data` catches.
    POSIX-only, so the case is the guest's."""
    if sys.platform == "win32":
        raise AssertionError("/dev/zero is POSIX-only; the linked manifest case runs in "
                             "the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "linked-manifest"
        manifest = _MODEL.corpus_manifest(_extracted(donor, {"rv64ui-p-add": b"\x7fELF"}))
        manifest.unlink()
        manifest.symlink_to("/dev/zero")
        _manifest_refused(donor, model_root)


# `_configure` in a child of its own, with `env.stage` standing in for the run. Two
# reasons for the child and neither is style: the environment that names a checkout's
# administrative directory is process-global and the runner runs modules in a pool, so
# an override set in-process is set for every module reading the real tree beside it;
# and `stage` itself is unrunnable here, `os.wait4` being POSIX-only and cmake being the
# one thing a test of what cmake is *told* has no business starting.
_CONFIGURE_PROBE = """
import json
import sys
from pathlib import Path

from vos import env
from vos.cli import model

seen = {}


def _record(name, argv, report_to=None, **kw):
    seen["argv"] = argv
    seen["add_env"] = kw.get("add_env")
    return 0


env.stage = _record
root = Path(sys.argv[1])
sail = sys.argv[2] or None
model.shutil.which = lambda name: sail if name == "sail" else None
e = env.Environment(root=root, model=root / "model", build_root=root / "build",
                    log_root=root / "log", lane="probe", cpus=1,
                    mem_available_mb=1024, jobs=1, test_jobs=1)
code = model._configure(e, root / "build" / "tree")
print(json.dumps({"code": code, "argv": seen["argv"], "add_env": seen["add_env"]}))
"""


def _probe_configure(root: Path, admin: Path | None, sail: str = "") -> dict[str, object]:
    declaration = root / "model/test/CMakeLists.txt"
    declaration.parent.mkdir(parents=True, exist_ok=True)
    declaration.write_text('set(TEST_DOWNLOAD_VERSION "2031-02-03" CACHE STRING "tests")\n',
                           encoding="utf-8")
    environment: dict[str, str] = {**os.environ, "PYTHONPATH": str(TOOLS)}
    if admin is None:
        environment.pop("VOS_GIT_DIR", None)
    else:
        environment["VOS_GIT_DIR"] = str(admin)
    done = subprocess.run([sys.executable, "-c", _CONFIGURE_PROBE, str(root), sail],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=120, env=environment)
    ensure(done.returncode == 0,
           f"the configure probe must answer, got {done.returncode} and "
           f"{done.stderr[-400:]!r}")
    return cast("dict[str, object]", json.loads(done.stdout))


def _configure_hands_the_child_the_work_tree() -> None:
    """The one line that decides what a lane's emulator stamps itself with.

    `env.git_overlay`'s own case decides that the pair reports a clean checkout clean
    and an edited one edited. That is a fact about the composer, and the defect was at
    this caller: it spelled `GIT_DIR` out for itself and named no work tree, so the
    overlay could be right and every lane still be stamped `-dirty`. Held here at the
    call, so reverting it to either of the two forms it has had, the one key or no
    environment at all, fails rather than passes.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        admin = root / "administrative"
        admin.mkdir()

        answered = _probe_configure(root, admin)
        argv = cast("list[str]", answered["argv"])
        ensure(argv[0] == "cmake" and str(root / "build" / "tree") in argv,
               f"precondition: the stage under test is the cmake configure, got "
               f"{argv[:4]}")
        ensure("-DTEST_DOWNLOAD_VERSION=2031-02-03" in argv,
               "configure must override a warm cache with the model's current corpus pin")
        overlay = answered["add_env"]
        ensure(overlay == {"GIT_DIR": str(admin), "GIT_WORK_TREE": str(root)},
               f"the configure must hand its child both halves, the work tree being "
               f"the repository root, got {overlay}")

        # and nothing where nothing needs saying: a checkout git resolves by itself
        # gets no environment at all rather than an overlay asserting its own tree
        answered = _probe_configure(root, None)
        ensure(answered["add_env"] is None,
               f"a checkout needing no overlay must be handed none, got "
               f"{answered['add_env']}")


def _configure_binds_the_environments_sail() -> None:
    """A tree configured before a lock change keeps the compiler it first found.

    The model's `find_program` caches `SAIL_BIN` as an absolute path inside the
    switch, and each Sail switch is named by its version, so a configure that names no
    binary leaves an existing tree emitting with the earlier compiler while the log
    and the build identity read the one on `PATH`. Every configure names this
    environment's `sail`, and names none where there is none to name.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        switch = "/root/.opam/verifiedos-sail-9.9.9-ocaml-5.4.1/bin/sail"
        argv = cast("list[str]", _probe_configure(root, None, switch)["argv"])
        ensure(f"-DSAIL_BIN={switch}" in argv,
               f"configure must bind the tree to the environment's sail, got {argv}")
        argv = cast("list[str]", _probe_configure(root, None)["argv"])
        ensure(not any(arg.startswith("-DSAIL_BIN=") for arg in argv),
               f"with no sail on PATH configure must leave the binding to cmake, got {argv}")


# `cmd_emit` in a child, with the lock, the seeding, the stages and the validator
# standing in, over a tree that already has a `build.ninja`: an existing tree is what
# the configure has to rebind.
_EMIT_PROBE = """
import argparse
import json
import sys
from pathlib import Path

from vos import env
from vos.cli import model

stages = []
env.stage = lambda name, argv, report_to=None, **kw: stages.append(name) or 0
env.build_lock = lambda build_dir: None
model._seed_tree = lambda e, build_dir: None
model._require = lambda binary, how: None
model.shutil.which = lambda name: "/opt/sail/bin/sail" if name == "sail" else None
model.config.validate = lambda schema, profile: (0, [])
root = Path(sys.argv[1])
e = env.Environment(root=root, model=root / "model", build_root=root / "build",
                    log_root=root / "log", lane="probe", cpus=1,
                    mem_available_mb=1024, jobs=1, test_jobs=1)
e.build_dir.mkdir(parents=True, exist_ok=True)
(e.build_dir / "build.ninja").write_text("", encoding="utf-8")
code = model.cmd_emit(e, argparse.Namespace())
print(json.dumps({"code": code, "stages": stages}))
"""


def _emit_configures_an_existing_tree() -> None:
    """`emit` configures as `build` does, so an existing tree is rebound too."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        declaration = root / "model/test/CMakeLists.txt"
        declaration.parent.mkdir(parents=True, exist_ok=True)
        declaration.write_text('set(TEST_DOWNLOAD_VERSION "2031-02-03" CACHE STRING "tests")\n',
                               encoding="utf-8")
        environment = {**os.environ, "PYTHONPATH": str(TOOLS)}
        environment.pop("VOS_GIT_DIR", None)
        done = subprocess.run([sys.executable, "-c", _EMIT_PROBE, str(root)],
                              capture_output=True, encoding="utf-8", errors="replace",
                              check=False, timeout=120, env=environment)
        ensure(done.returncode == 0,
               f"the emit probe must answer, got {done.returncode} and {done.stderr[-400:]!r}")
        answered = json.loads(done.stdout.strip().splitlines()[-1])
        ensure(answered == {"code": 0, "stages": ["configure", "emit"]},
               f"emit over an existing tree must configure before it emits, got {answered}")


_PROPERTY_SOURCE = (
    "// a comment\n"
    "$[property]\n"
    "function propOne(c : Capability) -> bool = true\n"
    "\n"
    "function helper(x : int) -> bool = true\n"
    "$[property]\n"
    "// the head may sit under a comment\n"
    "private function propTwo(a : bits(8), b : bits(8)) -> bool = {\n"
    "  a == b\n"
    "}\n"
    "$[test]\n"
    "function not_a_property() -> unit = ()\n"
)


def _property_census() -> None:
    names = _MODEL.property_names(_PROPERTY_SOURCE)
    ensure(names == ["propOne", "propTwo"],
           f"the census is every $[property] head in source order, got {names}")
    ensure(_MODEL.property_names("function f() -> bool = true\n") == [],
           "a source with no mark has an empty census")
    # a mark that names nothing is refused rather than counted or skipped
    for broken in ("$[property]\n", "$[property]\nval f : unit -> bool\n"):
        try:
            _MODEL.property_names(broken)
        except ValueError as defect:
            ensure("no function head" in str(defect), f"the refusal names the defect, got {defect}")
        else:
            raise AssertionError(f"{broken!r} must be refused, not counted")


def _solver_verdicts() -> None:
    # the three verdicts, read off the first line, with the model kept for a sat
    for output, want, rest in (
        ("unsat\n", _MODEL.PROVED, []),
        ("sat\n(\n  (define-fun x () Bool true)\n)\n", _MODEL.COUNTEREXAMPLE,
         ["(", "  (define-fun x () Bool true)", ")"]),
        ("unknown\n", _MODEL.UNDECIDED, []),
        ("timeout\n", _MODEL.UNDECIDED, []),
    ):
        verdict, model = _MODEL.solver_verdict(output)
        ensure(verdict == want and model == rest,
               f"{output!r} must read as {want} with {rest}, got {verdict} {model}")
    # anything else fails closed: a solver that changed its wording is not a proof
    for output in ("", "error: bad input\n", "sat unsat\n", "UNSAT\n", "(model)\nunsat\n"):
        verdict, _ = _MODEL.solver_verdict(output)
        ensure(verdict is None, f"{output!r} must be unrecognized, got {verdict}")


_AUTO_TRANSCRIPT = (
    "Checking counterexample: /root/build/lane-x/smt/model_propOne.smt2\n"
    "Solver could not find counterexample\n"
    "Solver output:\n"
    "unsat\n"
    "Checking counterexample: /root/build/lane-x/smt/model_propTwo.smt2\n"
    "Solver found counterexample: ok\n"
    "  c -> struct { tag = false }\n"
    "Replaying counterexample: ok\n"
    "Checking counterexample: /root/build/lane-x/smt/model_propThree.smt2\n"
    "Unexpected solver output:\n"
    "unsat\n"
    "Checking counterexample: /root/build/lane-x/smt/model_propFour.smt2\n"
)


def _auto_verdicts() -> None:
    got = _MODEL.auto_verdicts(_AUTO_TRANSCRIPT)
    ensure(got == {"propOne": _MODEL.PROVED, "propTwo": _MODEL.COUNTEREXAMPLE,
                   "propThree": _MODEL.UNRECOGNIZED, "propFour": _MODEL.UNRECOGNIZED},
           f"the three shapes Sail prints, and nothing else, decide a verdict; got {got}")
    # the solver's own `unsat` echoed under an unexpected-output line is not a proof
    ensure("propFive" not in _MODEL.auto_verdicts("unsat\nSolver could not find counterexample\n"),
           "a verdict line with no property opened before it names nothing")


def cases() -> list[Case]:
    return [
        Case("property-census", _property_census),
        Case("solver-verdicts", _solver_verdicts),
        Case("auto-verdicts", _auto_verdicts),
        Case("configure-hands-the-work-tree", _configure_hands_the_child_the_work_tree),
        Case("configure-binds-the-environments-sail", _configure_binds_the_environments_sail),
        Case("emit-configures-an-existing-tree", _emit_configures_an_existing_tree),
        Case("stage-exit-spelling", _stage_exit_spelling),
        Case("report-build-verdict", _report_build_verdict),
        Case("report-build-unfinished", _report_build_unfinished),
        Case("report-build-no-log", _report_build_no_log),
        Case("report-build-no-exits", _report_build_no_exits),
        Case("check-trace", _check_trace),
        Case("sync-oracle-tree", _sync_oracle_tree),
        Case("seed-smt-cache", _seed_smt_cache),
        Case("seed-cache-file", _seed_cache_file),
        Case("corpus-listing-format", _corpus_listing_format),
        Case("corpus-digests", _corpus_digests),
        Case("verify-test-corpus", _verify_test_corpus),
        Case("seed-test-data", _seed_test_data),
        Case("seed-test-data-refuses-unverified", _seed_test_data_refuses_unverified),
        Case("seed-refuses-a-device-donor", _seed_refuses_a_device_donor),
        Case("seed-refuses-a-fifo-donor", _seed_refuses_a_fifo_donor, lane="guest"),
        Case("seed-refuses-a-device-manifest", _seed_refuses_a_device_manifest),
        Case("seed-refuses-a-fifo-manifest", _seed_refuses_a_fifo_manifest, lane="guest"),
        Case("seed-refuses-a-manifest-linked-to-dev-zero",
             _seed_refuses_a_manifest_linked_to_dev_zero, lane="guest"),
    ]
