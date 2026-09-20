# SPDX-License-Identifier: Apache-2.0
"""Proof cache invalidation follows bytes and prerequisite closures, not mtimes."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import threading
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
        toolchain = {"pin": gate.env.ROCQ_VERSION, "version": "fixture",
                     "compiler": {"path": "/native/bin/rocq", "sha256": "first"},
                     "checker": {"path": "/native/bin/rocqchk", "sha256": "checker"}}
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
                    kernel: bool = True, kernel_jobs: int = 2) -> None:
                compiled_names.clear()
                audited.clear()
                recheck.reset_mock()
                ensure(gate._run_locked(root, 2, fresh) == result, "unexpected gate verdict")
                ensure(set(compiled_names) == expected,
                       f"compiled {compiled_names}, expected {expected}")
                ensure(recheck.call_count == int(kernel), "wrong kernel recheck reuse decision")
                if result == 0:
                    ensure(set(audited) == expected, "unchanged module was audited again")
                if kernel and result == 0:
                    available = {source.stem for source in gate._sources(root)}
                    ensure(recheck.call_args.args[2] == frozenset(available - expected),
                           "kernel admission differs from the validated reusable objects")
                    ensure(recheck.call_args.kwargs["jobs"] == kernel_jobs,
                           "kernel workers require a bound installed-library context")

            run(set(texts))
            receipt = (work / gate.RECEIPT).read_bytes()
            portable = root / gate.RECEIPT
            exported = json.loads(portable.read_text(encoding="utf-8"))
            ensure(exported["inputs"] == inputs(root, gate._sources(root)),
                   "portable receipt must retain the completed run's input hashes")
            ensure(exported["native_receipt_sha256"] == receipts.digest(work / gate.RECEIPT),
                   "portable receipt lost the full native receipt identity")
            ensure("/native/" not in portable.read_text(encoding="utf-8"),
                   "portable receipt leaked native executable paths")
            portable.unlink()
            run(set(), kernel=False)
            ensure(not audited, "unchanged receipt must avoid repeated native audits")
            ensure((work / gate.RECEIPT).read_bytes() == receipt,
                   "reuse must retain the original completed run's evidence")
            ensure(json.loads(portable.read_text(encoding="utf-8")) == exported,
                   "cached success must restore the portable receipt")
            with patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)):
                ensure(gate._export(root, check=True) == 0, "fresh export must compare equal")
                portable.write_text("{}", encoding="utf-8")
                ensure(gate._export(root, check=True) == 1, "altered export must fail comparison")
                # Export must preserve a completed run after gate inputs change, with no Rocq.
                owner.write_text("changed since the completed run", encoding="utf-8")
                ensure(gate._export(root) == 0, "historical export must not require a recheck")
                ensure(json.loads(portable.read_text(encoding="utf-8")) == exported,
                       "historical export rewrote the recorded inputs")
                ensure((work / gate.RECEIPT).read_bytes() == receipt,
                       "historical export changed the original receipt")
                ensure(gate._status(root) == 1, "historical export must not bless current inputs")
                owner.write_text("gate input", encoding="utf-8")
                product = work / "proofs" / "Base.vo"
                saved = product.read_bytes()
                product.write_bytes(b"tampered")
                ensure(gate._export(root) == 1, "export must reject altered native objects")
                product.write_bytes(saved)
            with patch.object(gate.receipts, "write", side_effect=OSError("export unavailable")):
                try:
                    run(set(), kernel=False)
                except OSError:
                    pass
                else:
                    raise AssertionError("failed publication reported a successful run")
            ensure((work / gate.RECEIPT).read_bytes() == receipt,
                   "failed publication destroyed the native receipt")
            ensure(json.loads(portable.read_text(encoding="utf-8")) == exported,
                   "failed publication destroyed the previous portable receipt")

            # A content change with exactly preserved timestamps still invalidates.
            source = folder / "Base.v"
            stamp = source.stat()
            source.write_text(texts["Base"].replace("0", "1"), encoding="utf-8")
            os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            run({"Base", "Consumer"})
            ensure(set(audited) == {"Base", "Consumer"}, "audits must follow invalidation")

            source = folder / "Consumer.v"
            source.write_text(texts["Consumer"] + "\n(* edited *)", encoding="utf-8")
            run({"Consumer"})
            (work / "proofs" / "Base.vo").write_bytes(b"corrupted object")
            run({"Base", "Consumer"})
            (work / "proofs" / "Consumer.vo").unlink()
            run({"Consumer"})
            context["library_hash"] = "changed-library"
            run(set(texts))
            toolchain["compiler"] = {"path": "/native/bin/rocq", "sha256": "changed-compiler"}
            run(set(texts))
            owner.write_text("changed gate input", encoding="utf-8")
            run(set(texts))
            run(set(texts), fresh=True)

            # Independent additions/removals retain previously checked components.
            (folder / "Added.v").write_text("Definition value := 1.", encoding="utf-8")
            run({"Added"})
            (folder / "Added.v").unlink()
            run(set())
            # Register identity is refreshed without repeating native proof work.
            register = root / "docs" / "requirements-register.md"
            register.parent.mkdir()
            register.write_text("new prose", encoding="utf-8")
            with patch.object(gate, "_inputs", side_effect=lambda base, sources:
                              receipts.snapshot(base, [*sources, owner, register])):
                run(set())
                ensure(gate._validate_receipt(root) is None, "metadata refresh is stale")
            run(set())
            # A changed resolution graph is not reusable even when the source is unchanged.
            (folder / "Consumer.v").write_text("Require Added. Definition value := 0.",
                                               encoding="utf-8")
            run({"Consumer"})
            (folder / "Added.v").write_text("Definition value := 1.", encoding="utf-8")
            run({"Added", "Consumer"})
            (folder / "Added.v").unlink()
            (folder / "Consumer.v").write_text(texts["Consumer"], encoding="utf-8")
            run({"Consumer"})
            # Malformed coverage/audits cannot authorize kernel admissions.
            saved = (work / gate.RECEIPT).read_text(encoding="utf-8")
            for field in ("kernel_evidence", "artifacts"):
                damaged = json.loads(saved)
                damaged[field] = {}
                (work / gate.RECEIPT).write_text(json.dumps(damaged), encoding="utf-8")
                run(set(texts))
            (work / gate.RECEIPT).write_text("{broken", encoding="utf-8")
            run(set(texts))

            # Kernel refusal must leave the earlier portable evidence intact and
            # retain only byte-matching prior successes for the next attempt.
            saved_portable = portable.read_bytes()
            (folder / "Consumer.v").write_text(texts["Consumer"] + "\n(* kernel retry *)",
                                               encoding="utf-8")
            recheck.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="refused")
            run({"Consumer"}, result=1)
            ensure(not (work / gate.RECEIPT).exists(), "kernel failure published success")
            ensure(portable.read_bytes() == saved_portable, "kernel failure rewrote history")
            recheck.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            run({"Consumer"})

            # A failed prerequisite cannot leave a dependent's stale object or receipt.
            failing.add("Base")
            saved_portable = portable.read_bytes()
            (folder / "Base.v").write_text("broken", encoding="utf-8")
            run({"Base"}, result=1, kernel=False)
            ensure(not (work / "proofs" / "Consumer.vo").exists(), "stale consumer survived")
            ensure(not (work / gate.RECEIPT).exists(), "failed run left successful evidence")
            ensure(portable.read_bytes() == saved_portable,
                   "failed run must preserve the last completed run's portable evidence")
            failing.clear()

            def tamper(_root: Path, sources: list[Path],
                       _reused: frozenset[str], *, jobs: int) -> subprocess.CompletedProcess[str]:
                ensure(jobs == 2, "kernel job limit was not forwarded")
                sources[0].with_suffix(".vo").write_bytes(b"changed during kernel check")
                return subprocess.CompletedProcess([], 0, stdout="", stderr="")

            recheck.side_effect = tamper
            run({"Base", "Consumer"}, result=1)
            ensure(not (work / gate.RECEIPT).exists(), "changed kernel input received a receipt")
            recheck.side_effect = None
            run(set(texts))
            # Compiling a changed module cannot overwrite a cached dependency and
            # then ask the kernel to admit its newly captured (unchecked) bytes.
            original_check = check

            def corrupt_cached(base: Path, source: Path, sources: list[Path], *,
                               compiled: bool = False) -> gate.Checked:
                result = original_check(base, source, sources, compiled=compiled)
                (work / "proofs" / "Base.vo").write_bytes(b"unchecked replacement")
                return result

            (folder / "Consumer.v").write_text(texts["Consumer"] + "\n(* changed *)",
                                               encoding="utf-8")
            with patch.object(gate, "_check_source", side_effect=corrupt_cached):
                run({"Consumer"}, result=1, kernel=False)
            with patch.object(gate, "_cache_context", return_value=None):
                run(set(texts), kernel_jobs=1)
                run(set(texts), kernel_jobs=1)


def _kernel_batches_preserve_dependencies() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-kernel-batches-") as temporary:
        folder = Path(temporary)
        texts = {"Cached": "Definition value := 0.",
                 "Base": "Require Cached.", "Left": "Require Base.",
                 "Right": "Require Base.", "Independent": "Require Cached.",
                 "Other": "Definition value := 1."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
            (folder / f"{name}.vo").write_bytes(b"object" * len(name))
        sources = sorted(folder.glob("*.v"))
        reused = frozenset({"Cached"})
        for jobs in (1, 2, 3, 8):
            batches = gate._kernel_batches(sources, reused, jobs)
            groups = [{source.stem for source in batch} for batch in batches]
            flattened = [name for group in groups for name in group]
            ensure(len(batches) == min(jobs, 3) and all(groups),
                   "kernel batches must be nonempty and bounded by independent components")
            ensure(set(flattened) == set(texts) - reused and len(flattened) == len(set(flattened)),
                   "changed roots must be covered exactly once, with no cached targets")
            ensure(any({"Base", "Left", "Right"} <= group for group in groups),
                   "shared changed prerequisites must stay in the same kernel batch")
            ensure(batches == gate._kernel_batches(list(reversed(sources)), reused, jobs),
                   "kernel scheduling must be deterministic for the same source set")


def _parallel_kernel_requires_every_batch_and_joint_pass() -> None:
    """A partial success, noisy worker or changed object can never authorize the join."""
    with tempfile.TemporaryDirectory(prefix="vos-parallel-kernel-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        folder.mkdir()
        texts = {"Cached": "Definition value := 0.", "Base": "Require Cached.",
                 "Consumer": "Require Base.", "Independent": "Require Cached."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        sources = gate._sources(root)
        stems = frozenset(texts)

        def exercise(failure: str) -> None:
            for source in sources:
                source.with_suffix(".vo").write_bytes(b"original object")
            barrier = threading.Barrier(2, timeout=5)
            calls: list[tuple[set[str], frozenset[str]]] = []

            def recheck(base: Path, batch: list[Path],
                        reused: frozenset[str]) -> subprocess.CompletedProcess[str]:
                ensure(base == root, "kernel worker escaped its workspace")
                names = {source.stem for source in batch}
                calls.append((names, reused))
                if reused == stems:
                    ensure(len(calls) == 3 and names == stems,
                           "joint pass must follow every worker and include every root")
                    return subprocess.CompletedProcess([], int(failure == "joint"),
                                                       stdout="", stderr="")
                ensure(reused == frozenset({"Cached"}) and "Cached" in names,
                       "a worker admitted unchecked peers or omitted the reusable closure")
                barrier.wait()
                targeted = "Independent" in names
                if targeted and failure == "tamper":
                    (folder / "Base.vo").write_bytes(b"changed after the other worker read it")
                if targeted and failure == "exception":
                    raise OSError("worker could not start")
                return subprocess.CompletedProcess(
                    [], int(targeted and failure == "exit"),
                    stdout="unexpected output" if targeted and failure == "stdout" else "",
                    stderr="unexpected diagnostic" if targeted and failure == "stderr" else "")

            with patch.object(gate, "_recheck_joint", side_effect=recheck):
                try:
                    result = gate._recheck(root, sources, frozenset({"Cached"}), jobs=2)
                except (OSError, ValueError):
                    ensure(failure in {"tamper", "exception"}, "unexpected kernel exception")
                else:
                    clean = not (result.returncode or result.stdout.strip() or result.stderr.strip())
                    ensure(clean == (failure == "none"), f"kernel lost {failure} verdict")
                    ensure(failure not in {"tamper", "exception"}, "kernel input failure was ignored")
            ensure(len(calls) == (3 if failure in {"none", "joint"} else 2),
                   "a failed batch authorized a final joint pass")
            targets = [name for names, reused in calls[:2] for name in names - reused]
            ensure(set(targets) == stems - {"Cached"} and len(targets) == len(set(targets)),
                   "parallel kernel workers duplicated or omitted a changed root")

        for failure in ("none", "exit", "stdout", "stderr", "tamper", "exception", "joint"):
            exercise(failure)


def _kernel_single_process_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-serial-kernel-") as temporary:
        root = Path(temporary)
        sources = [root / "Base.v", root / "Consumer.v"]
        for source, text in zip(sources, ("Definition value := 0.", "Require Base."), strict=True):
            source.write_text(text, encoding="utf-8")
            source.with_suffix(".vo").write_bytes(b"object")
        answer = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        samples: tuple[tuple[int, frozenset[str]], ...] = (
            (1, frozenset()), (4, frozenset({"Base"})),
            (4, frozenset({"Base", "Consumer"})), (4, frozenset()))
        for jobs, reused in samples:
            with patch.object(gate, "_recheck_joint", return_value=answer) as joint:
                ensure(gate._recheck(root, sources, reused, jobs=jobs) is answer,
                       "serial kernel path lost its verdict")
                joint.assert_called_once_with(root, sources, reused)


def _joint_kernel_keeps_recursive_targets() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-joint-kernel-") as temporary:
        root = Path(temporary)
        sources = [root / "proofs" / f"{name}.v"
                   for name in ("Cached", "Changed", "VerifiedOSProofClosure")]
        answer = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def compile_join(base: Path, source: Path) -> subprocess.CompletedProcess[str]:
            ensure(base == root and source.is_relative_to(root), "join escaped its native lane")
            ensure(source.stem == "VerifiedOSProofClosure_", "join collided with an authored module")
            ensure(source.read_text(encoding="utf-8") == "".join(
                f"Require {item.stem}.\n" for item in sources),
                "joint module must load every root, including disconnected cached ones")
            return answer

        with patch.object(gate.env, "rocqchk_command", return_value=["rocqchk"]), \
                patch.object(gate, "_compile", side_effect=compile_join), \
                patch.object(gate.subprocess, "run", return_value=answer) as run:
            ensure(gate._recheck_joint(root, sources, frozenset({"Cached"})) is answer,
                   "joint kernel verdict was lost")
            command = run.call_args.args[0]
            ensure(command[:5] == ["rocqchk", "-silent", "-Q", "proofs", ""]
                   and command[6:] == ["Changed", "VerifiedOSProofClosure", "-admit", "Cached"],
                   "joint kernel changed explicit targets, admissions or default conversion")
            ensure(Path(command[5]).stem == "VerifiedOSProofClosure_",
                   "joint environment was not an explicit kernel target")


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
                          "Definition RequiresEveryQuantity := 0.\n"
                          "Inductive Phase := PhaseRescanRequired.\n"
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
                            'Time Require Base.', 'Fail Require Base.',
                            'Add ML Path "external".', 'Declare ML Module "external".'):
                source.write_text(command, encoding="utf-8")
                ensure(gate._cache_context(work, [source]) is None,
                       f"dynamic command reused evidence: {command}")


def _native_incremental_kernel() -> None:
    """Exercise real selective checking, including disconnected roots and rejection."""
    lane = gate.workspace(Path(__file__).resolve().parents[2])
    lane.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="incremental-test-", dir=lane) as temporary:
        root = Path(temporary) / "source"
        folder = root / "proofs"
        folder.mkdir(parents=True)
        work = Path(temporary) / "output"
        texts = {"ApexTheorem": "Theorem sound : True. Proof. exact I. Qed.\n",
                 "Base": "Definition value := 0.\n",
                 "Consumer": "Require Base. Theorem same : Base.value = 0. reflexivity. Qed.\n"}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        recheck = gate._recheck
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                patch.object(gate, "_recheck", wraps=recheck) as kernel, \
                contextlib.redirect_stdout(io.StringIO()):
            ensure(gate._run(root, 2) == 0, "fresh native fixture failed")
            for name in ("Consumer", "Base"):
                source = folder / f"{name}.v"
                source.write_text(source.read_text(encoding="utf-8") + "(* edit *)\n",
                                  encoding="utf-8")
                ensure(gate._run(root, 2) == 0, f"selective native check failed for {name}")
                expected = {"ApexTheorem", "Base"} if name == "Consumer" else {"ApexTheorem"}
                ensure(kernel.call_args.args[2] == frozenset(expected),
                       "native gate reused the wrong dependency closure")
            added = folder / "Added.v"
            added.write_text("Require Consumer. Lemma added : True. exact I. Qed.\n",
                             encoding="utf-8")
            ensure(gate._run(root, 2) == 0, "native module addition failed")
            ensure(kernel.call_args.args[2] == frozenset(texts), "addition lost checked roots")
            added.unlink()
            ensure(gate._run(root, 2) == 0, "all-cached joint check after removal failed")
            ensure(kernel.call_args.args[2] == frozenset(texts), "removal lost checked roots")

            original = (folder / "Base.v").read_bytes()
            (folder / "Base.v").write_text("Definition value := 1.\n", encoding="utf-8")
            ensure(gate._run(root, 2) == 1, "changed dependency silently kept its old consumer")
            ensure(gate._status(root) == 1, "failed native run retained current success status")
            (folder / "Base.v").write_bytes(original)
            ensure(gate._run(root, 2) == 0, "native retry after failure did not recover")
            ensure(kernel.call_args.args[2] == frozenset({"ApexTheorem"}),
                   "native retry discarded its unaffected checked module")

            # Even admitted roots must agree in the joint environment. Consumer
            # was compiled against Base.value = 0, and cannot join a different Base.
            base = work / "proofs" / "Base.v"
            base.write_text("Definition value := 1.\n", encoding="utf-8")
            ensure(gate._compile(work, base).returncode == 0, "mismatched fixture did not compile")
            refused = recheck(work, gate._sources(work), frozenset(texts), jobs=2)
            ensure(refused.returncode != 0, "joint check accepted incompatible cached modules")

            # Separately valid libraries can impose contradictory constraints on
            # shared universes. A new root must join the cached roots, even when
            # no source dependency connects the two constrained libraries.
            joint = work / "joint-universes"
            (joint / "proofs").mkdir(parents=True)
            libraries = {"SharedUniverses": "Universe u v.\n",
                         "Left": "Require SharedUniverses.\n"
                                 "Constraint SharedUniverses.u < SharedUniverses.v.\n",
                         "Right": "Require SharedUniverses.\n"
                                  "Constraint SharedUniverses.v < SharedUniverses.u.\n"}
            for name, text in libraries.items():
                path = joint / "proofs" / f"{name}.v"
                path.write_text(text, encoding="utf-8")
                ensure(gate._compile(joint, path).returncode == 0,
                       f"individually valid universe fixture failed: {name}")
            for name in ("Left", "Right"):
                accepted = recheck(joint, [joint / "proofs" / f"{stem}.v"
                                          for stem in ("SharedUniverses", name)])
                ensure(not (accepted.returncode or accepted.stdout.strip() or accepted.stderr.strip()),
                       f"individually valid kernel batch failed: {name}")
            refused = recheck(joint, gate._sources(joint), frozenset({"SharedUniverses", "Left"}))
            ensure(refused.returncode != 0, "incremental join accepted contradictory universes")
            # The two changed roots form separate batches once their shared base
            # is cached. Both can pass alone, but their joint environment cannot.
            refused = recheck(joint, gate._sources(joint), frozenset({"SharedUniverses"}), jobs=2)
            ensure(refused.returncode != 0, "parallel join accepted contradictory universes")


def cases() -> list[Case]:
    return [Case("incremental-proof-cache-invalidation", _incremental_run),
            Case("kernel-batches-preserve-dependencies", _kernel_batches_preserve_dependencies),
            Case("parallel-kernel-requires-all-verdicts",
                 _parallel_kernel_requires_every_batch_and_joint_pass),
            Case("kernel-single-process-paths", _kernel_single_process_paths),
            Case("joint-kernel-recursive-targets", _joint_kernel_keeps_recursive_targets),
            Case("proof-cache-library-identities", _context_hashes_library_bytes, lane="guest"),
            Case("native-incremental-kernel", _native_incremental_kernel, lane="toolchain")]
