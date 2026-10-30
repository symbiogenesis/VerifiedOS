# SPDX-License-Identifier: Apache-2.0
"""Complete local proof identities for extracted-executable campaigns.

The staging library owns dependency traversal. This adapter checks the existing
campaign source/object receipt formats; it supplies no prover or extraction verdict.
"""

from collections.abc import Mapping
from pathlib import Path

from vos import proof_staging, receipts

IMPLEMENTATION = ("tools/vos/extracted_proofs.py", *proof_staging.IMPLEMENTATION_SOURCES)


def implementation_inputs(root: Path) -> dict[str, str]:
    """Bind the code deciding closure membership and compiled-input freshness."""
    return receipts.snapshot(root, [root / name for name in IMPLEMENTATION])


def compiled_inputs(root: Path, work: Path, entries: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Read matching staged source and object bytes for every local dependency."""
    result: dict[str, dict[str, str]] = {}
    for relative, expected in proof_staging.inputs(root, entries).items():
        source = work / Path(relative).name
        compiled = source.with_suffix(".vo")
        if not source.is_file() or receipts.digest(source) != expected:
            raise ValueError(f"missing same-source staged module: {source.stem}")
        if not compiled.is_file():
            raise ValueError(f"missing compiled module: {source.stem}")
        result[source.stem] = {"source_sha256": expected, "vo_sha256": receipts.digest(compiled)}
    return result


def require_inputs(root: Path, work: Path, entries: tuple[str, ...],
                   recorded: Mapping[str, object]) -> dict[str, dict[str, str]]:
    """Refuse incomplete or stale module-keyed source/object receipts."""
    expected = compiled_inputs(root, work, entries)
    if dict(recorded) != expected:
        raise ValueError("compiled proof closure differs from extraction receipt")
    return expected


def compiled_bindings(root: Path, work: Path, entries: tuple[str, ...]) -> dict[str, str]:
    """Read the flat binding names retained by the ML-DSA campaigns."""
    modules = compiled_inputs(root, work, entries)
    result = implementation_inputs(root)
    for name, identity in modules.items():
        result[f"proofs/{name}.v"] = identity["source_sha256"]
        result[f"{name}.vo"] = identity["vo_sha256"]
    return result


def require_bindings(root: Path, work: Path, entries: tuple[str, ...],
                     recorded: Mapping[str, str]) -> dict[str, str]:
    """Validate the complete closure inside a receipt also carrying driver outputs."""
    expected = compiled_bindings(root, work, entries)
    if any(recorded.get(name) != identity for name, identity in expected.items()):
        raise ValueError("compiled proof closure or extraction producer changed")
    return expected


def require_unchanged(root: Path, entries: tuple[str, ...], before: Mapping[str, str]) -> None:
    """Refuse both changed source bytes and a changed import closure."""
    if proof_staging.inputs(root, entries) != dict(before):
        raise ValueError("proof inputs changed during the extraction campaign")
