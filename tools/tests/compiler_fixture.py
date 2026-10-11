# SPDX-License-Identifier: Apache-2.0
"""Synthetic contained builds for compiler receipt acceptance/refusal tests."""

import json
from pathlib import Path

from vos import compiler_provenance, receipts


def create(root: Path, ccomp: Path | None = None) -> Path:
    """Write a minimal independent source inventory and released toolchain export."""
    ccomp = ccomp or root / "build/ccomp"
    ccomp.parent.mkdir(parents=True, exist_ok=True)
    if not ccomp.exists():
        ccomp.write_bytes(b"synthetic compiler")
    source = ccomp.parent / "source.v"
    source.write_bytes(b"synthetic source")
    lock = root / compiler_provenance.LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text('opam-version: "2.0"\ninstalled: [\n'
                    '  "rocq-core.9.3.0"\n  "ocaml-base-compiler.4.14.2"\n'
                    '  "menhir.20260209"\n]\n', encoding="utf-8", newline="\n")
    native: dict[str, object] = {"lock_sha256": receipts.digest(lock)}
    for role, package, version, reported in (
            ("prover", "rocq-core", "9.3.0", "The Rocq Prover, version 9.3.0"),
            ("ocaml", "ocaml-base-compiler", "4.14.2", "4.14.2"),
            ("menhir", "menhir", "20260209", "menhir, version 20260209")):
        native[role] = {"package": package, "version": version,
                        "reported_version": reported, "executable_sha256": "1" * 64}
    result = {"passed": True, "inputs_unchanged": True, "revision": "fixture-revision",
              "compiler_sha256": receipts.digest(ccomp), "toolchain": native}
    (ccomp.parent / "build-result.json").write_text(json.dumps(result), encoding="utf-8")
    (ccomp.parent / "build-inputs.json").write_text(json.dumps({"source.v": {
        "canonical_sha256": receipts.digest(source)}}), encoding="utf-8")
    return ccomp
