# SPDX-License-Identifier: Apache-2.0
"""Verify copy-service ELF member extents and Sail commit-trace execution envelopes."""

import argparse
import collections
import gzip
import hashlib
import itertools
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from vos import image, trace

PUBLIC_ENTRIES: Final = (
    "vos_copy_init",
    "vos_copy_init_generation",
    "vos_copy_submit",
    "vos_copy_submit_batch",
    "vos_copy_take",
    "vos_copy_prepare_sleep",
    "vos_copy_notify",
    "vos_copy_poll",
)

MEMBER_GROUPS: Final = (
    "compiled C",
    "src/atomic_target.s",
    "src/notification_target.s",
)

CAP_ADDR_MASK: Final = (1 << 36) - 1


@dataclass(frozen=True)
class LoadSegment:
    """One verified PT_LOAD segment in the ELF64 executable."""

    address: int
    flags: int
    data: bytes


@dataclass(frozen=True)
class ElfImage:
    """Validated position-fixed ELF64 RISC-V executable with disjoint RX and RW segments."""

    entry: int
    text_base: int
    text: bytes
    data_base: int
    data: bytes
    segments: tuple[LoadSegment, ...]


@dataclass(frozen=True)
class MemberExtent:
    """Verified assembled text extent and symbols for one copy-service member."""

    label: str
    start: int
    end_exclusive: int
    size: int
    sha256: str
    symbols: dict[str, int]


@dataclass
class _CallFrame:
    return_pc: int
    caller_pc: int
    entry_name: str | None
    entry_sp: int | None
    min_sp: int | None
    insns: int = 0
    writes: int = 0


