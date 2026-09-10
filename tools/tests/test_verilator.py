# SPDX-License-Identifier: Apache-2.0
"""Verilator's source integrity and the executable the provisioner actually probes."""

import hashlib
import io
import tarfile
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
        Case("provision-probes-project-binary", _provision_probes_the_selected_project_binary),
    ]
