# SPDX-License-Identifier: Apache-2.0
"""Guest installation refuses corrupt inputs and preserves failed process verdicts."""

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import IO
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


def _package_query_is_batched() -> None:
    packages = ("installed", "missing", "unconfigured", "multiarch")
    result = subprocess.CompletedProcess([], 1, stdout=(
        "installed\tinstall ok installed\n"
        "unconfigured\tinstall ok unpacked\n"
        "multiarch\tinstall ok installed\nmultiarch\tinstall ok installed\n"))
    with (patch.object(bootstrap, "PACKAGES", packages),
          patch.object(bootstrap.subprocess, "run", return_value=result) as query):
        ensure(bootstrap.missing_packages() == list(packages[1:]),
               "batch query lost missing, unconfigured or ambiguous packages")
        ensure(query.call_count == 1 and query.call_args.args[0][-4:] == packages,
               "package detection did not use one query for every dependency")
    result = subprocess.CompletedProcess([], 2, stdout="", stderr="database unreadable")
    with patch.object(bootstrap.subprocess, "run", return_value=result):
        try:
            bootstrap.missing_packages()
        except subprocess.CalledProcessError as error:
            ensure(error.returncode == 2, "fatal query failure was changed")
        else:
            raise AssertionError("a broken package database was treated as missing packages")


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


def _solver_available_before_sail() -> None:
    root = Path.home() / "guest-bootstrap-toolchain-fixture"
    solver_bin = str(root / "z3" / "bin")
    observed: list[str] = []

    def run(argv: tuple[str, ...], log: IO[str]) -> None:
        if argv[0] == "uv":
            observed.append("solver-install")
        elif argv[0] == str(root / "z3" / "bin" / "z3"):
            observed.append("solver-probe")
        elif "sail" in argv:
            ensure(observed == ["solver-install", "solver-probe", "sail-install"],
                   "Sail started before its solver was installed and probed")
            ensure(os.environ["PATH"].split(os.pathsep) == [solver_bin, "existing-tools"],
                   "Sail cannot find the private solver ahead of existing tools")
            observed.append("sail-probe")
        elif argv[0] == str(root / "opam" / bootstrap.env.ROCQ_SWITCH / "bin" / "rocq"):
            observed.append("rocq-probe")
        elif "rtl" in argv:
            observed.append("rtl-install")

    def install(steps: tuple[tuple[str, ...], ...], log: IO[str]) -> None:
        observed.append("sail-install" if steps == bootstrap.env.SAIL_INSTALL else "rocq-install")

    with (patch.dict(os.environ, {"PATH": "existing-tools"}),
          patch.object(bootstrap, "run", side_effect=run),
          patch.object(bootstrap, "install_switch", side_effect=install)):
        bootstrap.install_toolchains(root, 2, io.StringIO())
    ensure(observed == ["solver-install", "solver-probe", "sail-install", "sail-probe",
                        "rocq-install", "rocq-probe", "rtl-install"],
           "toolchain probes were deferred until after unrelated builds")


def _sail_probe_failure_stops_remaining_builds() -> None:
    root = Path.home() / "guest-bootstrap-toolchain-fixture"

    def run(argv: tuple[str, ...], log: IO[str]) -> None:
        if "sail" in argv:
            raise subprocess.CalledProcessError(2, argv)

    with (patch.dict(os.environ), patch.object(bootstrap, "run", side_effect=run),
          patch.object(bootstrap, "install_switch") as install):
        try:
            bootstrap.install_toolchains(root, 2, io.StringIO())
        except subprocess.CalledProcessError as error:
            ensure(error.returncode == 2, "the Sail probe failure was changed")
        else:
            raise AssertionError("failed Sail probe was accepted")
        ensure(install.call_count == 1, "a failed Sail probe still built the Rocq switch")


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


def _invalid_marker_refused() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        marker = root / bootstrap.MARKER
        for content in ("", "2\n", "unrelated\n"):
            marker.write_text(content, encoding="utf-8", newline="")
            try:
                bootstrap.claim_root(root)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid ownership marker accepted")
            ensure(marker.read_text(encoding="utf-8") == content,
                   "refused ownership marker was overwritten")


def _unsupported_filesystem_refused() -> None:
    root = Path.home() / "guest-bootstrap-placement-fixture"
    for kind in ("", "9p", "tmpfs"):
        with (patch.object(bootstrap.env, "filesystem", return_value=kind),
              patch.object(bootstrap, "claim_root") as claimed):
            try:
                bootstrap.prepare_root(root)
            except ValueError as error:
                ensure("native persistent filesystem" in str(error), "wrong placement refusal")
            else:
                raise AssertionError(f"unsupported filesystem {kind!r} was accepted")
            ensure(not claimed.called, "installer wrote into unverified storage")


