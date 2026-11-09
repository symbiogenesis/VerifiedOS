# SPDX-License-Identifier: Apache-2.0
"""Catalog-anchored explicit relocation, final drift and unchanged refusals."""

import gzip
import hashlib
import json
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import compiler_relocation as relocation
from vos.cli import compiler_relocation as cli


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode()


@contextmanager
def _fixture() -> Generator[tuple[Path, str]]:
    with tempfile.TemporaryDirectory(prefix="vos-compiler-relocation-") as temporary:
        root = Path(temporary).resolve()
        files = {"/historical/helper.py": b"# sealed helper\n", "/historical/switch.lock": b"sealed lock\n"}
        mapped = {}
        for historical, data in files.items():
            current = root / Path(historical).name
            current.write_bytes(data)
            mapped[historical] = str(current)
        seal = _bytes({"schema": "verifiedos-clean-compile-seal/2", "original": "/native/compiler-1",
                       "helpers": {"/historical/helper.py": hashlib.sha256(files["/historical/helper.py"]).hexdigest()},
                       "lock": "/historical/switch.lock",
                       "lock_sha256": hashlib.sha256(files["/historical/switch.lock"]).hexdigest()})
        (root / "seal.json").write_bytes(seal)
        (root / "seal.json.gz").write_bytes(gzip.compress(seal))
        catalog = _bytes({"schema": relocation.CATALOG, "candidates": [{"name": "candidate-1",
                         "native_root": "/native/compiler-1", "source_revision": "a" * 40,
                         "files": {"compile-seal.json": {"sha256": hashlib.sha256(seal).hexdigest(), "bytes": len(seal)}}}]})
        (root / "catalog.json").write_bytes(catalog)
        (root / "mapping.json").write_bytes(_bytes({"schema": relocation.PROTOCOL,
                                                  "candidate": "candidate-1", "files": mapped}))
        yield root, hashlib.sha256(catalog).hexdigest()


def _verify(root: Path, trusted: str, *, zipped: bool = False) -> dict[str, Any]:
    return relocation.verify(root / "catalog.json", trusted, "candidate-1",
                             root / ("seal.json.gz" if zipped else "seal.json"),
                             root / "mapping.json", output=root / "out/report.json", output_root=root / "out")


def _refused(operation: Callable[[], object], phrase: str) -> None:
    try:
        operation()
    except (ValueError, TypeError, OSError) as error:
        ensure(phrase in str(error), f"unexpected refusal: {error}")
    else:
        raise AssertionError("substituted relocation was accepted")


def _roundtrip() -> None:
    with _fixture() as (root, trusted):
        before = {path: path.read_bytes() for path in root.iterdir() if path.is_file()}
        report = _verify(root, trusted)
        ensure(report["status"] == "verified" and len(report["files"]) == 2, "complete exact mapping")
        for field in ("compilation_reuse", "kernel_qualification", "target_acceptance", "checker_resume"):
            ensure(report[field] is False, f"relocation supplied {field}")
        ensure(json.loads((root / "out/report.json").read_bytes()) == report, "retained report differs")
        zipped = _verify(root, trusted, zipped=True)
        ensure(zipped["files"] == report["files"] and zipped["seal"]["sha256"] == report["seal"]["sha256"],
               "lossless seal representation changed historical identities")
        ensure(all(path.read_bytes() == data for path, data in before.items()), "verification altered historical inputs")


def _substitutions() -> None:
    for name, phrase in (("catalog.json", "catalog differs"), ("seal.json", "compilation seal differs"),
                         ("helper.py", "restored helper/lock bytes"), ("switch.lock", "restored helper/lock bytes")):
        with _fixture() as (root, trusted):
            _verify(root, trusted)
            prior = (root / "out/report.json").read_bytes()
            (root / name).write_bytes((root / name).read_bytes() + b"substitution")
            _refused(lambda: _verify(root, trusted), phrase)
            ensure((root / "out/report.json").read_bytes() == prior, "refusal replaced useful output")


