# SPDX-License-Identifier: Apache-2.0
"""Wire framing and optional-install identities without requiring native packages."""

import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import env, saillsp


def _frames() -> None:
    message = {"jsonrpc": "2.0", "id": 7, "result": "lambda λ and emoji 🐚"}
    wire = saillsp.frame(message)
    header, body = wire.split(b"\r\n\r\n", 1)
    ensure(int(header.split(b": ")[1]) == len(body), "LSP lengths count encoded bytes")
    buffer = bytearray()
    for value in wire[:-1]:
        buffer.append(value)
        ensure(saillsp.decode_frame(buffer) is None, "partial frames must remain pending")
    buffer.extend(wire[-1:])
    buffer.extend(saillsp.frame({"jsonrpc": "2.0", "id": 8, "result": None}))
    ensure(saillsp.decode_frame(buffer) == message, "fragmented frames must reconstruct")
    ensure(saillsp.decode_frame(buffer) == {"jsonrpc": "2.0", "id": 8, "result": None},
           "coalesced frames must retain their boundaries")
    ensure(not buffer, "the decoder must consume exactly two frames")


def _bad_frames() -> None:
    for wire in (b"Content-Length: -1\r\n\r\n", b"Content-Length: 8388609\r\n\r\n",
                 b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
                 b"banner\r\nContent-Length: 2\r\n\r\n{}",
                 b"Content-Length: 2\r\n\r\n{}", b"x" * 8193):
        try:
            saillsp.decode_frame(bytearray(wire))
        except ValueError:
            continue
        raise AssertionError(f"invalid wire accepted: {wire[:60]!r}")


def _environment(root: Path) -> env.Environment:
    return env.Environment(root=root, model=root / "model", build_root=root / "native",
                           log_root=root / "logs", lane="", cpus=1, mem_available_mb=1024,
                           jobs=1, test_jobs=1)


