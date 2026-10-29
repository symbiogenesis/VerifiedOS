# SPDX-License-Identifier: Apache-2.0
"""Real retained boot-product inspection and historical composition binding."""

import json
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import ROOT, _sandbox
from vos import boot_chain, composer
from vos import composition as c
from vos import composition_staged as staged
from vos.cli import composer as cli

OUTPUT = "out/historical-composition.json"


@contextmanager
def _staged_sandbox() -> Generator[Path]:
    with _sandbox() as (root, _raw):
        shutil.copytree(ROOT / "firmware", root / "firmware", dirs_exist_ok=True)
        for relative in staged.INSPECTORS:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        yield root


def _refusal(root: Path, phrase: str) -> None:
    target = root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"useful prior candidate")
    try:
        staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
    except (OSError, ValueError) as error:
        ensure(phrase in str(error), str(error))
    else:
        raise AssertionError("invalid retained producer was accepted")
    ensure(target.read_bytes() == b"useful prior candidate", "refusal preserves useful prior candidate")


def _real_products() -> None:
    with _staged_sandbox() as root:
        originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        result = staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
        candidate = c.load(root, OUTPUT)
        products = result["products"]
        ensure(products == {
            "rot-firmware": [c.reference(root, "firmware/chain/target/rom.s"),
                             c.reference(root, "firmware/chain/target/runtime.s")],
            "mmode-firmware": [c.reference(root, "firmware/chain/target/mmode.s")]},
            "independent actual compiled product identities")
        ensure(result["final_target_acceptance"] is False and result["production_admission"] is False,
               "historical inspection cannot qualify compiler or generation")
        ensure("historical incomplete" in str(result["compiler_provenance_status"]),
               "actual checked-in compiler lacks current locked provenance")
        selected = {member["id"] for member in candidate["members"]
                    if member["producer"] == "historical-boot-chain"}
        ensure(selected == {"rot-firmware", "mmode-firmware"},
               "storage crypto and other members cannot borrow firmware comparison products")
        members = {member["id"]: member for member in candidate["members"]}
        ensure([ref["path"] for ref in members["rot-firmware"]["sources"]
                if ref["path"].startswith("firmware/chain/target/")]
               == ["firmware/chain/target/rom.s", "firmware/chain/target/runtime.s"],
               "candidate binds the normal RoT units to their actual member, excluding watchdog defects")
        ensure([ref["path"] for ref in members["mmode-firmware"]["sources"]
                if ref["path"].startswith("firmware/chain/target/")] == ["firmware/chain/target/mmode.s"],
               "candidate binds the actual M-mode unit to its own member")
        recipe = json.loads(c.projections(root, OUTPUT)["recipe-members.json"])
        ensure(all(member["status"] != "executable" for member in recipe["payload"]["members"]),
               "partial roster status remains owned by its contract")
        ensure(all(member["entry"] is None and member["placement"] is None
                   and member["derivation"]["source"] is None
                   for member in recipe["payload"]["members"]),
               "no target placement or derivation is invented")
        ensure(recipe["production_admission"] is False,
               "existing schema projections retain explicit open admission")
        ensure(all(path.read_bytes() == data for path, data in originals.items()),
               "recorded historical sources, products and manifests are immutable")


def _stale_population() -> None:
    for relative, phrase in (("firmware/chain/target/mmode.s", "differs from its manifest"),
                              ("firmware/crypto/target/mldsa.s", "differs from its manifest"),
                              ("firmware/chain/mmode.c", "stale source binding")):
        with _staged_sandbox() as root:
            path = root / relative
            path.write_bytes(path.read_bytes() + b"\n")
            _refusal(root, phrase)
    with _staged_sandbox() as root:
        (root / boot_chain.MANIFEST).unlink()
        _refusal(root, "manifest.json")


def _predeclared_products() -> None:
    with _staged_sandbox() as root:
        raw = c.load(root)
        members = {member["id"]: member for member in raw["members"]}
        declared = {}
        for member, units in (("rot-firmware", ("runtime", "rom")),
                              ("mmode-firmware", ("mmode",))):
            refs = [c.reference(root, f"firmware/chain/target/{unit}.s") for unit in units]
            members[member]["sources"].extend(refs)
            declared[member] = list(members[member]["sources"])
        (root / c.EXAMPLE).write_bytes(composer.canonical_bytes(raw))
        c.load(root)
        staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
        candidate = c.load(root, OUTPUT)
        for member in candidate["members"]:
            if member["id"] in declared:
                ensure(member["sources"] == declared[member["id"]],
                       "existing valid normal-product declarations stay unique and keep their order")


def _compiler_substitution() -> None:
    with _staged_sandbox() as root:
        manifest = root / boot_chain.MANIFEST
        raw = json.loads(manifest.read_bytes())
        raw["compiler_provenance"]["compiler_sha256"] = "0" * 64
        manifest.write_bytes(composer.canonical_bytes(raw))
        _refusal(root, "compiler compiler_sha256 is not")


def _publication_drift() -> None:
    inspect = boot_chain.staged
    for relative in (boot_chain.MANIFEST, "firmware/chain/mmode.c", c.EXAMPLE):
        with _staged_sandbox() as root:
            def drift(checkout: Path, *, historical: bool = False,
                      changed: str = relative) -> boot_chain.Staged:
                result = inspect(checkout, historical=historical)
                path = checkout / changed
                path.write_bytes(path.read_bytes() + b"\n")
                return result
            with patch.object(boot_chain, "staged", drift):
                _refusal(root, "stale source binding")


def _publication_alias() -> None:
    with _staged_sandbox() as root:
        target = root / OUTPUT
        target.parent.mkdir(parents=True)
        original = root / c.EXAMPLE
        before = original.read_bytes()
        os.link(original, target)
        try:
            staged.bind_boot_chain(root, c.EXAMPLE, OUTPUT)
        except c.CompositionError as error:
            ensure("overwrite an input or product" in str(error), str(error))
        else:
            raise AssertionError("candidate must not overwrite aliased input")
        ensure(original.read_bytes() == before, "input alias refusal preserves original bytes")


def _cli_roundtrip() -> None:
    with _staged_sandbox() as root:
        output = StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            code = cli.main(["bind-staged-boot-chain", c.EXAMPLE, "--output", OUTPUT])
        ensure(code == 0, output.getvalue())
        result = json.loads(output.getvalue())
        ensure(result["producer"] == "historical-boot-chain" and result["final_target_acceptance"] is False,
               "public adapter names historical inspection rather than target qualification")
        ensure(c.load(root, OUTPUT)["graph"] is None, "candidate keeps unresolved handler vocabulary")


def cases() -> list[Case]:
    return [Case("real-retained-boot-products", _real_products),
            Case("predeclared-normal-product-sources", _predeclared_products),
            Case("stale-and-missing-staged-population", _stale_population),
            Case("cross-manifest-compiler-substitution", _compiler_substitution),
            Case("staged-binding-publication-drift", _publication_drift),
            Case("staged-candidate-input-alias", _publication_alias),
            Case("public-staged-binding-roundtrip", _cli_roundtrip)]
