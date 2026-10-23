# SPDX-License-Identifier: Apache-2.0
"""Focused safety controls for the native metadata harness; no prover execution."""
import json
import runpy
import tempfile
import unittest
from pathlib import Path

from tests.harness import Case

_HELPERS = runpy.run_path(str(Path(__file__).resolve().parents[1] / "rocq-census/qualify.py"))


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
        self.assertEqual(_HELPERS["control_verdict"](0, False), (1, "identity-refused"))
        self.assertEqual(_HELPERS["control_verdict"](0, True), (0, "native-metadata-control-only"))
        self.assertEqual(_HELPERS["control_verdict"](2, True), (2, "refused"))

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
    return [Case("metadata-output-guard-refuses-missing-duplicate-and-foreign-emissions", checks.test_output_guard_refuses_missing_duplicate_and_foreign_emissions),
            Case("canonical-output-overlap-refuses-before-creation", checks.test_canonical_overlap_refuses_before_creation),
            Case("support-and-source-inputs-are-protected", checks.test_support_and_source_are_protected),
            Case("existing-and-relative-outputs-refuse", checks.test_existing_and_relative_outputs_refuse),
            Case("fresh-output-is-canonical", checks.test_unrelated_fresh_output_is_canonical),
            Case("identity-refusal-overrides-native-success", checks.test_identity_changes_override_native_success),
            Case("population-rescan-detects-membership-and-byte-changes", checks.test_population_detects_additions_deletions_and_content_changes)]
