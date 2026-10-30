# SPDX-License-Identifier: Apache-2.0
"""Joined wire chronology and checked production-manifest consumption."""

import io
import json
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Self, override
from unittest.mock import patch

from tests import compiler_fixture
from tests.harness import TOOLS, Case, ensure
from vos import boot, scalar_join, supervisor


def wire_publication_order() -> None:
    def read(lines: list[str]) -> scalar_join.WireTrace:
        return scalar_join.wire_trace(lines, request=0x1000, acknowledgment=0x2000,
                                      request_words=2, acknowledgment_words=2,
                                      supervisor_entry=0x8000, supervisor_top=0x9000)

    ensure(read([]) == scalar_join.WireTrace((), (), ()), "empty trace created a lifecycle event")
    request = ["I 1 0000000000008000 00000013\n", "W 1008 8 0 2\n", "W 1000 8 0 1\n"]
    early = [*request, "W 2008 1 0 5\n", "W 2000 8 0 1\n", "R 2000 8 0 1\n"]
    parsed = read(early)
    ensure(parsed.requests[0].words == (1, 2), "request cells lost their publication order")
    ensure(parsed.acknowledgments[0].words == (1, 5), "ack byte writes were not reconstructed")
    ensure(not parsed.later_reads, "same-reaction read passed as later acknowledgment consumption")
    later = read([*early, "I 2 0000000000008000 00000013\n", "R 2000 8 0 1\n",
                  "W 2000 8 0 1\n"])
    ensure(later.later_reads == (1,) and len(later.acknowledgments) == 1,
           "refreshing an acknowledgment invented a second effect result")
    kernel_read = read([*early, "I 2 0000000000008000 00000013\n",
                        "I 3 000000000000A000 00000013\n", "R 2000 8 0 1\n"])
    ensure(not kernel_read.later_reads, "a kernel read passed as supervisor acknowledgment consumption")


def fixed_table() -> None:
    ensure(scalar_join.table_rows(100, 20, 40, 4) == [
        ("copy", 120, 160), ("supervisor", 180, 200180),
        ("copy", 200200, 200240), ("supervisor", 200260, 400260)],
        "fixed rows changed width, role or common boundary charge")


def manifest_trace_bytes() -> None:
    expected = b"\x01\x00\x00\x00\x02\x03\x00\x00"
    observed = scalar_join.ManifestTrace(0x100, expected)
    observed.write(0x100, 4, 0, 1)
    observed.write(0x104, 2, 0, 0x302)
    observed.entry()
    ensure(not observed.accepted(), "unobserved zero initialization counted as exact target bytes")
    observed.write(0x106, 2, 0, 0)
    observed.entry()
    ensure(not observed.accepted(), "later repair hid wrong bytes at the first supervisor entry")
    complete = scalar_join.ManifestTrace(0x100, expected)
    complete.write(0xFE, 8, 0, int.from_bytes(b"xx" + expected[:6], "little"))
    complete.write(0x106, 2, 0, 0)
    complete.entry()
    ensure(complete.accepted(), "complete exact overlapping byte writes were refused")
    complete.write(0x104, 1, 0, 9)
    ensure(not complete.accepted(), "post-entry kernel byte substitution escaped the manifest account")
    tagged = scalar_join.ManifestTrace(0x100, expected)
    tagged.write(0x100, 8, 1, int.from_bytes(expected, "little"))
    tagged.entry()
    ensure(not tagged.accepted(), "tagged manifest data passed the scalar-layout account")


