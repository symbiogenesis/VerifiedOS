# SPDX-License-Identifier: Apache-2.0
"""Finite C/reference comparison for M7.1e; no target or refinement verdict."""

import hashlib
import itertools
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from vos import env, gallina
from vos.supervisor import c_compiler

CFLAGS: Final = ("-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic")
STATES: Final = ("Free", "Writing", "Submitted", "Accepted", "Terminal", "Reclaimed")
EVENTS: Final = ("reserve", "publish", "accept", "complete", "reclaim", "malformed")
WAITS: Final = ("Finite host C/reference agreement only. The accepted M1.2f backend, "
               "M4.4 notification adapter, target memory-order refinement and composed "
               "M7.1e roster member remain open.")
SOURCES: Final = ("include/vos_copy_service.h", "src/copy_service.c", "test/host.c")


@dataclass(frozen=True)
class Config:
    capacity: int
    span: int
    batch: int
    generation: int
    payloads: tuple[int, ...]

    @property
    def maximum(self) -> int:
        return max(self.payloads)


@dataclass(frozen=True)
class Comparison:
    inputs: tuple[int, ...]
    expressions: tuple[str, ...]


def configuration(root: Path) -> Config:
    """Read build bounds from their declaration; no parallel copy of its values."""
    data = json.loads((root / "interfaces" / "ring-reference.json").read_text(encoding="utf-8"))
    worlds = [w for w in data["worlds"] if w["world"] == "ring_reference"]
    if len(worlds) != 1:
        raise ValueError("requires exactly one ring_reference declaration")
    world = worlds[0]
    ring = world["ring"]
    index = world["operation_record_fields"].index("max_payload_bytes")
    config = Config(ring["capacity"], ring["index_span"], ring["max_batch_size"],
                    ring["session_generation"], tuple(op["record"][index] for op in world["operations"]))
    values = (config.capacity, config.span, config.batch, config.generation, *config.payloads)
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError("ring fields must be natural integers")
    if not (0 < config.batch <= config.capacity < config.span <= 2**31
            and config.span % config.capacity == 0 and 0 < config.maximum <= 65536
            and config.generation < 2**32):
        raise ValueError("declaration exceeds the bounded C implementation domain")
    return config


def configuration_header(config: Config) -> str:
    values = {"CAPACITY": config.capacity, "INDEX_SPAN": config.span,
              "MAX_BATCH": config.batch, "GENERATION": config.generation,
              "MAX_PAYLOAD": config.maximum, "OPERATION_COUNT": len(config.payloads)}
    lines = ["/* Generated from interfaces/ring-reference.json. */",
             "#ifndef VOS_COPY_CONFIG_H", "#define VOS_COPY_CONFIG_H"]
    lines += [f"#define VOS_COPY_{name} {value}u" for name, value in values.items()]
    lines += ["static const unsigned vos_copy_payload_limits[VOS_COPY_OPERATION_COUNT] = {",
              "    " + ", ".join(f"{v}u" for v in config.payloads), "};", "#endif", ""]
    return "\n".join(lines)


