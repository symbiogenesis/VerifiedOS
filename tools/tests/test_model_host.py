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

import argparse
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import (
    ExitStack,
    contextmanager,
    nullcontext,
    redirect_stderr,
    redirect_stdout,
    suppress,
)
from functools import partial
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import IO, Self, cast
from unittest.mock import Mock, patch

from tests.harness import TOOLS, Case, ensure
from vos import differential, env
from vos.cli import evidence


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


def _verified_inputs_are_the_suites_top_level_programs() -> None:
    """The inputs chosen from a suite that verified are the files at its top whose names
    the pattern matches, each with the digest its verification read: not the `.dump`
    disassembly beside one, which the pattern matches too, and not a file in a
    subdirectory, whose path the pattern also matches since a glob's `*` matches `/`."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF", "rv64ui-p-add.dump": b"d",
                                      "rv64ui-p-dir/rv64ui-p-nested": b"\x7fELF n"})
        verified = _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)
        chosen = _MODEL._verified_inputs(verified, "rv64ui-p-*")
    ensure(chosen == {suite / "rv64ui-p-add": hashlib.sha256(b"\x7fELF").hexdigest()},
           f"only the top-level program is an input, got {chosen}")


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


@contextmanager
def _copies_spied() -> Iterator[Mock]:
    """`_copy_regular_file` as it is, with the calls the seeding makes of it recorded."""
    with patch.object(_MODEL, "_copy_regular_file",
                      wraps=_MODEL._copy_regular_file) as copied:
        yield copied


def _seeded_without_copying(donor: Path, model_root: Path) -> None:
    """Seed from `donor`, which holds an entry that is not a regular file under a
    manifest crafted to list it, and hold that nothing is copied or seeded; then seed
    from a clean donor, the positive control, whose one file is copied."""
    ensure(_MODEL.corpus_manifest(donor / "test" / _RELEASE / "riscv-tests").is_file(),
           "precondition: the donor's manifest stands, so only the entry's kind decides "
           "the refusal")
    target = donor.parent / f"target-{donor.name}"
    with _copies_spied() as copied, redirect_stderr(io.StringIO()) as err:
        _MODEL._seed_test_data([donor], target, model_root)
    ensure(not copied.called,
           f"a donor holding a non-regular entry is refused before any file of it is "
           f"copied, got {copied.call_args_list}")
    ensure("non-regular" in err.getvalue() and str(donor) in err.getvalue(),
           f"the refusal names the donor and the entry's kind, got {err.getvalue()!r}")
    release = target / "test" / _RELEASE
    ensure(not release.exists() or not any(release.iterdir()), "and nothing is seeded")
    clean = donor.parent / f"clean-{donor.name}"
    _extracted(clean, {"rv64ui-p-add": b"\x7fELF"})
    with _copies_spied() as copied:
        _MODEL._seed_test_data([clean], donor.parent / f"target-clean-{donor.name}",
                               model_root)
    ensure(copied.call_count == 1,
           f"control: a clean donor's file is copied, got {copied.call_args_list}")


_DEVICE = "rv64ui-p-device"


def _seed_refuses_a_device_donor() -> None:
    """A character device such as a `/dev/zero` node is read without end, so a donor
    holding one would stall the lane's first build if it were read, and the donor is
    refused before the copy. A device node cannot be made unprivileged, so one is
    simulated: a regular stand-in that `Path.is_file`, the first question the listing
    asks of an entry that is not a link, answers as not a regular file."""
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
    returns, names the donor and the manifest's kind, copies no file, and seeds
    nothing."""
    manifest = _MODEL.corpus_manifest(donor / "test" / _RELEASE / "riscv-tests")
    target = donor.parent / f"target-{donor.name}"
    with _copies_spied() as copied, redirect_stderr(io.StringIO()) as err:
        _returns(lambda: _MODEL._seed_test_data([donor], target, model_root), unblock)
    said = err.getvalue()
    ensure(f"{manifest} is not a regular file" in said and str(donor) in said,
           f"the refusal names the donor and the manifest's kind, got {said!r}")
    ensure(not copied.called,
           f"a donor whose manifest is not a regular file is refused before any file is "
           f"copied, got {copied.call_args_list}")
    release = target / "test" / _RELEASE
    ensure(not release.exists() or not any(release.iterdir()), "and nothing is seeded")


def _os_with_a_device(named: Callable[[str], bool]) -> SimpleNamespace:
    """`os` as model.py sees it, except that a descriptor opened on a path `named`
    accepts reports itself a character device the first time it is asked. A device node
    cannot be made unprivileged, and the kind the opened descriptor reports is the one
    question model.py asks of a file before reading it."""
    devices: set[int] = set()

    def opened(path: str | Path, flags: int, mode: int = 0o777) -> int:
        fd = os.open(path, flags, mode)
        if named(str(path)):
            devices.add(fd)
        return fd

    def described(fd: int) -> os.stat_result:
        held = os.fstat(fd)
        if fd not in devices:
            return held
        devices.discard(fd)
        return os.stat_result((stat.S_IFCHR | 0o666, *tuple(held)[1:]))

    return SimpleNamespace(**{**vars(os), "open": opened, "fstat": described})


def _open_regular_asks_the_name_first() -> None:
    """`_open_regular` opens nothing its name reports as another kind than a regular
    file, since opening a device node can act on the device, and hands back a
    descriptor only on the very file the name reported. A device node cannot be made
    unprivileged, so the name's answer is simulated: a character device, which is never
    opened, and a regular file on another inode, a file replaced after its name was
    asked, which is opened and refused. The positive control is the same file asked as
    it is, which opens. `O_NONBLOCK`, `O_NOFOLLOW`, `O_NOCTTY` and `O_BINARY` ride every
    open where the platform defines them."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "rv64ui-p-add"
        path.write_bytes(b"\x7fELF")
        opened: list[str] = []

        def recorded(named: str | Path, flags: int, mode: int = 0o777) -> int:
            opened.append(str(named))
            return os.open(named, flags, mode)

        def answering(kind: int, inode_shift: int = 0) -> SimpleNamespace:
            def lstat(named: str | Path) -> os.stat_result:
                held = tuple(os.lstat(named))
                return os.stat_result((kind | stat.S_IMODE(held[0]), held[1] + inode_shift,
                                       *held[2:]))
            return SimpleNamespace(**{**vars(os), "open": recorded, "lstat": lstat})

        for kind, shift, why in ((stat.S_IFCHR, 0, "a device is refused unopened"),
                                 (stat.S_IFREG, 1, "another file is refused once opened")):
            opened.clear()
            with patch.object(_MODEL, "os", answering(kind, shift)):
                fd = _MODEL._open_regular(path)
            if fd is not None:
                os.close(fd)
            ensure(fd is None and opened == ([] if kind == stat.S_IFCHR else [str(path)]),
                   f"{why}, got {fd} after opening {opened}")
        opened.clear()
        with patch.object(_MODEL, "os", answering(stat.S_IFREG)):
            fd = _MODEL._open_regular(path)
        ensure(fd is not None and opened == [str(path)],
               f"control: the file the name reported opens, got {fd} after {opened}")
        with os.fdopen(cast("int", fd), "rb") as stream:
            ensure(stream.read() == b"\x7fELF", "and reads as it is")
        for name in ("O_NONBLOCK", "O_NOFOLLOW", "O_NOCTTY", "O_BINARY"):
            flag = getattr(os, name, 0)
            ensure(_MODEL._REGULAR_ONLY & flag == flag,
                   f"{name} rides every corpus open on a platform that defines it")


def _os_answering_regular() -> SimpleNamespace:
    """`os` as model.py sees it, except that a name answers as a regular file: what the
    name names, its final link followed, with its kind made regular. A FIFO keeps its
    own inode, and a symbolic link answers as the regular file it names, so only the
    open's flags and the opened descriptor stand between `_open_regular` and either."""

    def lstat(named: str | Path) -> os.stat_result:
        held = tuple(Path(named).stat())
        return os.stat_result((stat.S_IFREG | stat.S_IMODE(held[0]), *held[1:]))

    return SimpleNamespace(**{**vars(os), "lstat": lstat})