def _mapping_shapes() -> None:
    for mode in ("missing", "extra", "candidate", "relative", "parent", "field", "alias"):
        with _fixture() as (root, trusted):
            path = root / "mapping.json"
            raw = json.loads(path.read_bytes())
            phrase = "mapping must cover exactly"
            if mode == "missing":
                del raw["files"]["/historical/switch.lock"]
            elif mode == "extra":
                raw["files"]["/historical/extra.py"] = str(root / "helper.py")
            elif mode == "candidate":
                raw["candidate"] = "candidate-2"
            elif mode == "field":
                raw["accepted"] = True
            elif mode == "relative":
                raw["files"]["/historical/helper.py"] = "helper.py"
                phrase = "absolute without parent traversal"
            elif mode == "parent":
                raw["files"]["/historical/helper.py"] = str(root / "sub/../helper.py")
                phrase = "absolute without parent traversal"
            else:
                raw["files"]["/historical/helper.py"] = str(root / "switch.lock")
                phrase = "restored helper/lock bytes"
            path.write_bytes(_bytes(raw))
            _refused(lambda: _verify(root, trusted), phrase)


def _malformed_and_anchor() -> None:
    for data in (b'[]', b'{"schema":1,"schema":2}', b'{"schema":NaN}', b'not JSON',
                 b'{"nested":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
        with _fixture() as (root, trusted):
            (root / "mapping.json").write_bytes(data)
            _refused(lambda: _verify(root, trusted), "")
    with _fixture() as (root, trusted):
        raw = json.loads((root / "catalog.json").read_bytes())
        raw["candidates"][0]["native_root"] = "/substituted/root"
        data = _bytes(raw)
        (root / "catalog.json").write_bytes(data)
        _refused(lambda: _verify(root, trusted), "catalog differs")
        _refused(lambda: _verify(root, hashlib.sha256(data).hexdigest()), "compilation seal origin")
    with _fixture() as (root, trusted):
        _refused(lambda: relocation.verify(root / "catalog.json", trusted, "candidate-2", root / "seal.json",
                                           root / "mapping.json"), "missing or duplicate selected candidate")
    for mode in ("truncated", "corrupt"):
        with _fixture() as (root, trusted):
            path = root / "seal.json.gz"
            data = path.read_bytes()
            path.write_bytes(data[:-1] if mode == "truncated" else data[:-8] + b'corrupt!')
            _refused(lambda: _verify(root, trusted, zipped=True), "malformed compressed compilation seal")


def _drift() -> None:
    with _fixture() as (root, trusted):
        _verify(root, trusted)
        prior = (root / "out/report.json").read_bytes()
        original = relocation._recheck
        def change(snapshots: dict[Path, bytes]) -> None:
            (root / "helper.py").write_bytes(b"changed after verification")
            original(snapshots)
        with patch.object(relocation, "_recheck", side_effect=change):
            _refused(lambda: _verify(root, trusted), "input changed")
        ensure((root / "out/report.json").read_bytes() == prior, "late refusal replaced previous output")


def _output_and_cli() -> None:
    with _fixture() as (root, trusted):
        _refused(lambda: relocation.verify(root / "catalog.json", trusted, "candidate-1", root / "seal.json",
                                           root / "mapping.json", output=root / "helper.py", output_root=root),
                 "aliases a consumed input")
        _refused(lambda: relocation.verify(root / "catalog.json", trusted, "candidate-1", root / "seal.json",
                                           root / "mapping.json", output=root / "elsewhere/report", output_root=root / "out"),
                 "escapes its declared root")
        args = ["--catalog", str(root / "catalog.json"), "--catalog-sha256", trusted, "--candidate", "candidate-1",
                "--seal", str(root / "seal.json.gz"), "--mapping", str(root / "mapping.json"),
                "--output", str(root / "out/cli.json")]
        output = StringIO()
        with patch.object(cli, "find_root", return_value=root), redirect_stdout(output):
            ensure(cli.main(args) == 0, "CLI refused exact mapping")
        ensure(json.loads(output.getvalue())["compilation_reuse"] is False, "CLI authorized reuse")
        (root / "helper.py").write_bytes(b"wrong")
        with redirect_stderr(StringIO()):
            ensure(cli.main(args) == 1, "CLI accepted substituted helper")


def cases() -> list[Case]:
    return [Case("explicit helper and lock connection preserves history and no reuse", _roundtrip),
            Case("catalog seal helper and lock substitutions preserve prior report", _substitutions),
            Case("closed complete mapping and absolute paths refuse substitutions", _mapping_shapes),
            Case("malformed duplicate JSON and trusted catalog origin binding", _malformed_and_anchor),
            Case("final mapped input drift refuses before publication", _drift),
            Case("output containment alias refusal and public CLI", _output_and_cli)]