@dataclass(frozen=True)
class _CompletedCall:
    entry_name: str
    insns: int
    writes: int
    peak_stack_bytes: int | None


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def _parse_int(value: object, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{label} is not an integer or hex literal: {value!r}") from exc
    raise ValueError(f"{label} must be an integer or hex string")


def _is_call_insn(word: int) -> bool:
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    if rd == 0:
        return False
    if opcode == 0x6F:
        return True
    return opcode == 0x67 and ((word >> 12) & 0x7) == 0


def _is_return_insn(word: int) -> bool:
    return (word & 0x707F) == 0x67 and ((word >> 7) & 0x1F) == 0


def read_elf(raw: bytes) -> ElfImage:
    """Validate and extract the RX text and RW data segments from an ELF64 RISC-V image."""
    _require(len(raw) >= image.EHDR_SIZE, "ELF header is truncated")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", raw)
    ident, kind, machine, version = header[0], header[1], header[2], header[3]
    _require(
        ident[:7] == b"\x7fELF\x02\x01\x01"
        and kind == image.ET_EXEC
        and machine == image.EM_RISCV
        and version == 1
        and header[8] == image.EHDR_SIZE,
        "image must be an ELF64 RISC-V executable",
    )
    entry, phoff, phentsize, phnum = header[4], header[5], header[9], header[10]
    _require(
        phentsize == image.PHDR_SIZE and phnum > 0 and phoff + phentsize * phnum <= len(raw),
        "ELF program header table is truncated",
    )
    loads: list[LoadSegment] = []
    for index in range(phnum):
        seg_kind, flags, offset, virtual, physical, file_size, memory_size, _ = struct.unpack_from(
            "<IIQQQQQQ", raw, phoff + index * phentsize
        )
        if seg_kind == image.PT_LOAD:
            _require(
                physical == virtual and file_size == memory_size > 0 and offset + file_size <= len(raw),
                "unexpected ELF load segment extent",
            )
            loads.append(LoadSegment(physical, flags, raw[offset : offset + file_size]))
    loads.sort(key=lambda seg: seg.address)
    _require(
        len(loads) == 2
        and loads[0].address + len(loads[0].data) <= loads[1].address
        and [seg.flags for seg in loads] == [image.PF_R | image.PF_X, image.PF_R | image.PF_W],
        "image must have disjoint RX text and RW data load segments",
    )
    _require(entry == loads[0].address, "ELF entry differs from executable text base")
    return ElfImage(
        entry=entry,
        text_base=loads[0].address,
        text=loads[0].data,
        data_base=loads[1].address,
        data=loads[1].data,
        segments=tuple(loads),
    )


def validate_member_ranges(
    elf: ElfImage, ranges: Mapping[str, object]
) -> tuple[dict[str, MemberExtent], dict[int, str]]:
    """Verify assembled member ranges, SHA-256 digests, and public symbols against `elf`."""
    _require(set(ranges.keys()) == set(MEMBER_GROUPS), "member ranges must cover compiled C and both adapters")
    extents: dict[str, MemberExtent] = {}
    symbols: dict[str, int] = {}
    text_end = elf.text_base + len(elf.text)

    for label in MEMBER_GROUPS:
        raw_item = ranges[label]
        _require(isinstance(raw_item, Mapping), f"{label} range must be an object")
        item = cast(Mapping[str, object], raw_item)
        start = _parse_int(item.get("start"), f"{label}.start")
        end = _parse_int(item.get("end_exclusive"), f"{label}.end_exclusive")
        expected_bytes = _parse_int(item.get("bytes"), f"{label}.bytes")
        raw_sha = item.get("sha256")
        _require(isinstance(raw_sha, str) and len(raw_sha) == 64, f"{label} missing SHA-256 digest")
        expected_sha = cast(str, raw_sha)
        _require(
            elf.text_base <= start < end <= text_end and start % 4 == 0 and end % 4 == 0,
            f"{label} has an invalid RX extent",
        )
        content = elf.text[start - elf.text_base : end - elf.text_base]
        _require(
            len(content) == expected_bytes and _sha256(content) == expected_sha,
            f"{label} executable range differs from its expected digest or size",
        )
        raw_symbols = item.get("vos_copy_symbols")
        _require(isinstance(raw_symbols, Mapping), f"{label} missing vos_copy_symbols")
        symbol_map = cast(Mapping[object, object], raw_symbols)
        member_symbols: dict[str, int] = {}
        for raw_name, raw_pc in symbol_map.items():
            _require(isinstance(raw_name, str), f"{label} symbol name must be a string")
            name = cast(str, raw_name)
            addr = _parse_int(raw_pc, f"{label}.{name}")
            _require(
                name not in symbols and start <= addr < end and addr % 4 == 0,
                f"symbol {name} falls outside {label} extent or collides",
            )
            symbols[name] = addr
            member_symbols[name] = addr
        extents[label] = MemberExtent(
            label=label,
            start=start,
            end_exclusive=end,
            size=expected_bytes,
            sha256=expected_sha,
            symbols=member_symbols,
        )

    ordered = sorted(extents.values(), key=lambda ext: ext.start)
    for left, right in itertools.pairwise(ordered):
        _require(
            left.end_exclusive <= right.start,
            f"member extents {left.label} and {right.label} overlap",
        )

    entry_to_name: dict[int, str] = {}
    for name in PUBLIC_ENTRIES:
        _require(name in symbols, f"missing public entry symbol {name}")
        pc = symbols[name]
        _require(pc not in entry_to_name, f"public entry PC {pc:#x} collides for {name}")
        entry_to_name[pc] = name
    return extents, entry_to_name


def _locate_htif(elf: ElfImage, lines: list[str]) -> int:
    htif_lines = [line for line in lines if line.startswith("HTIF located at ")]
    _require(len(htif_lines) == 1, "trace must locate the HTIF word exactly once")
    htif = _parse_int(htif_lines[0].split()[-1], "HTIF address")
    _require(
        htif % 8 == 0 and elf.data_base <= htif <= elf.data_base + len(elf.data) - 8,
        "trace HTIF address is outside the loaded writable segment",
    )
    return htif


def _origin_role(pc: int, extents: dict[str, MemberExtent]) -> str:
    for label, ext in extents.items():
        if ext.start <= pc < ext.end_exclusive:
            return label
    return "harness"


def _innermost_public(call_stack: list[_CallFrame]) -> str | None:
    for frame in reversed(call_stack):
        if frame.entry_name is not None:
            return frame.entry_name
    return None


def analyze_trace(
    elf: ElfImage,
    extents: dict[str, MemberExtent],
    entry_to_name: dict[int, str],
    raw_lines: list[str],
) -> dict[str, object]:
    """Verify commit records against `elf` and compute per-entry execution envelopes."""
    htif = _locate_htif(elf, raw_lines)
    records = trace.normalize_commit(raw_lines)
    _require(bool(records), "trace contains no commit records")

    origin_counts: collections.Counter[str] = collections.Counter()
    retired = 0
    memory_reads = 0
    memory_writes = 0
    htif_writes: list[tuple[int, int, int]] = []
    call_stack: list[_CallFrame] = []
    completed: list[_CompletedCall] = []
    current_sp: int | None = None
    prev_pc: int | None = None
    prev_insn: int | None = None

    for record in records:
        kind = record[0]
        if kind == "I":
            _, pc_hex, word_hex = record.split()
            pc = int(pc_hex, 16)
            word = int(word_hex, 16)
            offset = pc - elf.text_base
            _require(
                0 <= offset <= len(elf.text) - 4 and offset % 4 == 0,
                f"retired PC {pc:#x} is outside aligned ELF text",
            )
            expected_word = int.from_bytes(elf.text[offset : offset + 4], "little")
            _require(
                expected_word == word,
                f"retired word {word:#010x} at {pc:#x} differs from ELF word {expected_word:#010x}",
            )
            if retired == 0:
                _require(pc == elf.entry, f"trace started at {pc:#x}, expected ELF entry {elf.entry:#x}")

            if call_stack and pc == call_stack[-1].return_pc and prev_insn is not None and _is_return_insn(prev_insn):
                frame = call_stack.pop()
                if frame.entry_name is not None:
                    if frame.entry_sp is not None and current_sp is not None and current_sp != frame.entry_sp:
                        raise ValueError(
                            f"unbalanced stack on return from {frame.entry_name}: "
                            f"entry {frame.entry_sp:#x}, return {current_sp:#x}"
                        )
                    peak = (
                        frame.entry_sp - frame.min_sp
                        if frame.entry_sp is not None and frame.min_sp is not None
                        else None
                    )
                    completed.append(
                        _CompletedCall(
                            entry_name=frame.entry_name,
                            insns=frame.insns,
                            writes=frame.writes,
                            peak_stack_bytes=peak,
                        )
                    )

            if prev_pc is not None and prev_insn is not None and _is_call_insn(prev_insn):
                call_stack.append(
                    _CallFrame(
                        return_pc=prev_pc + 4,
                        caller_pc=prev_pc,
                        entry_name=entry_to_name.get(pc),
                        entry_sp=current_sp,
                        min_sp=current_sp,
                    )
                )

            retired += 1
            origin_counts[_origin_role(pc, extents)] += 1
            for frame in call_stack:
                if frame.entry_name is not None:
                    frame.insns += 1
            prev_pc = pc
            prev_insn = word
        elif kind == "W":
            _, addr_hex, width_s, tag_s, value_hex = record.split()
            memory_writes += 1
            for frame in call_stack:
                if frame.entry_name is not None:
                    frame.writes += 1
            if int(addr_hex, 16) == htif:
                htif_writes.append((int(width_s), int(tag_s), int(value_hex, 16)))
        elif kind == "R":
            memory_reads += 1
        elif kind == "X":
            _, reg_s, _, value_hex = record.split()
            if int(reg_s) == 2:
                sp = int(value_hex, 16) & CAP_ADDR_MASK
                current_sp = sp
                for frame in call_stack:
                    if frame.entry_name is not None and (frame.min_sp is None or sp < frame.min_sp):
                        frame.min_sp = sp
        elif kind == "T":
            _, irq_s, cause_s = record.split()
            active = _innermost_public(call_stack)
            pc_note = f"{prev_pc:#x}" if prev_pc is not None else "unknown"
            where = f"inside {active}" if active is not None else "outside service entries"
            raise ValueError(
                f"unexpected trap {where} at {pc_note} (interrupt={irq_s}, cause={cause_s})"
            )

    _require(retired > 0, "trace retired zero instructions")
    if call_stack:
        unclosed = ", ".join(
            f"{frame.entry_name or 'internal'}@{frame.caller_pc:#x}" for frame in call_stack
        )
        raise ValueError(f"unbalanced call without return: {unclosed}")

    non_empty = [line.strip() for line in raw_lines if line.strip()]
    expected_htif_record = f"W {htif:016X} 8 0 0000000000000001"
    _require(
        htif_writes == [(8, 0, 1)]
        and bool(non_empty)
        and non_empty[-1] == "SUCCESS"
        and records[-1] == expected_htif_record,
        "trace did not end at the passing HTIF write",
    )

    by_entry: dict[str, list[_CompletedCall]] = {name: [] for name in PUBLIC_ENTRIES}
    for call in completed:
        by_entry[call.entry_name].append(call)

    entry_pcs = {name: pc for pc, name in entry_to_name.items()}
    operations: dict[str, object] = {}
    for name in PUBLIC_ENTRIES:
        calls = by_entry[name]
        insns_list = [c.insns for c in calls]
        writes_list = [c.writes for c in calls]
        stacks_list = [c.peak_stack_bytes for c in calls]
        known_stacks = [s for s in stacks_list if s is not None]
        operations[name] = {
            "entry_pc": hex(entry_pcs[name]),
            "call_count": len(calls),
            "retired_instructions": {
                "min": min(insns_list) if insns_list else None,
                "max": max(insns_list) if insns_list else None,
                "total": sum(insns_list),
                "per_call": insns_list,
            },
            "memory_writes": {
                "min": min(writes_list) if writes_list else None,
                "max": max(writes_list) if writes_list else None,
                "total": sum(writes_list),
                "per_call": writes_list,
            },
            "stack_frame_bytes": {
                "peak": max(known_stacks) if known_stacks else None,
                "per_call": stacks_list,
            },
        }

    trace_blob = "\n".join(records).encode("utf-8")
    return {
        "harness_entry": hex(elf.entry),
        "htif_address": hex(htif),
        "trace_summary": {
            "records": len(records),
            "trace_sha256": _sha256(trace_blob),
            "retired_instructions": retired,
            "retired_by_origin": {label: origin_counts.get(label, 0) for label in (*MEMBER_GROUPS, "harness")},
            "memory_reads": memory_reads,
            "memory_writes": memory_writes,
        },
        "call_accounting": "inclusive",
        "operations": operations,
    }


def observe(
    elf_bytes: bytes,
    raw_log: bytes,
    member_ranges: Mapping[str, object],
) -> dict[str, object]:
    """Validate an ELF image, its assembled member ranges, and its Sail commit trace."""
    elf = read_elf(elf_bytes)
    extents, entry_to_name = validate_member_ranges(elf, member_ranges)
    lines = raw_log.decode("utf-8").splitlines()
    analyzed = analyze_trace(elf, extents, entry_to_name, lines)
    compiled_c = extents["compiled C"]
    atomic = extents["src/atomic_target.s"]
    notification = extents["src/notification_target.s"]
    service_text_bytes = compiled_c.size + atomic.size + notification.size
    return {
        "elf_sha256": _sha256(elf_bytes),
        "raw_log_sha256": _sha256(raw_log),
        "load_segments": [
            {
                "address": hex(seg.address),
                "flags": seg.flags,
                "bytes": len(seg.data),
                "sha256": _sha256(seg.data),
            }
            for seg in elf.segments
        ],
        "static_footprint": {
            "compiled_c_bytes": compiled_c.size,
            "atomic_target_bytes": atomic.size,
            "notification_target_bytes": notification.size,
            "service_text_bytes": service_text_bytes,
            "rx_segment_bytes": len(elf.text),
            "rw_data_bytes": len(elf.data),
            "members": {
                label: {
                    "start": hex(ext.start),
                    "end_exclusive": hex(ext.end_exclusive),
                    "bytes": ext.size,
                    "sha256": ext.sha256,
                }
                for label, ext in extents.items()
            },
        },
        **analyzed,
    }


def _load_trace(path: Path) -> bytes:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        return gzip.decompress(raw)
    return raw


def _extract_member_ranges(receipt: Mapping[str, object]) -> Mapping[str, object]:
    for key in ("assembled_member_ranges", "assembled_member_ranges_in_harness"):
        candidate = receipt.get(key)
        if isinstance(candidate, Mapping):
            return cast(Mapping[str, object], candidate)
    raise ValueError("receipt JSON missing assembled_member_ranges")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for analyzing an ELF, member ranges receipt, and commit trace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--ranges", required=True, type=Path, help="JSON containing assembled_member_ranges")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    receipt = json.loads(args.ranges.read_text(encoding="utf-8"))
    _require(isinstance(receipt, Mapping), "ranges JSON must be an object")
    report = observe(
        args.elf.read_bytes(),
        _load_trace(args.trace),
        _extract_member_ranges(cast(Mapping[str, object], receipt)),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
