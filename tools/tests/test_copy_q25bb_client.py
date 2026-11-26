# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests and refusal controls for `vos.copy_q25bb_client` and its retained bundle."""

import copy
import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

from tests.harness import TOOLS, Case, ensure
from vos import copy_q25bb_client as q25bb

REPO_ROOT = TOOLS.parent
BUNDLE_DIR = REPO_ROOT / "docs/implementation/retained-evidence/holdfast-q25bb-purecap-client-20261126"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _refuse(fn: Callable[[], object], expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        ensure(expected in str(exc), f"expected {expected!r} in refusal, got: {exc}")
        return
    raise AssertionError(f"expected ValueError containing {expected!r}")


def _retained_bundle_positive() -> None:
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text(encoding="utf-8"))
    files = cast(dict[str, Any], manifest["files"])
    expected_members = {"report.json", "envelope.json", "controls.json", "driver.py.txt"}
    ensure(set(files.keys()) == expected_members, f"unexpected bundle members: {sorted(files)}")
    for name in expected_members:
        raw = (BUNDLE_DIR / name).read_bytes()
        entry = cast(dict[str, Any], files[name])
        ensure(
            entry["bytes"] == len(raw) and entry["sha256"] == _sha256(raw),
            f"manifest mismatch for {name}",
        )
    ensure(
        (BUNDLE_DIR / "driver.py.txt").read_bytes()
        == (REPO_ROOT / "tools/vos/copy_q25bb_client.py").read_bytes(),
        "retained driver.py.txt must match tools/vos/copy_q25bb_client.py",
    )

    report, envelope, controls = q25bb.validate_bundle_dir(BUNDLE_DIR)
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
    ctrl_map = cast(dict[str, Any], controls["controls"])
    ensure(
        ctrl_map["mutated-payload-limit"]["code"] == 14
        and ctrl_map["mutated-snapshot-byte"]["code"] == 7
        and ctrl_map["mutated-suffix-clobber"]["code"] == 8
        and ctrl_map["mutated-refusal-output"]["code"] in (2, 6)
        and ctrl_map["mutated-narrow-arena-cap"]["verdict"] == "trap"
        and ctrl_map["mutated-narrow-arena-cap"]["trap_cause"] == 28,
        f"unexpected negative control results: {ctrl_map}",
    )


def _wrapper_and_client_scoping() -> None:
    arena_bytes = q25bb.arena_bytes_for(4096)
    ensure(arena_bytes == 8197, f"expected 8197 arena bytes, got {arena_bytes}")
    ensure(q25bb.power_of_two_ceil(arena_bytes) == 16384, "expected 16384 power-of-two arena")

    pos_wrapper = q25bb.entry_wrapper(arena_bytes)
    ensure("li x31, 524288" in pos_wrapper and "li x31, 16384" in pos_wrapper, pos_wrapper)
    ensure("q25bb_arena +" not in pos_wrapper, pos_wrapper)

    narrow_wrapper = q25bb.entry_wrapper(arena_bytes, narrow_arena_by=1)
    ensure("li x31, q25bb_arena + 8188" in narrow_wrapper, narrow_wrapper)

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

    for key, bad_val in (
        ("qualified_producer", True),
        ("installed_entry", "vos_copy_submit"),
        ("production_admission", True),
        ("trial_acceptance", True),
    ):
        bad_report = copy.deepcopy(report)
        bad_report[key] = bad_val
        _refuse(lambda r=bad_report: q25bb.validate_bundle(r, envelope, controls), f"report: {key}")

    bad_source = copy.deepcopy(report)
    bad_source["prepared_source_sha256"] = "0" * 64
    _refuse(lambda: q25bb.validate_bundle(bad_source, envelope, controls), "prepared_source_sha256")

    bad_member = copy.deepcopy(envelope)
    bad_member["static_footprint"]["members"]["compiled C"]["sha256"] = "0" * 64
    _refuse(lambda: q25bb.validate_bundle(report, bad_member, controls), "frozen 498127d6 build")

    bad_verdict = copy.deepcopy(report)
    bad_verdict["verdict"] = "fail"
    _refuse(lambda: q25bb.validate_bundle(bad_verdict, envelope, controls), "passing verdict")

    bad_ctrl_trap = copy.deepcopy(controls)
    bad_ctrl_trap["controls"]["mutated-narrow-arena-cap"]["verdict"] = "fail"
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_ctrl_trap),
        "expected verdict 'trap'",
    )

    bad_ctrl_code = copy.deepcopy(controls)
    bad_ctrl_code["controls"]["mutated-payload-limit"]["code"] = 0
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, bad_ctrl_code),
        "expected code in (14,)",
    )

    missing_ctrl = copy.deepcopy(controls)
    del missing_ctrl["controls"]["mutated-suffix-clobber"]
    _refuse(
        lambda: q25bb.validate_bundle(report, envelope, missing_ctrl),
        "expected all 5 negative controls",
    )


def cases() -> list[Case]:
    return [
        Case("copy-q25bb-client-retained-bundle-passes", _retained_bundle_positive),
        Case("copy-q25bb-client-wrapper-and-scoping", _wrapper_and_client_scoping),
        Case("copy-q25bb-client-refuses-mutated-reports", _mutated_report_refusals),
    ]
