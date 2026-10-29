# SPDX-License-Identifier: Apache-2.0
"""Inspect retained boot products and bind them as historical composition inputs.

This adapter consumes the existing staged-chain validator. Its candidate retains
the roster's partial status and cannot qualify the historical compiler or image.
"""

from pathlib import Path
from typing import Any

from vos import boot_chain, boot_crypto_target, compiler_provenance, composer
from vos import boot_handoff as handoff
from vos import composition as production

PRODUCER = "historical-boot-chain"
MEMBER_UNITS = (("rot-firmware", ("rom", "runtime")), ("mmode-firmware", ("mmode",)))
INSPECTORS = ("tools/vos/composition_staged.py", "tools/vos/boot_chain.py",
              "tools/vos/boot_crypto_target.py", "tools/vos/boot_handoff.py",
              "tools/vos/compiler_provenance.py", "tools/vos/cli/compiler_diff.py",
              "tools/generated/dialect-table.json", handoff.CONTRACT, handoff.ROT_CONFIG,
              boot_crypto_target.LOCK)


def _manifest(root: Path, path: str) -> tuple[dict[str, Any], dict[str, str]]:
    ref = production.reference(root, path)
    raw = production._json(production._path(root, path), ref["sha256"])
    if not isinstance(raw, dict):
        raise production.CompositionError(f"staged producer manifest must be an object: {path}")
    return raw, ref


def _source_paths(manifest: dict[str, Any]) -> set[str]:
    sources = manifest.get("sources_sha256")
    if not isinstance(sources, dict) or not sources or not all(isinstance(path, str) for path in sources):
        raise production.CompositionError("staged producer manifest binds no source paths")
    return set(sources)


def _references(value: object) -> list[dict[str, str]]:
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            return [value]
        return [ref for child in value.values() for ref in _references(child)]
    if isinstance(value, list):
        return [ref for child in value for ref in _references(child)]
    return []


def bind_boot_chain(root: Path, source: str, output: str) -> dict[str, object]:
    """Publish a candidate using checked retained products, with no acceptance claim.

    Original manifests and source bindings are never rewritten. The ordinary
    project command consumes the resulting input through the existing schema.
    """
    raw, input_ref, _roster, roster_ref = production._load(root, source)
    if any(item["id"] == PRODUCER for item in raw["producers"]):
        raise production.CompositionError("historical boot-chain producer is already declared")
    selected = dict(MEMBER_UNITS)
    if any(member["producer"] is not None for member in raw["members"] if member["id"] in selected):
        raise production.CompositionError("boot-chain member already declares a producer")
    chain, chain_ref = _manifest(root, boot_chain.MANIFEST)
    crypto, crypto_ref = _manifest(root, boot_crypto_target.MANIFEST)
    paths = {*INSPECTORS, *_source_paths(chain), *_source_paths(crypto),
             *(f"{boot_chain.STAGED}/{name}" for name in boot_chain.STAGED_FILES),
             boot_crypto_target.MANIFEST,
             *(f"{boot_crypto_target.STAGED}/{mode}.s" for mode in boot_crypto_target.MODES)}
    refs = {path: production.reference(root, path) for path in sorted(paths)}
    # The manifest snapshots precede validation; a later read cannot replace the
    # identity whose source/product relations the validator actually inspected.
    refs[chain_ref["path"]] = chain_ref
    refs[crypto_ref["path"]] = crypto_ref
    binding = production._binding(root, raw, input_ref, roster_ref)
    inspected = boot_chain.staged(root, historical=True)
    if inspected.manifest != chain:
        raise production.CompositionError("stale boot-chain manifest during inspection")
    status = compiler_provenance.inspect(chain.get("compiler_provenance"),
                                         root / boot_crypto_target.LOCK)
    for ref in refs.values():
        production._bound(root, ref)
    raw["producers"].append({"id": PRODUCER, "sources": list(refs.values())})
    for member in raw["members"]:
        if member["id"] in selected:
            member["producer"] = PRODUCER
            for unit in selected[member["id"]]:
                ref = refs[f"{boot_chain.STAGED}/{unit}.s"]
                if ref not in member["sources"]:
                    member["sources"].append(ref)
    destination = production._path(root, output)
    if not destination.is_relative_to((root / "out").resolve()):
        raise production.CompositionError("staged composition candidate belongs under out/")
    protected = [*refs.values(), *_references(binding)]
    if any(destination == production._path(root, ref["path"])
           or (destination.exists() and destination.samefile(production._path(root, ref["path"])))
           for ref in protected):
        raise production.CompositionError("staged composition output would overwrite an input or product")
    # Recheck consumed identities immediately before publishing, including the
    # original input's transitive package sources. This is no atomic snapshot.
    for ref in protected:
        production._bound(root, ref)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(composer.canonical_bytes(raw))
    return {"output": output, "producer": PRODUCER, "compiler_provenance_status": status,
            "products": {member: [refs[f"{boot_chain.STAGED}/{unit}.s"] for unit in units]
                         for member, units in MEMBER_UNITS},
            "production_admission": False, "final_target_acceptance": False}