def _open_regular_refuses_what_the_name_answered_as_a_file() -> None:
    """A FIFO, and a symbolic link to a regular file, each under a name that answered as
    a regular file, which is an entry replaced between that answer and the open, are
    refused by the open itself: the FIFO is opened without waiting and refused by its
    descriptor's kind, and the link is not followed. The name's answer is simulated by
    `_os_answering_regular`, which gives the link the identity of the file it names, so
    a followed link would be the very file the name reported and would open, and an
    open that waits on the FIFO fails `_returns`'s deadline. The positive control is
    that file, asked through the same answer, which opens. POSIX-only, so the case is
    the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO and link open case runs in "
                             "the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        fifo, link, regular = root / "rv64ui-p-fifo", root / "rv64ui-p-link", root / "regular"
        os.mkfifo(fifo)
        regular.write_bytes(b"\x7fELF")
        link.symlink_to(regular)

        def opened(path: Path) -> int | None:
            held: list[int | None] = []
            with patch.object(_MODEL, "os", _os_answering_regular()):
                _returns(lambda: held.append(_MODEL._open_regular(path)),
                         partial(_end_of_file, fifo))
            return held[0]

        for path in (fifo, link):
            fd = opened(path)
            if fd is not None:
                os.close(fd)
            ensure(fd is None, f"{path.name} is refused by the open, got descriptor {fd}")
        fd = opened(regular)
        ensure(fd is not None, "control: the regular file the name answered for opens")
        with os.fdopen(cast("int", fd), "rb") as stream:
            ensure(stream.read() == b"\x7fELF", "and reads as it is")


def _seed_refuses_a_device_manifest() -> None:
    """A donor whose manifest is a device node is refused by the kind its opened
    descriptor reports, simulated by `_os_with_a_device`. The positive control is the
    same donor read with the descriptor's own kind, which seeds."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "device-manifest"
        _extracted(donor, {"rv64ui-p-add": b"\x7fELF"})
        device = _os_with_a_device(lambda path: path.endswith(_MODEL.CORPUS_MANIFEST_SUFFIX))
        with patch.object(_MODEL, "os", device):
            _manifest_refused(donor, model_root)
        target = root / "target-control"
        with _copies_spied() as copied:
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


def _seed_refuses_a_manifest_linked_to_a_fifo() -> None:
    """A donor whose manifest is a symbolic link is refused without being followed. The
    link names a FIFO, which a reader following it waits on for a writer that never
    comes, rather than a device such as `/dev/zero`, which such a reader reads until
    the guest runs out of memory: a regression then fails at `_returns`'s deadline, and
    the FIFO's write end, opened and closed, releases the reader. POSIX-only, so the
    case is the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the linked manifest case runs in the "
                             "guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "linked-manifest"
        manifest = _MODEL.corpus_manifest(_extracted(donor, {"rv64ui-p-add": b"\x7fELF"}))
        fifo = root / "target-fifo"
        os.mkfifo(fifo)
        manifest.unlink()
        manifest.symlink_to(fifo)
        _manifest_refused(donor, model_root, partial(_end_of_file, fifo))


# `verify_test_corpus` over the suite and digest it is given, in a child whose address
# space is held to a gibibyte once model.py is imported, printing the refusal. A read of
# more than that fails with `MemoryError` there whatever the kernel's overcommit policy,
# where a process allowed to overcommit would map the whole read and be killed for the
# memory it touched. `resource` is POSIX-only, and the child runs only on a guest lane.
_BOUNDED_VERIFY = """
import resource
import sys
from pathlib import Path

from vos.cli import model

_, hard = resource.getrlimit(resource.RLIMIT_AS)
limit = 1 << 30 if hard == resource.RLIM_INFINITY else min(1 << 30, hard)
resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
try:
    model.verify_test_corpus(Path(sys.argv[1]), sys.argv[2])
except ValueError as err:
    print(err)
else:
    sys.exit("the sparse manifest verified")
"""


def _verify_refuses_a_sparse_manifest() -> None:
    """A manifest that is a regular file, holding the suite's listing and then zeros to
    a terabyte, disagrees with the suite: no more of it is read than the listing the
    tree renders and one byte, where a read of the whole would end in the `MemoryError`
    that no refusal of `_seed_test_data` catches. The verification runs in a child whose
    address space `_BOUNDED_VERIFY` holds to a gibibyte, so such a read fails there as
    that `MemoryError` under any overcommit policy rather than having the child killed.
    The file is sparse, so it allocates nothing; NTFS allocates an extended file, so
    the case is the guest's and win32 is refused before the truncation."""
    if sys.platform == "win32":
        raise AssertionError("NTFS allocates an extended file; the sparse manifest case "
                             "runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF"})
        os.truncate(_MODEL.corpus_manifest(suite), 1 << 40)
        done = subprocess.run([sys.executable, "-c", _BOUNDED_VERIFY, str(suite),
                               _CORPUS_DIGEST],
                              capture_output=True, encoding="utf-8", errors="replace",
                              check=False, timeout=120,
                              env={**os.environ, "PYTHONPATH": str(TOOLS)})
        ensure(done.returncode == 0 and "disagrees" in done.stdout,
               f"the sparse manifest disagrees, got {done.returncode}, "
               f"{done.stdout[-400:]!r} and {done.stderr[-400:]!r}")


def _verify_reads_no_file_until_the_paths_agree() -> None:
    """A suite whose walked paths differ from the ones its manifest records is refused
    before any of its files is read, so an entry the manifest does not list is never
    hashed however long it is, and neither is any other when a listed one is gone. The
    positive control is the suite as sealed, each of whose files is read once."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF", "rv64ui-p-sub": b"\x7fELF"})

        def refused_unread(*where: str) -> None:
            with patch.object(_MODEL, "_regular_digest",
                              wraps=_MODEL._regular_digest) as hashed:
                said = _refused(partial(_MODEL.verify_test_corpus, suite, _CORPUS_DIGEST))
            ensure("disagrees" in said and all(part in said for part in where)
                   and not hashed.called,
                   f"the suite disagrees ({where}) before a file is read, got {said!r} "
                   f"after reading {hashed.call_args_list}")

        unlisted = suite / "rv64ui-p-unlisted"
        unlisted.write_bytes(b"never in the tarball")
        refused_unread(f"at line 4: the manifest has '<end>' and the tree '{unlisted.name}'")
        unlisted.unlink()
        # the manifest is read no further than the two remaining files' lines reach
        gone = suite / "rv64ui-p-sub"
        gone.unlink()
        refused_unread("at line 3: the manifest has '", ", read no further, and the tree '<end>'")
        gone.write_bytes(b"\x7fELF")
        with patch.object(_MODEL, "_regular_digest", wraps=_MODEL._regular_digest) as hashed:
            _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)
        ensure(sorted(Path(read.args[0]).name for read in hashed.call_args_list)
               == ["rv64ui-p-add", "rv64ui-p-sub"],
               f"control: each file of the sealed suite is read once, got "
               f"{hashed.call_args_list}")


def _refused(call: Callable[[], object], unblock: Callable[[], None] | None = None) -> str:
    """The `ValueError` `call` refuses with, under `_returns`'s deadline; a call that
    returns instead fails the case."""
    refusals: list[str] = []

    def run() -> None:
        try:
            call()
        except ValueError as err:
            refusals.append(str(err))

    _returns(run, unblock)
    ensure(bool(refusals), "the call must refuse, and it returned")
    return refusals[0]


def _copy_regular_file() -> None:
    """The copy the seeding makes of each file that verified reads a source only when
    the descriptor it opened is a regular file and the very file that verified, by
    device, inode and length. A regular source is copied byte for byte with its mode and
    modification time, as `copy2` copies it, and the carriage return and 0x1A in it hold
    that a win32 read is not a text-mode one; a device, simulated by
    `_os_with_a_device`, another file holding the same bytes, and the same file grown
    by a byte are each refused naming the source, and leave no destination. Seeding a
    clean donor copies its entry through it and writes the manifest that verified."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        source, copied = root / "rv64ui-p-add", root / "copied"
        source.write_bytes(b"\x7fELF\r\n\x1a after")
        source.chmod(0o640)
        os.utime(source, ns=(1_000_000_000, 2_000_000_000))
        verified = _MODEL._regular_digest(source)
        _MODEL._copy_regular_file(source, copied, verified)
        was, now = source.stat(), copied.stat()
        ensure(copied.read_bytes() == source.read_bytes()
               and stat.S_IMODE(now.st_mode) == stat.S_IMODE(was.st_mode)
               and now.st_mtime_ns == was.st_mtime_ns,
               "a regular source is copied byte for byte with its mode and time")

        twin = root / "rv64ui-p-twin"
        twin.write_bytes(source.read_bytes())
        grown = root / "rv64ui-p-grown"
        grown.write_bytes(source.read_bytes())
        grown_verified = _MODEL._regular_digest(grown)
        with grown.open("ab") as stream:
            stream.write(b"!")
        for path, held in ((twin, verified), (grown, grown_verified)):
            kept = root / f"{path.name}-copy"
            said = _refused(partial(_MODEL._copy_regular_file, path, kept, held))
            ensure(f"{path} is not the file that verified" in said,
                   f"the refusal names {path.name}, got {said!r}")
            ensure(not kept.exists(), f"and nothing is written for {path.name}")

        device, kept = root / "rv64ui-p-device", root / "device-copy"
        device.write_bytes(b"")
        blank = _MODEL._regular_digest(device)
        with patch.object(_MODEL, "os", _os_with_a_device(lambda path: path == str(device))):
            said = _refused(partial(_MODEL._copy_regular_file, device, kept, blank))
        ensure(f"{device} is not a regular file" in said,
               f"the refusal names the source, got {said!r}")
        ensure(not kept.exists(), "and nothing is written for it")

        model_root = _corpus_model(root)
        donor = root / "clean"
        suite = _extracted(donor, {"rv64ui-p-add": b"\x7fELF"})
        with _copies_spied() as copy:
            _MODEL._seed_test_data([donor], root / "target", model_root)
        sources = {Path(call.args[0]) for call in copy.call_args_list}
        ensure(sources == {suite / "rv64ui-p-add"},
               f"the entry is copied through it, got {sources}")
        seeded = _MODEL.corpus_manifest(root / "target" / "test" / _RELEASE / "riscv-tests")
        ensure(seeded.read_bytes() == _MODEL.corpus_manifest(suite).read_bytes(),
               "and the manifest that verified is written beside it")


