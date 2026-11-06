# SPDX-License-Identifier: Apache-2.0
"""Support-source authentication, bounded compatibility and qualification refusals."""

import hashlib
import io
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.vela import parser_checked as checked


def _tar(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as bundle:
        root = tarfile.TarInfo("release")
        root.type = tarfile.DIRTYPE
        bundle.addfile(root)
        for name, contents in files.items():
            member = tarfile.TarInfo(f"release/{name}")
            member.size = len(contents)
            bundle.addfile(member, io.BytesIO(contents))
    return stream.getvalue()


def _files() -> dict[str, bytes]:
    files = {f"coq-menhirlib/src/{name}.v": b"fixture source\n" for name in checked.MODULES}
    files.update({"coq-menhirlib/src/_CoqProject": b"fixture project\n",
                  "LICENSE": b"generator terms\n", "coq-menhirlib/LICENSE": b"support terms\n"})
    return files


def _archive_controls() -> None:
    files = _files()
    licenses = {name: checked._sha256(files[name]) for name in checked.LICENSES}
    version = checked._sha256(files["coq-menhirlib/src/Version.v"])
    original = _tar(files)
    with patch.object(checked, "LICENSES", licenses), patch.object(checked, "VERSION_SHA256", version):
        with patch.object(checked, "ARCHIVE_SHA512", hashlib.sha512(original).hexdigest()):
            ensure(checked._release_sources(original) == files, "authenticated selected sources changed")
            try:
                checked._release_sources(original + b"corruption")
            except ValueError as error:
                ensure("digest" in str(error), "archive corruption lost its cause")
            else:
                raise AssertionError("corrupt archive consumed")
        for change in ("missing", "license", "version", "escape"):
            changed = dict(files)
            if change == "missing":
                changed.pop("coq-menhirlib/src/Main.v")
            elif change == "license":
                changed["coq-menhirlib/LICENSE"] += b"changed"
            elif change == "version":
                changed["coq-menhirlib/src/Version.v"] = b"Definition require_unreleased := tt.\n"
            else:
                changed["../escape"] = b"unsafe"
            archive = _tar(changed)
            with patch.object(checked, "ARCHIVE_SHA512", hashlib.sha512(archive).hexdigest()):
                try:
                    checked._release_sources(archive)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"unsupported {change} archive accepted")


def _proof_footprint() -> None:
    # Original authored fixtures: no upstream proof text is incorporated here.
    original = b"".join(f"Definition {name} : nat.\nrefine 0.\nProof.\nexact 0.\nDefined.\n".encode()
                         for name in checked.TARGETS)
    candidate = original.replace(b"refine 0.\nProof.\n", b"Proof.\nrefine 0.\n")
    reference = original.replace(b"Proof.\n", b"")
    with patch.object(checked, "INTERPRETER_SHA256", checked._sha256(original)), \
            patch.object(checked, "CANDIDATE_SHA256", checked._sha256(candidate)), \
            patch.object(checked, "REFERENCE_SHA256", checked._sha256(reference)):
        ensure(checked._proof_openings(original) == candidate, "repair changed more than proof openings")
        ensure(checked._proof_openings(original, reference=True) == reference, "diagnostic twin changed terms")
        for source in (original + b"changed", candidate):
            try:
                checked._proof_openings(source)
            except ValueError as error:
                ensure("unsupported" in str(error), "unsupported source repair lost its cause")
            else:
                raise AssertionError("repair accepted different or already modified source")
        with patch.object(checked, "CANDIDATE_SHA256", "0" * 64):
            try:
                checked._proof_openings(original)
            except ValueError as error:
                ensure("reviewed candidate" in str(error), "changed repair digest lost its cause")
            else:
                raise AssertionError("unexpected repaired bytes accepted")


def _process_controls() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-support-") as temporary:
        directory = Path(temporary)
        for code, output, expected in ((1, b"require_unreleased was not found", True),
                                       (0, b"require_unreleased", False),
                                       (1, b"unrelated error", False),
                                       (127, b"require_unreleased", False)):
            process = subprocess.CompletedProcess(["rocq"], code, b"", output)
            steps: list[dict[str, object]] = []
            with patch.object(checked.subprocess, "run", return_value=process) as run:
                try:
                    checked._run(["rocq"], directory, directory / "control.stdout", steps,
                                 refusal="require_unreleased")
                except RuntimeError:
                    ensure(not expected, "genuine mismatched-version refusal failed")
                else:
                    ensure(expected, "successful or unrelated failure counted as negative control")
            ensure(run.call_args.kwargs["timeout"] == checked.TIMEOUT, "command lost its duration bound")
            ensure(steps[0]["exit"] == code, "command verdict not journalled")
        with patch.object(checked.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                "rocq", checked.TIMEOUT, output=b"partial", stderr=b"diagnostic")):
            steps = []
            try:
                checked._run(["rocq"], directory, directory / "timeout.stdout", steps)
            except RuntimeError as error:
                ensure("exceeded" in str(error), "timeout lacks a diagnostic")
            else:
                raise AssertionError("timed-out support command passed")
            ensure(steps[0]["status"] == "timeout", "timed-out attempt lost its verdict")
            ensure((directory / "timeout.stdout").read_bytes() == b"partialdiagnostic", "partial failure log lost")


