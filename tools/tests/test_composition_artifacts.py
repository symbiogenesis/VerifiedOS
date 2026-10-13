# SPDX-License-Identifier: Apache-2.0
"""Production bindings refuse physical file aliases before publication."""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import _refused, _write
from tests.test_composition_build_cli import (
    ARTIFACTS,
    GRAPH,
    IMAGE,
    PROJECT,
    RECORD,
    _build,
    _check,
    _products,
)
from vos import boot
from vos import composition as c


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _equal_products(root: Path) -> None:
    paths = json.loads((root / ARTIFACTS).read_bytes())
    for relative in paths.values():
        (root / relative).write_bytes(b"independent equal-byte product")


def _distinct_equal_products() -> None:
    with _products() as root:
        _equal_products(root)
        code, output = _build(root)
        ensure(code == 0, output)
        code, output = _check(root)
        ensure(code == 0, output)
        record = json.loads((root / RECORD).read_bytes())
        ensure(len({ref["sha256"] for ref in record["artifacts"].values()}) == 1,
               "independent runtime files with equal bytes retain their build binding")


def _hardlinked_runtime() -> None:
    with _products() as root:
        _equal_products(root)
        ensure(_build(root)[0] == 0, "independent equal-byte control")
        paths = json.loads((root / ARTIFACTS).read_bytes())
        alias = root / "products/aliased-storage.bin"
        os.link(root / paths["crypto-core-artifact"], alias)
        paths["storage-artifact"] = "products/aliased-storage.bin"
        (root / ARTIFACTS).write_bytes(json.dumps(paths).encode())
        before = _snapshot(root)
        code, output = _build(root)
        ensure(code == 1 and "substituted artifact" in output, output)
        ensure(_snapshot(root) == before, "runtime alias refusal preserves the previous record and inputs")
        record = json.loads((root / RECORD).read_bytes())
        record["artifacts"]["storage-artifact"] = c.reference(root, paths["storage-artifact"])
        outputs = {name: (root / PROJECT / name).read_bytes() for name in c.OUTPUTS}
        _refused(lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs,
                                               (root / GRAPH).read_bytes(), c.reference(root, IMAGE)),
                 "substituted artifact")


def _publication_runtime_alias() -> None:
    with _products() as root:
        _equal_products(root)
        ensure(_build(root)[0] == 0, "independent equal-byte control")
        record = json.loads((root / RECORD).read_bytes())
        artifacts = record["artifacts"]
        outputs = {name: (root / PROJECT / name).read_bytes() for name in c.OUTPUTS}
        graph = (root / GRAPH).read_bytes()
        image = c.reference(root, IMAGE)
        source = root / artifacts["crypto-core-artifact"]["path"]
        target = root / artifacts["storage-artifact"]["path"]
        original = target.read_bytes()
        bind = c._binding
        consumers = (lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph),
                     lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image))
        for consume in consumers:
            bindings = 0
            def substitute(checkout: Path, declaration: dict[str, Any], input_binding: dict[str, str],
                           roster_binding: dict[str, str]) -> dict[str, object]:
                nonlocal bindings
                result = bind(checkout, declaration, input_binding, roster_binding)
                bindings += 1
                if bindings == 2:
                    target.unlink()
                    os.link(source, target)
                return result
            try:
                with patch.object(c, "_binding", substitute):
                    _refused(consume, "substituted artifact")
                ensure(bindings == 2, "control aliases files after the final declared-source binding")
            finally:
                target.unlink()
                target.write_bytes(original)
            consume()


def _hardlinked_record_output() -> None:
    with _products() as root:
        raw = c.load(root)
        derivation = "products/derivation.v"
        (root / derivation).write_bytes(b"test-only derivation source")
        raw["members"][0]["derivation"]["source"] = c.reference(root, derivation)
        _write(root, raw)
        c.emit(root, c.EXAMPLE, PROJECT)
        relatives = [IMAGE, GRAPH, ARTIFACTS, c.EXAMPLE, boot.CONTRACT, *c.PRODUCERS,
                     "products/storage.bin", *(f"{PROJECT}/{name}" for name in c.OUTPUTS),
                     raw["configuration"]["path"], raw["members"][0]["sources"][0]["path"],
                     raw["members"][0]["descriptor"]["path"],
                     raw["producers"][0]["sources"][0]["path"], derivation]
        alias = root / "out/hardlinked-record.json"
        for relative in dict.fromkeys(relatives):
            os.link(root / relative, alias)
            try:
                before = _snapshot(root)
                code, output = _build(root, "out/hardlinked-record.json")
                ensure(code == 1 and "overwrite an input or product" in output, f"{relative}: {output}")
                ensure(_snapshot(root) == before, f"hardlinked {relative} survives record publication refusal")
            finally:
                alias.unlink()


def cases() -> list[Case]:
    return [Case("distinct-equal-byte-products", _distinct_equal_products),
            Case("hardlinked-runtime-artifacts", _hardlinked_runtime),
            Case("runtime-alias-at-publication", _publication_runtime_alias),
            Case("hardlinked-record-output", _hardlinked_record_output)]