class _CountedReader:
    """A binary reader that keeps a count of the bytes read through it."""

    def __init__(self, stream: IO[bytes], counts: list[int]) -> None:
        self._stream = stream
        self._counts = counts

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *raised: object) -> None:
        self._stream.close()

    def fileno(self) -> int:
        return self._stream.fileno()

    def read(self, size: int = -1) -> bytes:
        data = self._stream.read(size) or b""
        self._counts.append(len(data))
        return data


def _copy_regular_file_reads_no_further_than_verified() -> None:
    """A source that grows after the copy asked its length, which is the window the
    descriptor's identity does not close, is refused having read no more of it than the
    verified length and one byte, and leaves no destination: a donor file extended
    then, a sparse terabyte among them, is not read to its end. The growth is
    simulated: the descriptor's `fstat` answers the verified length of a file that is
    longer. Reads are counted through the reader `os.fdopen` hands the copy. A second run
    reads in chunks of the verified length, so the verified bytes end at a chunk's
    boundary and the one byte past them takes a read of its own, which the copy must
    still make to find the growth."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        source = root / "rv64ui-p-add"
        source.write_bytes(b"\x7fELF")
        verified = _MODEL._regular_digest(source)
        with source.open("ab") as stream:
            stream.write(bytes(1 << 16))
        counts: list[int] = []

        def fdopen(fd: int, mode: str = "r", buffering: int = -1) -> _CountedReader:
            return _CountedReader(cast("IO[bytes]", os.fdopen(fd, mode, buffering)), counts)

        def fstat(fd: int) -> os.stat_result:
            # with its times to the nanosecond, so a copy that misses the growth returns
            # as it would over a real file, rather than failing as it keeps them
            found = os.fstat(fd)
            held = tuple(found)
            return os.stat_result((*held[:6], verified.size, *held[7:]),
                                  {"st_atime_ns": found.st_atime_ns,
                                   "st_mtime_ns": found.st_mtime_ns})

        grown = SimpleNamespace(**{**vars(os), "fdopen": fdopen, "fstat": fstat})
        for chunk in (_MODEL._COPY_CHUNK, verified.size):
            counts.clear()
            kept = root / f"copy-{chunk}"
            with patch.object(_MODEL, "os", grown), patch.object(_MODEL, "_COPY_CHUNK", chunk):
                said = _refused(partial(_MODEL._copy_regular_file, source, kept, verified))
            ensure(f"{source} is longer than the 4 bytes that verified" in said,
                   f"the refusal names the source in {chunk}-byte reads, got {said!r}")
            ensure(sum(counts) == verified.size + 1,
                   f"the verified length and one byte are read, and no more, in {chunk}-byte "
                   f"reads, got {counts}")
            ensure(not kept.exists(), f"and nothing is written for it in {chunk}-byte reads")


def _copy_regular_file_refuses_a_fifo_and_a_link() -> None:
    """A real FIFO source is refused rather than waited on, and a symbolic link, here
    to a regular file, rather than followed. Each is held to the identity of the file
    the link names, so a followed link would be the file that verified. POSIX-only, so
    the case is the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO source case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        fifo, link = root / "rv64ui-p-fifo", root / "rv64ui-p-link"
        os.mkfifo(fifo)
        (root / "regular").write_bytes(b"\x7fELF")
        verified = _MODEL._regular_digest(root / "regular")
        link.symlink_to(root / "regular")
        for source in (fifo, link):
            kept = root / f"{source.name}-copy"
            said = _refused(partial(_MODEL._copy_regular_file, source, kept, verified),
                            partial(_end_of_file, fifo))
            ensure(f"{source} is not a regular file" in said,
                   f"the refusal names the source, got {said!r}")
            ensure(not kept.exists(), f"nothing is written for {source.name}")


@contextmanager
def _changed_after_verifying(change: Callable[[], object]) -> Iterator[None]:
    """`verify_test_corpus` as it is, except that `change` runs once the first suite it
    is asked about has verified, which is the window between a verification and its
    reader that no check by name closes."""
    verify = _MODEL.verify_test_corpus
    pending = [change]

    def verified_then_changed(suite: Path, digest: str) -> object:
        found = verify(suite, digest)
        while pending:
            pending.pop()()
        return found

    with patch.object(_MODEL, "verify_test_corpus", verified_then_changed):
        yield


def _seed_copies_only_what_verified() -> None:
    """The seeding copies what the donor's verification found, not what the donor holds
    once it has verified: an entry added then is not copied, and the copy verifies and
    is seeded without it; a manifest lengthened then is not read again, and the copy's
    manifest is the one that verified; and an entry replaced then by another
    file of the same bytes is refused as not the file that verified, which seeds
    nothing. The control is the clean donor, which seeds."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        sealed = {"rv64ui-p-add": b"\x7fELF"}

        def seeded(name: str, change: Callable[[Path], object]) -> tuple[Path, str]:
            suite = _extracted(root / name, sealed)
            target = root / f"target-{name}"
            with (_changed_after_verifying(partial(change, suite)),
                  redirect_stderr(io.StringIO()) as err):
                _MODEL._seed_test_data([root / name], target, model_root)
            return target / "test" / _RELEASE / "riscv-tests", err.getvalue()

        def displaced(suite: Path) -> None:
            # moved rather than removed, so its inode cannot be the replacement's
            entry = suite / "rv64ui-p-add"
            entry.replace(root / "original")
            entry.write_bytes(sealed["rv64ui-p-add"])

        def lengthened(suite: Path) -> None:
            manifest = _MODEL.corpus_manifest(suite)
            manifest.write_bytes(manifest.read_bytes() + bytes(1 << 16))

        copy, said = seeded("clean", lambda suite: None)
        ensure(said == "" and (copy / "rv64ui-p-add").read_bytes() == b"\x7fELF",
               f"control: the clean donor seeds, got {said!r}")
        copy, said = seeded("added", lambda suite: (suite / "rv64ui-p-late").write_bytes(
            b"\x7fELF late"))
        ensure(said == "" and sorted(p.name for p in copy.iterdir()) == ["rv64ui-p-add"],
               f"an entry added once the donor verified is not copied, got {said!r}")
        _MODEL.verify_test_corpus(copy, _CORPUS_DIGEST)
        copy, said = seeded("lengthened", lengthened)
        ensure(said == "" and _MODEL.corpus_manifest(copy).read_bytes()
               == _MODEL.corpus_listing(copy, _CORPUS_DIGEST),
               f"the copy's manifest is the one that verified, got {said!r}")
        copy, said = seeded("displaced", displaced)
        entry = root / "displaced" / "test" / _RELEASE / "riscv-tests" / "rv64ui-p-add"
        ensure(f"{entry} is not the file that verified" in said and not copy.exists(),
               f"an entry replaced once the donor verified is refused, got {said!r}")


def _seed_refuses_an_entry_replaced_during_the_copy() -> None:
    """A donor entry replaced by a FIFO after the donor verified, just before the copy
    opens it, the window a check by name does not close, is refused by the copy rather
    than waited on: the seeding returns, names the donor and the entry, and seeds
    nothing, and the staging copy is removed. POSIX-only, so the case is the guest's
    and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the replaced entry case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        model_root = _corpus_model(root)
        donor = root / "replaced"
        entry = _extracted(donor, {"rv64ui-p-add": b"\x7fELF"}) / "rv64ui-p-add"
        copy = _MODEL._copy_regular_file

        def replacing(source: Path, destination: Path, verified: object) -> None:
            if source == entry:
                entry.unlink()
                os.mkfifo(entry)
            copy(source, destination, verified)

        target = root / "target"
        with (patch.object(_MODEL, "_copy_regular_file", replacing),
              redirect_stderr(io.StringIO()) as err):
            _returns(lambda: _MODEL._seed_test_data([donor], target, model_root),
                     partial(_end_of_file, entry))
        said = err.getvalue()
        ensure(f"{entry} is not a regular file" in said and str(donor) in said,
               f"the refusal names the donor and the entry, got {said!r}")
        release = target / "test" / _RELEASE
        ensure(not release.exists() or not any(release.iterdir()),
               "nothing is seeded, and no staging copy is left behind")


