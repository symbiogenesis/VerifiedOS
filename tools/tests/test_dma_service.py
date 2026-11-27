# SPDX-License-Identifier: Apache-2.0
"""Dynamic ring_dma config check, pure-Python oracle, and native C17 ASan/UBSan + mutation controls."""

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos import env, gallina, proof_staging, ring as ring_owner, toolenv
from vos.corpus import find_root
from vos.jsonutil import unique_object

HEADER = "dma-service/include/vos_dma_service.h"
SOURCE = "dma-service/src/dma_service.c"
FIXTURE = "dma-service/test/test_dma_service.c"


@dataclass(frozen=True)
class DmaOpConfig:
    name: str
    max_payload_bytes: int
    max_segment_count: int
    cancellable: bool
    cancel_points: int
    commit_index: int
    quiescence_bound: int
    held_capabilities: int
    extent_validated_bytes: int
    descriptor_validation_cost: int
    segment_validation_cost: int
    validation_cost: int
    max_to_terminal: int


@dataclass(frozen=True)
class DmaConfig:
    capacity: int
    index_span: int
    max_batch_size: int
    initial_generation: int
    max_segments: int
    segment_max_bytes: int
    slot_budget: int
    directions: tuple[str, ...]
    permissions: tuple[str, ...]
    direction_permission: tuple[str, ...]
    ops: tuple[DmaOpConfig, ...]


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    return unique_object(pairs, duplicate_error=lambda key: ValueError(f"duplicate JSON key: {key}"))


def _as_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _load_dma_config(root: Path) -> DmaConfig:
    path = root / ring_owner.DECLARATION
    raw = path.read_bytes()
    parsed = cast(dict[str, object], json.loads(raw, object_pairs_hook=_unique))
    if path.read_bytes() != raw:
        raise ValueError("ring declaration changed while reading")
    worlds_obj = parsed.get("worlds")
    ensure(isinstance(worlds_obj, list), "declaration missing worlds list")
    worlds = cast(list[dict[str, object]], worlds_obj)
    dma_worlds = [w for w in worlds if w.get("world") == "ring_dma"]
    ensure(len(dma_worlds) == 1, "declaration must contain exactly one ring_dma world")
    world = dma_worlds[0]
    ring_tbl = cast(dict[str, object], world["ring"])
    fields = cast(list[str], world["operation_record_fields"])
    idx_val_cost = fields.index("validation_cost")
    idx_max_payload = fields.index("max_payload_bytes")
    idx_max_segs = fields.index("max_segment_count")

    dma_meta = cast(dict[str, object], world["dma"])
    directions = tuple(cast(list[str], world["directions"]))
    permissions = tuple(cast(list[str], dma_meta["permissions"]))
    dir_perm = tuple(cast(list[str], dma_meta["direction_permission"]))

    op_configs: list[DmaOpConfig] = []
    for op_raw in cast(list[dict[str, object]], world["operations"]):
        rec = cast(list[int], op_raw["record"])
        cancel_raw = cast(dict[str, object] | None, op_raw["cancellation"])
        op_dma = cast(dict[str, object], op_raw["dma"])
        cancellable = cancel_raw is not None
        op_configs.append(
            DmaOpConfig(
                name=str(op_raw["name"]),
                max_payload_bytes=_as_int(rec[idx_max_payload], "max_payload_bytes"),
                max_segment_count=_as_int(rec[idx_max_segs], "max_segment_count"),
                cancellable=cancellable,
                cancel_points=_as_int(cancel_raw["points"], "cancel.points") if cancel_raw else 0,
                commit_index=_as_int(cancel_raw["commit_index"], "cancel.commit_index") if cancel_raw else 0,
                quiescence_bound=_as_int(cancel_raw["quiescence_bound"], "cancel.quiescence_bound") if cancel_raw else 0,
                held_capabilities=_as_int(op_dma["held_capabilities"], "dma.held_capabilities"),
                extent_validated_bytes=_as_int(op_dma["extent_validated_bytes"], "dma.extent_validated_bytes"),
                descriptor_validation_cost=_as_int(op_dma["descriptor_validation_cost"], "dma.descriptor_validation_cost"),
                segment_validation_cost=_as_int(op_dma["segment_validation_cost"], "dma.segment_validation_cost"),
                validation_cost=_as_int(rec[idx_val_cost], "validation_cost"),
                max_to_terminal=_as_int(cancel_raw["max_to_terminal"], "cancel.max_to_terminal") if cancel_raw else 0,
            ),
        )

    cfg = DmaConfig(
        capacity=_as_int(ring_tbl["capacity"], "capacity"),
        index_span=_as_int(ring_tbl["index_span"], "index_span"),
        max_batch_size=_as_int(ring_tbl["max_batch_size"], "max_batch_size"),
        initial_generation=_as_int(ring_tbl["session_generation"], "session_generation"),
        max_segments=_as_int(ring_tbl["max_segments"], "max_segments"),
        segment_max_bytes=_as_int(ring_tbl["segment_max_bytes"], "segment_max_bytes"),
        slot_budget=_as_int(ring_tbl["slot_budget"], "slot_budget"),
        directions=directions,
        permissions=permissions,
        direction_permission=dir_perm,
        ops=tuple(op_configs),
    )
    ensure(0 < cfg.max_batch_size <= cfg.capacity < cfg.index_span
           and cfg.index_span % cfg.capacity == 0
           and 2 * cfg.capacity <= cfg.index_span
           and 0 < cfg.initial_generation < 2**32
           and cfg.max_segments > 0 and cfg.segment_max_bytes > 0,
           "ring_dma declaration violates bounded ring invariants")
    return cfg