def _environment_is_private_and_exports_validated() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.dict(os.environ, {}, clear=True):
            values = bootstrap.environment(root, 2)
        for key in ("OPAMROOT", "VOS_BUILD_ROOT", "VOS_LOG_DIR", "VOS_Z3_BIN", "CCACHE_DIR",
                    "TMPDIR", "UV_CACHE_DIR"):
            ensure(Path(values[key]).is_relative_to(root), f"{key} escapes the private root")
        env_file, path_file = root / "github-env", root / "github-path"
        paths = (root / "z3" / "bin", root / "bin")
        bootstrap.export_environment(values, paths, env_file, path_file)
        ensure(f"TMPDIR={root / 'tmp'}\n" in env_file.read_text(encoding="utf-8"),
               "GitHub environment did not retain native scratch path")
        before = env_file.read_bytes()
        ensure(path_file.read_text(encoding="utf-8").splitlines() ==
               [str(path) for path in reversed(paths)], "GitHub PATH precedence was changed")
        activation = bootstrap.activation(values, paths)
        ensure(str(paths[0]) in activation and str(paths[1]) in activation,
               "shell activation omitted a private tool directory")
        try:
            bootstrap.export_environment({"TMPDIR": "a\nINJECTED=b"}, paths, env_file, path_file)
        except ValueError:
            pass
        else:
            raise AssertionError("multiline environment value accepted")
        ensure(env_file.read_bytes() == before, "invalid export partially wrote its output")


def _failed_retention_preserves_verdict() -> None:
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
        root = Path(directory)
        logs = root / "logs"
        logs.mkdir()
        stale = (root / "environment.sh", logs / "evidence.json", logs / "proof-evidence.json",
                 logs / "results.json")
        for path in stale:
            path.write_text("old success", encoding="utf-8")
        (logs / "bootstrap.json").write_text('{"exit_code": 0}', encoding="utf-8")
        args = argparse.Namespace(jobs=2, install_system=False, github_env=None, github_path=None)
        with (patch.object(bootstrap, "system_packages",
                           side_effect=subprocess.CalledProcessError(7, ("apt-get", "update"))),
              patch.object(bootstrap, "retain_logs", side_effect=OSError("copy failed"))):
            code = bootstrap.install(args, root, "fixture")
        record = json.loads((logs / "bootstrap.json").read_text(encoding="utf-8"))
        ensure(code == record["exit_code"] == 1, "diagnostic failure lost the bootstrap verdict")
        ensure("7" in record["error"] and record["diagnostic_error"] == "copy failed",
               "log retention failure masked the original command error")
        ensure("seconds" in record, "failure lost its duration")
        ensure(not any(path.exists() for path in stale), "retry retained stale gate evidence")


def _busy_root_is_untouched() -> None:
    manifest = bootstrap.tomllib.loads((bootstrap.TOOLS / "pyproject.toml").read_text(encoding="utf-8"))
    version = manifest["tool"]["uv"]["required-version"].removeprefix("==")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        logs = root / "logs"
        logs.mkdir()
        record = logs / "environment.json"
        record.write_text("another bootstrap owns this", encoding="utf-8")
        args = argparse.Namespace(root=root, jobs=2, install_system=False,
                                  github_env=None, github_path=None)
        with (patch.object(bootstrap.sys, "platform", "linux"),
              patch.object(bootstrap.platform, "machine", return_value="x86_64"),
              patch.object(bootstrap.subprocess, "run", return_value=subprocess.CompletedProcess(
                  [], 0, stdout=f"uv {version}\n")),
              patch.object(bootstrap, "prepare_root", return_value=root),
              patch.object(bootstrap.env, "hold_lock", side_effect=SystemExit("already held")),
              patch.object(bootstrap, "install") as install):
            try:
                bootstrap.bootstrap(args)
            except SystemExit as error:
                ensure(str(error) == "already held", "lock refusal was changed")
            else:
                raise AssertionError("a busy root was accepted")
            ensure(not install.called, "bootstrap installed into a busy root")
        ensure(record.read_text(encoding="utf-8") == "another bootstrap owns this",
               "bootstrap wrote run state before acquiring its lock")
        ensure(not (root / "bin").exists(), "bootstrap created directories in a busy root")


def cases() -> list[Case]:
    return [
        Case("download integrity and verified reuse", _download_integrity),
        Case("corrupt download never published", _bad_download_never_published),
        Case("missing dependency refusal", _missing_dependency_refuses),
        Case("batched package query preserves missing and fatal outcomes", _package_query_is_batched),
        Case("unattended non-root package installation", _nonroot_system_install),
        Case("retry imports existing switch", _existing_switch_resumes_import),
        Case("failed process remains failure", _failed_child_remains_failure),
        Case("private solver precedes Sail startup", _solver_available_before_sail),
        Case("failed Sail probe stops subsequent builds", _sail_probe_failure_stops_remaining_builds),
        Case("foreign directory not adopted", _foreign_directory_is_not_adopted),
        Case("owned directory resumed", _owned_directory_reused),
        Case("invalid ownership marker refused without replacement", _invalid_marker_refused),
        Case("unverified or unsuitable filesystem refused", _unsupported_filesystem_refused),
        Case("private native environment and validated export", _environment_is_private_and_exports_validated),
        Case("log retention failure preserves verdict and discards stale evidence", _failed_retention_preserves_verdict),
        Case("busy root preserves the active bootstrap's state", _busy_root_is_untouched),
    ]