def generated(config: Config) -> list[Comparison]:
    """Inputs surround owned bounds; all expected answers remain Gallina terms."""
    cases: list[Comparison] = []
    # Every wire base, including the full window that crosses zero.
    for base, occupancy in itertools.product(range(config.span), (0, 1, config.capacity - 1, config.capacity)):
        produced = base + occupancy
        view = f"(mk_ring_view {produced} {base})"
        cases.append(Comparison((0, produced, base), (
            f"rv_occupancy {view}", f"rv_wire {produced}", f"rv_wire {base}",
            f"rv_slot {produced}", f"rv_wire (rv_produced (rv_publish {view}))",
            f"(if Nat.ltb 0 (rv_occupancy {view}) then 1 else 0)",
            f"(match service_submit {view} with submit_enqueued => 1 | submit_would_block => 0 end)",
            f"rv_wire (rv_consumed (rv_take {view}))")))
    for base, room, count in itertools.product((0, config.span - 1), range(config.batch + 1), range(config.batch + 1)):
        produced = base + config.capacity - room
        term = f"(submit_batch {count} (mk_ring_view {produced} {base}))"
        expressions = [f"rv_wire ({produced} + enqueued_count {term})"]
        expressions += [f"batch_answer {i} {term}" for i in range(count)]
        cases.append(Comparison((1, produced, base, count), tuple(expressions)))
    for event, state, readers, valid in itertools.product(range(6), range(6), range(3), range(2)):
        term = f"spec_advance ev_{EVENTS[event]} (mk_slot state_{STATES[state]} {readers} {'true' if valid else 'false'} 7)"
        cases.append(Comparison((2, event, state, readers, valid),
                                (f"(match {term} with Some s => S (lifecycle_rank (sl_state s)) | None => 0 end)",)))
    for extent in sorted({0, 1, *config.payloads}):
        for length in sorted({0, max(0, extent - 1), extent, extent + 1}):
            term = f"copy_once {extent} (mk_buffer {length} 7) (mk_buffer {length + 1} 9)"
            cases.append(Comparison((3, extent, length),
                                    (f"(match {term} with Some r => S (cr_bytes r) | None => 0 end)",)))
    for reset, budget, base, occupancy, armed, publication in itertools.product(
            range(2), (0, 1, config.batch), (0, config.span - 1),
            (0, 1, config.batch + 1, config.capacity), range(2), range(5)):
        produced = base + occupancy
        initial = f"(mk_world (mk_ring_view {produced} {base}) {'true' if armed else 'false'} 0 {base} 0 false)"
        owner = "reset_at_the_signal" if reset == 0 else "reset_at_the_drain"
        term = f"(activation {owner} {budget} spec_consumer_chain {publication} {initial})"
        expressions = (f"rv_wire (rv_produced (w_view {term}))",
                       f"rv_wire (rv_consumed (w_view {term}))",
                       f"(if w_armed {term} then 1 else 0)", f"w_signals {term}",
                       f"rv_wire (w_seen {term})", f"w_drained {term}",
                       f"(if w_asleep {term} then 1 else 0)")
        cases.append(Comparison((4, reset, budget, produced, base, armed, base, 0, publication, 0), expressions))
    return cases


def comparison_source(cases: list[Comparison], output: str) -> str:
    rows = output.splitlines()
    if len(rows) != len(cases) or not cases:
        raise ValueError("C answer count differs from nonempty generated input set")
    lines = ["(* SPDX-License-Identifier: Apache-2.0 *)",
             "Require Import RingContract CopyRingService.",
             "Fixpoint batch_answer (i : nat) (l : list submit_result) : nat :=",
             "  match l with nil => 0 | cons x rest => match i with",
             "  | 0 => match x with submit_enqueued => 1 | submit_would_block => 0 end",
             "  | S k => batch_answer k rest end end."]
    for i, (case, row) in enumerate(zip(cases, rows, strict=True)):
        fields = row.split()
        if len(fields) != len(case.expressions):
            raise ValueError(f"wrong column count at C answer {i}")
        for j, (field, expression) in enumerate(zip(fields, case.expressions, strict=True)):
            if not field.isascii() or not field.isdecimal() or int(field) > 2**17:
                raise ValueError(f"invalid bounded natural at C answer {i} column {j}")
            lines.append(f"Example comparison_{i}_{j} : ({expression}) = {int(field)}. Proof. vm_compute; reflexivity. Qed.")
    return "\n".join(lines) + "\n"


