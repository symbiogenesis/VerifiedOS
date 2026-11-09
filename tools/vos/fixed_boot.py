# SPDX-License-Identifier: Apache-2.0
"""Observe stored package images under [the boot contract](../../docs/implementation/contracts/boot-roster.md#fixed-package-image-observation)."""

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vos import boot, fixed_composition, jsonc, package_artifacts
from vos.atomic import atomic_path
from vos.jsonutil import unique_object

FIELDS = frozenset({"schema_version", "name", "composition", "store", "image",
                    "configuration", "inst_limit", "tohost", "expected"})
SCOPE = "fixed-package boot observer; real roster and qualified target acceptance remain open"


@dataclass(frozen=True)
class Recipe:
    path: Path
    snapshot: bytes
    document: dict[str, Any]
    expected: boot.Expected | None


def load_recipe(root: Path, relative: str) -> Recipe:
    path = fixed_composition._path(root, relative)
    snapshot = path.read_bytes()
    if len(snapshot) > package_artifacts.MANIFEST_LIMIT:
        raise boot.RecipeError("fixed boot recipe exceeds its byte limit")
    raw = boot._exact(boot._json(snapshot, relative), FIELDS, relative)
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise boot.RecipeError("fixed boot schema_version must be 1")
    for field in ("name", "composition", "store", "image", "configuration"):
        boot._text(raw[field], f"{relative}/{field}")
    for field in ("composition", "store", "image", "configuration"):
        fixed_composition._path(root, cast("str", raw[field]))
    boot._count(raw["inst_limit"], f"{relative}/inst_limit", positive=True)
    boot._address(raw["tohost"], f"{relative}/tohost")
    expected = boot.parse_expected(raw["expected"], f"{relative}/expected")
    return Recipe(path, snapshot, cast("dict[str, Any]", raw), expected)


def _memory(snapshot: bytes) -> list[package_artifacts.MemoryRegion]:
    try:
        raw = json.loads(jsonc.strip_comments(snapshot.decode("utf-8")), object_pairs_hook=unique_object)
        result = []
        for region in raw["memory"]["regions"]:
            attributes = region["attributes"]
            if attributes["mem_type"] != "MainMemory":
                continue
            memory_class = {"FirstClass": 0, "SecondClass": 1}[attributes["memory_class"]["Some"]]
            result.append(package_artifacts.MemoryRegion(
                boot._hex_value(region["base"], "memory base"),
                boot._hex_value(region["size"], "memory size"), memory_class,
                attributes["writable"], attributes["executable"]))
        if not result:
            raise ValueError("no MainMemory region")
        return result
    except (ValueError, UnicodeError, KeyError, TypeError) as error:
        raise boot.RecipeError(f"fixed boot configuration memory: {error}") from error


def _bindings(root: Path, recipe: Recipe, configuration: bytes) -> dict[str, object]:
    raw = recipe.document
    binding = fixed_composition.validate(root, raw["composition"], raw["store"], raw["image"])
    packages = cast("list[dict[str, Any]]", binding["packages"])
    tohost = int(raw["tohost"], 16)
    if tohost % boot.HTIF_BYTES or binding.get("tohost") != tohost:
        raise boot.RefusalError("fixed boot tohost differs from the aligned ELF/package export")
    blob = (root / raw["image"]).read_bytes()
    if package_artifacts.digest(blob) != cast("dict[str, str]", binding["image"])["sha256"]:
        raise boot.RefusalError("fixed boot image changed after package validation")
    if struct.unpack_from("<Q", blob, 24)[0] != packages[0]["entry"]:
        raise boot.RefusalError("fixed boot selected entry must start the package observation order")
    placements = [package_artifacts.place(package_artifacts.load(root / raw["store"], item["artifact"]),
                                         item["base"]) for item in packages]
    memory = _memory(configuration)
    package_artifacts.validate_memory(placements, memory)
    htif = [section for item in placements for section in item.sections
            if section.addr <= tohost and tohost + boot.HTIF_BYTES <= section.addr + len(section.data)
            and section.writable and not section.executable]
    if len(htif) != 1:
        raise boot.RefusalError("fixed boot tohost must be a complete writable initializer word")
    if recipe.path.read_bytes() != recipe.snapshot:
        raise boot.RefusalError("fixed boot observation recipe changed during binding")
    if (root / raw["configuration"]).read_bytes() != configuration:
        raise boot.RefusalError("fixed boot configuration changed during binding")
    return binding


