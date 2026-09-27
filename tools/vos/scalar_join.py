# SPDX-License-Identifier: Apache-2.0
"""Single-image scalar supervisor/copy integration, with bounded private reset.

This joins the real non-ASR context protocol and copy payload/notification path.
The copy allocation remains continuously owned; only the separate small exposed
grant slots are retired. Physical WCET, external clients and full boot remain
outside this checkpoint.
"""

import json
import subprocess
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from vos import asm, boot_handoff, copy_notification, copy_partition, copy_service, copy_target
from vos import dialect, image, jsonc, kernel_restore, kernel_target, kernelrun, lifecycle_target
from vos import receipts, supervisor_context, trace
from vos.boot_target import compiler_inputs
from vos.cli import compiler_diff as cd

LIMITS = ("Explicit reset composition; persistent private copy allocation, separate small retired "
          "grant slots. No external clients, physical WCET, full boot roster or ring bitmap claim.")
INPUTS = (*lifecycle_target.INPUTS, *copy_partition.INPUTS, "tools/vos/scalar_join.py",
          "tools/vos/supervisor_context.py")
MAX_STEPS = 200000000


@dataclass(frozen=True)
class Publication:
    instruction: int
    reaction: int
    pc: int
    words: tuple[int, ...]


@dataclass(frozen=True)
class WireTrace:
    requests: tuple[Publication, ...]
    acknowledgments: tuple[Publication, ...]
    later_reads: tuple[int, ...]


def wire_trace(lines: Iterable[str], *, request: int, acknowledgment: int,
               request_words: int, acknowledgment_words: int,
               supervisor_entry: int, supervisor_top: int) -> WireTrace:
    """Decode actual byte writes and sequence-last stores, never a C overlay.

    Repeated acknowledgment publication refreshes the same result; only a new
    sequence contributes another result. A later read must be in a supervisor
    reaction after the one which published that request.
    """
    memory: dict[int, int] = {}
    requests: list[Publication] = []
    acknowledgments: list[Publication] = []
    reads: list[int] = []
    instruction = reaction = pc = 0
    last_ack = 0
    request_reactions: dict[int, int] = {}
    for line in lines:
        for normalized in trace.normalize_commit([line]):
            kind, fields = kernelrun.parse_record(normalized)
            if kind == "I":
                instruction += 1
                pc = fields[0]
                if pc == supervisor_entry:
                    reaction += 1
            elif kind == "W":
                address, width, tag, value = fields
                if tag or not (request <= address < request + request_words * 8 or
                               acknowledgment <= address < acknowledgment + acknowledgment_words * 8):
                    continue
                for offset in range(width):
                    memory[address + offset] = (value >> (offset * 8)) & 255
                if width == 8 and value != 0 and address in (request, acknowledgment):
                    count = request_words if address == request else acknowledgment_words
                    words = tuple(sum(memory.get(address + word * 8 + byte, 0) << (byte * 8)
                                      for byte in range(8)) for word in range(count))
                    publication = Publication(instruction, reaction, pc, words)
                    if address == request:
                        requests.append(publication)
                        request_reactions[value] = reaction
                    elif value != last_ack:
                        acknowledgments.append(publication)
                        last_ack = value
            elif kind == "R":
                address, width, tag, value = fields
                if (address == acknowledgment and width == 8 and not tag and value != 0
                        and supervisor_entry <= pc < supervisor_top
                        and value in request_reactions and reaction > request_reactions[value]
                        and value not in reads):
                    reads.append(value)
    return WireTrace(tuple(requests), tuple(acknowledgments), tuple(reads))