def manifest_permission_observer() -> None:
    """Independent serialized traces must satisfy the joined control's oracle."""
    symbols = {name: 0x30000 + index * 8 for index, name in enumerate((
        "supervisor_stack", "supervisor_manifest", "acknowledgment", "request",
        "saved_clear", "restore_context", "lifecycle_timer_entry",
        "lifecycle_trap_save_begin", "lifecycle_trap_save_end", "lifecycle_trap_scrub_end",
        "scalar_join_copy_entry", "scalar_join_copy_idle", "vos_restore_dispatch",
        "scalar_join_restore_image_dispatch", "k_vos_kernel_lifecycle_prepare",
        "scalar_join_clear_begin", "scalar_join_clear_end", "k_vos_kernel_lifecycle_retire_finish",
        "scalar_join_copy_base", "lifecycle_old_root_tag", "lifecycle_fresh_root_tag",
        "lifecycle_padding_sample", "scalar_join_padding_sample", "kernel_private",
        "service_state", "lifecycle_owned_span", "lifecycle_ack_publish"))}
    symbols.update(supervisor_text_base=0x10000, supervisor_entry=0x10000,
                   supervisor_text_end=0x20000, supervisor_permission_control=0x10100)
    manifest = b"\x03\x00\x00\x00\x01\x00\x00\x00"
    checks: list[tuple[int, int]] = []
    for reg, name, extent, perm in ((20, "supervisor_text_base", 65536, 0x1CB),
            (2, "supervisor_stack", scalar_join.lifecycle_target.STACK, 0xFE),
            (10, "supervisor_manifest", 512, 3), (11, "acknowledgment", 256, 3),
            (12, "request", 512, 7)):
        for suffix, expected in (("tag", 1), ("base", symbols[name]),
                                 ("length", extent), ("permissions", perm)):
            label = f"supervisor_cap_{reg}_{suffix}"
            symbols[label] = 0x11000 + len(checks) * 4
            checks.append((symbols[label], expected))

    def observed(payload: bytes, *, successful_write: bool = False,
                 fault_pc: int = 0x10100) -> dict[str, object]:
        lines = ["I 1 0000000000009000 00000013\n",
                 f"W {symbols['supervisor_manifest']:X} 8 0 {int.from_bytes(payload, 'little'):X}\n",
                 "I 2 0000000000010000 00000013\n"]
        for index, (pc, expected) in enumerate(checks, 3):
            lines += [f"I {index} {pc:016X} 00000013\n", f"X 5 0 {expected:016X}\n"]
        lines.append(f"I 30 {fault_pc:016X} 00003023\n")
        if successful_write:
            lines.append(f"W {symbols['supervisor_manifest']:X} 8 0 3\n")
        lines.append("T 0 28\n")
        with tempfile.TemporaryDirectory(prefix="vos-manifest-observer-") as temporary:
            log = Path(temporary) / "trace"
            log.write_text("".join(lines), encoding="utf-8")
            return scalar_join.observations(log, symbols, (0xA000, 0xA008), (0xB000, 1),
                                            {"root": str(TOOLS.parent)}, "manifest-write", manifest)

    ensure(observed(manifest)["ok"] is True, "exact readonly manifest fault trace was refused")
    ensure(observed(b"\x04" + manifest[1:])["ok"] is False,
           "wrong initialized bytes passed the joined manifest oracle")
    ensure(observed(manifest, successful_write=True)["ok"] is False,
           "successful supervisor manifest store passed the named fault control")
    ensure(observed(manifest, fault_pc=0x10104)["ok"] is False,
           "fault at another instruction passed as the attempted manifest store")


