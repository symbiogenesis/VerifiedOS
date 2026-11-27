# SPDX-License-Identifier: Apache-2.0
"""Validate the retained HoldFast Q25ba first-slice replay evidence bundle."""

import argparse
import gzip
import hashlib
import json
import re
import sys
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from vos.jsonutil import unique_object  # noqa: E402

DEFAULT_BUNDLE_REL: Final = "docs/implementation/retained-evidence/holdfast-q25ba-f594585-20261127"
EXPECTED_REUSE_TOML_SHA256: Final = (
    "c5a9383eb3546b2f076b9f1397b7b0d62db75f7d608913d95a4ff97e114c536a"
)
REQUIRED_MISSING_DEPLOYED_KEYS: Final[tuple[str, ...]] = (
    "packet_functional_result",
    "returned_view_authority",
)
EXPECTED_PURECAP_CONTROLS: Final[dict[str, tuple[str, int, bool]]] = {
    "pass": ("pass", 0, True),
    "bounds-trap": ("trap", 284, False),
    "perm-trap": ("trap", 284, False),
    "tag-trap": ("trap", 284, False),
    "writable-view": ("fail", 2, True),
}
EXPECTED_PERTURBED_CONTROLS: Final[tuple[str, ...]] = (
    "perturbed-empty-view-origin",
    "perturbed-full-view-origin",
    "perturbed-wrong-payload-byte",
    "perturbed-writable-partial-view",
    "perturbed-stale-trailing-byte",
    "perturbed-checksum-error-code",
    "perturbed-unscrubbed-checksum-dst",
)
EXPECTED_ENTRY_MISMATCHES: Final[dict[str, str]] = {
    "perturbed-empty-view-origin": "view.cursor",
    "perturbed-full-view-origin": "view.cursor",
    "perturbed-writable-partial-view": "view.perm_write",
}

_EXPECTED_MANIFEST_MEMBERS: Final[frozenset[str]] = frozenset({
    "bindings.json",
    "qualification.json.gz",
    "summary.json",
})
_MIN_ASSUMPTION_EXPORTS: Final = 78
_MIN_NEGATIVE_CONTROLS: Final = 19
_MIN_SUITE_CASES: Final = 159
_FIRST_SLICE_CALL_COUNT: Final = 9
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_HEX40_RE: Final = re.compile(r"^[0-9a-f]{40}$")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    _require(isinstance(value, Mapping), f"{label}: expected JSON object")
    return cast(Mapping[str, object], value)


def _as_list(value: object, label: str) -> list[object]:
    _require(isinstance(value, list), f"{label}: expected JSON list")
    return cast(list[object], value)


def _require_sha256_str(value: object, label: str) -> str:
    _require(
        isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
        f"{label}: expected 64-hex SHA-256, got {value!r}",
    )
    return cast(str, value)


