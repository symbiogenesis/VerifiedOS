# SPDX-License-Identifier: Apache-2.0
"""Construct [the bounded boot fixture](../../docs/implementation/contracts/boot-roster.md#fixed-package-image-observation) once for two layouts."""

from pathlib import Path
from typing import Any

from vos import asm, fixed_composition, image, package_artifacts

BASE = 0x80000000
DATA_OFFSET = 256
PEER_OFFSET = 4096
LAYOUTS = (("lower", BASE), ("upper", BASE + 8192))
SOURCES = ("tools/boot/fixed-controller.s", "tools/boot/fixed-worker.s")
CONFIGURATION = "model/config/verifiedos.json"
CONTRACT = (b"fixture-only PC-relative controller/worker; worker offset 4096, initializer offset 256; "
            b"scalar result 7, caller-held reset root, HTIF F then success; no production authority")


def _reference(blob: bytes) -> dict[str, object]:
    return {"sha256": package_artifacts.digest(blob), "bytes": len(blob)}


def _package(root: Path, output: Path, source: str, snapshot: bytes,
             context: dict[str, str], *, controller: bool) -> dict[str, Any]:
    name = "fixture-controller" if controller else "fixture-worker"
    sections, symbols, entry = asm.Assembler(snapshot.decode("utf-8"), name, text_base=BASE,
                                            data_base=BASE + DATA_OFFSET).assemble()
    symbols["entry"] = (".text", entry)
    producer = output / f"{name}.elf"
    image.write_elf(producer, sections, symbols, entry)
    exports = [{"name": "entry", "offset": 0},
               {"name": "tohost" if controller else "value", "offset": DATA_OFFSET}]
    blobs = [snapshot, CONTRACT, bytes(sections[0].data), bytes(sections[1].data),
             f"fixture-only opaque derivation for {name}".encode(),
             f"fixture-only opaque correspondence for {name}".encode()]
    refs = [_reference(blob) for blob in blobs]
    manifest = {"schema_version": 1, "package_id": name, "context": context,
                "source_closure": refs[0], "contract": refs[1], "span": DATA_OFFSET + len(blobs[3]),
                "alignment": 16, "entry": 0, "exports": exports,
                "regions": [{"name": "text", "kind": "code", "offset": 0, "alignment": 4,
                             "memory_class": 0, "object": refs[2]},
                            {"name": "data", "kind": "initializer", "offset": DATA_OFFSET,
                             "alignment": 8, "memory_class": 0, "object": refs[3]}],
                "proofs": {"derivation_template": refs[4], "correspondence": refs[5],
                           "hyperproperties": []}}
    transports = []
    for ref, blob in zip(refs, blobs, strict=True):
        path = output / "inputs" / f"{ref['sha256']}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(blob)
        transports.append({**ref, "path": path.relative_to(root).as_posix()})
    request = output / f"{name}.json"
    request.write_bytes(package_artifacts.canonical({"manifest": manifest, "objects": transports}))
    relative = request.relative_to(root).as_posix()
    store = (output / "store").relative_to(root).as_posix()
    artifact = fixed_composition.publish_package(
        root, relative, store, producer_image=producer.relative_to(root).as_posix(), producer_base=BASE)
    return {**artifact, "request": relative, "source": source,
            "producer_base": BASE}


def prepare(root: Path, output: str = "out/fixed-boot-fixture") -> dict[str, object]:
    """Publish fresh fixture inputs; reused layouts never invoke their package producers."""
    root = root.resolve()
    destination = fixed_composition.store_path(root, output)
    if destination.exists():
        raise package_artifacts.PackageError("fixed boot fixture requires a fresh output directory")
    snapshots = {path: (root / path).read_bytes() for path in (*SOURCES, CONFIGURATION)}
    context = {field: package_artifacts.digest(b"fixture-only context/" + field.encode() + CONTRACT)
               for field in ("target", "specification", "model", "descriptor", "profile", "decoder", "dictionary")}
    destination.mkdir(parents=True)
    packages = [_package(root, destination, path, snapshots[path], context, controller=index == 0)
                for index, path in enumerate(SOURCES)]
    configuration = (destination / "configuration.json").relative_to(root).as_posix()
    (root / configuration).write_bytes(snapshots[CONFIGURATION])
    store = (destination / "store").relative_to(root).as_posix()
    layouts = []
    for name, base in LAYOUTS:
        directory = destination / name
        directory.mkdir()
        composition = (directory / "composition.json").relative_to(root).as_posix()
        recipe = {"schema_version": 1, "context": context,
                  "packages": [{"artifact": member["artifact"], "base": base + index * PEER_OFFSET}
                               for index, member in enumerate(packages)],
                  "memory": [{"base": BASE, "size": 65536, "memory_class": 0,
                              "writable": True, "executable": True}], "entry": packages[0]["artifact"]}
        (root / composition).write_bytes(package_artifacts.canonical(recipe))
        elf = (directory / "image.elf").relative_to(root).as_posix()
        binding = fixed_composition.compose(root, composition, store, elf)
        observation = (directory / "observation.json").relative_to(root).as_posix()
        (root / observation).write_bytes(package_artifacts.canonical({
            "schema_version": 1, "name": f"fixed-fixture-{name}", "composition": composition,
            "store": store, "image": elf, "configuration": configuration,
            "inst_limit": 1000, "tohost": hex(base + DATA_OFFSET), "expected": None}))
        layouts.append({"name": name, "base": base, "composition": composition, "image": elf,
                        "observation_recipe": observation, "tohost": binding["tohost"]})
    for path, snapshot in snapshots.items():
        if (root / path).read_bytes() != snapshot:
            raise package_artifacts.PackageError("fixed boot fixture source changed during construction")
    result: dict[str, object] = {
        "schema_version": 1, "scope": "two-package assembly fixture; opaque proof objects and synthetic context",
        "production_admission": False, "final_target_acceptance": False, "roster_identity": None,
        "source_identities": [{"path": path, **_reference(blob)} for path, blob in snapshots.items()],
        "packages": packages, "layouts": layouts,
        "construction": "each package assembled once before either translated layout"}
    (destination / "fixture.json").write_bytes(package_artifacts.canonical(result))
    return result
