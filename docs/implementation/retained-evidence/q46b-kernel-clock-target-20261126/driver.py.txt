# SPDX-License-Identifier: Apache-2.0
"""Q46b purecap CHERI-CompCert & source-bound Sail target replay for the executive clock horizon."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from vos import (  # noqa: E402
    asm,
    boot_handoff,
    compiler_diff,
    compiler_provenance,
    image,
    kernel_restore,
    kernel_target,
    kernelrun,
    native_build,
    receipts,
    simulator_build,
    trace,
)
from vos.boot_signing import SlhSigner  # noqa: E402
from vos.boot_target import compiler_inputs  # noqa: E402

PARTITIONS: Final = kernel_target.PARTITIONS
WINDOWS: Final = kernel_target.WINDOWS
SLOTS: Final = kernel_target.SLOTS
CSRS: Final = kernel_target.CSRS
DATA_BASE: Final = 0x80200000
# Q46b checked clock arithmetic expands target_unit.c .text past 0xa000 (to 0xa080);
# placing .data at 0xb000 with 4 KiB (.align 12) kdata/kstack alignment keeps
# kdata (0x4000) and kstack (0x2000) exact while fitting inside BRINGUP_MMODE_REGION_BYTES (0x10000).
PART_B_DATA_OFFSET: Final = 0xB000
SENTINEL: Final = 0xAAAAAAAAAAAAAAAA

PART_A_CASES: Final[tuple[str, ...]] = (
    "valid_zero_and_max_and_table_order",
    "phase_offset_overflow",
    "frame_index_mul_overflow",
    "final_sum_overflow",
    "frame_index_exhaustion",
    "target_release_epoch_and_duration_overflow",
)

PART_A_NEGATIVE_CONTROLS: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "mutated-phase-overflow",
        "executive",
        "if (f->phase_offset > UINT64_MAX - offset) {",
        "if (0) {",
    ),
    (
        "mutated-mul-overflow",
        "executive",
        "if (e->frame_index > (UINT64_MAX - origin) / f->major_frame) {",
        "if (0) {",
    ),
    (
        "mutated-frame-index-wrap",
        "executive",
        "    if (candidate.frame_index == UINT64_MAX) {\n      return 0;\n    }",
        "    if (0) {\n      return 0;\n    }",
    ),
    (
        "mutated-duration-overflow",
        "target",
        "if (duration > UINT64_MAX - absolute) {",
        "if (0) {",
    ),
)

PART_B_CONTROLS: Final[tuple[str, ...]] = (
    "adapter-epoch-overflow",
    "mutated-unguarded-target-release",
)

KERNEL_TARGET_CONTROL_NAMES: Final[tuple[str, ...]] = (
    "missing-timer",
    "wrong-timer-permission",
    "sealed-execute-root",
    "overbroad-stack",
    "overbroad-mtdc",
    "swapped-timers",
    "overbroad-timer",
    "resident-copy",
    "stale-saved-copy",
    "epoch-only",
    "missing-fence",
    "descriptor-data",
    "descriptor-unequal-width",
    "wrong-c-switch",
)

NON_ACCEPTANCE_FLAGS: Final[dict[str, object]] = {
    "qualified_producer": False,
    "production_admission": False,
    "trial_acceptance": False,
}

_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _part_a_driver_body() -> str:
    """Return the purecap C test driver body exercising the six Part A clock-horizon obligations."""
    return """
#define CLOCK_SENTINEL 0xaaaaaaaaaaaaaaaaULL

static void init_frame(struct vos_frame *f)
{
  f->major_frame = 0ULL;
  f->phase_offset = 0ULL;
  f->reserved_count = 0u;
  f->slot_count = 0u;
  for (uint32_t i = 0u; i < VOS_MAX_SLOTS; ++i) {
    f->slots[i].width = 0ULL;
    f->slots[i].offset = 0ULL;
    f->slots[i].bound = 0ULL;
    f->slots[i].period = 0ULL;
    f->slots[i].tenant = 0u;
  }
}

static void init_target_state(struct vos_target_state *state)
{
  state->boot.lifecycle = 0ULL;
  state->boot.entropy_ok = 0ULL;
  state->boot.boot_target = 0ULL;
  state->boot.security_version = 0ULL;
  state->boot.floor = 0ULL;
  state->boot.load_base = 0ULL;
  state->boot.payload_length = 0ULL;
  state->handoff.init.partition_count = 0u;
  state->handoff.init.window_count = 0u;
  state->handoff.init.switch_text.base = 0ULL;
  state->handoff.init.switch_text.top = 0ULL;
  init_frame(&state->handoff.init.frame);
  state->handoff.init.machine.csr_count = 0u;
  state->handoff.init.machine.pending_swapped = 0u;
  state->handoff.init.machine.rotation_swaps_pending = 0u;
  state->handoff.init.machine.pending_static_mask = 0ULL;
  vos_exec_start(&state->executive);
}

