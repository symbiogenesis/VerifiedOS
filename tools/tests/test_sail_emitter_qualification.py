# SPDX-License-Identifier: Apache-2.0
"""Fixture controls for the hosted Sail emitter qualification."""

import shutil
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from ci import sail_emitter_qualification as emitter
from tests.harness import TOOLS, Case, ensure
from vos import rocqterm

REVISION = "a" * 40
PROVISIONED: dict[str, rocqterm.Named] = {
    name: {"path": str((TOOLS / "fixture" / name).resolve()), "sha256": f"locked-{name}"}
    for name in ("sail", "z3")
}


def fixture(backend: str, output: str) -> dict[str, Any]:
    plugin = {"path": "/private/plugins/" + emitter.PLUGIN, "sha256": backend, "version": ""}
    other = {"path": "/private/plugins/sail_plugin_c.cmxs", "sha256": "other", "version": ""}
    return {
        "format": rocqterm.FORMAT,
        "target": rocqterm.TARGET,
        "checkout": {"revision": REVISION, "model_dirty": False},
        "inputs": {"sources": "source", "configuration": "config"},
        "command": [PROVISIONED["sail"]["path"], "--rocq"],
        "axioms": {"names": ["fixture"]},
        "outputs": {name: {"sha256": output} for name in rocqterm.OUTPUTS},
        "toolchain": {
            "sail": {**PROVISIONED["sail"], "version": "fixture"},
            "z3": {**PROVISIONED["z3"], "version": "fixture"},
            "library": "locked-library",
            "plugin_directories": ["/private/plugins"],
            "loaded_plugins": [plugin, other],
            "rocq_plugin": plugin,
        },
    }


def paired_comparison() -> None:
    stock, candidate = fixture("stock", "before"), fixture("patched", "after")
    options = {"revision": REVISION, "original_plugin": "stock", "patched_plugin": "patched"}
    emitter.check_comparison(stock, candidate, deepcopy(candidate), provisioned=PROVISIONED, **options)
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
            emitter.check_comparison(versions["stock"], versions["candidate"], versions["repeat"],
                                     provisioned=PROVISIONED, **options)
        except ValueError:
            continue
        raise AssertionError(f"accepted {reason}")


def native_plugin_order() -> None:
    stock = fixture("stock", "before")
    candidate = fixture("patched", "after")
    candidate["toolchain"]["loaded_plugins"].reverse()
    try:
        emitter.check_comparison(stock, candidate, deepcopy(candidate), revision=REVISION,
                                 original_plugin="stock", patched_plugin="patched", provisioned=PROVISIONED)
    except ValueError:
        return
    raise AssertionError("accepted a native load-order change outside the Rocq plugin bytes")


def substituted_producer() -> None:
    other = str((TOOLS / "elsewhere" / "sail").resolve())
    for name, field, value in (("command", 0, other), ("sail", "path", other),
                               ("sail", "sha256", "different Sail"), ("z3", "path", other),
                               ("z3", "sha256", "different Z3")):
        stock, candidate = fixture("stock", "before"), fixture("patched", "after")
        for record in (stock, candidate):
            if name == "command":
                record["command"][0] = value
            else:
                record["toolchain"][name][field] = value
        try:
            emitter.check_comparison(stock, candidate, deepcopy(candidate), revision=REVISION,
                                     original_plugin="stock", patched_plugin="patched", provisioned=PROVISIONED)
        except ValueError as error:
            ensure("bootstrapped" in str(error), f"unexpected refusal: {error}")
        else:
            raise AssertionError(f"accepted the same substituted {name} {field} in all three emissions")


def retained_source_inputs() -> None:
    root = TOOLS.parent
    emitter.evidence_input(root / emitter.SCOPED, "sail-emission-syntax.patch")
    emitter.evidence_input(root / emitter.SCOPED, "LICENSE.sail")
    emitter.evidence_input(root / emitter.INITIAL, "backend-dune-project.txt")