def _listing_hashes_only_regular_descriptors() -> None:
    """An entry the listing's check by name passes but that does not open as a regular
    file, which is an entry replaced between that check and the read, is listed unhashed
    rather than read, and the suite is refused as holding a non-regular entry. The
    device is simulated by `_os_with_a_device`; the positive control is the same suite
    read as it is, which verifies."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF"})
        entry = suite / "rv64ui-p-add"
        with patch.object(_MODEL, "os", _os_with_a_device(lambda path: path == str(entry))):
            listed = cast("bytes", _MODEL.corpus_listing(suite, _CORPUS_DIGEST))
            said = _refused(partial(_MODEL.verify_test_corpus, suite, _CORPUS_DIGEST))
        ensure(b"\nunhashed rv64ui-p-add\n" in listed,
               f"the entry is listed unhashed, got {listed!r}")
        ensure("non-regular" in said, f"and the suite is refused, got {said!r}")
        _MODEL.verify_test_corpus(suite, _CORPUS_DIGEST)


def _listing_refuses_a_fifo_its_check_by_name_missed() -> None:
    """A FIFO that the listing's check by name, `Path.is_file`, answers as a regular file,
    which is a file replaced by a FIFO between that check and the read, is refused by
    `_open_regular`'s own check by name before any open: it is listed unhashed rather
    than waited on, and the suite is refused. The FIFO stands under a name the manifest
    lists, so the suite's paths agree with the manifest's and only the read meets it.
    A FIFO that both checks answer as a regular file is the open's to refuse, which
    `_open_regular_refuses_what_the_name_answered_as_a_file` holds. POSIX-only, so the
    case is the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO listing case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        suite = _extracted(Path(td), {"rv64ui-p-add": b"\x7fELF", "rv64ui-p-fifo": b"x"})
        fifo = suite / "rv64ui-p-fifo"
        fifo.unlink()
        os.mkfifo(fifo)
        real = Path.is_file

        def is_file(self: Path, *, follow_symlinks: bool = True) -> bool:
            return self == fifo or real(self, follow_symlinks=follow_symlinks)

        with patch.object(Path, "is_file", is_file):
            said = _refused(partial(_MODEL.verify_test_corpus, suite, _CORPUS_DIGEST),
                            partial(_end_of_file, fifo))
        ensure("non-regular" in said, f"the suite is refused, got {said!r}")


def _built_receipt() -> dict[str, str]:
    """What the receipt records of `_built_tree`'s tree as it was built: every product,
    and the one input under the name `receipts.snapshot` gives the products."""
    product = hashlib.sha256(b"product").hexdigest()
    return {**dict.fromkeys(_MODEL.BUILD_ARTIFACTS, product),
            f"test/{_RELEASE}/riscv-tests/rv64ui-p-add": hashlib.sha256(b"\x7fELF").hexdigest()}


def _built_tree(root: Path) -> tuple[Path, Path, Path]:
    """A build tree holding every build product and a sealed suite of one ELF input,
    its model root, and the input; and the control on it: the receipt is
    `_built_receipt`."""
    model_root = _corpus_model(root)
    build = root / "build"
    for rel in _MODEL.BUILD_ARTIFACTS:
        (build / rel).parent.mkdir(parents=True, exist_ok=True)
        (build / rel).write_bytes(b"product")
    elf = _extracted(build, {"rv64ui-p-add": b"\x7fELF"}) / "rv64ui-p-add"
    recorded = _MODEL.build_artifacts(build, model_root)
    ensure(recorded == _built_receipt(),
           f"control: the receipt records every product and the input, got {recorded}")
    return build, model_root, elf


