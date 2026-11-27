# SPDX-License-Identifier: Apache-2.0
"""Expose the isolated tag replay and canonical closure host controls to normal test discovery."""

import runpy
from pathlib import Path

from tests.harness import Case


def cases() -> list[Case]:
    suite_dir = Path(__file__).resolve().parents[1] / "sail-tag-outcomes"
    replay_controls = runpy.run_path(str(suite_dir / "test_replay.py"))["IsolationControls"]()
    canonical_controls = runpy.run_path(
        str(suite_dir / "test_canonical_closure.py"),
    )["CanonicalClosureControls"]()
    return [
        Case("fresh-sibling-output", replay_controls.test_fresh_sibling),
        Case("protected-input-overlap-and-aliases", replay_controls.test_overlap_and_aliases),
        Case(
            "relative-and-unexpanded-output-refusal",
            replay_controls.test_relative_and_unexpanded,
        ),
        Case("exact-input-identity-refusal", replay_controls.test_exact_input_identity),
        Case("frozen-v1-declaration-readings", replay_controls.test_frozen_v1_declarations),
        Case(
            "retained-emission-binds-other-plugins-and-solver",
            replay_controls.test_retained_emission_binds_other_plugins_and_solver,
        ),
        Case(
            "support-comparison-matches-including-empty-modules",
            replay_controls.test_support_comparison_matches_including_empty_modules,
        ),
        Case("support-comparison-refusals", replay_controls.test_support_comparison_refusals),
        Case("authored-assumptions-audit", replay_controls.test_authored_assumptions_audit),
        Case(
            "recursive-kernel-partitions-and-refusals",
            replay_controls.test_recursive_kernel_partitions_and_refusals,
        ),
        Case(
            "frozen-closure-manifest-binding-and-refusals",
            replay_controls.test_frozen_closure_manifest_binding_and_refusals,
        ),
        Case(
            "candidate-recipe-binds-frozen-manifests",
            replay_controls.test_candidate_recipe_binds_frozen_manifests,
        ),
        Case(
            "canonical-output-path-accepts-new-and-empty-dirs",
            canonical_controls.test_output_path_accepts_new_and_empty_dirs,
        ),
        Case("canonical-output-path-refusals", canonical_controls.test_output_path_refusals),
        Case(
            "canonical-whole-term-and-support-input-verification",
            canonical_controls.test_whole_term_and_support_input_verification,
        ),
        Case(
            "canonical-assumptions-audit-and-refusals",
            canonical_controls.test_canonical_assumptions_audit_and_refusals,
        ),
        Case(
            "canonical-recursive-kernel-check-and-refusals",
            canonical_controls.test_recursive_kernel_check_and_refusals,
        ),
        Case(
            "canonical-installed-comparison-and-refusals",
            canonical_controls.test_installed_comparison_and_refusals,
        ),
        Case(
            "canonical-frozen-closure-manifest-binding-and-refusals",
            canonical_controls.test_frozen_canonical_closure_manifest_binding_and_refusals,
        ),
        Case(
            "canonical-candidate-recipe-binds-frozen-manifests",
            canonical_controls.test_candidate_recipe_binds_frozen_canonical_manifests,
        ),
    ]
