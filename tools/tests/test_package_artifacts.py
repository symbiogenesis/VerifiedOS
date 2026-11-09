# SPDX-License-Identifier: Apache-2.0
"""Stored native bytes retain their identity across translated package layouts."""

import copy
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import asm, image
from vos import package_artifacts as packages


def fixture_request(root: Path, name: str = "example", *, marker: int = 7) -> tuple[dict[str, Any], bytes]:
    """Construct real assembler output and opaque fixture proof objects once."""
    source = f".text\n_start:\n    la c5, value\n    addi t0, zero, {marker}\n.data\nvalue: .dword 11\n"
    sections, _, _ = asm.Assembler(source, name, text_base=0x80000000,
                                   data_base=0x80000100).assemble()
    blobs = [source.encode(), f"contract for {name}".encode(), bytes(sections[0].data),
             bytes(sections[1].data), b"fixture typing template", b"fixture correspondence theorem"]
    refs = [{"sha256": packages.digest(blob), "bytes": len(blob)} for blob in blobs]
    context = dict.fromkeys(("target", "specification", "model", "descriptor", "profile", "decoder", "dictionary"),
                            "1" * 64)
    manifest = {"schema_version": 1, "package_id": name, "context": context,
                "source_closure": refs[0], "contract": refs[1], "span": 272, "alignment": 16,
                "regions": [{"name": "text", "kind": "code", "offset": 0, "alignment": 4,
                             "memory_class": 0, "object": refs[2]},
                            {"name": "data", "kind": "initializer", "offset": 256,
                             "alignment": 8, "memory_class": 0, "object": refs[3]}],
                "entry": 0, "exports": [{"name": "main", "offset": 0}],
                "proofs": {"derivation_template": refs[4], "correspondence": refs[5],
                           "hyperproperties": []}}
    objects = []
    for ref, blob in zip(refs, blobs, strict=True):
        relative = f"inputs/{ref['sha256']}.bin"
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
        objects.append({**ref, "path": relative})
    return {"manifest": manifest, "objects": objects}, bytes(sections[0].data)


def fixture_artifact(root: Path, name: str = "example", *, marker: int = 7) -> packages.Artifact:
    request, _ = fixture_request(root, name, marker=marker)
    path = root / f"{name}.json"
    path.write_bytes(packages.canonical(request))
    return packages.read_request(root, path.name)


def _refused(action: Callable[[], object], detail: str) -> None:
    try:
        action()
    except (packages.PackageError, OSError) as error:
        ensure(detail in str(error), f"wrong package refusal: {error}")
        return
    raise AssertionError(f"fixed package unexpectedly accepted {detail}")


def _stored_bytes_at_two_layouts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-packages-") as directory:
        root = Path(directory)
        artifact = fixture_artifact(root)
        home = root / "store"
        ensure(packages.store(home, artifact) == artifact.identity, "store returns actual content identity")
        stored_before = {path.relative_to(home).as_posix(): path.read_bytes()
                         for path in home.rglob("*") if path.is_file()}
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer was invoked again")):
            for base in (0x80000000, 0x80001000):
                loaded = packages.load(home, artifact.identity)
                placed = packages.place(loaded, base)
                packages.validate_memory([placed], [packages.MemoryRegion(base, 4096, 0, True, True)])
                elf = root / "image.elf"
                image.write_elf(elf, list(placed.sections), {}, placed.entry)
                packages.verify_image(elf.read_bytes(), [placed])
                program = struct.unpack_from("<IIQQQQQQ", elf.read_bytes(), image.EHDR_SIZE)
                ensure(elf.read_bytes()[program[2]:program[2] + program[5]] == placed.sections[0].data,
                       "independent physical program header exposes the original instruction bytes")
                ensure(placed.entry == base and dict(placed.exports)["main"] == base,
                       "entry and exports translate with the one package base")
            packages.store(home, loaded)
        ensure(stored_before == {path.relative_to(home).as_posix(): path.read_bytes()
                                 for path in home.rglob("*") if path.is_file()},
               "reuse does not rewrite retained objects or proofs")


