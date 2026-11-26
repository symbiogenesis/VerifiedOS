# SPDX-License-Identifier: Apache-2.0
"""Run and validate HoldFast's purecap Q25bb copy client against frozen 498127d6 copy-service."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from vos import (  # noqa: E402
    asm,
    compiler_diff,
    compiler_provenance,
    copy_envelope,
    copy_package,
    copy_service,
    copy_target,
    image,
    trace,
)

FROZEN_SOURCE_REVISION: Final = "498127d6be3d1a70581ba4a9cc025c2d923e66f7"
FROZEN_SOURCE_SHA256: Final = "e6991359da24d4aaf459fb262ebbd906b2bb858ee61538337df88ec649945205"
FROZEN_MEMBERS: Final[dict[str, tuple[int, str]]] = {
    "compiled C": (4808, "a4d9ebf4439c5237ef4aaf8e8030f589b030bcad488701a036b7d2aacb91ee3a"),
    "src/atomic_target.s": (532, "80411cc51436678d7d3c514effc3230b82f247c92a1b74ec26388a100327e46e"),
    "src/notification_target.s": (
        96,
        "702fa545fd8ef32131913841d6ad19455dec63a406ae8cec8406b6890802d322",
    ),
}
COMPILER_SHA256: Final = "3dae6ac7bd5a074053130fdcaaab84c42030bdc24be9fff6a4b244db272252f8"
COMPCERT_INI_SHA256: Final = "e0efcb8f02d749b406ed243e21408307f2189af136ae562a48b0d2044581550f"
RING_BYTES: Final = copy_target.RING_BYTES
DATA_BASE: Final = 0x80200000

TRIAL_PASS: Final = 0
TRIAL_EMPTY: Final = 2
TRIAL_TOO_SMALL: Final = 6
TRIAL_SNAPSHOT: Final = 7
TRIAL_SUFFIX: Final = 8
TRIAL_PAYLOAD_LIMIT: Final = 14
CHERI_CAP_BOUNDS_TRAP_CODE: Final = compiler_diff.TRAP_BASE + 28
CHERI_CAP_BOUNDS_CAUSE: Final = 28

NEGATIVE_CONTROL_SPECS: Final[dict[str, tuple[str, tuple[int, ...], str]]] = {
    "mutated-payload-limit": ("fail", (TRIAL_PAYLOAD_LIMIT,), "c-mutation"),
    "mutated-snapshot-byte": ("fail", (TRIAL_SNAPSHOT,), "c-mutation"),
    "mutated-suffix-clobber": ("fail", (TRIAL_SUFFIX,), "c-mutation"),
    "mutated-refusal-output": ("fail", (TRIAL_EMPTY, TRIAL_TOO_SMALL), "c-mutation"),
    "mutated-narrow-arena-cap": (
        "trap",
        (CHERI_CAP_BOUNDS_TRAP_CODE,),
        "capability-bounds-narrowing",
    ),
}

NON_ACCEPTANCE_FLAGS: Final[dict[str, object]] = {
    "qualified_producer": False,
    "installed_entry": None,
    "production_admission": False,
    "trial_acceptance": False,
}

_STUB_SYMBOLS: Final = frozenset({
    "vos_copy_init_generation",
    "vos_copy_submit",
    "vos_copy_take",
})
_LOCAL_LABEL_RE: Final = re.compile(r"(?<![A-Za-z0-9_.$])\.L(\d+)\b")
_PAYLOAD_LIMIT_SYM_RE: Final = re.compile(r"\bvos_copy_payload_limit\b")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def arena_bytes_for(max_payload: int) -> int:
    """Return `HOLDFAST_COPY_TRIAL_ARENA_BYTES` for `VOS_COPY_MAX_PAYLOAD = max_payload`."""
    _require(max_payload > 0, "max_payload must be positive")
    view_bytes = max_payload + 1
    return 2 * view_bytes + 3


def power_of_two_ceil(size: int) -> int:
    """Return the smallest exact power of two >= `size`."""
    _require(size > 0, "size must be positive")
    return 1 << (size - 1).bit_length()


def entry_wrapper(arena_bytes: int, *, narrow_arena_by: int = 0) -> str:
    """Emit the purecap `main` entry wrapper constructing ring and arena capabilities."""
    _require(0 <= narrow_arena_by < arena_bytes, "invalid arena narrowing offset")
    arena_extent = power_of_two_ceil(arena_bytes)
    lines = [
        ".text",
        "main:",
        "    cmove c5, c2",
        "    cincoffsetimm c2, c2, -16",
        "    sc c1, 0(c2)",
        "    sc c5, 8(c2)",
        "    call vos_copy_target_layout",
        "    li x5, 1",
        "    bne x10, x5, q25bb_layout_fail",
        "    li x31, q25bb_ring",
        "    csetaddr c10, c4, x31",
        f"    li x31, {RING_BYTES}",
        "    csetbounds c10, c10, x31",
        "    li x31, q25bb_arena",
        "    csetaddr c11, c4, x31",
        f"    li x31, {arena_extent}",
        "    csetbounds c11, c11, x31",
    ]
    if narrow_arena_by > 0:
        # Advance the cursor inside the exact power-of-two capability so the accessible
        # tail equals `arena_bytes - narrow_arena_by` bytes and faults at the upper edge.
        narrow_offset = arena_extent - (arena_bytes - narrow_arena_by)
        _require(0 < narrow_offset < arena_extent, "narrowing does not fit inside arena extent")
        lines.extend([
            f"    li x31, q25bb_arena + {narrow_offset}",
            "    csetaddr c11, c11, x31",
        ])
    lines.extend([
        "    call holdfast_copy_trial",
        "    j q25bb_return",
        "q25bb_layout_fail:",
        "    li x10, 1",
        "q25bb_return:",
        "    lc c1, 0(c2)",
        "    lc c2, 8(c2)",
        "    ret",
        ".data",
        f"    .balign {RING_BYTES}",
        "q25bb_ring:",
        f"    .space {RING_BYTES}",
        f"    .balign {arena_extent}",
        "q25bb_arena:",
        f"    .space {arena_extent}",
    ])
    return "\n".join(lines) + "\n"


def _client_unit_source() -> str:
    """Closed-TU C wrapper supplying ABI declarations for external atomic entries."""
    return (
        '#define VOS_COPY_TARGET\n'
        '#include "q25bb-copy-client.h"\n'
        '#include "q25bb-copy-client.c"\n'
        "int vos_copy_init_generation(vos_copy_ring *ring, uint32_t generation)\n"
        "{\n"
        "    (void)ring;\n"
        "    (void)generation;\n"
        "    return 0;\n"
        "}\n"
        "int vos_copy_submit(vos_copy_ring *ring, uint32_t generation, uint32_t request,\n"
        "                    uint32_t operation, const uint8_t *source,\n"
        "                    size_t extent, size_t length, uint32_t *signal)\n"
        "{\n"
        "    (void)ring;\n"
        "    (void)generation;\n"
        "    (void)request;\n"
        "    (void)operation;\n"
        "    (void)source;\n"
        "    (void)extent;\n"
        "    (void)length;\n"
        "    (void)signal;\n"
        "    return 0;\n"
        "}\n"
        "int vos_copy_take(vos_copy_ring *ring, uint8_t *destination, size_t capacity,\n"
        "                  size_t *length, uint32_t *request)\n"
        "{\n"
        "    (void)ring;\n"
        "    (void)destination;\n"
        "    (void)capacity;\n"
        "    (void)length;\n"
        "    (void)request;\n"
        "    return 0;\n"
        "}\n"
    )


def prepare_client_assembly(raw_client_s: str) -> str:
    """Strip external ABI stub bodies and scope local labels/helpers in compiled client assembly."""
    normalized = compiler_diff.normalize(raw_client_s)
    lines = normalized.splitlines()
    blocks: list[tuple[str | None, list[str]]] = []
    current_sym: str | None = None
    current_lines: list[str] = []

    idx = 0
    while idx < len(lines):
        if (
            lines[idx].strip() == ".text"
            and idx + 2 < len(lines)
            and lines[idx + 1].strip().startswith(".globl ")
            and lines[idx + 2].strip().endswith(":")
        ):
            sym = lines[idx + 1].strip().split(None, 1)[1]
            label = lines[idx + 2].strip()[:-1]
            _require(sym == label, f"mismatched function block header: {sym} vs {label}")
            if current_lines or current_sym is not None:
                blocks.append((current_sym, current_lines))
            current_sym = sym
            current_lines = [lines[idx], lines[idx + 1], lines[idx + 2]]
            idx += 3
            continue
        current_lines.append(lines[idx])
        idx += 1
    if current_lines or current_sym is not None:
        blocks.append((current_sym, current_lines))

    seen_stubs: set[str] = set()
    kept_blocks: list[str] = []
    seen_entry = False
    for sym, block_lines in blocks:
        if sym in _STUB_SYMBOLS:
            seen_stubs.add(sym)
            continue
        if sym == "holdfast_copy_trial":
            seen_entry = True
        kept_blocks.append("\n".join(block_lines))

    _require(seen_stubs == _STUB_SYMBOLS, f"missing expected ABI stubs in client stream: {seen_stubs}")
    _require(seen_entry, "client stream missing holdfast_copy_trial")

    scoped = "\n".join(kept_blocks)
    if not scoped.endswith("\n"):
        scoped += "\n"
    scoped = _PAYLOAD_LIMIT_SYM_RE.sub("__q25bb_client_vos_copy_payload_limit", scoped)
    return _LOCAL_LABEL_RE.sub(r".L__q25bb_client_\1", scoped)


def _compile_package_unit(
    compiler: Path, config_path: Path, prepared: Path, recipe: Mapping[str, object], out_s: Path
) -> str:
    compiler_args = cast(list[str], recipe["compiler_arguments"])
    include_dirs = cast(list[str], recipe["include_directories"])
    translation_unit = cast(str, recipe["translation_unit"])
    argv = [
        str(compiler),
        "-conf",
        str(config_path),
        *compiler_args,
        *["-I" + d for d in include_dirs],
        translation_unit,
        "-o",
        str(out_s),
    ]
    done = subprocess.run(argv, cwd=prepared, capture_output=True, text=True, timeout=180, check=False)
    _require(
        done.returncode == 0 and out_s.is_file(),
        f"package_unit.c compilation failed: {(done.stderr + done.stdout).strip()}",
    )
    return compiler_diff.normalize(out_s.read_text(encoding="utf-8"))


def _compile_client_unit(
    compiler: Path,
    config_path: Path,
    prepared: Path,
    recipe: Mapping[str, object],
    client_c: Path,
    client_h: Path,
    scratch: Path,
) -> str:
    scratch.mkdir(parents=True, exist_ok=True)
    staged_c = scratch / "q25bb-copy-client.c"
    staged_h = scratch / "q25bb-copy-client.h"
    staged_c.write_bytes(client_c.read_bytes())
    staged_h.write_bytes(client_h.read_bytes())
    unit_c = scratch / "client_unit.c"
    unit_c.write_text(_client_unit_source(), encoding="utf-8")
    out_s = scratch / "client_unit.s"
    compiler_args = cast(list[str], recipe["compiler_arguments"])
    include_dirs = cast(list[str], recipe["include_directories"])
    argv = [
        str(compiler),
        "-conf",
        str(config_path),
        *compiler_args,
        "-DVOS_COPY_TARGET",
        f"-I{scratch}",
        *[f"-I{prepared / d}" for d in include_dirs],
        unit_c.name,
        "-o",
        str(out_s),
    ]
    done = subprocess.run(argv, cwd=scratch, capture_output=True, text=True, timeout=180, check=False)
    _require(
        done.returncode == 0 and out_s.is_file(),
        f"q25bb-copy-client.c compilation failed: {(done.stderr + done.stdout).strip()}",
    )
    return prepare_client_assembly(out_s.read_text(encoding="utf-8"))


def _assemble_and_check_extents(
    package_s: str,
    atomic_s: str,
    notification_s: str,
    client_s: str,
    wrapper_s: str,
    name: str,
    elf_path: Path,
    *,
    verify_frozen_extents: bool,
) -> tuple[bytes, dict[str, object]]:
    parts = [
        ("compiled C", package_s),
        ("src/atomic_target.s", atomic_s),
        ("src/notification_target.s", notification_s),
        ("client", client_s),
        ("wrapper", wrapper_s),
    ]
    stream = "".join(body for _, body in parts)
    refusals = compiler_diff.refusals(stream)
    _require(not refusals, f"{name}: assembly dialect refusals: {refusals[:5]}")
    assembler = asm.Assembler(compiler_diff.compose(stream), name, data_base=DATA_BASE)
    sections, symbols, entry = assembler.assemble()
    image.write_elf(elf_path, sections, symbols, entry)

    text_sec = next(sec for sec in sections if sec.name == ".text")
    members: dict[str, object] = {}
    cursor = compiler_diff.PROLOGUE.count("\n") + 1
    for label, body in parts:
        next_cursor = cursor + body.count("\n")
        if label in copy_envelope.MEMBER_GROUPS:
            sites = [site for site in assembler.sites if cursor <= site.source < next_cursor]
            _require(
                bool(sites) and all(site.section == ".text" for site in sites),
                f"{label} has no .text sites",
            )
            start, end = sites[0].address, sites[-1].address + 4
            _require(
                [site.address for site in sites] == list(range(start, end, 4)),
                f"{label} assembled instructions are noncontiguous",
            )
            raw_slice = bytes(text_sec.data[start - text_sec.addr : end - text_sec.addr])
            digest = _sha256(raw_slice)
            if verify_frozen_extents:
                exp_bytes, exp_sha = FROZEN_MEMBERS[label]
                _require(
                    len(raw_slice) == exp_bytes and digest == exp_sha,
                    f"{label} extent differs from frozen 498127d6 build: {len(raw_slice)} {digest}",
                )
            members[label] = {
                "start": hex(start),
                "end_exclusive": hex(end),
                "bytes": len(raw_slice),
                "sha256": digest,
                "vos_copy_symbols": {
                    sym: hex(addr)
                    for sym, (sec_name, addr) in sorted(symbols.items())
                    if sec_name == ".text" and start <= addr < end and sym.startswith("vos_copy_")
                },
            }
        cursor = next_cursor
    return elf_path.read_bytes(), members


def _apply_c_mutation(prepared_copy: Path, control_name: str) -> None:
    if control_name == "mutated-payload-limit":
        config_h = prepared_copy / "include/copy_service_config.h"
        original = config_h.read_text(encoding="utf-8")
        target = "if (operation == 0u) return 4096u;"
        replacement = "if (operation == 0u) return 4095u;"
        _require(original.count(target) == 1, "cannot locate operation 0 limit in copy_service_config.h")
        config_h.write_text(original.replace(target, replacement, 1), encoding="utf-8")
        return

    service_c = prepared_copy / "src/copy_service.c"
    original = service_c.read_text(encoding="utf-8")
    if control_name == "mutated-snapshot-byte":
        target = "(void)vos_copy_stage(slot->bytes, VOS_COPY_MAX_PAYLOAD, source, extent, length);"
        replacement = target + "\n    slot->bytes[0] = (uint8_t)(slot->bytes[0] + 1u);"
    elif control_name == "mutated-suffix-clobber":
        target = "(void)vos_copy_stage(destination, capacity, slot->bytes, slot->length, slot->length);"
        replacement = target + "\n    if (capacity > slot->length) destination[slot->length] = 0u;"
    elif control_name == "mutated-refusal-output":
        target = (
            "    if (!vos_copy_view_valid(view) || vos_copy_occupancy(view) == 0)\n"
            "        return 0;\n"
            "    vos_copy_payload *const slot = &ring->slots[view->consumed % VOS_COPY_CAPACITY];"
        )
        replacement = (
            "    if (!vos_copy_view_valid(view) || vos_copy_occupancy(view) == 0) {\n"
            "        *length = 0u;\n"
            "        return 0;\n"
            "    }\n"
            "    vos_copy_payload *const slot = &ring->slots[view->consumed % VOS_COPY_CAPACITY];"
        )
    else:
        raise ValueError(f"unsupported C control mutation: {control_name}")

    _require(original.count(target) == 1, f"cannot apply {control_name} mutation uniquely")
    service_c.write_text(original.replace(target, replacement, 1), encoding="utf-8")


def _trace_details(raw_log: bytes) -> tuple[int, str, list[int]]:
    records = trace.normalize_commit(raw_log.decode("utf-8").splitlines())
    _require(bool(records), "trace contains zero commit records")
    trace_sha = _sha256("\n".join(records).encode("utf-8"))
    trap_causes = [int(rec.split()[2]) for rec in records if rec.startswith("T ")]
    return len(records), trace_sha, trap_causes


def run(
    root: Path,
    holdfast_repo: Path,
    compiler: Path,
    simulator: Path,
    output: Path,
    *,
    timeout: int = 300,
) -> dict[str, object]:
    """Build, execute, observe, and validate HoldFast's purecap Q25bb client on Sail."""
    root, holdfast_repo, compiler, simulator, output = (
        p.resolve() for p in (root, holdfast_repo, compiler, simulator, output)
    )
    output.mkdir(parents=True, exist_ok=True)
    prepared = output / "prepared"
    copy_package.prepare(root, prepared)
    record = copy_package.check(root, prepared)
    _require(
        _sha256((prepared / copy_package.RECORD).read_bytes()) == FROZEN_SOURCE_SHA256,
        "prepared source record differs from frozen 498127d6 snapshot",
    )

    config_path = compiler.with_name("compcert.ini")
    _require(_sha256(compiler.read_bytes()) == COMPILER_SHA256, "retained compiler binary differs")
    _require(_sha256(config_path.read_bytes()) == COMPCERT_INI_SHA256, "retained compcert.ini differs")
    try:
        compiler_provenance.read(compiler, lock=root / compiler_provenance.LOCK)
    except ValueError as err:
        producer_refusal = str(err)
    else:
        raise ValueError("expected retained compiler provenance refusal")

    client_c = holdfast_repo / "tools/tests/fixtures/q25bb-copy-client.c"
    client_h = holdfast_repo / "tools/tests/fixtures/q25bb-copy-client.h"
    _require(client_c.is_file() and client_h.is_file(), "missing HoldFast q25bb-copy-client fixtures")
    holdfast_rev = subprocess.run(
        ["git", "-C", str(holdfast_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()

    cfg = copy_service.configuration(root)
    arena_bytes = arena_bytes_for(cfg.maximum)
    recipe = cast(Mapping[str, object], record["recipe"])
    atomic_s = (prepared / "src/atomic_target.s").read_text(encoding="utf-8")
    notification_s = (prepared / "src/notification_target.s").read_text(encoding="utf-8")

    positive_package_s = _compile_package_unit(
        compiler, config_path, prepared, recipe, output / "package_unit.s"
    )
    positive_client_s = _compile_client_unit(
        compiler, config_path, prepared, recipe, client_c, client_h, output / "client-build"
    )

    positive_elf = output / "q25bb-client.elf"
    positive_elf_bytes, members = _assemble_and_check_extents(
        positive_package_s,
        atomic_s,
        notification_s,
        positive_client_s,
        entry_wrapper(arena_bytes),
        "q25bb-client",
        positive_elf,
        verify_frozen_extents=True,
    )

    profile = root / "model/config/verifiedos.json"
    sim_run = copy_target.execute(simulator, profile, positive_elf, timeout=timeout)
    _require(
        sim_run["verdict"] == "pass" and sim_run["code"] == TRIAL_PASS,
        f"purecap HoldFast client failed on Sail: {sim_run}",
    )
    raw_log = Path(str(sim_run["log"])).read_bytes()

    envelope = copy_envelope.observe(positive_elf_bytes, raw_log, members)
    envelope.update({
        "scope": "Q25bb purecap HoldFast client execution envelope against frozen 498127d6 copy-service",
        "frozen_source_revision": FROZEN_SOURCE_REVISION,
        "prepared_source_sha256": FROZEN_SOURCE_SHA256,
        "runtime_verdict": sim_run["verdict"],
        "runtime_code": sim_run["code"],
        **NON_ACCEPTANCE_FLAGS,
    })

    controls_out: dict[str, object] = {}
    controls_dir = output / "controls"
    controls_dir.mkdir(parents=True, exist_ok=True)
    for control_name, (exp_verdict, exp_codes, kind) in NEGATIVE_CONTROL_SPECS.items():
        if kind == "c-mutation":
            with tempfile.TemporaryDirectory(prefix=f"{control_name}-", dir=controls_dir) as td:
                scratch = Path(td)
                mutated_prepared = scratch / "prepared"
                shutil.copytree(prepared, mutated_prepared)
                _apply_c_mutation(mutated_prepared, control_name)
                ctrl_package_s = _compile_package_unit(
                    compiler, config_path, mutated_prepared, recipe, scratch / "package_unit.s"
                )
            ctrl_wrapper_s = entry_wrapper(arena_bytes)
        else:
            ctrl_package_s = positive_package_s
            ctrl_wrapper_s = entry_wrapper(arena_bytes, narrow_arena_by=1)

        ctrl_elf = controls_dir / f"{control_name}.elf"
        ctrl_elf_bytes, _ = _assemble_and_check_extents(
            ctrl_package_s,
            atomic_s,
            notification_s,
            positive_client_s,
            ctrl_wrapper_s,
            control_name,
            ctrl_elf,
            verify_frozen_extents=(kind != "c-mutation"),
        )
        ctrl_run = copy_target.execute(simulator, profile, ctrl_elf, timeout=timeout)
        ctrl_log = Path(str(ctrl_run["log"])).read_bytes()
        ctrl_records, ctrl_trace_sha, trap_causes = _trace_details(ctrl_log)
        verdict = str(ctrl_run["verdict"])
        code = ctrl_run["code"]
        _require(
            verdict == exp_verdict and isinstance(code, int) and code in exp_codes,
            f"negative control {control_name} unexpected verdict: {ctrl_run}",
        )
        if exp_verdict == "trap":
            _require(
                CHERI_CAP_BOUNDS_CAUSE in trap_causes,
                f"negative control {control_name} missing CHERI bounds cause {CHERI_CAP_BOUNDS_CAUSE}: {trap_causes}",
            )
        controls_out[control_name] = {
            "name": control_name,
            "kind": kind,
            "expected_verdict": exp_verdict,
            "expected_codes": list(exp_codes),
            "verdict": verdict,
            "code": code,
            "detail": ctrl_run["detail"],
            "elf_sha256": _sha256(ctrl_elf_bytes),
            "records": ctrl_records,
            "trace_sha256": ctrl_trace_sha,
            "raw_log_sha256": _sha256(ctrl_log),
            "trap_cause": trap_causes[-1] if trap_causes else None,
            "passed": True,
        }

    controls_doc: dict[str, object] = {
        "scope": "Q25bb purecap HoldFast client target-side negative controls",
        "controls": controls_out,
        "all_controls_passed": True,
        **NON_ACCEPTANCE_FLAGS,
    }

    envelope_bytes = (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")
    controls_bytes = (json.dumps(controls_doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "envelope.json").write_bytes(envelope_bytes)
    (output / "controls.json").write_bytes(controls_bytes)

    trace_summary = cast(Mapping[str, object], envelope["trace_summary"])
    report: dict[str, object] = {
        "scope": "Q25bb purecap HoldFast client end-to-end target execution against frozen 498127d6 copy-service",
        "frozen_source_revision": FROZEN_SOURCE_REVISION,
        "prepared_source_sha256": FROZEN_SOURCE_SHA256,
        "holdfast_revision": holdfast_rev,
        "holdfast_client_c_sha256": _sha256(client_c.read_bytes()),
        "holdfast_client_h_sha256": _sha256(client_h.read_bytes()),
        "compiler_sha256": COMPILER_SHA256,
        "compcert_ini_sha256": COMPCERT_INI_SHA256,
        "qualified_target_entry_producer_refusal": producer_refusal,
        "simulator_sha256": _sha256(simulator.read_bytes()),
        "profile_sha256": _sha256(profile.read_bytes()),
        "frozen_members_matched": True,
        "frozen_members": {
            label: {"bytes": size, "sha256": digest}
            for label, (size, digest) in FROZEN_MEMBERS.items()
        },
        "elf_sha256": envelope["elf_sha256"],
        "verdict": sim_run["verdict"],
        "code": sim_run["code"],
        "trace_records": trace_summary["records"],
        "trace_sha256": trace_summary["trace_sha256"],
        "raw_log_sha256": envelope["raw_log_sha256"],
        "envelope_sha256": _sha256(envelope_bytes),
        "controls_sha256": _sha256(controls_bytes),
        "negative_controls_passed": True,
        **NON_ACCEPTANCE_FLAGS,
    }
    report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "report.json").write_bytes(report_bytes)

    validate_bundle(report, envelope, controls_doc)
    return report


def _check_non_acceptance(doc: Mapping[str, object], label: str) -> None:
    for key, expected in NON_ACCEPTANCE_FLAGS.items():
        _require(
            key in doc and doc[key] is expected,
            f"{label}: {key} must be {expected!r}, got {doc.get(key)!r}",
        )


def _check_frozen_members_map(members: object, label: str) -> None:
    _require(isinstance(members, Mapping), f"{label}: missing frozen members map")
    member_map = cast(Mapping[str, object], members)
    _require(
        set(member_map.keys()) == set(FROZEN_MEMBERS.keys()),
        f"{label}: member keys mismatch: {sorted(member_map.keys())}",
    )
    for name, (exp_bytes, exp_sha) in FROZEN_MEMBERS.items():
        entry = member_map[name]
        _require(isinstance(entry, Mapping), f"{label}: {name} entry must be an object")
        entry_map = cast(Mapping[str, object], entry)
        _require(
            entry_map.get("bytes") == exp_bytes and entry_map.get("sha256") == exp_sha,
            f"{label}: {name} extent differs from frozen 498127d6 build: {entry_map}",
        )


def validate_bundle(
    report: Mapping[str, object],
    envelope: Mapping[str, object],
    controls: Mapping[str, object],
) -> None:
    """Validate `report.json`, `envelope.json`, and `controls.json` invariants and verdicts."""
    _check_non_acceptance(report, "report")
    _check_non_acceptance(envelope, "envelope")
    _check_non_acceptance(controls, "controls")

    _require(
        report.get("prepared_source_sha256") == FROZEN_SOURCE_SHA256,
        "report: prepared_source_sha256 mismatch",
    )
    _require(report.get("compiler_sha256") == COMPILER_SHA256, "report: compiler_sha256 mismatch")
    _require(
        report.get("compcert_ini_sha256") == COMPCERT_INI_SHA256,
        "report: compcert_ini_sha256 mismatch",
    )
    refusal = report.get("qualified_target_entry_producer_refusal")
    _require(
        isinstance(refusal, str) and bool(refusal.strip()),
        "report: missing qualified_target_entry_producer_refusal",
    )
    _require(report.get("frozen_members_matched") is True, "report: frozen_members_matched must be True")
    _check_frozen_members_map(report.get("frozen_members"), "report.frozen_members")
    _require(
        report.get("verdict") == "pass" and report.get("code") == TRIAL_PASS,
        f"report: expected passing verdict, got {report.get('verdict')} ({report.get('code')})",
    )
    _require(report.get("negative_controls_passed") is True, "report: negative_controls_passed must be True")

    static_fp = envelope.get("static_footprint")
    _require(isinstance(static_fp, Mapping), "envelope: missing static_footprint")
    fp_map = cast(Mapping[str, object], static_fp)
    _check_frozen_members_map(fp_map.get("members"), "envelope.static_footprint.members")
    _require(
        fp_map.get("service_text_bytes") == sum(size for size, _ in FROZEN_MEMBERS.values()),
        "envelope: unexpected service_text_bytes",
    )
    _require(
        envelope.get("runtime_verdict") == "pass" and envelope.get("runtime_code") == TRIAL_PASS,
        "envelope: expected passing runtime verdict",
    )
    trace_summary = envelope.get("trace_summary")
    _require(isinstance(trace_summary, Mapping), "envelope: missing trace_summary")
    ts_map = cast(Mapping[str, object], trace_summary)
    records = ts_map.get("records")
    trace_sha = ts_map.get("trace_sha256")
    raw_log_sha = envelope.get("raw_log_sha256")
    _require(type(records) is int and records > 0, "envelope: trace_summary.records must be positive")
    _require(isinstance(trace_sha, str) and bool(_SHA256_RE.fullmatch(trace_sha)), "envelope: invalid trace_sha256")
    _require(isinstance(raw_log_sha, str) and bool(_SHA256_RE.fullmatch(raw_log_sha)), "envelope: invalid raw_log_sha256")
    _require(report.get("trace_records") == records, "report: trace_records disagrees with envelope")
    _require(report.get("trace_sha256") == trace_sha, "report: trace_sha256 disagrees with envelope")
    _require(report.get("raw_log_sha256") == raw_log_sha, "report: raw_log_sha256 disagrees with envelope")
    _require(report.get("elf_sha256") == envelope.get("elf_sha256"), "report: elf_sha256 disagrees with envelope")

    operations = envelope.get("operations")
    _require(isinstance(operations, Mapping), "envelope: missing operations")
    ops_map = cast(Mapping[str, object], operations)
    _require(set(ops_map.keys()) == set(copy_envelope.PUBLIC_ENTRIES), "envelope: operations keys mismatch")
    for exercised in ("vos_copy_init_generation", "vos_copy_submit", "vos_copy_take"):
        op = ops_map[exercised]
        _require(isinstance(op, Mapping), f"envelope: {exercised} must be an object")
        op_map = cast(Mapping[str, object], op)
        calls = op_map.get("call_count")
        _require(type(calls) is int and calls > 0, f"envelope: {exercised} must be exercised")
        stack = op_map.get("stack_frame_bytes")
        _require(
            isinstance(stack, Mapping) and type(stack.get("peak")) is int,
            f"envelope: {exercised} missing stack_frame_bytes.peak",
        )

    _require(controls.get("all_controls_passed") is True, "controls: all_controls_passed must be True")
    ctrl_entries = controls.get("controls")
    _require(isinstance(ctrl_entries, Mapping), "controls: missing controls map")
    ctrl_map = cast(Mapping[str, object], ctrl_entries)
    _require(
        set(ctrl_map.keys()) == set(NEGATIVE_CONTROL_SPECS.keys()),
        f"controls: expected all 5 negative controls, got {sorted(ctrl_map.keys())}",
    )
    for name, (exp_verdict, exp_codes, _) in NEGATIVE_CONTROL_SPECS.items():
        raw_entry = ctrl_map[name]
        _require(isinstance(raw_entry, Mapping), f"controls.{name}: must be an object")
        entry = cast(Mapping[str, object], raw_entry)
        _require(entry.get("passed") is True, f"controls.{name}: passed must be True")
        _require(
            entry.get("verdict") == exp_verdict,
            f"controls.{name}: expected verdict {exp_verdict!r}, got {entry.get('verdict')!r}",
        )
        code = entry.get("code")
        _require(
            type(code) is int and code in exp_codes,
            f"controls.{name}: expected code in {exp_codes}, got {code!r}",
        )
        ctrl_sha = entry.get("trace_sha256")
        _require(
            isinstance(ctrl_sha, str) and bool(_SHA256_RE.fullmatch(ctrl_sha)),
            f"controls.{name}: invalid trace_sha256",
        )
        if exp_verdict == "trap":
            _require(
                entry.get("trap_cause") == CHERI_CAP_BOUNDS_CAUSE,
                f"controls.{name}: expected CHERI bounds trap cause {CHERI_CAP_BOUNDS_CAUSE}",
            )


def validate_bundle_dir(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read, hash-verify, and validate `report.json`, `envelope.json`, and `controls.json`."""
    report_bytes = (bundle_dir / "report.json").read_bytes()
    envelope_bytes = (bundle_dir / "envelope.json").read_bytes()
    controls_bytes = (bundle_dir / "controls.json").read_bytes()
    report = json.loads(report_bytes.decode("utf-8"))
    envelope = json.loads(envelope_bytes.decode("utf-8"))
    controls = json.loads(controls_bytes.decode("utf-8"))
    _require(
        isinstance(report, dict) and isinstance(envelope, dict) and isinstance(controls, dict),
        "bundle JSON artifacts must be objects",
    )
    _require(
        report.get("envelope_sha256") == _sha256(envelope_bytes),
        "report: envelope_sha256 disagrees with envelope.json bytes",
    )
    _require(
        report.get("controls_sha256") == _sha256(controls_bytes),
        "report: controls_sha256 disagrees with controls.json bytes",
    )
    validate_bundle(report, envelope, controls)
    return report, envelope, controls


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for building and executing the Q25bb purecap HoldFast client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--holdfast-repo", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--simulator", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)
    report = run(
        args.checkout,
        args.holdfast_repo,
        args.compiler,
        args.simulator,
        args.output,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
