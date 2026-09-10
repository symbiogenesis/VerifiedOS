# SPDX-License-Identifier: Apache-2.0
"""Verilator's source integrity and the executable the provisioner actually probes."""

import hashlib
import io
import tarfile
from argparse import Namespace
from contextlib import nullcontext
from subprocess import CompletedProcess
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import env
from vos.cli import provision, rtl


def _rejects_changed_archive_before_extraction() -> None:
    with sandbox_tree({"archive.tar.gz": "changed download"}) as root:
        work = root / "source"
        try:
            rtl._extract_verilator(root / "archive.tar.gz", work)
        except ValueError as error:
            ensure("SHA256" in str(error), "the refusal must name the failed integrity check")
        else:
            raise AssertionError("a changed source archive was accepted")
        ensure(not work.exists(), "no archive member may be extracted before integrity passes")


def _authenticated_archive_cannot_escape() -> None:
    with sandbox_tree({"README.md": "fixture"}) as root:
        archive = root / "archive.tar.gz"
        with tarfile.open(archive, "w:gz") as source:
            entry = tarfile.TarInfo("../escaped")
            entry.size = 1
            source.addfile(entry, io.BytesIO(b"x"))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        with patch.object(rtl, "VERILATOR_SHA256", digest):
            try:
                rtl._extract_verilator(archive, root / "source")
            except tarfile.FilterError:
                pass
            else:
                raise AssertionError("a path outside the source directory was accepted")
        ensure(not (root / "escaped").exists(), "archive paths must stay inside the source tree")


def _verified_archive_replaces_stale_source_tree() -> None:
    name = f"verilator-{rtl.VERILATOR_PIN}"
    with sandbox_tree({f"{name}/stale.o": "unverified object"}) as root:
        archive = root / "archive.tar.gz"
        with tarfile.open(archive, "w:gz") as source:
            entry = tarfile.TarInfo(f"{name}/source.txt")
            entry.size = 1
            source.addfile(entry, io.BytesIO(b"x"))
        with patch.object(rtl, "VERILATOR_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()):
            extracted = rtl._extract_verilator(archive, root)
        ensure((extracted / "source.txt").read_bytes() == b"x", "verified source must be extracted")
        ensure(not (extracted / "stale.o").exists(), "old build products must not enter a new build")


def _failed_repair_invalidates_receipt() -> None:
    with (sandbox_tree({"README.md": "fixture"}) as root,
          patch.object(env, "build_root", return_value=root),
          patch.object(env, "_lane", return_value="test"),
          patch.object(env, "hold_lock", return_value=nullcontext()),
          patch.object(rtl, "_verilator_version", return_value="0.000"),
          patch.object(rtl.shutil, "which", return_value="/usr/bin/verilator"),
          patch.object(rtl.subprocess, "run", return_value=CompletedProcess([], 0)),
          patch.object(rtl, "_extract_verilator", side_effect=ValueError("bad source"))):
        prefix = rtl.verilator_prefix()
        (prefix / "bin").mkdir(parents=True)
        (prefix / "bin/verilator").write_text("broken binary", encoding="utf-8")
        receipt = prefix / "source.sha256"
        receipt.write_text(rtl.VERILATOR_SHA256, encoding="utf-8")
        work = root / "lane-test" / f"verilator-{rtl.VERILATOR_PIN}-source"
        work.mkdir(parents=True)
        (work / f"verilator-{rtl.VERILATOR_PIN}.tar.gz").write_bytes(b"cached source")
        ensure(rtl.cmd_install(Namespace(jobs=1)) == 1, "the attempted repair must report failure")
        ensure(not receipt.exists(), "a failed repair must invalidate the previous completion receipt")
        ensure(rtl._verilator() == "/usr/bin/verilator", "the partial prefix must not be selected")


def _provision_probes_the_selected_project_binary() -> None:
    with (sandbox_tree({"README.md": "fixture"}) as root,
          patch.object(env, "build_root", return_value=root)):
        binary = rtl.verilator_prefix() / "bin" / "verilator"
        binary.parent.mkdir(parents=True)
        binary.write_text("fixture", encoding="utf-8")
        with (patch.object(rtl.shutil, "which", return_value="/usr/bin/verilator"),
              patch.object(provision, "_at_version",
                           return_value=provision.Found(True, rtl.VERILATOR_PIN)) as probe):
            ensure(rtl._verilator() == "/usr/bin/verilator",
                   "an unfinished installation must not hide the working PATH binary")
            (rtl.verilator_prefix() / "source.sha256").write_text(
                rtl.VERILATOR_SHA256, encoding="utf-8")
            ensure(rtl._verilator() == str(binary), "the project binary precedes PATH")
            ensure(provision._verilator().present, "the selected binary is what gets probed")
            probe.assert_called_once_with((str(binary), "--version"), rtl.VERILATOR_PIN)
            binary.unlink()
            ensure(rtl._verilator() == "/usr/bin/verilator",
                   "PATH remains available when no project installation exists")


def cases() -> list[Case]:
    return [
        Case("changed-archive-is-rejected", _rejects_changed_archive_before_extraction),
        Case("authenticated-archive-cannot-escape", _authenticated_archive_cannot_escape),
        Case("verified-archive-replaces-stale-source", _verified_archive_replaces_stale_source_tree),
        Case("failed-repair-invalidates-receipt", _failed_repair_invalidates_receipt),
        Case("provision-probes-project-binary", _provision_probes_the_selected_project_binary),
    ]
