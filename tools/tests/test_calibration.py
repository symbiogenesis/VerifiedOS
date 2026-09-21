# SPDX-License-Identifier: Apache-2.0
"""The calibration schema cannot accept measured values as qualified facts."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.harness import Case
from vos import calibration

ROOT = Path(__file__).resolve().parents[2]


class CalibrationTests(unittest.TestCase):
    def test_each_class_has_a_declaration_and_wrong_owner_is_refused(self) -> None:
        data = json.loads((ROOT / calibration.SOURCE).read_text(encoding="utf-8"))
        for row in data["classes"]:
            declaration = {"name": "candidate", "class": row["id"], "ceiling_owner": row["ceiling_owner"]}
            calibration.validate_field(ROOT, declaration)
            with self.assertRaises(ValueError):
                calibration.validate_field(ROOT, {**declaration, "ceiling_owner": "R-17-062"})
            with self.assertRaises(ValueError):
                calibration.validate_field(ROOT, {**declaration, "value": 1})

    def test_out_of_class_field_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            calibration.validate_field(ROOT, {"name": "candidate", "class": "authority-trim", "ceiling_owner": "R-15-127"})

    def test_schema_controls(self) -> None:
        original = json.loads((ROOT / calibration.SOURCE).read_text(encoding="utf-8"))
        mutations = []
        missing = copy.deepcopy(original)
        missing["classes"].pop()
        mutations.append(missing)
        duplicate = copy.deepcopy(original)
        duplicate["classes"][1] = duplicate["classes"][0]
        mutations.append(duplicate)
        populated = copy.deepcopy(original)
        populated["status"] = "qualified"
        mutations.append(populated)
        binding = copy.deepcopy(original)
        binding["device_tree"]["length"] = 0
        mutations.append(binding)
        owner = copy.deepcopy(original)
        owner["classes"][0]["ceiling_owner"] = "R-99-999"
        mutations.append(owner)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "interfaces").mkdir()
            (root / "docs").mkdir()
            (root / "docs/requirements-register.md").write_bytes((ROOT / "docs/requirements-register.md").read_bytes())
            for mutation in mutations:
                (root / calibration.SOURCE).write_text(json.dumps(mutation), encoding="utf-8")
                with self.assertRaises(ValueError):
                    calibration.load(root)

    def test_generated_view_records_the_open_physical_join(self) -> None:
        result = calibration.emit(ROOT)
        self.assertIn("current Sail device tree does not populate", result)
        self.assertIn("calibration-not-qualified", result)


def cases() -> list[Case]:
    checks = CalibrationTests()
    return [Case("classes-and-ceilings", checks.test_each_class_has_a_declaration_and_wrong_owner_is_refused),
            Case("out-of-class", checks.test_out_of_class_field_is_refused),
            Case("schema-controls", checks.test_schema_controls),
            Case("physical-join-open", checks.test_generated_view_records_the_open_physical_join)]