def _receipt_records_what_verified() -> None:
    """The sweep and its build receipt take their inputs from what the suite's
    verification found, and the receipt records each with the SHA-256 that verification
    read rather than reading it again. An ELF added beside the input once the suite has
    verified is neither swept nor recorded; an input that would open as a device then,
    simulated by `_os_with_a_device`, is recorded as it verified, and is read once, by
    the verification. The next verification refuses the suite the added ELF changed.
    The control is `_built_tree`'s receipt."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        build, model_root, elf = _built_tree(Path(td))
        late = elf.with_name("rv64ui-p-late")
        add_late = partial(late.write_bytes, b"\x7fELF late")
        with _changed_after_verifying(add_late):
            selected = _MODEL.sweep_inputs(build, model_root)
        ensure(selected == [elf], f"an ELF added once the suite verified is not swept, "
                                  f"got {selected}")
        late.unlink()
        device = _os_with_a_device(lambda path: path == str(elf))
        with ExitStack() as later:

            def change() -> None:
                add_late()
                later.enter_context(patch.object(_MODEL, "os", device))

            with (patch.object(_MODEL, "_regular_digest",
                               wraps=_MODEL._regular_digest) as hashed,
                  _changed_after_verifying(change)):
                recorded = _MODEL.build_artifacts(build, model_root)
        ensure(recorded == _built_receipt(),
               f"the receipt records what verified and nothing added since, got {recorded}")
        read = [Path(call.args[0]) for call in hashed.call_args_list]
        ensure(read == [elf], f"the input is read once, by the verification, got {read}")
        said = _refused(partial(_MODEL.build_artifacts, build, model_root))
        ensure("disagrees" in said, f"the next verification refuses the suite, got {said!r}")


def _receipt_opens_no_sweep_input_after_verifying() -> None:
    """A sweep input replaced by a real FIFO once its suite has verified is not opened
    by the build receipt, which returns within `_returns`'s deadline recording the
    bytes that verified; the next verification refuses the suite holding the FIFO.
    POSIX-only, so the case is the guest's and win32 is refused before `os.mkfifo`."""
    if sys.platform == "win32":
        raise AssertionError("mkfifo is POSIX-only; the FIFO input case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        build, model_root, elf = _built_tree(Path(td))

        def replace() -> None:
            elf.unlink()
            os.mkfifo(elf)

        recorded: list[object] = []
        with _changed_after_verifying(replace):
            _returns(lambda: recorded.append(_MODEL.build_artifacts(build, model_root)),
                     partial(_end_of_file, elf))
        ensure(recorded == [_built_receipt()],
               f"the receipt records the bytes that verified, got {recorded}")
        said = _refused(partial(_MODEL.build_artifacts, build, model_root),
                        partial(_end_of_file, elf))
        ensure("non-regular" in said, f"the next verification refuses the suite, got {said!r}")


def _build_records_an_unreadable_product() -> None:
    """A build whose stages pass and one of whose products is gone before its evidence is
    recorded fails with the reason in its receipt, rather than with the `OSError`
    escaping the command before any receipt is written. The stages, configure and the
    build identity stand in; the control is the same build over `_built_tree`'s whole
    tree, whose receipt records its products and input."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        build, model_root, _ = _built_tree(root)
        e = env.Environment(root, model_root, root / "build-root", root / "logs", "", 4,
                            4096, 2, 2)
        log = e.log("model-build")
        sail = subprocess.CompletedProcess([], 0, "Sail 9.9.9 (fixture)\n", "")

        def built() -> tuple[int, dict[str, object]]:
            with (patch.object(_MODEL, "build_identity", return_value={"inputs": {}}),
                  patch.object(_MODEL, "_configure", return_value=0),
                  patch.object(_MODEL, "env", SimpleNamespace(stage=Mock(return_value=0))),
                  patch.object(_MODEL, "subprocess",
                               SimpleNamespace(run=Mock(return_value=sail))),
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                code = cast("int", _MODEL._build_locked(e, build, log, []))
            record = json.loads(log.with_suffix(".json").read_text(encoding="utf-8"))
            return code, cast("dict[str, object]", record)

        code, record = built()
        ensure(code == 0 and record.get("artifacts") == _built_receipt(),
               f"control: the whole tree's build records its evidence, got {code}, {record}")
        product = build / _MODEL.BUILD_ARTIFACTS[-1]
        product.unlink()
        code, record = built()
        refusal = str(record.get("refusal"))
        ensure(code == 1 and record.get("exit_code") == 1
               and "the build's evidence cannot be recorded" in refusal
               and product.name in refusal,
               f"the receipt records the unreadable product, got {code} and {record}")


# A tree's ninja log as `_fresh_outputs` reads it: the header, two emission entries
# earlier builds left, this build's, and an entry for another output.
_NINJA_HEADER = b"# ninja log v6\n"
_OLDER_EMISSION = b"9\t35000\t1600000000000000000\tsail_riscv_model.cpp\t1a2b3c\n"
_STALE_EMISSION = b"10\t36000\t1700000000000000000\tsail_riscv_model.cpp\t1a2b3c\n"
_FRESH_EMISSION = b"12\t36500\t1800000000000000000\tsail_riscv_model.cpp\t1a2b3c\n"
_OTHER_OUTPUT = b"40\t900\t1800000000000000001\tc_emulator/CMakeFiles/x.dir/y.cpp.o\t4d5e\n"


def _until(done: Callable[[], bool], what: str) -> None:
    """Wait for the build's emission watch to have done `what`, failing rather than
    hanging."""
    deadline = time.monotonic() + 30
    while not done():
        if time.monotonic() > deadline:
            raise AssertionError(f"the emission watch never {what}")
        time.sleep(0.002)


def _replaced(staged: Path, path: Path) -> bool:
    """Rename `staged` over `path`, as ninja's compaction does, or say it could not yet:
    Windows refuses the rename while the watch has the old file open."""
    try:
        staged.replace(path)
    except PermissionError:
        return False
    return True


class _EarlyStandIn:
    """`_EarlyRun` without a process: a ctest run of the one test, exiting `code`."""

    def __init__(self, argv: list[str], since: float, build: Path, code: int) -> None:
        self.argv = argv
        self.since = since
        self.code = code
        self.printed = f"Test project {build}\n    Start 1: smt_properties_rv64d\n" + (
            "1/1 Test #1: smt_properties_rv64d ....   Passed   26.30 sec\n\n"
            "100% tests passed, 0 tests failed out of 1\n" if code == 0 else
            "1/1 Test #1: smt_properties_rv64d ....***Failed   26.30 sec\n"
            "a counterexample, printed on failure\n\n"
            "0% tests passed, 1 tests failed out of 1\n")
        self.waited = False
        self.killed = False

    def wait(self) -> int:
        self.waited = True
        return self.code

    def report(self) -> str:
        return (f"{self.printed}"
                "STAGE ctest-early start=+41.2s wall=26.4s cpu=99% maxrss=790000kB\n")

    def kill(self) -> None:
        # `_build_locked` ends every run it started this way, and a reaped run has
        # nothing left to kill
        self.killed = self.killed or not self.waited


class _BuildRig:
    """`_build_locked` with its configure, stages, early run and identity standing in.
    `run` takes the build stage; the ctest stage prints the summary of the tests it was
    asked for, fourteen when it excludes the early test and fifteen otherwise. Every
    read of the ninja log the emission watch makes is counted in `polls`, and the time
    the build stage began is `build_began`."""

    def __init__(self, root: Path, *, memory: int = 8192, early_code: int = 0) -> None:
        self.build = root / "build"
        self.build.mkdir(parents=True, exist_ok=True)
        self.ninja_log = self.build / ".ninja_log"
        self.env = env.Environment(root, root / "model", root / "build-root", root / "logs",
                                   "", 4, memory, 2, 2)
        self.log = self.env.log("model-build")
        self.early_code = early_code
        self.calls: list[tuple[str, list[str], object]] = []
        self.runs: list[_EarlyStandIn] = []
        self.polls = 0
        self.build_began = 0.0
        self._read = _MODEL._fresh_outputs
        self._on_build: Callable[[], int] | None = None

    def _stage(self, name: str, argv: list[str], report_to: object = None,
               **kw: object) -> int:
        self.calls.append((name, argv, kw.get("add_env")))
        if name == "build":
            self.build_began = time.perf_counter()
            if self._on_build is None:
                raise AssertionError("the rig runs a build stage only inside `run`")
            return self._on_build()
        tests = 14 if "-E" in argv else 15
        cast("IO[str]", kw["stdout"]).write(
            f"Test project {self.build}\n100% tests passed, 0 tests failed out of {tests}\n")
        return 0

    def _start(self, argv: list[str], since: float) -> _EarlyStandIn:
        run = _EarlyStandIn(argv, since, self.build, self.early_code)
        self.runs.append(run)
        return run

    def _counted(self, path: Path, mark: object) -> set[str]:
        found = cast("set[str]", self._read(path, mark))
        self.polls += 1
        return found

    def polled(self, since: int) -> None:
        """Wait until the watch has read the log twice since `since` reads, counted
        after a change to it: the second read began after the first ended, and so after
        the change."""
        _until(lambda: self.polls >= since + 2, "read the log again")

    def started(self) -> None:
        _until(lambda: bool(self.runs), "started the early test")

    def run(self, on_build: Callable[[], int]) -> int:
        self._on_build = on_build
        sail = subprocess.CompletedProcess([], 0, "Sail 9.9.9 (fixture)\n", "")
        with (patch.object(_MODEL, "build_identity", return_value={"inputs": {}}),
              patch.object(_MODEL, "_configure", return_value=0),
              patch.object(_MODEL, "build_artifacts", return_value={}),
              patch.object(_MODEL, "env", SimpleNamespace(stage=self._stage)),
              patch.object(_MODEL, "subprocess", SimpleNamespace(run=Mock(return_value=sail))),
              patch.object(_MODEL, "_EarlyRun", self._start),
              patch.object(_MODEL, "_fresh_outputs", self._counted),
              patch.object(_MODEL, "EMISSION_POLL_SECONDS", 0.001),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            return cast("int", _MODEL._build_locked(self.env, self.build, self.log, []))

    def ctest_argv(self) -> list[list[str]]:
        return [argv for name, argv, _ in self.calls if name == "ctest"]

    def text(self) -> str:
        return self.log.read_text(encoding="utf-8")

    def record(self) -> dict[str, object]:
        raw = json.loads(self.log.with_suffix(".json").read_text(encoding="utf-8"))
        return cast("dict[str, object]", raw)


def _fresh_outputs_reads_only_this_builds_entries() -> None:
    """The outputs a build has recorded since its mark: a log the build created is all
    the build's, a line is read once its newline is there, a log grown past the mark is
    read from it, and a log rewritten over the mark, renamed over it or shorter, holds
    the build's lines and the earlier lines the mark already held."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / ".ninja_log"
        mark = _MODEL._ninja_log_mark(path)
        ensure(_MODEL._fresh_outputs(path, mark) == set(), "no log records nothing")
        path.write_bytes(_NINJA_HEADER + _FRESH_EMISSION[:-1])
        ensure(_MODEL._fresh_outputs(path, mark) == set(),
               "a line without its newline is still being written")
        with path.open("ab") as log:
            log.write(b"\n")
        got = _MODEL._fresh_outputs(path, mark)
        ensure(got == {"sail_riscv_model.cpp"},
               f"a log the build created is all the build's, got {got}")

        path.write_bytes(_NINJA_HEADER + _STALE_EMISSION)
        mark = _MODEL._ninja_log_mark(path)
        with path.open("ab") as log:
            log.write(_OTHER_OUTPUT)
        got = _MODEL._fresh_outputs(path, mark)
        ensure(got == {"c_emulator/CMakeFiles/x.dir/y.cpp.o"},
               f"a log grown past its mark is read from the mark, got {got}")

        staged = path.with_name("staged")
        staged.write_bytes(_NINJA_HEADER + _STALE_EMISSION
                           + _FRESH_EMISSION.replace(b".cpp", b".h"))
        staged.replace(path)
        got = _MODEL._fresh_outputs(path, mark)
        ensure(got == {"sail_riscv_model.h"},
               f"a log renamed over the mark holds the mark's lines again, got {got}")

        mark = _MODEL._ninja_log_mark(path)
        path.write_bytes(_NINJA_HEADER + _STALE_EMISSION)
        ensure(_MODEL._fresh_outputs(path, mark) == set(),
               "a log rewritten shorter in place holds only lines its mark held")
        path.write_bytes(_NINJA_HEADER + _OTHER_OUTPUT)
        got = _MODEL._fresh_outputs(path, mark)
        ensure(got == {"c_emulator/CMakeFiles/x.dir/y.cpp.o"},
               f"a log rewritten shorter in place is read whole, got {got}")


def _early_test_starts_on_this_builds_emission() -> None:
    """The Sail property test starts beside the build once this build's emission entry
    is complete in the ninja log, and not on the entry an earlier build left nor on a
    line still without its newline. The ctest stage then runs the rest of the suite,
    places the early run's output after it inside the one ctest section, and the
    evidence reads the whole suite's tally. The build stage's ninja prints the elapsed
    seconds on each finished edge."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td))
        rig.ninja_log.write_bytes(_NINJA_HEADER + _STALE_EMISSION)

        def build() -> int:
            with rig.ninja_log.open("ab") as log:
                log.write(_OTHER_OUTPUT + _FRESH_EMISSION[:-1])
                log.flush()
                rig.polled(rig.polls)
                ensure(not rig.runs,
                       "an earlier build's entry or a partial line must start nothing")
                log.write(b"\n")
            rig.started()
            return 0

        code = rig.run(build)
        text = rig.text()
        ensure(code == 0 and rig.record().get("stages")
               == {"configure": 0, "build": 0, "ctest": 0},
               f"the build passes every stage, got {code} and {rig.record()}")
        ensure([run.argv for run in rig.runs]
               == [["ctest", "--test-dir", str(rig.build), "-R", "^smt_properties_rv64d$",
                    "--output-on-failure"]],
               f"one early run of the one test, got {[run.argv for run in rig.runs]}")
        ensure(0 < rig.runs[0].since <= rig.build_began,
               f"the run's start is counted from the build stage's, got "
               f"{rig.runs[0].since} against {rig.build_began}")
        ensure(rig.ctest_argv() == [["ctest", "--test-dir", str(rig.build), "-j", "2",
                                     "--output-on-failure", "-E", "^smt_properties_rv64d$"]],
               f"the ctest stage runs the rest of the suite, got {rig.ctest_argv()}")
        ensure([add for name, _, add in rig.calls if name == "build"]
               == [{"NINJA_STATUS": "[%f/%t %e] "}],
               f"the build's status lines carry elapsed seconds, got {rig.calls}")
        ensure("smt_properties_rv64d may start beside the build within 4096 MB" in text,
               f"the host line states the decision, got {text!r}")
        ensure(text.index("out of 14\n") < text.index("out of 1\n")
               < text.index("STAGE ctest-early") < text.index("CTEST_EXIT=0\n")
               and text.endswith("CTEST_EXIT=0\nALL_DONE\n"),
               f"the early run's output closes the one ctest section, got {text!r}")
        tally = evidence._ctest(rig.log)
        ensure(tally == "15 of 15", f"the evidence reads the whole suite, got {tally}")
        with redirect_stdout(io.StringIO()):
            verdict = cast("int", _MODEL._report_build(rig.log))
        ensure(verdict == 0, f"wait reads the build as green, got {verdict}")


def _early_test_needs_this_builds_emission() -> None:
    """A log ninja compacts into a new file at its start holds an earlier build's
    emission entry again, and that starts nothing: the suite runs whole after the build,
    as it does when the emission is up to date, and the evidence reads the same
    tally."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td))
        rig.ninja_log.write_bytes(_NINJA_HEADER + _OLDER_EMISSION + _STALE_EMISSION)
        staged = rig.ninja_log.with_name(".ninja_log.recompact")

        def build() -> int:
            staged.write_bytes(_NINJA_HEADER + _STALE_EMISSION + _OTHER_OUTPUT)
            _until(partial(_replaced, staged, rig.ninja_log), "let the log be replaced")
            rig.polled(rig.polls)
            return 0

        code = rig.run(build)
        ensure(code == 0 and not rig.runs, f"nothing starts early, got {code}, {rig.runs}")
        ensure(rig.ctest_argv() == [["ctest", "--test-dir", str(rig.build), "-j", "2",
                                     "--output-on-failure"]],
               f"the ctest stage runs the whole suite, got {rig.ctest_argv()}")
        tally = evidence._ctest(rig.log)
        ensure(tally == "15 of 15" and "STAGE ctest-early" not in rig.text(),
               f"the evidence reads the same tally, got {tally}")


def _early_test_waits_for_memory() -> None:
    """The test may start beside the build only where the memory available covers the
    build's budget and the test's; otherwise, or with no reading, it runs after the
    build, and the host line says which and why."""
    nowhere = Path("nowhere")
    for memory, decided in (
            (4096, (True, "smt_properties_rv64d may start beside the build within 4096 MB")),
            (4095, (False, "smt_properties_rv64d after the build, 4096 MB wanted beside it")),
            (0, (False, "smt_properties_rv64d after the build, no memory reading"))):
        e = env.Environment(nowhere, nowhere, nowhere, nowhere, "", 4, memory, 2, 2)
        got = _MODEL._early_decision(e)
        ensure(got == decided, f"at {memory} MB the decision is {decided}, got {got}")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td), memory=4095)

        def build() -> int:
            rig.ninja_log.write_bytes(_NINJA_HEADER + _FRESH_EMISSION)
            return 0

        with patch.object(_MODEL, "_EmissionWatch", wraps=_MODEL._EmissionWatch) as watch:
            code = rig.run(build)
        ensure(code == 0 and not watch.called and not rig.runs
               and "after the build, 4096 MB wanted beside it" in rig.text()
               and rig.ctest_argv() == [["ctest", "--test-dir", str(rig.build), "-j", "2",
                                         "--output-on-failure"]],
               f"a short host runs the whole suite after the build, got {code}, {rig.calls}")


