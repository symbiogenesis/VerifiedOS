# SPDX-License-Identifier: Apache-2.0
"""Fixture controls for the hosted Sail emitter qualification."""

from copy import deepcopy
from typing import Any

from ci import sail_emitter_qualification as emitter
from tests.harness import TOOLS, Case
from vos import rocqterm

REVISION = "a" * 40


def fixture(backend: str, output: str) -> dict[str, Any]:
    plugin = {"path": "/private/plugins/" + emitter.PLUGIN, "sha256": backend, "version": ""}
    other = {"path": "/private/plugins/sail_plugin_c.cmxs", "sha256": "other", "version": ""}
    return {
        "format": rocqterm.FORMAT,
        "target": rocqterm.TARGET,
        "checkout": {"revision": REVISION, "model_dirty": False},
        "inputs": {"sources": "source", "configuration": "config"},
        "command": ["/tools/sail", "--rocq"],
        "axioms": {"names": ["fixture"]},
        "outputs": {name: {"sha256": output} for name in rocqterm.OUTPUTS},
        "toolchain": {
            "sail": "locked-sail",
            "z3": "locked-z3",
            "library": "locked-library",
            "plugin_directories": ["/private/plugins"],
            "loaded_plugins": [plugin, other],
            "rocq_plugin": plugin,
        },
    }


def paired_comparison() -> None:
    stock, candidate = fixture("stock", "before"), fixture("patched", "after")
    options = {"revision": REVISION, "original_plugin": "stock", "patched_plugin": "patched"}
    emitter.check_comparison(stock, candidate, deepcopy(candidate), **options)
    mutations = (
        ("candidate changed source", "candidate", "inputs", {}),
        ("repeat changed outputs", "repeat", "outputs", stock["outputs"]),
        ("stock and candidate outputs identical", "stock", "outputs", candidate["outputs"]),
        ("stock missing output", "stock", "outputs", {}),
        ("candidate changed axioms", "candidate", "axioms", {}),
        ("candidate changed target invocation", "candidate", "command", ["/tools/sail", "--cpp"]),
        ("candidate changed revision", "candidate", "checkout", {}),
    )
    for reason, label, field, value in mutations:
        versions = {"stock": deepcopy(stock), "candidate": deepcopy(candidate), "repeat": deepcopy(candidate)}
        versions[label][field] = value
        try:
            emitter.check_comparison(versions["stock"], versions["candidate"], versions["repeat"], **options)
        except ValueError:
            continue
        raise AssertionError(f"accepted {reason}")


def native_plugin_order() -> None:
    stock = fixture("stock", "before")
    candidate = fixture("patched", "after")
    candidate["toolchain"]["loaded_plugins"].reverse()
    try:
        emitter.check_comparison(stock, candidate, deepcopy(candidate), revision=REVISION,
                                 original_plugin="stock", patched_plugin="patched")
    except ValueError:
        return
    raise AssertionError("accepted a native load-order change outside the Rocq plugin bytes")


def retained_source_inputs() -> None:
    root = TOOLS.parent
    emitter.evidence_input(root / emitter.SCOPED, "sail-emission-syntax.patch")
    emitter.evidence_input(root / emitter.SCOPED, "LICENSE.sail")
    emitter.evidence_input(root / emitter.INITIAL, "backend-dune-project.txt")


def cases() -> list[Case]:
    return [
        Case("paired-canonical-emission", paired_comparison),
        Case("native-plugin-order", native_plugin_order),
        Case("retained-source-inputs", retained_source_inputs),
    ]
