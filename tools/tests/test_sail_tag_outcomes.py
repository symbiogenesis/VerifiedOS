# SPDX-License-Identifier: Apache-2.0
"""Expose the isolated tag replay's host controls to normal test discovery."""

import runpy
from pathlib import Path

from tests.harness import Case


def cases() -> list[Case]:
    source = Path(__file__).resolve().parents[1] / "sail-tag-outcomes" / "test_replay.py"
    controls = runpy.run_path(str(source))["IsolationControls"]()
    return [
        Case("fresh-sibling-output", controls.test_fresh_sibling),
        Case("protected-input-overlap-and-aliases", controls.test_overlap_and_aliases),
        Case("relative-and-unexpanded-output-refusal", controls.test_relative_and_unexpanded),
        Case("exact-input-identity-refusal", controls.test_exact_input_identity),
    ]
