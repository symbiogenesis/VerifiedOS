# SPDX-License-Identifier: Apache-2.0
"""Focused host controls for qualification output isolation and input identity."""
import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name("replay.py")))
_test_helpers = runpy.run_path(str(Path(__file__).with_name("_test_helpers.py")))
_kernel_summary = _test_helpers["kernel_summary"]
output_path = helpers["output_path"]
require_sha = helpers["require_sha"]
sha = helpers["sha"]
retained_emission_inputs = helpers["retained_emission_inputs"]
match_v1_reading = helpers["match_v1_reading"]
read_support_module = helpers["read_support_module"]
check_support_source_diff = helpers["check_support_source_diff"]
compare_support_readings = helpers["compare_support_readings"]
verify_support_comparison = helpers["verify_support_comparison"]
verify_frozen_support = helpers["verify_frozen_support"]
AUTHORED_MODULES = helpers["AUTHORED_MODULES"]
VALUES_LEMMAS_AXIOMS = helpers["VALUES_LEMMAS_AXIOMS"]
authored_inventory_query = helpers["authored_inventory_query"]
authored_assumption_query = helpers["authored_assumption_query"]
audit_authored_assumptions = helpers["audit_authored_assumptions"]
verify_kernel_partition = helpers["verify_kernel_partition"]
build_kernel_report = helpers["build_kernel_report"]
verify_frozen_closure = helpers["verify_frozen_closure"]


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

    def test_support_comparison_matches_including_empty_modules(self) -> None:
        modules = ["Base", "ConcurrencyInterface", "ConcurrencyInterfaceBuiltins", "State_monad", "TypeCasts"]
        alias_sym = "State_monad.NMap.E.t"
        opaque_sym = "TypeCasts.dummy_value"
        ci_sym = "ConcurrencyInterface.empOutcome"
        state_mod = {
            f"SailStdpp.{alias_sym}": {
                "check": f"SailStdpp.{alias_sym} : Type@{{?u1}}",
                "about": (
                    f"{alias_sym} : Type@{{?u1}}\n\n"
                    f"{alias_sym} is not universe polymorphic\n"
                    f"{alias_sym} is transparent\n"
                    f"Expands to: Constant SailStdpp.{alias_sym} "
                    f"(syntactically equal to Stdlib.Structures.OrderedTypeEx.N_as_OT.t)"
                ),
                "print": f"{alias_sym} = OrderedTypeEx.N_as_OT.t",
            },
        }
        typecasts_mod = {
            f"SailStdpp.{opaque_sym}": {
                "check": f"SailStdpp.{opaque_sym} : Prop",
                "about": (
                    f"{opaque_sym} : Prop\n\n"
                    f"{opaque_sym} is not universe polymorphic\n"
                    f"{opaque_sym} is opaque but may be made transparent\n"
                    f"Expands to: Constant SailStdpp.{opaque_sym}"
                ),
                "print": f"{opaque_sym} = True",
            },
        }
        ci_mod = {
            f"SailStdpp.{ci_sym}": {
                "check": f"SailStdpp.{ci_sym} : Prop",
                "about": (
                    f"{ci_sym} : Prop\n\n"
                    f"{ci_sym} is not universe polymorphic\n"
                    f"{ci_sym} is transparent\n"
                    f"Expands to: Constant SailStdpp.{ci_sym}"
                ),
                "print": f"{ci_sym} = False",
            },
        }
        fixtures = {
            "Base": {},
            "ConcurrencyInterfaceBuiltins": {},
            "ConcurrencyInterface": ci_mod,
            "State_monad": state_mod,
            "TypeCasts": typecasts_mod,
        }

        def make_query(table: dict[str, dict[str, dict[str, str]]]) -> object:
            def query(phase_mod: str, content: str) -> str:
                if phase_mod.startswith("VosReadingInventory_"):
                    mod = phase_mod.removeprefix("VosReadingInventory_")
                    self.assertIn(f"Search _ inside SailStdpp.{mod}.", content)
                    rows = "".join(
                        f"{name.removeprefix('SailStdpp.')}: Prop\n" for name in sorted(table[mod])
                    )
                    footer = (
                        f'(use "About" for full details on the implicit arguments of {alias_sym})\n'
                        if mod == "State_monad" and table[mod] else ""
                    )
                    return "Current search blacklist :  is empty.\n" + rows + footer
                phase, _, mod = phase_mod.removeprefix("VosReading").partition("_")
                entries = table[mod]
                answers = []
                for name in sorted(entries):
                    if phase == "Facts":
                        answers.extend([
                            (name + "|check", entries[name]["check"].replace("?u1", f"{phase_mod}.1")),
                            (name + "|about", entries[name]["about"].replace("?u1", f"{phase_mod}.1") + "\nDeclared in library X"),
                        ])
                    elif phase == "Bodies":
                        answers.append((name + "|print", entries[name]["print"]))
                    else:
                        self.fail(f"unexpected query phase {phase_mod}")
                return "".join(f"VOS_PROOF_READING|{key}\n{value}\n" for key, value in answers)
            return query

        q_fn = make_query(fixtures)
        baseline_readings = {mod: read_support_module(q_fn, mod) for mod in modules}
        candidate_readings = {mod: read_support_module(q_fn, mod) for mod in modules}
        self.assertEqual(baseline_readings["Base"], {})
        self.assertEqual(baseline_readings["ConcurrencyInterfaceBuiltins"], {})
        self.assertEqual(
            baseline_readings["TypeCasts"][f"SailStdpp.{opaque_sym}"]["opacity"],
            "opaque but may be made transparent",
        )

        with tempfile.TemporaryDirectory(prefix="vos-support-cmp-") as directory:
            root = Path(directory)
            base_dir = root / "baseline"
            cand_dir = root / "candidate"
            base_dir.mkdir()
            cand_dir.mkdir()
            for mod in modules:
                (base_dir / f"{mod}.v").write_text(f"(* {mod} *)\n", encoding="utf-8")
                body = f"(* patched {mod} *)\n" if mod in ("ConcurrencyInterface", "ConcurrencyInterfaceBuiltins") else f"(* {mod} *)\n"
                (cand_dir / f"{mod}.v").write_text(body, encoding="utf-8")
            source_diff = check_support_source_diff(base_dir, cand_dir, modules)
            base_objs = {mod: hashlib.sha256(f"b-{mod}".encode()).hexdigest() for mod in modules}
            cand_objs = {mod: hashlib.sha256(f"c-{mod}".encode()).hexdigest() for mod in modules}
            report = compare_support_readings(
                modules, baseline_readings, candidate_readings, source_diff, base_objs, cand_objs,
            )
            verify_support_comparison(report)

            base_payload = (json.dumps(baseline_readings, sort_keys=True, indent=2) + "\n").encode("utf-8")
            cand_payload = (json.dumps(candidate_readings, sort_keys=True, indent=2) + "\n").encode("utf-8")
            cmp_bytes = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
            frozen_dir = root / "frozen"
            frozen_dir.mkdir()
            (frozen_dir / "support-comparison.json").write_bytes(cmp_bytes)
            manifest = frozen_dir / "manifest.json"
            manifest.write_text(json.dumps({
                "files": {
                    "support-baseline.json.gz": {"path": "support-baseline.json.gz", "sha256": hashlib.sha256(base_payload).hexdigest(), "bytes": len(base_payload)},
                    "support-candidate.json.gz": {"path": "support-candidate.json.gz", "sha256": hashlib.sha256(cand_payload).hexdigest(), "bytes": len(cand_payload)},
                    "support-comparison.json": {"path": "support-comparison.json", "sha256": hashlib.sha256(cmp_bytes).hexdigest(), "bytes": len(cmp_bytes)},
                },
            }), encoding="utf-8")
            manifest_sha = sha(manifest)
            verify_frozen_support(manifest, manifest_sha, base_payload, cand_payload, report)
            with self.assertRaisesRegex(ValueError, "candidate reading differs"):
                verify_frozen_support(manifest, manifest_sha, base_payload, b"{}\n", report)

    def test_support_comparison_refusals(self) -> None:
        modules = ["Base", "ConcurrencyInterface", "ConcurrencyInterfaceBuiltins"]
        ci_sym = "SailStdpp.ConcurrencyInterface.empOutcome"
        entry = {
            "kind": "Constant",
            "opacity": "transparent",
            "universes": "monomorphic",
            "check": f"{ci_sym} : Prop",
            "about": f"ConcurrencyInterface.empOutcome : Prop\n\nConcurrencyInterface.empOutcome is transparent\nExpands to: Constant {ci_sym}",
            "print": "ConcurrencyInterface.empOutcome = False",
        }
        base_readings = {"Base": {}, "ConcurrencyInterface": {ci_sym: dict(entry)}, "ConcurrencyInterfaceBuiltins": {}}
        source_diff = {
            mod: {
                "baseline_sha256": hashlib.sha256(f"b-{mod}".encode()).hexdigest(),
                "candidate_sha256": hashlib.sha256(f"{'c' if mod.startswith('ConcurrencyInterface') else 'b'}-{mod}".encode()).hexdigest(),
                "differs": mod.startswith("ConcurrencyInterface"),
            }
            for mod in modules
        }
        objs = {mod: hashlib.sha256(mod.encode()).hexdigest() for mod in modules}

        with tempfile.TemporaryDirectory(prefix="vos-support-refuse-") as directory:
            root = Path(directory)
            base_dir = root / "baseline"
            cand_dir = root / "candidate"
            base_dir.mkdir()
            cand_dir.mkdir()
            for mod in modules:
                (base_dir / f"{mod}.v").write_text("base\n", encoding="utf-8")
                (cand_dir / f"{mod}.v").write_text("cand\n" if mod.startswith("ConcurrencyInterface") else "base\n", encoding="utf-8")
            check_support_source_diff(base_dir, cand_dir, modules)

            # Untouched source modified.
            (cand_dir / "Base.v").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source diff mismatch"):
                check_support_source_diff(base_dir, cand_dir, modules)
            (cand_dir / "Base.v").write_text("base\n", encoding="utf-8")

            # Missing source.
            (cand_dir / "Base.v").unlink()
            with self.assertRaisesRegex(ValueError, "missing support source"):
                check_support_source_diff(base_dir, cand_dir, modules)

        # Missing / mismatched module set.
        with self.assertRaisesRegex(ValueError, "exact selected module set"):
            compare_support_readings(modules, {"Base": {}}, base_readings, source_diff, objs, objs)

        # Added declaration on candidate.
        cand_added = {"Base": {"SailStdpp.Base.extra": dict(entry)}, "ConcurrencyInterface": {ci_sym: dict(entry)}, "ConcurrencyInterfaceBuiltins": {}}
        rep_added = compare_support_readings(modules, base_readings, cand_added, source_diff, objs, objs)
        with self.assertRaisesRegex(ValueError, "empty top-level support modules disagree"):
            verify_support_comparison(rep_added)

        # Removed declaration on candidate (from non-empty module).
        cand_removed = {
            "Base": {},
            "ConcurrencyInterface": {ci_sym: dict(entry), "SailStdpp.ConcurrencyInterface.extra": dict(entry)},
            "ConcurrencyInterfaceBuiltins": {},
        }
        rep_removed = compare_support_readings(modules, cand_removed, base_readings, source_diff, objs, objs)
        with self.assertRaisesRegex(ValueError, "ConcurrencyInterface"):
            verify_support_comparison(rep_removed)

        # Modified check, about, or print reading.
        for field in ("check", "about", "print"):
            with self.subTest(field=field):
                cand_mod = {"Base": {}, "ConcurrencyInterface": {ci_sym: {**entry, field: "mutated"}}, "ConcurrencyInterfaceBuiltins": {}}
                rep = compare_support_readings(modules, base_readings, cand_mod, source_diff, objs, objs)
                self.assertEqual(rep["modules"]["ConcurrencyInterface"]["changed"], {ci_sym: [field]})
                with self.assertRaisesRegex(ValueError, "ConcurrencyInterface"):
                    verify_support_comparison(rep)

        # Source outside patched pair marked differing in report.
        bad_src_diff = {**source_diff, "Base": {**source_diff["Base"], "differs": True}}
        rep_bad_src = compare_support_readings(modules, base_readings, base_readings, bad_src_diff, objs, objs)
        with self.assertRaisesRegex(ValueError, "source diff mismatch"):
            verify_support_comparison(rep_bad_src)

    def test_authored_assumptions_audit(self) -> None:
        targets = {
            "TagInterpreter": ("TagPlaneInst", ["TagPlaneInst.tag_get", "TagPlaneInst.legal_read"]),
            "TagControls": ("TagControls", ["TagControls.aligned_capability", "TagControls.trace"]),
            "TagConservativity": ("OldOutcomesInst", ["OldOutcomesInst.tag_free_run_preserved"]),
            "PhysicalCallerBridge": ("PhysicalCallerBridge", ["PhysicalCallerBridge.read_ram_request_order"]),
        }

        def make_query(
            *, empty_mod: str | None = None, axiom_symbol: str | None = None,
        ) -> object:
            def query(name: str, content: str) -> str:
                if name.startswith("AssumptionsInventory_"):
                    mod = name.removeprefix("AssumptionsInventory_")
                    target, symbols = targets[mod]
                    if mod in ("TagInterpreter", "TagConservativity"):
                        self.assertIn(f"Module {target} :=", content)
                    self.assertIn(f"Search _ inside {target}.", content)
                    if mod == empty_mod:
                        return "Current search blacklist :  is empty.\n"
                    return (
                        "Current search blacklist :  is empty.\n"
                        + "".join(f"{sym}: Prop\n" for sym in symbols)
                    )
                if name.startswith("AssumptionsCheck_"):
                    mod = name.removeprefix("AssumptionsCheck_")
                    target, symbols = targets[mod]
                    lines: list[str] = []
                    for sym in sorted(symbols):
                        self.assertIn(f"Print Assumptions {sym}.", content)
                        lines.append(f"VOS_PROOF_AUDIT|{sym}")
                        if sym == axiom_symbol:
                            lines.append("Axioms:")
                            lines.append("Stdlib.Logic.Classical_Prop.classic : forall P : Prop, P \\/ ~ P")
                        else:
                            lines.append("Closed under the global context")
                    return "\n".join(lines) + "\n"
                self.fail(f"unexpected assumption query {name}")
                return ""
            return query

        report = audit_authored_assumptions(AUTHORED_MODULES, make_query())
        self.assertTrue(report["all_closed"])
        self.assertEqual(report["total_declarations"], 6)
        self.assertEqual(report["modules"]["TagInterpreter"]["query_target"], "TagPlaneInst")
        self.assertTrue(report["modules"]["TagInterpreter"]["instantiated_functor"])
        self.assertEqual(report["modules"]["TagConservativity"]["query_target"], "OldOutcomesInst")
        self.assertTrue(report["modules"]["TagConservativity"]["instantiated_functor"])
        self.assertFalse(report["modules"]["TagControls"]["instantiated_functor"])
        self.assertFalse(report["modules"]["PhysicalCallerBridge"]["instantiated_functor"])

        with self.assertRaisesRegex(ValueError, "empty native inventory"):
            audit_authored_assumptions(AUTHORED_MODULES, make_query(empty_mod="TagConservativity"))

        with self.assertRaisesRegex(ValueError, "non-closed declaration"):
            audit_authored_assumptions(
                AUTHORED_MODULES,
                make_query(axiom_symbol="PhysicalCallerBridge.read_ram_request_order"),
            )

        # Direct helper checks on functor instantiation preambles.
        target_ti, inv_ti = authored_inventory_query("TagInterpreter")
        self.assertEqual(target_ti, "TagPlaneInst")
        self.assertIn("Module TagPlaneInst := TagInterpreter.TagPlane", inv_ti)
        assump_tc = authored_assumption_query(
            "TagConservativity",
            [{"name": "OldOutcomesInst.tag_free_run_preserved", "type": "Prop", "assumptions": [], "claims": []}],
        )
        self.assertIn("Module OldOutcomesInst := TagConservativity.OldOutcomes", assump_tc)

    def _kernel_summary(
        self, axioms: list[str], indices: list[str] | None = None,
    ) -> str:
        return str(_kernel_summary(axioms, indices))

    def test_recursive_kernel_partitions_and_refusals(self) -> None:
        portable_flags = [
            "-silent", "-o", "-boot",
            "-R", "<rocq_prefix>/lib/coq/theories", "Corelib",
            "-Q", "<rocq_prefix>/lib/coq/user-contrib/Stdlib", "Stdlib",
            "-Q", "<out>/stdpp", "stdpp",
            "-R", "<out>/candidate", "SailStdpp",
            "-R", "<out>/emitted", "",
        ]
        real_axioms = [
            "Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep",
            "Stdlib.Reals.ClassicalDedekindReals.sig_not_dec",
            "Stdlib.Reals.ClassicalDedekindReals.sig_forall_dec",
            "Stdlib.Logic.Classical_Prop.classic",
        ]
        base_argv = ["/opt/rocq/bin/rocqchk", *portable_flags]
        partitions = {
            "authored_and_emitted": verify_kernel_partition(
                "authored_and_emitted",
                [*base_argv, "bindings_types", "bindings", *AUTHORED_MODULES],
                0, "",
                self._kernel_summary([], ["bindings_types.Interface.outcome", "Corelib.Init.Logic.eq"]),
                ["bindings_types", "bindings", *AUTHORED_MODULES],
                [],
                portable_flags=portable_flags,
            ),
            "support_axiom_free": verify_kernel_partition(
                "support_axiom_free",
                [*base_argv, "SailStdpp.Base", "SailStdpp.Values"],
                0, "",
                self._kernel_summary([], ["Corelib.Init.Logic.eq"]),
                ["SailStdpp.Base", "SailStdpp.Values"],
                [],
                portable_flags=portable_flags,
            ),
            "support_values_lemmas_control": verify_kernel_partition(
                "support_values_lemmas_control",
                [*base_argv, "SailStdpp.Values_lemmas"],
                0, "",
                self._kernel_summary(list(VALUES_LEMMAS_AXIOMS), ["Stdlib.Logic.JMeq.JMeq"]),
                ["SailStdpp.Values_lemmas"],
                list(VALUES_LEMMAS_AXIOMS),
                portable_flags=portable_flags,
                note="Values_lemmas Program.Wf control",
            ),
            "support_real_control": verify_kernel_partition(
                "support_real_control",
                [*base_argv, "SailStdpp.Real"],
                0, "",
                self._kernel_summary(real_axioms, ["Corelib.Init.Logic.eq"]),
                ["SailStdpp.Real"],
                real_axioms,
                portable_flags=portable_flags,
            ),
        }
        report = build_kernel_report(partitions)
        self.assertTrue(report["recursive"])
        self.assertTrue(report["norec_absent"])
        self.assertEqual(partitions["support_values_lemmas_control"]["axioms"], sorted(VALUES_LEMMAS_AXIOMS))
        self.assertEqual(partitions["support_real_control"]["axioms"], sorted(real_axioms))

        # Refuse -norec in argv or portable_flags.
        with self.assertRaisesRegex(ValueError, "-norec"):
            verify_kernel_partition(
                "authored_and_emitted",
                [*base_argv, "-norec", "bindings_types"],
                0, "", self._kernel_summary([]),
                ["bindings_types"], [],
                portable_flags=portable_flags,
            )
        with self.assertRaisesRegex(ValueError, "-norec"):
            verify_kernel_partition(
                "authored_and_emitted",
                [*base_argv, "bindings_types"],
                0, "", self._kernel_summary([]),
                ["bindings_types"], [],
                portable_flags=[*portable_flags, "-norec"],
            )

        # Refuse unexpected axiom in 0-axiom partition.
        with self.assertRaisesRegex(ValueError, "axioms mismatch"):
            verify_kernel_partition(
                "support_axiom_free",
                [*base_argv, "SailStdpp.Base"],
                0, "",
                self._kernel_summary(["Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq"]),
                ["SailStdpp.Base"], [],
                portable_flags=portable_flags,
            )

        # Refuse missing axiom in Real or Values_lemmas control.
        with self.assertRaisesRegex(ValueError, "axioms mismatch"):
            verify_kernel_partition(
                "support_real_control",
                [*base_argv, "SailStdpp.Real"],
                0, "",
                self._kernel_summary(real_axioms[:-1]),
                ["SailStdpp.Real"], real_axioms,
                portable_flags=portable_flags,
            )
        with self.assertRaisesRegex(ValueError, "axioms mismatch"):
            verify_kernel_partition(
                "support_values_lemmas_control",
                [*base_argv, "SailStdpp.Values_lemmas"],
                0, "",
                self._kernel_summary(list(VALUES_LEMMAS_AXIOMS[:-1])),
                ["SailStdpp.Values_lemmas"], list(VALUES_LEMMAS_AXIOMS),
                portable_flags=portable_flags,
            )

    def test_frozen_closure_manifest_binding_and_refusals(self) -> None:
        assumptions_doc = {
            "schema": "verifiedos-tag-assumptions/1",
            "all_closed": True,
            "modules_audited": list(AUTHORED_MODULES),
            "total_declarations": 4,
            "modules": {
                mod: {
                    "module": mod,
                    "query_target": mod,
                    "instantiated_functor": False,
                    "declaration_count": 1,
                    "closed_count": 1,
                    "all_closed": True,
                    "non_closed": [],
                    "symbols": [f"{mod}.lem"],
                }
                for mod in AUTHORED_MODULES
            },
        }
        portable_flags = ["-silent", "-o", "-boot", "-R", "<out>/emitted", ""]
        kernel_doc = {
            "schema": "verifiedos-tag-kernel-check/1",
            "recursive": True,
            "norec_absent": True,
            "partition_order": [
                "authored_and_emitted",
                "support_axiom_free",
                "support_values_lemmas_control",
                "support_real_control",
            ],
            "partitions": {
                "authored_and_emitted": {
                    "modules": ["bindings_types"],
                    "argv": ["/run-1/rocqchk", *portable_flags, "bindings_types"],
                    "portable_flags": portable_flags,
                    "norec_present": False,
                    "exit_code": 0,
                    "expected_axioms": [],
                    "axioms": [],
                    "indices_not_mattering": ["Corelib.Init.Logic.eq"],
                },
                "support_axiom_free": {
                    "modules": ["SailStdpp.Base"],
                    "argv": ["/run-1/rocqchk", *portable_flags, "SailStdpp.Base"],
                    "portable_flags": portable_flags,
                    "norec_present": False,
                    "exit_code": 0,
                    "expected_axioms": [],
                    "axioms": [],
                    "indices_not_mattering": [],
                },
                "support_values_lemmas_control": {
                    "modules": ["SailStdpp.Values_lemmas"],
                    "argv": ["/run-1/rocqchk", *portable_flags, "SailStdpp.Values_lemmas"],
                    "portable_flags": portable_flags,
                    "norec_present": False,
                    "exit_code": 0,
                    "expected_axioms": sorted(VALUES_LEMMAS_AXIOMS),
                    "axioms": sorted(VALUES_LEMMAS_AXIOMS),
                    "indices_not_mattering": ["Stdlib.Logic.JMeq.JMeq"],
                },
                "support_real_control": {
                    "modules": ["SailStdpp.Real"],
                    "argv": ["/run-1/rocqchk", *portable_flags, "SailStdpp.Real"],
                    "portable_flags": portable_flags,
                    "norec_present": False,
                    "exit_code": 0,
                    "expected_axioms": ["Stdlib.Logic.Classical_Prop.classic"],
                    "axioms": ["Stdlib.Logic.Classical_Prop.classic"],
                    "indices_not_mattering": [],
                },
            },
        }
        with tempfile.TemporaryDirectory(prefix="vos-closure-manifest-") as directory:
            root = Path(directory)
            a_bytes = (json.dumps(assumptions_doc, sort_keys=True, indent=2) + "\n").encode("utf-8")
            k_bytes = (json.dumps(kernel_doc, sort_keys=True, indent=2) + "\n").encode("utf-8")
            (root / "assumptions.json").write_bytes(a_bytes)
            (root / "kernel-check.json").write_bytes(k_bytes)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "files": {
                    "assumptions.json": {
                        "path": "assumptions.json",
                        "sha256": hashlib.sha256(a_bytes).hexdigest(),
                        "bytes": len(a_bytes),
                    },
                    "kernel-check.json": {
                        "path": "kernel-check.json",
                        "sha256": hashlib.sha256(k_bytes).hexdigest(),
                        "bytes": len(k_bytes),
                    },
                },
            }), encoding="utf-8")
            manifest_sha = sha(manifest)

            # Different raw argv paths pass when normalized invariants match.
            fresh_kernel = json.loads(json.dumps(kernel_doc))
            fresh_kernel["partitions"]["authored_and_emitted"]["argv"] = [
                "/run-2/rocqchk", *portable_flags, "bindings_types",
            ]
            verify_frozen_closure(manifest, manifest_sha, assumptions_doc, fresh_kernel)

            # Manifest digest mismatch refused.
            with self.assertRaisesRegex(ValueError, "input digest mismatch"):
                verify_frozen_closure(manifest, "0" * 64, assumptions_doc, fresh_kernel)

            # Assumptions count/symbol mismatch refused.
            bad_assumptions = json.loads(json.dumps(assumptions_doc))
            bad_assumptions["total_declarations"] = 3
            with self.assertRaisesRegex(ValueError, "assumptions total_declarations differs"):
                verify_frozen_closure(manifest, manifest_sha, bad_assumptions, fresh_kernel)

            # Kernel axiom drift refused.
            bad_kernel = json.loads(json.dumps(fresh_kernel))
            bad_kernel["partitions"]["support_axiom_free"]["axioms"] = ["Extra.ax"]
            with self.assertRaisesRegex(ValueError, "kernel-check support_axiom_free.axioms differs"):
                verify_frozen_closure(manifest, manifest_sha, assumptions_doc, bad_kernel)

            # -norec in fresh report refused.
            norec_kernel = json.loads(json.dumps(fresh_kernel))
            norec_kernel["partitions"]["authored_and_emitted"]["portable_flags"].append("-norec")
            with self.assertRaisesRegex(ValueError, "violated recursive check invariants"):
                verify_frozen_closure(manifest, manifest_sha, assumptions_doc, norec_kernel)

    def test_candidate_recipe_binds_frozen_manifests(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        recipe = json.loads((repo / "tools/sail-tag-outcomes/candidate.json").read_text(encoding="utf-8"))
        for key in ("frozen_v1_manifest", "frozen_support_manifest", "frozen_closure_manifest"):
            entry = recipe[key]
            manifest = repo / entry["path"]
            self.assertTrue(manifest.is_file(), f"missing {key}: {manifest}")
            require_sha(manifest, entry["sha256"])


if __name__ == "__main__":
    unittest.main()