def _failed_build_discards_the_early_test() -> None:
    """A build that fails after the early test started waits for it and discards it:
    the log ends as a failed build's does, with no ctest output and no CTEST_EXIT."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td))

        def build() -> int:
            rig.ninja_log.write_bytes(_NINJA_HEADER + _FRESH_EMISSION)
            rig.started()
            return 2

        code = rig.run(build)
        text = rig.text()
        ensure(code == 2 and rig.record().get("stages") == {"configure": 0, "build": 2},
               f"the build's failure is the verdict, got {code} and {rig.record()}")
        ensure(len(rig.runs) == 1 and rig.runs[0].waited and not rig.runs[0].killed,
               "the early test is waited for, not killed")
        ensure(not rig.ctest_argv() and "CTEST_EXIT" not in text and "Test project" not in text
               and text.endswith("BUILD_EXIT=2\nALL_DONE\n"),
               f"no ctest output reaches a failed build's log, got {text!r}")


def _failed_early_test_fails_ctest() -> None:
    """An early test that fails fails the ctest stage, its output in the log, and the
    evidence reads no tally from it."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td), early_code=8)

        def build() -> int:
            rig.ninja_log.write_bytes(_NINJA_HEADER + _FRESH_EMISSION)
            rig.started()
            return 0

        code = rig.run(build)
        text = rig.text()
        ensure(code == 8 and rig.record().get("stages")
               == {"configure": 0, "build": 0, "ctest": 8},
               f"the early test's failure fails the ctest stage, got {code}, {rig.record()}")
        ensure("a counterexample, printed on failure" in text
               and text.endswith("CTEST_EXIT=8\nALL_DONE\n"),
               f"the failing test's output is in the ctest section, got {text!r}")
        try:
            tally = evidence._ctest(rig.log)
        except ValueError as refused:
            ensure("failing" in str(refused), f"the evidence refuses the tally, got {refused}")
        else:
            raise AssertionError(f"a failing early test gave the evidence {tally}")