def generated_pipeline(generated: bool = True, drift: str = "") -> None:
    """Exercise real joined source generation, with synthetic target execution."""
    with tempfile.TemporaryDirectory(prefix="vos-scalar-manifest-") as temporary:
        fixture = Path(temporary)
        root = TOOLS.parent
        ccomp = compiler_fixture.create(fixture)
        out = fixture / "joined"
        simulator, receipt = fixture / "simulator", fixture / "model.json"
        simulator.write_bytes(b"synthetic executor")
        receipt.write_text("{}", encoding="utf-8")
        snapshot = supervisor.checked_manifest(root)
        expected = scalar_join.lifecycle_target.manifest_bytes(json.loads(snapshot["manifest.json"])["payload"])
        compiled_roles: list[str] = []
        emitted: list[str] = []
        executed: list[str] = []

        def compile_c(args: list[str], unit: Path, work: Path, _timeout: int) -> SimpleNamespace:
            role = work.name
            compiled_roles.append(role)
            if role == "kernel":
                ensure("-DVOS_JOIN_INITIAL_EPOCH=1" in args and
                       f"-DVOS_JOIN_OWNED_BYTES={scalar_join.copy_partition.OWNED_BYTES}" in args,
                       "generated mode changed the joined epoch or complete copy allocation")
                ensure(unit == (out / "manifest-target.c" if generated else
                                root / "supervisor/test/context_join.c"),
                       "scalar kernel compiled the wrong manifest producer")
                if generated:
                    ensure((out / "manifest.c").read_bytes() == snapshot["manifest.c"],
                           "joined compiler did not consume the immutable projection")
                    ensure('#include "manifest.c"' in unit.read_text(encoding="utf-8"),
                           "joined unit omitted the actual generated object")
                    if drift in {"manifest.c", "manifest.json", "compile-unit"}:
                        changed = unit if drift == "compile-unit" else out / drift
                        changed.write_bytes(changed.read_bytes() + b" ")
            elif role == "supervisor":
                ensure(unit == root / "supervisor/test/context_join.c",
                       "reactor compiled a replacement implementation")
            else:
                ensure(unit == root / "copy-service/test/target_unit.c",
                       "joined source omitted the real copy producer")
            return SimpleNamespace(stream=f"{role}_body:\n    ret\n", said="")

        def assemble(text: str, *_args: object, **_kwargs: object) -> SimpleNamespace:
            ensure(all(label in text for label in
                       ("k_kernel_body:", "s_supervisor_body:", "copy_body:",
                        "scalar_join_copy_entry:", "call k_vos_join_init", "call s_vos_join_react")),
                   "joined source generation dropped an actual component")
            emitted.append(text)
            return SimpleNamespace(symbols={"grant_slots": 512, "scalar_join_copy_code": 0,
                                             "scalar_join_copy_code_end": 16},
                                   assemble=lambda: ([], {}, 0))

        def execute(case: scalar_join.TargetCase) -> dict[str, object]:
            ensure(case.expected_manifest == (expected if generated else None),
                   "joined observer did not receive the independent manifest layout")
            executed.append(case.name)
            if drift == "execute-unit":
                unit = out / "manifest-target.c"
                unit.write_bytes(unit.read_bytes() + b" ")
            return {"ok": True}

        def reaction(_counts: dict[str, int], *, backoff_count: int) -> dict[str, object]:
            ensure(backoff_count == (4 if generated else 1),
                   "joined reaction account omitted admitted backoff entries")
            return {"backoff_count": backoff_count}

        with ExitStack() as stack:
            replacements = [
                (scalar_join.compiler_provenance, "find_root", lambda: fixture),
                (scalar_join.receipts, "inputs", lambda *args: {}),
                (scalar_join.kernel_restore, "require_build", lambda *args: None),
                (scalar_join, "compiler_inputs", lambda *args: {}),
                (scalar_join.cd, "compile_c", compile_c),
                (scalar_join.lifecycle_target, "instruction_counts", lambda *args: {}),
                (scalar_join.lifecycle_target, "longest_path", lambda *args: {"longest_path_steps": 1}),
                (scalar_join.lifecycle_target, "reaction_path", reaction),
                (scalar_join.asm, "Assembler", assemble),
                (scalar_join.kernel_target, "revocation_window", lambda *args: (512, 1)),
                (scalar_join.image, "write_elf", lambda path, *args: path.write_bytes(b"synthetic image")),
                (scalar_join, "ProcessPoolExecutor", ThreadPoolExecutor),
                (scalar_join, "execute_case", execute),
            ]
            for module, member, replacement in replacements:
                stack.enter_context(patch.object(module, member, replacement))
            report = scalar_join.run(root, out, ccomp, [], simulator, receipt,
                                     generated_manifest=generated)
        ensure(compiled_roles == ["kernel", "supervisor", "copy"], "joined compile membership changed")
        expected_controls = ["none", "stale", "incomplete", "manifest-write"] if generated else ["none", "stale", "incomplete"]
        ensure(sorted(executed) == sorted(expected_controls), "joined controls omitted a required path")
        ensure(report["ok"] is True and report["production_admission"] is False and
               report["milestone_acceptance"] == "open", "fixture execution promoted acceptance")
        ensure(report["production_manifest"] == ({
            name: scalar_join.receipts.digest(out / name) for name in snapshot} if generated else {}),
            "joined receipt lost its checked projection identities")
        if generated:
            ensure("supervisor_permission_control:\n    sd x0, 0(c10)" in emitted[-1] and
                   "li x6, supervisor_permission_control" in emitted[-1],
                   "joined manifest write control lacks the actual store and named fault check")
            ensure("    ld x5, 80(c11)\n    beqz x5, supervisor_poll_return" in emitted[0],
                   "short-delay generated policy lost its initial empty publication")