def _emit_config_header(cfg: DmaConfig) -> str:
    lines = [
        "// SPDX-License-Identifier: Apache-2.0",
        "/* Generated dynamically from interfaces/ring-reference.json (ring_dma world). */",
        "#ifndef VOS_DMA_SERVICE_CONFIG_H",
        "#define VOS_DMA_SERVICE_CONFIG_H",
        "",
        "#include \"vos_dma_service.h\"",
        "",
        f"#define VOS_DMA_CAPACITY {cfg.capacity}u",
        f"#define VOS_DMA_INDEX_SPAN {cfg.index_span}u",
        f"#define VOS_DMA_MAX_BATCH {cfg.max_batch_size}u",
        f"#define VOS_DMA_GENERATION {cfg.initial_generation}u",
        f"#define VOS_DMA_MAX_SEGMENTS {cfg.max_segments}u",
        f"#define VOS_DMA_SEGMENT_MAX_BYTES {cfg.segment_max_bytes}u",
        f"#define VOS_DMA_SLOT_BUDGET {cfg.slot_budget}u",
        f"#define VOS_DMA_OP_COUNT {len(cfg.ops)}u",
    ]
    for i, op in enumerate(cfg.ops):
        lines.append(f"#define VOS_DMA_OP_{op.name.upper()} {i}u")
    lines += [
        "",
        "static inline vos_dma_config vos_dma_reference_config(void)",
        "{",
        f"    static const vos_dma_op_spec ops[{len(cfg.ops)}] = {{",
    ]
    for op in cfg.ops:
        lines.append(
            "        { "
            f".max_payload_bytes = {op.max_payload_bytes}u, "
            f".max_segment_count = {op.max_segment_count}u, "
            f".cancellable = {1 if op.cancellable else 0}u, "
            f".cancel_points = {op.cancel_points}u, "
            f".commit_index = {op.commit_index}u, "
            f".quiescence_bound = {op.quiescence_bound}u, "
            f".held_capabilities = {op.held_capabilities}u, "
            f".extent_validated_bytes = {op.extent_validated_bytes}u, "
            f".descriptor_validation_cost = {op.descriptor_validation_cost}u, "
            f".segment_validation_cost = {op.segment_validation_cost}u, "
            f".validation_cost = {op.validation_cost}u, "
            f".max_to_terminal = {op.max_to_terminal}u "
            "},"
        )
    lines += [
        "    };",
        "    const vos_dma_config cfg = {",
        "        .capacity = VOS_DMA_CAPACITY,",
        "        .index_span = VOS_DMA_INDEX_SPAN,",
        "        .max_batch_size = VOS_DMA_MAX_BATCH,",
        "        .initial_generation = VOS_DMA_GENERATION,",
        "        .max_segments = VOS_DMA_MAX_SEGMENTS,",
        "        .segment_max_bytes = VOS_DMA_SEGMENT_MAX_BYTES,",
        "        .slot_budget = VOS_DMA_SLOT_BUDGET,",
        "        .ops = ops,",
        "        .op_count = VOS_DMA_OP_COUNT",
        "    };",
        "    return cfg;",
        "}",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def dynamic_declaration_and_oracle() -> None:
    """Verify single-owner ring_dma parsing, duplicate-key refusal, and DMA invariants."""
    root = find_root()
    cfg = _load_dma_config(root)
    ensure(cfg.directions == ("to_server", "to_client"), "unexpected ring_dma directions")
    ensure(cfg.permissions == ("load", "store"), "unexpected ring_dma permissions")
    ensure(cfg.direction_permission == ("load", "store"), "unexpected direction_permission map")
    for op in cfg.ops:
        ensure(op.extent_validated_bytes == op.max_payload_bytes,
               f"{op.name}: extent_validated_bytes != max_payload_bytes")
        ensure(op.max_segment_count <= cfg.max_segments,
               f"{op.name}: max_segment_count exceeds ring max_segments")
        if op.cancellable:
            ensure(0 < op.commit_index <= op.cancel_points,
                   f"{op.name}: invalid commit_index vs cancel_points")
            ensure(op.quiescence_bound > 0, f"{op.name}: missing quiescence_bound")
    header = _emit_config_header(cfg)
    ensure(f"#define VOS_DMA_CAPACITY {cfg.capacity}u" in header, "missing capacity macro")
    ensure(f"#define VOS_DMA_MAX_SEGMENTS {cfg.max_segments}u" in header, "missing max_segments macro")

    try:
        json.loads('{"worlds":[],"worlds":[]}', object_pairs_hook=_unique)
    except ValueError as err:
        ensure("duplicate" in str(err), "duplicate key error unexpected")
    else:
        raise AssertionError("duplicate JSON keys accepted")


def source_discipline_check() -> None:
    """Verify SPDX headers, GC-free C17 rules, and zero duplicated ring_dma bounds."""
    root = find_root()
    cfg = _load_dma_config(root)
    for rel in (HEADER, SOURCE, FIXTURE):
        text = (root / rel).read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"{rel}: missing // SPDX-License-Identifier: Apache-2.0 header")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"{rel}: forbidden heap allocator {forbidden}")
    # Header and source must not duplicate ring_dma numeric bounds from ring-reference.json.
    for rel in (HEADER, SOURCE):
        text = (root / rel).read_text(encoding="utf-8")
        for num in (cfg.segment_max_bytes, cfg.slot_budget,
                    *(op.max_payload_bytes for op in cfg.ops if op.max_payload_bytes > 0)):
            ensure(str(num) not in text,
                   f"{rel}: duplicates ring_dma bound {num} owned by ring-reference.json")