def _refused_qualification() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-support-") as temporary:
        directory = Path(temporary)
        latest = directory / "qualification.json"
        latest.write_text('{"status":"passed","old":true}', encoding="utf-8")
        with patch.object(checked, "_work_root", return_value=directory), \
                patch.object(checked, "_inputs", return_value={}), \
                patch.object(checked, "_toolchain", side_effect=ValueError("different locked prover")):
            try:
                checked.qualify(directory)
            except ValueError as error:
                ensure("different locked prover" in str(error), "qualification failure swallowed")
            else:
                raise AssertionError("unsupported toolchain acquired a passing receipt")
        ensure(not latest.exists(), "failed qualification preserved old success")
        attempts = list(directory.glob("support-*/attempt.json"))
        ensure(len(attempts) == 1 and '"status": "failed"' in attempts[0].read_text(encoding="utf-8"),
               "failed qualification lost its retained attempt")


def _toolchain_controls() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-support-") as temporary:
        directory = Path(temporary)
        locks = directory / "tools/opam"
        locks.mkdir(parents=True)
        sail = locks / "sail.lock"
        sail.write_text(f'"menhir.{checked.RELEASE}"\n', encoding="utf-8")
        (locks / "rocq.lock").write_text(f'"rocq-core.{checked.proofenv.ROCQ_VERSION}"\n', encoding="utf-8")
        for name in ("rocq", "rocqchk", "ocamlc"):
            (directory / name).write_bytes(b"tool identity")
        expected = [f"The Rocq Prover, version {checked.proofenv.ROCQ_VERSION}",
                    checked.proofenv.OCAML_VERSION, str(directory)]
        with patch.object(checked, "_run", side_effect=expected):
            identity = checked._toolchain(directory, directory, [])
        digests = identity["binary_sha256"]
        ensure(isinstance(digests, dict) and len(digests) == 3, "support tools lost executable identities")
        for index in (0, 1, 2):
            changed = [*expected]
            changed[index] = "different identity"
            with patch.object(checked, "_run", side_effect=changed):
                try:
                    checked._toolchain(directory, directory, [])
                except ValueError:
                    pass
                else:
                    raise AssertionError("unsupported tool identity accepted")
        sail.write_text('"menhir.different"\n', encoding="utf-8")
        with patch.object(checked, "_run") as run:
            try:
                checked._toolchain(directory, directory, [])
            except ValueError as error:
                ensure("Sail snapshot" in str(error), "different generator source lost its cause")
            else:
                raise AssertionError("support source disagreed with locked generator")
            run.assert_not_called()


def _changed_observations() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-support-observations-") as temporary:
        root = Path(temporary)
        candidate, reference = root / "candidate", root / "reference"
        candidate.mkdir()
        reference.mkdir()
        guard = f"Definition guard := Version.require_{checked.RELEASE}.\n"
        files = {candidate / "Frozen.v": checked.FROZEN_QUERY, reference / "Frozen.v": checked.FROZEN_QUERY,
                 candidate / "Assumptions.v": checked.ASSUMPTIONS_QUERY,
                 candidate / "VersionAccepted.v": guard,
                 candidate / "VersionRefused.v": guard.replace(f"require_{checked.RELEASE}", "require_unreleased"),
                 root / "run.stdout": "Closed under the global context\n", root / "run.stderr": ""}
        steps: list[dict[str, object]] = [{"stdout": str(root / "run.stdout"), "stderr": str(root / "run.stderr"),
                                         "stdout_sha256": checked._sha256(files[root / "run.stdout"].encode()),
                                         "stderr_sha256": checked._sha256(b"")}]
        for changed in (None, *files):
            for path, text in files.items():
                path.write_text(text, encoding="utf-8", newline="")
            if changed is not None:
                changed.write_bytes(b"substituted observation")
            try:
                checked._observations(candidate, reference, guard, steps)
            except ValueError as error:
                ensure(changed is not None and "changed" in str(error), "unexpected observation refusal")
            else:
                ensure(changed is None, "changed proof probe or transcript acquired qualification")


def cases() -> list[Case]:
    return [Case("immutable-source-and-version-controls", _archive_controls),
            Case("proof-opening-byte-footprint", _proof_footprint),
            Case("bounded-command-and-negative-verdict-controls", _process_controls),
            Case("locked-generator-and-prover-controls", _toolchain_controls),
            Case("changed-probes-and-transcripts-refuse", _changed_observations),
            Case("failed-qualification-discards-stale-success", _refused_qualification)]
