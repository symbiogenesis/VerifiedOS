# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests and refusal controls for `vos.holdfast_q25ba` and its retained bundle."""

import copy
import gzip
import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.harness import TOOLS, Case, ensure
from vos import holdfast_q25ba as q25ba

INDEPENDENT_CASES = True

REPO_ROOT = TOOLS.parent
LIVE_BUNDLE_DIR = REPO_ROOT / q25ba.DEFAULT_BUNDLE_REL


def _refuse(fn: Callable[[], object], expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        ensure(expected in str(exc), f"expected {expected!r} in refusal, got: {exc}")
        return
    raise AssertionError(f"expected ValueError containing {expected!r}")


def _live_bundle_positive() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)
    ensure(qual_sha == bindings["receipt_sha256"], "manifest decompressed SHA disagrees with bindings")
    s2, b2, q2 = q25ba.validate_bundle_dir(LIVE_BUNDLE_DIR)
    ensure(s2 == summary and b2 == bindings and q2 == qualification, "validate_bundle_dir mismatch")
    ensure(q25ba.main(["--bundle", str(LIVE_BUNDLE_DIR)]) == 0, "CLI main failed on live bundle")


def _non_acceptance_flag_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    for key in ("artifact_accepted", "production_admission", "proof_replayed"):
        bad_bindings = copy.deepcopy(bindings)
        bad_bindings[key] = True
        _refuse(
            lambda b=bad_bindings: q25ba.validate_bundle(
                summary, b, qualification, qualification_sha256=qual_sha
            ),
            f"bindings: {key} must be False",
        )

    for key in (
        "artifact_accepted",
        "production_admission",
        "source_correspondence",
        "full_machine_refinement_closed",
    ):
        bad_summary = copy.deepcopy(summary)
        bad_summary["qualification"][key] = True
        _refuse(
            lambda s=bad_summary: q25ba.validate_bundle(
                s, bindings, qualification, qualification_sha256=qual_sha
            ),
            f"summary.qualification: {key} must be False",
        )

        bad_qual = copy.deepcopy(qualification)
        bad_qual[key] = True
        _refuse(
            lambda q=bad_qual: q25ba.validate_bundle(
                summary, bindings, q, qualification_sha256=qual_sha
            ),
            f"qualification: {key} must be False",
        )


def _bindings_and_missing_evidence_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    for key in q25ba.REQUIRED_MISSING_DEPLOYED_KEYS:
        missing_key_b = copy.deepcopy(bindings)
        del missing_key_b["missing_deployed_evidence"][key]
        missing_key_s = copy.deepcopy(summary)
        del missing_key_s["bindings"]["missing_deployed_evidence"][key]
        _refuse(
            lambda s=missing_key_s, b=missing_key_b: q25ba.validate_bundle(
                s, b, qualification, qualification_sha256=qual_sha
            ),
            f"missing or blank required key {key!r}",
        )

        blank_val_b = copy.deepcopy(bindings)
        blank_val_b["missing_deployed_evidence"][key] = "   "
        blank_val_s = copy.deepcopy(summary)
        blank_val_s["bindings"]["missing_deployed_evidence"][key] = "   "
        _refuse(
            lambda s=blank_val_s, b=blank_val_b: q25ba.validate_bundle(
                s, b, qualification, qualification_sha256=qual_sha
            ),
            f"missing or blank required key {key!r}",
        )