def _exception_ends_the_early_test() -> None:
    """A build leaving by an exception ends the early test rather than leaving it to
    outlive the lane's lock."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        rig = _BuildRig(Path(td))

        def build() -> int:
            rig.ninja_log.write_bytes(_NINJA_HEADER + _FRESH_EMISSION)
            rig.started()
            raise RuntimeError("the build was interrupted")

        try:
            rig.run(build)
        except RuntimeError as err:
            ensure("interrupted" in str(err), f"the build's own exception, got {err}")
        else:
            raise AssertionError("the build's exception must reach its caller")
        ensure(len(rig.runs) == 1 and rig.runs[0].killed and not rig.runs[0].waited,
               "the early test is killed")
        ensure("ALL_DONE" not in rig.text(), "an interrupted build writes no ALL_DONE")


def _gone(pid: int) -> bool:
    """Whether `pid` has exited, a zombie awaiting its reaper counting as exited."""
    try:
        record = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return record[record.rfind(")") + 1:].split()[0] == "Z"


def _early_run_reports_and_ends_its_tree() -> None:
    """The early run over a stand-in command: reaped, it reports what it printed and
    then its `STAGE` line, which counts its start from the build stage's and whose wall
    time ends when the run exited rather than when the ctest stage asked for it; killed
    while it runs, the process it started dies with it. POSIX-only, like the stage it
    runs beside."""
    if sys.platform == "win32":
        raise AssertionError("os.wait4 is POSIX-only; the early run's case runs in the guest")
    began = time.perf_counter()
    run = _MODEL._EarlyRun([sys.executable, "-c", "import sys; print('one test'); sys.exit(3)"],
                           began - 5.0)
    pid = cast("int", run._proc.pid)
    _until(partial(_gone, pid), "saw the stand-in exit")
    lived = time.perf_counter() - began
    # the ctest stage asks for the run well after it ended, as the rest of the suite
    # outlasts the Sail test
    time.sleep(2.0)
    code = cast("int", run.wait())
    said = cast("str", run.report())
    run.kill()
    cost = re.search(r"^STAGE ctest-early start=\+5\.\ds wall=(\d+\.\d)s cpu=\d+% "
                     r"maxrss=\d+kB$", said, re.MULTILINE)
    ensure(code == 3 and said.startswith("one test\n") and cost is not None,
           f"a reaped run reports its output, its start and its cost, got {code} and "
           f"{said!r}")
    wall = float(cost.group(1)) if cost is not None else 0.0
    ensure(wall < lived + 1.0,
           f"the run's wall time ends at its exit, {lived:.1f}s in, got {said!r}")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        marker = Path(td) / "child"
        script = (
            "import pathlib, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
            f"staged = pathlib.Path({str(marker)!r} + '.tmp')\n"
            "staged.write_text(str(child.pid))\n"
            f"staged.replace({str(marker)!r})\n"
            "time.sleep(600)\n")
        run = _MODEL._EarlyRun([sys.executable, "-c", script], time.perf_counter())
        try:
            _until(marker.exists, "saw the stand-in start its child")
            child = int(marker.read_text(encoding="utf-8"))
            run.kill()
            _until(partial(_gone, child), "saw the stand-in's child end")
        finally:
            run.kill()


def _pids_in(path: Path) -> list[int]:
    """The pids a stand-in has written to `path`, one per line."""
    try:
        return [int(word) for word in path.read_text(encoding="utf-8").split()]
    except FileNotFoundError:
        return []


def _early_run_ends_a_tree_still_forking() -> None:
    """Killed while a process under it keeps starting more, as Sail starts a solver for
    each property, the early run ends every process that process started, those started
    while the tree was being read among them. POSIX-only, like the stage it runs
    beside."""
    if sys.platform == "win32":
        raise AssertionError("/proc is Linux's; the early run's case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        started = Path(td) / "started"
        loop = (f"while :; do sleep 600 & echo $! >> {shlex.quote(str(started))}; "
                "sleep 0.002; done")
        script = ("import subprocess, time\n"
                  f"subprocess.Popen(['sh', '-c', {loop!r}])\n"
                  "time.sleep(600)\n")
        run = _MODEL._EarlyRun([sys.executable, "-c", script], time.perf_counter())
        try:
            _until(lambda: len(_pids_in(started)) >= 3, "saw the stand-in start processes")
            run.kill()
            pids = _pids_in(started)
            _until(lambda: all(_gone(pid) for pid in pids),
                   "saw every process the stand-in started end")
        finally:
            run.kill()
            # what a failure left running, so that it does not outlive the case
            for pid in _pids_in(started):
                with suppress(OSError):
                    os.kill(pid, signal.SIGKILL)


def _trace_diff_compares_what_verified() -> None:
    """`trace-diff --corpus` compares the rv64ui programs its suite's verification
    found, and not an ELF added beside them once the suite has verified. The oracle's
    checks, its lock and the comparison stand in, so only the selection is decided."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        build, model_root, elf = _built_tree(Path(td))
        late = elf.with_name("rv64ui-p-late")
        e = SimpleNamespace(build_dir=build, model=model_root, oracle_root=Path(td) / "oracle")
        unlocked = SimpleNamespace(hold_lock=lambda *_, **__: nullcontext())
        with (patch.object(_MODEL, "_missing_simulator", return_value=None),
              patch.object(_MODEL, "_missing_oracle", return_value=None),
              patch.object(_MODEL, "_unvouched_oracle", return_value=None),
              patch.object(_MODEL, "env", unlocked),
              patch.object(_MODEL, "_adjudicate", return_value=0) as adjudicated,
              _changed_after_verifying(partial(late.write_bytes, b"\x7fELF late"))):
            code = _MODEL.cmd_trace_diff(e, argparse.Namespace(elf=[], corpus=True))
        compared = adjudicated.call_args.args[2] if adjudicated.called else None
        ensure(code == 0 and compared == [elf],
               f"only the program that verified is compared, got {code} and {compared}")

# The model's own declaration, whose two suite functions the case below cuts out and runs
# under cmake, so what it holds is what configure runs rather than a copy of it.
_SUITE_CMAKE = TOOLS.parent / "model/test/CMakeLists.txt"
_SPLIT = {"a;b": b"split", "a": b"A", "b": b"B"}


def _cmake(work: Path, body: str, digest: str = _CORPUS_DIGEST) -> subprocess.CompletedProcess[str]:
    """`body` under `cmake -P`, after `riscv_tests_listing` and `download_riscv_tests`
    and with `digest` recorded for riscv-tests at the fixture release."""
    text = _SUITE_CMAKE.read_text(encoding="utf-8")
    functions = [re.search(rf"^function\({name} .*?^endfunction\(\)\n", text,
                           re.MULTILINE | re.DOTALL)
                 for name in ("riscv_tests_listing", "download_riscv_tests")]
    ensure(all(functions), f"{_SUITE_CMAKE} must define both suite functions")
    script = work / "suite.cmake"
    script.write_text(f'set(TEST_DOWNLOAD_VERSION "{_RELEASE}")\n'
                      f'set(TEST_DOWNLOAD_SHA256_{_RELEASE}_riscv-tests "{digest}")\n'
                      + "".join(found.group(0) for found in functions if found) + body,
                      encoding="utf-8", newline="")
    return subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True,
                          errors="replace", check=False, timeout=300)


def _cmake_listing(work: Path, suite: Path) -> bytes:
    """The listing `riscv_tests_listing` renders for `suite`."""
    out = work / "listing.out"
    done = _cmake(work, f'riscv_tests_listing("{suite}" "riscv-tests" "{_CORPUS_DIGEST}" '
                        f'listing)\nfile(WRITE "{out}" "${{listing}}")\n')
    ensure(done.returncode == 0, f"the listing runs, said {done.stderr[-400:]!r}")
    return out.read_bytes()


def _suite_of(where: Path, files: dict[str, bytes]) -> Path:
    suite = where / "riscv-tests"
    for name, data in files.items():
        (suite / name).parent.mkdir(parents=True, exist_ok=True)
        (suite / name).write_bytes(data)
    return suite


