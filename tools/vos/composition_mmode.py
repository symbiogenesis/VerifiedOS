# SPDX-License-Identifier: Apache-2.0
"""Export the complete retained M-mode stage without admitting its harness mapping.

The [bounded export contract](../../docs/implementation/contracts/production-admission.md#complete-retained-m-mode-export-checkpoint)
keeps the actual RWX harness window distinct from the reconstructed text/data.
"""

import hashlib
from pathlib import Path
from typing import TypedDict

from vos import asm, boot_chain, chain_mmode, composer, source_bindings
from vos import boot_handoff as handoff
from vos import composition as production
from vos import composition_staged as staged
from vos.atomic import atomic_path


class Region(TypedDict):
    kind: str
    address: int
    length: int
    sha256: str
    hex: str


def _region(kind: str, address: int, data: bytes) -> Region:
    return {"kind": kind, "address": address, "length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "hex": data.hex()}


def _destination(root: Path, output: str, bindings: list[dict[str, str]]) -> Path:
    destination = production._path(root, output)
    if not destination.is_relative_to((root / "out").resolve()):
        raise production.CompositionError("M-mode export output belongs under out/")
    for ref in bindings:
        protected = production._path(root, ref["path"])
        if destination == protected or (destination.exists() and destination.samefile(protected)):
            raise production.CompositionError("M-mode export output would overwrite an input")
    return destination


def _bind(root: Path, bindings: list[dict[str, str]]) -> None:
    for ref in bindings:
        production._bound(root, ref)


def export_mmode(root: Path, source: str, products: str, output: str) -> dict[str, object]:
    """Reconstruct all stage bytes and atomically publish their historical identity."""
    # The existing owner authenticates membership/catalog and every retained input.
    _catalog, retained = staged._products(root, source)
    bindings = [*retained, production.reference(root, products),
                *source_bindings.references(root, "composer-package"),
                production.reference(root, chain_mmode.MMODE_ENTRY)]
    unique: dict[str, dict[str, str]] = {}
    for ref in bindings:
        if ref["path"] in unique and unique[ref["path"]] != ref:
            raise production.CompositionError("M-mode export input changed while binding sources")
        unique[ref["path"]] = ref
    bindings = list(unique.values())
    _destination(root, output, bindings)
    selected = staged.select_boot_product(root, source, products,
                                          "mmode-firmware-artifact", "mmode",
                                          f"{boot_chain.STAGED}/mmode.s")
    inputs = boot_chain.staged(root, historical=True)
    layout = handoff.chain_layout(root)
    base = layout["CHAIN_MMODE_LOAD_BASE"]
    built = chain_mmode.mmode_image(root, inputs.streams["mmode"], inputs.kernel_root)
    assembler = asm.Assembler(built.assembly, "export-retained-mmode", text_base=base,
                              data_base=base + layout["CHAIN_MMODE_DATA_AT"],
                              externals=chain_mmode.externals(root))
    sections, _symbols, entry = assembler.assemble()
    if ([section.name for section in sections] != [".text", ".data"] or entry != base):
        raise production.CompositionError("M-mode export has a different entry or section population")
    text, data = sections
    if (text.addr != base or data.addr != base + layout["CHAIN_MMODE_DATA_AT"]
            or text.writable or not text.executable or not data.writable or data.executable
            or not text.data or text.addr + len(text.data) > data.addr):
        raise production.CompositionError("M-mode export has different extents or section permissions")
    gap = bytes(data.addr - text.addr - len(text.data))
    tag = chain_mmode.slot_tag_bytes(root)[0]
    regions = [_region("text", text.addr, bytes(text.data)),
               _region("zero-gap", text.addr + len(text.data), gap),
               _region("initializer", data.addr, bytes(data.data)),
               _region("slot-tag", data.addr + len(data.data), tag)]
    payload = b"".join(bytes.fromhex(region["hex"]) for region in regions)
    retained_payload = inputs.images["mmode-a"][layout["BOOT_HEADER_BYTES"]:]
    if payload != built.payload + tag or payload != retained_payload:
        raise production.CompositionError("M-mode export differs from the complete retained slot-A payload")
    stack_base = built.constants["MMODE_STACK_BASE"]
    stack_bytes = built.constants["MMODE_STACK_BYTES"]
    window_bytes = layout["CHAIN_MMODE_REGION_BYTES"]
    if (base + len(payload) > stack_base or stack_base + stack_bytes != base + window_bytes
            or built.constants["MMODE_STACK_TOP"] != base + window_bytes):
        raise production.CompositionError("M-mode export has a different external stack extent")
    window = payload + bytes(window_bytes - len(payload))
    harness = chain_mmode.compose_main(root, window, bytes(layout["HANDOFF_BYTES"]),
                                      bytes(layout["CHAIN_MAILBOX_BYTES"]), inputs.images["kernel"])
    windows = [section for section in harness.sections if section.name == ".mmode"]
    if (len(windows) != 1 or harness.entry != entry or windows[0].addr != base
            or bytes(windows[0].data) != window
            or windows[0].writable is not True or windows[0].executable is not True):
        raise production.CompositionError("M-mode harness window bytes, entry or RWX permissions differ")
    record: dict[str, object] = {
        "schema_version": 1, "kind": "historical-mmode-byte-export", "member": "mmode-firmware",
        "source": selected["source"], "catalog": selected["catalog"], "bindings": bindings,
        "compiler_provenance_status": selected["compiler_provenance_status"],
        "entry": entry, "regions": regions,
        "payload": {"address": base, "length": len(payload), "sha256": hashlib.sha256(payload).hexdigest()},
        "stack": {"address": stack_base, "length": stack_bytes, "zeroing_owner": "RoT stage placement"},
        "harness_window": {"address": base, "length": window_bytes,
                           "writable": windows[0].writable, "executable": windows[0].executable},
        "installed_mapping": "unresolved-rwx-window", "production_admission": False,
        "final_target_acceptance": False}
    _bind(root, bindings)
    destination = _destination(root, output, bindings)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(destination) as pending:
        pending.write_bytes(composer.canonical_bytes(record))
        _bind(root, bindings)
        if _destination(root, output, bindings) != destination:
            raise production.CompositionError("M-mode export destination changed before publication")
    return record