def _require_false_flags(doc: Mapping[str, object], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        _require(
            key in doc and doc[key] is False,
            f"{label}: {key} must be False, got {doc.get(key)!r}",
        )


def _unique_json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=lambda pairs: unique_object(
                pairs,
                duplicate_error=lambda key: ValueError(f"{label}: duplicate JSON key {key!r}"),
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid JSON ({exc})") from exc
    _require(isinstance(parsed, dict), f"{label}: JSON root must be an object")
    return cast(dict[str, Any], parsed)


def _verify_identity(raw: bytes, entry: Mapping[str, object], label: str, *, stored: bool) -> str:
    bytes_key = "stored_bytes" if stored else "bytes"
    sha_key = "stored_sha256" if stored else "sha256"
    exp_bytes = entry.get(bytes_key)
    exp_sha = _require_sha256_str(entry.get(sha_key), f"{label}.{sha_key}")
    _require(
        type(exp_bytes) is int and exp_bytes >= 0,
        f"{label}.{bytes_key}: expected non-negative int, got {exp_bytes!r}",
    )
    actual_sha = _sha256(raw)
    _require(
        len(raw) == exp_bytes and actual_sha == exp_sha,
        f"{label}: {bytes_key}/{sha_key} mismatch (expected {exp_bytes}/{exp_sha}, got {len(raw)}/{actual_sha})",
    )
    return actual_sha


def validate_manifest(
    bundle_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Verify `manifest.json` digests and load `(summary, bindings, qualification, decompressed_sha256)`."""
    manifest_path = bundle_dir / "manifest.json"
    _require(manifest_path.is_file(), f"missing manifest.json in {bundle_dir}")
    manifest = _unique_json_object(manifest_path.read_bytes(), "manifest.json")
    files = _as_mapping(manifest.get("files"), "manifest.files")
    _require(
        set(files.keys()) == _EXPECTED_MANIFEST_MEMBERS,
        f"manifest.files must cover exact members {sorted(_EXPECTED_MANIFEST_MEMBERS)}, got {sorted(files.keys())}",
    )

    loaded: dict[str, dict[str, Any]] = {}
    qual_sha256 = ""
    for name in sorted(_EXPECTED_MANIFEST_MEMBERS):
        entry = _as_mapping(files[name], f"manifest.files.{name}")
        _require(
            entry.get("path") == name,
            f"manifest.files.{name}: path must equal {name!r}, got {entry.get('path')!r}",
        )
        member_path = bundle_dir / name
        _require(member_path.is_file(), f"manifest member missing on disk: {name}")
        raw = member_path.read_bytes()

        encoding = entry.get("encoding")
        if name == "qualification.json.gz":
            _require(encoding == "gzip", f"{name}: encoding must be 'gzip', got {encoding!r}")
            _verify_identity(raw, entry, f"manifest.{name}", stored=True)
            _require(raw.startswith(b"\x1f\x8b"), f"{name}: missing gzip header")
            try:
                decompressed = gzip.decompress(raw)
            except (OSError, EOFError, zlib.error) as exc:
                raise ValueError(f"{name}: gzip decompression failed ({exc})") from exc
            qual_sha256 = _verify_identity(decompressed, entry, f"manifest.{name}", stored=False)
            loaded[name] = _unique_json_object(decompressed, name)
        else:
            _require(encoding == "identity", f"{name}: encoding must be 'identity', got {encoding!r}")
            _verify_identity(raw, entry, f"manifest.{name}", stored=False)
            loaded[name] = _unique_json_object(raw, name)

    return loaded["summary.json"], loaded["bindings.json"], loaded["qualification.json.gz"], qual_sha256


def _validate_missing_deployed(raw_map: object, label: str) -> None:
    missing = _as_mapping(raw_map, label)
    for key in REQUIRED_MISSING_DEPLOYED_KEYS:
        val = missing.get(key)
        _require(
            isinstance(val, str) and bool(val.strip()),
            f"{label}: missing or blank required key {key!r}",
        )


def _validate_proof_honesty(qdoc: Mapping[str, object], label: str) -> None:
    _require(qdoc.get("status") == "passed", f"{label}: status must be 'passed', got {qdoc.get('status')!r}")
    _require(qdoc.get("accepted") is True, f"{label}: accepted must be True")
    _require(qdoc.get("kernel_checked") is True, f"{label}: kernel_checked must be True")
    _require(qdoc.get("proof_corruption_refused") is True, f"{label}: proof_corruption_refused must be True")
    trusted_count = qdoc.get("solver_trusted_count")
    _require(
        type(trusted_count) is int and trusted_count == 0,
        f"{label}: solver_trusted_count must be 0, got {trusted_count!r}",
    )
    _require(
        qdoc.get("solver_trusted_axioms") == [],
        f"{label}: solver_trusted_axioms must be [], got {qdoc.get('solver_trusted_axioms')!r}",
    )
    assumption_count = qdoc.get("assumption_exports_count")
    _require(
        type(assumption_count) is int and assumption_count >= _MIN_ASSUMPTION_EXPORTS,
        f"{label}: assumption_exports_count must be >= {_MIN_ASSUMPTION_EXPORTS}, got {assumption_count!r}",
    )
    neg_count = qdoc.get("negative_controls_count")
    _require(
        type(neg_count) is int and neg_count >= _MIN_NEGATIVE_CONTROLS,
        f"{label}: negative_controls_count must be >= {_MIN_NEGATIVE_CONTROLS}, got {neg_count!r}",
    )
    cap_inv = _as_mapping(qdoc.get("capacity_invariance"), f"{label}.capacity_invariance")
    _require(
        cap_inv.get("small_capacity") == "8usize"
        and cap_inv.get("large_capacity") == "1_000_000_000usize",
        f"{label}.capacity_invariance: unexpected capacities {cap_inv!r}",
    )
    _require(cap_inv.get("kernel_checked") is True, f"{label}.capacity_invariance: kernel_checked must be True")
    reduction_steps = cap_inv.get("reduction_steps")
    _require(
        type(reduction_steps) is int and reduction_steps == 0,
        f"{label}.capacity_invariance: reduction_steps must be 0, got {reduction_steps!r}",
    )


def _validate_compcert_sail(cs: Mapping[str, object], label: str) -> dict[str, Mapping[str, object]]:
    _require(cs.get("available") is True, f"{label}: available must be True")
    _require(cs.get("sail_verdict") == "pass", f"{label}: sail_verdict must be 'pass'")
    _require(cs.get("sail_cap_roundtrip") is True, f"{label}: sail_cap_roundtrip must be True")
    interp_exit = cs.get("interp_exit_code")
    _require(
        type(interp_exit) is int and interp_exit == 0,
        f"{label}: interp_exit_code must be 0, got {interp_exit!r}",
    )
    sail_records = cs.get("sail_records")
    _require(
        type(sail_records) is int and sail_records > 0,
        f"{label}: sail_records must be > 0, got {sail_records!r}",
    )
    perturbed = _as_list(cs.get("perturbed_controls"), f"{label}.perturbed_controls")
    by_name: dict[str, Mapping[str, object]] = {}
    for idx, item in enumerate(perturbed):
        ctrl = _as_mapping(item, f"{label}.perturbed_controls[{idx}]")
        name = ctrl.get("name")
        if not isinstance(name, str) or name in by_name:
            raise ValueError(f"{label}: invalid/duplicate control name {name!r}")
        _require(
            ctrl.get("verdict") == "fail",
            f"{label}.{name}: expected verdict 'fail', got {ctrl.get('verdict')!r}",
        )
        check_id = ctrl.get("check_id")
        interp_code = ctrl.get("interp_code")
        target_code = ctrl.get("target_code")
        _require(
            type(check_id) is int
            and type(interp_code) is int
            and type(target_code) is int
            and interp_code == target_code == check_id,
            f"{label}.{name}: expected interp_code == target_code == check_id, "
            f"got {interp_code!r}/{target_code!r}/{check_id!r}",
        )
        by_name[name] = ctrl
    _require(
        set(by_name.keys()) == set(EXPECTED_PERTURBED_CONTROLS),
        f"{label}: perturbed_controls keys mismatch: {sorted(by_name.keys())}",
    )
    return by_name


def _validate_purecap_controls(runs: Mapping[str, object], label: str) -> None:
    _require(
        set(runs.keys()) == set(EXPECTED_PURECAP_CONTROLS.keys()),
        f"{label}: keys mismatch: {sorted(runs.keys())}",
    )
    for name, (exp_verdict, exp_code, exp_roundtrip) in EXPECTED_PURECAP_CONTROLS.items():
        entry = _as_mapping(runs[name], f"{label}.{name}")
        _require(
            entry.get("verdict") == exp_verdict,
            f"{label}.{name}: expected verdict {exp_verdict!r}, got {entry.get('verdict')!r}",
        )
        code = entry.get("code")
        _require(
            type(code) is int and code == exp_code,
            f"{label}.{name}: expected code {exp_code}, got {code!r}",
        )
        _require(
            entry.get("cap_roundtrip") is exp_roundtrip,
            f"{label}.{name}: expected cap_roundtrip={exp_roundtrip!r}, got {entry.get('cap_roundtrip')!r}",
        )
        records = entry.get("records")
        _require(type(records) is int and records > 0, f"{label}.{name}: records must be > 0, got {records!r}")


def _validate_entry_observer(
    summary: Mapping[str, object],
    qualification: Mapping[str, object],
) -> None:
    observer = _as_mapping(summary.get("integrated_entry_observer"), "summary.integrated_entry_observer")
    _require(
        observer.get("no_tagged_store_into_result_fields") is True,
        "integrated_entry_observer: no_tagged_store_into_result_fields must be True",
    )
    calls_count = observer.get("first_slice_calls_count")
    calls = _as_list(observer.get("first_slice_calls"), "integrated_entry_observer.first_slice_calls")
    _require(
        type(calls_count) is int and calls_count == _FIRST_SLICE_CALL_COUNT and len(calls) == calls_count,
        f"integrated_entry_observer: expected {_FIRST_SLICE_CALL_COUNT} first_slice_calls, "
        f"got count={calls_count!r} len={len(calls)}",
    )
    for idx, raw_call in enumerate(calls):
        call = _as_mapping(raw_call, f"integrated_entry_observer.first_slice_calls[{idx}]")
        _require(
            call.get("mismatches") == [],
            f"integrated_entry_observer.first_slice_calls[{idx}]: non-empty mismatches {call.get('mismatches')!r}",
        )

    teo = _as_mapping(qualification.get("target_entry_observations"), "qualification.target_entry_observations")
    q_first = _as_mapping(teo.get("first_slice"), "qualification.target_entry_observations.first_slice")
    q_calls = _as_list(q_first.get("calls"), "qualification.target_entry_observations.first_slice.calls")
    _require(
        len(q_calls) == _FIRST_SLICE_CALL_COUNT,
        f"qualification.target_entry_observations.first_slice: expected {_FIRST_SLICE_CALL_COUNT} calls",
    )
    for idx, (s_call, q_raw) in enumerate(zip(calls, q_calls, strict=True)):
        q_call = _as_mapping(q_raw, f"qualification.target_entry_observations.first_slice.calls[{idx}]")
        _require(
            q_call.get("mismatches") == [],
            f"qualification.target_entry_observations.first_slice.calls[{idx}]: non-empty mismatches",
        )
        _require(
            cast(Mapping[str, object], s_call).get("case") == q_call.get("case"),
            f"integrated_entry_observer: first_slice_calls[{idx}] case disagrees with qualification",
        )

    pec = _as_mapping(
        observer.get("perturbed_entry_controls"),
        "integrated_entry_observer.perturbed_entry_controls",
    )
    _require(
        set(pec.keys()) == set(EXPECTED_PERTURBED_CONTROLS),
        f"integrated_entry_observer.perturbed_entry_controls keys mismatch: {sorted(pec.keys())}",
    )
    for ctrl_name in EXPECTED_PERTURBED_CONTROLS:
        ctrl = _as_mapping(pec[ctrl_name], f"perturbed_entry_controls.{ctrl_name}")
        observed = ctrl.get("calls_observed")
        mbc = _as_list(ctrl.get("mismatches_by_call"), f"perturbed_entry_controls.{ctrl_name}.mismatches_by_call")
        _require(
            type(observed) is int and observed > 0 and len(mbc) == observed,
            f"perturbed_entry_controls.{ctrl_name}: calls_observed/mismatches_by_call mismatch",
        )
        q_ctrl = _as_mapping(teo.get(ctrl_name), f"qualification.target_entry_observations.{ctrl_name}")
        q_ctrl_calls = _as_list(q_ctrl.get("calls"), f"qualification.target_entry_observations.{ctrl_name}.calls")
        _require(
            len(q_ctrl_calls) == observed,
            f"qualification.target_entry_observations.{ctrl_name}: call count disagrees with summary",
        )
        q_mbc = [
            _as_mapping(c, f"qualification.target_entry_observations.{ctrl_name}.calls[{i}]").get("mismatches")
            for i, c in enumerate(q_ctrl_calls)
        ]
        _require(
            q_mbc == mbc,
            f"perturbed_entry_controls.{ctrl_name}: mismatches_by_call disagrees with qualification",
        )
        if ctrl_name in EXPECTED_ENTRY_MISMATCHES:
            expected_field = EXPECTED_ENTRY_MISMATCHES[ctrl_name]
            _require(
                any(isinstance(m, list) and expected_field in m for m in mbc),
                f"perturbed_entry_controls.{ctrl_name}: expected mismatch {expected_field!r} in {mbc!r}",
            )


def _validate_suites(summary: Mapping[str, object]) -> int:
    new_controls = _as_mapping(summary.get("new_f594585_controls"), "summary.new_f594585_controls")
    suites = _as_mapping(new_controls.get("suites"), "summary.new_f594585_controls.suites")
    _require(bool(suites), "summary.new_f594585_controls.suites must be non-empty")
    total_cases = 0
    for suite_name, raw_suite in suites.items():
        suite = _as_mapping(raw_suite, f"suites.{suite_name}")
        rc = suite.get("returncode")
        _require(type(rc) is int and rc == 0, f"suites.{suite_name}: returncode must be 0, got {rc!r}")
        skipped_slow = suite.get("cases_skipped_slow")
        skipped_unavail = suite.get("cases_skipped_unavailable")
        _require(
            type(skipped_slow) is int and skipped_slow == 0,
            f"suites.{suite_name}: cases_skipped_slow must be 0, got {skipped_slow!r}",
        )
        _require(
            type(skipped_unavail) is int and skipped_unavail == 0,
            f"suites.{suite_name}: cases_skipped_unavailable must be 0, got {skipped_unavail!r}",
        )
        modules = _as_mapping(suite.get("modules"), f"suites.{suite_name}.modules")
        _require(bool(modules), f"suites.{suite_name}.modules must be non-empty")
        module_sum = 0
        for mod_name, mod_count in modules.items():
            _require(
                type(mod_count) is int and mod_count > 0,
                f"suites.{suite_name}.modules.{mod_name}: count must be > 0, got {mod_count!r}",
            )
            module_sum += cast(int, mod_count)
        cases_run = suite.get("cases_run")
        _require(
            type(cases_run) is int and cases_run > 0 and cases_run == module_sum,
            f"suites.{suite_name}: cases_run ({cases_run!r}) must be > 0 and equal sum(modules.values()) ({module_sum})",
        )
        total_cases += cast(int, cases_run)

    _require(
        total_cases >= _MIN_SUITE_CASES,
        f"new_f594585_controls.suites: total cases must be >= {_MIN_SUITE_CASES}, got {total_cases}",
    )
    if "total_cases_run" in new_controls:
        _require(
            new_controls["total_cases_run"] == total_cases,
            f"new_f594585_controls.total_cases_run ({new_controls['total_cases_run']!r}) != {total_cases}",
        )
    if "total_cases_skipped" in new_controls:
        _require(
            new_controls["total_cases_skipped"] == 0,
            f"new_f594585_controls.total_cases_skipped must be 0, got {new_controls['total_cases_skipped']!r}",
        )
    return total_cases


def validate_bundle(
    summary: Mapping[str, object],
    bindings: Mapping[str, object],
    qualification: Mapping[str, object],
    *,
    qualification_sha256: str | None = None,
) -> None:
    """Validate all non-acceptance, provenance, proof, simulation, and suite invariants of Q25ba."""
    _require_false_flags(
        bindings,
        ("artifact_accepted", "production_admission", "proof_replayed"),
        "bindings",
    )
    summary_qual = _as_mapping(summary.get("qualification"), "summary.qualification")
    _require_false_flags(
        summary_qual,
        (
            "artifact_accepted",
            "production_admission",
            "source_correspondence",
            "full_machine_refinement_closed",
        ),
        "summary.qualification",
    )
    _require_false_flags(
        qualification,
        (
            "artifact_accepted",
            "production_admission",
            "source_correspondence",
            "full_machine_refinement_closed",
        ),
        "qualification",
    )

    _require(bindings.get("status") == "matched", f"bindings: status must be 'matched', got {bindings.get('status')!r}")
    summary_bindings = _as_mapping(summary.get("bindings"), "summary.bindings")
    _require(dict(bindings) == dict(summary_bindings), "bindings.json disagrees with summary.bindings")
    _validate_missing_deployed(bindings.get("missing_deployed_evidence"), "bindings.missing_deployed_evidence")
    q_inv = _as_mapping(qualification.get("inventory"), "qualification.inventory")
    _validate_missing_deployed(
        q_inv.get("missing_deployed_evidence"),
        "qualification.inventory.missing_deployed_evidence",
    )

    bindings_receipt = _require_sha256_str(bindings.get("receipt_sha256"), "bindings.receipt_sha256")
    summary_receipt = _require_sha256_str(summary_qual.get("receipt_sha256"), "summary.qualification.receipt_sha256")
    _require(
        bindings_receipt == summary_receipt,
        f"receipt_sha256 mismatch between bindings ({bindings_receipt}) and summary ({summary_receipt})",
    )
    if qualification_sha256 is not None:
        expected_qual_sha = _require_sha256_str(qualification_sha256, "qualification_sha256")
        _require(
            bindings_receipt == expected_qual_sha,
            f"receipt_sha256 mismatch against decompressed qualification.json "
            f"({bindings_receipt} vs {expected_qual_sha})",
        )

    holdfast = _as_mapping(summary.get("holdfast"), "summary.holdfast")
    commit = holdfast.get("commit")
    _require(
        isinstance(commit, str) and _HEX40_RE.fullmatch(commit) is not None,
        f"summary.holdfast.commit: expected 40-hex commit SHA, got {commit!r}",
    )
    _require(
        qualification.get("producer_revision") == commit,
        f"qualification.producer_revision ({qualification.get('producer_revision')!r}) != holdfast.commit ({commit!r})",
    )
    _require(
        summary.get("reuse_toml_sha256") == EXPECTED_REUSE_TOML_SHA256
        and holdfast.get("reuse_toml_sha256") == EXPECTED_REUSE_TOML_SHA256,
        "reuse_toml_sha256 disagrees with expected REUSE.toml digest",
    )
    reuse_diff = holdfast.get("reuse_and_licenses_diff")
    _require(
        isinstance(reuse_diff, str) and (reuse_diff == "empty" or reuse_diff.startswith("empty ")),
        f"holdfast.reuse_and_licenses_diff must report empty diff, got {reuse_diff!r}",
    )

    _validate_proof_honesty(summary_qual, "summary.qualification")
    _validate_proof_honesty(qualification, "qualification")
    for field in (
        "assumption_exports_count",
        "negative_controls_count",
        "capacity_invariance",
        "gallina_sha256",
        "lowered_c_sha256",
        "source_sha256",
    ):
        _require(
            summary_qual.get(field) == qualification.get(field),
            f"summary.qualification.{field} disagrees with qualification.{field}",
        )
    q_neg = _as_list(qualification.get("negative_controls"), "qualification.negative_controls")
    _require(
        len(q_neg) == qualification.get("negative_controls_count"),
        "qualification.negative_controls length disagrees with negative_controls_count",
    )

    s_cs = _as_mapping(summary.get("compcert_sail"), "summary.compcert_sail")
    q_cs = _as_mapping(qualification.get("compcert_sail"), "qualification.compcert_sail")
    s_perturbed = _validate_compcert_sail(s_cs, "summary.compcert_sail")
    q_perturbed = _validate_compcert_sail(q_cs, "qualification.compcert_sail")
    for field in (
        "available",
        "sail_verdict",
        "sail_cap_roundtrip",
        "interp_exit_code",
        "sail_records",
        "sail_trace_digest",
        "asm_sha256",
        "clight_sha256",
        "ccomp_sha256",
    ):
        _require(
            s_cs.get(field) == q_cs.get(field),
            f"summary.compcert_sail.{field} disagrees with qualification.compcert_sail.{field}",
        )
    for name in EXPECTED_PERTURBED_CONTROLS:
        _require(
            dict(s_perturbed[name]) == dict(q_perturbed[name]),
            f"compcert_sail.perturbed_controls.{name} disagrees between summary and qualification",
        )

    s_runs = _as_mapping(summary.get("purecap_cheri_runs"), "summary.purecap_cheri_runs")
    q_runs = _as_mapping(qualification.get("purecap_cheri_runs"), "qualification.purecap_cheri_runs")
    _validate_purecap_controls(s_runs, "summary.purecap_cheri_runs")
    _validate_purecap_controls(q_runs, "qualification.purecap_cheri_runs")
    for name in EXPECTED_PURECAP_CONTROLS:
        s_entry = _as_mapping(s_runs[name], f"summary.purecap_cheri_runs.{name}")
        q_entry = _as_mapping(q_runs[name], f"qualification.purecap_cheri_runs.{name}")
        for field in ("verdict", "code", "cap_roundtrip", "records", "trace_digest"):
            _require(
                s_entry.get(field) == q_entry.get(field),
                f"purecap_cheri_runs.{name}.{field} disagrees between summary and qualification",
            )

    _validate_entry_observer(summary, qualification)

    nbc = _as_mapping(summary.get("negative_binding_control"), "summary.negative_binding_control")
    nbc_rc = nbc.get("returncode")
    nbc_msg = nbc.get("refusal_message")
    _require(
        type(nbc_rc) is int and nbc_rc != 0,
        f"negative_binding_control: returncode must be non-zero, got {nbc_rc!r}",
    )
    _require(
        isinstance(nbc_msg, str) and bool(nbc_msg.strip()),
        "negative_binding_control: missing non-empty refusal_message",
    )

    _validate_suites(summary)


def validate_bundle_dir(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Verify `manifest.json` digests and validate the Q25ba retained evidence bundle at `bundle_dir`."""
    summary, bindings, qualification, decompressed_sha256 = validate_manifest(bundle_dir)
    validate_bundle(
        summary,
        bindings,
        qualification,
        qualification_sha256=decompressed_sha256,
    )
    return summary, bindings, qualification


def main(argv: list[str] | None = None) -> int:
    """CLI entry point validating a HoldFast Q25ba retained evidence bundle."""
    default_bundle = Path(__file__).resolve().parents[2] / DEFAULT_BUNDLE_REL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=default_bundle,
        help=f"Path to Q25ba retained bundle directory (default: {DEFAULT_BUNDLE_REL})",
    )
    args = parser.parse_args(argv)
    bundle_dir = cast(Path, args.bundle).resolve()
    summary, bindings, _ = validate_bundle_dir(bundle_dir)
    total_cases = _validate_suites(summary)
    result = {
        "status": "ok",
        "bundle": str(bundle_dir),
        "holdfast_commit": summary["holdfast"]["commit"],
        "receipt_sha256": bindings["receipt_sha256"],
        "purecap_controls": len(EXPECTED_PURECAP_CONTROLS),
        "perturbed_controls": len(EXPECTED_PERTURBED_CONTROLS),
        "suite_cases_run": total_cases,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