def build_host(root: Path, work: Path, compiler: str) -> subprocess.CompletedProcess[str]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "copy_service_config.h").write_text(configuration_header(configuration(root)), encoding="utf-8", newline="")
    return subprocess.run([compiler, *CFLAGS, "-I", str(work), "-I", str(root / "copy-service" / "include"),
                           str(root / "copy-service" / "src" / "copy_service.c"),
                           str(root / "copy-service" / "test" / "host.c"), "-o", str(work / "copy-host")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path, work: Path) -> tuple[int, list[str]]:
    work.mkdir(parents=True, exist_ok=True)
    logs = env.log_root() / env.lane_of(root) / "copy-service"
    logs.mkdir(parents=True, exist_ok=True)
    report_path = work / "report.json"
    report_path.write_text('{"comparison":"incomplete","milestone_acceptance":"open"}\n', encoding="utf-8")
    compiler, found = c_compiler(), gallina.prover(env.ROCQ_SWITCH)
    if compiler is None or found is None:
        return 1, [f"FAIL requires C compiler and locked switch {env.ROCQ_SWITCH}", WAITS]
    identities = [root / "proofs" / name for name in ("RingContract.v", "CopyRingService.v")]
    identities += [root / "copy-service" / name for name in SOURCES]
    identities += [root / "tools" / "vos" / "copy_service.py", root / "interfaces" / "ring-reference.json"]
    before = {p.relative_to(root).as_posix(): _digest(p) for p in identities}
    tools_before = {p: _digest(Path(p)) for p in (compiler, found.argv[0])}
    built = build_host(root, work, compiler)
    (logs / "compile.log").write_text(built.stdout + built.stderr, encoding="utf-8")
    if built.returncode:
        return 1, ["FAIL C compile", built.stderr, WAITS]
    binary = work / "copy-host"
    controls = subprocess.run([str(binary), "controls"], capture_output=True, text=True, timeout=60, check=False)
    (logs / "controls.log").write_text(controls.stdout + controls.stderr, encoding="utf-8")
    if controls.returncode:
        return 1, ["FAIL fixed consumer controls", controls.stderr, WAITS]
    cases = generated(configuration(root))
    inputs = "\n".join(" ".join(map(str, case.inputs)) for case in cases) + "\n"
    (work / "inputs.txt").write_text(inputs, encoding="utf-8")
    answers = subprocess.run([str(binary)], input=inputs, capture_output=True, text=True, timeout=60, check=False)
    (work / "answers.txt").write_text(answers.stdout, encoding="utf-8")
    if answers.returncode:
        return 1, ["FAIL C input harness", answers.stderr, WAITS]
    try:
        source = comparison_source(cases, answers.stdout)
    except ValueError as error:
        return 1, [f"FAIL {error}", WAITS]
    (work / "CopyServiceComparison.v").write_text(source, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="comparison-", dir=work) as directory:
        scratch = Path(directory)
        (scratch / "proofs").mkdir()
        (scratch / "harness").mkdir()
        references = [scratch / "proofs" / name for name in ("RingContract.v", "CopyRingService.v")]
        for path in references:
            shutil.copyfile(root / "proofs" / path.name, path)
        harness = scratch / "harness" / "CopyServiceComparison.v"
        harness.write_text(source, encoding="utf-8")
        for artifact in [*references, harness]:
            compiled = gallina.compile_one(found, scratch, artifact, timeout=600)
            (logs / f"{artifact.stem}.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
            if compiled.returncode:
                return 1, [f"FAIL Gallina comparison at {artifact.name}", compiled.stderr, WAITS]
        # Corrupt an actual C answer. A passing comparison must reject it.
        corrupt = answers.stdout.splitlines()
        fields = corrupt[0].split()
        fields[0] = str(int(fields[0]) + 1)
        corrupt[0] = " ".join(fields)
        negative = scratch / "harness" / "CopyServiceNegative.v"
        negative.write_text(comparison_source(cases[:1], corrupt[0] + "\n"), encoding="utf-8")
        refused = gallina.compile_one(found, scratch, negative)
        (logs / "negative.log").write_text(refused.stdout + refused.stderr, encoding="utf-8")
        if refused.returncode == 0 or "Unable to unify" not in refused.stderr:
            return 1, ["FAIL reference negative control was not a comparison refusal", refused.stderr, WAITS]
    if before != {p.relative_to(root).as_posix(): _digest(p) for p in identities} or tools_before != {p: _digest(Path(p)) for p in tools_before}:
        return 1, ["FAIL source/tool bytes changed during comparison", WAITS]
    report = {"schema": 1, "comparison": "passed", "milestone_acceptance": "open",
              "cases": len(cases), "equalities": sum(len(c.expressions) for c in cases),
              "negative_control": "wrong C answer refused by reference conversion",
              "sources": before, "tool_sha256": tools_before, "prover": gallina.version(found),
              "cflags": CFLAGS, "binary_sha256": _digest(binary),
              "config_sha256": _digest(work / "copy_service_config.h"),
              "answers_sha256": _digest(work / "answers.txt"),
              "comparison_sha256": _digest(work / "CopyServiceComparison.v"), "limits": WAITS}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0, [controls.stderr.strip(), f"ok {len(cases)} generated C answers, {report['equalities']} Gallina equalities",
               "ok wrong-answer negative control refused", f"report: {report_path}", f"logs: {logs}", WAITS]