def _identity_binds_actual_outputs() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-identities-") as directory:
        root = Path(directory)
        request, _ = fixture_request(root)
        path = root / "request.json"
        path.write_bytes(packages.canonical(request))
        before = packages.read_request(root, path.name)
        changed_transport = copy.deepcopy(request)
        for item in changed_transport["objects"]:
            original = root / item["path"]
            alternate = f"other/{original.name}"
            (root / alternate).parent.mkdir(exist_ok=True)
            (root / alternate).write_bytes(original.read_bytes())
            item["path"] = alternate
        path.write_bytes(packages.canonical(changed_transport))
        ensure(packages.read_request(root, path.name).identity == before.identity,
               "transport names are absent from content identity")
        for field in ("source_closure", "contract"):
            changed = copy.deepcopy(request)
            blob = f"changed {field}".encode()
            ref = {"sha256": packages.digest(blob), "bytes": len(blob)}
            old = changed["manifest"][field]
            changed["manifest"][field] = ref
            changed["objects"] = [item for item in changed["objects"] if item["sha256"] != old["sha256"]]
            relative = f"inputs/{ref['sha256']}.bin"
            (root / relative).write_bytes(blob)
            changed["objects"].append({**ref, "path": relative})
            path.write_bytes(packages.canonical(changed))
            ensure(packages.read_request(root, path.name).identity != before.identity,
                   f"changed {field} must create a different artifact")
        changed = copy.deepcopy(request)
        changed["manifest"]["context"]["model"] = "2" * 64
        path.write_bytes(packages.canonical(changed))
        ensure(packages.read_request(root, path.name).identity != before.identity,
               "model context belongs to artifact identity")
        for key in ("correspondence", "derivation_template"):
            changed = copy.deepcopy(request)
            blob = f"changed {key}".encode()
            ref = {"sha256": packages.digest(blob), "bytes": len(blob)}
            old = changed["manifest"]["proofs"][key]
            changed["manifest"]["proofs"][key] = ref
            changed["objects"] = [item for item in changed["objects"] if item["sha256"] != old["sha256"]]
            relative = f"inputs/{ref['sha256']}.bin"
            (root / relative).write_bytes(blob)
            changed["objects"].append({**ref, "path": relative})
            path.write_bytes(packages.canonical(changed))
            ensure(packages.read_request(root, path.name).identity != before.identity,
                   "actual emitted proof bytes belong to artifact identity")
        for index in (0, 1):
            changed = copy.deepcopy(request)
            old = changed["manifest"]["regions"][index]["object"]
            original = next(item for item in changed["objects"] if item["sha256"] == old["sha256"])
            blob = bytearray((root / original["path"]).read_bytes())
            blob[-1] ^= 1
            ref = {"sha256": packages.digest(bytes(blob)), "bytes": len(blob)}
            changed["manifest"]["regions"][index]["object"] = ref
            changed["objects"] = [item for item in changed["objects"] if item["sha256"] != old["sha256"]]
            relative = f"inputs/{ref['sha256']}.bin"
            (root / relative).write_bytes(blob)
            changed["objects"].append({**ref, "path": relative})
            path.write_bytes(packages.canonical(changed))
            ensure(packages.read_request(root, path.name).identity != before.identity,
                   "code and initializer output changes create new identities with identical source/context")


def _malformed_and_corrupt_objects() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-refusals-") as directory:
        root = Path(directory)
        request, _ = fixture_request(root)
        path = root / "request.json"
        changes: list[tuple[Callable[[dict[str, Any]], object], str]] = [
            (lambda raw: raw["manifest"].update(accepted=True), "schema"),
            (lambda raw: raw["manifest"].update(schema_version=True), "schema"),
            (lambda raw: raw["manifest"]["regions"][0].update(writable=True), "schema"),
            (lambda raw: raw["manifest"]["regions"][1].update(offset=0), "overlap"),
            (lambda raw: raw["manifest"].update(entry=256), "entry"),
            (lambda raw: raw["manifest"].update(alignment=3), "power of two"),
            (lambda raw: raw["manifest"]["proofs"].update(
                correspondence=raw["manifest"]["regions"][0]["object"]), "proof objects"),
            (lambda raw: raw["objects"].pop(), "population"),
            (lambda raw: raw["objects"][0].update(path="../outside"), "relative"),
        ]
        for change, detail in changes:
            bad = copy.deepcopy(request)
            change(bad)
            path.write_bytes(packages.canonical(bad))
            _refused(lambda: packages.read_request(root, path.name), detail)
        path.write_bytes(packages.canonical(request))
        artifact = packages.read_request(root, path.name)
        home = root / "store"
        packages.store(home, artifact)
        object_path = home / "objects" / f"{artifact.objects[0][0]}.bin"
        object_path.write_bytes(b"corrupt")
        _refused(lambda: packages.load(home, artifact.identity), "digest or byte length")
        _refused(lambda: packages.store(home, artifact), "digest or byte length")
        ensure(object_path.read_bytes() == b"corrupt", "reuse must not silently repair corrupt retained bytes")
        object_path.unlink()
        _refused(lambda: packages.store(home, artifact), ".bin")
        ensure(not object_path.exists(), "publishing an existing root must not restore missing retained bytes")
        _refused(lambda: packages.place(artifact, (1 << 36) - 16), "overflow")
        _refused(lambda: packages.place(artifact, True), "alignment")


