# SPDX-License-Identifier: Apache-2.0
"""Focused safety controls for the native metadata harness; no prover execution."""
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case

_HELPERS = runpy.run_path(str(Path(__file__).resolve().parents[1] / "rocq-census/qualify.py"))


def _mock_campaign(outcome: object, *, unreadable_output: bool = False) -> tuple[int, dict[str, object], dict[str, object], bytes]:
    """Exercise the real receipt path while replacing every native launch."""
    with tempfile.TemporaryDirectory(prefix="vos-census-mocked-") as scratch:
        root = Path(scratch)
        switch, support, output = root / "switch", root / "support", root / "out"
        (switch / "bin").mkdir(parents=True)
        (switch / "lib/coq").mkdir(parents=True)
        (switch / "bin/rocq").write_bytes(b"mock-launcher")
        (switch / "lib/coq/installed.vo").write_bytes(b"installed")
        support.mkdir()
        (support / "support.vo").write_bytes(b"support")
        argv = ["rocq-census", "--switch-root", str(switch), "--support-source", str(support),
                "--out", str(output), "--targets", "Expected"]
        original_read = Path.read_bytes
        def read_bytes(path: Path) -> bytes:
            if unreadable_output and path.name == "native-query.stdout.log":
                raise OSError("mock output read refused")
            return original_read(path)
        with patch.object(sys, "argv", argv), redirect_stdout(StringIO()), patch.object(Path, "read_bytes", read_bytes), patch("subprocess.run", side_effect=[
            subprocess.CompletedProcess(["mock-plugin"], 0, stdout=b"", stderr=b""), outcome,
        ]) as native:
            main = cast("Callable[[], int]", _HELPERS["main"])
            code = main()
            receipt = cast("dict[str, object]", json.loads((output / "receipt.json").read_text()))
            checkpoint = cast("dict[str, object]", json.loads((output / "checkpoint.json").read_text()))
            if native.call_count != 2:
                raise AssertionError("mock campaign did not cover the query invocation")
        stdout = output / "native-query.stdout.log"
        return code, receipt, checkpoint, original_read(stdout) if stdout.exists() else b""

def _last_command(receipt: dict[str, object]) -> dict[str, object]:
    return cast("list[dict[str, object]]", receipt["commands"])[-1]