def frozen_emission_join() -> None:
    root = TOOLS.parent
    stock, candidate = (
        emitter.load(root / emitter.REFRESH / f"{label}-generation.json")
        for label in ("original", "candidate")
    )
    for record in (stock, candidate):
        record["checkout"]["revision"] = REVISION
        record["command"][0] = "/runner/sail/bin/sail"
    bound = emitter.check_frozen_pair(root, stock, candidate)
    ensure(set(bound) == {"comparison", "inputs", "handwritten_source", "original", "candidate",
                          "refreshed_original", "refreshed_candidate"},
           "hosted result omitted frozen comparison inputs")

    stale_stock = deepcopy(stock)
    stale_stock["inputs"] = emitter.load(root / emitter.REPLAY / "original-generation.json")["inputs"]
    changed_stock = deepcopy(stock)
    changed_stock["outputs"][rocqterm.OUTPUTS[0]]["sha256"] = "different stock"
    changed_candidate = deepcopy(candidate)
    changed_candidate["outputs"][rocqterm.OUTPUTS[1]]["sha256"] = "different candidate"
    changed_flags = deepcopy(candidate)
    changed_flags["command"].append("--different")
    changed_library = deepcopy(stock)
    changed_candidate_library = deepcopy(candidate)
    for record in (changed_library, changed_candidate_library):
        record["toolchain"]["library"] = rocqterm.manifest({"replacement.sail": "0" * 64})
    for left, right, expected in (
        (stale_stock, candidate, "hosted original inputs"),
        (changed_stock, candidate, "hosted original outputs"),
        (stock, changed_candidate, "hosted candidate outputs"),
        (stock, changed_flags, "hosted candidate arguments"),
        (changed_library, changed_candidate_library, "original Sail library"),
    ):
        try:
            emitter.check_frozen_pair(root, left, right)
        except ValueError as error:
            ensure(str(error).startswith(expected), f"unexpected refusal: {error}")
        else:
            raise AssertionError(f"accepted changed frozen emission: {expected}")

    # A refresh with different emitted bytes cannot substitute for the frozen readings.
    load = emitter.load

    def load_changed_refresh(path: Path) -> dict[str, Any]:
        if path == root / emitter.REFRESH / "candidate-generation.json":
            return changed_candidate
        return load(path)

    with patch.object(emitter, "load", side_effect=load_changed_refresh):
        try:
            emitter.check_frozen_pair(root, stock, changed_candidate)
        except ValueError as error:
            ensure(str(error).startswith("refreshed candidate outputs"),
                   f"unexpected refusal: {error}")
        else:
            raise AssertionError("accepted a refreshed emission with changed output bytes")


def changed_handwritten_support() -> None:
    root = TOOLS.parent
    with TemporaryDirectory() as temporary:
        checkout = Path(temporary)
        for directory in (emitter.FROZEN, emitter.REPLAY, emitter.REFRESH):
            shutil.copytree(root / directory, checkout / directory)
        source = Path("model/handwritten_support/riscv_extras.v")
        support = checkout / source
        support.parent.mkdir(parents=True)
        support.write_bytes((root / source).read_bytes() + b"\n")
        stock, candidate = (emitter.load(checkout / emitter.REFRESH / f"{label}-generation.json")
                            for label in ("original", "candidate"))
        try:
            emitter.check_frozen_pair(checkout, stock, candidate)
        except ValueError as error:
            ensure(support.name in str(error), f"unexpected refusal: {error}")
        else:
            raise AssertionError("reused frozen readings after the handwritten support changed")


def cases() -> list[Case]:
    return [
        Case("paired-canonical-emission", paired_comparison),
        Case("native-plugin-order", native_plugin_order),
        Case("substituted-producer", substituted_producer),
        Case("retained-source-inputs", retained_source_inputs),
        Case("frozen-emission-join", frozen_emission_join),
        Case("changed-handwritten-support", changed_handwritten_support),
    ]
