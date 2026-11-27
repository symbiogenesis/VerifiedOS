# SPDX-License-Identifier: Apache-2.0
"""Differential Python/C17 checks and compiled behavioral mutation kills for inference admission."""

import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from itertools import product
from pathlib import Path

from tests.harness import Case, ensure
from vos import inference_admission as py_admission
from vos import inference_grant as py_grant
from vos import inference_residency as py_residency
from vos import toolenv
from vos.inference_contract import Ceiling, Costs, Refusal, Shape

ROOT = Path(__file__).resolve().parents[2]
COMP_DIR = ROOT / "inference-admission"
HEADER_PATH = COMP_DIR / "include" / "vos_inference_admission.h"
SOURCE_PATH = COMP_DIR / "src" / "inference_admission.c"
TEST_C_PATH = COMP_DIR / "test" / "test_inference_admission.c"

REFUSAL_TO_INT: dict[Refusal, int] = {
    Refusal.DESCRIPTOR_NOT_CANONICAL: 1,
    Refusal.RESIDENT_BYTES_ABOVE_CEILING: 2,
    Refusal.CONTEXT_ABOVE_CEILING: 3,
    Refusal.FORMAT_NOT_ADMITTED: 4,
    Refusal.EXPERT_COUNT_ABOVE_CEILING: 5,
    Refusal.TOP_K_NOT_THE_FIXED_VALUE: 6,
    Refusal.KV_PER_TOKEN_ABOVE_CEILING: 7,
    Refusal.PER_TOKEN_BYTES_NOT_DECLARED: 8,
    Refusal.SESSION_POOL_EXHAUSTED: 9,
    Refusal.TOKEN_RATE_ABOVE_GRANT: 10,
    Refusal.EXPERT_NOT_RESIDENT: 11,
    Refusal.ROUTED_FETCH_ACROSS_STORAGE: 12,
    Refusal.ROUTE_NOT_QUALIFIED: 13,
}

type Widths = tuple[int, int, int, int, int, int]


def _shape_fields(shape: Shape) -> tuple[int, int, int, int, int, int]:
    return (
        shape.resident_bytes,
        shape.context_length,
        shape.format,
        shape.expert_count,
        shape.top_k,
        shape.kv_bytes_per_token,
    )


def _py_shape_fits(widths: Widths, shape: Shape) -> bool:
    if any(w < 0 or w > 8 for w in widths):
        return False
    return all(val < (1 << (8 * w)) for w, val in zip(widths, _shape_fields(shape), strict=True))


def _py_encode_shape(widths: Widths, shape: Shape) -> bytes | None:
    if not _py_shape_fits(widths, shape):
        return None
    out = bytearray()
    for w, val in zip(widths, _shape_fields(shape), strict=True):
        out.extend(val.to_bytes(w, "little"))
    return bytes(out)


def _py_decode_shape(widths: Widths, raw: bytes) -> Shape | None:
    if any(w < 0 or w > 8 for w in widths):
        return None
    if len(raw) != sum(widths):
        return None
    vals: list[int] = []
    pos = 0
    for w in widths:
        vals.append(int.from_bytes(raw[pos:pos + w], "little"))
        pos += w
    return Shape(*vals)


