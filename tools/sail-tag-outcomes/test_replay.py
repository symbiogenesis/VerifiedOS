# SPDX-License-Identifier: Apache-2.0
"""Focused host controls for qualification output isolation and input identity."""
import json
import runpy
import tempfile
import unittest
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name("replay.py")))
output_path = helpers["output_path"]
require_sha = helpers["require_sha"]
sha = helpers["sha"]
retained_emission_inputs = helpers["retained_emission_inputs"]


class IsolationControls(unittest.TestCase):
    def test_fresh_sibling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-tag-host-") as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            self.assertEqual(output_path(str(root / "output"), (source,)), root / "output")

    def test_overlap_and_aliases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-tag-host-") as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "nested").mkdir()
            (root / "alias").mkdir()
            for path in [source, source / "new", root, root / "alias" / ".." / "source"]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    output_path(str(path), (source,))

    def test_relative_and_unexpanded(self) -> None:
        for path in ["relative-output", "%TEMP%/output"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                output_path(path, ())

    def test_exact_input_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-tag-host-") as directory:
            source = Path(directory) / "source"
            source.write_bytes(b"bound bytes")
            digest = sha(source)
            require_sha(source, digest)
            source.write_bytes(b"changed bytes")
            with self.assertRaises(ValueError):
                require_sha(source, digest)

    def test_retained_emission_binds_other_plugins_and_solver(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-tag-host-") as directory:
            root = Path(directory)
            plugin, companion, sail, z3 = (
                root / name for name in ("sail_plugin_coq.cmxs", "sail_plugin_c.cmxs", "sail", "z3")
            )
            inputs = (plugin, companion, sail, z3)
            for path in inputs:
                path.write_text(path.name, encoding="utf-8")
            expected = {"bindings.v": "recorded digest"}
            evidence = root / "reading.json"
            evidence.write_text(json.dumps({
                "checks": {"matched_retained_outputs": True, "unchanged_inputs": True},
                "input_hashes": {f"/old/location/{path.name}": sha(path) for path in inputs},
                "expected": expected,
            }), encoding="utf-8")
            self.assertEqual(
                retained_emission_inputs(evidence, plugin, sail, z3),
                ({plugin: sha(plugin), companion: sha(companion)}, expected),
            )
            for path in (companion, z3):
                with self.subTest(path=path):
                    path.write_bytes(b"different")
                    with self.assertRaisesRegex(ValueError, path.name):
                        retained_emission_inputs(evidence, plugin, sail, z3)
                    path.write_text(path.name, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