def generated_drift() -> None:
    for name in ("manifest.c", "manifest.json", "compile-unit", "execute-unit"):
        try:
            generated_pipeline(drift=name)
        except ValueError as error:
            ensure("changed during" in str(error), f"wrong joined snapshot refusal: {error}")
        else:
            raise AssertionError(f"joined target accepted snapshot drift: {name}")


def locked_producer_refusal() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-scalar-producer-refusal-") as temporary:
        root = Path(temporary)
        out = root / "out"
        with (patch.object(scalar_join.compiler_provenance, "read",
                           side_effect=ValueError("contained compiler toolchain does not bind the recorded lock")),
              patch.object(scalar_join.cd, "compile_c") as compile_c):
            try:
                scalar_join.run(root, out, root / "ccomp", [], root / "simulator",
                                root / "receipt", generated_manifest=True)
            except ValueError:
                pass
            else:
                raise AssertionError("generated scalar join bypassed locked compiler preflight")
            ensure(not compile_c.called, "unqualified compiler reached target compilation")
        report = json.loads((out / "report.json").read_bytes())
        ensure(report["status"] == "refused" and report["stage"] == "compiler-provenance" and
               report["target_execution"] is False and report["generated_manifest"] is True,
               "preflight refusal invented target execution or lost the selected mode")


def joined_boot_observer() -> None:
    """Exercise the real streaming boot observer and joined receipt on scripted processes."""
    for scenario in ("normal", "stale", "incomplete", "manifest-write", "unexpected-copy",
                     "missing-copy", "wrong-order", "console-mismatch", "htif-failure",
                     "process-failure", "timeout", "missing-exit", "lifecycle-failure",
                     "late-failure"):
        _joined_boot_case(scenario)


