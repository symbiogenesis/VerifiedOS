# SPDX-License-Identifier: Apache-2.0
"""Explicit status-only relocation framing preserves independent historical identities."""

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_compiler_build import _session
from vos import compiler_build as cb
from vos import compiler_relocation as cr


@contextmanager
def fixture() -> Generator[tuple[cb.Settings, Path, dict[str, Any]]]:
    with _session() as (settings, checkout):
        root = settings.source.parent
        original = settings.source / "compiled"
        receipt = original / "compiler/build-result.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"pending":true}')
        helper = root / "original-helper.py"
        helper.write_bytes(b"historical helper")
        seal = {"schema": "verifiedos-clean-compile-seal/2", "original": str(original),
                "helpers": {"/historical/helper.py": cb.digest(helper)},
                "lock": "/historical/lock", "lock_sha256": cb.digest(settings.lock)}
        seal_path = original / "compile-seal.json"
        seal_path.write_text(json.dumps(seal))
        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({"schema": cr.CATALOG, "candidates": [{
            "name": "first", "native_root": str(original), "source_revision": settings.source_revision,
            "files": {name: {"sha256": cb.digest(path), "bytes": path.stat().st_size}
                      for name, path in (("compile-seal.json", seal_path),
                                         ("compiler/build-result.json", receipt))}}]}))
        mapping = root / "mapping.json"
        mapping.write_text(json.dumps({"schema": cr.PROTOCOL, "candidate": "first",
                                      "files": {"/historical/helper.py": str(helper),
                                                "/historical/lock": str(settings.lock)}}))
        connection = root / "connection.json"
        connection.write_text(json.dumps({"schema": cr.CONNECTION, "catalog": str(catalog),
                                         "catalog_sha256": cb.digest(catalog), "candidate": "first",
                                         "seal": str(seal_path), "mapping": str(mapping)}))
        selected = replace(settings, relocation=connection, reuse_from=receipt)
        expected = cr.connection(connection, settings.source_revision, receipt, settings.lock)
        (root / "expected.json").write_text(json.dumps(expected))
        driver = settings.driver_root / "build.py"
        script = driver.read_text().replace("p(r['response_json']).write_text(json.dumps(result))",
            "if 'relocation' in r: result['relocation'] = json.loads(p(r['relocation']).with_name('expected.json').read_text())\n"
            "p(r['response_json']).write_text(json.dumps(result))")
        driver.write_text(script)
        manifest = cb.read_json(settings.driver_manifest)
        manifest["files"]["build.py"] = cb.digest(driver)
        settings.driver_manifest.write_text(json.dumps(manifest))
        yield selected, checkout, expected


def refused(operation: Callable[[], object]) -> None:
    try:
        operation()
    except (OSError, ValueError, TypeError):
        return
    raise AssertionError("invalid relocated status was accepted")


def accepted() -> None:
    with fixture() as (settings, checkout, expected):
        if settings.reuse_from is None:
            raise AssertionError("fixture explicit candidate")
        before = settings.reuse_from.read_bytes()
        result = cb.run(settings, checkout, status=True)
        ensure(result["relocation"] == expected and result["phases"]["compile"]["action"] == "reused",
               "status did not bind independent relocated compilation")
        ensure(all(result["phases"][key]["action"] == "not_run" for key in ("queries", "kernel", "classification")),
               "relocated status executed qualification")
        ensure(settings.reuse_from.read_bytes() == before and not settings.out.exists() and not settings.cache.exists(),
               "read-only status changed historical receipt or published outputs")


def operation_refusals() -> None:
    with fixture() as (settings, checkout, _):
        with patch.object(cb.subprocess, "run", side_effect=AssertionError("invalid operation launched driver")):
            for candidate, status, prime in ((settings, False, False), (settings, False, True),
                    (replace(settings, reuse_from=None), True, False),
                    (replace(settings, fresh=True), True, False), (replace(settings, profile=True), True, False)):
                refused(lambda candidate=candidate, status=status, prime=prime:
                        cb.run(candidate, checkout, status=status, prime=prime))
        ensure(not settings.out.exists() and not settings.cache.exists(), "refusal published outputs")


def substitutions() -> None:
    for name in ("catalog.json", "mapping.json", "original-helper.py", "lock", "connection.json"):
        with fixture() as (settings, checkout, _):
            path = settings.source.parent / name
            path.write_bytes(path.read_bytes() + b"changed")
            with patch.object(cb.subprocess, "run", side_effect=AssertionError("changed input launched driver")):
                refused(lambda: cb.run(settings, checkout, status=True))
    for mode in ("extra", "missing", "candidate", "revision", "receipt", "lock"):
        with fixture() as (settings, checkout, _):
            if settings.relocation is None:
                raise AssertionError("fixture connection")
            raw = cb.read_json(settings.relocation)
            attempted = settings
            if mode == "extra":
                raw["accepted"] = True
            elif mode == "missing":
                del raw["mapping"]
            elif mode == "candidate":
                raw["candidate"] = "other"
            elif mode == "revision":
                attempted = replace(settings, source_revision="b" * 40)
            elif mode == "receipt":
                attempted = replace(settings, reuse_from=settings.configuration)
            else:
                attempted = replace(settings, lock=settings.configuration)
            settings.relocation.write_text(json.dumps(raw))
            refused(lambda attempted=attempted: cb.run(attempted, checkout, status=True))


def _disagreement(mode: str) -> None:
    with fixture() as (settings, checkout, _):
        original = cb.read_json
        def read(path: Path) -> dict[str, Any]:
            raw = original(path)
            if path.name == "response.json":
                if mode == "missing":
                    raw.pop("relocation", None)
                elif mode == "altered":
                    raw["relocation"]["candidate"] = "other"
                elif mode == "late-drift":
                    (settings.source.parent / "original-helper.py").write_bytes(b"late changed bytes")
                else:
                    raw["effective_policy"] = "complete-reuse"
            return raw
        with patch.object(cb, "read_json", side_effect=read):
            refused(lambda: cb.run(settings, checkout, status=True))
        ensure(not settings.out.exists() and not settings.cache.exists(), "disagreement published output")


def private_disagreement() -> None:
    for mode in ("missing", "altered", "late-drift", "complete-claim"):
        _disagreement(mode)


def overlap() -> None:
    with fixture() as (settings, checkout, _):
        if settings.relocation is None:
            raise AssertionError("fixture connection")
        attempted = replace(settings, out=settings.relocation)
        with patch.object(cb.subprocess, "run", side_effect=AssertionError("overlap launched driver")):
            refused(lambda: cb.run(attempted, checkout, status=True))


def cases() -> list[Case]:
    return [Case("explicit relocated compilation status preserves history", accepted),
            Case("relocation refuses execution implicit lookup and cold requests", operation_refusals),
            Case("relocation connection and original identity substitutions refuse", substitutions),
            Case("independent private connection and final input drift are decisive", private_disagreement),
            Case("relocation input output overlap refuses before launch", overlap)]
