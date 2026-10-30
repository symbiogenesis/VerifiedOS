# SPDX-License-Identifier: Apache-2.0
"""Extraction consumers bind helper imports and refuse stale compiled baselines."""

import importlib.util
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import extracted_proofs as extracted
from vos import proof_staging

PROOFS = {
    "ProofSupport.v": "Definition shared := 1.\n",
    "CryptoLists.v": "Require ProofSupport.\n",
    "PqArith.v": "Require CryptoLists.\n",
    "Keccak.v": "Require ProofSupport CryptoLists.\n",
    "MlDsa.v": "Require PqArith Keccak.\n",
    "MlKem.v": "Require PqArith Keccak.\n",
    "EndpointIPC.v": "Require ProofSupport.\n",
    "Unrelated.v": "Definition other := 2.\n",
}


def _fixture(root: Path) -> None:
    for name, text in PROOFS.items():
        path = root / "proofs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for name in extracted.IMPLEMENTATION:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture implementation: {name}\n", encoding="utf-8")


def _objects(root: Path, work: Path, entry: str) -> None:
    staged = proof_staging.stage(root, work, (entry,))
    for source in staged.sources:
        source.with_suffix(".vo").write_bytes(b"compiled fixture: " + source.read_bytes())


def _refused(action: Callable[[], object], message: str) -> None:
    try:
        action()
    except ValueError as error:
        ensure(message in str(error), f"wrong refusal: {error}")
        return
    raise AssertionError(f"accepted invalid extraction inputs: {message}")


def _load(relative: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TOOLS.parent / relative)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load test subject: {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_baseline() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        work = root / "compiled"
        _objects(root, work, "MlKem.v")
        inputs = extracted.compiled_inputs(root, work, ("MlKem.v",))
        ensure(set(inputs) == {"ProofSupport", "CryptoLists", "PqArith", "Keccak", "MlKem"},
               "receipt omitted a shared imported module or included an unrelated one")
        extracted.require_inputs(root, work, ("MlKem.v",), inputs)
        incomplete = dict(inputs)
        del incomplete["ProofSupport"]
        _refused(lambda: extracted.require_inputs(root, work, ("MlKem.v",), incomplete), "closure")


def _shared_source_and_object_drift() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        work = root / "compiled"
        _objects(root, work, "MlDsa.v")
        bindings = extracted.compiled_bindings(root, work, ("MlDsa.v",))
        source = root / "proofs/ProofSupport.v"
        source.write_text("Definition shared := 2.\n", encoding="utf-8")
        _refused(lambda: extracted.require_bindings(root, work, ("MlDsa.v",), bindings), "same-source")
        source.write_text(PROOFS["ProofSupport.v"], encoding="utf-8")
        (work / "ProofSupport.vo").write_bytes(b"changed object")
        _refused(lambda: extracted.require_bindings(root, work, ("MlDsa.v",), bindings), "changed")


def _producer_drift() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        work = root / "compiled"
        _objects(root, work, "MlDsa.v")
        bindings = extracted.compiled_bindings(root, work, ("MlDsa.v",))
        (root / "tools/vos/proof_staging.py").write_text("changed producer\n", encoding="utf-8")
        _refused(lambda: extracted.require_bindings(root, work, ("MlDsa.v",), bindings), "producer changed")


def _wasm_compile_order_and_drift() -> None:
    module = _load("tools/wasm-oracle/compare_component.py", "fixture_wasm_comparison")
    compile_reference = cast("Callable[..., proof_staging.Staged]", module.__dict__["compile_reference"])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        before = proof_staging.inputs(root, ("EndpointIPC.v",))
        compiled: list[str] = []
        compile_reference(root, root / "stage", before, lambda source: compiled.append(source.name))
        ensure(compiled == ["ProofSupport.v", "EndpointIPC.v"], "Wasm root compiled before its import")

        def corrupt(source: Path) -> None:
            if source.name == "EndpointIPC.v":
                (source.parent / "ProofSupport.v").write_text("changed staged input\n", encoding="utf-8")

        _refused(lambda: compile_reference(root, root / "changed", before, corrupt), "staged proof bytes")


def _mldsa_build_closure() -> None:
    module = _load("proofs/campaigns/mldsa_vectors.py", "fixture_dsa_campaign")
    build = cast("Callable[[Path], dict[str, str]]", module.__dict__["build"])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        work = root / "native"
        compiled: list[str] = []

        def checked(command: list[str], cwd: Path, log: str) -> str:
            if command[0] == "fixture-rocq":
                source = Path(command[-1])
                source.with_suffix(".vo").write_bytes(b"compiled fixture: " + source.read_bytes())
                if source.name == "ExtractDsa.v":
                    for name in ("mldsa.ml", "mldsa.mli"):
                        (cwd / name).write_text("extracted fixture\n", encoding="utf-8")
                else:
                    compiled.append(source.name)
            else:
                (cwd / "dsa.exe").write_bytes(b"linked fixture")
            return ""

        with (patch.object(module, "ROOT", root), patch.object(module, "checked", checked),
              patch.object(module.__dict__["gallina"], "switch_env", return_value={}),
              patch.object(module.__dict__["env"], "rocq_command", return_value=["fixture-rocq"])):
            bindings = build(work)
        ensure(set(compiled) == {"ProofSupport.v", "CryptoLists.v", "PqArith.v", "Keccak.v", "MlDsa.v"},
               "ML-DSA compilation missed a transitive proof import")
        ensure(compiled.index("ProofSupport.v") < compiled.index("CryptoLists.v") < compiled.index("MlDsa.v"),
               "ML-DSA compile order violates an import edge")
        extracted.require_bindings(root, work, ("MlDsa.v",), bindings)


def cases() -> list[Case]:
    return [Case("compiled receipts include shared helpers", _complete_baseline),
            Case("shared source and object drift refuse", _shared_source_and_object_drift),
            Case("producer drift refuses", _producer_drift),
            Case("Wasm compilation follows imports and detects drift", _wasm_compile_order_and_drift),
            Case("ML-DSA compiles the selected closure", _mldsa_build_closure)]