def _image_and_memory_substitutions() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-image-") as directory:
        root = Path(directory)
        artifact = fixture_artifact(root)
        placed = packages.place(artifact, 0x80000000)
        elf = root / "image.elf"
        image.write_elf(elf, list(placed.sections), {}, placed.entry)
        good = elf.read_bytes()
        # Mutating the convenience Section does not change the immutable expected image.
        placed.sections[0].data[0] ^= 1
        packages.verify_image(good, [placed])
        image.write_elf(elf, list(placed.sections), {}, placed.entry)
        _refused(lambda: packages.verify_image(elf.read_bytes(), [placed]), "bytes or permissions")
        for displacement, fmt, value, detail in (
            (4, "<I", image.PF_R | image.PF_W | image.PF_X, "permissions"),
            (32, "<Q", 0, "extent"),
            (24, "<Q", (1 << 36) - 1, "extent"),
        ):
            bad = bytearray(good)
            struct.pack_into(fmt, bad, image.EHDR_SIZE + displacement, value)
            _refused(lambda bad=bad: packages.verify_image(bytes(bad), [placed]), detail)
        _refused(lambda: packages.verify_image(good[:64], [placed]), "truncated")
        for entry in (0x80000004, 0x80000100, 0x80001000):
            bad = bytearray(good)
            struct.pack_into("<Q", bad, 24, entry)
            _refused(lambda bad=bad: packages.verify_image(bytes(bad), [placed]), "entry")
        fresh = packages.place(artifact, placed.base)
        hidden = image.Section(".hidden", 0x80002000, bytearray(b"\x13\0\0\0"), executable=True)
        image.write_elf(elf, [*fresh.sections, hidden], {}, fresh.entry)
        _refused(lambda: packages.verify_image(elf.read_bytes(), [fresh]), "declared regions")
        other = packages.place(fixture_artifact(root, "other"), 0x80000010)
        _refused(lambda: packages.verify_image(good, [placed, other]), "spans overlap")
        _refused(lambda: packages.validate_memory([placed],
                    [packages.MemoryRegion(0x80000000, 4096, 1, True, True)]), "memory class")
        _refused(lambda: packages.validate_memory([placed],
                    [packages.MemoryRegion(0x80000000, 4096, 0, False, True)]), "permissions")


def _selected_image_entry() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-entry-") as directory:
        root = Path(directory)
        first = packages.place(fixture_artifact(root, "first"), 0x80000000)
        second = packages.place(fixture_artifact(root, "second"), 0x80001000)
        placements = [first, second]
        elf = root / "image.elf"
        for selected, other in ((first, second), (second, first)):
            image.write_elf(elf, [section for item in placements for section in item.sections], {}, selected.entry)
            blob = elf.read_bytes()
            packages.verify_image(blob, placements)
            packages.verify_image(blob, placements, expected_entry=selected.entry)
            _refused(lambda blob=blob, expected=other.entry:
                     packages.verify_image(blob, placements, expected_entry=expected),
                     "selected package entry")
        malformed_entries: tuple[Any, ...] = (True, float(second.entry), second.entry + 4)
        for malformed in malformed_entries:
            _refused(lambda malformed=malformed: packages.verify_image(blob, placements, expected_entry=malformed),
                     "selected package entry")


def cases() -> list[Case]:
    return [Case("one stored native artifact composes at two layouts without its producer", _stored_bytes_at_two_layouts),
            Case("source contract context and actual proof outputs determine identity", _identity_binds_actual_outputs),
            Case("malformed geometry and corrupt retained objects refuse reuse", _malformed_and_corrupt_objects),
            Case("physical image and memory classes match immutable package bytes", _image_and_memory_substitutions),
            Case("an explicitly selected entry cannot be replaced by another package entry", _selected_image_entry)]
