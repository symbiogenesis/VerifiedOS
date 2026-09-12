# SPDX-License-Identifier: Apache-2.0
"""Executable finite frame transformations with a checked, static byte schedule.

The emitted instructions are a research interpreter language, not target code.
All storage and instruction costs below are explicit model assumptions. Python's
allocations, target capability encoding, instruction selection and WCET are not
measured by this experiment. Inputs are exclusively owned and may be destroyed.
"""

import hashlib
import itertools
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vos import static_memory as sm

GENERATOR = "tools/vos/static_memory_transform.py"
VARIANTS = ("lexical-cache", "phased-cache", "early-input-release", "chunked-cache",
            "tiled-rematerialized", "fused-rematerialized", "in-place-phased")
DESCRIPTOR_BYTES = 32
DESCRIPTOR_ACCESS_BYTES = 24
WORKSPACE_BYTES = 64
ALIGNMENT = 8
MAX_LENGTH = 64


@dataclass(frozen=True)
class Instruction:
    op: str
    buffer: str = ""
    index: int = 0
    other: str = ""
    other_index: int = 0
    size: int = 0
    role: str = ""


@dataclass(frozen=True)
class Program:
    variant: str
    length: int
    tile: int
    instructions: tuple[Instruction, ...]


def _positive(value: int, name: str, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name}: expected an integer in [1,{maximum}]")


def reference(frame: bytes) -> bytes:
    """Value specification, independent of bytecode, storage and map implementation."""
    mapped = [(3 * value + 1) % 256 for value in frame]
    checksum = sum(mapped) % 256
    return bytes(value ^ checksum for value in mapped)


