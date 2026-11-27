# SPDX-License-Identifier: Apache-2.0
"""Focused host controls for canonical closure isolation, assumptions, kernel check, and manifest binding."""

import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from typing import cast

_HELPERS = runpy.run_path(str(Path(__file__).with_name("canonical_closure.py")))
_kernel_summary = runpy.run_path(str(Path(__file__).with_name("_test_helpers.py")))["kernel_summary"]
AUTHORED_CANONICAL_MODULES = cast(
    "tuple[str, ...]", _HELPERS["AUTHORED_CANONICAL_MODULES"],
)
KERNEL_CHECK_MODULES = cast(
    "tuple[str, ...]", _HELPERS["KERNEL_CHECK_MODULES"],
)
EXPECTED_CANONICAL_FP_AXIOMS = cast(
    "tuple[str, ...]", _HELPERS["EXPECTED_CANONICAL_FP_AXIOMS"],
)
WHOLE_TERM_MODULES = cast("tuple[str, ...]", _HELPERS["WHOLE_TERM_MODULES"])
output_path = _HELPERS["output_path"]
require_sha = _HELPERS["require_sha"]
sha = _HELPERS["sha"]
verify_whole_term_inputs = _HELPERS["verify_whole_term_inputs"]
verify_canonical_support_inputs = _HELPERS["verify_canonical_support_inputs"]
compare_installed_inventories = _HELPERS["compare_installed_inventories"]
verify_installed_unchanged = _HELPERS["verify_installed_unchanged"]
canonical_inventory_query = _HELPERS["canonical_inventory_query"]
canonical_assumption_query = _HELPERS["canonical_assumption_query"]
audit_canonical_assumptions = _HELPERS["audit_canonical_assumptions"]
verify_canonical_kernel_check = _HELPERS["verify_canonical_kernel_check"]
build_canonical_kernel_report = _HELPERS["build_canonical_kernel_report"]
verify_frozen_canonical_closure = _HELPERS["verify_frozen_canonical_closure"]


