# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + mutation controls for replay/."""

import hashlib
import hmac
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import replay_record as rr
from vos import toolenv
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
REPLAY_DIR = ROOT / "replay"
REPLAY_H = REPLAY_DIR / "include" / "vos_replay_record.h"
REPLAY_C = REPLAY_DIR / "src" / "replay_record.c"
REPLAY_TEST_C = REPLAY_DIR / "test" / "test_replay_record.c"
REPLAY_README = REPLAY_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "ReplayRecord.v"

_WIRE_MAGIC = b"VOSRR01\x00"
_WIRE_EVENT_FIXED_BYTES = 84
_SOURCES = ("entropy", "link_address", "time_read", "physical_event")


@dataclass(frozen=True)
class _OracleWireEvent:
    seq: int
    point: rr.Point
    source: str
    payload_class: int
    interface_id: bytes
    payload: bytes


def _oracle_seal_entropy(
    seal_key: bytes,
    composition: bytes,
    input_trace: bytes,
    point: rr.Point,
    interface_id: bytes,
    raw_draw: bytes,
) -> bytes:
    msg = (
        b"VOSRRCM1"
        + composition
        + input_trace
        + point.slot.to_bytes(8, "little")
        + point.core.to_bytes(8, "little")
        + point.retire.to_bytes(8, "little")
        + point.ordinal.to_bytes(8, "little")
        + interface_id
        + len(raw_draw).to_bytes(4, "little")
        + raw_draw
    )
    return hmac.new(seal_key, msg, hashlib.sha256).digest()


def _oracle_encode_wire(
    base_root: bytes,
    composition: bytes,
    input_trace: bytes,
    events: tuple[_OracleWireEvent, ...],
) -> bytes:
    out = bytearray(_WIRE_MAGIC)
    out += len(base_root).to_bytes(4, "little")
    out += base_root
    out += composition
    out += input_trace
    out += len(events).to_bytes(4, "little")
    for ev in events:
        src_code = _SOURCES.index(ev.source)
        out += ev.seq.to_bytes(8, "little")
        out += ev.point.slot.to_bytes(8, "little")
        out += ev.point.core.to_bytes(8, "little")
        out += ev.point.retire.to_bytes(8, "little")
        out += ev.point.ordinal.to_bytes(8, "little")
        out += src_code.to_bytes(4, "little")
        out += ev.payload_class.to_bytes(4, "little")
        out += ev.interface_id
        out += len(ev.payload).to_bytes(4, "little")
        out += ev.payload
    return bytes(out)


def _oracle_wire_to_json(
    base_root: bytes,
    composition: bytes,
    input_trace: bytes,
    events: tuple[_OracleWireEvent, ...],
) -> bytes:
    body = {
        "schema": rr.SCHEMA,
        "binding": {
            "base_image_root": base_root.hex(),
            "composition": composition.hex(),
            "input_trace": input_trace.hex(),
        },
        "events": [
            {
                "seq": ev.seq,
                "point": {
                    "slot": ev.point.slot,
                    "core": ev.point.core,
                    "retire": ev.point.retire,
                    "ordinal": ev.point.ordinal,
                },
                "source": ev.source,
                "interface": ev.interface_id.hex(),
                "payload": {
                    "sealed_commitment" if ev.source == "entropy" else "value": ev.payload.hex(),
                },
            }
            for ev in events
        ],
    }
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _refused(fn: Callable[[], object]) -> None:
    try:
        fn()
    except rr.RecordError:
        return
    raise AssertionError("defective replay-record fixture was accepted")