def emit_program(variant: str, length: int, tile: int = 8) -> Program:
    """Specialize an unrolled fixed schedule to one public, exact frame length.

    Every variant has the same value/ownership interface and a contiguous result.
    Chunks use bounded index views; their descriptors and contiguous output staging
    remain charged. There is no secret-dependent phase selection or allocator.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    _positive(length, "length", MAX_LENGTH)
    _positive(tile, "tile", MAX_LENGTH)
    tile = min(tile, length)
    code: list[Instruction] = []

    def add(op: str, buffer: str = "", index: int = 0, other: str = "",
            other_index: int = 0, size: int = 0, role: str = "") -> None:
        code.append(Instruction(op, buffer, index, other, other_index, size, role))

    def reserve(name: str, size: int, role: str, useful: int | None = None) -> None:
        add("reserve", name, index=size if useful is None else useful, size=size, role=role)

    def ingress(name: str, start: int, count: int) -> None:
        for index in range(count):
            add("ingress", name, index, other_index=start + index)

    def emit(name: str) -> None:
        for index in range(length):
            add("emit", name, index)
        add("retire", name)

    chunks = [(start, min(tile, length - start)) for start in range(0, length, tile)]
    if variant == "early-input-release":
        # All input chunks coexist at entry, matching the complete-frame interface.
        # Last chunk padding is charged even when its logical extent is smaller.
        for start, count in chunks:
            reserve(f"input-{start}", tile, "input", count)
            ingress(f"input-{start}", start, count)
        reserve("mapped", length, "mapped")
        for start, count in chunks:
            for index in range(count):
                add("map", f"input-{start}", index, "mapped", start + index)
                add("sum", "mapped", start + index)
            add("retire", f"input-{start}")
        reserve("result", length, "output")
        for index in range(length):
            add("xor", "mapped", index, "result", index)
        add("retire", "mapped")
        emit("result")
        return Program(variant, length, tile, tuple(code))

    reserve("input", length, "input")
    ingress("input", 0, length)
    if variant in {"lexical-cache", "phased-cache"}:
        reserve("mapped", length, "mapped")
        for index in range(length):
            add("map", "input", index, "mapped", index)
            add("sum", "mapped", index)
        if variant == "phased-cache":
            add("retire", "input")
        reserve("result", length, "output")
        for index in range(length):
            add("xor", "mapped", index, "result", index)
        for index in range(length):
            add("emit", "result", index)
        for name in (("input", "mapped", "result") if variant == "lexical-cache"
                     else ("mapped", "result")):
            add("retire", name)
    elif variant == "chunked-cache":
        for start, count in chunks:
            reserve(f"mapped-{start}", tile, "mapped", count)
            for index in range(count):
                add("map", "input", start + index, f"mapped-{start}", index)
                add("sum", f"mapped-{start}", index)
        add("retire", "input")
        reserve("result", length, "output")
        # A bounded transport stage, followed by a copy to the contiguous sink.
        reserve("stage", tile, "staging")
        for start, count in chunks:
            for index in range(count):
                add("xor", f"mapped-{start}", index, "stage", index)
                add("copy", "stage", index, "result", start + index)
            add("retire", f"mapped-{start}")
        add("retire", "stage")
        emit("result")
    elif variant == "tiled-rematerialized":
        reserve("tile", tile, "staging")
        for start, count in chunks:
            for index in range(count):
                add("map", "input", start + index, "tile", index)
                add("sum", "tile", index)
        reserve("result", length, "output")
        for start, count in chunks:
            for index in range(count):
                add("map", "input", start + index, "tile", index)
                add("xor", "tile", index, "result", start + index)
        add("retire", "tile")
        add("retire", "input")
        emit("result")
    elif variant == "fused-rematerialized":
        for index in range(length):
            add("map-sum", "input", index)
        reserve("result", length, "output")
        for index in range(length):
            add("map-xor", "input", index, "result", index)
        add("retire", "input")
        emit("result")
    else:
        for index in range(length):
            add("map", "input", index, "input", index)
            add("sum", "input", index)
        for index in range(length):
            add("xor", "input", index, "input", index)
        emit("input")
    return Program(variant, length, tile, tuple(code))


def layout(program: Program) -> dict[str, Any]:
    """Offline first fit over fixed instruction intervals; independent safety check.

    The resource remains reserved throughout its retirement scrub. Its descriptor
    and padding are one indivisible extent with its backing. Absolute tick values
    are instruction ordinals, never elapsed-time bounds or semantic revocation.
    """
    resources: list[dict[str, Any]] = []
    opened: dict[str, dict[str, Any]] = {}
    for tick, ins in enumerate(program.instructions):
        if ins.op == "reserve":
            if ins.buffer in opened or any(r["id"] == ins.buffer for r in resources):
                raise ValueError("duplicate resource identity")
            if not 0 < ins.index <= ins.size:
                raise ValueError("invalid logical or physical extent")
            padded = (ins.size + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT
            row = {"id": ins.buffer, "role": ins.role, "payload": ins.index,
                   "padding": padded - ins.index, "descriptor": DESCRIPTOR_BYTES,
                   "size": padded + DESCRIPTOR_BYTES, "start": tick,
                   "payload_end": tick + 1, "alignment": ALIGNMENT}
            opened[ins.buffer] = row
            resources.append(row)
        elif ins.op == "retire":
            if ins.buffer not in opened:
                raise ValueError("retiring a resource without authority")
            row = opened.pop(ins.buffer)
            row.update(authority_end=tick, sweep_end=tick, reuse=tick + 1)
        else:
            operands = [ins.buffer] + ([ins.other] if ins.other else [])
            for name in operands:
                if name not in opened:
                    raise ValueError(f"instruction uses inactive resource {name}")
                opened[name]["payload_end"] = tick + 1
    if opened:
        raise ValueError("program leaves owned resources open")
    placed: list[dict[str, Any]] = []
    for row in resources:
        conflicts = [prev for prev in placed if prev["reuse"] > row["start"]]
        base = WORKSPACE_BYTES
        for prev in sorted(conflicts, key=lambda r: r["base"]):
            if base + row["size"] <= prev["base"]:
                break
            base = max(base, prev["base"] + prev["size"])
        row["base"] = base
        placed.append(row)
    span = max((r["base"] + r["size"] for r in resources), default=WORKSPACE_BYTES)
    horizon = len(program.instructions)
    objects = [{key: row[key] for key in ("id", "base", "size", "payload", "alignment",
                                         "start", "payload_end", "authority_end",
                                         "sweep_end", "reuse")} | {"arena": "frame"}
               for row in resources]
    objects.append({"id": "control-workspace", "arena": "frame", "base": 0,
                    "size": WORKSPACE_BYTES, "payload": WORKSPACE_BYTES,
                    "alignment": ALIGNMENT, "start": 0, "payload_end": horizon,
                    "authority_end": horizon, "sweep_end": horizon, "reuse": horizon})
    raw = {"name": program.variant, "mode": f"exact-public-length-{program.length}",
           "provenance": "executable-host-witness",
           "arenas": [{"id": "frame", "owner": "frame-service", "capacity": span}],
           "objects": objects}
    case = sm.parse_case(raw)
    findings = sm.check_placement(case, sm.standing_placement(case))
    if findings:
        raise ValueError("invalid static layout: " + "; ".join(findings))
    snapshots: list[dict[str, Any]] = []
    times = sorted({0} | {row[key] for row in resources
                         for key in ("start", "payload_end", "authority_end", "reuse")})
    for tick in times:
        charges = dict.fromkeys(("input", "mapped", "output", "staging", "descriptors",
                                "padding", "retained", "zeroizing", "control", "idle"), 0)
        charges["control"] = WORKSPACE_BYTES if tick < horizon else 0
        for row in resources:
            if row["start"] <= tick < row["reuse"]:
                if tick >= row["authority_end"]:
                    charges["zeroizing"] += row["size"]
                elif tick >= row["payload_end"]:
                    charges["retained"] += row["size"]
                else:
                    charges[row["role"]] += row["payload"]
                    charges["descriptors"] += row["descriptor"]
                    charges["padding"] += row["padding"]
        charges["idle"] = span - sum(charges.values())
        if charges["idle"] < 0:
            raise ValueError("physical ledger does not conserve capacity")
        snapshots.append({"tick": tick, "charges": charges})
    return {"case": raw, "resources": resources, "reserved_span": span,
            "charged_peak": sm.peak_load(case, "frame"), "snapshots": snapshots,
            "placement_findings": findings, "contract_sha256": sm.contract_hash(case)}


def execute(program: Program, frame: bytes) -> dict[str, Any]:
    """Run the emitted program on its checked backing and count executed operations."""
    if type(frame) is not bytes or len(frame) != program.length:
        raise ValueError("frame must be bytes of the program's exact public length")
    plan = layout(program)
    memory = bytearray(plan["reserved_span"])
    by_id = {row["id"]: row for row in plan["resources"]}
    active: set[str] = set()
    counts: Counter[str] = Counter()
    result = bytearray()
    checksum = 0
    # Fixed workspace is reserved for scalar state, including the checksum and
    # instruction temporaries. Its entry/exit erasure is charged explicitly.
    counts["zeroization_writes"] = 2 * WORKSPACE_BYTES

    def access(name: str, index: int, value: int | None = None) -> int:
        if name not in active:
            raise ValueError("access after retirement")
        row = by_id[name]
        if not 0 <= index < row["payload"]:
            raise ValueError("out-of-bounds narrowed view")
        counts["bounds_checks"] += 1
        counts["descriptor_reads"] += DESCRIPTOR_ACCESS_BYTES
        address = int(row["base"]) + index
        if value is None:
            counts["data_reads"] += 1
            return memory[address]
        counts["data_writes"] += 1
        memory[address] = value
        return value

    def mapped(value: int) -> int:
        counts["map_evaluations"] += 1
        counts["shift_left"] += 1
        counts["add"] += 2
        counts["mask"] += 1
        return ((value << 1) + value + 1) & 255

    for ins in program.instructions:
        counts["instructions"] += 1
        if ins.op in {"reserve", "retire"}:
            row = by_id[ins.buffer]
            base, end = row["base"], row["base"] + row["size"]
            memory[base:end] = bytes(row["size"])
            counts["zeroization_writes"] += row["size"]
            if ins.op == "reserve":
                active.add(ins.buffer)
                counts["descriptor_writes"] += DESCRIPTOR_BYTES
                desc = end - DESCRIPTOR_BYTES
                memory[desc:end] = (base.to_bytes(8, "little")
                                    + row["payload"].to_bytes(8, "little")
                                    + bytes(DESCRIPTOR_BYTES - 16))
            else:
                active.remove(ins.buffer)
        elif ins.op == "ingress":
            counts["ingress_reads"] += 1
            access(ins.buffer, ins.index, frame[ins.other_index])
        elif ins.op == "emit":
            result.append(access(ins.buffer, ins.index))
            counts["egress_writes"] += 1
        elif ins.op in {"sum", "map-sum"}:
            value = access(ins.buffer, ins.index)
            if ins.op == "map-sum":
                value = mapped(value)
            checksum = (checksum + value) & 255
            counts["add"] += 1
            counts["mask"] += 1
        elif ins.op in {"map", "map-xor", "xor", "copy"}:
            value = access(ins.buffer, ins.index)
            if ins.op in {"map", "map-xor"}:
                value = mapped(value)
            if ins.op in {"xor", "map-xor"}:
                value ^= checksum
                counts["xor"] += 1
            if ins.op == "copy":
                counts["staging_copies"] += 1
            access(ins.other, ins.other_index, value)
        else:
            raise ValueError(f"unknown instruction {ins.op}")
    counts["memory_traffic_bytes"] = sum(counts[key] for key in (
        "zeroization_writes", "descriptor_reads", "descriptor_writes", "data_reads",
        "data_writes", "ingress_reads", "egress_writes"))
    counts["arithmetic_operations"] = sum(counts[key] for key in (
        "shift_left", "add", "mask", "xor"))
    return {"output": bytes(result), "counts": dict(sorted(counts.items())),
            "all_released_and_zero": not active and not any(memory)}


def equivalence_findings(program: Program, frames: list[bytes]) -> list[str]:
    """Compare outputs and erasure against a separate value specification."""
    findings: list[str] = []
    for index, frame in enumerate(frames):
        result = execute(program, frame)
        if result["output"] != reference(frame):
            findings.append(f"frame-{index}: output differs from reference")
        if not result["all_released_and_zero"]:
            findings.append(f"frame-{index}: backing survives return")
    return findings


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def transformation_report(source_revision: str = "unspecified") -> dict[str, Any]:
    """Replay bounded equivalence and emit comparable bytes/work witness receipts."""
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ValueError("source_revision must be a nonempty string")
    alphabet = (0, 1, 255)
    small = [bytes(values) for length in range(1, 5)
             for values in itertools.product(alphabet, repeat=length)]
    generated = [bytes((seed + 17 * index) & 255 for index in range(MAX_LENGTH))
                 for seed in range(256)]
    frames = small + generated
    by_length = {length: [frame for frame in frames if len(frame) == length]
                 for length in {len(frame) for frame in frames}}
    failures: list[str] = []
    checked = 0
    for variant in VARIANTS:
        for length in sorted(by_length):
            program = emit_program(variant, length)
            failures.extend(f"{variant}/{length}/{failure}" for failure in
                            equivalence_findings(program, by_length[length]))
            checked += len(by_length[length])
    measurements: list[dict[str, Any]] = []
    for length in (4, 16, MAX_LENGTH):
        for variant in VARIANTS:
            program = emit_program(variant, length)
            plan = layout(program)
            run = execute(program, bytes(range(length)))
            measurements.append({"variant": variant, "length": length,
                                 "tile": program.tile, "program_sha256": _digest(asdict(program)),
                                 "program_instruction_count": len(program.instructions),
                                 "output_equivalent": run["output"] == reference(bytes(range(length))),
                                 "layout": plan, "work": run["counts"]})
    frontier: dict[str, list[str]] = {}
    for length in (4, 16, MAX_LENGTH):
        group = [row for row in measurements if row["length"] == length]
        def costs(row: dict[str, Any]) -> tuple[int, int, int]:
            return (int(row["layout"]["reserved_span"]), int(row["work"]["arithmetic_operations"]),
                    int(row["work"]["memory_traffic_bytes"]))
        frontier[str(length)] = [row["variant"] for row in group if not any(
            all(a <= b for a, b in zip(costs(other), costs(row), strict=True))
            and costs(other) != costs(row)
            for other in group)]
    errors = list(failures)
    errors.extend(f"{row['variant']}/{row['length']}: measurement output differs"
                  for row in measurements if not row["output_equivalent"])
    return {"schema": 1, "provenance": "executable-host-witness", "errors": errors,
            "source_revision": source_revision,
            "source_hashes": {GENERATOR: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              "tools/vos/static_memory.py": hashlib.sha256(
                                  Path(sm.__file__).read_bytes()).hexdigest()},
            "settings": {"lengths": [4, 16, MAX_LENGTH], "tile_bytes": 8,
                         "descriptor_bytes": DESCRIPTOR_BYTES,
                         "descriptor_bytes_per_data_access": DESCRIPTOR_ACCESS_BYTES,
                         "control_workspace_bytes": WORKSPACE_BYTES, "alignment": ALIGNMENT,
                         "small_alphabet": list(alphabet), "small_lengths": [1, 2, 3, 4],
                         "generated_seeds": 256, "generated_stride": 17},
            "service_contract": {"input": "exclusive, disposable, exact public frame length",
                                 "output": "contiguous result equal to reference, consumed through egress",
                                 "observable": "result bytes; same input envelope per length",
                                 "overflow": "reject wrong length before allocating",
                                 "product_admission_evidence": False},
            "equivalence": {"checked_executions": checked, "input_sha256": _digest(
                [frame.hex() for frame in frames]), "failures": failures,
                "scope": "exhaustive small alphabet and deterministic generated frames; no target proof"},
            "measurements": measurements, "modeled_pareto_frontier": frontier,
            "unknown": {"target_wcet": None, "target_code_size": None,
                        "target_energy": None, "bank_traffic_and_vectorization": None,
                        "compiled_stack_and_capability_metadata": None,
                        "authority_barrier_and_dma_completion": None,
                        "original_deadline_admission": None},
            "scope": "Executable bounded service witness; no target compilation or admission claim.",
            "limitations": ["Instruction counts describe emitted abstract code, not Python allocations.",
                      "Descriptor traffic assumes memory lookup on each access; registers may differ.",
                      "Single synchronous owner; no retained external aliases or DMA are admitted.",
                      "Erasure before reuse is executable; target revocation is not proved.",
                      "All addresses are fixed before execution; no packing optimum is claimed.",
                      "Ingress source and egress consumer backing are outside this service arena.",
                      "In-place legality depends on this service's disposable-input contract."]}
