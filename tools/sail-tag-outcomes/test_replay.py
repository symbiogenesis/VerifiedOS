# SPDX-License-Identifier: Apache-2.0
"""Focused host controls for qualification output isolation and input identity."""
import hashlib
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
match_v1_reading = helpers["match_v1_reading"]


class IsolationControls(unittest.TestCase):
    def test_frozen_v1_declarations(self) -> None:
        trace = "bindings_types.Interface.pure_iTrace_aux"
        wrapper = "bindings_types.Interface.pure_iTrace"
        bodies = {trace: "TagRead _ => recurse tail", wrapper: "pure_iTrace_aux trace"}
        checks = {name: name + " : Prop" for name in bodies}
        abouts = {
            name: (f"{checks[name]}\n\n{name} is not universe polymorphic\n"
                   f"{name} is transparent\nExpands to: Constant {name}")
            for name in bodies
        }
        expected = {name: {"kind": "Constant", "opacity": "transparent", "universes": "monomorphic",
                           "check": checks[name], "about": abouts[name], "print": body}
                    for name, body in bodies.items()}
        frozen = hashlib.sha256((json.dumps(expected, indent=2, sort_keys=True) + "\n").encode()).hexdigest()
        names = sorted(bodies)

        def query(phase: str, content: str) -> str:
            if phase == "Inventory":
                self.assertIn("Search _ inside bindings_types.Interface bindings_types.Defs.", content)
                return "Current search blacklist :  is empty.\n" + "".join(f"{name}: Prop\n" for name in names)
            answers = []
            for name in names:
                if phase == "Facts":
                    self.assertIn(f"Check @{name}.", content)
                    self.assertIn(f"About {name}.", content)
                    answers.extend([(name + "|check", checks[name]),
                                    (name + "|about", abouts[name] + "\nDeclared in a relocated file")])
                elif phase == "Bodies":
                    self.assertIn(f"Print {name}.", content)
                    answers.append((name + "|print", bodies[name]))
                else:
                    self.fail(f"unexpected query {phase}")
            return "".join(f"VOS_PROOF_READING|{key}\n{value}\n" for key, value in answers)

        with tempfile.TemporaryDirectory(prefix="vos-tag-reading-") as directory:
            output = Path(directory) / "v1-candidate.json"
            match_v1_reading(query, output, frozen)
            for subject, current, replacement in (
                (trace, bodies, "TagRead _ => True"), (wrapper, bodies, "True"),
                (trace, checks, "different type"), (wrapper, abouts, abouts[wrapper] + "\nextra metadata"),
            ):
                with self.subTest(subject=subject, replacement=replacement):
                    original = current[subject]
                    current[subject] = replacement
                    with self.assertRaisesRegex(ValueError, "differ from the frozen reading"):
                        match_v1_reading(query, output, frozen)
                    current[subject] = original
            names.remove(wrapper)
            with self.assertRaisesRegex(ValueError, "differ from the frozen reading"):
                match_v1_reading(query, output, frozen)

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
