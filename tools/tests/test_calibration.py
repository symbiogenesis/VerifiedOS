# SPDX-License-Identifier: Apache-2.0
"""The calibration schema cannot accept measured values as qualified facts."""

import copy
import json
import unittest
from pathlib import Path

from tests.harness import Case, sandbox_tree
from vos import calibration

ROOT = Path(__file__).resolve().parents[2]


def _files(owner: object) -> dict[str, str]:
    return {calibration.SOURCE: json.dumps(owner),
            calibration.SCHEMA: (ROOT / calibration.SCHEMA).read_text(encoding="utf-8"),
            calibration.FIELD_SCHEMA: (ROOT / calibration.FIELD_SCHEMA).read_text(encoding="utf-8"),
            "docs/requirements-register.md":
                (ROOT / "docs/requirements-register.md").read_text(encoding="utf-8")}


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
        mutations: list[object] = [None, [], dict(original, schema=True),
                                   dict(original, schema=1.0), dict(original, extra="unread")]
        for key in original:
            missing_key = copy.deepcopy(original)
            del missing_key[key]
            mutations.append(missing_key)
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
        for field, value in (("length", 32.0), ("length", True), ("property", "unknown"),
                             ("encoding", "hex"), ("absence", "none"), ("extra", "unread")):
            changed = copy.deepcopy(original)
            changed["device_tree"][field] = value
            mutations.append(changed)
        for field, value in (("id", "unknown"), ("id", " "), ("ceiling_owner", "R-15-127\n"),
                             ("ceiling_owner", "bad"), ("qualification_owner", "R6"),
                             ("containment", False), ("required_evidence", "\t"),
                             ("extra", "unread")):
            changed = copy.deepcopy(original)
            changed["classes"][0][field] = value
            mutations.append(changed)
        with sandbox_tree(_files(original)) as root:
            self.assertEqual(calibration.load(root), original)
            self.assertEqual(calibration.emit(root), calibration.emit(ROOT))
            for mutation in mutations:
                (root / calibration.SOURCE).write_text(json.dumps(mutation), encoding="utf-8")
                with self.assertRaises(ValueError):
                    calibration.load(root)
            duplicate_key = json.dumps(original).replace('"schema": 1', '"schema": 1, "schema": 1', 1)
            (root / calibration.SOURCE).write_text(duplicate_key, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                calibration.load(root)

    def test_field_shapes_refuse(self) -> None:
        good = {"name": "candidate", "class": "sensor-trim", "ceiling_owner": "R-15-127"}
        for field, value in (("name", "Upper"), ("name", "name\n"), ("name", False),
                             ("class", []), ("ceiling_owner", 1), ("extra", "unread")):
            with self.assertRaises(ValueError):
                calibration.validate_field(ROOT, {**good, field: value})
        for key in good:
            missing = {field: value for field, value in good.items() if field != key}
            with self.assertRaises(ValueError):
                calibration.validate_field(ROOT, missing)

    def test_schema_inputs_fail_closed(self) -> None:
        original = json.loads((ROOT / calibration.SOURCE).read_text(encoding="utf-8"))
        declaration = {"name": "candidate", "class": "sensor-trim", "ceiling_owner": "R-15-127"}
        for path in (calibration.SCHEMA, calibration.FIELD_SCHEMA):
            for contents in (None, "{", '{"type":"not-a-type"}',
                             '{"type":"object","type":"object"}'):
                files = _files(original)
                if contents is None:
                    del files[path]
                else:
                    files[path] = contents
                with sandbox_tree(files) as root, self.assertRaises(ValueError) as error:
                    calibration.validate_field(root, declaration)
                self.assertIn(Path(path).name, str(error.exception))

    def test_generated_view_records_the_open_physical_join(self) -> None:
        result = calibration.emit(ROOT)
        self.assertEqual(result, (ROOT / calibration.ARTIFACT).read_text(encoding="utf-8"))
        self.assertIn("current Sail device tree does not populate", result)
        self.assertIn("calibration-not-qualified", result)


def cases() -> list[Case]:
    checks = CalibrationTests()
    return [Case("classes-and-ceilings", checks.test_each_class_has_a_declaration_and_wrong_owner_is_refused),
            Case("out-of-class", checks.test_out_of_class_field_is_refused),
            Case("schema-controls", checks.test_schema_controls),
            Case("field-shapes", checks.test_field_shapes_refuse),
            Case("schema-inputs-fail-closed", checks.test_schema_inputs_fail_closed),
            Case("physical-join-open", checks.test_generated_view_records_the_open_physical_join)]
