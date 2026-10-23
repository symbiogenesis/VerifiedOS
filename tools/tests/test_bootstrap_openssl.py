# SPDX-License-Identifier: Apache-2.0
"""OpenSSL bootstrap validates export destinations before starting a native build."""

import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ci import bootstrap_openssl as bootstrap
from tests.harness import Case, ensure


def _relative_export_refuses_before_installation() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-openssl-bootstrap-") as directory:
        root = Path(directory).resolve()
        for option in ("--github-env", "--github-path"):
            other = "--github-path" if option == "--github-env" else "--github-env"
            destination = root / "valid-output"
            destination.write_text("keep\n", encoding="utf-8")
            argv = ["bootstrap_openssl.py", "--prefix", str(root / "openssl"),
                    other, str(destination), option, "relative-output"]
            errors = io.StringIO()
            with (patch.object(bootstrap.sys, "argv", argv),
                  patch.object(bootstrap.openssl, "install") as install,
                  redirect_stderr(errors), redirect_stdout(io.StringIO())):
                try:
                    bootstrap.main()
                except SystemExit as error:
                    ensure(error.code == 2, "invalid export destination did not produce a usage error")
                else:
                    raise AssertionError("relative export destination was accepted")
            ensure("GitHub environment files must be absolute" in errors.getvalue(),
                   "invalid export destination was not explained")
            ensure(not install.called, "invalid export destination started the native installation")
            ensure(destination.read_text(encoding="utf-8") == "keep\n",
                   "invalid invocation changed its other export destination")


def _absolute_exports_append_after_installation() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-openssl-bootstrap-") as directory:
        root = Path(directory).resolve()
        prefix = root / "openssl"
        environment, paths = root / "environment", root / "paths"
        for path in (environment, paths):
            path.write_text("keep\n", encoding="utf-8")
        argv = ["bootstrap_openssl.py", "--prefix", str(prefix), "--jobs", "3",
                "--github-env", str(environment), "--github-path", str(paths)]
        with (patch.object(bootstrap.sys, "argv", argv),
              patch.object(bootstrap.openssl, "install", return_value={}) as install,
              redirect_stdout(io.StringIO())):
            ensure(bootstrap.main() == 0, "valid export invocation failed")
        install.assert_called_once_with(prefix, 3)
        expected = "keep\n" + "".join(f"{key}={value}\n"
                                      for key, value in bootstrap.openssl.environment(prefix).items())
        ensure(environment.read_text(encoding="utf-8") == expected,
               "valid environment export did not preserve and append the selected installation")
        ensure(paths.read_text(encoding="utf-8") == f"keep\n{prefix / 'bin'}\n",
               "valid PATH export did not preserve and append the selected binary directory")


def cases() -> list[Case]:
    return [Case("relative export paths refuse before installation", _relative_export_refuses_before_installation),
            Case("absolute exports append after installation", _absolute_exports_append_after_installation)]