def _proof_honesty_and_receipt_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    bad_trusted_summary = copy.deepcopy(summary)
    bad_trusted_summary["qualification"]["solver_trusted_count"] = 1
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_trusted_summary, bindings, qualification, qualification_sha256=qual_sha
        ),
        "summary.qualification: solver_trusted_count must be 0",
    )

    bad_axioms_summary = copy.deepcopy(summary)
    bad_axioms_summary["qualification"]["solver_trusted_axioms"] = ["trusted_ax"]
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_axioms_summary, bindings, qualification, qualification_sha256=qual_sha
        ),
        "summary.qualification: solver_trusted_axioms must be []",
    )

    bad_trusted_qual = copy.deepcopy(qualification)
    bad_trusted_qual["solver_trusted_count"] = 2
    _refuse(
        lambda: q25ba.validate_bundle(
            summary, bindings, bad_trusted_qual, qualification_sha256=qual_sha
        ),
        "qualification: solver_trusted_count must be 0",
    )

    bad_axioms_qual = copy.deepcopy(qualification)
    bad_axioms_qual["solver_trusted_axioms"] = ["trusted_ax"]
    _refuse(
        lambda: q25ba.validate_bundle(
            summary, bindings, bad_axioms_qual, qualification_sha256=qual_sha
        ),
        "qualification: solver_trusted_axioms must be []",
    )

    bad_receipt_summary = copy.deepcopy(summary)
    bad_receipt_summary["qualification"]["receipt_sha256"] = "0" * 64
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_receipt_summary, bindings, qualification, qualification_sha256=qual_sha
        ),
        "receipt_sha256 mismatch between bindings",
    )

    bad_receipt_bindings = copy.deepcopy(bindings)
    bad_receipt_bindings["receipt_sha256"] = "0" * 64
    bad_receipt_sb = copy.deepcopy(summary)
    bad_receipt_sb["bindings"]["receipt_sha256"] = "0" * 64
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_receipt_sb, bad_receipt_bindings, qualification, qualification_sha256=qual_sha
        ),
        "receipt_sha256 mismatch between bindings",
    )

    _refuse(
        lambda: q25ba.validate_bundle(
            summary, bindings, qualification, qualification_sha256="f" * 64
        ),
        "receipt_sha256 mismatch against decompressed qualification.json",
    )


def _perturbed_and_purecap_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    bad_perturbed_pass = copy.deepcopy(summary)
    bad_perturbed_pass["compcert_sail"]["perturbed_controls"][0]["verdict"] = "pass"
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_perturbed_pass, bindings, qualification, qualification_sha256=qual_sha
        ),
        "expected verdict 'fail'",
    )

    bad_perturbed_code = copy.deepcopy(summary)
    bad_perturbed_code["compcert_sail"]["perturbed_controls"][0]["interp_code"] = 999
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_perturbed_code, bindings, qualification, qualification_sha256=qual_sha
        ),
        "expected interp_code == target_code == check_id",
    )

    bad_trap_code = copy.deepcopy(summary)
    bad_trap_code["purecap_cheri_runs"]["bounds-trap"]["code"] = 0
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_trap_code, bindings, qualification, qualification_sha256=qual_sha
        ),
        "bounds-trap: expected code 284",
    )

    bad_trap_verdict = copy.deepcopy(summary)
    bad_trap_verdict["purecap_cheri_runs"]["perm-trap"]["verdict"] = "pass"
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_trap_verdict, bindings, qualification, qualification_sha256=qual_sha
        ),
        "perm-trap: expected verdict 'trap'",
    )


def _observer_and_negative_binding_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    bad_call_mismatch = copy.deepcopy(summary)
    bad_call_mismatch["integrated_entry_observer"]["first_slice_calls"][0]["mismatches"] = ["view.cursor"]
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_call_mismatch, bindings, qualification, qualification_sha256=qual_sha
        ),
        "non-empty mismatches",
    )

    bad_tagged_store = copy.deepcopy(summary)
    bad_tagged_store["integrated_entry_observer"]["no_tagged_store_into_result_fields"] = False
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_tagged_store, bindings, qualification, qualification_sha256=qual_sha
        ),
        "no_tagged_store_into_result_fields must be True",
    )

    for ctrl_name, expected_field in q25ba.EXPECTED_ENTRY_MISMATCHES.items():
        bad_entry_s = copy.deepcopy(summary)
        bad_entry_q = copy.deepcopy(qualification)
        bad_entry_s["integrated_entry_observer"]["perturbed_entry_controls"][ctrl_name]["mismatches_by_call"] = [
            [] for _ in bad_entry_s["integrated_entry_observer"]["perturbed_entry_controls"][ctrl_name]["mismatches_by_call"]
        ]
        for call in bad_entry_q["target_entry_observations"][ctrl_name]["calls"]:
            call["mismatches"] = []
        _refuse(
            lambda s=bad_entry_s, q=bad_entry_q: q25ba.validate_bundle(
                s, bindings, q, qualification_sha256=qual_sha
            ),
            f"expected mismatch {expected_field!r}",
        )

    bad_nbc = copy.deepcopy(summary)
    bad_nbc["negative_binding_control"]["returncode"] = 0
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_nbc, bindings, qualification, qualification_sha256=qual_sha
        ),
        "returncode must be non-zero",
    )