def _oracle_and_host_cross_check() -> None:
    """Verify pure-Python reference semantics and cross-check against tools/vos/replay_record.py."""
    seal_key = bytes((0xA5 ^ (i * 7)) & 0xFF for i in range(32))
    base_root = b"\x00\x11\x22\x33"
    comp = bytes((0x11 + i) & 0xFF for i in range(32))
    trace = bytes((0x21 + i) & 0xFF for i in range(32))
    binding = rr.Binding(base_root.hex(), comp.hex(), trace.hex())

    iface_bytes = {src: bytes(((0x01 + idx * 0x10) + i) & 0xFF for i in range(32))
                   for idx, src in enumerate(_SOURCES)}
    interfaces = {
        iface_bytes[src].hex(): rr.Interface(src, 32 if src == "entropy" else 16)
        for src in _SOURCES
    }
    limits = rr.Limits(16_384, 8)

    secret_draw = bytes.fromhex("deadbeefcafebabe13374299aa557788")
    pt0 = rr.Point(0, 0, 0, 0)
    pt1 = rr.Point(0, 0, 1, 0)
    pt2 = rr.Point(0, 1, 0, 0)
    pt3 = rr.Point(1, 0, 1, 0)

    commitment = _oracle_seal_entropy(
        seal_key, comp, trace, pt0, iface_bytes["entropy"], secret_draw,
    )
    ensure(len(commitment) == 32 and secret_draw not in commitment,
           "commitment must be 32 bytes and must not expose raw entropy draw")

    pub_payloads = {
        "link_address": b"\x10\x02\x03\x04\x05\x06",
        "time_read": b"\x10\x00\x00\x01\x02\x03\x04\x05",
        "physical_event": b"\x10\xaa\xbb\xcc",
    }

    recorder = rr.FixtureRecorder(
        binding,
        limits=limits,
        interfaces=interfaces,
        validators={
            iface_bytes[s].hex(): (lambda b: len(b) >= 2 and b[0] == 0x10)
            for s in _SOURCES if s != "entropy"
        },
    )
    ensure(recorder.record(point=pt0, interface=iface_bytes["entropy"].hex(), produce=lambda: None) is None,
           "declined draw must not emit event")
    ev0 = recorder.record(point=pt0, interface=iface_bytes["entropy"].hex(), produce=lambda: commitment)
    ev1 = recorder.record(point=pt1, interface=iface_bytes["link_address"].hex(),
                          produce=lambda: pub_payloads["link_address"])
    ev2 = recorder.record(point=pt2, interface=iface_bytes["time_read"].hex(),
                          produce=lambda: pub_payloads["time_read"])
    ev3 = recorder.record(point=pt3, interface=iface_bytes["physical_event"].hex(),
                          produce=lambda: pub_payloads["physical_event"])
    ensure(ev0 is not None and ev1 is not None and ev2 is not None and ev3 is not None,
           "all four sources must record")

    blob = recorder.finish(expected=binding, expected_events=4)
    ensure(secret_draw.hex().encode("ascii") not in blob,
           "raw entropy draw hex leaked into JSON record")

    wire_events = (
        _OracleWireEvent(0, pt0, "entropy", 0, iface_bytes["entropy"], commitment),
        _OracleWireEvent(1, pt1, "link_address", 1, iface_bytes["link_address"], pub_payloads["link_address"]),
        _OracleWireEvent(2, pt2, "time_read", 1, iface_bytes["time_read"], pub_payloads["time_read"]),
        _OracleWireEvent(3, pt3, "physical_event", 1, iface_bytes["physical_event"], pub_payloads["physical_event"]),
    )
    oracle_json = _oracle_wire_to_json(base_root, comp, trace, wire_events)
    ensure(oracle_json == blob, "C-aligned oracle JSON must match FixtureRecorder compact JSON")

    wire_bytes = _oracle_encode_wire(base_root, comp, trace, wire_events)
    expected_wire_len = (
        8 + 4 + len(base_root) + 32 + 32 + 4
        + sum(_WIRE_EVENT_FIXED_BYTES + len(e.payload) for e in wire_events)
    )
    ensure(len(wire_bytes) == expected_wire_len, "canonical wire byte length mismatch")

    decoded = rr.decode(oracle_json, expected=binding, expected_events=4,
                        limits=limits, interfaces=interfaces)
    cursor = rr.FixtureCursor(decoded)
    for point, src in ((pt0, "entropy"), (pt1, "link_address"),
                       (pt2, "time_read"), (pt3, "physical_event")):
        got = cursor.consume(point=point, source=src, interface=iface_bytes[src].hex())
        ensure(got.source == src, "demand cursor source mismatch")
    _refused(lambda: cursor.consume(point=pt0, source="entropy", interface=iface_bytes["entropy"].hex()))
    cursor2 = rr.FixtureCursor(decoded)
    cursor2.consume(point=pt0, source="entropy", interface=iface_bytes["entropy"].hex())
    _refused(cursor2.finish)

    # Binding mismatch and caller-selected classification refusals.
    _refused(lambda: rr.decode(oracle_json, expected=replace(binding, base_image_root="ff"),
                               expected_events=4, limits=limits, interfaces=interfaces))
    bad_json = oracle_json.replace(b'"value"', b'"sealed_commitment"', 1)
    _refused(lambda: rr.decode(bad_json, expected=binding, expected_events=4,
                               limits=limits, interfaces=interfaces))


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, heap-free C17 surface, and ReplayRecord.v proof invariants."""
    for path in (REPLAY_H, REPLAY_C, REPLAY_TEST_C, REPLAY_README, PROOFS_V):
        ensure(path.is_file(), f"missing replay artifact: {path}")

    for c_path in (REPLAY_H, REPLAY_C, REPLAY_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = REPLAY_C.read_text(encoding="utf-8")
    for fn in (
        "vos_rr_source_is_valid",
        "vos_rr_classify_source",
        "vos_rr_point_lt",
        "vos_rr_seal_entropy_draw",
        "vos_rr_recorder_init",
        "vos_rr_recorder_source_of",
        "vos_rr_recorder_abort",
        "vos_rr_recorder_record",
        "vos_rr_recorder_finish",
        "vos_rr_encode_wire",
        "vos_rr_decode_wire",
        "vos_rr_encode_json",
        "vos_rr_decode_json",
        "vos_rr_cursor_init",
        "vos_rr_cursor_abort",
        "vos_rr_cursor_consume",
        "vos_rr_cursor_finish",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure("Require ProofSupport." in v_src, "ReplayRecord.v must require ProofSupport")
    ensure("(*| BEGIN derived: cited entries |*)" in v_src and "(*| END derived |*)" in v_src,
           "ReplayRecord.v missing derived cited entries header")
    for req_id in (
        "R-05-163", "R-05-164", "R-05-165", "R-05-166", "R-15-241",
        "R-16-013", "R-16-015", "R-16-016", "R-16-017", "R-16-018",
        "R-16-019", "R-16-020", "R-16-021", "R-16-022", "R-16-023",
    ):
        ensure(req_id in v_src, f"missing requirement citation {req_id} in ReplayRecord.v")

    for sym in (
        "closed_four_sources",
        "source_class_secret_iff_entropy",
        "source_class_public_iff_not_entropy",
        "source_determines_classification",
        "decode_accepts_only_expected_binding_and_count",
        "decoded_events_contiguous_seq",
        "pre_invocation_capacity_checks_worst_case",
        "accepted_step_releases_unused_margin",
        "sticky_failure_blocks_record",
        "sticky_failure_blocks_finish",
        "reentrancy_latches_failure",
        "cursor_consume_exact_match",
        "cursor_refuses_exhaustion",
        "cursor_refuses_trailing_events",
        "commitment_hides_secret_draw",
        "ct_scope_deterministic_replay_equivalence",
        "positive_four_source_trace_accepted",
        "positive_four_source_cursor_replayed",
        "refute_secret_in_public",
        "refute_public_in_entropy",
        "refute_regressing_coordinate",
        "refute_capacity_overflow",
        "refute_uncertain_prefix",
        "refute_cursor_exhaustion",
        "refute_cursor_trailing",
        "refute_substituted_binding",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in ReplayRecord.v")

    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in ReplayRecord.v",
        )
    records = re.findall(r"(?m)^Record\s+([A-Za-z_]\w*)\b", v_clean)
    ensure(len(records) >= 9, "expected Record declarations in ReplayRecord.v")
    for rec in records:
        ensure(
            re.search(rf"(?m)^Definition\s+witness_{rec}\s*:\s*{rec}\s*:=", v_clean) is not None,
            f"missing closed witness_{rec} definition in ReplayRecord.v",
        )


def _supports_flags(compiler: str, flags: list[str], scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_bin = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    built = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if built.returncode != 0:
        return False
    ran = subprocess.run([str(probe_bin)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _compile_and_run(compiler: str, flags: list[str], src_c: Path,
                     out_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{REPLAY_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(REPLAY_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )


def _mutants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str, label: str) -> str:
        ensure(source.count(before) == 1, f"mutant anchor missing or non-unique ({label}): {before!r}")
        return source.replace(before, after, 1)

    return [
        (
            "caller-selected-classification",
            replaced(
                "        if (ev->payload_class != (uint32_t)expected_cls) {\n"
                "            return VOS_RR_ERR_CLASS_MISMATCH;\n"
                "        }",
                "        if (0 && ev->payload_class != (uint32_t)expected_cls) {\n"
                "            return VOS_RR_ERR_CLASS_MISMATCH;\n"
                "        }",
                "caller-selected-classification",
            ),
            "caller-selected classification",
        ),
        (
            "raw-entropy-leak-in-commitment",
            replaced(
                "    if (entry->profile.source == (uint32_t)VOS_RR_SRC_ENTROPY) {\n"
                "        const enum vos_rr_status seal_st = vos_rr_seal_entropy_draw(\n"
                "            recorder->seal_key, &recorder->binding, point,\n"
                "            entry->profile.id, scratch, produced_len, ev.payload);\n"
                "        secure_zero(scratch, sizeof(scratch));\n"
                "        if (seal_st != VOS_RR_OK) {\n"
                "            secure_zero((uint8_t *)&ev, sizeof(ev));\n"
                "            return recorder_fail(recorder, seal_st);\n"
                "        }\n"
                "        ev.payload_len = VOS_RR_DIGEST_BYTES;",
                "    if (entry->profile.source == (uint32_t)VOS_RR_SRC_ENTROPY) {\n"
                "        memcpy(ev.payload, scratch, produced_len);\n"
                "        secure_zero(scratch, sizeof(scratch));\n"
                "        ev.payload_len = (uint32_t)produced_len;",
                "raw-entropy-leak-in-commitment",
            ),
            "raw entropy draw leaked into commitment",
        ),
        (
            "coordinate-regression-accepted",
            replaced(
                "    if (recorder->event_count > 0u &&\n"
                "        !vos_rr_point_lt(&recorder->events[recorder->event_count - 1u].point, point)) {\n"
                "        return recorder_fail(recorder, VOS_RR_ERR_COORD_REGRESSION);\n"
                "    }",
                "    if (0 && recorder->event_count > 0u &&\n"
                "        !vos_rr_point_lt(&recorder->events[recorder->event_count - 1u].point, point)) {\n"
                "        return recorder_fail(recorder, VOS_RR_ERR_COORD_REGRESSION);\n"
                "    }",
                "coordinate-regression-accepted",
            ),
            "coordinate regression accepted in recorder",
        ),
        (
            "retire-regression-accepted",
            replaced(
                "    if (!check_core_retire_monotonic(recorder->events, recorder->event_count, point)) {\n"
                "        return recorder_fail(recorder, VOS_RR_ERR_RETIRE_REGRESSION);\n"
                "    }",
                "    if (0 && !check_core_retire_monotonic(recorder->events, recorder->event_count, point)) {\n"
                "        return recorder_fail(recorder, VOS_RR_ERR_RETIRE_REGRESSION);\n"
                "    }",
                "retire-regression-accepted",
            ),
            "local retire regression accepted in recorder",
        ),
        (
            "seq-gap-accepted",
            replaced(
                "        if (ev->seq != (uint64_t)i) {\n"
                "            return VOS_RR_ERR_SEQ_GAP;\n"
                "        }",
                "        if (0 && ev->seq != (uint64_t)i) {\n"
                "            return VOS_RR_ERR_SEQ_GAP;\n"
                "        }",
                "seq-gap-accepted",
            ),
            "seq gap accepted on wire",
        ),
        (
            "post-invocation-capacity-check",
            replaced(
                "    const size_t worst_event_bytes =\n"
                "        (size_t)VOS_RR_WIRE_EVENT_FIXED_BYTES +\n"
                "        (size_t)entry->profile.max_payload_bytes;\n"
                "    if (worst_event_bytes > (size_t)recorder->limits.max_body_bytes - recorder->wire_bytes_used) {\n"
                "        return recorder_fail(recorder, VOS_RR_ERR_OVER_CAPACITY);\n"
                "    }",
                "    (void)entry;",
                "post-invocation-capacity-check",
            ),
            "post-invocation capacity check",
        ),
        (
            "missing-sticky-failure-latch",
            replaced(
                "    if (recorder == NULL) {\n"
                "        return VOS_RR_ERR_INVALID_ARG;\n"
                "    }\n"
                "    const enum vos_rr_status ready = recorder_check_ready(recorder);\n"
                "    if (ready != VOS_RR_OK) {\n"
                "        return ready;\n"
                "    }\n"
                "    if (expected_binding == NULL || out_wire == NULL || out_wire_len == NULL) {",
                "    if (recorder == NULL) {\n"
                "        return VOS_RR_ERR_INVALID_ARG;\n"
                "    }\n"
                "    if (recorder->busy != 0u) {\n"
                "        return VOS_RR_ERR_REENTRANT;\n"
                "    }\n"
                "    if (recorder->finished != 0u) {\n"
                "        return VOS_RR_ERR_ALREADY_FINISHED;\n"
                "    }\n"
                "    if (expected_binding == NULL || out_wire == NULL || out_wire_len == NULL) {",
                "missing-sticky-failure-latch",
            ),
            "missing sticky failure latch allowed finish",
        ),
        (
            "reentrancy-allowed",
            replaced(
                "    if (recorder->busy != 0u) {\n"
                "        recorder->failed = 1u;\n"
                "        recorder->fault_routed = 1u;\n"
                "        return VOS_RR_ERR_REENTRANT;\n"
                "    }",
                "    if (0 && recorder->busy != 0u) {\n"
                "        recorder->failed = 1u;\n"
                "        recorder->fault_routed = 1u;\n"
                "        return VOS_RR_ERR_REENTRANT;\n"
                "    }",
                "reentrancy-allowed",
            ),
            "reentrancy allowed inside record",
        ),
        (
            "self-declared-binding-accepted",
            replaced(
                "    if (!bindings_equal(&record->binding, expected_binding)) {\n"
                "        return VOS_RR_ERR_BINDING_MISMATCH;\n"
                "    }",
                "    if (0 && !bindings_equal(&record->binding, expected_binding)) {\n"
                "        return VOS_RR_ERR_BINDING_MISMATCH;\n"
                "    }",
                "self-declared-binding-accepted",
            ),
            "self-declared binding accepted",
        ),
        (
            "trailing-event-ignored-by-cursor",
            replaced(
                "    if (cursor->next != cursor->record.event_count) {\n"
                "        cursor->failed = 1u;\n"
                "        return VOS_RR_ERR_TRAILING_EVENTS;\n"
                "    }",
                "    if (0 && cursor->next != cursor->record.event_count) {\n"
                "        cursor->failed = 1u;\n"
                "        return VOS_RR_ERR_TRAILING_EVENTS;\n"
                "    }",
                "trailing-event-ignored-by-cursor",
            ),
            "trailing event ignored by cursor",
        ),
        (
            "premature-cursor-exhaustion-ignored",
            replaced(
                "    if (cursor->next >= cursor->record.event_count) {\n"
                "        cursor->failed = 1u;\n"
                "        return VOS_RR_ERR_EXHAUSTED;\n"
                "    }",
                "    if (cursor->next >= cursor->record.event_count) {\n"
                "        return VOS_RR_OK;\n"
                "    }",
                "premature-cursor-exhaustion-ignored",
            ),
            "premature cursor exhaustion ignored",
        ),
        (
            "public-validator-bypassed",
            replaced(
                "        if (valid_pub == 0) {\n"
                "            secure_zero(scratch, sizeof(scratch));\n"
                "            return recorder_fail(recorder, VOS_RR_ERR_PUBLIC_VALIDATION);\n"
                "        }",
                "        (void)valid_pub;",
                "public-validator-bypassed",
            ),
            "public validator bypassed",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run replay C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang is required in Linux guest")
    ensure(gcc is not None, "gcc is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes", "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "replay-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rr-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_rr_clang"
        clang_built = _compile_and_run(clang, strict_flags, REPLAY_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(clang_ran.returncode == 0 and "replay_record_test: ok" in clang_ran.stdout,
               f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}")

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_rr_gcc_san"
        gcc_built = _compile_and_run(gcc, asan_flags, REPLAY_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(gcc_ran.returncode == 0 and "replay_record_test: ok" in gcc_ran.stdout,
               f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}")

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = REPLAY_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 10, f"expected >= 10 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_run(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, timeout=60, check=False,
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("replay_record_oracle_and_host_cross_check", _oracle_and_host_cross_check, lane="any"),
        Case("replay_record_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("replay_record_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
