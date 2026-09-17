# SPDX-License-Identifier: Apache-2.0
"""Proof cache invalidation follows bytes and prerequisite closures, not mtimes."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import receipts
from vos.cli import proofs as gate


def _incremental_run() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-cache-") as temporary:
        root = Path(temporary) / "source"
        folder = root / "proofs"
        folder.mkdir(parents=True)
        work = Path(temporary) / "output"
        work.mkdir()
        texts = {"ApexTheorem": "Theorem sound : True. Proof. exact I. Qed.",
                 "Base": "Definition value := 0.",
                 "Consumer": "Require Base. Definition value := Base.value."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        owner = root / "gate-input.txt"
        owner.write_text("gate input", encoding="utf-8")
        compiled_names: list[str] = []
        audited: list[str] = []
        context: dict[str, object] = {"library_hash": "first"}
        toolchain = {"pin": gate.env.ROCQ_VERSION, "binary": "first"}
        failing: set[str] = set()

        def inputs(base: Path, sources: list[Path]) -> dict[str, str]:
            return receipts.snapshot(base, [*sources, owner])

        def check(_root: Path, source: Path, _sources: list[Path], *,
                  compiled: bool = False) -> gate.Checked:
            if not compiled:
                compiled_names.append(source.stem)
                source.with_suffix(".vo").write_bytes(source.read_bytes())
            audited.append(source.stem)
            return gate.Checked(source, symbols=[{
                "name": f"{source.stem}.sound", "type": "True", "claims": [], "assumptions": []}],
                error="seeded failure" if source.stem in failing else "")

        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=inputs), \
                patch.object(gate, "_toolchain", return_value=toolchain), \
                patch.object(gate, "_cache_context", side_effect=lambda *_: dict(context)), \
                patch.object(gate, "_check_source", side_effect=check), \
                patch.object(gate, "_recheck", return_value=subprocess.CompletedProcess(
                    [], 0, stdout="", stderr="")) as recheck, \
                contextlib.redirect_stdout(io.StringIO()):

            def run(expected: set[str], *, fresh: bool = False, result: int = 0,
                    kernel: bool = True) -> None:
                compiled_names.clear()
                audited.clear()
                recheck.reset_mock()
                ensure(gate._run_locked(root, 2, fresh) == result, "unexpected gate verdict")
                ensure(set(compiled_names) == expected,
                       f"compiled {compiled_names}, expected {expected}")
                ensure(recheck.call_count == int(kernel), "wrong kernel recheck reuse decision")

            run(set(texts))
            receipt = (work / gate.RECEIPT).read_bytes()
            run(set(), kernel=False)
            ensure(not audited, "unchanged receipt must avoid repeated native audits")
            ensure((work / gate.RECEIPT).read_bytes() == receipt,
                   "reuse must retain the original completed run's evidence")

            # A content change with exactly preserved timestamps still invalidates.
            source = folder / "Base.v"
            stamp = source.stat()
            source.write_text(texts["Base"].replace("0", "1"), encoding="utf-8")
            os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            run({"Base", "Consumer"})
            ensure(set(audited) == set(texts), "changed runs must audit even cached objects")

            source = folder / "Consumer.v"
            source.write_text(texts["Consumer"] + "\n(* edited *)", encoding="utf-8")
            run({"Consumer"})
            (work / "proofs" / "Base.vo").write_bytes(b"corrupted object")
            run({"Base", "Consumer"})
            (work / "proofs" / "Consumer.vo").unlink()
            run({"Consumer"})
            context["library_hash"] = "changed-library"
            run(set(texts))
            toolchain["binary"] = "changed-compiler"
            run(set(texts))
            owner.write_text("changed gate input", encoding="utf-8")
            run(set(texts))
            run(set(texts), fresh=True)

            # Source-set changes and malformed prior receipts are conservative misses.
            (folder / "Added.v").write_text("Definition value := 1.", encoding="utf-8")
            run({*texts, "Added"})
            (folder / "Added.v").unlink()
            run(set(texts))
            (work / gate.RECEIPT).write_text("{broken", encoding="utf-8")
            run(set(texts))

            # A failed prerequisite cannot leave a dependent's stale object or receipt.
            failing.add("Base")
            (folder / "Base.v").write_text("broken", encoding="utf-8")
            run({"Base"}, result=1, kernel=False)
            ensure(not (work / "proofs" / "Consumer.vo").exists(), "stale consumer survived")
            ensure(not (work / gate.RECEIPT).exists(), "failed run left successful evidence")
            failing.clear()

            def tamper(_root: Path, sources: list[Path]) -> subprocess.CompletedProcess[str]:
                sources[0].with_suffix(".vo").write_bytes(b"changed during kernel check")
                return subprocess.CompletedProcess([], 0, stdout="", stderr="")

            recheck.side_effect = tamper
            run(set(texts), result=1)
            ensure(not (work / gate.RECEIPT).exists(), "changed kernel input received a receipt")
            recheck.side_effect = None
            with patch.object(gate, "_cache_context", return_value=None):
                run(set(texts))
                run(set(texts))


def _context_hashes_library_bytes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-context-") as temporary:
        work = Path(temporary)
        library = work / "library"
        runtime = work / "runtime"
        library.mkdir()
        runtime.mkdir()
        artifact = library / "Base.vo"
        artifact.write_bytes(b"first")
        source = work / "Example.v"
        source.write_text("Record Load := { level : nat }.\n"
                          "Theorem sound : True. Proof. exact I. Qed.", encoding="utf-8")
        # Print LoadPath uses absolute POSIX paths in the guest.
        physical = library.as_posix()
        listing = f"Installed / Logical Path / Physical path:\ni Corelib\n  {physical}\n"
        config = f"COQLIB={library}\nCOQCORELIB={runtime}\n"

        def invoke(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            value = config if command[-1] == "-config" else (
                str(library) if command[-1] == "-where" else listing)
            return subprocess.CompletedProcess(command, 0, stdout=value, stderr="")

        # Native path parsing is tested in the guest; the incremental state machine
        # above runs on both operating systems.
        with patch.object(gate.env, "rocq_command", return_value=["rocq", "c"]), \
                patch.object(gate.env, "rocqchk_command", return_value=["rocqchk"]), \
                patch.object(gate.subprocess, "run", side_effect=invoke), \
                patch.dict(os.environ, {"CACHE_TEST_SECRET": "do-not-record-this"}):
            before = gate._cache_context(work, [source])
            ensure(before is not None, "known load-path output must enable caching")
            ensure("do-not-record-this" not in json.dumps(before), "environment values leaked")
            with patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/new_interop",
                                         "SHLVL": "9", "_": "different-launcher"}):
                ensure(before == gate._cache_context(work, [source]),
                       "launch bookkeeping must not defeat reuse across WSL invocations")
            with patch.dict(os.environ, {"ROCQPATH": "/different/library"}):
                ensure(before != gate._cache_context(work, [source]),
                       "library environment changes must invalidate cached evidence")
            stamp = artifact.stat()
            artifact.write_bytes(b"other")
            os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            ensure(before != gate._cache_context(work, [source]), "library bytes escaped identity")
            for command in ('Load "external.v".', 'Time Load "external.v".',
                            'Add ML Path "external".', 'Declare ML Module "external".'):
                source.write_text(command, encoding="utf-8")
                ensure(gate._cache_context(work, [source]) is None,
                       f"dynamic command reused evidence: {command}")


def cases() -> list[Case]:
    return [Case("incremental-proof-cache-invalidation", _incremental_run),
            Case("proof-cache-library-identities", _context_hashes_library_bytes, lane="guest")]