def _protected_inputs(root: Path, recipe: Recipe, simulator: Path,
                      binding: dict[str, object]) -> list[Path]:
    raw = recipe.document
    protected = [recipe.path, simulator, *(root / raw[key] for key in
                  ("composition", "image", "configuration"))]
    store = (root / raw["store"]).resolve()
    for item in cast("list[dict[str, Any]]", binding["packages"]):
        artifact = package_artifacts.load(store, item["artifact"])
        protected.append(store / "manifests" / f"{artifact.identity}.json")
        protected.extend(store / "objects" / f"{identity}.bin" for identity, _ in artifact.objects)
    return protected


def _outputs(protected: list[Path], store: Path, out: Path) -> None:
    for name in ("console.log", "trace.log", "events.log", "run.json"):
        path = out / name
        if path.resolve().is_relative_to(store):
            raise boot.RefusalError("fixed boot outputs cannot replace stored package objects")
        for source in protected:
            if (path.resolve() == source.resolve()
                    or (path.exists() and source.exists() and path.samefile(source))):
                raise boot.RefusalError("fixed boot output aliases a consumed input")


def run(root: Path, recipe: Recipe, out: Path, simulator: Path, *, timeout: float,
        refresh: bool = False, keep_trace: bool = False) -> dict[str, object]:
    """Validate, observe and rebind existing bytes; a clean replay supplies no admission."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise boot.RecipeError("fixed boot timeout must be positive and finite")
    raw = recipe.document
    configuration = (root / raw["configuration"]).read_bytes()
    binding = _bindings(root, recipe, configuration)
    protected = _protected_inputs(root, recipe, simulator, binding)
    store = (root / raw["store"]).resolve()
    _outputs(protected, store, out)
    simulator_sha = boot.digest_file(simulator)
    out.mkdir(parents=True, exist_ok=True)
    entries = {int(item["entry"]): str(item["package_id"])
               for item in cast("list[dict[str, Any]]", binding["packages"])}
    record: dict[str, object] = {"members": [{"id": name, "entry": hex(entry)}
                                           for entry, name in entries.items()]}
    argv = [str(simulator), "--config", str(root / raw["configuration"]), "--trace-commit",
            "--terminal-log", str(out / "console.log"), "--inst-limit", str(raw["inst_limit"]),
            str(root / raw["image"])]
    observation = boot.boot_image(argv, out / "console.log", entries, int(raw["tohost"], 16),
                                  timeout, out / "trace.log" if keep_trace else None)
    findings = boot.run_findings(observation, record)
    try:
        if _bindings(root, recipe, configuration) != binding:
            findings.append("fixed boot composition binding changed during the run")
        if boot.digest_file(simulator) != simulator_sha:
            findings.append("fixed boot simulator changed during the run")
    except (boot.RecipeError, boot.RefusalError, package_artifacts.PackageError, OSError) as error:
        findings.append(f"fixed boot final binding: {error}")
    _outputs(protected, store, out)
    image_sha = cast("dict[str, str]", binding["image"])["sha256"]
    expected = boot.expected_block(observation, image_sha)
    refreshed = False
    if refresh:
        if findings:
            findings.append("--refresh refused: expected digests require a clean run and unchanged inputs")
        else:
            updated = {**raw, "expected": expected}
            with atomic_path(recipe.path) as pending:
                pending.write_bytes(package_artifacts.canonical(updated))
            refreshed = True
    else:
        findings += boot.against_expected(observation, image_sha, recipe.expected)
    result: dict[str, object] = {
        "schema_version": 1, "scope": SCOPE, "production_admission": False,
        "final_target_acceptance": False, "roster_identity": None,
        "roster_identity_withheld": "fixed package observations do not establish the accepted real roster",
        "observation_recipe_sha256": package_artifacts.digest(recipe.snapshot),
        "configuration_sha256": package_artifacts.digest(configuration),
        "composition": binding, "simulator_sha256": simulator_sha, **expected,
        "returncode": observation.returncode, "timed_out": observation.timed_out,
        "wall_seconds": round(observation.wall_seconds, 3),
        "emulator_verdict": observation.projection.verdict, "htif_exit": observation.projection.htif_exit,
        "records": observation.projection.records, "findings": findings, "refreshed": refreshed}
    (out / "events.log").write_bytes(observation.projection.event_log())
    with atomic_path(out / "run.json") as pending:
        pending.write_bytes(package_artifacts.canonical(result))
    return result
