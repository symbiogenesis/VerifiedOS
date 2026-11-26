# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests and negative controls for `vos.copy_envelope`."""

import gzip
import hashlib
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.harness import TOOLS, Case, ensure
from vos import asm, copy_envelope, image

REPO_ROOT = TOOLS.parent
ARCHIVE_DIR = REPO_ROOT / "docs/implementation/retained-evidence"
ASSEMBLY_REPORT = ARCHIVE_DIR / "holdfast-q25bb-standalone-assembly-20261125/report.json"
RUNTIME_REPORT = ARCHIVE_DIR / "holdfast-q25bb-standalone-runtime-20261125/report.json"
RUNTIME_TRACE = ARCHIVE_DIR / "holdfast-q25bb-standalone-runtime-20261125/standalone-notification.log.gz"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _refuse(fn: Callable[[], object], expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        ensure(expected in str(exc), f"expected {expected!r} in refusal, got: {exc}")
        return
    raise AssertionError(f"expected ValueError containing {expected!r}")


def _build_synthetic_fixture() -> tuple[bytes, dict[str, object], dict[str, int]]:
    """Assemble a real ELF64 RISC-V binary with all eight public entries and a helper."""
    harness_src = "\n".join(
        [
            ".text",
            "main:",
            "    call vos_copy_init",
            "    call vos_copy_init_generation",
            "    call vos_copy_submit_batch",
            "    call vos_copy_take",
            "    call vos_copy_prepare_sleep",
            "    call vos_copy_notify",
            "    call vos_copy_poll",
            "    nop",
        ]
    )
    compiled_c_src = "\n".join(
        [
            "vos_copy_helper:",
            "    cincoffsetimm c2, c2, -32",
            "    cincoffsetimm c2, c2, 32",
            "    ret",
            "vos_copy_init_slots:",
            "    cincoffsetimm c2, c2, -16",
            "    sc c1, 0(c2)",
            "    call vos_copy_helper",
            "    lc c1, 0(c2)",
            "    cincoffsetimm c2, c2, 16",
            "    ret",
        ]
    )
    atomic_src = "\n".join(
        [
            "vos_copy_init:",
            "    li x11, 1",
            "vos_copy_init_generation:",
            "    cincoffsetimm c2, c2, -16",
            "    sc c1, 0(c2)",
            "    call vos_copy_init_slots",
            "    lc c1, 0(c2)",
            "    cincoffsetimm c2, c2, 16",
            "    ret",
            "vos_copy_submit:",
            "    cincoffsetimm c2, c2, -24",
            "    sc c1, 0(c2)",
            "    lc c1, 0(c2)",
            "    cincoffsetimm c2, c2, 24",
            "    ret",
            "vos_copy_submit_batch:",
            "    cincoffsetimm c2, c2, -32",
            "    sc c1, 0(c2)",
            "    call vos_copy_submit",
            "    call vos_copy_submit",
            "    lc c1, 0(c2)",
            "    cincoffsetimm c2, c2, 32",
            "    ret",
            "vos_copy_take:",
            "    ret",
            "vos_copy_prepare_sleep:",
            "    ret",
        ]
    )
    notification_src = "\n".join(
        [
            "vos_copy_notify:",
            "    ret",
            "vos_copy_poll:",
            "    ret",
        ]
    )
    data_src = "\n".join(
        [
            ".data",
            "    .balign 8",
            "tohost:",
            "    .dword 0",
        ]
    )

    parts = [
        ("harness", harness_src + "\n"),
        ("compiled C", compiled_c_src + "\n"),
        ("src/atomic_target.s", atomic_src + "\n"),
        ("src/notification_target.s", notification_src + "\n"),
        ("data", data_src + "\n"),
    ]
    full_source = "".join(body for _, body in parts)
    assembler = asm.Assembler(full_source, "synthetic-envelope", data_base=0x80200000)
    sections, symbols, entry = assembler.assemble()
    with tempfile.TemporaryDirectory(prefix="vos-env-") as td:
        elf_path = Path(td) / "synthetic.elf"
        image.write_elf(elf_path, sections, symbols, entry)
        elf_bytes = elf_path.read_bytes()

    text_sec = next(sec for sec in sections if sec.name == ".text")
    ranges: dict[str, object] = {}
    line_cursor = 1
    for label, body in parts:
        next_cursor = line_cursor + body.count("\n")
        if label in copy_envelope.MEMBER_GROUPS:
            sites = [site for site in assembler.sites if line_cursor <= site.source < next_cursor]
            start = sites[0].address
            end = sites[-1].address + 4
            raw_slice = bytes(text_sec.data[start - text_sec.addr : end - text_sec.addr])
            ranges[label] = {
                "start": hex(start),
                "end_exclusive": hex(end),
                "bytes": len(raw_slice),
                "sha256": _sha256(raw_slice),
                "vos_copy_symbols": {
                    name: hex(addr)
                    for name, (sec_name, addr) in sorted(symbols.items())
                    if sec_name == ".text" and start <= addr < end and name.startswith("vos_copy_")
                },
            }
        line_cursor = next_cursor

    site_words = {site.address: site.word for site in assembler.sites}
    return elf_bytes, ranges, {name: addr for name, (_, addr) in symbols.items()} | {
        f"__word_{addr:#x}": word for addr, word in site_words.items()
    }


def _make_synthetic_trace(
    symbols: dict[str, int], *, include_sp: bool = True
) -> list[str]:
    """Build a valid multi-entry Sail commit trace over the synthetic fixture."""
    htif = symbols["tohost"]
    sp_base = 0x48580410_80284000
    order = 0
    lines = [
        f"HTIF located at {htif:#x}",
        f"Entry point: {symbols['main']:#x}",
    ]

    def step(pc: int, *effects: str) -> None:
        nonlocal order
        word = symbols[f"__word_{pc:#x}"]
        lines.append(f"I {order} {pc:016X} {word:08X}")
        lines.extend(effects)
        order += 1

    def set_sp(delta: int) -> str:
        return f"X 2 1 {(sp_base + delta):016X}"

    main_pc = symbols["main"]
    helper_pc = symbols["vos_copy_helper"]
    slots_pc = symbols["vos_copy_init_slots"]
    init_pc = symbols["vos_copy_init"]
    init_gen_pc = symbols["vos_copy_init_generation"]
    submit_pc = symbols["vos_copy_submit"]
    batch_pc = symbols["vos_copy_submit_batch"]
    take_pc = symbols["vos_copy_take"]
    sleep_pc = symbols["vos_copy_prepare_sleep"]
    notify_pc = symbols["vos_copy_notify"]
    poll_pc = symbols["vos_copy_poll"]

    def run_init_gen_body(caller_sp: int) -> None:
        step(init_gen_pc, *([set_sp(caller_sp - 16)] if include_sp else []))
        step(init_gen_pc + 4, f"W {htif + 8:016X} 8 1 0000000000000000")
        step(init_gen_pc + 8)
        step(slots_pc, *([set_sp(caller_sp - 32)] if include_sp else []))
        step(slots_pc + 4, f"W {htif + 16:016X} 8 1 0000000000000000")
        step(slots_pc + 8)
        step(helper_pc, *([set_sp(caller_sp - 64)] if include_sp else []))
        step(helper_pc + 4, *([set_sp(caller_sp - 32)] if include_sp else []))
        step(helper_pc + 8)
        step(slots_pc + 12)
        step(slots_pc + 16, *([set_sp(caller_sp - 16)] if include_sp else []))
        step(slots_pc + 20)
        step(init_gen_pc + 12)
        step(init_gen_pc + 16, *([set_sp(caller_sp)] if include_sp else []))
        step(init_gen_pc + 20)

    def run_submit_body(caller_sp: int) -> None:
        step(submit_pc, *([set_sp(caller_sp - 24)] if include_sp else []))
        step(submit_pc + 4, f"W {htif + 24:016X} 4 0 00000001")
        step(submit_pc + 8)
        step(submit_pc + 12, *([set_sp(caller_sp)] if include_sp else []))
        step(submit_pc + 16)

    # 1. main -> call vos_copy_init (falls through to vos_copy_init_generation)
    step(main_pc, *([set_sp(0)] if include_sp else []))
    step(init_pc)
    run_init_gen_body(0)

    # 2. main -> call vos_copy_init_generation directly
    step(main_pc + 4)
    run_init_gen_body(0)

    # 3. main -> call vos_copy_submit_batch (nested calls to vos_copy_submit x2)
    step(main_pc + 8)
    step(batch_pc, *([set_sp(-32)] if include_sp else []))
    step(batch_pc + 4, f"W {htif + 32:016X} 8 1 0000000000000000")
    step(batch_pc + 8)
    run_submit_body(-32)
    step(batch_pc + 12)
    run_submit_body(-32)
    step(batch_pc + 16)
    step(batch_pc + 20, *([set_sp(0)] if include_sp else []))
    step(batch_pc + 24)

    # 4. Leaf calls
    step(main_pc + 12)
    step(take_pc)
    step(main_pc + 16)
    step(sleep_pc)
    step(main_pc + 20)
    step(notify_pc, f"W {htif + 40:016X} 8 0 0000000000000001")
    step(main_pc + 24)
    step(poll_pc)
    step(main_pc + 28, f"W {htif:016X} 8 0 0000000000000001")
    lines.append("SUCCESS")
    return lines


def _synthetic_positive() -> None:
    elf_bytes, ranges, symbols = _build_synthetic_fixture()
    lines = _make_synthetic_trace(symbols, include_sp=True)
    report = copy_envelope.observe(elf_bytes, "\n".join(lines).encode("utf-8"), ranges)

    ops = cast(dict[str, Any], report["operations"])
    ensure(isinstance(ops, dict), "operations must be a dict")
    ensure(ops["vos_copy_init"]["call_count"] == 1, f"expected 1 init call: {ops['vos_copy_init']}")
    ensure(
        ops["vos_copy_init"]["retired_instructions"]["per_call"] == [16]
        and ops["vos_copy_init"]["memory_writes"]["per_call"] == [2]
        and ops["vos_copy_init"]["stack_frame_bytes"]["peak"] == 64,
        f"unexpected vos_copy_init envelope: {ops['vos_copy_init']}",
    )
    ensure(
        ops["vos_copy_init_generation"]["call_count"] == 1
        and ops["vos_copy_init_generation"]["retired_instructions"]["per_call"] == [15]
        and ops["vos_copy_init_generation"]["stack_frame_bytes"]["peak"] == 64,
        f"unexpected vos_copy_init_generation envelope: {ops['vos_copy_init_generation']}",
    )
    ensure(
        ops["vos_copy_submit_batch"]["call_count"] == 1
        and ops["vos_copy_submit_batch"]["retired_instructions"]["per_call"] == [17]
        and ops["vos_copy_submit_batch"]["memory_writes"]["per_call"] == [3]
        and ops["vos_copy_submit_batch"]["stack_frame_bytes"]["peak"] == 56,
        f"unexpected vos_copy_submit_batch envelope: {ops['vos_copy_submit_batch']}",
    )
    ensure(
        ops["vos_copy_submit"]["call_count"] == 2
        and ops["vos_copy_submit"]["retired_instructions"]["per_call"] == [5, 5]
        and ops["vos_copy_submit"]["memory_writes"]["total"] == 2
        and ops["vos_copy_submit"]["stack_frame_bytes"]["peak"] == 24,
        f"unexpected vos_copy_submit envelope: {ops['vos_copy_submit']}",
    )
    ensure(
        ops["vos_copy_notify"]["memory_writes"]["total"] == 1
        and ops["vos_copy_poll"]["retired_instructions"]["total"] == 1
        and ops["vos_copy_take"]["stack_frame_bytes"]["peak"] == 0,
        f"unexpected leaf envelopes: {ops}",
    )

    no_sp_lines = _make_synthetic_trace(symbols, include_sp=False)
    no_sp_report = copy_envelope.observe(elf_bytes, "\n".join(no_sp_lines).encode("utf-8"), ranges)
    no_sp_ops = cast(dict[str, Any], no_sp_report["operations"])
    ensure(isinstance(no_sp_ops, dict), "operations must be a dict")
    ensure(
        no_sp_ops["vos_copy_init"]["stack_frame_bytes"]["peak"] is None,
        f"missing X 2 trace must report peak=None: {no_sp_ops['vos_copy_init']}",
    )


def _archived_trace_positive() -> None:
    assembly = json.loads(ASSEMBLY_REPORT.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME_REPORT.read_text(encoding="utf-8"))
    raw_trace = gzip.decompress(RUNTIME_TRACE.read_bytes()).decode("utf-8")
    lines = raw_trace.splitlines()

    ranges = assembly["assembled_member_ranges_in_harness"]
    ensure(ranges == runtime["assembled_member_ranges"], "retained assembly/runtime ranges disagree")

    text_base = 0x80000000
    insn_words: dict[int, int] = {}
    for line in lines:
        if line.startswith("I "):
            _, _, pc_hex, word_hex = line.split()
            insn_words[int(pc_hex, 16)] = int(word_hex, 16)
    max_end = max(
        *(pc + 4 for pc in insn_words),
        *(int(item["end_exclusive"], 16) for item in ranges.values()),
    )
    text_buf = bytearray(max_end - text_base)
    for pc, word in insn_words.items():
        offset = pc - text_base
        text_buf[offset : offset + 4] = word.to_bytes(4, "little")

    # Fill untouched member bytes inside the archive test only for trace replay, while
    # validating trace_summary and entry envelopes against the retained runtime receipt.
    elf = copy_envelope.ElfImage(
        entry=text_base,
        text_base=text_base,
        text=bytes(text_buf),
        data_base=0x80200000,
        data=b"\x00" * 0x81000,
        segments=(
            copy_envelope.LoadSegment(text_base, image.PF_R | image.PF_X, bytes(text_buf)),
            copy_envelope.LoadSegment(0x80200000, image.PF_R | image.PF_W, b"\x00" * 0x81000),
        ),
    )
    extents: dict[str, copy_envelope.MemberExtent] = {}
    symbols: dict[str, int] = {}
    for label in copy_envelope.MEMBER_GROUPS:
        item = ranges[label]
        start = int(item["start"], 16)
        end = int(item["end_exclusive"], 16)
        member_syms = {name: int(pc, 16) for name, pc in item["vos_copy_symbols"].items()}
        symbols.update(member_syms)
        extents[label] = copy_envelope.MemberExtent(
            label=label,
            start=start,
            end_exclusive=end,
            size=item["bytes"],
            sha256=item["sha256"],
            symbols=member_syms,
        )
    entry_to_name = {symbols[name]: name for name in copy_envelope.PUBLIC_ENTRIES}

    analyzed = copy_envelope.analyze_trace(elf, extents, entry_to_name, lines)
    summary = cast(dict[str, Any], analyzed["trace_summary"])
    ensure(isinstance(summary, dict), "trace_summary must be a dict")
    ensure(
        summary["records"] == runtime["runtime_observed"]["records"]
        and summary["trace_sha256"] == runtime["runtime_observed"]["trace_sha256"],
        f"archived trace digest mismatch: {summary}",
    )
    ops = cast(dict[str, Any], analyzed["operations"])
    ensure(isinstance(ops, dict), "operations must be a dict")
    for name, expected in runtime["retired_entries"].items():
        ensure(
            ops[name]["call_count"] == expected["observed"],
            f"entry count mismatch for {name}: {ops[name]} vs {expected}",
        )
    ensure(
        ops["vos_copy_init"]["retired_instructions"]["per_call"] == [5728]
        and ops["vos_copy_init"]["stack_frame_bytes"]["peak"] == 32
        and ops["vos_copy_submit"]["retired_instructions"]["per_call"] == [527]
        and ops["vos_copy_submit"]["stack_frame_bytes"]["peak"] == 240
        and ops["vos_copy_take"]["retired_instructions"]["per_call"] == [499]
        and ops["vos_copy_take"]["stack_frame_bytes"]["peak"] == 176,
        f"archived per-entry metrics drifted: {ops}",
    )


def _negative_controls() -> None:
    elf_bytes, ranges, symbols = _build_synthetic_fixture()
    lines = _make_synthetic_trace(symbols, include_sp=True)
    htif = symbols["tohost"]

    # 1. Altered retired instruction word
    altered_word = lines.copy()
    first_i = next(idx for idx, line in enumerate(altered_word) if line.startswith("I "))
    altered_word[first_i] = altered_word[first_i][:-1] + ("1" if altered_word[first_i][-1] == "0" else "0")
    _refuse(
        lambda: copy_envelope.observe(elf_bytes, "\n".join(altered_word).encode("utf-8"), ranges),
        "differs from ELF word",
    )

    # 2. Unbalanced call without return (drop the return from vos_copy_poll before HTIF write)
    poll_idx = max(idx for idx, line in enumerate(lines) if f" {symbols['vos_copy_poll']:016X} " in line)
    unbalanced = lines[: poll_idx + 1] + lines[-2:]
    _refuse(
        lambda: copy_envelope.observe(elf_bytes, "\n".join(unbalanced).encode("utf-8"), ranges),
        "unbalanced call without return",
    )

    # 3. Trap during service call
    trapped = [*lines[: poll_idx + 1], "T 0 28", *lines[poll_idx + 1 :]]
    _refuse(
        lambda: copy_envelope.observe(elf_bytes, "\n".join(trapped).encode("utf-8"), ranges),
        "unexpected trap inside vos_copy_poll",
    )

    # 4. Wrong member digest
    bad_ranges = json.loads(json.dumps(ranges))
    bad_ranges["compiled C"]["sha256"] = "0" * 64
    _refuse(
        lambda: copy_envelope.observe(elf_bytes, "\n".join(lines).encode("utf-8"), bad_ranges),
        "differs from its expected digest or size",
    )

    # 5. Bad HTIF exit code
    bad_htif = [
        line.replace("0000000000000001", "0000000000000003")
        if line.startswith(f"W {htif:016X} ")
        else line
        for line in lines
    ]
    _refuse(
        lambda: copy_envelope.observe(elf_bytes, "\n".join(bad_htif).encode("utf-8"), ranges),
        "passing HTIF write",
    )


def cases() -> list[Case]:
    return [
        Case("copy-envelope-accepts-synthetic-multi-entry-traces", _synthetic_positive),
        Case("copy-envelope-matches-archived-notification-trace", _archived_trace_positive),
        Case("copy-envelope-refuses-five-negative-controls", _negative_controls),
    ]
