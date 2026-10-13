# SPDX-License-Identifier: Apache-2.0
"""Projection publication preserves consumed sources and resolves file aliases."""

import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import _refused, _resolve_descriptors, _sandbox, _write
from vos import boot
from vos import composition as c
from vos.cli import composer as cli

OUTPUT = "out/project"


def _sentinels(root: Path) -> None:
    destination = root / OUTPUT
    destination.mkdir(parents=True, exist_ok=True)
    for name in c.OUTPUTS:
        (destination / name).write_bytes(f"retained earlier {name}\n".encode())


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _regeneration() -> None:
    with _sandbox() as (root, _raw):
        expected = c.projections(root)
        for destination in (OUTPUT, c.GENERATED):
            c.emit(root, c.EXAMPLE, destination)
            ensure({name: (root / destination / name).read_bytes() for name in c.OUTPUTS} == expected,
                   "normal out/ and documented generated publication preserve canonical bytes")
            (root / destination / c.OUTPUTS[-1]).write_bytes(b"stale previous projection")
            c.emit(root, c.EXAMPLE, destination)
            c.check(root, output=destination)


def _input_collision() -> None:
    for name in c.OUTPUTS:
        with _sandbox() as (root, _raw):
            # The last-leaf control also starts without earlier projections;
            # preflight must preserve absence as well as useful prior outputs.
            if name != c.OUTPUTS[-1]:
                _sentinels(root)
            source = f"{OUTPUT}/{name}"
            (root / source).parent.mkdir(parents=True, exist_ok=True)
            (root / source).write_bytes((root / c.EXAMPLE).read_bytes())
            before = _snapshot(root)
            _refused(lambda: c.emit(root, source, OUTPUT), "overwrite a composition source")
            ensure(_snapshot(root) == before,
                   "input collision refuses before replacing any earlier projection")


def _declared_source_collisions() -> None:
    for kind in ("configuration", "member", "producer", "descriptor", "derivation"):
        with _sandbox() as (root, raw):
            _resolve_descriptors(root, raw)
            _sentinels(root)
            member = raw["members"][0]
            if kind == "configuration":
                original = raw["configuration"]
            elif kind == "producer":
                original = raw["producers"][0]["sources"][0]
            elif kind == "descriptor":
                original = member["descriptor"]
            else:
                original = member["sources"][0]
            relative = f"{OUTPUT}/{c.OUTPUTS[-1]}"
            (root / relative).write_bytes((root / original["path"]).read_bytes())
            ref = c.reference(root, relative)
            if kind == "configuration":
                raw["configuration"] = ref
            elif kind == "producer":
                raw["producers"][0]["sources"][0] = ref
            elif kind == "descriptor":
                member["descriptor"] = ref
            elif kind == "derivation":
                member["derivation"]["source"] = ref
            else:
                member["sources"][0] = ref
            _write(root, raw)
            before = _snapshot(root)
            _refused(lambda: c.emit(root, c.EXAMPLE, OUTPUT), "overwrite a composition source")
            ensure(_snapshot(root) == before, f"bound {kind} source and earlier projections survive refusal")


def _hardlink_collisions() -> None:
    for relative in (c.EXAMPLE, boot.CONTRACT, *c.PRODUCERS):
        with _sandbox() as (root, _raw):
            _sentinels(root)
            alias = root / OUTPUT / c.OUTPUTS[-1]
            alias.unlink()
            os.link(root / relative, alias)
            before = _snapshot(root)
            _refused(lambda: c.emit(root, c.EXAMPLE, OUTPUT), "overwrite a composition source")
            ensure(_snapshot(root) == before, f"hardlinked consumed source {relative} survives refusal")
    with _sandbox() as (root, _raw):
        _sentinels(root)
        alias = root / OUTPUT / c.OUTPUTS[-1]
        alias.unlink()
        os.link(root / OUTPUT / c.OUTPUTS[0], alias)
        before = _snapshot(root)
        _refused(lambda: c.emit(root, c.EXAMPLE, OUTPUT), "projection outputs share a file")
        ensure(_snapshot(root) == before, "two projection names cannot publish into one hardlinked file")


def _leaf_symlinks() -> None:
    for location in ("repository", "other-output", "outside-checkout"):
        with _sandbox() as (root, _raw):
            _sentinels(root)
            target = {"repository": root / "retained-source.bin",
                      "other-output": root / "out/other/retained-source.bin",
                      "outside-checkout": root.parent / f"{root.name}-retained-source.bin"}[location]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"retained source outside selected output directory")
            alias = root / OUTPUT / c.OUTPUTS[-1]
            alias.unlink()
            alias.symlink_to(target)
            before = _snapshot(root)
            try:
                _refused(lambda: c.emit(root, c.EXAMPLE, OUTPUT), "projection output")
                ensure(_snapshot(root) == before, "leaf symlink refuses before replacing earlier projections")
                ensure(target.read_bytes() == b"retained source outside selected output directory",
                       "publication must not write through the escaped leaf")
            finally:
                if not target.is_relative_to(root):
                    target.unlink()


def _cli_refusal() -> None:
    with _sandbox() as (root, _raw):
        _sentinels(root)
        source = f"{OUTPUT}/{c.OUTPUTS[-1]}"
        (root / source).write_bytes((root / c.EXAMPLE).read_bytes())
        before = _snapshot(root)
        output = StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            code = cli.main(["project", source, "--output", OUTPUT])
        ensure(code == 1 and "overwrite a composition source" in output.getvalue(), output.getvalue())
        ensure(_snapshot(root) == before, "CLI names the publication refusal and preserves all prior bytes")


def cases() -> list[Case]:
    return [Case("permitted-regeneration", _regeneration),
            Case("composition-input-collision", _input_collision),
            Case("declared-source-collisions", _declared_source_collisions),
            Case("hardlinked-source-and-output-collisions", _hardlink_collisions),
            Case("cli-publication-refusal", _cli_refusal),
            Case("resolved-leaf-containment", _leaf_symlinks, lane="guest")]