def source(root: Path, kernel: str, supervisor: str, copy: str,
           windows: tuple[int, int], bitmap: tuple[int, int], boundary: int,
           service_slot: int, defect: str = "none") -> str:
    """Compose stable owner hooks; never rewrite another emitter's assembly."""
    if defect not in ("none", "stale", "incomplete"):
        raise ValueError("unknown scalar join control")
    layout = supervisor_context.layout(root)
    address, cap, call, roots = (lifecycle_target._address, lifecycle_target._cap,
                                lifecycle_target._call, lifecycle_target._root)
    send, pending, _ = copy_notification.layout(root)
    init = [*cap(20, "lifecycle_owned_span", copy_partition.OWNED_BYTES, 0xfe),
            "    sc c20, 96(c31)",
            *cap(20, f"lifecycle_owned_span + {copy_partition.STACK_OFFSET}",
                 copy_partition.STACK_BYTES, 0xfe),
            f"    li x5, {copy_partition.STACK_BYTES}", "    cincoffset c20, c20, x5",
            "    sc c20, 104(c31)", "    la c20, scalar_join_copy_code",
            f"    li x5, {copy_partition.CODE_BYTES}", "    csetbounds c20, c20, x5",
            "    li x5, 0x1cb", "    candperm c20, c20, x5",
            "    cgetbase x5, c20", "    li x6, scalar_join_copy_code",
            "    li x3, 20", "    bne x5, x6, lifecycle_fail",
            "    li x5, scalar_join_copy_entry", "    csetaddr c20, c20, x5",
            "    sc c20, 112(c31)", "    sd x0, 120(c31)",
            *address(20, "service_state + 64"), "    li x5, 123", "    sd x5, 0(c20)"]
    after = [*address(20, "acknowledgment"),
             f"    ld x5, {8 * layout['ACK_STATUS']}(c20)"]
    if defect == "stale":
        after += [f"    li x6, {layout['STATUS_STALE']}",
                  "    bne x5, x6, scalar_join_ack_normal", "    ld x5, 0(c20)",
                  "    li x6, 3", "    li x3, 21", "    bne x5, x6, lifecycle_fail",
                  "    ld x5, 120(c31)", "    li x6, 2", "    bne x5, x6, lifecycle_fail",
                  *call("vos_join_dispatchable", ("effects",)),
                  "    bnez x10, lifecycle_fail", "    j lifecycle_control_pass",
                  "scalar_join_ack_normal:", *address(20, "acknowledgment"),
                  f"    ld x5, {8 * layout['ACK_STATUS']}(c20)"]
    after += ["    bnez x5, scalar_join_ack_continue",
              f"    ld x5, {8 * layout['ACK_OPERATION']}(c20)",
              f"    li x6, {layout['OP_START']}", "    bne x5, x6, scalar_join_ack_continue",
              "    ld x5, 120(c31)", "    beqz x5, scalar_join_first",
              "    li x6, 2", "    li x3, 22", "    bne x5, x6, lifecycle_fail",
              "    li x5, 3", "    j scalar_join_mark", "scalar_join_first:", "    li x5, 1",
              "scalar_join_mark:", "    sd x5, 120(c31)",
              *call("vos_join_dispatchable", ("effects",)),
              "    li x3, 23", "    beqz x10, lifecycle_fail",
              *call("vos_join_epoch", ("effects",)), "    li x5, 0xffffffff",
              "    li x3, 24", "    bgtu x10, x5, lifecycle_fail", "    beqz x10, lifecycle_fail",
              *address(19, "restore_context")]
    after += [f"    sc cnull, {8 * register}(c19)" for register in range(33)]
    after += ["    sd x10, 88(c19)", "    lc c20, 104(c31)", "    sc c20, 16(c19)",
              "    lc c20, 96(c31)", "    li x5, 6", "    candperm c20, c20, x5",
              "    sc c20, 80(c19)", "    lc c20, 112(c31)", "    sc c20, 256(c19)"]
    for register, location, permissions in ((12, "service_state + 64", 3),
            (13, "service_state + 72", 7), (14, str(send), 7), (15, str(pending), 7)):
        after += cap(20, location, 8, permissions)
        if register in (13, 15):
            after += ["    sd x0, 0(c20)"]
        if register == 15:
            after += ["    li x5, 3", "    candperm c20, c20, x5"]
        after += [f"    sc c20, {8 * register}(c19)"]
    after += address(20, "saved_clear")
    after += ["    li x6, 33", "scalar_join_abandon_supervisor:", "    sc cnull, 0(c20)",
              "    cincoffsetimm c20, c20, 8", "    addi x6, x6, -1",
              "    bnez x6, scalar_join_abandon_supervisor", "    ld x7, 48(c31)",
              f"    li x6, {boundary}", "    add x7, x7, x6", "    sd x7, 56(c31)",
              f"    li x6, {service_slot}", "    add x6, x7, x6", "    sd x6, 48(c31)",
              "    lc c20, 16(c31)", "    sd x6, 0(c20)", "    lc c20, 24(c31)",
              "    cmove c31, c19", "scalar_join_padding_sample:", "    ld x5, 0(c20)",
              "    sub x6, x7, x5", "    addi x6, x6, -44", "    li x3, 25",
              "    bltz x6, lifecycle_fail", "    srli x8, x6, 1", "    andi x6, x6, 1",
              "    beqz x6, scalar_join_padding_even", "    nop", "scalar_join_padding_even:",
              "    beqz x8, scalar_join_restore", "scalar_join_padding_loop:", "    addi x8, x8, -1",
              "    bnez x8, scalar_join_padding_loop", "scalar_join_restore:",
              kernel_restore.emit().replace("vos_restore", "scalar_join_restore_image"),
              "scalar_join_ack_continue:"]
    fault = ["    csrr x5, mcause", "    li x6, 28", "    li x3, 26",
             "    bne x5, x6, lifecycle_fail", "    cspecialrw c20, mepcc, cnull",
             "    cgetaddr x5, c20", "    li x6, vos_copy_partition_fault",
             "    bne x5, x6, lifecycle_fail", "    ld x5, 120(c31)", "    li x6, 1",
             "    bne x5, x6, scalar_join_second_fault", "    li x5, 2", "    sd x5, 120(c31)",
             "    j lifecycle_not_done", "scalar_join_second_fault:", "    li x6, 3",
             "    bne x5, x6, lifecycle_fail", "    li x5, 4", "    sd x5, 120(c31)",
             "    j lifecycle_finish_check"]
    publish = ""
    if defect == "stale":
        publish = "\n".join([f"    ld x5, {8 * layout['REQ_EPOCH']}(c12)", "    li x6, 1",
             "    bleu x5, x6, scalar_join_publish_current",
             f"    ld x6, {8 * layout['REQ_OPERATION']}(c12)", f"    li x7, {layout['OP_START']}",
             "    bne x6, x7, scalar_join_publish_current", "    addi x5, x5, -1",
             f"    sd x5, {8 * layout['REQ_EPOCH']}(c12)", "scalar_join_publish_current:"])
    service = "\n".join([".align 16", "scalar_join_copy_code:", cd.normalize(copy),
             copy_target.adapter(root), copy_notification.adapter(root), copy_partition.entry(root),
             "scalar_join_copy_entry:", "    cspecialrw c5, pcc, cnull",
             "scalar_join_copy_base:", "    cgetbase x6, c5", "    li x7, scalar_join_copy_code",
             "    bne x6, x7, vos_copy_partition_failed_fault", "    j vos_copy_partition_entry",
             "scalar_join_copy_code_end:"])
    return lifecycle_target.source(kernel, supervisor, windows, bitmap, boundary,
        defect="incomplete" if defect == "incomplete" else "none", owned_bytes=copy_partition.OWNED_BYTES,
        service_text=service, init_extra="\n".join(init), after_ack="\n".join(after),
        retire_extra="\n".join(["    lc c20, 96(c31)", copy_partition.clear_span("scalar_join")]),
        fault_handler="\n".join(fault), supervisor_publish_extra=publish,
        dispatch_handler="\n".join([*roots(), "    ld x5, 120(c31)", "    li x6, 4",
                                      "    li x3, 27", "    bne x5, x6, lifecycle_fail"]))