def _cmake_suite_listing() -> None:
    """The suite functions configure runs, run by cmake. A clean suite lists the bytes
    `corpus_listing` renders. A name holding ";" leaves an unhashed line however the
    list splits it: whole inside brackets, into pieces naming nothing, into pieces
    that are themselves listed files, or into pieces holding backslashed ".." steps
    that a relative glob would collapse onto a listed file; and a name holding a
    backslash is listed unhashed beside the file its "/" spelling names. A name
    ending in a backslash escapes the ";" joining the next path to it, so the sort
    keeps the two as one element without the backslash and the loop hashes only
    listed files, "a0" sorting between the two "a" lines so that neither repeats the
    line before it; the check before the sort lists that escape unhashed. Configure
    keeps a clean suite beside its manifest and removes one holding a split name even
    beside a manifest recording its listing exactly; a verified tarball extracting a
    clean suite writes the manifest `corpus_listing` renders, and one extracting a
    split name writes none; and a download path the glob would read as a pattern or
    split is refused before anything in it is touched. The download URL of a suite
    already standing is never fetched, so it is a `file://` path that does not
    exist."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        work = Path(td).resolve()
        clean = {"rv64ui-p-add": b"\x7fELF", "a0": b"zero", "a/b": b"nested",
                 "a.c": b"dot", "a-b": b"dash", "k[1]": b"bracketed", "with space": b"sp"}
        suite = _suite_of(work / "clean", clean)
        ensure(_cmake_listing(work, suite) == _MODEL.corpus_listing(suite, _CORPUS_DIGEST),
               "cmake lists a clean suite in the bytes corpus_listing renders")

        def hashed(data: bytes, name: str) -> str:
            return f"{hashlib.sha256(data).hexdigest()}  {name}\n"

        head = f"tarball riscv-tests.tar.gz sha256 {_CORPUS_DIGEST}\n"
        for name, files, want in (
                ("bracketed", {"[;]": b"whole", "z": b"z"}, "unhashed [;]\n" + hashed(b"z", "z")),
                ("absent-pieces", {"x;y": b"split", "z": b"z"},
                 "unhashed x\n" + hashed(b"z", "z") + "unhashed y\n"),
                ("listed-pieces", _SPLIT,
                 hashed(b"A", "a") + "unhashed a\n" + hashed(b"B", "b") + "unhashed b\n"),
                ("collapsing-pieces", {"p;..\\..\\q": b"hidden", "q": b"Q"},
                 "unhashed ..\\..\\q\nunhashed p\n" + hashed(b"Q", "q")),
                ("backslashed", {"a\\b": b"hidden", "a/b": b"nested"},
                 hashed(b"nested", "a/b") + "unhashed a\\b\n"),
                ("escaping-backslash", {"a": b"A", "a0": b"0", "a\\": b"hidden", "b": b"B"},
                 "unhashed a name holding \\ before a semicolon\n" + hashed(b"A", "a")
                 + hashed(b"0", "a0") + hashed(b"A", "a") + hashed(b"B", "b"))):
            got = _cmake_listing(work, _suite_of(work / name, files))
            ensure(got == (head + want).encode(),
                   f"the {name} name leaves its unhashed lines, got {got!r}")

        absent = (work / "nowhere" / "riscv-tests.tar.gz").as_uri()
        for name, files, kept in (("kept", clean, True), ("removed", _SPLIT, False)):
            suite = _suite_of(work / name, files)
            manifest = _MODEL.corpus_manifest(suite)
            manifest.write_bytes(_cmake_listing(work, suite))
            done = _cmake(work, f'download_riscv_tests("{suite.parent}" "riscv-tests" '
                                f'"{absent}")\n')
            said = " ".join((done.stdout + done.stderr).split())
            again = "riscv-tests has no matching riscv-tests.manifest, downloading again"
            if kept:
                ensure(done.returncode == 0 and again not in said and suite.is_dir()
                       and manifest.is_file(),
                       f"control: configure keeps a clean suite beside its manifest, got "
                       f"{done.returncode} and {said[-400:]!r}")
            else:
                ensure(done.returncode != 0 and again in said
                       and not suite.exists() and not manifest.exists(),
                       f"configure removes a suite holding a split name and downloads it "
                       f"again, got {done.returncode} and {said[-400:]!r}")

        for name, files, extracts in (("fresh", clean, True), ("split", _SPLIT, False)):
            tarball = work / f"{name}.tar.gz"
            with tarfile.open(tarball, "w:gz") as archive:
                for member, data in files.items():
                    info = tarfile.TarInfo(member)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
            (work / name).mkdir()
            done = _cmake(work, f'download_riscv_tests("{work / name}" "riscv-tests" '
                                f'"{tarball.as_uri()}")\n', digest)
            said = " ".join(done.stderr.split())
            manifest = _MODEL.corpus_manifest(work / name / "riscv-tests")
            if extracts:
                ensure(done.returncode == 0 and manifest.read_bytes()
                       == _MODEL.corpus_listing(work / name / "riscv-tests", digest),
                       f"a verified tarball's suite is recorded as corpus_listing renders "
                       f"it, got {done.returncode} and {said[-400:]!r}")
            else:
                ensure(done.returncode != 0 and "a name the listing cannot hash" in said
                       and not manifest.exists(),
                       f"a tarball extracting a split name writes no manifest, got "
                       f"{done.returncode} and {said[-400:]!r}")

        for where in ("dl[x]", "dl;x"):
            suite = _suite_of(work / where, {"rv64ui-p-add": b"\x7fELF"})
            done = _cmake(work, f'download_riscv_tests("{suite.parent}" "riscv-tests" '
                                f'"{absent}")\n')
            said = " ".join(done.stderr.split())
            ensure(done.returncode != 0 and "holds [, ], *, ? or ;" in said
                   and (suite / "rv64ui-p-add").is_file(),
                   f"a download path holding {where[2]!r} is refused before its suite is "
                   f"touched, got {done.returncode} and {said[-400:]!r}")


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
        Case("verified-inputs-are-the-suites-top-level-programs",
             _verified_inputs_are_the_suites_top_level_programs),
        Case("seed-test-data", _seed_test_data),
        Case("seed-test-data-refuses-unverified", _seed_test_data_refuses_unverified),
        Case("seed-refuses-a-device-donor", _seed_refuses_a_device_donor),
        Case("seed-refuses-a-fifo-donor", _seed_refuses_a_fifo_donor, lane="guest"),
        Case("open-regular-asks-the-name-first", _open_regular_asks_the_name_first),
        Case("open-regular-refuses-what-the-name-answered-as-a-file",
             _open_regular_refuses_what_the_name_answered_as_a_file, lane="guest"),
        Case("seed-refuses-a-device-manifest", _seed_refuses_a_device_manifest),
        Case("seed-refuses-a-fifo-manifest", _seed_refuses_a_fifo_manifest, lane="guest"),
        Case("seed-refuses-a-manifest-linked-to-a-fifo",
             _seed_refuses_a_manifest_linked_to_a_fifo, lane="guest"),
        Case("verify-refuses-a-sparse-manifest", _verify_refuses_a_sparse_manifest,
             lane="guest"),
        Case("verify-reads-no-file-until-the-paths-agree",
             _verify_reads_no_file_until_the_paths_agree),
        Case("copy-regular-file", _copy_regular_file),
        Case("copy-regular-file-reads-no-further-than-verified",
             _copy_regular_file_reads_no_further_than_verified),
        Case("seed-copies-only-what-verified", _seed_copies_only_what_verified),
        Case("copy-regular-file-refuses-a-fifo-and-a-link",
             _copy_regular_file_refuses_a_fifo_and_a_link, lane="guest"),
        Case("seed-refuses-an-entry-replaced-during-the-copy",
             _seed_refuses_an_entry_replaced_during_the_copy, lane="guest"),
        Case("listing-hashes-only-regular-descriptors",
             _listing_hashes_only_regular_descriptors),
        Case("listing-refuses-a-fifo-its-check-by-name-missed",
             _listing_refuses_a_fifo_its_check_by_name_missed, lane="guest"),
        Case("receipt-records-what-verified", _receipt_records_what_verified),
        Case("receipt-opens-no-sweep-input-after-verifying",
             _receipt_opens_no_sweep_input_after_verifying, lane="guest"),
        Case("trace-diff-compares-what-verified", _trace_diff_compares_what_verified),
        Case("build-records-an-unreadable-product", _build_records_an_unreadable_product),
        Case("fresh-outputs-reads-only-this-builds-entries",
             _fresh_outputs_reads_only_this_builds_entries),
        Case("early-test-starts-on-this-builds-emission",
             _early_test_starts_on_this_builds_emission),
        Case("early-test-needs-this-builds-emission", _early_test_needs_this_builds_emission),
        Case("early-test-waits-for-memory", _early_test_waits_for_memory),
        Case("failed-build-discards-the-early-test", _failed_build_discards_the_early_test),
        Case("failed-early-test-fails-ctest", _failed_early_test_fails_ctest),
        Case("exception-ends-the-early-test", _exception_ends_the_early_test),
        Case("early-run-reports-and-ends-its-tree", _early_run_reports_and_ends_its_tree,
             lane="guest"),
        Case("early-run-ends-a-tree-still-forking", _early_run_ends_a_tree_still_forking,
             lane="guest"),

        # Only where cmake is on PATH: the runner has no skipped verdict, and a case
        # that returned without cmake would pass having decided nothing.
        *([Case("cmake-suite-listing", _cmake_suite_listing, lane="guest")]
          if shutil.which("cmake") else []),
    ]
