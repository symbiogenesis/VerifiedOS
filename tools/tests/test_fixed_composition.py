# SPDX-License-Identifier: Apache-2.0
"""The public fixed-package commands compose actual stored bytes without producers."""

import copy
import json
import struct
import tempfile
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
            Case("HTIF symbol omission duplicates malformed tables and undeclared exports refuse", _htif_symbol_population_is_closed)]