def _variants(source: str) -> list[tuple[str, str, str]]:
    def changed(before: str, after: str) -> str:
        ensure(source.count(before) == 1, f"dma mutation anchor must be unique: {before!r}")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("omitted-segment-check-max-bytes",
         changed("    if (seg->length > ring->config->segment_max_bytes) {\n        return 0;\n    }",
                 "    (void)0;"),
         "omitted segment check"),
        ("omitted-segment-check-cap-bounds",
         changed("    if (seg->offset > cap->capability_bytes\n"
                 "        || seg->length > (cap->capability_bytes - seg->offset)) {\n"
                 "        return 0;\n"
                 "    }",
                 "    (void)0;"),
         "omitted segment check"),
        ("direction-mismatch-accepted",
         changed("int vos_dma_direction_authorized(vos_dma_perm granted, vos_dma_direction dir)\n"
                 "{\n"
                 "    return granted == vos_dma_direction_permission(dir);\n"
                 "}",
                 "int vos_dma_direction_authorized(vos_dma_perm granted, vos_dma_direction dir)\n"
                 "{\n"
                 "    (void)granted;\n"
                 "    (void)dir;\n"
                 "    return 1;\n"
                 "}"),
         "direction mismatch"),
        ("post-commit-cancel-accepted",
         changed("        if (position < spec->commit_index) {\n"
                 "            slot->state = VOS_DMA_TERMINAL;",
                 "        if (position <= spec->commit_index) {\n"
                 "            slot->state = VOS_DMA_TERMINAL;"),
         "post-commit cancel"),
        ("missing-quiescence-fail-stop-reset",
         changed("    if (dma_quiesced == 0U || (has_active != 0U && quiescence_elapsed > max_quiesce)) {\n"
                 "        ring->fail_stopped = 1U;\n"
                 "        release_all_capabilities(ring);\n"
                 "        return 0;\n"
                 "    }",
                 "    (void)dma_quiesced;\n"
                 "    (void)quiescence_elapsed;\n"
                 "    (void)has_active;\n"
                 "    (void)max_quiesce;"),
         "missing quiescence fail-stop"),
        ("missing-quiescence-fail-stop-enforce",
         changed("    if (dma_quiesced == 0U || quiescence_elapsed > bound) {\n"
                 "        ring->fail_stopped = 1U;\n"
                 "        release_all_capabilities(ring);\n"
                 "        return VOS_DMA_STATUS_DEVICE_FAULT;\n"
                 "    }",
                 "    (void)dma_quiesced;\n"
                 "    (void)quiescence_elapsed;\n"
                 "    (void)bound;"),
         "missing quiescence fail-stop"),
        ("retained-capability-after-completion",
         changed("    slot->state = VOS_DMA_TERMINAL;\n"
                 "    slot->completion_status = status;\n"
                 "    slot->held_capabilities = 0U;",
                 "    slot->state = VOS_DMA_TERMINAL;\n"
                 "    slot->completion_status = status;"),
         "retained capability after completion"),
        ("stale-generation-accepted",
         changed("    if (desc->generation != ring->generation || ring->generation == 0U) {\n"
                 "        return VOS_DMA_STATUS_REFUSED;\n"
                 "    }",
                 "    (void)0;"),
         "stale generation"),
        ("duplicate-live-request-accepted",
         changed("    if (duplicate_live_request(ring, desc->request_id)) {\n"
                 "        return VOS_DMA_STATUS_REFUSED;\n"
                 "    }",
                 "    (void)duplicate_live_request(ring, desc->request_id);"),
         "duplicate live request"),
        ("non-cancellable-op-canceled",
         changed("    if (spec->cancellable == 0U) {\n        return VOS_DMA_NOT_LIVE;\n    }",
                 "    (void)0;"),
         "non-cancellable op"),
    ]