class CanonicalClosureControls(unittest.TestCase):
    """Positive and negative controls for `canonical_closure.py` helpers."""

    def test_output_path_accepts_new_and_empty_dirs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-canon-out-") as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            fresh = root / "fresh-out"
            self.assertEqual(output_path(str(fresh), (source,)), fresh.resolve())
            empty = root / "empty-out"
            empty.mkdir()
            self.assertEqual(output_path(str(empty), (source,)), empty.resolve())

    def test_output_path_refusals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-canon-out-refuse-") as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (root / "alias").mkdir()
            non_empty = root / "non-empty"
            non_empty.mkdir()
            (non_empty / "artifact.txt").write_text("stale\n", encoding="utf-8")
            regular_file = root / "regular.txt"
            regular_file.write_text("file\n", encoding="utf-8")
            for candidate in (
                source,
                source / "nested",
                root,
                root / "alias" / ".." / "source",
                non_empty,
                regular_file,
            ):
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    output_path(str(candidate), (source,))
        for bad in ("relative-out", "%TEMP%/canonical-closure"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                output_path(bad, ())

    def test_whole_term_and_support_input_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-canon-inputs-") as directory:
            root = Path(directory)
            whole_dir = root / "whole"
            support_dir = root / "support"
            whole_dir.mkdir()
            support_dir.mkdir()

            results = []
            for mod in WHOLE_TERM_MODULES:
                src = whole_dir / f"{mod}.v"
                obj = whole_dir / f"{mod}.vo"
                src.write_text(f"(* {mod} *)\n", encoding="utf-8")
                obj.write_bytes(f"vo:{mod}".encode())
                results.append({
                    "name": f"{mod}.v",
                    "source_sha256": sha(src),
                    "object_sha256": sha(obj),
                })
            compile_result = root / "compile-result.json"
            compile_result.write_text(json.dumps({"results": results}), encoding="utf-8")
            verified_whole = verify_whole_term_inputs(whole_dir, compile_result)
            self.assertEqual(set(verified_whole), set(WHOLE_TERM_MODULES))

            (whole_dir / "rv64d.vo").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "input digest mismatch"):
                verify_whole_term_inputs(whole_dir, compile_result)

            modules = ["Base", "Real", "Values"]
            support_map: dict[str, dict[str, str]] = {}
            for mod in modules:
                src = support_dir / f"{mod}.v"
                obj = support_dir / f"{mod}.vo"
                src.write_text(f"(* support {mod} *)\n", encoding="utf-8")
                obj.write_bytes(f"support-vo:{mod}".encode())
                support_map[mod] = {
                    "source_sha256": sha(src),
                    "object_sha256": sha(obj),
                }
            closure_reading = root / "closure-reading.json"
            closure_reading.write_text(
                json.dumps({"candidate_support_modules": support_map}),
                encoding="utf-8",
            )
            verified_support = verify_canonical_support_inputs(
                support_dir, closure_reading, modules,
            )
            self.assertEqual(set(verified_support), set(modules))

            with self.assertRaisesRegex(ValueError, "does not match qualification"):
                verify_canonical_support_inputs(support_dir, closure_reading, ["Base", "Real"])

            (support_dir / "Real.vo").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "input digest mismatch"):
                verify_canonical_support_inputs(support_dir, closure_reading, modules)

    def test_canonical_assumptions_audit_and_refusals(self) -> None:
        targets = {
            "TagInterpreter": (
                "CanonicalTagPlaneInst",
                ["CanonicalTagPlaneInst.tag_get", "CanonicalTagPlaneInst.legal_read"],
            ),
            "TagConservativity": (
                "CanonicalOldOutcomesInst",
                ["CanonicalOldOutcomesInst.tag_free_run_preserved"],
            ),
            "CanonicalPhysicalCallerBridge": (
                "CanonicalPhysicalCallerBridge",
                [
                    "CanonicalPhysicalCallerBridge.read_ram_request_order",
                    "CanonicalPhysicalCallerBridge.write_ram_request_order",
                ],
            ),
            "CanonicalTagConservativity": (
                "CanonicalTagConservativity",
                [
                    "CanonicalTagConservativity.read_ram_no_meta_preserves_tags",
                    "CanonicalTagConservativity.write_ram_refusal_run",
                ],
            ),
        }

        def make_query(
            *, empty_mod: str | None = None, axiom_symbol: str | None = None,
        ) -> object:
            def query(name: str, content: str) -> str:
                if name.startswith("AssumptionsInventory_"):
                    mod = name.removeprefix("AssumptionsInventory_")
                    target, symbols = targets[mod]
                    if mod == "TagInterpreter":
                        self.assertIn(
                            "Module CanonicalTagPlaneInst := TagInterpreter.TagPlane "
                            "rv64d_types.Arch rv64d_types.Interface.",
                            content,
                        )
                    elif mod == "TagConservativity":
                        self.assertIn(
                            "Module CanonicalOldOutcomesInst := TagConservativity.OldOutcomes "
                            "rv64d_types.Arch rv64d_types.Interface.",
                            content,
                        )
                    self.assertIn(f"Search _ inside {target}.", content)
                    if mod == empty_mod:
                        return "Current search blacklist :  is empty.\n"
                    return (
                        "Current search blacklist :  is empty.\n"
                        + "".join(f"{sym}: Prop\n" for sym in symbols)
                    )
                if name.startswith("AssumptionsCheck_"):
                    mod = name.removeprefix("AssumptionsCheck_")
                    _, symbols = targets[mod]
                    lines: list[str] = []
                    for sym in sorted(symbols):
                        self.assertIn(f"Print Assumptions {sym}.", content)
                        lines.append(f"VOS_PROOF_AUDIT|{sym}")
                        if sym == axiom_symbol:
                            lines.append("Axioms:")
                            lines.append("rv64d.riscv_f32Add : Prop")
                        else:
                            lines.append("Closed under the global context")
                    return "\n".join(lines) + "\n"
                self.fail(f"unexpected query {name}")
                return ""

            return query

        report = audit_canonical_assumptions(AUTHORED_CANONICAL_MODULES, make_query())
        self.assertTrue(report["all_closed"])
        self.assertEqual(report["total_declarations"], 7)
        self.assertEqual(
            report["modules"]["TagInterpreter"]["query_target"], "CanonicalTagPlaneInst",
        )
        self.assertTrue(report["modules"]["TagInterpreter"]["instantiated_functor"])
        self.assertEqual(
            report["modules"]["TagConservativity"]["query_target"], "CanonicalOldOutcomesInst",
        )
        self.assertTrue(report["modules"]["TagConservativity"]["instantiated_functor"])
        self.assertFalse(
            report["modules"]["CanonicalPhysicalCallerBridge"]["instantiated_functor"],
        )
        self.assertFalse(
            report["modules"]["CanonicalTagConservativity"]["instantiated_functor"],
        )

        with self.assertRaisesRegex(ValueError, "empty native inventory"):
            audit_canonical_assumptions(
                AUTHORED_CANONICAL_MODULES, make_query(empty_mod="TagInterpreter"),
            )

        with self.assertRaisesRegex(ValueError, "non-closed declaration"):
            audit_canonical_assumptions(
                AUTHORED_CANONICAL_MODULES,
                make_query(axiom_symbol="CanonicalTagConservativity.write_ram_refusal_run"),
            )

        target_ti, inv_ti = canonical_inventory_query("TagInterpreter")
        self.assertEqual(target_ti, "CanonicalTagPlaneInst")
        self.assertIn("Require rv64d_types TagInterpreter.", inv_ti)
        target_tc, inv_tc = canonical_inventory_query("TagConservativity")
        self.assertEqual(target_tc, "CanonicalOldOutcomesInst")
        self.assertIn("Require rv64d_types TagConservativity.", inv_tc)
        assump_ti = canonical_assumption_query(
            "TagInterpreter",
            [{"name": "CanonicalTagPlaneInst.tag_get", "type": "Prop",
              "assumptions": [], "claims": []}],
        )
        self.assertIn("Print Assumptions CanonicalTagPlaneInst.tag_get.", assump_ti)
        assump_tc = canonical_assumption_query(
            "TagConservativity",
            [{"name": "CanonicalOldOutcomesInst.tag_free_run_preserved", "type": "Prop",
              "assumptions": [], "claims": []}],
        )
        self.assertIn(
            "Print Assumptions CanonicalOldOutcomesInst.tag_free_run_preserved.",
            assump_tc,
        )

    def test_recursive_kernel_check_and_refusals(self) -> None:
        self.assertEqual(len(EXPECTED_CANONICAL_FP_AXIOMS), 31)
        portable_flags = [
            "-silent", "-o", "-boot",
            "-R", "<rocq_prefix>/lib/coq/theories", "Corelib",
            "-Q", "<rocq_prefix>/lib/coq/user-contrib/Stdlib", "Stdlib",
            "-Q", "<stdpp>", "stdpp",
            "-R", "<canonical_support>", "SailStdpp",
            "-R", "<whole_term_dir>", "",
            "-R", "<out>", "",
        ]
        argv = ["/opt/rocq/bin/rocqchk", *portable_flags, "CanonicalPhysicalCallerBridge"]
        summary = _kernel_summary(
            list(EXPECTED_CANONICAL_FP_AXIOMS),
            ["Corelib.Init.Logic.eq", "rv64d_types.Interface.outcome"],
        )
        report = verify_canonical_kernel_check(
            argv, 0, "", summary,
            portable_flags=portable_flags,
            elapsed_seconds=12.5,
        )
        self.assertTrue(report["recursive"])
        self.assertTrue(report["norec_absent"])
        self.assertFalse(report["norec_present"])
        self.assertEqual(report["axiom_count"], 31)
        self.assertEqual(report["unexpected_axioms"], [])
        self.assertEqual(report["missing_expected_axioms"], [])

        # Refuse -norec in argv or portable_flags.
        with self.assertRaisesRegex(ValueError, "-norec"):
            verify_canonical_kernel_check(
                [*argv, "-norec"], 0, "", summary, portable_flags=portable_flags,
            )
        with self.assertRaisesRegex(ValueError, "-norec"):
            verify_canonical_kernel_check(
                argv, 0, "", summary, portable_flags=[*portable_flags, "-norec"],
            )

        # Refuse unexpected axioms (Reals, Program.Wf, new bridge/tag axiom).
        for unexpected in (
            "Stdlib.Logic.Classical_Prop.classic",
            "Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq",
            "CanonicalPhysicalCallerBridge.extra_axiom",
        ):
            with self.subTest(unexpected=unexpected), self.assertRaisesRegex(
                ValueError, "axioms mismatch",
            ):
                verify_canonical_kernel_check(
                    argv, 0, "",
                    _kernel_summary([*EXPECTED_CANONICAL_FP_AXIOMS, unexpected]),
                    portable_flags=portable_flags,
                )

        # Refuse missing expected 31 FP axiom.
        with self.assertRaisesRegex(ValueError, "axioms mismatch"):
            verify_canonical_kernel_check(
                argv, 0, "",
                _kernel_summary(list(EXPECTED_CANONICAL_FP_AXIOMS[:-1])),
                portable_flags=portable_flags,
            )

        argv_conservativity = [
            "/opt/rocq/bin/rocqchk", *portable_flags, "CanonicalTagConservativity",
        ]
        conserv_report = verify_canonical_kernel_check(
            argv_conservativity, 0, "", summary,
            target_module="CanonicalTagConservativity",
            portable_flags=portable_flags,
            elapsed_seconds=11.0,
        )
        multi_report = build_canonical_kernel_report({
            "CanonicalPhysicalCallerBridge": report,
            "CanonicalTagConservativity": conserv_report,
        })
        self.assertEqual(multi_report["schema"], "verifiedos-canonical-tag-kernel-check/2")
        self.assertEqual(multi_report["target_modules"], list(KERNEL_CHECK_MODULES))
        self.assertEqual(multi_report["axiom_count"], 31)
        self.assertEqual(multi_report["total_elapsed_seconds"], 23.5)

        with self.assertRaisesRegex(ValueError, "target order"):
            build_canonical_kernel_report({"CanonicalTagConservativity": conserv_report})

        # Refuse non-zero exit code.
        with self.assertRaisesRegex(ValueError, "failed"):
            verify_canonical_kernel_check(
                argv, 1, "", summary, portable_flags=portable_flags,
            )

    def test_installed_comparison_and_refusals(self) -> None:
        before = {"/opt/rocq": {"bin/rocq": "aaa", "lib/a.vo": "bbb"}}
        after_same = {"/opt/rocq": {"bin/rocq": "aaa", "lib/a.vo": "bbb"}}
        changes = compare_installed_inventories(before, after_same)
        self.assertEqual(changes, {"/opt/rocq": []})
        verify_installed_unchanged(changes)

        after_modified = {"/opt/rocq": {"bin/rocq": "aaa", "lib/a.vo": "ccc", "lib/new": "ddd"}}
        bad_changes = compare_installed_inventories(before, after_modified)
        self.assertEqual(bad_changes, {"/opt/rocq": ["lib/a.vo", "lib/new"]})
        with self.assertRaisesRegex(ValueError, "installed paths changed"):
            verify_installed_unchanged(bad_changes)

    def test_frozen_canonical_closure_manifest_binding_and_refusals(self) -> None:
        assumptions_doc: dict[str, object] = {
            "schema": "verifiedos-canonical-tag-assumptions/1",
            "all_closed": True,
            "modules_audited": list(AUTHORED_CANONICAL_MODULES),
            "total_declarations": 4,
            "modules": {
                "TagInterpreter": {
                    "module": "TagInterpreter",
                    "query_target": "CanonicalTagPlaneInst",
                    "instantiated_functor": True,
                    "declaration_count": 1,
                    "closed_count": 1,
                    "all_closed": True,
                    "non_closed": [],
                    "symbols": ["CanonicalTagPlaneInst.tag_get"],
                },
                "TagConservativity": {
                    "module": "TagConservativity",
                    "query_target": "CanonicalOldOutcomesInst",
                    "instantiated_functor": True,
                    "declaration_count": 1,
                    "closed_count": 1,
                    "all_closed": True,
                    "non_closed": [],
                    "symbols": ["CanonicalOldOutcomesInst.tag_free_run_preserved"],
                },
                "CanonicalPhysicalCallerBridge": {
                    "module": "CanonicalPhysicalCallerBridge",
                    "query_target": "CanonicalPhysicalCallerBridge",
                    "instantiated_functor": False,
                    "declaration_count": 1,
                    "closed_count": 1,
                    "all_closed": True,
                    "non_closed": [],
                    "symbols": ["CanonicalPhysicalCallerBridge.read_ram_request_order"],
                },
                "CanonicalTagConservativity": {
                    "module": "CanonicalTagConservativity",
                    "query_target": "CanonicalTagConservativity",
                    "instantiated_functor": False,
                    "declaration_count": 1,
                    "closed_count": 1,
                    "all_closed": True,
                    "non_closed": [],
                    "symbols": ["CanonicalTagConservativity.read_ram_no_meta_preserves_tags"],
                },
            },
        }
        portable_flags = ["-silent", "-o", "-boot", "-R", "<out>", ""]
        bridge_target: dict[str, object] = {
            "schema": "verifiedos-canonical-tag-kernel-check/1",
            "recursive": True,
            "norec_absent": True,
            "norec_present": False,
            "target_module": "CanonicalPhysicalCallerBridge",
            "argv": ["/run-1/rocqchk", *portable_flags, "CanonicalPhysicalCallerBridge"],
            "portable_flags": portable_flags,
            "exit_code": 0,
            "elapsed_seconds": 80.0,
            "expected_axioms": sorted(EXPECTED_CANONICAL_FP_AXIOMS),
            "axioms": sorted(EXPECTED_CANONICAL_FP_AXIOMS),
            "axiom_count": 31,
            "unexpected_axioms": [],
            "missing_expected_axioms": [],
            "indices_not_mattering": ["Corelib.Init.Logic.eq"],
        }
        conserv_target: dict[str, object] = {
            "schema": "verifiedos-canonical-tag-kernel-check/1",
            "recursive": True,
            "norec_absent": True,
            "norec_present": False,
            "target_module": "CanonicalTagConservativity",
            "argv": ["/run-1/rocqchk", *portable_flags, "CanonicalTagConservativity"],
            "portable_flags": portable_flags,
            "exit_code": 0,
            "elapsed_seconds": 70.0,
            "expected_axioms": sorted(EXPECTED_CANONICAL_FP_AXIOMS),
            "axioms": sorted(EXPECTED_CANONICAL_FP_AXIOMS),
            "axiom_count": 31,
            "unexpected_axioms": [],
            "missing_expected_axioms": [],
            "indices_not_mattering": ["Corelib.Init.Logic.eq"],
        }
        kernel_doc = build_canonical_kernel_report({
            "CanonicalPhysicalCallerBridge": bridge_target,
            "CanonicalTagConservativity": conserv_target,
        })
        with tempfile.TemporaryDirectory(prefix="vos-canon-manifest-") as directory:
            root = Path(directory)
            members: dict[str, dict[str, object]] = {}
            payloads: dict[str, object] = {
                "assumptions.json": assumptions_doc,
                "commands.json": [],
                "inputs.json": {"schema": "verifiedos-canonical-tag-inputs/1"},
                "installed-comparison.json": {"/opt/rocq": []},
                "kernel-check.json": kernel_doc,
            }
            for name, obj in payloads.items():
                raw = (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")
                (root / name).write_bytes(raw)
                members[name] = {
                    "path": name,
                    "encoding": "identity",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"files": members}), encoding="utf-8")
            manifest_sha = sha(manifest)

            fresh_kernel = json.loads(json.dumps(kernel_doc))
            fresh_kernel["targets"]["CanonicalPhysicalCallerBridge"]["argv"] = [
                "/run-2/rocqchk", *portable_flags, "CanonicalPhysicalCallerBridge",
            ]
            fresh_kernel["targets"]["CanonicalTagConservativity"]["argv"] = [
                "/run-2/rocqchk", *portable_flags, "CanonicalTagConservativity",
            ]
            fresh_kernel["targets"]["CanonicalPhysicalCallerBridge"]["elapsed_seconds"] = 75.5
            fresh_kernel["total_elapsed_seconds"] = 145.5
            verify_frozen_canonical_closure(
                manifest, manifest_sha, assumptions_doc, fresh_kernel, {"/opt/rocq": []},
            )

            with self.assertRaisesRegex(ValueError, "input digest mismatch"):
                verify_frozen_canonical_closure(
                    manifest, "0" * 64, assumptions_doc, fresh_kernel,
                )

            bad_assumptions = json.loads(json.dumps(assumptions_doc))
            bad_assumptions["total_declarations"] = 1
            with self.assertRaisesRegex(ValueError, "total_declarations differs"):
                verify_frozen_canonical_closure(
                    manifest, manifest_sha, bad_assumptions, fresh_kernel,
                )

            bad_kernel = json.loads(json.dumps(fresh_kernel))
            bad_kernel["targets"]["CanonicalTagConservativity"]["axioms"] = [
                *bad_kernel["targets"]["CanonicalTagConservativity"]["axioms"][:-1], "Extra.ax",
            ]
            with self.assertRaisesRegex(ValueError, "do not equal the 31 FP axioms"):
                verify_frozen_canonical_closure(
                    manifest, manifest_sha, assumptions_doc, bad_kernel,
                )

            norec_kernel = json.loads(json.dumps(fresh_kernel))
            norec_kernel["targets"]["CanonicalPhysicalCallerBridge"]["portable_flags"].append("-norec")
            with self.assertRaisesRegex(ValueError, "violated recursive check invariants"):
                verify_frozen_canonical_closure(
                    manifest, manifest_sha, assumptions_doc, norec_kernel,
                )

            with self.assertRaisesRegex(ValueError, "installed paths changed"):
                verify_frozen_canonical_closure(
                    manifest, manifest_sha, assumptions_doc, fresh_kernel,
                    {"/opt/rocq": ["bin/rocq"]},
                )

    def test_candidate_recipe_binds_frozen_canonical_manifests(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        recipe = json.loads(
            (repo / "tools/sail-tag-outcomes/candidate.json").read_text(encoding="utf-8"),
        )
        entry = recipe["frozen_canonical_conservativity_manifest"]
        self.assertEqual(
            entry["path"],
            "docs/implementation/retained-evidence/q35p-canonical-tag-effects-20261127/manifest.json",
        )
        self.assertEqual(
            entry["sha256"],
            "b1ec37b27b3c9a176bd49c19181ba9e22c768c3df78d2e98f1ac79a98fed0546",
        )
        manifest = repo / entry["path"]
        self.assertTrue(manifest.is_file(), f"missing frozen_canonical_conservativity_manifest: {manifest}")
        require_sha(manifest, entry["sha256"])
        require_sha(
            repo / "tools/sail-tag-outcomes/CanonicalTagConservativity.v",
            cast("str", _HELPERS["CANONICAL_TAG_CONSERVATIVITY_SHA256"]),
        )
        bundle_dir = manifest.parent
        assumptions_doc = json.loads((bundle_dir / "assumptions.json").read_text(encoding="utf-8"))
        kernel_doc = json.loads((bundle_dir / "kernel-check.json").read_text(encoding="utf-8"))
        installed_doc = json.loads(
            (bundle_dir / "installed-comparison.json").read_text(encoding="utf-8"),
        )
        verify_frozen_canonical_closure(
            manifest, entry["sha256"], assumptions_doc, kernel_doc, installed_doc,
        )
        self.assertEqual(assumptions_doc["total_declarations"], 1079)
        self.assertEqual(
            {mod: assumptions_doc["modules"][mod]["declaration_count"] for mod in AUTHORED_CANONICAL_MODULES},
            {
                "TagInterpreter": 122,
                "TagConservativity": 145,
                "CanonicalPhysicalCallerBridge": 307,
                "CanonicalTagConservativity": 505,
            },
        )


if __name__ == "__main__":
    unittest.main()