def _suite_refusals() -> None:
    summary, bindings, qualification, qual_sha = q25ba.validate_manifest(LIVE_BUNDLE_DIR)

    bad_skip_slow = copy.deepcopy(summary)
    bad_skip_slow["new_f594585_controls"]["suites"]["holdfast_graded"]["cases_skipped_slow"] = 1
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_skip_slow, bindings, qualification, qualification_sha256=qual_sha
        ),
        "cases_skipped_slow must be 0",
    )

    bad_skip_unavail = copy.deepcopy(summary)
    bad_skip_unavail["new_f594585_controls"]["suites"]["holdfast_loan"]["cases_skipped_unavailable"] = 1
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_skip_unavail, bindings, qualification, qualification_sha256=qual_sha
        ),
        "cases_skipped_unavailable must be 0",
    )

    bad_suite_rc = copy.deepcopy(summary)
    bad_suite_rc["new_f594585_controls"]["suites"]["locked_resolution"]["returncode"] = 1
    _refuse(
        lambda: q25ba.validate_bundle(
            bad_suite_rc, bindings, qualification, qualification_sha256=qual_sha
        ),
        "returncode must be 0",
    )


def _manifest_digest_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="q25ba-manifest-") as td:
        bundle = Path(td) / "bundle"
        shutil.copytree(LIVE_BUNDLE_DIR, bundle)
        q25ba.validate_bundle_dir(bundle)

        # Corrupt identity member digest
        summary_path = bundle / "summary.json"
        orig_summary = summary_path.read_bytes()
        summary_obj = json.loads(orig_summary.decode("utf-8"))
        summary_obj["scope"] = "tampered"
        summary_path.write_text(json.dumps(summary_obj), encoding="utf-8")
        _refuse(lambda: q25ba.validate_manifest(bundle), "manifest.summary.json: bytes/sha256 mismatch")
        summary_path.write_bytes(orig_summary)

        # Corrupt gzip stored digest while keeping valid gzip bytes
        gz_path = bundle / "qualification.json.gz"
        orig_gz = gz_path.read_bytes()
        raw_qual = gzip.decompress(orig_gz)
        recompressed = gzip.compress(raw_qual, compresslevel=1)
        ensure(
            hashlib.sha256(recompressed).hexdigest() != hashlib.sha256(orig_gz).hexdigest(),
            "recompressed gzip must differ in stored digest for negative control",
        )
        gz_path.write_bytes(recompressed)
        _refuse(
            lambda: q25ba.validate_manifest(bundle),
            "manifest.qualification.json.gz: stored_bytes/stored_sha256 mismatch",
        )

        # Corrupt decompressed qualification digest in manifest
        manifest_path = bundle / "manifest.json"
        manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
        manifest["files"]["qualification.json.gz"]["stored_bytes"] = len(recompressed)
        manifest["files"]["qualification.json.gz"]["stored_sha256"] = hashlib.sha256(recompressed).hexdigest()
        manifest["files"]["qualification.json.gz"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        _refuse(
            lambda: q25ba.validate_manifest(bundle),
            "manifest.qualification.json.gz: bytes/sha256 mismatch",
        )


def cases() -> list[Case]:
    return [
        Case("holdfast-q25ba-live-bundle-passes", _live_bundle_positive),
        Case("holdfast-q25ba-refuses-non-acceptance-flags", _non_acceptance_flag_refusals),
        Case("holdfast-q25ba-refuses-missing-deployed-evidence", _bindings_and_missing_evidence_refusals),
        Case("holdfast-q25ba-refuses-proof-honesty-and-receipt-drift", _proof_honesty_and_receipt_refusals),
        Case("holdfast-q25ba-refuses-perturbed-and-purecap-drift", _perturbed_and_purecap_refusals),
        Case("holdfast-q25ba-refuses-entry-observer-and-binding-drift", _observer_and_negative_binding_refusals),
        Case("holdfast-q25ba-refuses-suite-skips-or-failures", _suite_refusals),
        Case("holdfast-q25ba-refuses-corrupted-manifest-digests", _manifest_digest_refusals),
    ]