def _python_codec_and_admission_reference() -> None:
    widths: Widths = (2, 2, 2, 2, 2, 2)
    shape = Shape(40, 64, 4, 8, 2, 10)
    raw = _py_encode_shape(widths, shape)
    ensure(raw is not None and len(raw) == 12, "demo shape must encode to 12 bytes")
    if raw is None:
        return
    ensure(_py_decode_shape(widths, raw) == shape, "canonical round-trip failed")
    ensure(_py_decode_shape(widths, raw + b"\x00") is None, "trailing byte accepted")
    ensure(_py_decode_shape(widths, raw[:-1]) is None, "truncated descriptor accepted")
    ensure(_py_encode_shape((0, 1, 1, 1, 1, 1), Shape(1, 0, 0, 0, 0, 0)) is None,
           "nonzero value in zero-width field accepted")
    mixed: Widths = (8, 1, 0, 2, 1, 4)
    boundary = Shape((1 << 64) - 1, 255, 0, 65535, 2, 100000)
    enc = _py_encode_shape(mixed, boundary)
    ensure(enc is not None and _py_decode_shape(mixed, enc) == boundary,
           "mixed width boundary round-trip failed")

    ceiling = Ceiling(50, 64, (4, 5), 8, 2, 16, 200)
    server = py_admission.Server(40, (0, 1), 60, 1)
    step = py_admission.opening(shape, ceiling, (True,) * 8, py_grant.KvPlacement.BANK, server, 0, 4)
    ensure(step.refusal is None and step.admitted_rate == 4 and step.sessions_open == 1,
           "reference bank admission mismatch")
    step_weights = py_admission.opening(
        shape, ceiling, (True,) * 8, py_grant.KvPlacement.OUTSIDE_BANK, server, 0, 5)
    ensure(step_weights.refusal is None and step_weights.admitted_rate == 5,
           "reference weights-only admission mismatch")


def _c_sources_and_contract_alignment() -> None:
    for path in (HEADER_PATH, SOURCE_PATH, TEST_C_PATH):
        ensure(path.is_file(), f"missing C deliverable: {path}")
        text = path.read_text(encoding="utf-8")
        ensure(text.startswith("// SPDX-License-Identifier: Apache-2.0\n"),
               f"invalid SPDX line in {path}")
    header = HEADER_PATH.read_text(encoding="utf-8")
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for symbol in (
        "vos_inf_composition_opening",
        "vos_inf_checked_routed_work",
        "VOS_INF_ROUTED_FETCH_ACROSS_STORAGE",
        "VOS_KV_WEIGHTS_ONLY",
        "VOS_KV_WEIGHTS_AND_CACHE",
    ):
        ensure(symbol in header and symbol in source,
               f"required symbol missing across header/source: {symbol}")
    alloc_pattern = re.compile(r"\b(malloc|calloc|realloc|free)\s*\(")
    for path, text in ((HEADER_PATH, header), (SOURCE_PATH, source)):
        ensure(alloc_pattern.search(text) is None,
               f"dynamic memory allocation forbidden by GC-free C17 profile: {path}")