int main(void)
{
  struct vos_frame f;
  struct vos_exec e;
  struct vos_target_state state;
  uint64_t out = CLOCK_SENTINEL;
  uint64_t deadline = CLOCK_SENTINEL;

  /* 1. Valid releases at 0 and UINT64_MAX, normal multi-slot table order and frame advancement. */
  init_frame(&f);
  vos_exec_start(&e);
  f.major_frame = 2ULL;
  f.phase_offset = 0ULL;
  f.reserved_count = 0u;
  f.slot_count = 1u;
  f.slots[0].width = 1ULL;
  f.slots[0].offset = 0ULL;
  f.slots[0].tenant = 1u;
  if (vos_frame_validate(&f) != VOS_OK) {
    return 10;
  }
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 1 || out != 0ULL) {
    return 11;
  }

  f.phase_offset = UINT64_MAX - 1ULL;
  f.slots[0].offset = 1ULL;
  if (vos_frame_validate(&f) != VOS_OK) {
    return 12;
  }
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 1 || out != UINT64_MAX) {
    return 13;
  }

  f.major_frame = 1ULL;
  f.phase_offset = 0ULL;
  f.slots[0].offset = 0ULL;
  e.frame_index = UINT64_MAX;
  e.cursor = 0u;
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 1 || out != UINT64_MAX) {
    return 14;
  }

  init_frame(&f);
  f.major_frame = 11ULL;
  f.phase_offset = 7ULL;
  f.reserved_count = 0u;
  f.slot_count = 2u;
  f.slots[0].offset = 1ULL;
  f.slots[0].width = 2ULL;
  f.slots[0].tenant = 1u;
  f.slots[1].offset = 5ULL;
  f.slots[1].width = 3ULL;
  f.slots[1].tenant = 2u;
  if (vos_frame_validate(&f) != VOS_OK) {
    return 15;
  }
  vos_exec_start(&e);
  for (uint32_t visit = 0u; visit < 8u; ++visit) {
    const uint32_t expected_tenant = (visit % 2u) ? 2u : 1u;
    const uint64_t expected_offset = (visit % 2u) ? 5ULL : 1ULL;
    const uint64_t expected_release = 7ULL + (uint64_t)(visit / 2u) * 11ULL + expected_offset;
    if (vos_exec_tenant(&f, &e) != expected_tenant) {
      return 16;
    }
    out = CLOCK_SENTINEL;
    if (vos_exec_release(&f, &e, &out) != 1 || out != expected_release) {
      return 17;
    }
    if (vos_exec_advance(&f, &e) != 1) {
      return 18;
    }
    if (e.frame_index != (uint64_t)((visit + 1u) / 2u) || e.cursor != ((visit + 1u) % 2u)) {
      return 19;
    }
  }

  /* 2. Phase+offset overflow: VOS_TABLE_OVERFLOW, release -> 0, output unchanged. */
  init_frame(&f);
  vos_exec_start(&e);
  f.major_frame = 2ULL;
  f.phase_offset = UINT64_MAX;
  f.slot_count = 1u;
  f.slots[0].width = 1ULL;
  f.slots[0].offset = 1ULL;
  f.slots[0].tenant = 1u;
  if (vos_frame_validate(&f) != VOS_TABLE_OVERFLOW) {
    return 20;
  }
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 0 || out != CLOCK_SENTINEL) {
    return 21;
  }
  if (vos_exec_advance(&f, &e) != 0 || e.frame_index != 0ULL || e.cursor != 0u) {
    return 22;
  }

  /* 3. Frame-index multiplication overflow: release -> 0, output unchanged. */
  init_frame(&f);
  f.major_frame = 2ULL;
  f.phase_offset = 0ULL;
  f.slot_count = 1u;
  f.slots[0].width = 1ULL;
  f.slots[0].offset = 0ULL;
  e.frame_index = (UINT64_MAX / 2ULL) + 1ULL;
  e.cursor = 0u;
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 0 || out != CLOCK_SENTINEL) {
    return 30;
  }

  /* 4. Final sum overflow: boundary succeeds at UINT64_MAX, +1 refuses with output unchanged. */
  f.phase_offset = 1ULL;
  e.frame_index = UINT64_MAX / 2ULL;
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 1 || out != UINT64_MAX) {
    return 40;
  }
  f.phase_offset = 2ULL;
  out = CLOCK_SENTINEL;
  if (vos_exec_release(&f, &e, &out) != 0 || out != CLOCK_SENTINEL) {
    return 41;
  }

  /* 5. Frame-index exhaustion at UINT64_MAX: advance -> 0, cursor unchanged. */
  init_frame(&f);
  f.major_frame = 1ULL;
  f.phase_offset = 0ULL;
  f.slot_count = 1u;
  f.slots[0].width = 1ULL;
  f.slots[0].offset = 0ULL;
  e.frame_index = UINT64_MAX;
  e.cursor = 0u;
  if (vos_exec_advance(&f, &e) != 0 || e.frame_index != UINT64_MAX || e.cursor != 0u) {
    return 50;
  }

  /* 6. vos_target_release epoch and duration overflow: refusal leaves deadline unchanged. */
  init_target_state(&state);
  state.handoff.init.frame.major_frame = 11ULL;
  state.handoff.init.frame.phase_offset = 7ULL;
  state.handoff.init.frame.slot_count = 2u;
  state.handoff.init.frame.slots[0].offset = 1ULL;
  state.handoff.init.frame.slots[0].width = 2ULL;
  state.handoff.init.frame.slots[0].tenant = 1u;
  state.handoff.init.frame.slots[1].offset = 5ULL;
  state.handoff.init.frame.slots[1].width = 3ULL;
  state.handoff.init.frame.slots[1].tenant = 2u;
  vos_exec_start(&state.executive);

  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, 3ULL, 2ULL, &deadline) != 1 || deadline != 13ULL) {
    return 60;
  }
  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, UINT64_MAX, 0ULL, &deadline) != 0 || deadline != CLOCK_SENTINEL) {
    return 61;
  }
  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, UINT64_MAX - 8ULL, 0ULL, &deadline) != 1 || deadline != UINT64_MAX) {
    return 62;
  }
  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, 0ULL, UINT64_MAX, &deadline) != 0 || deadline != CLOCK_SENTINEL) {
    return 63;
  }

  init_target_state(&state);
  state.handoff.init.frame.major_frame = 1ULL;
  state.handoff.init.frame.phase_offset = 0ULL;
  state.handoff.init.frame.slot_count = 1u;
  state.handoff.init.frame.slots[0].offset = 0ULL;
  state.handoff.init.frame.slots[0].width = 1ULL;
  state.executive.frame_index = UINT64_MAX;
  state.executive.cursor = 0u;
  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, 0ULL, 0ULL, &deadline) != 1 || deadline != UINT64_MAX) {
    return 64;
  }
  deadline = CLOCK_SENTINEL;
  if (vos_target_release(&state, 0ULL, 1ULL, &deadline) != 0 || deadline != CLOCK_SENTINEL) {
    return 65;
  }

  return 0;
}
"""


def _assemble_part_a(closed_s: str, name: str, elf_path: Path) -> bytes:
    stream = compiler_diff.normalize(closed_s)
    found = compiler_diff.refusals(stream)
    _require(not found, f"{name}: assembly dialect refusals: {found[:5]}")
    composite = compiler_diff.compose(stream)
    elf_path.with_suffix(".s").write_text(composite, encoding="utf-8", newline="\n")
    assembler = asm.Assembler(composite, name, data_base=DATA_BASE)
    sections, symbols, entry = assembler.assemble()
    text_sec = next(section for section in sections if section.name == ".text")
    _require(
        text_sec.addr + len(text_sec.data) <= DATA_BASE,
        f"{name}: .text ({len(text_sec.data)} bytes) reaches .data at {hex(DATA_BASE)}",
    )
    image.write_elf(elf_path, sections, symbols, entry)
    return elf_path.read_bytes()


def _run_sail_trace(
    simulator: Path,
    profile: Path,
    elf: Path,
    timeout: int,
    *,
    inst_limit: int = 200000,
) -> tuple[str, int | None, list[kernelrun.Record], str, str, list[str]]:
    argv = [
        str(simulator),
        "--config",
        str(profile),
        "--trace-commit",
        "--inst-limit",
        str(inst_limit),
        str(elf),
    ]
    done = subprocess.run(
        argv,
        cwd=elf.parent,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    raw = done.stdout + done.stderr
    elf.with_suffix(".trace").write_text(raw, encoding="utf-8", newline="\n")
    normalized = trace.normalize_commit(raw.splitlines())
    _require(bool(normalized), f"{elf.name}: simulator produced zero commit records")
    records = kernelrun.parse_records(normalized)
    htif, code, _ = compiler_diff.htif_verdict(raw, done.returncode)
    trace_sha = _sha256("\n".join(normalized).encode("utf-8"))
    return htif, code, records, trace_sha, _sha256(raw.encode("utf-8")), argv


def _validate_simulator_receipt(
    root: Path,
    simulator: Path,
    build_receipt: Path,
    simulator_sha: str,
    model_sources: dict[str, str],
) -> dict[str, object]:
    """Validate simulator receipt via `kernel_restore.require_build` (v1) or `simulator_build` (v2)."""
    receipt = json.loads(build_receipt.read_text(encoding="utf-8"))
    _require(isinstance(receipt, dict), "simulator build receipt must be a JSON object")
    schema = receipt.get("schema")
    if schema == 1:
        kernel_restore.require_build(receipt, simulator_sha, model_sources)
        return {
            "schema": 1,
            "validator": "vos.kernel_restore.require_build",
            "bundled_model_tests": "passed",
            "full_model_acceptance": "passed",
            "environment_note": "exact schema 1 receipt",
        }
    if schema == simulator_build.SCHEMA:
        try:
            simulator_build.read(root, simulator, build_receipt)
            env_note = "exact simulator_build.read match"
        except ValueError as err:
            # Focused simulator receipts bind PATH in native_inputs.environment; accept cross-session
            # replay only when every non-environment binding (model sources, profile, binary, stages,
            # native files, targets, and population) verifies identically.
            if "native build inputs changed" not in str(err):
                raise
            raw_native = receipt.get("native_inputs")
            recorded = native_build._record(raw_native)
            observed = native_build.observe(recorded)
            _require(
                recorded["complete"] is True
                and recorded["files"] == observed["files"]
                and recorded["targets"] == observed["targets"]
                and recorded["population"] == observed["population"],
                f"focused simulator native files/targets/population changed: {err}",
            )
            profile = root / "model/config/verifiedos.json"
            identity = receipt.get("identity")
            artifacts = receipt.get("artifacts")
            _require(
                receipt.get("passed") is True
                and receipt.get("inputs_unchanged") is True
                and receipt.get("exit_code") == 0
                and receipt.get("profile_validation_exit") == 0
                and isinstance(identity, dict)
                and identity.get("model_inputs") == model_sources
                and identity.get("profile_sha256") == receipts.digest(profile)
                and isinstance(artifacts, dict)
                and artifacts.get(simulator_build.ARTIFACT) == simulator_sha,
                "focused simulator receipt bindings disagree with checkout or binary",
            )
            env_note = (
                "all native_inputs files/targets/population, model_inputs, profile, and simulator "
                "binary matched; only native_inputs.environment.PATH differed from build session"
            )
        return {
            "schema": simulator_build.SCHEMA,
            "validator": "vos.simulator_build.read",
            "bundled_model_tests": receipt.get("bundled_model_tests"),
            "full_model_acceptance": receipt.get("full_model_acceptance"),
            "environment_note": env_note,
        }
    raise ValueError(f"unsupported simulator build receipt schema: {schema!r}")


def _read_compiler_provenance(
    root: Path, ccomp: Path, compiler_sha: str
) -> tuple[dict[str, object], dict[str, str], str]:
    try:
        prov, prov_files = compiler_provenance.read(ccomp, lock=root / compiler_provenance.LOCK)
    except ValueError as err:
        refusal = str(err)
        result_path = ccomp.parent / "build-result.json"
        prov_summary: dict[str, object] = {
            "build_receipt": "refused",
            "refusal": refusal,
            "compiler_sha256": compiler_sha,
        }
        if result_path.is_file():
            raw_res = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(raw_res, dict):
                prov_summary["revision"] = raw_res.get("revision")
                prov_summary["kind"] = raw_res.get("kind")
                prov_summary["passed"] = raw_res.get("passed")
                prov_summary["inputs_unchanged"] = raw_res.get("inputs_unchanged")
        return prov_summary, {}, refusal
    return (
        dict(prov),
        prov_files,
        "qualified provenance present; non-accepting until hosted target gate passes",
    )


def _compile_mutated_target_unit(
    root: Path,
    compiler_argv: list[str],
    scratch: Path,
    name: str,
    owner: str,
    old: str,
    new: str,
    timeout: int,
) -> compiler_diff.Compiled:
    scratch.mkdir(parents=True, exist_ok=True)
    sources = {
        unit: (root / f"kernel/src/{unit}.c").read_text(encoding="utf-8")
        for unit in ("context", "executive", "partition", "handoff", "target")
    }
    _require(sources[owner].count(old) == 1, f"{name}: anchor not unique in kernel/src/{owner}.c")
    sources[owner] = sources[owner].replace(old, new, 1)
    mutant_unit = scratch / "target_unit.c"
    mutant_unit.write_text(
        '#include "vos_target.h"\n' + "\n".join(sources.values()) + "\n" + _part_a_driver_body(),
        encoding="utf-8",
        newline="\n",
    )
    compiled = compiler_diff.compile_c(compiler_argv, mutant_unit, scratch / "compiler", timeout)
    _require(
        compiled.exit_code == 0 and compiled.stream is not None,
        f"{name}: C mutant is stillborn: {compiled.said}",
    )
    return compiled


def _part_b_consumer(
    compiled_stream: str,
    init_magic: int,
    windows: tuple[tuple[int, int], tuple[int, int]],
    bitmap: tuple[int, int],
) -> str:
    raw = kernel_target.consumer_source(
        compiler_diff.normalize(compiled_stream), init_magic, windows, bitmap
    )
    head, tail = raw.split(".data\n", 1)
    _require(tail.count(".align 13\n") == 2, "unexpected .align 13 layout in kernel_target consumer")
    return head + ".data\n" + tail.replace(".align 13\n", ".align 12\n")


def _run_composed_variant(
    root: Path,
    destination: Path,
    stage: str,
    consumer: str,
    lay: boot_handoff.Layout,
    signer: SlhSigner,
    binary: Path,
    inputs: boot_handoff.RotInputs,
    simulator: Path,
    profile: Path,
    timeout: int,
) -> tuple[boot_handoff.Assembled, dict[str, str], str, int | None, list[kernelrun.Record], str, str, bytes]:
    destination.mkdir(parents=True, exist_ok=True)
    built = boot_handoff.assemble_mmode(
        root,
        stage_text=stage,
        kernel_text=consumer,
        data_base=lay["BRINGUP_MMODE_LOAD_BASE"] + PART_B_DATA_OFFSET,
    )
    source = stage + "\n" + consumer
    (destination / "kernel.s").write_text(source, encoding="utf-8", newline="\n")
    signed = boot_handoff.build_image(
        lay,
        built.payload,
        security_version=inputs.floor,
        signer=signer.roots[boot_handoff.LIFECYCLES[inputs.lifecycle]],
        sign=signer.sign,
    )
    image_path = destination / "image.bin"
    image_path.write_bytes(signed)
    release = boot_handoff.rot_stage(binary, image_path, inputs, "slh256s", destination, roots=signer.roots)
    _require(
        release.get("verdict") == "release" and release.get("released") == "1",
        f"{destination.name}: RoT stage refused payload: {release}",
    )
    window = (destination / "sram.bin").read_bytes()
    record = (destination / "handoff.bin").read_bytes()
    _require(
        window[: len(built.payload)] == built.payload
        and not any(window[len(built.payload) :])
        and not boot_handoff._record_findings(lay, record, release, built.payload, inputs),
        f"{destination.name}: release bytes disagree",
    )
    elf = destination / "kernel.elf"
    boot_handoff.placed_elf(lay, window, record, built.symbols["tohost"], elf)
    htif, code, records, trace_sha, raw_log_sha, _ = _run_sail_trace(
        simulator, profile, elf, timeout, inst_limit=200000
    )
    return built, release, htif, code, records, trace_sha, raw_log_sha, elf.read_bytes()


def run(
    root: Path,
    ccomp: Path,
    ccomp_args: list[str],
    simulator: Path,
    build_receipt: Path,
    out: Path,
    timeout: int = 300,
) -> dict[str, object]:
    """Run Part A standalone purecap clock-horizon tests and Part B composed Q46b replay."""
    root, ccomp, simulator, build_receipt, out = (
        path.resolve() for path in (root, ccomp, simulator, build_receipt, out)
    )
    out.mkdir(parents=True, exist_ok=True)
    config_path = ccomp.with_name("compcert.ini")
    _require(ccomp.is_file(), f"missing compiler binary: {ccomp}")
    _require(config_path.is_file(), f"missing compcert.ini next to compiler: {config_path}")
    _require(simulator.is_file(), f"missing simulator binary: {simulator}")
    _require(build_receipt.is_file(), f"missing simulator build receipt: {build_receipt}")

    compiler_sha = receipts.digest(ccomp)
    compcert_ini_sha = receipts.digest(config_path)
    simulator_sha = receipts.digest(simulator)
    build_sha = receipts.digest(build_receipt)
    profile = root / boot_handoff.MAIN_CONFIG
    profile_sha = receipts.digest(profile)
    model_sources = receipts.inputs(root, "model")
    sources = receipts.inputs(root, *kernel_target.INPUTS)

    sim_meta = _validate_simulator_receipt(root, simulator, build_receipt, simulator_sha, model_sources)
    compiler_prov, provenance_files, producer_refusal = _read_compiler_provenance(
        root, ccomp, compiler_sha
    )

    host_cc = shutil.which("cc")
    if host_cc is None:
        raise ValueError("composed RoT release requires a host C compiler")
    host_cc_sha = receipts.digest(Path(host_cc))

    effective_args = [*ccomp_args]
    if "-conf" not in effective_args:
        effective_args = ["-conf", str(config_path), *effective_args]
    private_inputs = compiler_inputs(effective_args)

    flags = [
        *effective_args,
        "-fverifiedos-typed",
        f"-DVOS_MAX_PARTITIONS={PARTITIONS}",
        f"-DVOS_MAX_WINDOWS={WINDOWS}",
        f"-DVOS_MAX_SLOTS={SLOTS}",
        f"-DVOS_MAX_CSRS={CSRS}",
        f"-I{root / 'kernel/include'}",
        f"-I{root / 'firmware/include'}",
    ]
    compiler_argv = [str(ccomp), *flags]

    # Compile target_unit.c once for both Part A and Part B.
    compiled_unit = compiler_diff.compile_c(
        compiler_argv, root / "kernel/test/target_unit.c", out / "compiler-unit", timeout
    )
    if compiled_unit.exit_code != 0 or compiled_unit.stream is None:
        raise ValueError(f"kernel target_unit.c compilation failed: {compiled_unit.said}")
    unit_stream = compiled_unit.stream

    # --- Part A: Standalone Clock-Horizon Purecap Target Harness ---
    part_a_dir = out / "part-a"
    part_a_dir.mkdir(parents=True, exist_ok=True)
    driver_c = part_a_dir / "clock_driver.c"
    driver_c.write_text(
        '#include "target_unit.c"\n' + _part_a_driver_body(),
        encoding="utf-8",
        newline="\n",
    )
    part_a_argv = [*compiler_argv, f"-I{root / 'kernel/test'}"]
    compiled_driver = compiler_diff.compile_c(
        part_a_argv, driver_c, part_a_dir / "compiler-driver", timeout
    )
    if compiled_driver.exit_code != 0 or compiled_driver.stream is None:
        raise ValueError(f"Part A clock_driver.c compilation failed: {compiled_driver.said}")
    driver_stream = compiled_driver.stream

    part_a_elf = part_a_dir / "clock-horizon.elf"
    part_a_elf_bytes = _assemble_part_a(driver_stream, "q46b-part-a", part_a_elf)
    a_htif, a_code, a_records, a_trace_sha, a_log_sha, _ = _run_sail_trace(
        simulator, profile, part_a_elf, timeout, inst_limit=400000
    )
    _require(
        a_htif == "pass" and a_code == 0,
        f"Part A purecap clock-horizon positive harness failed: {a_htif} ({a_code})",
    )

    part_a_controls: dict[str, object] = {}
    for name, owner, old, new in PART_A_NEGATIVE_CONTROLS:
        ctrl_dir = part_a_dir / "controls" / name
        mutant_compiled = _compile_mutated_target_unit(
            root, compiler_argv, ctrl_dir, name, owner, old, new, timeout
        )
        if mutant_compiled.stream is None:
            raise ValueError(f"{name}: C mutant emitted no stream")
        ctrl_elf = ctrl_dir / f"{name}.elf"
        ctrl_elf_bytes = _assemble_part_a(mutant_compiled.stream, name, ctrl_elf)
        c_htif, c_code, c_records, c_trace_sha, c_log_sha, _ = _run_sail_trace(
            simulator, profile, ctrl_elf, timeout, inst_limit=400000
        )
        _require(
            c_htif == "fail" and isinstance(c_code, int) and c_code != 0,
            f"Part A negative control {name} did not exit nonzero via HTIF: {c_htif} ({c_code})",
        )
        part_a_controls[name] = {
            "name": name,
            "part": "A",
            "kind": "c-mutation",
            "owner": f"kernel/src/{owner}.c",
            "expected_verdict": "fail",
            "verdict": c_htif,
            "code": c_code,
            "elf_sha256": _sha256(ctrl_elf_bytes),
            "trace_records": len(c_records),
            "trace_sha256": c_trace_sha,
            "raw_log_sha256": c_log_sha,
            "compilation": {
                "stream_sha256": mutant_compiled.stream_sha256,
                "preprocessed_sha256": mutant_compiled.preprocessed.sha256,
            },
            "passed": True,
        }

    # --- Part B: Composed Two-Slot Signed Kernel Replay with Q46b Adapter Overflow Control ---
    part_b_dir = out / "part-b"
    part_b_dir.mkdir(parents=True, exist_ok=True)
    lay = boot_handoff.layout(root)
    compare, clock = boot_handoff.timer_windows(root)
    windows = ((compare, 8), (clock, 8))
    retired_object = lay["BRINGUP_MMODE_LOAD_BASE"] + PART_B_DATA_OFFSET + 64
    bitmap = kernel_target.revocation_window(root, retired_object)
    consumer = _part_b_consumer(unit_stream, lay["INIT_MAGIC"], windows, bitmap)
    stage = boot_handoff.scheduled_mmode(
        root,
        partition_text=(("partition_one", "partition_one_end"), ("partition_two", "partition_two_end")),
        revocation_word="REVOCATION_WORD",
    )
    stage = f".equ REVOCATION_WORD, {bitmap[0]}\n" + stage
    source = stage + "\n" + consumer
    (part_b_dir / "kernel.s").write_text(source, encoding="utf-8", newline="\n")

    signer = SlhSigner(
        part_b_dir / "signing",
        boot_handoff.ROOT_STATES,
        public_bytes=lay["BOOT_PUBLIC_KEY_BYTES"],
        signature_bytes=lay["BOOT_SIGNATURE_BYTES"],
    )
    probe_elf = part_b_dir / "rot-inputs.elf"
    asm.assemble_file(root / boot_handoff.PROBE, probe_elf)
    probe = boot_handoff.emulate(
        simulator,
        root / boot_handoff.ROT_CONFIG,
        probe_elf,
        timeout,
        signature=part_b_dir / "rot-inputs.sig",
    )
    _require(
        probe.verdict == "success" and len(probe.signature) == 3,
        "RoT probe did not supply lifecycle, entropy, and floor",
    )
    lifecycle, health, floor = probe.signature
    _require(0 <= lifecycle < len(boot_handoff.LIFECYCLES), "RoT probe supplied unknown lifecycle")
    entropy = int(bool((health >> 32) & 1) and not bool((health >> 33) & 1))
    inputs = boot_handoff.RotInputs(lifecycle, entropy, 0, floor)

    binary, host_compiler = boot_handoff.compile_rot_stage(root, part_b_dir)
    host_stage_sha = receipts.digest(binary)

    b_built, b_release, b_htif, b_code, b_records, b_trace_sha, b_log_sha, b_elf_bytes = (
        _run_composed_variant(
            root,
            part_b_dir / "positive",
            stage,
            consumer,
            lay,
            signer,
            binary,
            inputs,
            simulator,
            profile,
            timeout,
        )
    )
    _require(
        b_built.symbols["retired_object"] == retired_object,
        "retired object disagrees with declared bitmap word",
    )
    _require(
        len(b_built.payload) <= lay["BRINGUP_MMODE_REGION_BYTES"],
        "kernel payload exceeds declared M-mode image region",
    )
    expected_regs = boot_handoff.expected_registers(
        root,
        lay,
        inputs,
        hashlib.shake_256(b_built.payload).digest(lay["BOOT_DIGEST_BYTES"]),
    )
    _require(
        tuple(b_release.get(k) for k in ("generation", "device", "chain")) == expected_regs,
        "kernel release measurement registers disagree with owner",
    )

    b_observed = kernel_target.observations(b_records, b_built.symbols, bitmap)
    _require(
        b_htif == "pass" and b_code == 0 and all(bool(v) for v in b_observed.values()),
        f"Part B positive composed replay failed: {b_htif} ({b_code}), {b_observed}",
    )

    kt_rows = kernel_target.control_sources(stage, consumer)
    switch_ctrl_dir = part_b_dir / "kernel-target-controls/wrong-c-switch-build"
    switch_ctrl_dir.mkdir(parents=True, exist_ok=True)
    switch_parts = [
        (root / f"kernel/src/{name}.c").read_text(encoding="utf-8")
        for name in ("context", "executive", "partition", "handoff", "target")
    ]
    switch_parts[0] = kernel_target.replace_once(
        switch_parts[0],
        "    post->reg[r] = succ->reg[r];",
        "    if (r != 7u) { post->reg[r] = succ->reg[r]; }",
    )
    switch_unit = switch_ctrl_dir / "target_unit.c"
    switch_unit.write_text("\n".join(switch_parts), encoding="utf-8", newline="\n")
    switch_compile = compiler_diff.compile_c(
        compiler_argv, switch_unit, switch_ctrl_dir / "compiler", timeout
    )
    if switch_compile.exit_code != 0 or switch_compile.stream is None:
        raise ValueError(f"wrong-c-switch mutant is stillborn: {switch_compile.said}")
    kt_rows.append((
        "wrong-c-switch",
        stage,
        _part_b_consumer(switch_compile.stream, lay["INIT_MAGIC"], windows, bitmap),
        "complete_restores",
    ))
    kt_controls_summary: list[dict[str, object]] = []
    for ctrl_name, bad_stage, bad_consumer, decisive in kt_rows:
        c_built, _, c_htif, c_code, c_records, c_trace_sha, _, c_elf_bytes = (
            _run_composed_variant(
                root,
                part_b_dir / "kernel-target-controls" / ctrl_name,
                bad_stage,
                bad_consumer,
                lay,
                signer,
                binary,
                inputs,
                simulator,
                profile,
                timeout,
            )
        )
        c_obs = kernel_target.observations(c_records, c_built.symbols, bitmap)
        entered = any(
            kind == "I" and fields[0] == c_built.symbols["kernel_entry"]
            for kind, fields in c_records
        )
        matched = (
            (c_htif == "fail" and c_code == decisive)
            if isinstance(decisive, int)
            else (c_htif == "pass" and c_obs[decisive] is False)
        )
        _require(
            entered and matched,
            f"kernel_target control {ctrl_name} failed: entered={entered} htif={c_htif} "
            f"code={c_code} decisive={decisive}",
        )
        kt_controls_summary.append({
            "name": ctrl_name,
            "matched": True,
            "htif": c_htif,
            "htif_code": c_code,
            "decisive": decisive,
            "elf_sha256": _sha256(c_elf_bytes),
            "trace_sha256": c_trace_sha,
        })

    # Q46b composed-kernel adapter overflow control (timer_epoch = 0xfffffffffffff000).
    overflow_consumer = kernel_target.replace_once(
        consumer,
        "    li x5, timer_epoch\n    csetaddr c19, c18, x5\n    sd x6, 0(c19)",
        "    li x5, timer_epoch\n    csetaddr c19, c18, x5\n    li x6, 0xfffffffffffff000\n    sd x6, 0(c19)",
    )
    ov_built, ov_rel, ov_htif, ov_code, ov_records, ov_trace_sha, ov_log_sha, ov_elf_bytes = (
        _run_composed_variant(
            root,
            part_b_dir / "controls/adapter-epoch-overflow",
            stage,
            overflow_consumer,
            lay,
            signer,
            binary,
            inputs,
            simulator,
            profile,
            timeout,
        )
    )
    ov_release_called = any(
        kind == "I" and fields[0] == ov_built.symbols["vos_target_release"]
        for kind, fields in ov_records
    )
    ov_x10_at_fail: int | None = None
    for kind, fields in ov_records:
        if kind == "X" and fields[0] == 10:
            ov_x10_at_fail = fields[2]
        if kind == "I" and fields[0] == ov_built.symbols["kernel_fail"]:
            break
    ov_mtimecmp_written = any(kind == "W" and fields[0] == compare for kind, fields in ov_records)
    ov_p1_entered = any(
        kind == "I"
        and ov_built.symbols["partition_one"] <= fields[0] < ov_built.symbols["partition_one_end"]
        for kind, fields in ov_records
    )
    ov_p2_entered = any(
        kind == "I"
        and ov_built.symbols["partition_two"] <= fields[0] < ov_built.symbols["partition_two_end"]
        for kind, fields in ov_records
    )
    _require(
        ov_htif == "fail"
        and ov_code == 22
        and ov_release_called
        and ov_x10_at_fail == 0
        and not ov_mtimecmp_written
        and not ov_p1_entered
        and not ov_p2_entered,
        f"adapter-epoch-overflow check failed: htif={ov_htif} code={ov_code} "
        f"called={ov_release_called} x10={ov_x10_at_fail} mtimecmp={ov_mtimecmp_written} "
        f"p1={ov_p1_entered} p2={ov_p2_entered}",
    )

    # Negative control: remove `beqz x10, kernel_fail` after `call vos_target_release`.
    unguarded_consumer = kernel_target.replace_once(
        overflow_consumer,
        "    call vos_target_release\n    li gp, 22\n    beqz x10, kernel_fail\n    cspecialrw c18, mtdc, cnull",
        "    call vos_target_release\n    li gp, 22\n    cspecialrw c18, mtdc, cnull",
    )
    ug_built, ug_rel, ug_htif, ug_code, ug_records, ug_trace_sha, ug_log_sha, ug_elf_bytes = (
        _run_composed_variant(
            root,
            part_b_dir / "controls/mutated-unguarded-target-release",
            stage,
            unguarded_consumer,
            lay,
            signer,
            binary,
            inputs,
            simulator,
            profile,
            timeout,
        )
    )
    ug_mtimecmp_written = any(kind == "W" and fields[0] == compare for kind, fields in ug_records)
    ug_p1_entered = any(
        kind == "I"
        and ug_built.symbols["partition_one"] <= fields[0] < ug_built.symbols["partition_one_end"]
        for kind, fields in ug_records
    )
    _require(
        ug_mtimecmp_written and ug_p1_entered and not (ug_htif == "fail" and ug_code == 22),
        f"mutated-unguarded-target-release was not detected as unguarded: htif={ug_htif} "
        f"code={ug_code} mtimecmp={ug_mtimecmp_written} p1={ug_p1_entered}",
    )

    part_b_controls: dict[str, object] = {
        "adapter-epoch-overflow": {
            "name": "adapter-epoch-overflow",
            "part": "B",
            "kind": "adapter-overflow-control",
            "expected_verdict": "fail",
            "expected_code": 22,
            "verdict": ov_htif,
            "code": ov_code,
            "vos_target_release_called": ov_release_called,
            "vos_target_release_returned_zero": ov_x10_at_fail == 0,
            "mtimecmp_written": ov_mtimecmp_written,
            "partition_one_entered": ov_p1_entered,
            "partition_two_entered": ov_p2_entered,
            "elf_sha256": _sha256(ov_elf_bytes),
            "trace_records": len(ov_records),
            "trace_sha256": ov_trace_sha,
            "raw_log_sha256": ov_log_sha,
            "release": ov_rel,
            "passed": True,
        },
        "mutated-unguarded-target-release": {
            "name": "mutated-unguarded-target-release",
            "part": "B",
            "kind": "assembly-mutation",
            "expected_verdict": "detected-unguarded-dispatch",
            "verdict": ug_htif,
            "code": ug_code,
            "mtimecmp_written": ug_mtimecmp_written,
            "partition_one_entered": ug_p1_entered,
            "elf_sha256": _sha256(ug_elf_bytes),
            "trace_records": len(ug_records),
            "trace_sha256": ug_trace_sha,
            "raw_log_sha256": ug_log_sha,
            "release": ug_rel,
            "passed": True,
        },
    }

    controls_doc: dict[str, object] = {
        "scope": "Q46b purecap CHERI-CompCert & source-bound Sail target controls (Part A + Part B)",
        "part_a_controls": part_a_controls,
        "part_b_controls": part_b_controls,
        "kernel_target_controls": kt_controls_summary,
        "all_controls_passed": True,
        **NON_ACCEPTANCE_FLAGS,
    }
    controls_bytes = (json.dumps(controls_doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / "controls.json").write_bytes(controls_bytes)

    unchanged = (
        sources == receipts.inputs(root, *kernel_target.INPUTS)
        and model_sources == receipts.inputs(root, "model")
        and compiler_sha == receipts.digest(ccomp)
        and compcert_ini_sha == receipts.digest(config_path)
        and simulator_sha == receipts.digest(simulator)
        and build_sha == receipts.digest(build_receipt)
        and profile_sha == receipts.digest(profile)
        and private_inputs == compiler_inputs(effective_args)
        and host_cc_sha == receipts.digest(Path(host_cc))
        and host_stage_sha == receipts.digest(binary)
    )
    if provenance_files and not compiler_provenance.unchanged(provenance_files):
        raise ValueError("contained compiler build receipt changed during execution")
    _require(unchanged, "campaign inputs changed during execution")

    report: dict[str, object] = {
        "scope": (
            "Q46b purecap CHERI-CompCert & source-bound Sail target replay: Part A standalone "
            "clock-horizon harness and Part B composed two-slot kernel + adapter overflow control"
        ),
        "milestone_acceptance": "open",
        "compiler_provenance": compiler_prov,
        "compiler_receipts_sha256": provenance_files,
        "compiler_sha256": compiler_sha,
        "compcert_ini_sha256": compcert_ini_sha,
        "qualified_target_entry_producer_refusal": producer_refusal,
        "simulator_sha256": simulator_sha,
        "build_receipt_sha256": build_sha,
        "simulator_receipt": sim_meta,
        "profile_sha256": profile_sha,
        "host_compiler": host_compiler,
        "host_compiler_sha256": host_cc_sha,
        "host_stage_sha256": host_stage_sha,
        "private_compiler_inputs": private_inputs,
        "sources": sources,
        "model_sources": model_sources,
        "compilation": {
            "argv": list(compiled_unit.argv),
            "stream_sha256": compiled_unit.stream_sha256,
            "preprocessed_sha256": compiled_unit.preprocessed.sha256,
        },
        "part_a": {
            "verdict": a_htif,
            "code": a_code,
            "elf_sha256": _sha256(part_a_elf_bytes),
            "trace_records": len(a_records),
            "trace_sha256": a_trace_sha,
            "raw_log_sha256": a_log_sha,
            "driver_compilation": {
                "stream_sha256": compiled_driver.stream_sha256,
                "preprocessed_sha256": compiled_driver.preprocessed.sha256,
            },
            "cases_covered": list(PART_A_CASES),
            "negative_controls_count": len(part_a_controls),
        },
        "part_b": {
            "verdict": b_htif,
            "code": b_code,
            "data_offset": PART_B_DATA_OFFSET,
            "payload_bytes": len(b_built.payload),
            "elf_sha256": _sha256(b_elf_bytes),
            "trace_records": len(b_records),
            "trace_sha256": b_trace_sha,
            "raw_log_sha256": b_log_sha,
            "source_sha256": _sha256(source.encode("utf-8")),
            "observations": b_observed,
            "release": b_release,
            "signer": signer.identity(),
            "kernel_target_controls_count": len(kt_controls_summary),
            "kernel_target_controls_passed": True,
            "q46b_controls_count": len(part_b_controls),
        },
        "controls_sha256": _sha256(controls_bytes),
        "part_a_passed": True,
        "part_b_passed": True,
        "negative_controls_passed": True,
        "inputs_unchanged": unchanged,
        "ok": True,
        **NON_ACCEPTANCE_FLAGS,
    }
    report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / "report.json").write_bytes(report_bytes)

    validate_bundle(report, controls_doc)
    return report


def _check_non_acceptance(doc: Mapping[str, object], label: str) -> None:
    for key, expected in NON_ACCEPTANCE_FLAGS.items():
        _require(
            key in doc and doc[key] is expected,
            f"{label}: {key} must be {expected!r}, got {doc.get(key)!r}",
        )


def _check_sha256(value: object, label: str) -> None:
    _require(
        isinstance(value, str) and bool(_SHA256_RE.fullmatch(value)),
        f"{label}: invalid SHA-256 {value!r}",
    )


def validate_bundle(report: Mapping[str, object], controls: Mapping[str, object]) -> None:
    """Validate `report.json` and `controls.json` invariants, digests, and control verdicts."""
    _check_non_acceptance(report, "report")
    _check_non_acceptance(controls, "controls")
    _require(
        report.get("milestone_acceptance") == "open",
        f"report: milestone_acceptance must be 'open', got {report.get('milestone_acceptance')!r}",
    )
    refusal = report.get("qualified_target_entry_producer_refusal")
    _require(
        isinstance(refusal, str) and bool(refusal.strip()),
        "report: missing qualified_target_entry_producer_refusal",
    )
    for key in (
        "compiler_sha256",
        "compcert_ini_sha256",
        "simulator_sha256",
        "build_receipt_sha256",
        "profile_sha256",
        "controls_sha256",
    ):
        _check_sha256(report.get(key), f"report.{key}")

    _require(report.get("ok") is True, "report: ok must be True")
    _require(report.get("inputs_unchanged") is True, "report: inputs_unchanged must be True")
    _require(report.get("part_a_passed") is True, "report: part_a_passed must be True")
    _require(report.get("part_b_passed") is True, "report: part_b_passed must be True")
    _require(
        report.get("negative_controls_passed") is True,
        "report: negative_controls_passed must be True",
    )

    part_a = report.get("part_a")
    _require(isinstance(part_a, Mapping), "report: missing part_a object")
    a_map = cast(Mapping[str, object], part_a)
    _require(
        a_map.get("verdict") == "pass" and a_map.get("code") == 0,
        f"report.part_a: expected pass (0), got {a_map.get('verdict')} ({a_map.get('code')})",
    )
    _require(
        type(a_map.get("trace_records")) is int and cast(int, a_map["trace_records"]) > 0,
        "report.part_a: trace_records must be positive",
    )
    for key in ("elf_sha256", "trace_sha256", "raw_log_sha256"):
        _check_sha256(a_map.get(key), f"report.part_a.{key}")
    _require(
        a_map.get("cases_covered") == list(PART_A_CASES),
        "report.part_a: cases_covered mismatch",
    )

    part_b = report.get("part_b")
    _require(isinstance(part_b, Mapping), "report: missing part_b object")
    b_map = cast(Mapping[str, object], part_b)
    _require(
        b_map.get("verdict") == "pass" and b_map.get("code") == 0,
        f"report.part_b: expected pass (0), got {b_map.get('verdict')} ({b_map.get('code')})",
    )
    _require(
        type(b_map.get("trace_records")) is int and cast(int, b_map["trace_records"]) > 0,
        "report.part_b: trace_records must be positive",
    )
    for key in ("elf_sha256", "trace_sha256", "raw_log_sha256", "source_sha256"):
        _check_sha256(b_map.get(key), f"report.part_b.{key}")
    obs = b_map.get("observations")
    _require(isinstance(obs, Mapping), "report.part_b: missing observations")
    obs_map = cast(Mapping[str, object], obs)
    _require(
        obs_map.get("restore_count") == SLOTS
        and all(
            v is True
            for k, v in obs_map.items()
            if k != "restore_count"
        ),
        f"report.part_b.observations: failed observations: {obs_map}",
    )
    _require(
        b_map.get("kernel_target_controls_passed") is True,
        "report.part_b: kernel_target_controls_passed must be True",
    )

    _require(controls.get("all_controls_passed") is True, "controls: all_controls_passed must be True")

    a_ctrls = controls.get("part_a_controls")
    _require(isinstance(a_ctrls, Mapping), "controls: missing part_a_controls")
    a_ctrl_map = cast(Mapping[str, object], a_ctrls)
    expected_a = {spec[0] for spec in PART_A_NEGATIVE_CONTROLS}
    _require(
        set(a_ctrl_map.keys()) == expected_a,
        f"controls.part_a_controls: expected all 4 controls, got {sorted(a_ctrl_map.keys())}",
    )
    for name in expected_a:
        raw_entry = a_ctrl_map[name]
        _require(isinstance(raw_entry, Mapping), f"controls.part_a_controls.{name}: must be object")
        entry = cast(Mapping[str, object], raw_entry)
        _require(entry.get("passed") is True, f"controls.part_a_controls.{name}: passed must be True")
        _require(
            entry.get("verdict") == "fail",
            f"controls.part_a_controls.{name}: expected verdict 'fail', got {entry.get('verdict')!r}",
        )
        code = entry.get("code")
        _require(
            type(code) is int and code != 0,
            f"controls.part_a_controls.{name}: expected nonzero code, got {code!r}",
        )
        for key in ("elf_sha256", "trace_sha256", "raw_log_sha256"):
            _check_sha256(entry.get(key), f"controls.part_a_controls.{name}.{key}")

    b_ctrls = controls.get("part_b_controls")
    _require(isinstance(b_ctrls, Mapping), "controls: missing part_b_controls")
    b_ctrl_map = cast(Mapping[str, object], b_ctrls)
    _require(
        set(b_ctrl_map.keys()) == set(PART_B_CONTROLS),
        f"controls.part_b_controls: expected {sorted(PART_B_CONTROLS)}, got {sorted(b_ctrl_map.keys())}",
    )

    ov_raw = b_ctrl_map["adapter-epoch-overflow"]
    _require(isinstance(ov_raw, Mapping), "controls.part_b_controls.adapter-epoch-overflow: must be object")
    ov = cast(Mapping[str, object], ov_raw)
    _require(
        ov.get("passed") is True
        and ov.get("verdict") == "fail"
        and ov.get("code") == 22
        and ov.get("vos_target_release_called") is True
        and ov.get("vos_target_release_returned_zero") is True
        and ov.get("mtimecmp_written") is False
        and ov.get("partition_one_entered") is False
        and ov.get("partition_two_entered") is False,
        f"controls.part_b_controls.adapter-epoch-overflow: invariant failure: {ov}",
    )
    for key in ("elf_sha256", "trace_sha256", "raw_log_sha256"):
        _check_sha256(ov.get(key), f"controls.part_b_controls.adapter-epoch-overflow.{key}")

    ug_raw = b_ctrl_map["mutated-unguarded-target-release"]
    _require(
        isinstance(ug_raw, Mapping),
        "controls.part_b_controls.mutated-unguarded-target-release: must be object",
    )
    ug = cast(Mapping[str, object], ug_raw)
    _require(
        ug.get("passed") is True
        and ug.get("mtimecmp_written") is True
        and ug.get("partition_one_entered") is True
        and not (ug.get("verdict") == "fail" and ug.get("code") == 22),
        f"controls.part_b_controls.mutated-unguarded-target-release: invariant failure: {ug}",
    )
    for key in ("elf_sha256", "trace_sha256", "raw_log_sha256"):
        _check_sha256(
            ug.get(key), f"controls.part_b_controls.mutated-unguarded-target-release.{key}"
        )

    kt_list = controls.get("kernel_target_controls")
    _require(isinstance(kt_list, list), "controls: kernel_target_controls must be a list")
    kt_names: set[str] = set()
    for item in cast(list[object], kt_list):
        _require(isinstance(item, Mapping), "controls.kernel_target_controls entry must be object")
        item_map = cast(Mapping[str, object], item)
        name = item_map.get("name")
        _require(isinstance(name, str), "controls.kernel_target_controls entry missing name")
        _require(
            item_map.get("matched") is True,
            f"controls.kernel_target_controls.{name}: matched must be True",
        )
        kt_names.add(cast(str, name))
    _require(
        kt_names == set(KERNEL_TARGET_CONTROL_NAMES),
        f"controls.kernel_target_controls: expected {sorted(KERNEL_TARGET_CONTROL_NAMES)}, "
        f"got {sorted(kt_names)}",
    )


def validate_bundle_dir(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read, hash-verify, and validate `report.json` and `controls.json` in `bundle_dir`."""
    report_bytes = (bundle_dir / "report.json").read_bytes()
    controls_bytes = (bundle_dir / "controls.json").read_bytes()
    report = json.loads(report_bytes.decode("utf-8"))
    controls = json.loads(controls_bytes.decode("utf-8"))
    _require(
        isinstance(report, dict) and isinstance(controls, dict),
        "bundle JSON artifacts must be objects",
    )
    _require(
        report.get("controls_sha256") == _sha256(controls_bytes),
        "report: controls_sha256 disagrees with controls.json bytes",
    )
    validate_bundle(report, controls)
    return report, controls


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Q46b purecap CHERI-CompCert & Sail target replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--ccomp-arg", action="append", default=[])
    parser.add_argument("--simulator", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)
    report = run(
        args.checkout,
        args.compiler,
        list(args.ccomp_arg),
        args.simulator,
        args.build_receipt,
        args.output,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
