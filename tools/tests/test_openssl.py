# SPDX-License-Identifier: Apache-2.0
"""Offline controls for the external oracle's source/build and loaded-library boundary."""

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import openssl


def _fixture(prefix: Path) -> None:
    (prefix / openssl.MARKER).write_text("1\n", encoding="utf-8")
    names = (*openssl.ARTIFACTS, "source/LICENSE.txt", "configure.log", "build.log", "install.log")
    for name in names:
        path = prefix / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    record = {"schema": openssl.SCHEMA, "passed": True, "source": openssl.pin(),
              "prefix": str(prefix), "steps": [{"name": name, "exit": 0}
                                                for name in ("configure", "build", "install")],
              "bindings": {name: openssl._sha(prefix / name) for name in names}}
    (prefix / openssl.MANIFEST).write_text(json.dumps(record), encoding="utf-8")


def _probe(prefix: Path, *, version: str | None = None,
           foreign: bool = False) -> Callable[[list[str], Path], str]:
    def run(argv: list[str], _: Path) -> str:
        if argv[0] != "ldd":
            return version or f"OpenSSL {openssl.VERSION} fixture (Library: OpenSSL {openssl.VERSION} fixture)"
        crypto = prefix.parent / "foreign.so" if foreign else prefix / "lib/libcrypto.so.3"
        return f"libcrypto.so.3 => {crypto}\nlibssl.so.3 => {prefix / 'lib/libssl.so.3'}\n"
    return run


def _refuses(action: Callable[[], object], message: str) -> None:
    try:
        action()
    except ValueError as error:
        ensure(message in str(error), f"wrong refusal: {error}")
        return
    raise AssertionError("oracle identity accepted a bad control")


def selected_and_loaded_library() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-openssl-test-") as name:
        prefix = Path(name).resolve()
        with (patch.dict(os.environ, openssl.environment(prefix)),
              patch.object(openssl, "LICENSE_SHA256",
                           hashlib.sha256(b"source/LICENSE.txt").hexdigest())):
            _fixture(prefix)
            with patch.object(openssl, "_run", side_effect=_probe(prefix)):
                found = openssl.identity()
                ensure(len(found["binaries"]) == 3 and found["source"] == openssl.pin(),
                       "source-built identity lost its selected source or actual binaries")
                ensure(openssl.executable() == prefix / "bin/openssl", "selection used PATH")
            with patch.object(openssl, "_run", side_effect=_probe(prefix, foreign=True)):
                _refuses(openssl.identity, "foreign OpenSSL loaded library")
            with patch.object(openssl, "_run", side_effect=_probe(prefix, version="OpenSSL 3.5.5 old")):
                _refuses(openssl.identity, "not the selected release")


def stale_build_and_configuration() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-openssl-test-") as name:
        prefix = Path(name).resolve()
        with (patch.dict(os.environ, openssl.environment(prefix)),
              patch.object(openssl, "LICENSE_SHA256",
                           hashlib.sha256(b"source/LICENSE.txt").hexdigest()),
              patch.object(openssl, "_run", side_effect=_probe(prefix))):
            _fixture(prefix)
            (prefix / "lib/libcrypto.so.3").write_bytes(b"changed after build")
            _refuses(openssl.identity, "stale OpenSSL build identity")
            _fixture(prefix)
            manifest = prefix / openssl.MANIFEST
            record = json.loads(manifest.read_text())
            record["steps"][1]["exit"] = 1
            manifest.write_text(json.dumps(record), encoding="utf-8")
            _refuses(openssl.identity, "did not complete")
            _fixture(prefix)
            record = json.loads(manifest.read_text())
            record["source"]["version"] = "3.5.5"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            _refuses(openssl.identity, "not the selected release")
            _fixture(prefix)
            with patch.dict(os.environ, {"OPENSSL_CONF": str(prefix / "foreign.cnf")}):
                _refuses(openssl.identity, "foreign OpenSSL configuration")


def explicit_selection_and_owned_installation() -> None:
    with patch.dict(os.environ, {"VOS_OPENSSL_ROOT": ""}):
        _refuses(openssl.executable, "set VOS_OPENSSL_ROOT")
    with tempfile.TemporaryDirectory(prefix="vos-openssl-test-") as name:
        prefix = Path(name).resolve()
        marker = prefix / "someone-elses-file"
        marker.write_text("preserve", encoding="utf-8")
        with patch.object(openssl.sys, "platform", "linux"):
            _refuses(lambda: openssl.install(prefix, 2), "nonempty unowned")
        ensure(marker.read_text() == "preserve", "bootstrap overwrote an unrelated installation")


def cases() -> list[Case]:
    return [Case("selected source and actual loaded libraries", selected_and_loaded_library),
            Case("stale source build and foreign configuration refuse", stale_build_and_configuration),
            Case("explicit selection never replaces an unowned prefix", explicit_selection_and_owned_installation)]
