# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests and refusal controls for `vos.copy_q25bb_client` and its retained bundle."""

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.harness import TOOLS, Case, ensure
from vos import copy_q25bb_client as q25bb

REPO_ROOT = TOOLS.parent
EVIDENCE_ROOT = REPO_ROOT / "docs/implementation/retained-evidence"
BUNDLE_F594585 = EVIDENCE_ROOT / "holdfast-q25bb-purecap-client-f594585-20261127"
BUNDLE_DIR = BUNDLE_F594585


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _refuse(fn: Callable[[], object], expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        ensure(expected in str(exc), f"expected {expected!r} in refusal, got: {exc}")
        return
    raise AssertionError(f"expected ValueError containing {expected!r}")


def _check_manifest(bundle_dir: Path, expected_members: set[str]) -> None:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    files = cast(dict[str, Any], manifest["files"])
    ensure(set(files.keys()) == expected_members, f"unexpected bundle members: {sorted(files)}")
    for name in expected_members:
        raw = (bundle_dir / name).read_bytes()
        entry = cast(dict[str, Any], files[name])
        ensure(
            entry["bytes"] == len(raw) and entry["sha256"] == _sha256(raw),
            f"manifest mismatch for {name}",
        )


def _check_envelope_metrics(report: dict[str, Any], envelope: dict[str, Any]) -> None:
    ensure(report["verdict"] == "pass" and report["code"] == 0, f"unexpected verdict: {report}")
    ops = cast(dict[str, Any], envelope["operations"])
    ensure(ops["vos_copy_init_generation"]["call_count"] == 5, f"unexpected init_gen count: {ops}")
    ensure(ops["vos_copy_submit"]["call_count"] == 602, f"unexpected submit count: {ops}")
    ensure(ops["vos_copy_take"]["call_count"] == 593, f"unexpected take count: {ops}")
    ensure(
        ops["vos_copy_init_generation"]["stack_frame_bytes"]["peak"] == 32
        and ops["vos_copy_submit"]["stack_frame_bytes"]["peak"] == 240
        and ops["vos_copy_take"]["stack_frame_bytes"]["peak"] == 176,
        f"unexpected stack bounds: {ops}",
    )


def _retained_bundle_positive() -> None:
    _check_manifest(
        BUNDLE_DIR,
        {"report.json", "envelope.json", "controls.json", "native-parity.json", "driver.py.txt"},
    )
    ensure(
        (BUNDLE_DIR / "driver.py.txt").read_bytes()
        == (REPO_ROOT / "tools/vos/copy_q25bb_client.py").read_bytes(),
        "retained driver.py.txt must match tools/vos/copy_q25bb_client.py",
    )

    report, envelope, controls = q25bb.validate_bundle_dir(BUNDLE_DIR)
    _check_envelope_metrics(report, envelope)
    ctrl_map = cast(dict[str, Any], controls["controls"])
    ensure(
        len(ctrl_map) == 15
        and ctrl_map["mutated-payload-limit"]["code"] == 14
        and ctrl_map["mutated-snapshot-byte"]["code"] == 7
        and ctrl_map["mutated-suffix-clobber"]["code"] == 8
        and ctrl_map["mutated-refusal-output"]["code"] in (2, 6)
        and ctrl_map["mutated-stale-generation"]["code"] == 3
        and ctrl_map["mutated-duplicate-request"]["code"] == 5
        and ctrl_map["mutated-full-ring"]["code"] == 11
        and ctrl_map["mutated-too-small-dst"]["code"] == 6
        and ctrl_map["mutated-overlapping-views"]["code"] == 9
        and ctrl_map["mutated-narrow-arena-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-narrow-arena-cap"]["code"] == 284
        and ctrl_map["mutated-narrow-arena-cap"]["trap_cause"] == 28
        and ctrl_map["mutated-read-only-arena-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-read-only-arena-cap"]["code"] == 284
        and ctrl_map["mutated-read-only-arena-cap"]["trap_cause"] == 28
        and ctrl_map["mutated-untagged-arena-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-untagged-arena-cap"]["code"] == 284
        and ctrl_map["mutated-untagged-arena-cap"]["trap_cause"] == 28
        and ctrl_map["mutated-narrow-ring-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-narrow-ring-cap"]["code"] == 284
        and ctrl_map["mutated-narrow-ring-cap"]["trap_cause"] == 28
        and ctrl_map["mutated-read-only-ring-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-read-only-ring-cap"]["code"] == 284
        and ctrl_map["mutated-read-only-ring-cap"]["trap_cause"] == 28
        and ctrl_map["mutated-untagged-ring-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-untagged-ring-cap"]["code"] == 284
        and ctrl_map["mutated-untagged-ring-cap"]["trap_cause"] == 28,
        f"unexpected negative control results: {ctrl_map}",
    )
    native_parity = json.loads((BUNDLE_DIR / "native-parity.json").read_text(encoding="utf-8"))
    ensure(
        native_parity["all_parity_matched"] is True
        and native_parity["holdfast_revision"] == "f594585fed3430e7c385f661ff73e3d70a6b4762"
        and set(native_parity["parity_checks"].keys())
        == {native for native, _ in q25bb.PARITY_CASE_MAP},
        f"unexpected native parity record: {native_parity}",
    )


def _wrapper_and_client_scoping() -> None:
    arena_bytes = q25bb.arena_bytes_for(4096)
    ensure(arena_bytes == 8197, f"expected 8197 arena bytes, got {arena_bytes}")
    ensure(q25bb.power_of_two_ceil(arena_bytes) == 16384, "expected 16384 power-of-two arena")

    pos_wrapper = q25bb.entry_wrapper(arena_bytes)
    ensure("li x31, 524288" in pos_wrapper and "li x31, 16384" in pos_wrapper, pos_wrapper)
    ensure("q25bb_arena +" not in pos_wrapper and "q25bb_ring +" not in pos_wrapper, pos_wrapper)
    ensure("candperm" not in pos_wrapper and "cgetaddr" not in pos_wrapper, pos_wrapper)

    narrow_wrapper = q25bb.entry_wrapper(arena_bytes, narrow_arena_by=1)
    ensure("li x31, q25bb_arena + 8188" in narrow_wrapper, narrow_wrapper)

    ro_wrapper = q25bb.entry_wrapper(arena_bytes, read_only_arena=True)
    ensure("andi x31, x31, -5" in ro_wrapper and "candperm c11, c11, x31" in ro_wrapper, ro_wrapper)

    untagged_wrapper = q25bb.entry_wrapper(arena_bytes, untagged_arena=True)
    ensure("cgetaddr x11, c11" in untagged_wrapper, untagged_wrapper)

    narrow_ring_wrapper = q25bb.entry_wrapper(arena_bytes, narrow_ring=True)
    ensure(
        f"li x31, q25bb_ring + {q25bb.RING_BYTES - 4096}" in narrow_ring_wrapper
        and "csetaddr c10, c10, x31" in narrow_ring_wrapper,
        narrow_ring_wrapper,
    )

    ro_ring_wrapper = q25bb.entry_wrapper(arena_bytes, read_only_ring=True)
    ensure(
        "cgetperm x31, c10" in ro_ring_wrapper
        and "andi x31, x31, -5" in ro_ring_wrapper
        and "candperm c10, c10, x31" in ro_ring_wrapper,
        ro_ring_wrapper,
    )

    untagged_ring_wrapper = q25bb.entry_wrapper(arena_bytes, untagged_ring=True)
    ensure("cgetaddr x10, c10" in untagged_ring_wrapper, untagged_ring_wrapper)

    _refuse(
        lambda: q25bb.entry_wrapper(arena_bytes, read_only_arena=True, untagged_arena=True),
        "at most one capability mutation",
    )
    _refuse(
        lambda: q25bb.entry_wrapper(arena_bytes, narrow_arena_by=1, read_only_ring=True),
        "at most one capability mutation",
    )
    _refuse(
        lambda: q25bb.entry_wrapper(arena_bytes, narrow_ring=True, untagged_ring=True),
        "at most one capability mutation",
    )

    sample_asm = "\n".join([
        "# header",
        ".text",
        ".globl vos_copy_payload_limit",
        "vos_copy_payload_limit:",
        "    bne x10, x0, .L100",
        ".L100:",
        "    cjalr cnull, cra, 0",
        ".text",
        ".globl holdfast_copy_trial",
        "holdfast_copy_trial:",
        "    call vos_copy_payload_limit",
        "    call vos_copy_init_generation",
        "    call vos_copy_submit",
        "    call vos_copy_take",
        "    j .L100",
        ".L100:",
        "    cjalr cnull, cra, 0",
        ".text",
        ".globl vos_copy_init_generation",
        "vos_copy_init_generation:",
        "    cjalr cnull, cra, 0",
        ".text",
        ".globl vos_copy_submit",
        "vos_copy_submit:",
        "    cjalr cnull, cra, 0",
        ".text",
        ".globl vos_copy_take",
        "vos_copy_take:",
        "    cjalr cnull, cra, 0",
        "",
    ])
    scoped = q25bb.prepare_client_assembly(sample_asm)
    ensure("__q25bb_client_vos_copy_payload_limit:" in scoped, scoped)
    ensure("call __q25bb_client_vos_copy_payload_limit" in scoped, scoped)
    ensure(".L__q25bb_client_100:" in scoped and ".L100" not in scoped, scoped)
    ensure("vos_copy_init_generation:" not in scoped, scoped)
    ensure("vos_copy_submit:" not in scoped, scoped)
    ensure("vos_copy_take:" not in scoped, scoped)
    ensure("call vos_copy_submit" in scoped, scoped)

    _refuse(
        lambda: q25bb.prepare_client_assembly(sample_asm.replace("vos_copy_take:", "other_fn:")),
        "mismatched function block header",
    )
    _refuse(
        lambda: q25bb.prepare_client_assembly(sample_asm.replace("holdfast_copy_trial", "other_entry")),
        "missing holdfast_copy_trial",
    )


def _mutated_report_refusals() -> None:
    report, envelope, controls = q25bb.validate_bundle_dir(BUNDLE_DIR)
    native_parity = json.loads((BUNDLE_DIR / "native-parity.json").read_text(encoding="utf-8"))

    for key, bad_val in (
        ("qualified_producer", True),
        ("installed_entry", "vos_copy_submit"),
        ("production_admission", True),
        ("trial_acceptance", True),
    ):
        bad_report = copy.deepcopy(report)
        bad_report[key] = bad_val
        _refuse(
            lambda r=bad_report: q25bb.validate_bundle(r, envelope, controls, native_parity),
            f"report: {key}",
        )

    bad_source = copy.deepcopy(report)
    bad_source["prepared_source_sha256"] = "0" * 64
    _refuse(
        lambda: q25bb.validate_bundle(bad_source, envelope, controls, native_parity),
        "prepared_source_sha256",
    )

    bad_member = copy.deepcopy(envelope)
    bad_member["static_footprint"]["members"]["compiled C"]["sha256"] = "0" * 64
    _refuse(
        lambda: q25bb.validate_bundle(report, bad_member, controls, native_parity),
        "frozen 498127d6 build",
    )

    bad_verdict = copy.deepcopy(report)
    bad_verdict["verdict"] = "fail"
    _refuse(
        lambda: q25bb.validate_bundle(bad_verdict, envelope, controls, native_parity),
        "passing verdict",
    )

    bad_ctrl_trap = copy.deepcopy(controls)
    bad_ctrl_trap["controls"]["mutated-narrow-arena-cap"]["verdict"] = "fail"
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_ctrl_trap, native_parity),
        "expected verdict 'trap'",
    )

    bad_ro_cause = copy.deepcopy(controls)
    bad_ro_cause["controls"]["mutated-read-only-arena-cap"]["trap_cause"] = 0
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_ro_cause, native_parity),
        "expected CHERI trap cause 28",
    )

    bad_untagged_verdict = copy.deepcopy(controls)
    bad_untagged_verdict["controls"]["mutated-untagged-arena-cap"]["verdict"] = "pass"
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_untagged_verdict, native_parity),
        "expected verdict 'trap'",
    )

    bad_overlap_code = copy.deepcopy(controls)
    bad_overlap_code["controls"]["mutated-overlapping-views"]["code"] = 0
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_overlap_code, native_parity),
        "expected code in (9,)",
    )

    for ctrl_name, expected_code in (
        ("mutated-payload-limit", 14),
        ("mutated-stale-generation", 3),
        ("mutated-duplicate-request", 5),
        ("mutated-full-ring", 11),
        ("mutated-too-small-dst", 6),
    ):
        bad_ctrl_code = copy.deepcopy(controls)
        bad_ctrl_code["controls"][ctrl_name]["code"] = 0
        _refuse(
            lambda c=bad_ctrl_code: q25bb.validate_bundle(report, envelope, c, native_parity),
            f"expected code in ({expected_code},)",
        )

    for ring_trap in ("mutated-narrow-ring-cap", "mutated-untagged-ring-cap"):
        bad_ring_verdict = copy.deepcopy(controls)
        bad_ring_verdict["controls"][ring_trap]["verdict"] = "fail"
        _refuse(
            lambda c=bad_ring_verdict: q25bb.validate_bundle(report, envelope, c, native_parity),
            "expected verdict 'trap'",
        )

    bad_ring_ro_cause = copy.deepcopy(controls)
    bad_ring_ro_cause["controls"]["mutated-read-only-ring-cap"]["trap_cause"] = 0
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_ring_ro_cause, native_parity),
        "expected CHERI trap cause 28",
    )

    missing_ctrl = copy.deepcopy(controls)
    del missing_ctrl["controls"]["mutated-suffix-clobber"]
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, missing_ctrl, native_parity),
        "expected all 15 negative controls",
    )

    bad_parity_exit = copy.deepcopy(native_parity)
    bad_parity_exit["parity_checks"]["tightened_payload_limit"]["native_exit"] = 1
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, controls, bad_parity_exit),
        "native/target exit mismatch",
    )

    bad_parity_flag = copy.deepcopy(native_parity)
    bad_parity_flag["all_parity_matched"] = False
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, controls, bad_parity_flag),
        "all_parity_matched must be True",
    )

    bad_parity_syntax = copy.deepcopy(native_parity)
    bad_parity_syntax["native_report"]["target_declarations_syntax_exit"] = 1
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, controls, bad_parity_syntax),
        "target_declarations_syntax_exit must be 0",
    )

    bad_parity_accept = copy.deepcopy(native_parity)
    bad_parity_accept["trial_acceptance"] = True
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, controls, bad_parity_accept),
        "native_parity: trial_acceptance",
    )


def cases() -> list[Case]:
    return [
        Case("copy-q25bb-client-retained-bundle-passes", _retained_bundle_positive),
        Case("copy-q25bb-client-wrapper-and-scoping", _wrapper_and_client_scoping),
        Case("copy-q25bb-client-refuses-mutated-reports", _mutated_report_refusals),
    ]
