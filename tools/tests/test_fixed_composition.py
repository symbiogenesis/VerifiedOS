# SPDX-License-Identifier: Apache-2.0
"""The public fixed-package commands compose actual stored bytes without producers."""

import copy
import json
import struct
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_package_artifacts import fixture_artifact, fixture_request
from vos import asm, fixed_composition, image, package_artifacts
from vos.cli import composer


def fixture_recipe(root: Path) -> str:
    artifact = fixture_artifact(root, "cli-example")
    package_artifacts.store(root / "out/native-packages", artifact)
    raw = {"schema_version": 1, "context": artifact.document()["context"],
           "packages": [{"artifact": artifact.identity, "base": 0x80000000}],
           "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                       "writable": True, "executable": True}], "entry": artifact.identity}
    name = "fixed-recipe.json"
    (root / name).write_bytes(package_artifacts.canonical(raw))
    return name


def fixture_store(root: Path) -> str:
    fixture_artifact(root, "cli-stored")
    return "cli-stored.json"


def _run(root: Path, args: list[str]) -> tuple[int, str]:
    out = StringIO()
    with patch.object(composer.corpus, "find_root", return_value=root), redirect_stdout(out):
        code = composer.main(args)
    return code, out.getvalue()


def producer_fixture(root: Path) -> tuple[str, Path, dict[str, Any]]:
    request, code = fixture_request(root, "produced")
    request["manifest"]["exports"].append({"name": "value", "offset": 256})
    source = "produced.json"
    (root / source).write_bytes(package_artifacts.canonical(request))
    path = root / "out/producer.elf"
    path.parent.mkdir(parents=True, exist_ok=True)
    sections = [image.Section(".text", 0x80000000, bytearray(code), executable=True),
                image.Section(".data", 0x80000100, bytearray(struct.pack("<Q", 11)), writable=True)]
    image.write_elf(path, sections, {"main": (".text", 0x80000000), "value": (".data", 0x80000100)}, 0x80000000)
    return source, path, request


def _import_produced_image_at_two_layouts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-produced-package-") as directory:
        root = Path(directory)
        source, path, request = producer_fixture(root)
        original = path.read_bytes()
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            result = fixed_composition.publish_package(root, source, "out/store",
                                                      producer_image="out/producer.elf", producer_base=0x80000000)
            artifact = package_artifacts.load(root / "out/store", str(result["artifact"]))
            ensure(result["producer_image"] == {"path": "out/producer.elf", "base": 0x80000000,
                                                "sha256": package_artifacts.digest(original)}
                   and result["production_admission"] is False,
                   "import binds actual produced image bytes and withholds proof/target acceptance")
            for base in (0x80000000, 0x80001000):
                recipe = {"schema_version": 1, "context": request["manifest"]["context"],
                          "packages": [{"artifact": artifact.identity, "base": base}],
                          "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                                      "writable": True, "executable": True}], "entry": artifact.identity}
                (root / "recipe.json").write_bytes(package_artifacts.canonical(recipe))
                output = f"out/translated-{base:x}.elf"
                fixed_composition.compose(root, "recipe.json", "out/store", output)
                package_artifacts.verify_image((root / output).read_bytes(),
                                               [package_artifacts.place(artifact, base)], expected_entry=base)
            ensure(path.read_bytes() == original, "import and translated composition preserve original producer ELF")


def _producer_image_refusals_preserve_the_store() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-produced-refusals-") as directory:
        root = Path(directory)
        source, path, _request = producer_fixture(root)
        prior = fixture_artifact(root, "retained")
        package_artifacts.store(root / "out/store", prior)
        retained = {p.relative_to(root / "out/store").as_posix(): p.read_bytes()
                    for p in (root / "out/store").rglob("*") if p.is_file()}
        original = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", original)
        first_load = struct.unpack_from("<IIQQQQQQ", original, image.EHDR_SIZE)
        symbol_section_at = header[6] + (header[12] - 3) * image.SHDR_SIZE
        symbol_table = struct.unpack_from("<IIQQQQIIQQ", original, symbol_section_at)
        corruptions: list[tuple[str, bytes]] = []
        for field, at, format_, value in (
                ("load-byte", first_load[2], "<B", original[first_load[2]] ^ 1),
                ("load-permission", image.EHDR_SIZE + 4, "<I", image.PF_R | image.PF_W | image.PF_X),
                ("entry", 24, "<Q", 0x80000004),
                ("export-value", symbol_table[4] + image.SYM_SIZE + 8, "<Q", 0x80000004),
                ("undefined-export", symbol_table[4] + image.SYM_SIZE + 6, "<H", 0),
                ("export-region-flags", header[6] + image.SHDR_SIZE + 8, "<Q", image.SHF_ALLOC),
                ("export-region-bytes", header[6] + image.SHDR_SIZE + 24, "<Q", first_load[2] + 1),
                ("symbol-table-shape", symbol_section_at + 56, "<Q", 8)):
            changed = bytearray(original)
            struct.pack_into(format_, changed, at, value)
            corruptions.append((field, bytes(changed)))
        missing = bytearray(original)
        struct.pack_into("<I", missing, symbol_table[4] + image.SYM_SIZE, 0)
        corruptions.append(("missing-export", bytes(missing)))
        duplicate = bytearray(original)
        main_name = struct.unpack_from("<I", original, symbol_table[4] + image.SYM_SIZE)[0]
        struct.pack_into("<I", duplicate, symbol_table[4] + 2 * image.SYM_SIZE, main_name)
        corruptions.append(("duplicate-export", bytes(duplicate)))
        for field, changed in corruptions:
            path.write_bytes(changed)
            try:
                fixed_composition.publish_package(root, source, "out/store",
                                                  producer_image="out/producer.elf", producer_base=0x80000000)
            except package_artifacts.PackageError:
                pass
            else:
                raise AssertionError(f"producer import accepted {field}")
            ensure(path.read_bytes() == changed and retained == {
                p.relative_to(root / "out/store").as_posix(): p.read_bytes()
                for p in (root / "out/store").rglob("*") if p.is_file()},
                f"{field} refusal preserves producer bytes and every existing store member")


def _producer_import_refuses_input_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-produced-drift-") as directory:
        root = Path(directory)
        source, path, request = producer_fixture(root)
        original = path.read_bytes()
        source_bytes = (root / source).read_bytes()
        object_path = root / request["objects"][0]["path"]
        object_bytes = object_path.read_bytes()
        verify = package_artifacts.verify_exports
        for changed in (root / source, object_path, path):
            (root / source).write_bytes(source_bytes)
            object_path.write_bytes(object_bytes)
            path.write_bytes(original)

            def drift(blob: bytes, placement: package_artifacts.Placement, changed: Path = changed) -> None:
                verify(blob, placement)
                changed.write_bytes(changed.read_bytes() + b" ")

            with patch.object(package_artifacts, "verify_exports", side_effect=drift):
                try:
                    fixed_composition.publish_package(root, source, "out/store",
                                                      producer_image="out/producer.elf", producer_base=0x80000000)
                except package_artifacts.PackageError as error:
                    ensure("changed before publication" in str(error), str(error))
                else:
                    raise AssertionError("producer import accepted input drift")
            ensure(not (root / "out/store").exists(), "drift refuses before creating or publishing store contents")


def _producer_import_requires_paired_inputs_and_separate_outputs() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-produced-inputs-") as directory:
        root = Path(directory)
        source, path, _request = producer_fixture(root)
        original = path.read_bytes()
        for producer_image, producer_base in (("out/producer.elf", None), (None, 0x80000000),
                                              ("out/producer.elf", True)):
            try:
                fixed_composition.publish_package(root, source, "out/store", producer_image=producer_image,
                                                  producer_base=producer_base)
            except package_artifacts.PackageError:
                pass
            else:
                raise AssertionError("producer import accepted unpaired or noninteger base inputs")
        (root / "out/producer").mkdir()
        (root / "out/producer/producer.elf").write_bytes(original)
        try:
            fixed_composition.publish_package(root, source, "out/producer", producer_image="out/producer/producer.elf",
                                              producer_base=0x80000000)
        except package_artifacts.PackageError as error:
            ensure("overlap" in str(error), str(error))
        else:
            raise AssertionError("producer import accepted a store containing its input image")
        (root / "out/store").mkdir()
        (root / "out/store/.publish.lock").hardlink_to(path)
        try:
            fixed_composition.publish_package(root, source, "out/store", producer_image="out/producer.elf",
                                              producer_base=0x80000000)
        except package_artifacts.PackageError as error:
            ensure("overlap" in str(error), str(error))
        else:
            raise AssertionError("producer import accepted a store output hardlinked to its input image")
        ensure(path.read_bytes() == original and not (root / "out/store/manifests").exists(),
               "input and output refusals preserve produced bytes and publish no artifact root")


def _producer_import_rechecks_under_lock_and_before_root_publication() -> None:
    for boundary in ("lock", "root", "retained-hit"):
        for input_kind in ("request", "object", "image"):
            with tempfile.TemporaryDirectory(prefix="vos-produced-publication-") as directory:
                root = Path(directory)
                source, path, request = producer_fixture(root)
                prior = fixture_artifact(root, "retained")
                home = root / "out/store"
                package_artifacts.store(home, prior)
                artifact = package_artifacts.read_request(root, source)
                if boundary == "retained-hit":
                    package_artifacts.store(home, artifact)
                retained = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
                changed = {"request": root / source, "object": root / request["objects"][0]["path"],
                           "image": path}[input_kind]

                def mutate(changed: Path = changed) -> None:
                    changed.write_bytes(changed.read_bytes() + b" ")

                enter = package_artifacts.FileLock.__enter__
                publish = package_artifacts._publish
                load = package_artifacts.load

                def lock_drift(lock: package_artifacts.FileLock,
                               enter: Callable[[package_artifacts.FileLock], package_artifacts.FileLock] = enter
                               ) -> package_artifacts.FileLock:
                    acquired = enter(lock)
                    mutate()
                    return acquired

                def object_drift(path: Path, data: bytes, publish: Callable[[Path, bytes], None] = publish) -> None:
                    publish(path, data)
                    mutate()

                def retained_drift(directory: Path, identity: str,
                                   load: Callable[[Path, str], package_artifacts.Artifact] = load
                                   ) -> package_artifacts.Artifact:
                    result = load(directory, identity)
                    mutate()
                    return result

                target, replacement = {"lock": ("FileLock.__enter__", lock_drift),
                                       "root": ("_publish", object_drift),
                                       "retained-hit": ("load", retained_drift)}[boundary]
                if boundary == "lock":
                    hook = patch.object(package_artifacts.FileLock, "__enter__", side_effect=replacement, autospec=True)
                else:
                    hook = patch.object(package_artifacts, target, side_effect=replacement)
                with hook:
                    try:
                        fixed_composition.publish_package(root, source, "out/store",
                                                          producer_image="out/producer.elf", producer_base=0x80000000)
                    except package_artifacts.PackageError as error:
                        ensure("changed before publication" in str(error), str(error))
                    else:
                        raise AssertionError(f"producer import accepted {input_kind} drift at {boundary}")
                ensure(all(p.read_bytes() == data for p, data in retained.items()),
                       "publication refusal preserves every previously retained store byte")
                expected_roots = {f"{prior.identity}.json"}
                if boundary == "retained-hit":
                    expected_roots.add(f"{artifact.identity}.json")
                ensure({p.name for p in (home / "manifests").iterdir()} == expected_roots,
                       "publication refusal creates no new artifact root or imported success")


def _commands_reuse_the_actual_artifact() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-cli-") as directory:
        root = Path(directory)
        source = fixture_store(root)
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            code, out = _run(root, ["package-store", source])
            ensure(code == 0, out)
            stored = json.loads(out)
            artifact = package_artifacts.load(root / "out/native-packages", stored["artifact"])
            raw: dict[str, Any] = {"schema_version": 1, "context": artifact.document()["context"],
                   "packages": [{"artifact": artifact.identity, "base": 0x80000000}],
                   "memory": [{"base": 0x80000000, "size": 65536, "memory_class": 0,
                               "writable": True, "executable": True}], "entry": artifact.identity}
            retained = {path.relative_to(root).as_posix(): path.read_bytes()
                        for path in (root / "out/native-packages").rglob("*") if path.is_file()}
            for index, base in enumerate((0x80000000, 0x80001000)):
                raw["packages"][0]["base"] = base
                (root / "recipe.json").write_bytes(package_artifacts.canonical(raw))
                destination = f"out/generation-{index}.elf"
                code, out = _run(root, ["compose-fixed", "recipe.json", "--output", destination])
                ensure(code == 0, out)
                report = json.loads(out)
                ensure(report["packages"][0]["artifact"] == artifact.identity
                       and report["packages"][0]["base"] == base
                       and report["production_admission"] is False,
                       "public composition preserves artifact identity and its honest producer scope")
                package_artifacts.verify_image((root / destination).read_bytes(),
                                               [package_artifacts.place(artifact, base)])
            ensure(retained == {path.relative_to(root).as_posix(): path.read_bytes()
                                for path in (root / "out/native-packages").rglob("*") if path.is_file()},
                   "successor layout does not rewrite unchanged package objects or proofs")


def _replace_only_one_package() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-update-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        original = raw["packages"][0]["artifact"]
        old = fixture_artifact(root, "changed", marker=9)
        new = fixture_artifact(root, "changed", marker=10)
        for artifact in (old, new):
            package_artifacts.store(root / "out/native-packages", artifact)
        with patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")):
            for index, artifact in enumerate((old, new)):
                raw["packages"] = [{"artifact": original, "base": 0x80000000},
                                   {"artifact": artifact.identity, "base": 0x80001000}]
                (root / source).write_bytes(package_artifacts.canonical(raw))
                result = fixed_composition.compose(root, source, "out/native-packages", f"out/update-{index}.elf")
                members = result["packages"]
                ensure(isinstance(members, list) and members[0]["artifact"] == original
                       and members[1]["artifact"] == artifact.identity,
                       "only the changed package identity moves between native generations")


def _refusals_preserve_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-cli-refusals-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        original = json.loads((root / source).read_bytes())
        destination = root / "out/preserved.elf"
        destination.write_bytes(b"old generation")
        variants: list[dict[str, Any]] = []
        bad = copy.deepcopy(original)
        bad["packages"][0]["base"] = True
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["memory"][0]["memory_class"] = 1
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["context"]["model"] = "2" * 64
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["entry"] = "0" * 64
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["packages"].append(bad["packages"][0])
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["accepted"] = True
        variants.append(bad)
        for raw in variants:
            (root / source).write_bytes(package_artifacts.canonical(raw))
            code, out = _run(root, ["compose-fixed", source, "--output", "out/preserved.elf"])
            ensure(code == 1 and out.startswith("FAIL composer:"), out)
            ensure(destination.read_bytes() == b"old generation", "refused composition replaced a generation")
        (root / source).write_bytes(package_artifacts.canonical(original))
        for output in (source, "out/native-packages/objects/substitute.bin", "../outside.elf"):
            code, out = _run(root, ["compose-fixed", source, "--output", output])
            ensure(code == 1 and out.startswith("FAIL composer:"), out)
        (root / source).write_bytes(b" " * (package_artifacts.MANIFEST_LIMIT + 1))
        code, out = _run(root, ["compose-fixed", source, "--output", "out/preserved.elf"])
        ensure(code == 1 and "byte limit" in out and destination.read_bytes() == b"old generation", out)


def _selected_entry_substitution_preserves_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-entry-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        sibling = fixture_artifact(root, "sibling")
        package_artifacts.store(root / "out/native-packages", sibling)
        raw["packages"].append({"artifact": sibling.identity, "base": 0x80001000})
        original = image.write_elf
        destination = root / "out/generation.elf"
        for selected in (raw["packages"][0]["artifact"], sibling.identity):
            raw["entry"] = selected
            (root / source).write_bytes(package_artifacts.canonical(raw))
            args = ["compose-fixed", source, "--output", "out/generation.elf"]
            code, report = _run(root, args)
            ensure(code == 0, report)
            selected_base = next(item["base"] for item in raw["packages"] if item["artifact"] == selected)
            ensure(struct.unpack_from("<Q", destination.read_bytes(), 24)[0] == selected_base,
                   "composition starts at the recipe-selected member")
            previous = destination.read_bytes()
            alternate = next(item["base"] for item in raw["packages"] if item["artifact"] != selected)

            def substituted(path: Path, sections: list[image.Section], symbols: dict[str, tuple[str, int]],
                            entry: int, *, alternate_entry: int = alternate) -> None:
                original(path, sections, symbols, entry)
                blob = bytearray(path.read_bytes())
                struct.pack_into("<Q", blob, 24, alternate_entry)
                path.write_bytes(blob)

            with patch.object(image, "write_elf", side_effect=substituted):
                code, report = _run(root, args)
            ensure(code == 1 and "selected package entry" in report, report)
            ensure(destination.read_bytes() == previous,
                   "a valid sibling entry substitution preserves the prior generation")


def _checked_images_need_no_producer_or_writes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-check-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        expected = fixed_composition.compose(root, source, "out/native-packages", "out/image.elf")
        before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        with (patch.object(asm.Assembler, "assemble", side_effect=AssertionError("producer reran")),
              patch.object(image, "write_elf", side_effect=AssertionError("image rebuilt")),
              patch.object(Path, "write_bytes", side_effect=AssertionError("read-only check wrote bytes")),
              patch.object(Path, "mkdir", side_effect=AssertionError("read-only check made a directory"))):
            code, report = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
        ensure(code == 0 and json.loads(report) == expected, report)
        ensure(expected["tohost"] is None, "host-only composition declares no HTIF export")
        ensure(before == {path.relative_to(root): path.read_bytes()
                          for path in root.rglob("*") if path.is_file()},
               "read-only checking preserves the complete source/store/image population")


def _read_only_image_and_input_refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-check-refusal-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        fixed_composition.compose(root, source, "out/native-packages", "out/image.elf")
        path = root / "out/image.elf"
        original = path.read_bytes()
        payload = struct.unpack_from("<IIQQQQQQ", original, image.EHDR_SIZE)[2]
        changed = bytearray(original)
        changed[payload] ^= 1
        bad_entry = bytearray(original)
        struct.pack_into("<Q", bad_entry, 24, 0x80000004)
        bad_permissions = bytearray(original)
        struct.pack_into("<I", bad_permissions, image.EHDR_SIZE + 4, image.PF_R | image.PF_W)
        variants = (bytes(changed), bytes(bad_entry), bytes(bad_permissions), original[:64])
        for contents in variants:
            path.write_bytes(contents)
            before = {item.relative_to(root): item.read_bytes() for item in root.rglob("*") if item.is_file()}
            code, report = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
            ensure(code == 1 and report.startswith("FAIL composer:"), report)
            ensure(before == {item.relative_to(root): item.read_bytes()
                              for item in root.rglob("*") if item.is_file()},
                   "a refused image check writes no existing output")
        path.write_bytes(original)
        raw = json.loads((root / source).read_bytes())
        for change in ("context", "placement"):
            bad = copy.deepcopy(raw)
            if change == "context":
                bad["context"]["model"] = "2" * 64
            else:
                bad["packages"][0]["base"] += 4096
            (root / source).write_bytes(package_artifacts.canonical(bad))
            code, report = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
            ensure(code == 1 and path.read_bytes() == original, report)


def _read_only_check_refuses_input_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-check-drift-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        fixed_composition.compose(root, source, "out/native-packages", "out/image.elf")
        image_path = root / "out/image.elf"
        recipe_path = root / source
        recipe_bytes, image_bytes = recipe_path.read_bytes(), image_path.read_bytes()
        raw = json.loads(recipe_bytes)
        artifact = package_artifacts.load(root / "out/native-packages", raw["entry"])
        object_path = root / "out/native-packages/objects" / f"{artifact.objects[0][0]}.bin"
        object_bytes = object_path.read_bytes()
        original = package_artifacts.verify_observation_symbol
        for changed_input in ("recipe", "store", "image"):
            def changed(blob: bytes, expected: tuple[str, int] | None, *, target: str = changed_input) -> None:
                original(blob, expected)
                if target == "recipe":
                    recipe_path.write_bytes(recipe_bytes + b" ")
                elif target == "store":
                    object_path.write_bytes(bytes([object_bytes[0] ^ 1]) + object_bytes[1:])
                else:
                    image_path.write_bytes(image_bytes[:-1] + bytes([image_bytes[-1] ^ 1]))

            with patch.object(package_artifacts, "verify_observation_symbol", side_effect=changed):
                code, report = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
            ensure(code == 1 and report.startswith("FAIL composer:"), report)
            recipe_path.write_bytes(recipe_bytes)
            object_path.write_bytes(object_bytes)
            image_path.write_bytes(image_bytes)
        code, report = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
        ensure(code == 0, report)


def _htif_artifact(root: Path, name: str) -> package_artifacts.Artifact:
    request, _ = fixture_request(root, name)
    request["manifest"]["exports"].append({"name": "tohost", "offset": 256})
    source = root / f"{name}.json"
    source.write_bytes(package_artifacts.canonical(request))
    artifact = package_artifacts.read_request(root, source.name)
    package_artifacts.store(root / "out/native-packages", artifact)
    return artifact


def _htif_export_and_actual_elf_symbol_agree() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-htif-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        artifact = _htif_artifact(root, "observed")
        raw["packages"] = [{"artifact": artifact.identity, "base": 0x80000000}]
        raw["entry"] = artifact.identity
        (root / source).write_bytes(package_artifacts.canonical(raw))
        report = fixed_composition.compose(root, source, "out/native-packages", "out/image.elf")
        ensure(report["tohost"] == 0x80000100, "report exposes the translated initializer export")
        ensure(fixed_composition.validate(root, source, "out/native-packages", "out/image.elf") == report,
               "read-only check binds the exact same observation address")
        path = root / "out/image.elf"
        original = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", original)
        table = struct.unpack_from("<IIQQQQIIQQ", original,
                                   header[6] + (header[12] - 3) * image.SHDR_SIZE)
        entry = table[4] + image.SYM_SIZE
        ensure(struct.unpack_from("<Q", original, entry + 8)[0] == 0x80000100,
               "the emitted ELF symbol carries the independently expected HTIF address")
        for field, value in (("value", 0x80000000), ("undefined", 0), ("type", 3), ("section", 1)):
            bad = bytearray(original)
            if field == "value":
                struct.pack_into("<Q", bad, entry + 8, value)
            elif field == "type":
                bad[entry + 4] = value
            else:
                struct.pack_into("<H", bad, entry + 6, value)
            path.write_bytes(bad)
            code, out = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
            ensure(code == 1 and "tohost" in out and path.read_bytes() == bad, out)
        path.write_bytes(original)
        sibling = _htif_artifact(root, "another-observer")
        raw["packages"].append({"artifact": sibling.identity, "base": 0x80001000})
        (root / source).write_bytes(package_artifacts.canonical(raw))
        code, out = _run(root, ["compose-fixed", source, "--output", "out/image.elf"])
        ensure(code == 1 and "unambiguous tohost" in out and path.read_bytes() == original, out)


def _htif_requires_a_complete_writable_word() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-htif-window-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        fixed_composition.compose(root, source, "out/native-packages", "out/image.elf")
        path = root / "out/image.elf"
        previous = path.read_bytes()
        for label, offset in (("code", 0), ("unaligned", 260), ("short", 264)):
            request, _ = fixture_request(root, label)
            request["manifest"]["exports"].append({"name": "tohost", "offset": offset})
            if label == "short":
                request["manifest"]["regions"][1].update(offset=260, alignment=4)
            request_path = root / f"{label}.json"
            request_path.write_bytes(package_artifacts.canonical(request))
            artifact = package_artifacts.read_request(root, request_path.name)
            package_artifacts.store(root / "out/native-packages", artifact)
            raw["packages"] = [{"artifact": artifact.identity, "base": 0x80000000}]
            raw["entry"] = artifact.identity
            (root / source).write_bytes(package_artifacts.canonical(raw))
            code, out = _run(root, ["compose-fixed", source, "--output", "out/image.elf"])
            ensure(code == 1 and "aligned writable initializer word" in out, out)
            ensure(path.read_bytes() == previous, "invalid exported HTIF windows preserve the image")


def _htif_symbol_population_is_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-fixed-htif-symbols-") as directory:
        root = Path(directory)
        source = fixture_recipe(root)
        raw = json.loads((root / source).read_bytes())
        artifact = _htif_artifact(root, "symbol-owner")
        raw["packages"] = [{"artifact": artifact.identity, "base": 0x80000000}]
        raw["entry"] = artifact.identity
        (root / source).write_bytes(package_artifacts.canonical(raw))
        placement = package_artifacts.place(artifact, 0x80000000)
        path = root / "out/image.elf"
        symbol = (placement.sections[1].name, 0x80000100)
        # Independently emitted metadata supplies omission and duplicate-name
        # cases without changing any of the package's physical load bytes.
        image.write_elf(path, list(placement.sections), {}, placement.entry)
        code, out = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
        ensure(code == 1 and "tohost symbol differs" in out, out)
        image.write_elf(path, list(placement.sections), {"probe": symbol, "tohost": symbol}, placement.entry)
        original = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", original)
        table_address = header[6] + (header[12] - 3) * image.SHDR_SIZE
        table = struct.unpack_from("<IIQQQQIIQQ", original, table_address)
        bad = bytearray(original)
        tohost_name = struct.unpack_from("<I", original, table[4] + 2 * image.SYM_SIZE)[0]
        struct.pack_into("<I", bad, table[4] + image.SYM_SIZE, tohost_name)
        path.write_bytes(bad)
        code, out = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
        ensure(code == 1 and "tohost symbol differs" in out, out)
        for field, value in (("entry-size", 8), ("link", header[12]), ("table-offset", len(original))):
            bad = bytearray(original)
            if field == "entry-size":
                struct.pack_into("<Q", bad, table_address + 56, value)
            elif field == "link":
                struct.pack_into("<I", bad, table_address + 40, value)
            else:
                struct.pack_into("<Q", bad, table_address + 24, value)
            path.write_bytes(bad)
            code, out = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
            ensure(code == 1 and "symbol" in out and path.read_bytes() == bad, out)
        # Removing the declared export leaves the formerly valid named symbol
        # unauthorized even though its physical initializer bytes still match.
        request = json.loads((root / "symbol-owner.json").read_bytes())
        request["manifest"]["exports"] = [{"name": "main", "offset": 0}]
        (root / "symbol-owner.json").write_bytes(package_artifacts.canonical(request))
        unexported = package_artifacts.read_request(root, "symbol-owner.json")
        package_artifacts.store(root / "out/native-packages", unexported)
        raw["packages"][0]["artifact"] = unexported.identity
        raw["entry"] = unexported.identity
        (root / source).write_bytes(package_artifacts.canonical(raw))
        path.write_bytes(original)
        code, out = _run(root, ["check-fixed", source, "--image", "out/image.elf"])
        ensure(code == 1 and "undeclared tohost symbol" in out, out)


def cases() -> list[Case]:
    return [Case("public commands reuse exact stored native bytes at two layouts", _commands_reuse_the_actual_artifact),
            Case("one changed package leaves its unchanged neighbor intact", _replace_only_one_package),
            Case("bad context placement and output aliases preserve the old image", _refusals_preserve_output),
            Case("another valid package entry refuses before replacing the generation", _selected_entry_substitution_preserves_output),
            Case("checking an existing package image invokes no producer or writer", _checked_images_need_no_producer_or_writes),
            Case("read-only checks refuse substituted images and changed inputs", _read_only_image_and_input_refusals),
            Case("recipe store and image drift refuse during read-only validation", _read_only_check_refuses_input_drift),
            Case("the exported HTIF window binds the actual loader symbol", _htif_export_and_actual_elf_symbol_agree),
            Case("HTIF requires a complete aligned writable initializer word", _htif_requires_a_complete_writable_word),
            Case("HTIF symbol omission duplicates malformed tables and undeclared exports refuse", _htif_symbol_population_is_closed),
            Case("explicit producer import binds native exports before two translated layouts", _import_produced_image_at_two_layouts),
            Case("producer byte permission entry and export refusals preserve useful store contents", _producer_image_refusals_preserve_the_store),
            Case("request transported objects and producer image drift refuse before publication", _producer_import_refuses_input_drift),
            Case("producer imports require paired inputs and separate store outputs", _producer_import_requires_paired_inputs_and_separate_outputs),
            Case("producer imports recheck lock waits root publication and retained hits", _producer_import_rechecks_under_lock_and_before_root_publication)]
