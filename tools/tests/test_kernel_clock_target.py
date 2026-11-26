# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests and refusal controls for `vos.kernel_clock_target` and its retained bundle."""

import copy
import hashlib
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.harness import TOOLS, Case, ensure
from vos import kernel_clock_target as kct

REPO_ROOT = TOOLS.parent
BUNDLE_DIR = REPO_ROOT / "docs/implementation/retained-evidence/q46b-kernel-clock-target-20261126"


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
    expected_members = {"report.json", "controls.json", "driver.py.txt"}
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
        == (REPO_ROOT / "tools/vos/kernel_clock_target.py").read_bytes(),
        "retained driver.py.txt must match tools/vos/kernel_clock_target.py",
    )

    report, controls = kct.validate_bundle_dir(BUNDLE_DIR)
    ensure(report["qualified_producer"] is False, f"unexpected qualified_producer: {report}")
    ensure(report["production_admission"] is False, f"unexpected production_admission: {report}")
    ensure(report["trial_acceptance"] is False, f"unexpected trial_acceptance: {report}")
    ensure(report["milestone_acceptance"] == "open", f"unexpected milestone_acceptance: {report}")
    ensure(
        bool(report["qualified_target_entry_producer_refusal"]),
        "missing qualified_target_entry_producer_refusal",
    )

    part_a = cast(dict[str, Any], report["part_a"])
    ensure(part_a["verdict"] == "pass" and part_a["code"] == 0, f"unexpected Part A: {part_a}")

    part_b = cast(dict[str, Any], report["part_b"])
    ensure(part_b["verdict"] == "pass" and part_b["code"] == 0, f"unexpected Part B: {part_b}")
    obs = cast(dict[str, Any], part_b["observations"])
    ensure(obs["restore_count"] == 2 and all(bool(v) for v in obs.values()), f"bad Part B obs: {obs}")

    a_ctrls = cast(dict[str, Any], controls["part_a_controls"])
    for name in ("mutated-phase-overflow", "mutated-mul-overflow", "mutated-frame-index-wrap", "mutated-duration-overflow"):
        ensure(
            a_ctrls[name]["passed"] is True
            and a_ctrls[name]["verdict"] == "fail"
            and a_ctrls[name]["code"] != 0,
            f"unexpected Part A control {name}: {a_ctrls[name]}",
        )

    b_ctrls = cast(dict[str, Any], controls["part_b_controls"])
    ov = cast(dict[str, Any], b_ctrls["adapter-epoch-overflow"])
    ensure(
        ov["verdict"] == "fail"
        and ov["code"] == 22
        and ov["vos_target_release_returned_zero"] is True
        and ov["mtimecmp_written"] is False
        and ov["partition_one_entered"] is False
        and ov["partition_two_entered"] is False,
        f"unexpected adapter-epoch-overflow: {ov}",
    )
    ug = cast(dict[str, Any], b_ctrls["mutated-unguarded-target-release"])
    ensure(
        ug["mtimecmp_written"] is True and ug["partition_one_entered"] is True,
        f"unexpected mutated-unguarded-target-release: {ug}",
    )


def _mutated_report_refusals() -> None:
    report, controls = kct.validate_bundle_dir(BUNDLE_DIR)

    for key in ("qualified_producer", "production_admission", "trial_acceptance"):
        bad_report = copy.deepcopy(report)
        bad_report[key] = True
        _refuse(lambda r=bad_report: kct.validate_bundle(r, controls), f"report: {key}")

        bad_controls = copy.deepcopy(controls)
        bad_controls[key] = True
        _refuse(lambda c=bad_controls: kct.validate_bundle(report, c), f"controls: {key}")

    bad_milestone = copy.deepcopy(report)
    bad_milestone["milestone_acceptance"] = "accepted"
    _refuse(lambda: kct.validate_bundle(bad_milestone, controls), "milestone_acceptance")

    bad_refusal = copy.deepcopy(report)
    bad_refusal["qualified_target_entry_producer_refusal"] = ""
    _refuse(
        lambda: kct.validate_bundle(bad_refusal, controls),
        "qualified_target_entry_producer_refusal",
    )

    bad_a = copy.deepcopy(report)
    bad_a["part_a"]["verdict"] = "fail"
    _refuse(lambda: kct.validate_bundle(bad_a, controls), "report.part_a: expected pass")

    bad_b = copy.deepcopy(report)
    bad_b["part_b"]["observations"]["frame_order"] = False
    _refuse(lambda: kct.validate_bundle(bad_b, controls), "report.part_b.observations")

    missing_a_ctrl = copy.deepcopy(controls)
    del missing_a_ctrl["part_a_controls"]["mutated-mul-overflow"]
    _refuse(
        lambda: kct.validate_bundle(report, missing_a_ctrl),
        "expected all 4 controls",
    )

    zero_a_ctrl = copy.deepcopy(controls)
    zero_a_ctrl["part_a_controls"]["mutated-phase-overflow"]["code"] = 0
    _refuse(
        lambda: kct.validate_bundle(report, zero_a_ctrl),
        "expected nonzero code",
    )

    bad_ov = copy.deepcopy(controls)
    bad_ov["part_b_controls"]["adapter-epoch-overflow"]["mtimecmp_written"] = True
    _refuse(
        lambda: kct.validate_bundle(report, bad_ov),
        "adapter-epoch-overflow: invariant failure",
    )

    bad_ug = copy.deepcopy(controls)
    bad_ug["part_b_controls"]["mutated-unguarded-target-release"]["mtimecmp_written"] = False
    _refuse(
        lambda: kct.validate_bundle(report, bad_ug),
        "mutated-unguarded-target-release: invariant failure",
    )

    bad_kt = copy.deepcopy(controls)
    bad_kt["kernel_target_controls"][0]["matched"] = False
    _refuse(
        lambda: kct.validate_bundle(report, bad_kt),
        "matched must be True",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tampered_report = copy.deepcopy(report)
        tampered_report["controls_sha256"] = "0" * 64
        (tmp_dir / "report.json").write_text(json.dumps(tampered_report), encoding="utf-8")
        (tmp_dir / "controls.json").write_bytes((BUNDLE_DIR / "controls.json").read_bytes())
        _refuse(
            lambda: kct.validate_bundle_dir(tmp_dir),
            "controls_sha256 disagrees",
        )


def cases() -> list[Case]:
    return [
        Case("kernel-clock-target-retained-bundle-passes", _retained_bundle_positive),
        Case("kernel-clock-target-refuses-mutated-reports", _mutated_report_refusals),
    ]