def _joined_boot_case(scenario: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vos-scalar-boot-") as temporary:
        out = Path(temporary)
        name = "manifest-write" if scenario == "unexpected-copy" else (
            scenario if scenario in {"stale", "incomplete", "manifest-write"} else "none")
        (out / f"{name}.elf").write_bytes(b"scripted image")
        (out / f"{name}.s").write_bytes(b"scripted compiled-source placeholder")
        entries = [0x1000, 0x2000, 0x3000]
        if scenario in {"missing-copy", "manifest-write"}:
            entries.pop()
        if scenario == "wrong-order":
            entries[:2] = reversed(entries[:2])
        lines = [f"I {index} {pc:016X} 00000013\n" for index, pc in enumerate(entries)]
        lines += ["T 0 28\n", "W 0000000000004000 8 0 0101000000000041\n", "SUCCESS\n"]
        if scenario != "missing-exit":
            # The final commit record deliberately has no newline. Both the
            # boot projector and the retained lifecycle reader must see it.
            lines.append("W 0000000000004000 8 0 " +
                         ("0000000000000003" if scenario == "htif-failure" else "0000000000000001"))
        if scenario == "late-failure":
            lines[-1] += "\n"
            lines.append("FAILURE: 3 (0x3)")
        text = "".join(lines)
        killed: list[bool] = []

        class Stream(io.StringIO):
            @override
            def read(self, size: int | None = -1) -> str:
                raise AssertionError("boot observer must stream rather than read the trace whole")

            @override
            def readlines(self, hint: int = -1) -> list[str]:
                raise AssertionError("boot observer must stream rather than collect trace lines")

        class Process:
            def __init__(self, argv: list[str], **kwargs: object) -> None:
                ensure(kwargs["cwd"] == out, "joined simulator lost its assigned lane directory")
                Path(argv[argv.index("--terminal-log") + 1]).write_bytes(
                    b"B" if scenario == "console-mismatch" else b"A")
                self.stdout = Stream(text)

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_args: object) -> None:
                ensure(self.stdout.tell() == len(text), "boot observer omitted the final trace line")

            def wait(self) -> int:
                return -9 if killed else (1 if scenario == "process-failure" else 0)

            def kill(self) -> None:
                killed.append(True)

        class Timer:
            def __init__(self, _interval: float, callback: Callable[[], None]) -> None:
                self.callback = callback

            def start(self) -> None:
                if scenario == "timeout":
                    self.callback()

            def cancel(self) -> None:
                pass

        def lifecycle(log: Path, *_args: object) -> dict[str, object]:
            with log.open(encoding="utf-8") as retained:
                ensure(list(retained) == lines,
                       "lifecycle observer did not receive every streamed byte and final line")
            return {"ok": scenario != "lifecycle-failure"}

        case = scalar_join.TargetCase(out / "simulator", out / "profile", out, name,
            {"_start": 0x1000, "supervisor_entry": 0x2000,
             "scalar_join_copy_entry": 0x3000, "tohost": 0x4000},
            (0, 0), (0, 0), {}, 100, 10)
        with (patch.object(boot.subprocess, "Popen", Process),
              patch.object(boot.threading, "Timer", Timer),
              patch.object(scalar_join, "observations", lifecycle)):
            result = scalar_join.execute_case(case)
        passed = scenario in {"normal", "stale", "incomplete", "manifest-write"}
        ensure(result["ok"] is passed, f"joined boot result changed for {scenario}: {result}")
        observed = result["boot_observation"]
        ensure(isinstance(observed, dict), "joined receipt omitted boot observations")
        if not isinstance(observed, dict):
            return
        ensure(observed["production_admission"] is False and observed["milestone_acceptance"] == "open",
               "scripted observer test promoted a bounded checkpoint to full boot acceptance")
        ensure(observed["event_sha256"] == scalar_join.receipts.digest(out / f"{name}.events") and
               observed["console_sha256"] == scalar_join.receipts.digest(out / f"{name}.console"),
               "joined receipt does not bind retained events and console bytes")
        ensure(observed["timed_out"] is (scenario == "timeout"), "timeout status was lost")
        if scenario == "lifecycle-failure":
            ensure(observed["findings"] == [], "lifecycle refusal was replaced by boot failure")


def cases() -> list[Case]:
    return [Case("joined request publication and later acknowledgment chronology", wire_publication_order),
            Case("joined fixed supervisor/copy table", fixed_table),
            Case("joined independent manifest bytes and entry snapshots", manifest_trace_bytes),
            Case("joined serialized readonly-manifest fault and spoiled traces", manifest_permission_observer),
            Case("production manifest reaches real joined source generation", generated_pipeline),
            Case("ordinary scalar comparison keeps its manifest", lambda: generated_pipeline(False)),
            Case("joined manifest compile and execution drift refuse", generated_drift),
            Case("joined locked compiler refusal precedes target compilation", locked_producer_refusal),
            Case("joined real boot observer streams target output and retains refusals", joined_boot_observer)]