def _provenance() -> None:
    files = {saillsp.LOCK: "{}", "tools/opam/sail.lock": 'installed: ["ocaml.5.4.1"]',
             "tools/vos/saillsp.py": "recipe", "tools/sail-lsp/dependency-refresh.patch": "patch"}
    with sandbox_tree(files) as root:
        environment = _environment(root)
        ensure(saillsp.status(environment)["installed"] is False, "absence must be explicit")
        location = saillsp.home(environment)
        binary = location / "prefix/bin/sail_lsp"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"pinned executable")
        receipt = {"lock_sha256": saillsp.lock_identity(root), "elapsed_seconds": 1.0,
                   "log": "build.log", "artifacts": {"prefix/bin/sail_lsp": saillsp.sha256(binary)}}
        (location / "installation.json").write_text(json.dumps(receipt), encoding="utf-8")
        result = saillsp.status(environment)
        ensure(result["installed"] is True, "matching artifacts must be usable")
        schema = json.loads((TOOLS / "sail-lsp.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(result)
        binary.write_bytes(b"changed executable")
        try:
            saillsp.status(environment)
        except ValueError as exc:
            ensure("artifact changed" in str(exc), "artifact mismatch needs a concrete error")
        else:
            raise AssertionError("modified native executable accepted")
        (root / saillsp.LOCK).write_text('{"changed":true}', encoding="utf-8")
        try:
            saillsp.status(environment)
        except ValueError as exc:
            ensure("stale" in str(exc), "changed recipe must invalidate installation")
        else:
            raise AssertionError("stale optional installation accepted")


def _archive_confinement() -> None:
    with sandbox_tree({"marker": "unchanged"}) as root:
        directory = root / "sources"
        directory.mkdir()
        archive = directory / "test.archive"
        with tarfile.open(archive, "w") as output:
            member = tarfile.TarInfo("../marker")
            member.size = 7
            output.addfile(member, io.BytesIO(b"changed"))
        spec = {"name": "test", "directory": "test", "sha256": saillsp.sha256(archive)}
        try:
            saillsp._source(spec, directory)
        except tarfile.FilterError:
            pass
        else:
            raise AssertionError("archive escaped its source directory")
        ensure((root / "marker").read_text() == "unchanged", "rejected source must not overwrite outside its directory")


def _tar(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as output:
        for name, data in members.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


def _superseded_archive() -> None:
    with sandbox_tree({"marker": "unchanged"}) as root:
        directory = root / "sources"
        directory.mkdir()
        archive = directory / "test.archive"
        archive.write_bytes(_tar({"test-1/old.ml": b"earlier pin"}))
        stale = directory / "test-1/old.ml"
        stale.parent.mkdir()
        stale.write_bytes(b"earlier pin")
        current = _tar({"test-1/new.ml": b"current pin"})
        spec = {"name": "test", "directory": "test-1", "url": "https://example.invalid/test.tbz",
                "sha256": hashlib.sha256(current).hexdigest()}
        with patch.object(saillsp.urllib.request, "urlopen", return_value=io.BytesIO(current)) as fetch:
            target = saillsp._source(spec, directory)
        ensure(fetch.call_count == 1, "an archive whose digest differs from the tracked pin must be fetched again")
        ensure(archive.read_bytes() == current and not archive.with_name("test.archive.part").exists(),
               "the verified download must replace the superseded archive")
        ensure((target / "new.ml").read_bytes() == b"current pin" and not (target / "old.ml").exists(),
               "no member of the superseded archive may survive into the build tree")
        with patch.object(saillsp.urllib.request, "urlopen") as fetch:
            saillsp._source(spec, directory)
        ensure(not fetch.called, "an archive matching its pin must be reused without a download")
        stale_bytes = _tar({"test-1/old.ml": b"earlier pin"})
        archive.write_bytes(stale_bytes)
        with patch.object(saillsp.urllib.request, "urlopen", return_value=io.BytesIO(b"not the pin")):
            try:
                saillsp._source(spec, directory)
            except ValueError as exc:
                ensure("digest mismatch" in str(exc), "a mismatched download needs a concrete error")
            else:
                raise AssertionError("a download differing from its pin was accepted")
        ensure(archive.read_bytes() == stale_bytes and not archive.with_name("test.archive.part").exists(),
               "a mismatched download must neither replace the archive nor remain as a partial file")
        for escaped in ("..", "../outside", ""):
            try:
                saillsp._source({**spec, "directory": escaped}, directory)
            except ValueError:
                continue
            raise AssertionError(f"source directory {escaped!r} escaped its lane directory")
        ensure((root / "marker").read_text() == "unchanged", "a refused directory must not be removed")


def _base_lock() -> None:
    files = {"tools/opam/sail.lock": 'installed: ["ocaml.5.4.1" "dune.3.24.2" "sail.0.20.3"]',
             saillsp.LOCK: json.dumps({"sources": [{"name": "lsp", "version": "1.27.0"},
                                                   {"name": "sail", "version": "0.20.3"}]})}
    listing = "dune 3.24.2\nocaml 5.4.1\nsail 0.20.3\n"
    with sandbox_tree(files) as root:
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, listing)):
            ensure(saillsp._base_inventory(root) == ["dune.3.24.2", "ocaml.5.4.1", "sail.0.20.3"],
                   "the complete base lock must match")
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, listing.replace("5.4.1", "5.5.0"))):
            try:
                saillsp._base_inventory(root)
            except ValueError:
                pass
            else:
                raise AssertionError("compiler drift was accepted")
        (root / saillsp.LOCK).write_text(files[saillsp.LOCK].replace("0.20.3", "0.20.4"), encoding="utf-8")
        with patch.object(saillsp.subprocess, "run") as run:
            try:
                saillsp._base_inventory(root)
            except ValueError as exc:
                ensure("not the Sail release" in str(exc), "a foreign Sail pin needs a concrete error")
            else:
                raise AssertionError("a Sail archive pin the locked compiler does not install was accepted")
            ensure(not run.called, "the Sail pin must be refused before the switch is inspected")


def _tool_sail_pins_agree() -> None:
    lsp = next(spec for spec in json.loads((TOOLS / "sail-lsp/sources.lock.json").read_text(encoding="utf-8"))
               ["sources"] if spec["name"] == "sail")
    isla = json.loads((TOOLS / "sail-isla/lock.json").read_text(encoding="utf-8"))["sail"]
    fields = ("version", "revision", "url", "sha256", "directory")
    ensure({key: lsp[key] for key in fields} == {key: isla[key] for key in fields},
           "the LSP and Isla tools must pin one Sail release archive")
    locked = (TOOLS / "opam/sail.lock").read_text(encoding="utf-8")
    block = re.search(r"installed:\s*\[(.*?)\]", locked, re.DOTALL)
    ensure(block is not None and f'"sail.{lsp["version"]}"' in block[1],
           "the tools' Sail archive must be the release the locked compiler installs")


def cases() -> list[Case]:
    return [Case("standard-framing-fragments-and-coalescing", _frames),
            Case("malformed-and-unbounded-frames", _bad_frames),
            Case("optional-installation-provenance", _provenance),
            Case("archive-extraction-confinement", _archive_confinement),
            Case("superseded-archive-fetched-verified-and-replaced", _superseded_archive),
            Case("locked-base-dependency-closure", _base_lock),
            Case("tool-sail-pins-are-the-locked-release", _tool_sail_pins_agree)]
