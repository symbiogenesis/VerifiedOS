# SPDX-License-Identifier: Apache-2.0
"""Wire framing and optional-install identities without requiring native packages."""

import io
import json
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


def _base_lock() -> None:
    with sandbox_tree({"tools/opam/sail.lock": 'installed: ["ocaml.5.4.1" "dune.3.24.2"]'}) as root:
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "dune 3.24.2\nocaml 5.4.1\n")):
            ensure(saillsp._base_inventory(root) == ["dune.3.24.2", "ocaml.5.4.1"], "the complete base lock must match")
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "dune 3.24.2\nocaml 5.5.0\n")):
            try:
                saillsp._base_inventory(root)
            except ValueError:
                pass
            else:
                raise AssertionError("compiler drift was accepted")


def cases() -> list[Case]:
    return [Case("standard-framing-fragments-and-coalescing", _frames),
            Case("malformed-and-unbounded-frames", _bad_frames),
            Case("optional-installation-provenance", _provenance),
            Case("archive-extraction-confinement", _archive_confinement),
            Case("locked-base-dependency-closure", _base_lock)]