def _supports_asan_ubsan(compiler: str, scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_exe = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    compiled = subprocess.run(
        [compiler, "-std=c17", "-fsanitize=address,undefined", str(probe_c), "-o", str(probe_exe)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if compiled.returncode != 0:
        return False
    ran = subprocess.run([str(probe_exe)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _rocq_dma_comparison(root: Path, work: Path, cfg: DmaConfig) -> None:
    found = gallina.prover(env.ROCQ_SWITCH)
    if found is None:
        return
    with tempfile.TemporaryDirectory(prefix="dma-rocq-", dir=work) as td:
        scratch = Path(td)
        (scratch / "proofs").mkdir()
        (scratch / "harness").mkdir()
        staged = proof_staging.stage(root, scratch / "proofs", ("RingContract.v",))
        op_checks = [
            f"  Nat.eqb (RingDma.rec_max_payload_bytes (RingDma.op_declared_record RingDma.op_{op.name})) {op.max_payload_bytes} = true /\\\n"
            f"  Nat.eqb (RingDma.rec_max_segment_count (RingDma.op_declared_record RingDma.op_{op.name})) {op.max_segment_count} = true /\\\n"
            f"  Nat.eqb (RingDma.op_commit_index RingDma.op_{op.name}) {op.commit_index} = true /\\\n"
            f"  Nat.eqb (RingDma.op_quiescence_bound RingDma.op_{op.name}) {op.quiescence_bound} = true /\\\n"
            f"  Nat.eqb (RingDma.op_held_capabilities RingDma.op_{op.name}) {op.held_capabilities} = true"
            for op in cfg.ops
        ]
        comp_v = (
            "(* SPDX-License-Identifier: Apache-2.0 *)\n"
            "Require Import RingContract.\n"
            "Example dma_config_matches_ring_contract :\n"
            f"  Nat.eqb RingDma.ring_capacity {cfg.capacity} = true /\\\n"
            f"  Nat.eqb RingDma.ring_max_segments {cfg.max_segments} = true /\\\n"
            f"  Nat.eqb RingDma.ring_segment_max_bytes {cfg.segment_max_bytes} = true /\\\n"
            + " /\\\n".join(op_checks)
            + ".\nProof. vm_compute; repeat split; reflexivity. Qed.\n"
        )
        harness_v = scratch / "harness" / "DmaConfigComparison.v"
        harness_v.write_text(comp_v, encoding="utf-8", newline="\n")
        for artifact in (*staged.sources, harness_v):
            res = gallina.compile_one(found, scratch, artifact, timeout=120)
            ensure(res.returncode == 0, f"Rocq DMA comparison failed at {artifact.name}: {res.stderr}")
        staged.validate(root)


def native_dma_controls() -> None:
    """Emit build-lane dma_service_config.h, compile ASan/UBSan C17, kill mutants, and verify RingDma."""
    candidates = [path for name in ("clang", "cc", "gcc") if (path := shutil.which(name)) is not None]
    ensure(bool(candidates), "native dma-service controls require clang, cc, or gcc")
    root = find_root()
    cfg = _load_dma_config(root)
    work = toolenv.environment(root, sys.platform).parent / "dma-service-tests"
    work.mkdir(parents=True, exist_ok=True)
    source = (root / SOURCE).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="dma-", dir=work) as directory:
        scratch = Path(directory)
        (scratch / "dma_service_config.h").write_text(
            _emit_config_header(cfg), encoding="utf-8", newline="\n",
        )
        san_compiler = next((c for c in candidates if _supports_asan_ubsan(c, scratch)), None)
        ensure(san_compiler is not None, "native dma-service controls require an ASan/UBSan C17 compiler")
        if san_compiler is None:
            return
        clang_path = shutil.which("clang")
        if clang_path is not None and clang_path != san_compiler:
            clang_exe = scratch / "pristine-clang"
            clang_build = subprocess.run(
                [
                    clang_path, "-std=c17", "-O1", "-Wall", "-Wextra",
                    "-Wstrict-prototypes", "-Werror", "-pedantic",
                    "-I", str(scratch), "-I", str(root / "dma-service" / "include"),
                    str(root / SOURCE), str(root / FIXTURE),
                    "-o", str(clang_exe),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ensure(clang_build.returncode == 0, f"clang strict C17 compile failed: {clang_build.stderr}")
            clang_run = subprocess.run([str(clang_exe)], capture_output=True, text=True, timeout=30, check=False)
            ensure(clang_run.returncode == 0 and "ok dma-service C controls" in clang_run.stderr,
                   f"clang pristine run failed: {clang_run.stderr}")
        for name, candidate, expected in _variants(source):
            c_path = scratch / f"{name}.c"
            c_path.write_text(candidate, encoding="utf-8", newline="\n")
            exe_path = scratch / name
            compiled = subprocess.run(
                [
                    san_compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                    "-Wstrict-prototypes", "-Werror", "-pedantic",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(scratch), "-I", str(root / "dma-service" / "include"),
                    str(c_path), str(root / FIXTURE),
                    "-o", str(exe_path),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ensure(compiled.returncode == 0,
                   f"{name}: stillborn compilation is not an executed rejection: {compiled.stderr}")
            result = subprocess.run(
                [str(exe_path)], capture_output=True, text=True, timeout=30, check=False,
            )
            if name == "pristine":
                ensure(result.returncode == 0, f"pristine dma-service C failed: {result.stderr}")
                ensure("ok dma-service C controls" in result.stderr,
                       "pristine dma-service controls did not print success verdict")
            else:
                ensure(result.returncode != 0 and expected in result.stderr,
                       f"{name}: mutant survived or missed oracle ({expected!r}): {result.stderr}")
        _rocq_dma_comparison(root, scratch, cfg)


def cases() -> list[Case]:
    return [
        Case("dma-service ring_dma dynamic declaration and invariants", dynamic_declaration_and_oracle),
        Case("dma-service C17 SPDX, GC-free and single-owner source discipline", source_discipline_check),
        Case("dma-service native C17 ASan/UBSan, mutation kills and RingDma check",
             native_dma_controls, lane="guest"),
    ]
