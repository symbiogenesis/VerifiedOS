# SPDX-License-Identifier: Apache-2.0
"""Guest installation refuses corrupt inputs and preserves failed process verdicts."""

import hashlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from ci import bootstrap_guest as bootstrap
from tests.harness import Case, ensure


def _download_integrity() -> None:
    payload = b"verified release bytes"
    expected = hashlib.sha256(payload).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "client"
        with patch.object(bootstrap.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
            bootstrap.download("https://example.invalid/client", target, expected)
        ensure(target.read_bytes() == payload, "verified bytes were not published")
        with patch.object(bootstrap.urllib.request, "urlopen") as network:
            bootstrap.download("https://example.invalid/client", target, expected)
            ensure(not network.called, "a verified cached archive should require no download")
        target.write_bytes(b"corrupt")
        with patch.object(bootstrap.urllib.request, "urlopen") as network:
            try:
                bootstrap.download("https://example.invalid/client", target, expected)
            except ValueError:
                pass
            else:
                raise AssertionError("a corrupt cached executable was accepted")
            ensure(not network.called, "corrupt cache must be refused explicitly")


def _bad_download_never_published() -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "client"
        with patch.object(bootstrap.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
            try:
                bootstrap.download("https://example.invalid/client", target, "0" * 64)
            except ValueError:
                pass
            else:
                raise AssertionError("a corrupt download was accepted")
        ensure(not target.exists() and not target.with_suffix(".download").exists(),
               "a failed download left executable or partial bytes behind")


def _missing_dependency_refuses() -> None:
    with (patch.object(bootstrap, "missing_packages", return_value=["device-tree-compiler"]),
          patch.object(bootstrap, "run") as launched):
        try:
            bootstrap.system_packages(False, io.StringIO())
        except ValueError as error:
            ensure("device-tree-compiler" in str(error), "missing package was not named")
        else:
            raise AssertionError("missing dependency was accepted")
        ensure(not launched.called, "check-only mode attempted a system mutation")


def _nonroot_system_install() -> None:
    with (patch.object(bootstrap, "missing_packages", side_effect=[["m4"], []]),
          patch.object(bootstrap.os, "geteuid", return_value=1000, create=True),
          patch.object(bootstrap, "run") as launched):
        bootstrap.system_packages(True, io.StringIO())
        ensure(len(launched.call_args_list) == 2, "system install did not update and install")
        for call in launched.call_args_list:
            ensure(call.args[0][:2] == ("sudo", "-n"), "non-root install may prompt or lacks sudo")


def _existing_switch_resumes_import() -> None:
    steps = (("opam", "switch", "create", "private", "--empty", "-y"),
             ("opam", "switch", "import", "snapshot.lock", "--switch=private", "-y"))
    result = subprocess.CompletedProcess([], 0, stdout="private\n")
    with (patch.object(bootstrap.subprocess, "run", return_value=result),
          patch.object(bootstrap, "run") as launched):
        bootstrap.install_switch(steps, io.StringIO())
        ensure(len(launched.call_args_list) == 1, "retry recreated an existing switch")
        ensure(launched.call_args.args[0] == steps[1], "retry skipped the snapshot import")


def _failed_child_remains_failure() -> None:
    with (tempfile.TemporaryDirectory() as directory,
          (Path(directory) / "log").open("w", encoding="utf-8") as log):
        try:
            bootstrap.run((sys.executable, "-c", "raise SystemExit(7)"), log)
        except subprocess.CalledProcessError as error:
            ensure(error.returncode == 7, "child's failure code was changed")
        else:
            raise AssertionError("failed prerequisite was accepted")


def _foreign_directory_is_not_adopted() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "foreign"
        root.mkdir()
        other = root / "valuable.txt"
        other.write_text("keep", encoding="utf-8")
        try:
            bootstrap.claim_root(root)
        except ValueError as error:
            ensure("nonempty unowned" in str(error), "the ownership check was not reached")
        else:
            raise AssertionError("installer adopted an unrelated nonempty directory")
        ensure(other.read_text(encoding="utf-8") == "keep", "foreign contents changed")
        ensure(not (root / bootstrap.MARKER).exists(), "foreign directory acquired ownership")


def _owned_directory_reused() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "private"
        first = bootstrap.claim_root(root)
        (first / "retained.txt").write_text("keep", encoding="utf-8")
        second = bootstrap.claim_root(root)
        ensure(first == second and (second / "retained.txt").exists(),
               "resuming bootstrap discarded its existing state")


def _environment_is_private_and_exports_validated() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.dict(os.environ, {}, clear=True):
            values = bootstrap.environment(root, 2)
        for key in ("OPAMROOT", "VOS_BUILD_ROOT", "VOS_LOG_DIR", "VOS_Z3_BIN", "CCACHE_DIR",
                    "TMPDIR", "UV_CACHE_DIR"):
            ensure(Path(values[key]).is_relative_to(root), f"{key} escapes the private root")
        env_file, path_file = root / "github-env", root / "github-path"
        bootstrap.export_environment(values, root / "bin", env_file, path_file)
        ensure(f"TMPDIR={root / 'tmp'}\n" in env_file.read_text(encoding="utf-8"),
               "GitHub environment did not retain native scratch path")
        before = env_file.read_bytes()
        try:
            bootstrap.export_environment({"TMPDIR": "a\nINJECTED=b"}, root, env_file, path_file)
        except ValueError:
            pass
        else:
            raise AssertionError("multiline environment value accepted")
        ensure(env_file.read_bytes() == before, "invalid export partially wrote its output")


def cases() -> list[Case]:
    return [
        Case("download integrity and verified reuse", _download_integrity),
        Case("corrupt download never published", _bad_download_never_published),
        Case("missing dependency refusal", _missing_dependency_refuses),
        Case("unattended non-root package installation", _nonroot_system_install),
        Case("retry imports existing switch", _existing_switch_resumes_import),
        Case("failed process remains failure", _failed_child_remains_failure),
        Case("foreign directory not adopted", _foreign_directory_is_not_adopted),
        Case("owned directory resumed", _owned_directory_reused),
        Case("private native environment and validated export", _environment_is_private_and_exports_validated),
    ]