class RocqCensusHarnessTests(unittest.TestCase):
    def test_canonical_overlap_refuses_before_creation(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            protected = root / "switch"
            protected.mkdir()
            lane = root / "lane"
            lane.mkdir()
            aliases = (protected / "new", lane / ".." / "switch" / "new")
            for output in aliases:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    _HELPERS["validate_output"](output, (protected,))
                self.assertFalse((protected / "new").exists())

    def test_support_and_source_are_protected(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            support, source = root / "support", root / "source"
            support.mkdir()
            source.mkdir()
            for owner in (support, source):
                with self.subTest(owner=owner), self.assertRaises(ValueError):
                    _HELPERS["validate_output"](owner / "new", (support, source))

    def test_existing_and_relative_outputs_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            for output in (Path(scratch), Path("relative")):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    _HELPERS["validate_output"](output, ())

    def test_unrelated_fresh_output_is_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            owner = root / "support"
            owner.mkdir()
            output = root / "lane" / ".." / "fresh"
            self.assertEqual(_HELPERS["validate_output"](output, (owner,)), root.resolve() / "fresh")
            self.assertFalse((root / "fresh").exists())

    def test_identity_changes_override_native_success(self) -> None:
        flags = {"query_completed": True, "metadata_validated": True, "execution_finished": True}
        self.assertEqual(_HELPERS["control_verdict"](0, False, **flags), (1, "identity-refused"))
        self.assertEqual(_HELPERS["control_verdict"](0, True, **flags), (0, "native-metadata-control-only"))
        self.assertEqual(_HELPERS["control_verdict"](2, True, **flags), (2, "refused"))
        for missing in flags:
            with self.subTest(missing=missing):
                self.assertEqual(_HELPERS["control_verdict"](0, True, **(flags | {missing: False})), (1, "refused"))

    def test_output_guard_refuses_missing_duplicate_and_foreign_emissions(self) -> None:
        good = {"schema": "verifiedos-rocq-native-metadata/1", "acceptance": "metadata-only",
                "roots": [{"requested": "Expected", "native_path": {}, "module": {}}]}
        encoded = json.dumps(good).encode()
        self.assertIsNone(_HELPERS["metadata_output"](encoded, ["Expected"]))
        bad = [b"", encoded + b"\n" + encoded,
               json.dumps(good | {"schema": "other"}).encode(),
               json.dumps(good | {"acceptance": "accepted"}).encode(),
               json.dumps(good | {"roots": []}).encode()]
        for output in bad:
            with self.subTest(output=output), self.assertRaises(ValueError):
                _HELPERS["metadata_output"](output, ["Expected"])
        with self.assertRaises(ValueError):
            _HELPERS["metadata_output"](encoded, ["Foreign"])
        with self.assertRaises(ValueError):
            _HELPERS["metadata_output"](encoded, ["Expected", "Expected"])

    def test_query_timeout_retains_intent_and_partial_logs_without_success(self) -> None:
        timeout = subprocess.TimeoutExpired(["mock-query"], 180, output=b"partial output", stderr=b"partial error")
        code, receipt, checkpoint, stdout = _mock_campaign(timeout)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["verdict"], "refused")
        self.assertIsNone(receipt["native_exit"])
        self.assertFalse(receipt["query_completed"])
        self.assertFalse(receipt["metadata_validated"])
        self.assertEqual(stdout, b"partial output")
        self.assertEqual(_last_command(receipt)["status"], "timed-out")
        self.assertEqual(_last_command(checkpoint)["status"], "pending")
        self.assertIsNone(_last_command(checkpoint)["exit"])

    def test_query_launch_error_cannot_inherit_plugin_success(self) -> None:
        code, receipt, checkpoint, _ = _mock_campaign(OSError("mock query launch refused"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["verdict"], "refused")
        self.assertIsNone(receipt["native_exit"])
        self.assertEqual(_last_command(receipt)["status"], "launch-error")
        self.assertEqual(_last_command(checkpoint)["status"], "pending")

    def test_validation_read_failure_preserves_query_exit_and_refuses_evidence(self) -> None:
        result = subprocess.CompletedProcess(["mock-query"], 0, stdout=b"anything", stderr=b"")
        code, receipt, _, _ = _mock_campaign(result, unreadable_output=True)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["native_exit"], 0)
        self.assertTrue(receipt["query_completed"])
        self.assertFalse(receipt["metadata_validated"])
        self.assertEqual(receipt["verdict"], "refused")

    def test_mock_success_requires_completed_query_and_validated_metadata(self) -> None:
        metadata = {"schema": "verifiedos-rocq-native-metadata/1", "acceptance": "metadata-only",
                    "roots": [{"requested": "Expected", "native_path": {}, "module": {}}]}
        result = subprocess.CompletedProcess(["mock-query"], 0, stdout=json.dumps(metadata).encode(), stderr=b"")
        code, receipt, _, _ = _mock_campaign(result)
        self.assertEqual(code, 0)
        self.assertEqual(receipt["native_exit"], 0)
        self.assertTrue(receipt["query_completed"])
        self.assertTrue(receipt["metadata_validated"])
        self.assertTrue(receipt["execution_finished"])
        self.assertEqual(receipt["verdict"], "native-metadata-control-only")

    def test_population_detects_additions_deletions_and_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "keep.vo").write_bytes(b"old")
            (root / "gone.glob").write_bytes(b"gone")
            (root / "irrelevant.v").write_bytes(b"source")
            before = _HELPERS["population"](root)
            (root / "keep.vo").write_bytes(b"changed")
            (root / "gone.glob").unlink()
            (root / "added.vo").write_bytes(b"new")
            after = _HELPERS["population"](root)
            self.assertEqual(_HELPERS["changes"](before, after), {
                "added": ["added.vo"], "deleted": ["gone.glob"], "changed": ["keep.vo"]})


def cases() -> list[Case]:
    checks = RocqCensusHarnessTests()
    return [Case("query-timeout-retains-intent-partial-logs-and-refusal", checks.test_query_timeout_retains_intent_and_partial_logs_without_success),
            Case("query-launch-error-cannot-inherit-plugin-success", checks.test_query_launch_error_cannot_inherit_plugin_success),
            Case("output-read-error-refuses-evidence-after-query-success", checks.test_validation_read_failure_preserves_query_exit_and_refuses_evidence),
            Case("mock-success-requires-completed-validated-query", checks.test_mock_success_requires_completed_query_and_validated_metadata),
            Case("metadata-output-guard-refuses-missing-duplicate-and-foreign-emissions", checks.test_output_guard_refuses_missing_duplicate_and_foreign_emissions),
            Case("canonical-output-overlap-refuses-before-creation", checks.test_canonical_overlap_refuses_before_creation),
            Case("support-and-source-inputs-are-protected", checks.test_support_and_source_are_protected),
            Case("existing-and-relative-outputs-refuse", checks.test_existing_and_relative_outputs_refuse),
            Case("fresh-output-is-canonical", checks.test_unrelated_fresh_output_is_canonical),
            Case("identity-refusal-overrides-native-success", checks.test_identity_changes_override_native_success),
            Case("population-rescan-detects-membership-and-byte-changes", checks.test_population_detects_additions_deletions_and_content_changes)]