def _clang_supports_sanitizers(clang: str, work_dir: Path) -> bool:
    probe_c = work_dir / "_san_probe.c"
    probe_bin = work_dir / "_san_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    done = subprocess.run(
        [clang, "-std=c17", "-fsanitize=address,undefined", str(probe_c), "-o", str(probe_bin)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return done.returncode == 0


def _compile_c(work_dir: Path, source_override: str | None = None) -> list[Path]:
    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None or gcc is not None,
           "clang or gcc is required for native C17 verification")
    work_dir.mkdir(parents=True, exist_ok=True)
    c_src = SOURCE_PATH
    if source_override is not None:
        c_src = work_dir / "inference_admission.c"
        c_src.write_text(source_override, encoding="utf-8", newline="")

    common = [
        "-std=c17", "-O1", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
        "-pedantic", "-I" + str(COMP_DIR / "include"), str(c_src), str(TEST_C_PATH),
    ]
    san_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    binaries: list[Path] = []

    if clang is not None:
        has_san = _clang_supports_sanitizers(clang, work_dir)
        clang_bin = work_dir / "test_inference_admission_clang"
        flags = [*common, *(san_flags if has_san else []), "-o", str(clang_bin)]
        done = subprocess.run([clang, *flags], capture_output=True, text=True,
                              timeout=60, check=False)
        ensure(done.returncode == 0,
               f"C17 clang compile failed (not a mutant kill): {done.stderr}")
        binaries.append(clang_bin)
        if not has_san:
            ensure(gcc is not None,
                   "gcc is required for ASan/UBSan when clang lacks libclang_rt")
            if gcc is not None:
                gcc_bin = work_dir / "test_inference_admission_san"
                done_san = subprocess.run(
                    [gcc, *common, *san_flags, "-o", str(gcc_bin)],
                    capture_output=True, text=True, timeout=60, check=False,
                )
                ensure(done_san.returncode == 0,
                       f"C17 gcc ASan/UBSan compile failed (not a mutant kill): {done_san.stderr}")
                binaries.append(gcc_bin)
    elif gcc is not None:
        gcc_bin = work_dir / "test_inference_admission_san"
        done_san = subprocess.run(
            [gcc, *common, *san_flags, "-o", str(gcc_bin)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(done_san.returncode == 0,
               f"C17 gcc ASan/UBSan compile failed (not a mutant kill): {done_san.stderr}")
        binaries.append(gcc_bin)

    return binaries


def _run_c_controls(binary: Path) -> None:
    done = subprocess.run([str(binary), "controls"], capture_output=True, text=True,
                          timeout=30, check=False)
    ensure(done.returncode == 0,
           f"C controls failed ({done.returncode}): {done.stdout} {done.stderr}")


def _eval_lines(binary: Path, lines: list[str]) -> list[str]:
    payload = "\n".join(lines) + "\n"
    done = subprocess.run([str(binary), "--eval"], input=payload, capture_output=True,
                          text=True, timeout=60, check=False)
    ensure(done.returncode == 0,
           f"C --eval harness failed ({done.returncode}): {done.stderr}")
    out_lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    ensure(len(out_lines) == len(lines),
           f"eval response line count mismatch: expected {len(lines)}, got {len(out_lines)}")
    return out_lines


def _encode_cmd(widths: Widths, shape: Shape) -> str:
    return "ENCODE " + " ".join(str(x) for x in (*widths, *_shape_fields(shape)))


def _decode_cmd(widths: Widths, raw: bytes) -> str:
    hex_str = "-" if len(raw) == 0 else raw.hex()
    return f"DECODE {' '.join(str(w) for w in widths)} {len(raw)} {hex_str}"


def _open_cmd(mode: int, widths: Widths, ceiling: Ceiling, costs: Costs,
              residency: tuple[bool, ...], placement: py_grant.KvPlacement,
              server: py_admission.Server, sessions_open: int,
              requested_rate: int, desc: bytes) -> str:
    place_int = 1 if placement is py_grant.KvPlacement.BANK else 0
    hex_str = "-" if len(desc) == 0 else desc.hex()
    parts = [
        mode,
        *widths,
        ceiling.max_resident_bytes,
        ceiling.max_context_length,
        len(ceiling.admitted_formats),
        *ceiling.admitted_formats,
        ceiling.max_expert_count,
        ceiling.fixed_top_k,
        ceiling.max_kv_bytes_per_token,
        ceiling.ceiling_grant,
        costs.dense_work_per_token,
        costs.expert_work_per_token,
        costs.fetch_penalty,
        len(residency),
        *(1 if flag else 0 for flag in residency),
        place_int,
        server.slot,
        server.pool_bytes,
        server.session_capacity,
        sessions_open,
        requested_rate,
        len(desc),
        hex_str,
    ]
    return "OPEN " + " ".join(str(x) for x in parts)


def _differential_check(binary: Path, *, thorough: bool = True) -> None:
    _run_c_controls(binary)

    commands: list[str] = []
    expected: list[str] = []

    # 1. Canonical codec differential checks (round-trip, bounds, trailing & truncated bytes).
    width_sets: list[Widths] = [
        (2, 2, 2, 2, 2, 2),
        (8, 4, 1, 2, 1, 4),
        (0, 1, 0, 1, 1, 0),
    ]
    sample_shapes = [
        Shape(0, 0, 0, 0, 0, 0),
        Shape(40, 64, 4, 8, 2, 10),
        Shape(50, 64, 5, 8, 2, 16),
        Shape(255, 255, 0, 255, 255, 0),
        Shape((1 << 64) - 1, (1 << 32) - 1, 255, 65535, 255, (1 << 32) - 1),
    ]
    for widths in width_sets:
        for shape in sample_shapes:
            enc = _py_encode_shape(widths, shape)
            commands.append(_encode_cmd(widths, shape))
            if enc is None:
                expected.append("ERR")
            else:
                hex_str = "-" if len(enc) == 0 else enc.hex()
                expected.append(f"OK {len(enc)} {hex_str}")
                commands.append(_decode_cmd(widths, enc))
                expected.append("OK " + " ".join(str(v) for v in _shape_fields(shape)))
                commands.append(_decode_cmd(widths, enc + b"\x00"))
                expected.append("ERR")
                if len(enc) > 0:
                    commands.append(_decode_cmd(widths, enc[:-1]))
                    expected.append("ERR")

    # 2. Opening & composition_opening differential checks against Python contract.
    widths = (2, 2, 2, 2, 2, 2)
    ceiling = Ceiling(50, 64, (4, 5), 8, 2, 16, 200)
    costs = Costs(10, 3, 5)
    server = py_admission.Server(40, (0, 1), 60, 2)
    base = Shape(40, 64, 4, 4, 2, 10)
    candidates = [
        base,
        Shape(50, 64, 5, 8, 2, 16),
        replace(base, resident_bytes=51),
        replace(base, context_length=65),
        replace(base, format=6),
        replace(base, expert_count=9),
        replace(base, top_k=3),
        replace(base, kv_bytes_per_token=17),
        replace(base, resident_bytes=0, kv_bytes_per_token=0),
    ]
    residency_cases: list[tuple[bool, ...]] = [
        (True,) * 8,
        (False, True, True, True, True, True, True, True),
        (True, True),
    ]
    occupancies = (0, 1, 2, 3) if thorough else (0, 2)
    rates = (0, 3, 4, 5, 6) if thorough else (4, 5)
    for cand in candidates:
        desc = _py_encode_shape(widths, cand)
        ensure(desc is not None, "test shape must fit 2-byte widths")
        if desc is None:
            continue
        for res in residency_cases:
            for placement in (py_grant.KvPlacement.BANK, py_grant.KvPlacement.OUTSIDE_BANK):
                for occ in occupancies:
                    for req_rate in rates:
                        step = py_admission.opening(
                            cand, ceiling, res, placement, server, occ, req_rate)
                        commands.append(_open_cmd(
                            1, widths, ceiling, costs, res, placement, server, occ, req_rate, desc))
                        if step.refusal is None:
                            expected.append(
                                f"ADMIT {step.admitted_rate} {step.sessions_open} "
                                f"{server.slot} {server.pool_bytes} {server.session_capacity}")
                        else:
                            expected.append(
                                f"REFUSE {REFUSAL_TO_INT[step.refusal]} {step.sessions_open} "
                                f"{server.slot} {server.pool_bytes} {server.session_capacity}")
        # Trailing-byte descriptor refusal.
        commands.append(_open_cmd(
            1, widths, ceiling, costs, (True,) * 8, py_grant.KvPlacement.BANK,
            server, 0, 1, desc + b"\x00"))
        expected.append(
            f"REFUSE {REFUSAL_TO_INT[Refusal.DESCRIPTOR_NOT_CANONICAL]} 0 "
            f"{server.slot} {server.pool_bytes} {server.session_capacity}")

    # 3. Residency, routed work, serve, and ensemble differential checks.
    work_shape = Shape(40, 64, 4, 4, 2, 10)
    for res in product((False, True), repeat=4):
        for route in ((0, 1), (2, 3), (1, 1), (0, 4), (0,)):
            work = py_residency.checked_routed_work(work_shape, costs, res, route)
            parts = [
                *_shape_fields(work_shape),
                costs.dense_work_per_token,
                costs.expert_work_per_token,
                costs.fetch_penalty,
                len(res),
                *(1 if flag else 0 for flag in res),
                len(route),
                *route,
            ]
            commands.append("WORK " + " ".join(str(x) for x in parts))
            expected.append("ERR" if work is None else f"OK {work}")
        for expert in range(5):
            fetched = py_residency.serve(res, expert)
            commands.append(
                f"SERVE {len(res)} {' '.join('1' if f else '0' for f in res)} {expert}")
            if isinstance(fetched, py_residency.FromResidentBank):
                expected.append(f"BANK {fetched.expert}")
            else:
                expected.append(
                    f"REFUSE {REFUSAL_TO_INT[Refusal.ROUTED_FETCH_ACROSS_STORAGE]}")

    for members in (
        ((200, 50), (180, 60)),
        ((200, 40), (180, 60), (500, 100)),
        ((200, 0), (180, 60)),
    ):
        flat = " ".join(f"{g} {b}" for g, b in members)
        commands.append(f"ENSEMBLE {len(members)} {flat}")
        rates = [py_grant.admitted_rate(g, b) for g, b in members]
        valid_rates = [r for r in rates if r is not None]
        if len(valid_rates) != len(members):
            expected.append("ERR")
        else:
            expected.append(f"OK {min(valid_rates)}")

    actual = _eval_lines(binary, commands)
    for idx, (cmd, exp, act) in enumerate(zip(commands, expected, actual, strict=True)):
        ensure(act == exp,
               f"differential mismatch at case {idx} ({cmd}): expected {exp!r}, got {act!r}")


def _native_c_differential_and_sanitizers() -> None:
    if sys.platform == "win32":
        return
    work = toolenv.environment(ROOT, sys.platform).parent / "inference-admission-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as td:
        for binary in _compile_c(Path(td)):
            _differential_check(binary, thorough=True)


def _caught(fn: Callable[[], None], label: str) -> None:
    try:
        fn()
    except AssertionError:
        return
    raise AssertionError(f"compiled C mutant survived differential/control checks: {label}")


def _compiled_c_behavioral_mutants() -> None:
    if sys.platform == "win32":
        return
    source = SOURCE_PATH.read_text(encoding="utf-8")
    mutations: tuple[tuple[str, str, str], ...] = (
        (
            "accept trailing byte",
            "if (len != total || (len > 0u && bytes == NULL)) {",
            "if (len < total || (len > 0u && bytes == NULL)) {",
        ),
        (
            "accept over-ceiling field",
            "if (shape->resident_bytes > ceiling->max_resident_bytes) {",
            "if (shape->resident_bytes > ceiling->max_resident_bytes + 1u) {",
        ),
        (
            "degrade rate instead of refusing",
            "if (req->requested_tokens_per_second > max_rate) {",
            "if (req->requested_tokens_per_second > max_rate && max_rate == UINT64_MAX && srv->slot == UINT64_MAX) {",
        ),
        (
            "fetch nonresident expert from storage",
            "    return (vos_inf_fetch){\n"
            "        .kind = VOS_INF_FETCH_REFUSED,\n"
            "        .expert = expert,\n"
            "        .refusal = VOS_INF_ROUTED_FETCH_ACROSS_STORAGE\n"
            "    };",
            "    return (vos_inf_fetch){\n"
            "        .kind = VOS_INF_FROM_RESIDENT_BANK,\n"
            "        .expert = expert,\n"
            "        .refusal = VOS_INF_REFUSAL_NONE\n"
            "    };",
        ),
        (
            "expert-dependent work",
            "total += costs->expert_work_per_token;",
            "total += costs->expert_work_per_token + route[i];",
        ),
        (
            "overcommit session pool",
            "if (st.sessions_open >= srv->session_capacity) {",
            "if (st.sessions_open > srv->session_capacity) {",
        ),
    )
    work = toolenv.environment(ROOT, sys.platform).parent / "inference-admission-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mutants-", dir=work) as td:
        scratch = Path(td)
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift ({source.count(old)}): {label}")
            binaries = _compile_c(scratch / str(index), source.replace(old, new, 1))
            for binary in binaries:
                _caught(lambda b=binary: _differential_check(b, thorough=False), label)


def cases() -> list[Case]:
    return [
        Case("Python canonical codec and admission reference",
             _python_codec_and_admission_reference),
        Case("C17 source headers, GC-free profile and required symbols",
             _c_sources_and_contract_alignment),
        Case("Native C17 ASan/UBSan controls and Python differential checks",
             _native_c_differential_and_sanitizers, lane="guest"),
        Case("Compiled behavioral C17 mutation kills",
             _compiled_c_behavioral_mutants, lane="guest"),
    ]
