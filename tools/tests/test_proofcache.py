# SPDX-License-Identifier: Apache-2.0
"""Proof cache invalidation follows bytes and prerequisite closures, not mtimes.

A run's log gives each module it compiled a span and replays the wave schedule over
those spans beside the phase's wall seconds.
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_proofaudit import KERNEL_CLEAN
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
                patch.object(gate, "_recheck", return_value="") as recheck, \
                contextlib.redirect_stdout(io.StringIO()) as output:

            def run(expected: set[str], *, fresh: bool = False, result: int = 0,
                    kernel: bool = True, kernel_jobs: int = 2, jobs: int | None = 2,
                    refusal: str = "") -> None:
                compiled_names.clear()
                audited.clear()
                recheck.reset_mock()
                said = len(output.getvalue())
                ensure(gate._run_locked(root, jobs, fresh) == result, "unexpected gate verdict")
                reported = [line for line in output.getvalue()[said:].splitlines()
                            if "reuse: no earlier evidence applies" in line]
                ensure(bool(reported) == bool(refusal) and all(refusal in line for line in reported),
                       f"reuse refusal {reported} does not name {refusal!r}")
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

            run(set(texts), refusal="no earlier successful run")
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
            # Each refusal names what differs, never its recorded value.
            context["library_hash"] = "changed-library"
            run(set(texts), refusal="installed-library context differs (library_hash)")
            toolchain["compiler"] = {"path": "/native/bin/rocq", "sha256": "changed-compiler"}
            run(set(texts), refusal="toolchain differs (compiler: sha256)")
            owner.write_text("changed gate input", encoding="utf-8")
            run(set(texts), refusal="proof-gate implementation differs (gate-input.txt)")
            ensure("changed-compiler" not in output.getvalue(), "a refusal printed a recorded value")
            run(set(texts), fresh=True, refusal="--fresh was requested")

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
                run(set(texts), refusal="the earlier receipt cannot authorize reuse")
            (work / gate.RECEIPT).write_text("{broken", encoding="utf-8")
            run(set(texts), refusal="the earlier receipt is unreadable")

            # Kernel refusal must leave the earlier portable evidence intact and
            # retain only byte-matching prior successes for the next attempt.
            saved_portable = portable.read_bytes()
            (folder / "Consumer.v").write_text(texts["Consumer"] + "\n(* kernel retry *)",
                                               encoding="utf-8")
            recheck.return_value = "refused"
            run({"Consumer"}, result=1)
            ensure(not (work / gate.RECEIPT).exists(), "kernel failure published success")
            ensure(portable.read_bytes() == saved_portable, "kernel failure rewrote history")
            recheck.return_value = ""
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
                       _reused: frozenset[str], *, jobs: int) -> str:
                ensure(jobs == 2, "kernel job limit was not forwarded")
                sources[0].with_suffix(".vo").write_bytes(b"changed during kernel check")
                return ""

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
            with patch.object(gate.env, "proof_jobs", side_effect=[8, 3]) as sizing:
                run(set(texts), fresh=True, jobs=None, kernel_jobs=3, refusal="--fresh")
                ensure([call.kwargs for call in sizing.call_args_list] == [{}, {"kernel": True}],
                       "automatic sizing must sample compilation and kernel phases separately")
            with patch.object(gate.env, "proof_jobs", side_effect=AssertionError("unexpected probe")):
                run(set(), jobs=None, kernel=False)
                run(set(texts), fresh=True, refusal="--fresh")
            unbound = "this installed-library context cannot authorize reuse"
            with patch.object(gate, "_cache_context", return_value=None):
                run(set(texts), kernel_jobs=1, refusal=unbound)
                with patch.object(gate.env, "proof_jobs", return_value=8) as sizing:
                    run(set(texts), jobs=None, kernel_jobs=1, refusal=unbound)
                    sizing.assert_called_once_with()


_SPAN_LINE = re.compile(r"^  compile/audit (\S+\.v): (\d+\.\d\d)s to (\d+\.\d\d)s$")
_PHASE_LINE = re.compile(r"^  compile/audit: (\d+\.\d\d)s; wave schedule replayed over these "
                         r"modules' seconds at worker limit (\d+): (\d+\.\d\d)s; ")


def _the_phase_line_replays_the_wave_schedule() -> None:
    """Each compiled module logs its span, a reused one none, and the phase's line gives
    the replay `wave_makespan` computes over exactly those spans at the run's limit."""
    with tempfile.TemporaryDirectory(prefix="vos-proof-replay-") as temporary:
        root = Path(temporary) / "source"
        folder = root / "proofs"
        folder.mkdir(parents=True)
        work = Path(temporary) / "output"
        work.mkdir()
        texts = {"ApexTheorem": "Require Consumer.", "Base": "Definition value := 0.",
                 "Consumer": "Require Base.", "Side": "Definition value := 1."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        toolchain = {"pin": gate.env.ROCQ_VERSION, "version": "fixture",
                     "compiler": {"path": "/native/bin/rocq", "sha256": "compiler"},
                     "checker": {"path": "/native/bin/rocqchk", "sha256": "checker"}}

        def check(_root: Path, source: Path, _sources: object) -> gate.Checked:
            source.with_suffix(".vo").write_bytes(source.read_bytes())
            return gate.Checked(source, symbols=[{
                "name": f"{source.stem}.sound", "type": "True", "claims": [], "assumptions": []}])

        waves = [[source.stem for source in wave]
                 for wave in gate.proofs_mod.SourceIndex.read(gate._sources(root)).ordered]
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                patch.object(gate, "_toolchain", return_value=toolchain), \
                patch.object(gate, "_cache_context", return_value={"library_hash": "fixed"}), \
                patch.object(gate, "_check_source", side_effect=check), \
                patch.object(gate, "_recheck", return_value=""):
            for jobs, edited, compiled in ((2, "", set(texts)),
                                           (3, "Consumer", {"Consumer", "ApexTheorem"})):
                if edited:
                    source = folder / f"{edited}.v"
                    source.write_text(texts[edited] + "\n(* edited *)", encoding="utf-8")
                with patch.object(gate, "wave_makespan", wraps=gate.wave_makespan) as replay, \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    ensure(gate._run_locked(root, jobs) == 0, "the replay fixture failed")
                lines = output.getvalue().splitlines()
                spans = {match.group(1): (float(match.group(2)), float(match.group(3)))
                         for match in map(_SPAN_LINE.match, lines) if match}
                ensure(set(spans) == {f"{stem}.v" for stem in compiled},
                       f"timing lines {sorted(spans)} do not name exactly the compiled modules")
                ensure(all(0 <= start <= end for start, end in spans.values()),
                       f"a span does not run forward from the phase's start: {spans}")
                phase = [match for match in map(_PHASE_LINE.match, lines) if match]
                ensure(len(phase) == 1 and int(phase[0].group(2)) == jobs,
                       f"no phase line names the replay at worker limit {jobs}: {lines}")
                replay.assert_called_once()
                durations, limit = replay.call_args.args
                ensure(limit == jobs and [len(wave) for wave in durations]
                       == [len(wave) for wave in waves],
                       "the replay is not over the gate's waves at the run's worker limit")
                for wave, measured in zip(waves, durations, strict=True):
                    for stem, seconds in zip(wave, measured, strict=True):
                        logged = spans.get(f"{stem}.v")
                        ensure(logged is None or abs(logged[1] - logged[0] - seconds) <= 0.011,
                               f"the replay's {seconds}s for {stem} is not its logged span")
                expected = gate.wave_makespan(durations, limit)
                ensure(phase[0].group(3) == f"{expected:.2f}",
                       f"the phase line's replay {phase[0].group(3)} is not {expected:.2f}")


def _gate_identity_follows_imports() -> None:
    """The implementation identity is the gate's import closure, not a kept list."""
    checkout = Path(__file__).resolve().parents[2]
    live = {path.relative_to(checkout).as_posix() for path in gate._gate_modules(checkout)}
    for required in ("tools/vos/cli/proofs.py", "tools/vos/proofaudit.py",
                     "tools/vos/receipts.py", "tools/vos/cli/__init__.py",
                     "tools/vos/__init__.py", "tools/vos/proofheaders.py"):
        ensure(required in live, f"the gate's identity omits {required}")
    for launcher in ("tools/run.py", "tools/vos/commands.py", "tools/vos/toolenv.py"):
        ensure(launcher not in live, f"{launcher} chooses the process and must not invalidate proofs")

    with tempfile.TemporaryDirectory(prefix="vos-gate-identity-") as temporary:
        root = Path(temporary)
        files = {
            "vos/__init__.py": "",
            "vos/cli/__init__.py": "",
            "vos/cli/proofs.py": "from vos import helper\nimport vos.deep.leaf\n\n"
                                 "def later():\n    from .sibling import value\n"
                                 "    from ..nested import inner\n",
            "vos/helper.py": "import json\n",
            "vos/cli/sibling.py": "value = 1\n",
            "vos/deep/__init__.py": "",
            "vos/deep/leaf.py": "",
            "vos/nested/__init__.py": "from . import inner\n",
            "vos/nested/inner.py": "",
            "vos/unused.py": "",
            "vos/commands.py": "from vos.cli import proofs\n",
        }
        for name, text in files.items():
            path = root / "tools" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        found = {path.relative_to(root / "tools").as_posix() for path in gate._gate_modules(root)}
        ensure(found == set(files) - {"vos/unused.py", "vos/commands.py"},
               f"derived gate modules differ: {sorted(found)}")
        register = root / "docs" / "requirements-register.md"
        register.parent.mkdir()
        register.write_text("register", encoding="utf-8")
        before = gate._inputs(root, [])
        (root / "tools" / "vos" / "unused.py").write_text("changed = True\n", encoding="utf-8")
        (root / "tools" / "vos" / "commands.py").write_text("rows = ()\n", encoding="utf-8")
        ensure(gate._inputs(root, []) == before, "an unimported module changed the gate identity")
        (root / "tools" / "vos" / "helper.py").write_text("from vos import unused\n",
                                                          encoding="utf-8")
        after = gate._inputs(root, [])
        ensure(after != before and "tools/vos/unused.py" in after,
               "a newly imported module did not join the gate identity")
        (root / "tools" / "vos" / "cli" / "proofs.py").unlink()
        try:
            gate._gate_modules(root)
        except ValueError:
            pass
        else:
            raise AssertionError("a checkout without the gate module derived an identity")


def _identity_binds_what_reuse_compares() -> None:
    """A cache keyed by the identity offers only candidates whose context the gate accepts."""
    with tempfile.TemporaryDirectory(prefix="vos-proof-identity-") as temporary:
        root = Path(temporary)
        context: dict[str, object] = {"files": {"/lib/Base.vo": "first"}}
        toolchain: dict[str, object] = {"pin": gate.env.ROCQ_VERSION, "compiler": {"sha256": "first"}}

        def identity(value: dict[str, object] | None) -> tuple[int, str, str]:
            with patch.object(gate, "workspace", return_value=root / "work"), \
                    patch.object(gate, "_sources", return_value=[]), \
                    patch.object(gate, "_cache_context", return_value=value), \
                    patch.object(gate, "_toolchain", return_value=toolchain), \
                    contextlib.redirect_stdout(io.StringIO()) as printed, \
                    contextlib.redirect_stderr(io.StringIO()) as said:
                code = gate._identity(root)
            return code, printed.getvalue(), said.getvalue()

        code, digest, _ = identity(context)
        ensure(code == 0 and digest == gate._json_digest(
            {"toolchain": toolchain, "cache_context": context}) + "\n",
            "the identity must digest exactly the toolchain and context reuse compares")
        ensure(identity(dict(context))[1] == digest, "equal contexts must share one identity")
        ensure(identity({"files": {"/lib/Base.vo": "second"}})[1] != digest,
               "changed library bytes must change the identity")
        code, digest, said = identity(None)
        ensure(code == 1 and not digest and "FAIL" in said,
               "an unsupported context must fail without printing a key")


def _jobs_cli_defaults_to_auto_without_probing_metadata_commands() -> None:
    root = Path(__file__).resolve().parents[2]
    with patch.object(gate, "find_root", return_value=root), \
            patch.object(gate, "_run", return_value=0) as run, \
            patch.object(gate, "_status", return_value=0) as status, \
            patch.object(gate, "_export", return_value=0) as export, \
            patch.object(gate, "_identity", return_value=0) as identity, \
            patch.object(gate.env, "proof_jobs", side_effect=AssertionError("premature probe")):
        ensure(gate.main([]) == 0, "automatic proof invocation failed")
        run.assert_called_once_with(root, None, False)
        run.reset_mock()
        ensure(gate.main(["--jobs", "7"]) == 0, "explicit proof invocation failed")
        run.assert_called_once_with(root, 7, False)
        run.reset_mock()
        ensure(gate.main(["status"]) == 0, "proof status failed")
        status.assert_called_once_with(root)
        ensure(gate.main(["export"]) == 0, "proof export failed")
        export.assert_called_once_with(root, check=False)
        ensure(gate.main(["identity"]) == 0, "proof identity failed")
        identity.assert_called_once_with(root)
        for args, code in ((["--help"], 0), (["--jobs", "0"], 2), (["--jobs", "-1"], 2)):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    gate.main(args)
                except SystemExit as err:
                    ensure(err.code == code, "wrong proof option exit")
                else:
                    raise AssertionError("help or an invalid job count must exit during parsing")
        ensure(not run.called, "metadata/help/invalid options started proof work")


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


def _parallel_kernel_combines_joint_work_and_waits_for_peers() -> None:
    """The joint worker finishing first cannot accept a failed or still-pending peer."""
    with tempfile.TemporaryDirectory(prefix="vos-parallel-kernel-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        folder.mkdir()
        texts = {"Cached": "Definition value := 0.", "Base": "Require Cached.",
                 "Consumer": "Require Base.", "Independent": "Definition value := 1."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        sources = gate._sources(root)
        stems = frozenset(texts)

        def exercise(failure: str, reused: frozenset[str]) -> None:
            for source in sources:
                source.with_suffix(".vo").write_bytes(b"original object")
            barrier = threading.Barrier(2, timeout=5)
            joint_finished = threading.Event()
            calls: list[tuple[set[str], frozenset[str]]] = []

            def recheck(base: Path, batch: list[Path],
                        admitted: frozenset[str]) -> subprocess.CompletedProcess[str]:
                ensure(base == root, "kernel worker escaped its workspace")
                names = {source.stem for source in batch}
                calls.append((names, admitted))
                ensure(len(calls) <= 2, "kernel launched a separate final consistency pass")
                joint = names == stems
                if joint:
                    ensure(admitted == stems - {"Independent"},
                           "the smallest batch must keep its own roots as explicit targets")
                else:
                    ensure(admitted == reused and names == stems - {"Independent"},
                           "a peer admitted unchecked work or omitted its reusable closure")
                barrier.wait()
                if joint:
                    joint_finished.set()
                    return subprocess.CompletedProcess([], int(failure == "joint"),
                                                       stdout="", stderr=KERNEL_CLEAN)
                ensure(joint_finished.wait(timeout=5), "peer never observed joint worker completion")
                if failure == "tamper":
                    (folder / "Base.vo").write_bytes(b"changed after the other worker read it")
                if failure == "exception":
                    raise OSError("worker could not start")
                return subprocess.CompletedProcess(
                    [], int(failure == "exit"),
                    stdout="unexpected output" if failure == "stdout" else "",
                    stderr=KERNEL_CLEAN + ("unexpected diagnostic" if failure == "stderr" else ""))

            with patch.object(gate, "_recheck_joint", side_effect=recheck):
                try:
                    fault = gate._recheck(root, sources, reused, jobs=2)
                except (OSError, ValueError):
                    ensure(failure in {"tamper", "exception"}, "unexpected kernel exception")
                else:
                    ensure(bool(fault) == (failure != "none"), f"kernel lost {failure} verdict")
                    ensure(failure not in {"tamper", "exception"}, "kernel input failure was ignored")
            ensure(len(calls) == 2 and sum(names == stems for names, _ in calls) == 1,
                   "exactly one of the two workers must check the complete joint environment")
            targets = [name for names, admitted in calls for name in names - admitted]
            ensure(set(targets) == stems - reused and len(targets) == len(set(targets)),
                   "parallel kernel workers duplicated or omitted a changed root")

        for failure in ("none", "exit", "stdout", "stderr", "tamper", "exception", "joint"):
            exercise(failure, frozenset())
            exercise(failure, frozenset({"Cached"}))


def _kernel_batches_cannot_omit_provisionally_admitted_work() -> None:
    root = Path("unused-workspace")
    sources = [root / f"{name}.v" for name in ("Cached", "First", "Second", "Third")]
    cached, first, second, third = sources
    invalid = ([[first], [second]], [[first, second], [second, third]],
               [[first, second, third], [cached]], [[first, second, third], []],
               [[first, second], [root / "Foreign.v"]])
    for batches in invalid:
        with patch.object(gate, "_kernel_batches", return_value=batches), \
                patch.object(gate, "_recheck_joint") as worker:
            try:
                gate._recheck(root, sources, frozenset({"Cached"}), jobs=2)
            except ValueError as err:
                ensure("exactly once" in str(err), "wrong malformed-batch refusal")
            else:
                raise AssertionError("malformed coverage authorized provisional admissions")
            ensure(not worker.called, "kernel worker started before coverage was established")


def _kernel_single_process_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-serial-kernel-") as temporary:
        root = Path(temporary)
        sources = [root / "Base.v", root / "Consumer.v"]
        for source, text in zip(sources, ("Definition value := 0.", "Require Base."), strict=True):
            source.write_text(text, encoding="utf-8")
            source.with_suffix(".vo").write_bytes(b"object")
        samples: tuple[tuple[int, frozenset[str]], ...] = (
            (1, frozenset[str]()), (4, frozenset({"Base"})),
            (4, frozenset({"Base", "Consumer"})), (4, frozenset[str]()))
        for jobs, reused in samples:
            for stderr, accepted in ((KERNEL_CLEAN, True), ("", False)):
                answer = subprocess.CompletedProcess([], 0, stdout="", stderr=stderr)
                with patch.object(gate, "_recheck_joint", return_value=answer) as joint:
                    ensure(bool(gate._recheck(root, sources, reused, jobs=jobs)) != accepted,
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
            ensure(command[:6] == ["rocqchk", "-silent", "-o", "-Q", "proofs", ""]
                   and command[7:] == ["Changed", "VerifiedOSProofClosure", "-admit", "Cached"],
                   "joint kernel changed explicit targets, admissions, default conversion "
                   "or its context summary")
            ensure(Path(command[6]).stem == "VerifiedOSProofClosure_",
                   "joint environment was not an explicit kernel target")


def _admission_covers_only_the_installed_names_it_repeats() -> None:
    """A load-only pass over admitted roots covers installed names, never a proof's own."""
    sealed = "Stdlib.Arith.PeanoNat.Nat.PrivateImplementsBitwiseSpec.testbit_odd_0"
    loaded = "Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep"

    def summary(*axioms: str) -> str:
        listed = "".join(f"    {axiom}\n" for axiom in axioms)
        return KERNEL_CLEAN.replace("* Axioms: <none>\n", f"* Axioms:\n{listed}") if axioms \
            else KERNEL_CLEAN

    with tempfile.TemporaryDirectory(prefix="vos-kernel-admission-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        folder.mkdir()
        texts = {"Cached": "Definition value := 0.", "Left": "Require Cached.",
                 "Middle": "Require Cached.", "Right": "Definition value := 1."}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
            (folder / f"{name}.vo").write_bytes(b"object" * len(name))
        sources = gate._sources(root)
        stems = frozenset(texts)
        reused = frozenset({"Cached"})
        # Each worker's axioms, the load-only pass's (None when that pass fails) and the
        # text a refusal must carry. `sealed` is never refused while that pass names it.
        samples: tuple[tuple[tuple[str, ...], tuple[str, ...] | None, str], ...] = (
            ((sealed,), (sealed,), ""),
            ((sealed, loaded), (sealed,), loaded),
            ((sealed, "Cached.a"), (sealed, "Cached.a"), "Cached.a"),
            ((sealed,), None, "own context summary failed"),
            ((), (sealed,), ""))
        for worker, alone, refusal in samples:
            for jobs in (1, 3):
                passes: list[frozenset[str]] = []

                def recheck(_base: Path, members: list[Path], admitted: frozenset[str],
                            worker: tuple[str, ...] = worker, alone: tuple[str, ...] | None = alone,
                            passes: list[frozenset[str]] = passes) -> subprocess.CompletedProcess[str]:
                    if {member.stem for member in members} != admitted:
                        return subprocess.CompletedProcess([], 0, stdout="", stderr=summary(*worker))
                    passes.append(admitted)
                    return subprocess.CompletedProcess(
                        [], int(alone is None), stdout="",
                        stderr="Error: unreadable" if alone is None else summary(*alone))

                with patch.object(gate, "_recheck_joint", side_effect=recheck), \
                        contextlib.redirect_stdout(io.StringIO()) as said:
                    fault = gate._recheck(root, sources, reused, jobs=jobs)
                ensure(bool(fault) == bool(refusal) and refusal in fault,
                       f"wrong admission verdict for {worker} with {jobs} job(s): {fault!r}")
                ensure(sealed not in fault, "a name the admitted roots repeat was refused")
                ensure((sealed.rsplit(".", 1)[0] in said.getvalue()) == (bool(worker) and not fault),
                       "an accepted run must report exactly the names its admissions covered")
                # Only a worker naming an installed axiom pays for a load-only pass, and
                # workers admitting the same roots share it.
                expected = ([] if not worker else [reused] if jobs == 1
                            else [reused, stems - {"Left"}])
                ensure(sorted(passes, key=sorted) == sorted(expected, key=sorted),
                       f"load-only passes {passes} differ from {expected}")
        # With nothing admitted the worker checked every library it names.
        with patch.object(gate, "_recheck_joint", side_effect=lambda *_: subprocess.CompletedProcess(
                [], 0, stdout="", stderr=summary(sealed))) as run:
            ensure(sealed in gate._recheck(root, sources, frozenset(), jobs=1),
                   "an axiom of a checked installed library was covered")
            ensure(run.call_count == 1, "a worker that admitted nothing ran a load-only pass")


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
        plugin = runtime / "plugin.cmxs"
        plugin.write_bytes(b"plugin")
        system = work / "libc.so.6"
        system.write_bytes(b"c library")
        # Print LoadPath uses absolute POSIX paths in the guest.
        physical = library.as_posix()
        listing = f"Installed / Logical Path / Physical path:\ni Corelib\n  {physical}\n"
        config = f"COQLIB={library}\nCOQCORELIB={runtime}\n"
        loaded = ("/native/bin/rocq:\n\tlinux-vdso.so.1 (0x0000f8674390e000)\n"
                  f"\tlibc.so.6 => {system.as_posix()} (0x0000f867430e0000)\n"
                  f"{plugin.as_posix()}:\n\tstatically linked\n")
        # What `ldd` answers next, and every object list it was asked about.
        linked: dict[str, tuple[int, str]] = {"answer": (0, loaded)}
        objects: list[list[str]] = []

        def invoke(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[0] == "ldd":
                objects.append(command[1:])
                code, stdout = linked["answer"]
                return subprocess.CompletedProcess(command, code, stdout=stdout, stderr="")
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
            ensure(objects[-1] == ["rocq", "rocqchk", str(plugin.resolve())],
                   "shared-library discovery must cover both executables and every plugin")
            ensure(before is not None
                   and before["shared_libraries"] == {system.as_posix(): receipts.digest(system)},
                   "the loaded C library was not bound by its bytes")
            with patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/new_interop",
                                         "SHLVL": "9", "_": "different-launcher"}):
                ensure(before == gate._cache_context(work, [source]),
                       "launch bookkeeping must not defeat reuse across WSL invocations")
            with patch.dict(os.environ, {"ROCQPATH": "/different/library"}):
                changed = gate._cache_context(work, [source])
                ensure(before != changed,
                       "library environment changes must invalidate cached evidence")
                ensure(before is not None and changed is not None
                       and gate._changed(before, changed) == "environment: ROCQPATH",
                       "a refusal must name the changed variable")
            system.write_bytes(b"patched c library")
            changed = gate._cache_context(work, [source])
            ensure(before is not None and changed is not None
                   and gate._changed(before, changed) == f"shared_libraries: {system.as_posix()}",
                   "a changed system library escaped identity")
            system.write_bytes(b"c library")
            for answer in ((0, loaded + "\tlibgmp.so.10 => not found\n"), (1, loaded)):
                linked["answer"] = answer
                ensure(gate._cache_context(work, [source]) is None,
                       f"unresolved shared libraries authorized reuse: {answer}")
            linked["answer"] = (0, loaded)
            stamp = artifact.stat()
            artifact.write_bytes(b"other")
            os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            ensure(before != gate._cache_context(work, [source]), "library bytes escaped identity")
            for command in ('Load "external.v".', 'Time Load "external.v".',
                            'Time Require Base.', 'Fail Require Base.',
                            'Add ML Path "external".', 'Declare ML Module "external".',
                            'Instructions Load "external.v".',
                            'Profile "p" Declare ML Module "external".'):
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
                 "Consumer": ("Require Base. Theorem same : Base.value = 0. "
                              "Proof. reflexivity. Qed.\n")}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        recheck = gate._recheck
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                patch.object(gate, "_recheck", wraps=recheck) as kernel, \
                contextlib.redirect_stdout(io.StringIO()):
            with patch.object(gate, "_recheck_joint", wraps=gate._recheck_joint) as workers:
                ensure(gate._run(root, 2) == 0, "fresh native fixture failed")
                ensure(workers.call_count == 2,
                       "native parallel check added a separate final consistency pass")
                ensure(sum({source.stem for source in call.args[1]} == set(texts)
                           for call in workers.call_args_list) == 1,
                       "one native worker must include the full joint environment")
            for name in ("Consumer", "Base"):
                source = folder / f"{name}.v"
                source.write_text(source.read_text(encoding="utf-8") + "(* edit *)\n",
                                  encoding="utf-8")
                ensure(gate._run(root, 2) == 0, f"selective native check failed for {name}")
                expected = {"ApexTheorem", "Base"} if name == "Consumer" else {"ApexTheorem"}
                ensure(kernel.call_args.args[2] == frozenset(expected),
                       "native gate reused the wrong dependency closure")
            added = folder / "Added.v"
            added.write_text("Require Consumer. Lemma added : True. Proof. exact I. Qed.\n",
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
            ensure(bool(recheck(work, gate._sources(work), frozenset(texts), jobs=2)),
                   "joint check accepted incompatible cached modules")

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
                fault = recheck(joint, [joint / "proofs" / f"{stem}.v"
                                       for stem in ("SharedUniverses", name)])
                ensure(not fault, f"individually valid kernel batch failed: {name}: {fault}")
            ensure(bool(recheck(joint, gate._sources(joint), frozenset({"SharedUniverses", "Left"}))),
                   "incremental join accepted contradictory universes")
            # The two changed roots form separate batches once their shared base
            # is cached. Both can pass alone, but their joint environment cannot.
            ensure(bool(recheck(joint, gate._sources(joint), frozenset({"SharedUniverses"}), jobs=2)),
                   "parallel join accepted contradictory universes")


def _native_admitted_installed_axioms() -> None:
    """A root that loads a sealed installed module can be admitted without refusal.

    Corelib's ssrunder seals Under_rel, whose fields rocqchk names as axioms wherever
    the library is admitted rather than checked. An installed library's axiom in a
    library the worker checks is refused beside them.
    """
    lane = gate.workspace(Path(__file__).resolve().parents[2])
    lane.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="admission-test-", dir=lane) as temporary:
        root = Path(temporary) / "source"
        folder = root / "proofs"
        folder.mkdir(parents=True)
        work = Path(temporary) / "output"
        apex = "Theorem sound : True. Proof. exact I. Qed.\n"
        texts = {"ApexTheorem": apex,
                 "Base": "Require Corelib.ssr.ssrunder.\nDefinition value := 0.\n",
                 "Consumer": ("Require Base.\n"
                              "Theorem same : Base.value = 0. Proof. reflexivity. Qed.\n")}
        for name, text in texts.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
        sealed = "Corelib.ssr.ssrunder.Under_rel"
        steps = ((apex, 0, ""),
                 (apex + "(* edit *)\n", 0, sealed),
                 ("From Stdlib Require Import FunctionalExtensionality.\n" + apex, 1,
                  "functional_extensionality_dep"))
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                patch.object(gate, "_recheck", wraps=gate._recheck) as kernel:
            for text, verdict, said in steps:
                (folder / "ApexTheorem.v").write_text(text, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    ensure(gate._run(root, 2) == verdict,
                           f"wrong verdict {verdict} expected: {output.getvalue()}")
                ensure(said in output.getvalue(), f"run did not report {said!r}: {output.getvalue()}")
                if verdict:
                    ensure(f"{sealed}." not in output.getvalue().split("FAIL", 1)[1],
                           "an admitted sealed module's field was refused")
                elif said:
                    ensure(kernel.call_args.args[2] == frozenset({"Base", "Consumer"}),
                           "the edit did not admit the root that loads the sealed module")


def _hold_while_retired(td: Path, recreated: bool) -> None:
    if sys.platform == "win32":
        raise AssertionError("flock is POSIX-only; the workspace lock cases run in the guest")
    import fcntl
    take = fcntl.flock
    work, aside = td / "proof-gate", td / "retained"
    taken: list[int] = []

    def retire_while_blocked(fd: int, operation: int) -> None:
        take(fd, operation)
        taken.append(os.fstat(fd).st_ino)
        if len(taken) == 1:
            work.rename(aside)
            if recreated:
                work.mkdir()

    with patch.object(fcntl, "flock", side_effect=retire_while_blocked):
        fd = gate._hold(work)
    try:
        ensure(len(taken) == 2 and os.fstat(fd).st_ino == work.stat().st_ino
               and os.fstat(fd).st_ino != aside.stat().st_ino,
               f"recreated={recreated}: the gate holds the moved directory, "
               f"locks taken on {taken}")
    finally:
        os.close(fd)


def _the_lock_follows_a_moved_workspace() -> None:
    """A gate blocked on the workspace's lock while retirement moves the directory aside
    holds, once the lock is released, the directory the workspace's path then names:
    a new one where the path is gone, or one another gate recreated there."""
    for recreated in (False, True):
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            _hold_while_retired(Path(td), recreated)


def cases() -> list[Case]:
    return [Case("incremental-proof-cache-invalidation", _incremental_run),
            Case("phase-line-replays-the-wave-schedule", _the_phase_line_replays_the_wave_schedule),
            Case("gate-identity-follows-imports", _gate_identity_follows_imports),
            Case("proof-identity-binds-reuse-context", _identity_binds_what_reuse_compares),
            Case("proof-jobs-cli-defaults-to-auto",
                 _jobs_cli_defaults_to_auto_without_probing_metadata_commands),
            Case("kernel-batches-preserve-dependencies", _kernel_batches_preserve_dependencies),
            Case("parallel-kernel-combines-joint-work",
                 _parallel_kernel_combines_joint_work_and_waits_for_peers),
            Case("kernel-batches-require-complete-coverage",
                 _kernel_batches_cannot_omit_provisionally_admitted_work),
            Case("kernel-single-process-paths", _kernel_single_process_paths),
            Case("joint-kernel-recursive-targets", _joint_kernel_keeps_recursive_targets),
            Case("kernel-admission-covers-installed-names",
                 _admission_covers_only_the_installed_names_it_repeats),
            Case("proof-cache-library-identities", _context_hashes_library_bytes, lane="guest"),
            Case("proof-workspace-lock-follows-a-move", _the_lock_follows_a_moved_workspace,
                 lane="guest"),
            Case("native-incremental-kernel", _native_incremental_kernel, lane="toolchain"),
            Case("native-admitted-installed-axioms", _native_admitted_installed_axioms,
                 lane="toolchain")]