def observations(log: Path, symbols: dict[str, int], windows: tuple[int, int],
                 bitmap: tuple[int, int], bound: dict[str, object], defect: str) -> dict[str, object]:
    """One streaming pass over actual registers, wire cells and complete storage."""
    pc = previous_pc = order = 0
    registers = dict.fromkeys(range(32), (0, 0))
    owned = bytearray(copy_partition.OWNED_BYTES)
    tagged: set[int] = set()
    slots: dict[int, tuple[int, int]] = {}
    entries, faults, scrubs, clears, retire_clean, releases = [], [], [], [], [], []
    bitmap_writes, old_tags, fresh_tags, copy_bases = [], [], [], []
    generations, payloads, notifications = [], [], []
    checks: dict[int, tuple[int, list[int]]] = {}
    for reg, name, extent, perm in ((20, "supervisor_text_base", 65536, 0x1cb),
            (2, "supervisor_stack", lifecycle_target.STACK, 0xfe),
            (10, "supervisor_manifest", 512, 3), (11, "acknowledgment", 256, 3),
            (12, "request", 512, 7)):
        for suffix, expected in (("tag", 1), ("base", symbols[name]),
                                 ("length", extent), ("permissions", perm)):
            checks[symbols[f"supervisor_cap_{reg}_{suffix}"]] = (expected, [])
    send, _, _ = copy_notification.layout(log_root := Path(bound["root"]))
    del log_root
    expected_slots = {symbols[name] + offset for name in ("saved_clear", "restore_context")
                      for offset in range(0, 264, 8)}
    mepcc = None
    clearing: set[int] | None = None
    sample = None
    release = None
    work_start = None
    work_steps = []
    ack_zero, ack_fences, empty_boundaries = [], [], []
    phase = 0
    no_ecall = confined = True

    def monitor(lines: Iterable[str]) -> Iterable[str]:
        nonlocal pc, previous_pc, order, mepcc, clearing, sample, release, work_start, phase
        nonlocal no_ecall, confined
        for raw in lines:
            text = raw.strip()
            if not trace.COMMIT_RE.fullmatch(text):
                continue
            normalized = trace.ORDER_RE.sub("I ", text)
            kind, fields = kernelrun.parse_record(normalized)
            if kind == "I":
                previous_pc, pc = pc, fields[0]
                order = int(text.split()[1])
                no_ecall &= fields[1] != 0x73
                if pc == symbols["lifecycle_timer_entry"]:
                    work_start = order
                if pc == symbols["lifecycle_trap_scrub_end"]:
                    scrubs.append(all(registers[r] == (0, 0) for r in range(1, 31)))
                if pc == symbols["supervisor_entry"]:
                    entries.append(order)
                if pc == symbols["scalar_join_copy_entry"]:
                    generations.append(registers[11])
                if pc in (symbols["supervisor_entry"], symbols["scalar_join_copy_entry"]):
                    if sample is not None:
                        releases.append({"expected": release, "observed": sample[1] + order - sample[0],
                                         "kind": "supervisor" if pc == symbols["supervisor_entry"] else "copy"})
                        sample = None
                if pc == symbols["scalar_join_clear_begin"]:
                    clearing = set()
                if pc == symbols["scalar_join_clear_end"]:
                    clears.append(clearing)
                    clearing = None
                if pc == symbols["k_vos_kernel_lifecycle_retire_finish"]:
                    retire_clean.append(mepcc == (0, 0) and set(slots) == expected_slots and
                                        all(value == (0, 0) for value in slots.values()) and
                                        not any(owned) and not tagged)
            elif kind == "X":
                registers[fields[0]] = fields[1:]
                if pc in checks and fields[0] == 5:
                    checks[pc][1].append(fields[2])
                if pc == symbols["scalar_join_copy_base"] and fields[0] == 6:
                    copy_bases.append(fields[2])
                if pc == symbols["lifecycle_old_root_tag"] and fields[0] == 5:
                    old_tags.append(fields[2])
                if pc == symbols["lifecycle_fresh_root_tag"] and fields[0] == 5:
                    fresh_tags.append(fields[2])
            elif kind == "S" and fields[0] == dialect.SCRS["mepcc"]:
                mepcc = fields[1:]
            elif kind == "T" and fields[0] == 0:
                faults.append((pc, fields))
            elif kind == "R":
                if pc in (symbols["lifecycle_padding_sample"], symbols["scalar_join_padding_sample"]):
                    if fields[0] == windows[1]:
                        sample = (order, fields[3])
                        if work_start is not None:
                            work_steps.append(order - work_start + 44)
            elif kind == "W":
                address, width, tag, value = fields
                if address == symbols["kernel_private"] + 56:
                    release = value
                if address == symbols["kernel_private"] + 120:
                    phase = value
                if address == bitmap[0]:
                    bitmap_writes.append(value)
                if address == send and value == 1:
                    notifications.append(order)
                if address == symbols["service_state"] + 72 and width == 1 and value == 123:
                    payloads.append(order)
                if symbols["supervisor_text_base"] <= pc < symbols["supervisor_text_end"]:
                    confined &= any(symbols[name] <= address and address + width <= symbols[name] + size
                                    for name, size in (("request", 512), ("supervisor_stack", lifecycle_target.STACK)))
                if address in expected_slots and width == 8:
                    slots[address] = (tag, value)
                offset = address - symbols["lifecycle_owned_span"]
                if 0 <= offset and offset + width <= len(owned):
                    owned[offset:offset + width] = value.to_bytes(width, "little")
                    for slot in range(offset // 8, (offset + width - 1) // 8 + 1):
                        tagged.discard(slot)
                    if tag:
                        tagged.add(offset // 8)
                    if clearing is not None and width == 8 and tag == value == 0:
                        clearing.add(offset)
                if address == symbols["acknowledgment"] and width == 8 and value != 0:
                    ack_fences.append(previous_pc == symbols["lifecycle_ack_publish"])
                    if value == 2:
                        ack_zero.append(not any(owned) and not tagged)
                    empty_boundaries.append(value)
            yield normalized

    with log.open(encoding="utf-8") as lines:
        wire = wire_trace(monitor(lines), request=symbols["request"], acknowledgment=symbols["acknowledgment"],
                          request_words=64, acknowledgment_words=32,
                          supervisor_entry=symbols["supervisor_entry"], supervisor_top=symbols["supervisor_text_end"])
    expected_entries = 2 if defect == "none" else 1
    reqs = [list(item.words[:6]) for item in wire.requests]
    acks = [list(item.words[:12]) for item in wire.acknowledgments]
    facts = {
        "actual_copy_payload_notification": len(payloads) == len(notifications) == expected_entries,
        "fresh_copy_generations": generations == [(0, n) for n in range(1, expected_entries + 1)],
        "exact_copy_pcc_base": copy_bases == [symbols["scalar_join_copy_code"]] * expected_entries,
        "completed_copy_faults": faults == [(symbols["vos_copy_partition_fault"], (0, 28))] * expected_entries,
        "all_resident_scrubs": bool(scrubs) and all(scrubs),
        "all_owned_words_and_tags_cleared": clears == [set(range(0, copy_partition.OWNED_BYTES, 8))],
        "save_restore_mepcc_before_completion": retire_clean == [True],
        "whole_owned_zero_at_ack": bool(ack_zero) and all(ack_zero),
        "actual_supervisor_cap_checks": bool(entries) and all(len(values) == len(entries) and
             all(value == expected for value in values) for expected, values in checks.values()),
        "supervisor_stores_confined": confined,
        "no_extra_syscall": no_ecall,
        "ack_sequence_last_fences": bool(ack_fences) and all(ack_fences),
        "ack_consumed_in_later_reaction": set(wire.later_reads) >= ({1, 2} if defect != "incomplete" else {1}),
        "fixed_releases": bool(releases) and all(item["expected"] == item["observed"] for item in releases),
        "source_work_account": bool(work_steps) and max(work_steps) <= int(bound["longest_path_steps"]),
        "bitmap_old_and_fresh": bitmap_writes == [7] and old_tags == [0] and fresh_tags == [1],
    }
    if defect == "incomplete":
        facts["incomplete_refusal"] = len(acks) == 2 and acks[-1][0:2] == [2, 3] and phase == 2
    else:
        facts["actual_start_retire_start"] = [r[:2] for r in reqs] == [[1, 2], [2, 1], [3, 2]]
        facts["empty_and_occupied_boundaries"] = empty_boundaries.count(2) >= 2
        facts["fresh_epoch_or_stale_refusal"] = len(acks) == 3 and acks[-1][0:2] == [3, 2 if defect == "stale" else 0] and acks[-1][3] == 2
        facts["final_copy_state"] = phase == (2 if defect == "stale" else 4)
    return {"ok": all(facts.values()), "facts": facts, "requests": reqs, "acknowledgments": acks,
            "later_ack_reads": wire.later_reads, "release_instants": releases, "handler_steps": work_steps}


def run(root: Path, out: Path, ccomp: Path, arguments: list[str], simulator: Path,
        build_receipt: Path, timeout: int = 900) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    receipts.write(out / "report.json", {"ok": False, "status": "incomplete"})
    inputs, model = receipts.inputs(root, *INPUTS), receipts.inputs(root, "model")
    external = {"compiler": receipts.digest(ccomp), "simulator": receipts.digest(simulator),
                "build_receipt": receipts.digest(build_receipt)}
    private = compiler_inputs(arguments)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")), external["simulator"], model)
    args = [str(ccomp), *arguments, "-fverifiedos-typed", f"-I{root / 'supervisor/include'}", f"-I{root / 'kernel/include'}"]
    unit = root / "supervisor/test/context_join.c"
    kernel = cd.compile_c([*args, "-DVOS_JOIN_KERNEL", "-DVOS_JOIN_INITIAL_EPOCH=1",
                           f"-DVOS_JOIN_OWNED_BYTES={copy_partition.OWNED_BYTES}"], unit, out / "kernel", timeout)
    supervisor = cd.compile_c(args, unit, out / "supervisor", timeout)
    config = copy_service.configuration(root)
    (out / "copy_service_config.h").write_text(copy_service.configuration_header(config), encoding="utf-8")
    copy = cd.compile_c([str(ccomp), *arguments, "-fverifiedos-typed", f"-I{out}",
                        f"-I{root / 'copy-service/include'}"], root / "copy-service/test/target_unit.c", out / "copy", timeout)
    if kernel.stream is None or supervisor.stream is None or copy.stream is None:
        raise ValueError(f"typed join compilation refused: {kernel.said};{supervisor.said};{copy.said}")
    counts = lifecycle_target.instruction_counts(kernel.stream)
    bound = lifecycle_target.longest_path(counts, copy_partition.OWNED_BYTES, 1 << 26)
    copy_counts = lifecycle_target.instruction_counts(copy.stream)
    # In this immutable entry only initialization loops64 times, two one-byte
    # stages run, and the empty submit scan executes zero iterations. Eight
    # calls per whole body and128 traversals overcounts every reachable branch.
    copy_steps = 1024 * sum(copy_counts.values()) + 16384
    service_slot = 1 << copy_steps.bit_length()
    hooks = 4 * (copy_partition.OWNED_BYTES // 8 + 33) + 4096
    hooks += 4 * sum(counts.values())  # actual fault helper and dispatch predicates
    bound["joined_hook_steps"] = hooks
    bound["longest_path_steps"] = int(bound["longest_path_steps"]) + hooks
    boundary = 1 << int(bound["longest_path_steps"]).bit_length()
    bound.update({"padded_boundary_steps": boundary, "root": str(root), "copy_reaction_steps": copy_steps,
                  "copy_slot_steps": service_slot, "copy_counts": copy_counts,
                  "supervisor_reaction": lifecycle_target.reaction_path(lifecycle_target.instruction_counts(supervisor.stream))})
    windows = boot_handoff.timer_windows(root)
    probe = asm.Assembler(source(root, kernel.stream, supervisor.stream, copy.stream, windows, (0, 1), boundary, service_slot),
                          "layout", text_base=lifecycle_target.TEXT_BASE, data_base=lifecycle_target.DATA_BASE)
    probe.assemble()
    bitmap = kernel_target.revocation_window(root, probe.symbols["grant_slots"])
    profile = jsonc.load(root / boot_handoff.MAIN_CONFIG)
    profile["platform"]["instructions_per_tick"] = 1
    profile_path = out / "profile.json"
    receipts.write(profile_path, profile)
    results = []
    for defect in ("none", "stale", "incomplete"):
        emitted = source(root, kernel.stream, supervisor.stream, copy.stream, windows, bitmap, boundary, service_slot, defect)
        source_path = out / f"{defect}.s"
        source_path.write_text(emitted, encoding="utf-8")
        assembler = asm.Assembler(emitted, defect, text_base=lifecycle_target.TEXT_BASE, data_base=lifecycle_target.DATA_BASE)
        sections, symbols, entry = assembler.assemble()
        if assembler.symbols["scalar_join_copy_code_end"] - assembler.symbols["scalar_join_copy_code"] > copy_partition.CODE_BYTES:
            raise ValueError("copy code exceeds the exact composed PCC extent")
        elf, log = out / f"{defect}.elf", out / f"{defect}.trace"
        image.write_elf(elf, sections, symbols, entry)
        with log.open("w", encoding="utf-8") as output:
            done = subprocess.run([str(simulator), "--config", str(profile_path), "--trace-commit",
                                   "--inst-limit", str(MAX_STEPS), str(elf)], cwd=out, stdout=output,
                                  stderr=subprocess.STDOUT, timeout=timeout, check=False)
        with log.open(encoding="utf-8") as output:
            tail = "".join(deque(output, maxlen=64))
        verdict, code, detail = cd.htif_verdict(tail, done.returncode)
        observed = observations(log, assembler.symbols, windows, bitmap, bound, defect)
        results.append({"name": defect, "verdict": verdict, "code": code, "detail": detail,
                        "observations": observed, "source_sha256": receipts.digest(source_path),
                        "image_sha256": receipts.digest(elf), "trace_sha256": receipts.digest(log)})
        receipts.write(out / f"{defect}.json", results[-1])
        if verdict != "pass" or not observed["ok"]:
            break
    unchanged = inputs == receipts.inputs(root, *INPUTS) and model == receipts.inputs(root, "model")
    unchanged &= private == compiler_inputs(arguments) and external == {
        "compiler": receipts.digest(ccomp), "simulator": receipts.digest(simulator),
        "build_receipt": receipts.digest(build_receipt)}
    report = {"ok": unchanged and len(results) == 3 and all(r["verdict"] == "pass" and r["observations"]["ok"] for r in results),
              "sources": inputs, "model_sources": model, "external": external, "compiler_inputs": private,
              "bound": bound, "results": results, "limits": LIMITS, "instruction_limit": MAX_STEPS,
              "timeout_seconds_per_image": timeout, "inputs_unchanged": unchanged}
    receipts.write(out / "report.json", report)
    return report
